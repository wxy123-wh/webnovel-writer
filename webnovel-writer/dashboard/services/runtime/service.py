"""Runtime profile and migration service."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scripts.data_modules.config import read_project_env_values

OPENAI_BASE_URL_DEFAULT = "https://api.openai.com/v1"
OPENAI_MODEL_DEFAULT = "gpt-4o-mini"
LOCAL_PROVIDER = "local"
LOCAL_MODEL = "local-assist-v1"

DEFAULT_WORKSPACE_ID = "workspace-default"
TARGET_CONTEXT_DIR = ".codex"
CURRENT_PROJECT_POINTER_FILE = ".webnovel-current-project"
_WIN_POSIX_DRIVE_RE = re.compile(r"^/(?P<drive>[a-zA-Z])/(?P<rest>.*)$")
_WIN_WSL_MNT_DRIVE_RE = re.compile(r"^/mnt/(?P<drive>[a-zA-Z])/(?P<rest>.*)$")


class RuntimeServiceError(Exception):
    """P0-3 修复：改为标准异常类定义，避免 @dataclass(slots=True) 与 Exception.__slots__ 在
    Python 3.10+ 中的布局冲突（TypeError: multiple bases have instance lay-out conflict）。
    """

    def __init__(
        self,
        *,
        status_code: int,
        error_code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details

    def __str__(self) -> str:
        return self.message


def get_runtime_profile(*, workspace_id: str | None, project_root: str | None) -> dict[str, Any]:
    root = _resolve_project_root(workspace_id=workspace_id, project_root=project_root)
    workspace_root = _resolve_workspace_root(root)

    pointer_state = _collect_pointer_state(workspace_root=workspace_root)
    legacy_state = _collect_legacy_state(project_root=root, workspace_root=workspace_root)
    migration_preview = _preview_migration(project_root=root, workspace_root=workspace_root)
    generation_state = _collect_generation_state(project_root=root)
    project_state = _collect_project_summary(project_root=root)

    return {
        "runtime_name": "codex",
        "workspace": {
            "workspace_id": _normalize_workspace_id(workspace_id),
            "project_root": str(root),
        },
        "pointer": pointer_state,
        "legacy": legacy_state,
        "generation": generation_state,
        "project": project_state,
        "migration_preview": migration_preview,
    }


def migrate_runtime(*, workspace_id: str | None, project_root: str | None, dry_run: bool) -> dict[str, Any]:
    root = _resolve_project_root(workspace_id=workspace_id, project_root=project_root)
    workspace_root = _resolve_workspace_root(root)
    migrate_fn = _load_migrate_codex_runtime()

    try:
        report = migrate_fn(
            project_root=root,
            dry_run=bool(dry_run),
            workspace_hint=workspace_root,
            persist_report=True,
        )
    except TypeError as exc:
        if "persist_report" in str(exc):
            raise RuntimeServiceError(
                status_code=501,
                error_code="RUNTIME_NOT_IMPLEMENTED",
                message="Runtime migration backend does not support API mode.",
                details={"error": str(exc)},
            ) from exc
        raise
    except FileNotFoundError as exc:
        raise RuntimeServiceError(
            status_code=404,
            error_code="RUNTIME_PROJECT_ROOT_NOT_FOUND",
            message=str(exc),
            details={"project_root": str(root)},
        ) from exc
    except RuntimeServiceError:
        raise
    except Exception as exc:
        raise RuntimeServiceError(
            status_code=500,
            error_code="RUNTIME_MIGRATION_FAILED",
            message="Failed to run codex runtime migration.",
            details={"error": f"{type(exc).__name__}: {exc}"},
        ) from exc

    normalized_report = _normalize_report(report)
    if not normalized_report["report_path"]:
        raise RuntimeServiceError(
            status_code=500,
            error_code="RUNTIME_REPORT_MISSING",
            message="Migration report_path is missing.",
            details={"project_root": str(root)},
        )
    return normalized_report


def _load_migrate_codex_runtime() -> Callable[..., dict[str, Any]]:
    _ensure_scripts_path()
    try:
        from migrations.codex_migration import migrate_codex_runtime
    except Exception as exc:
        raise RuntimeServiceError(
            status_code=501,
            error_code="RUNTIME_NOT_IMPLEMENTED",
            message="Codex migration backend is unavailable in this runtime.",
            details={"error": f"{type(exc).__name__}: {exc}"},
        ) from exc
    return migrate_codex_runtime


def _resolve_project_root(*, workspace_id: str | None, project_root: str | None) -> Path:
    root_hint = (project_root or "").strip() or os.environ.get("WEBNOVEL_PROJECT_ROOT", "").strip()
    if not root_hint:
        raise RuntimeServiceError(
            status_code=501,
            error_code="RUNTIME_NOT_IMPLEMENTED",
            message="Runtime API requires workspace.project_root or WEBNOVEL_PROJECT_ROOT.",
            details={"action": "provide workspace.project_root"},
        )

    root = _normalize_path(root_hint)
    if not root.exists() or not root.is_dir():
        raise RuntimeServiceError(
            status_code=404,
            error_code="RUNTIME_PROJECT_ROOT_NOT_FOUND",
            message="project_root does not exist.",
            details={"project_root": str(root)},
        )
    if not _is_project_root(root):
        raise RuntimeServiceError(
            status_code=400,
            error_code="RUNTIME_PROJECT_ROOT_INVALID",
            message="project_root must contain .webnovel/state.json.",
            details={"project_root": str(root)},
        )

    expected_workspace_id = _workspace_id_for_root(root)
    normalized_workspace_id = _normalize_workspace_id(workspace_id)
    if normalized_workspace_id not in {DEFAULT_WORKSPACE_ID, expected_workspace_id}:
        raise RuntimeServiceError(
            status_code=403,
            error_code="RUNTIME_WORKSPACE_FORBIDDEN",
            message="workspace_id does not match project_root.",
            details={
                "workspace_id": normalized_workspace_id,
                "expected_workspace_id": expected_workspace_id,
            },
        )
    return root


def _normalize_workspace_id(workspace_id: str | None) -> str:
    return (workspace_id or DEFAULT_WORKSPACE_ID).strip() or DEFAULT_WORKSPACE_ID


def _workspace_id_for_root(root: Path) -> str:
    digest = hashlib.sha1(str(root).encode("utf-8")).hexdigest()[:12]
    return f"ws-{digest}"


def _normalize_path(raw: str | Path) -> Path:
    normalized = normalize_windows_path(str(raw)).expanduser()
    if not normalized.is_absolute():
        normalized = Path.cwd().resolve() / normalized
    try:
        return normalized.resolve()
    except Exception:
        return normalized


def _is_project_root(path: Path) -> bool:
    return (path / ".webnovel" / "state.json").is_file()


def _collect_generation_state(*, project_root: Path) -> dict[str, Any]:
    settings = _resolve_generation_settings(project_root=project_root)
    provider = settings["provider"]
    api_key = settings["api_key"]
    configured = provider not in {"", LOCAL_PROVIDER, "stub"} and bool(api_key)
    model = settings["model"]
    base_url = settings["base_url"]
    if provider == LOCAL_PROVIDER:
        model = LOCAL_MODEL
        base_url = ""
    return {
        "provider": provider,
        "configured": configured,
        "skill_draft_available": configured,
        "api_key_configured": bool(api_key),
        "model": model,
        "base_url": base_url,
    }


def _resolve_generation_settings(*, project_root: Path) -> dict[str, str]:
    project_env = read_project_env_values(project_root)
    api_key = _read_generation_value(project_env, "GENERATION_API_KEY", aliases=("OPENAI_API_KEY",))
    provider = _read_generation_value(project_env, "GENERATION_API_TYPE")
    if not provider:
        provider = "openai" if api_key else LOCAL_PROVIDER

    model = _read_generation_value(project_env, "GENERATION_MODEL", aliases=("OPENAI_MODEL",))
    if not model:
        model = OPENAI_MODEL_DEFAULT if api_key else LOCAL_MODEL

    base_url = _read_generation_value(project_env, "GENERATION_BASE_URL", aliases=("OPENAI_BASE_URL",))
    if not base_url and provider != LOCAL_PROVIDER:
        base_url = OPENAI_BASE_URL_DEFAULT

    return {
        "provider": provider,
        "api_key": api_key,
        "model": model,
        "base_url": base_url,
    }


def _read_generation_value(project_env: dict[str, str], key: str, aliases: tuple[str, ...] = ()) -> str:
    """Read a generation-related env value, preferring the project .env file over os.environ.

    This ensures that after a PATCH writes new values to .env, subsequent GETs
    return the freshly-saved values rather than stale os.environ entries.
    os.environ is still used as fallback (important for Docker deployments).
    """
    for candidate in (key, *aliases):
        project_value = str(project_env.get(candidate, "") or "").strip()
        if project_value:
            return project_value
        env_value = str(os.environ.get(candidate, "") or "").strip()
        if env_value:
            return env_value
    return ""


def _collect_project_summary(*, project_root: Path) -> dict[str, str]:
    state_path = project_root / ".webnovel" / "state.json"
    if not state_path.is_file():
        return {"title": "", "genre": "", "current_chapter": ""}

    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"title": "", "genre": "", "current_chapter": ""}

    if not isinstance(payload, dict):
        return {"title": "", "genre": "", "current_chapter": ""}

    project_info = payload.get("project_info")
    progress = payload.get("progress")
    if not isinstance(project_info, dict):
        project_info = {}
    if not isinstance(progress, dict):
        progress = {}

    return {
        "title": str(project_info.get("title") or "").strip(),
        "genre": str(project_info.get("genre") or "").strip(),
        "current_chapter": str(progress.get("current_chapter") if progress.get("current_chapter") is not None else "").strip(),
    }


def _resolve_workspace_root(project_root: Path) -> Path:
    for candidate in (project_root, *project_root.parents):
        if (candidate / TARGET_CONTEXT_DIR).is_dir():
            return candidate
    if project_root.parent != project_root:
        return project_root.parent
    return project_root


def _legacy_context_dir_name() -> str:
    _ensure_scripts_path()
    try:
        from migrations.codex_migration import LEGACY_CONTEXT_DIR as legacy_context_dir
    except Exception:
        return ".legacy"
    return str(legacy_context_dir)


def _collect_pointer_state(*, workspace_root: Path) -> dict[str, Any]:
    codex_pointer = workspace_root / TARGET_CONTEXT_DIR / CURRENT_PROJECT_POINTER_FILE
    legacy_pointer = workspace_root / _legacy_context_dir_name() / CURRENT_PROJECT_POINTER_FILE

    codex_state = _pointer_file_state(codex_pointer)
    legacy_state = _pointer_file_state(legacy_pointer)
    status = _pointer_status(codex=codex_state, legacy=legacy_state)

    return {
        "workspace_root": str(workspace_root),
        "status": status,
        "has_conflict": status == "conflict",
        "codex": codex_state,
        "legacy": legacy_state,
    }


def _pointer_file_state(pointer_path: Path) -> dict[str, Any]:
    state: dict[str, Any] = {
        "path": str(pointer_path),
        "exists": pointer_path.is_file(),
        "target": None,
        "target_exists": None,
        "target_is_project_root": None,
        "read_error": None,
    }
    if not state["exists"]:
        return state

    try:
        raw = pointer_path.read_text(encoding="utf-8").strip()
    except Exception as exc:
        state["read_error"] = f"{type(exc).__name__}: {exc}"
        return state

    if not raw:
        state["target"] = ""
        state["target_exists"] = False
        state["target_is_project_root"] = False
        return state

    target = _resolve_pointer_target(raw=raw, pointer_parent=pointer_path.parent)
    state["target"] = str(target)
    state["target_exists"] = target.exists()
    state["target_is_project_root"] = _is_project_root(target)
    return state


def _resolve_pointer_target(*, raw: str, pointer_parent: Path) -> Path:
    target = normalize_windows_path(raw).expanduser()
    if not target.is_absolute():
        target = pointer_parent / target
    try:
        return target.resolve()
    except Exception:
        return target


def _pointer_status(*, codex: dict[str, Any], legacy: dict[str, Any]) -> str:
    codex_exists = bool(codex.get("exists"))
    legacy_exists = bool(legacy.get("exists"))
    if codex_exists and legacy_exists:
        codex_target = str(codex.get("target") or "")
        legacy_target = str(legacy.get("target") or "")
        if codex_target and legacy_target and _path_key(Path(codex_target)) == _path_key(Path(legacy_target)):
            return "aligned"
        return "conflict"
    if codex_exists:
        return "codex_only"
    if legacy_exists:
        return "legacy_only"
    return "missing"


def _path_key(path: Path) -> str:
    try:
        resolved = path.expanduser().resolve()
    except Exception:
        resolved = path.expanduser()
    return os.path.normcase(str(resolved))


def _collect_legacy_state(*, project_root: Path, workspace_root: Path) -> dict[str, Any]:
    legacy_context_dir = _legacy_context_dir_name()
    workspace_legacy_dir = workspace_root / legacy_context_dir
    project_legacy_dir = project_root / legacy_context_dir
    project_legacy_references_dir = project_legacy_dir / "references"

    return {
        "workspace_legacy_dir": str(workspace_legacy_dir),
        "workspace_legacy_dir_exists": workspace_legacy_dir.is_dir(),
        "project_legacy_dir": str(project_legacy_dir),
        "project_legacy_dir_exists": project_legacy_dir.is_dir(),
        "project_legacy_references_dir": str(project_legacy_references_dir),
        "project_legacy_references_exists": project_legacy_references_dir.is_dir(),
        "project_legacy_reference_files": _count_files(project_legacy_references_dir),
    }


def _count_files(path: Path) -> int:
    if not path.is_dir():
        return 0
    count = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                count += 1
    except Exception:
        return count
    return count


def _preview_migration(*, project_root: Path, workspace_root: Path) -> dict[str, Any]:
    migrate_fn = _load_migrate_codex_runtime()
    try:
        preview_report = migrate_fn(
            project_root=project_root,
            dry_run=True,
            workspace_hint=workspace_root,
            persist_report=False,
        )
    except TypeError as exc:
        if "persist_report" in str(exc):
            raise RuntimeServiceError(
                status_code=501,
                error_code="RUNTIME_NOT_IMPLEMENTED",
                message="Runtime profile preview is unavailable in current migration backend.",
                details={"error": str(exc)},
            ) from exc
        raise
    except RuntimeServiceError:
        raise
    except Exception as exc:
        raise RuntimeServiceError(
            status_code=500,
            error_code="RUNTIME_PROFILE_PREVIEW_FAILED",
            message="Failed to build runtime migration preview.",
            details={"error": f"{type(exc).__name__}: {exc}"},
        ) from exc

    normalized = _normalize_report(preview_report)
    normalized.pop("report_path", None)
    normalized["migratable_items"] = len(normalized["moved"]) + len(normalized["removed"])
    return normalized


def _normalize_report(report: dict[str, Any]) -> dict[str, Any]:
    payload = report if isinstance(report, dict) else {}

    moved_raw = payload.get("moved", [])
    removed_raw = payload.get("removed", [])
    skipped_raw = payload.get("skipped", [])
    warnings_raw = payload.get("warnings", [])

    moved = []
    for item in moved_raw:
        if not isinstance(item, dict):
            continue
        moved.append(
            {
                "kind": str(item.get("kind") or ""),
                "from": str(item.get("from") or ""),
                "to": str(item.get("to") or ""),
                "dry_run": bool(item.get("dry_run", False)),
            }
        )

    removed = []
    for item in removed_raw:
        if not isinstance(item, dict):
            continue
        removed.append(
            {
                "kind": str(item.get("kind") or ""),
                "path": str(item.get("path") or ""),
                "reason": str(item.get("reason") or ""),
                "dry_run": bool(item.get("dry_run", False)),
            }
        )

    skipped = []
    for item in skipped_raw:
        if not isinstance(item, dict):
            continue
        skipped.append(
            {
                "kind": str(item.get("kind") or ""),
                "path": str(item.get("path") or ""),
                "reason": str(item.get("reason") or ""),
            }
        )

    warnings = [str(item) for item in warnings_raw if item is not None]

    return {
        "moved": moved,
        "removed": removed,
        "skipped": skipped,
        "warnings": warnings,
        "created_at": str(payload.get("created_at") or ""),
        "dry_run": bool(payload.get("dry_run", False)),
        "project_root": str(payload.get("project_root") or ""),
        "report_path": str(payload.get("report_path") or ""),
    }


def _ensure_scripts_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[3] / "scripts"
    scripts_dir_str = str(scripts_dir)
    if scripts_dir_str not in sys.path:
        sys.path.insert(0, scripts_dir_str)


def normalize_windows_path(value: str | Path) -> Path:
    if sys.platform != "win32":
        return Path(value)

    raw = str(value).strip()
    if not raw:
        return Path(raw)

    m = _WIN_WSL_MNT_DRIVE_RE.match(raw)
    if m:
        drive = m.group("drive").upper()
        rest = m.group("rest")
        return Path(f"{drive}:/{rest}")

    m = _WIN_POSIX_DRIVE_RE.match(raw)
    if m:
        drive = m.group("drive").upper()
        rest = m.group("rest")
        return Path(f"{drive}:/{rest}")

    return Path(value)
