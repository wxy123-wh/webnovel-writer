"""
Codex CLI bridge router.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from ..models.codex_bridge import (
    CodexFileEditDialogOpenRequest,
    CodexFileEditDialogOpenResponse,
    CodexSplitDialogOpenRequest,
    CodexSplitDialogOpenResponse,
)
from ..models.common import ApiErrorResponse
from ..path_guard import safe_resolve

router = APIRouter(prefix="/api/codex", tags=["codex-bridge"])

WRITE_ERROR_RESPONSES = {
    400: {"model": ApiErrorResponse, "description": "Bad request."},
    403: {"model": ApiErrorResponse, "description": "Workspace path forbidden."},
    404: {"model": ApiErrorResponse, "description": "Project root not found."},
    500: {"model": ApiErrorResponse, "description": "Failed to launch Codex CLI."},
}


def _error_response(status_code: int, error_code: str, message: str, details: dict | None = None) -> JSONResponse:
    payload = ApiErrorResponse(
        error_code=error_code,
        message=message,
        details=details,
        request_id=None,
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def _resolve_project_root(project_root: str) -> Path:
    root_hint = (project_root or "").strip()
    if not root_hint:
        raise ValueError("CODex project_root is required")
    root = Path(root_hint).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(str(root))
    if not (root / ".webnovel" / "state.json").is_file():
        raise ValueError("project_root must contain .webnovel/state.json")
    return root


def _normalize_relative_path(path: str) -> str:
    return str(path or "").replace("\\", "/").strip()


def _resolve_target_file(project_root: Path, file_path: str) -> tuple[str, Path]:
    normalized = _normalize_relative_path(file_path)
    if not normalized:
        raise ValueError("file_path is required")
    try:
        resolved = safe_resolve(project_root, normalized)
    except HTTPException as exc:
        raise PermissionError(str(exc.detail)) from exc
    if not resolved.is_file():
        raise FileNotFoundError(normalized)
    return normalized, resolved


def _has_valid_selection(selection_start: int, selection_end: int, selection_text: str) -> bool:
    return selection_end > selection_start and bool((selection_text or "").strip())


def _powershell_literal(value: str) -> str:
    return value.replace("'", "''")


def _write_prompt_file(project_root: Path, prefix: str, prompt_text: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    prompt_path = project_root / ".webnovel" / "tmp" / f"{prefix}-{timestamp}.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt_text, encoding="utf-8")
    return prompt_path


def _launch_codex(project_root: Path, prompt_path: Path, launch_message: str) -> None:
    prompt_path_ps = _powershell_literal(str(prompt_path))
    launch_message_ps = _powershell_literal(launch_message)
    inner_cmd = (
        f"$prompt = Get-Content -Raw '{prompt_path_ps}'; "
        f"Write-Host '{launch_message_ps}' -ForegroundColor Yellow; "
        "if (Get-Command codex -ErrorAction SilentlyContinue) { "
        "  try { codex $prompt } catch { "
        "    Write-Host 'codex 参数启动失败，切换为交互模式。' -ForegroundColor DarkYellow; codex "
        "  } "
        "} else { "
        "  Write-Host '未检测到 codex 命令，请先安装并加入 PATH。' -ForegroundColor Red "
        "}"
    )

    creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen(
        ["powershell", "-NoExit", "-Command", inner_cmd],
        cwd=str(project_root),
        creationflags=creationflags,
    )


def _build_split_prompt(selection_text: str) -> str:
    return (
        "你是小说大纲拆分助手。\\n"
        "任务：把下面选中的总纲内容，拆分成高可写性的\"场景\"清单。\\n"
        "要求：\\n"
        "1) 必须输出 6-12 个场景，按时间顺序。\\n"
        "2) 每个场景必须包含：场景标题、目标、冲突、转折、结尾钩子。\\n"
        "3) 不要写空话，不要泛化总结，必须引用选中内容中的具体信息。\\n"
        "4) 输出使用中文 Markdown。\\n\\n"
        "【选中的总纲内容】\\n"
        f"{selection_text.strip()}\\n"
    )


def _build_file_edit_prompt(
    *,
    file_path: str,
    target_file: Path,
    selection_start: int,
    selection_end: int,
    selection_text: str,
    instruction: str,
    source_id: str,
) -> str:
    normalized_instruction = instruction.strip() or "请直接改写选中文本，保持设定与事实一致。"
    normalized_source_id = source_id.strip() or "dashboard.text.selection"
    return (
        "你是 Webnovel Writer 项目内的 Codex CLI 编辑助手。\\n"
        "必须直接修改文件，不要只给建议。\\n\\n"
        f"source_id: {normalized_source_id}\\n"
        f"目标文件(相对路径): {file_path}\\n"
        f"目标文件(绝对路径): {target_file}\\n"
        f"选区偏移: [{selection_start}, {selection_end})\\n\\n"
        "任务要求：\\n"
        f"{normalized_instruction}\\n\\n"
        "选中文本（用于定位上下文）：\\n"
        "```text\\n"
        f"{selection_text.strip()}\\n"
        "```\\n\\n"
        "执行要求：\\n"
        "1) 直接编辑并保存目标文件。\\n"
        "2) 仅修改与任务相关的内容，保持其他段落稳定。\\n"
        "3) 完成后简要总结改动点。\\n"
    )


@router.post("/split-dialog/open", response_model=CodexSplitDialogOpenResponse, responses=WRITE_ERROR_RESPONSES)
def open_codex_split_dialog(request: CodexSplitDialogOpenRequest):
    if not _has_valid_selection(request.selection_start, request.selection_end, request.selection_text):
        return _error_response(
            400,
            "CODEX_SPLIT_SELECTION_INVALID",
            "请先在总纲中选中有效文本后再启动 Codex 对话。",
        )

    try:
        project_root = _resolve_project_root(request.workspace.project_root)
    except FileNotFoundError as exc:
        return _error_response(
            404,
            "CODEX_SPLIT_PROJECT_ROOT_NOT_FOUND",
            "workspace.project_root does not exist",
            {"project_root": str(exc)},
        )
    except ValueError as exc:
        return _error_response(
            400,
            "CODEX_SPLIT_PROJECT_ROOT_INVALID",
            str(exc),
            {"project_root": request.workspace.project_root},
        )

    prompt_text = _build_split_prompt(request.selection_text)
    prompt_path = _write_prompt_file(project_root, "codex-outline-split", prompt_text)

    try:
        _launch_codex(
            project_root=project_root,
            prompt_path=prompt_path,
            launch_message="已加载拆分提示词，正在启动 Codex CLI...",
        )
    except Exception as exc:
        return _error_response(
            500,
            "CODEX_SPLIT_LAUNCH_FAILED",
            "启动 Codex CLI 对话失败",
            {"error": f"{type(exc).__name__}: {exc}"},
        )

    return CodexSplitDialogOpenResponse(
        status="ok",
        launched=True,
        message="Codex CLI 对话窗口已启动",
        prompt_file=str(prompt_path),
    )


@router.post("/file-edit/open", response_model=CodexFileEditDialogOpenResponse, responses=WRITE_ERROR_RESPONSES)
def open_codex_file_edit_dialog(request: CodexFileEditDialogOpenRequest):
    if not _has_valid_selection(request.selection_start, request.selection_end, request.selection_text):
        return _error_response(
            400,
            "CODEX_FILE_EDIT_SELECTION_INVALID",
            "请先选中有效文本后再启动 Codex 文件编辑。",
        )

    try:
        project_root = _resolve_project_root(request.workspace.project_root)
    except FileNotFoundError as exc:
        return _error_response(
            404,
            "CODEX_FILE_EDIT_PROJECT_ROOT_NOT_FOUND",
            "workspace.project_root does not exist",
            {"project_root": str(exc)},
        )
    except ValueError as exc:
        return _error_response(
            400,
            "CODEX_FILE_EDIT_PROJECT_ROOT_INVALID",
            str(exc),
            {"project_root": request.workspace.project_root},
        )

    try:
        normalized_file_path, target_file = _resolve_target_file(project_root, request.file_path)
    except ValueError:
        return _error_response(
            400,
            "CODEX_FILE_EDIT_FILE_PATH_REQUIRED",
            "file_path is required",
        )
    except PermissionError as exc:
        return _error_response(
            403,
            "CODEX_FILE_EDIT_PATH_FORBIDDEN",
            "file_path is outside project_root",
            {"file_path": request.file_path, "detail": str(exc)},
        )
    except FileNotFoundError:
        return _error_response(
            404,
            "CODEX_FILE_EDIT_TARGET_NOT_FOUND",
            "target file does not exist",
            {"file_path": request.file_path},
        )

    prompt_text = _build_file_edit_prompt(
        file_path=normalized_file_path,
        target_file=target_file,
        selection_start=request.selection_start,
        selection_end=request.selection_end,
        selection_text=request.selection_text,
        instruction=request.instruction,
        source_id=request.source_id,
    )
    prompt_path = _write_prompt_file(project_root, "codex-file-edit", prompt_text)

    try:
        _launch_codex(
            project_root=project_root,
            prompt_path=prompt_path,
            launch_message="已加载文件修改任务，正在启动 Codex CLI...",
        )
    except Exception as exc:
        return _error_response(
            500,
            "CODEX_FILE_EDIT_LAUNCH_FAILED",
            "启动 Codex CLI 文件修改失败",
            {"error": f"{type(exc).__name__}: {exc}"},
        )

    return CodexFileEditDialogOpenResponse(
        status="ok",
        launched=True,
        message="Codex CLI 文件修改对话已启动",
        prompt_file=str(prompt_path),
        target_file=normalized_file_path,
    )
