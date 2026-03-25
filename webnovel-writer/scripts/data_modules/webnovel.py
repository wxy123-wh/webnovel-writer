#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
webnovel 统一入口（面向 skills / agents / Codex 的稳定 CLI）

设计目标：
- 只有一个入口命令，避免到处拼 `python -m data_modules.xxx ...` 导致参数位置/引号/路径炸裂。
- 自动解析正确的 book project_root（包含 `.webnovel/state.json` 的目录）。
- 所有写入类命令在解析到 project_root 后，统一前置 `--project-root` 传给具体模块。

典型用法（推荐，不依赖 PYTHONPATH / 不要求 cd）：
  python "<SCRIPTS_DIR>/webnovel.py" preflight
  python "<SCRIPTS_DIR>/webnovel.py" where
  python "<SCRIPTS_DIR>/webnovel.py" use D:\\wk\\xiaoshuo\\凡人资本论
  python "<SCRIPTS_DIR>/webnovel.py" --project-root D:\\wk\\xiaoshuo index stats
  python "<SCRIPTS_DIR>/webnovel.py" --project-root D:\\wk\\xiaoshuo state process-chapter --chapter 100 --data @payload.json
  python "<SCRIPTS_DIR>/webnovel.py" --project-root D:\\wk\\xiaoshuo extract-context --chapter 100 --format json

也支持（不推荐，容易踩 PYTHONPATH/cd/参数顺序坑）：
  python -m data_modules.webnovel where
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from runtime_compat import normalize_windows_path
from project_locator import (
    CURRENT_PROJECT_POINTER_FILE,
    POINTER_DIR_NAMES,
    _global_registry_paths,
    _load_global_registry,
    _normcase_path_key,
    resolve_project_root,
    update_global_registry_current_project,
    write_current_project_pointer,
)


USE_EXIT_OK = 0
USE_EXIT_INVALID_PROJECT_ROOT = 2
USE_EXIT_REGISTRY_FAILED = 3


def _normalize_path(raw: str | Path) -> Path:
    p = normalize_windows_path(str(raw)).expanduser()
    try:
        return p.resolve()
    except Exception:
        return p


def _is_project_root(path: Path) -> bool:
    return (path / ".webnovel" / "state.json").is_file()


def _find_workspace_root_with_context_dir(start: Path) -> Optional[Path]:
    for candidate in (start, *start.parents):
        for dirname in POINTER_DIR_NAMES:
            if (candidate / dirname).is_dir():
                return candidate
    return None


def _first_context_dir(workspace_root: Optional[Path]) -> Optional[Path]:
    if workspace_root is None:
        return None
    for dirname in POINTER_DIR_NAMES:
        candidate = workspace_root / dirname
        if candidate.is_dir():
            return candidate
    return None


def _resolve_workspace_root_for_binding(
    *,
    project_root: Optional[Path],
    explicit_workspace_root: Optional[Path],
) -> Optional[Path]:
    if explicit_workspace_root is not None:
        return _normalize_path(explicit_workspace_root)

    if project_root is not None:
        ws = _find_workspace_root_with_context_dir(project_root)
        if ws is not None:
            return ws.resolve()

    cwd = Path.cwd().resolve()
    ws_from_cwd = _find_workspace_root_with_context_dir(cwd)
    if ws_from_cwd is not None:
        return ws_from_cwd.resolve()

    if project_root is not None and project_root.parent != project_root:
        return project_root.parent
    return None


def _path_eq(a: Path, b: Path) -> bool:
    return _normcase_path_key(a) == _normcase_path_key(b)


def _pointer_skip_detail(*, reason: str, workspace_root: Optional[Path]) -> tuple[str, str]:
    if reason == "context_dir_missing":
        if workspace_root is None:
            return reason, "create <workspace>/.codex and rerun `webnovel use ... --workspace-root <workspace>`"
        return reason, f"create {workspace_root / '.codex'} and rerun `webnovel use ... --workspace-root {workspace_root}`"
    if reason == "workspace_root_unavailable":
        return reason, "pass --workspace-root <workspace> to `webnovel use`"
    if reason == "pointer_write_failed":
        return reason, "check write permissions for workspace context dir and rerun"
    return reason, "rerun `webnovel use` after fixing workspace context"


def _inspect_pointer_state(project_root: Optional[Path], workspace_root: Optional[Path]) -> dict[str, object]:
    result: dict[str, object] = {
        "ok": False,
        "status": "skipped",
        "path": "",
        "reason": "",
        "suggestion": "",
        "target": "",
    }
    project_label = str(project_root) if project_root is not None else "<project_root>"
    workspace_label = str(workspace_root) if workspace_root is not None else "<workspace>"

    if project_root is None:
        result["reason"] = "project_root_unresolved"
        result["suggestion"] = "fix project_root first"
        return result

    if workspace_root is None:
        reason, suggestion = _pointer_skip_detail(reason="workspace_root_unavailable", workspace_root=None)
        result["reason"] = reason
        result["suggestion"] = suggestion
        return result

    context_dir = _first_context_dir(workspace_root)
    if context_dir is None:
        reason, suggestion = _pointer_skip_detail(reason="context_dir_missing", workspace_root=workspace_root)
        result["reason"] = reason
        result["suggestion"] = suggestion
        return result

    pointer_file = context_dir / CURRENT_PROJECT_POINTER_FILE
    result["path"] = str(pointer_file)
    if not pointer_file.is_file():
        result["status"] = "missing"
        result["reason"] = "pointer_file_missing"
        result["suggestion"] = f"run `webnovel use {project_label} --workspace-root {workspace_label}`"
        return result

    try:
        raw = pointer_file.read_text(encoding="utf-8").strip()
    except Exception as exc:
        result["status"] = "error"
        result["reason"] = f"pointer_read_failed:{type(exc).__name__}"
        result["suggestion"] = "check pointer file permissions/encoding"
        return result

    if not raw:
        result["status"] = "error"
        result["reason"] = "pointer_empty"
        result["suggestion"] = f"run `webnovel use {project_label} --workspace-root {workspace_label}`"
        return result

    target = _normalize_path(raw) if Path(raw).is_absolute() else _normalize_path(pointer_file.parent / raw)
    result["target"] = str(target)
    if not _is_project_root(target):
        result["status"] = "error"
        result["reason"] = "pointer_target_invalid"
        result["suggestion"] = f"run `webnovel use {project_label} --workspace-root {workspace_label}`"
        return result

    if not _path_eq(target, project_root):
        result["status"] = "error"
        result["reason"] = "pointer_target_mismatch"
        result["suggestion"] = f"run `webnovel use {project_label} --workspace-root {workspace_label}`"
        return result

    result["ok"] = True
    result["status"] = "valid"
    result["reason"] = ""
    result["suggestion"] = ""
    return result


def _inspect_registry_state(project_root: Optional[Path], workspace_root: Optional[Path]) -> dict[str, object]:
    result: dict[str, object] = {
        "ok": False,
        "status": "missing",
        "path": "",
        "reason": "",
        "suggestion": "",
        "mapped_project_root": "",
    }
    project_label = str(project_root) if project_root is not None else "<project_root>"
    workspace_label = str(workspace_root) if workspace_root is not None else "<workspace>"

    registry_candidates = _global_registry_paths()
    if not registry_candidates:
        result["status"] = "error"
        result["reason"] = "registry_path_unavailable"
        result["suggestion"] = "set CODEX_HOME/CLAUDE_HOME and rerun preflight"
        return result

    existing_files = [path for path in registry_candidates if path.is_file()]
    inspect_path = existing_files[0] if existing_files else registry_candidates[0]
    result["path"] = str(inspect_path)

    if workspace_root is None:
        result["status"] = "skipped"
        result["reason"] = "workspace_root_unavailable"
        result["suggestion"] = "pass --project-root <workspace> or run preflight inside workspace"
        return result

    ws_key = _normcase_path_key(workspace_root)
    for reg_path in existing_files:
        data = _load_global_registry(reg_path)
        workspaces = data.get("workspaces")
        if not isinstance(workspaces, dict):
            continue
        entry = workspaces.get(ws_key)
        if not isinstance(entry, dict):
            continue

        result["path"] = str(reg_path)
        mapped = entry.get("current_project_root")
        if not isinstance(mapped, str) or not mapped.strip():
            result["status"] = "error"
            result["reason"] = "registry_entry_invalid"
            result["suggestion"] = f"run `webnovel use {project_label} --workspace-root {workspace_label}`"
            return result

        target = _normalize_path(mapped)
        result["mapped_project_root"] = str(target)
        if not _is_project_root(target):
            result["status"] = "error"
            result["reason"] = "registry_target_invalid"
            result["suggestion"] = f"run `webnovel use {project_label} --workspace-root {workspace_label}`"
            return result

        if project_root is not None and not _path_eq(target, project_root):
            result["status"] = "error"
            result["reason"] = "registry_target_mismatch"
            result["suggestion"] = f"run `webnovel use {project_label} --workspace-root {workspace_label}`"
            return result

        result["ok"] = True
        result["status"] = "valid"
        result["reason"] = ""
        result["suggestion"] = ""
        return result

    if not existing_files:
        result["status"] = "missing"
        result["reason"] = "registry_file_missing"
        result["suggestion"] = f"run `webnovel use {project_label} --workspace-root {workspace_label}`"
        return result

    result["status"] = "missing"
    result["reason"] = "workspace_unregistered"
    result["suggestion"] = f"run `webnovel use {project_label} --workspace-root {workspace_label}`"
    return result


def _binding_check_item(name: str, detail: dict[str, object], *, required: bool = False) -> dict[str, object]:
    item: dict[str, object] = {
        "name": name,
        "ok": bool(detail.get("ok")),
        "required": bool(required),
        "path": str(detail.get("path") or ""),
        "status": str(detail.get("status") or ""),
    }
    reason = str(detail.get("reason") or "")
    suggestion = str(detail.get("suggestion") or "")
    if reason:
        item["reason"] = reason
    if suggestion:
        item["suggestion"] = suggestion
    target = str(detail.get("target") or "")
    if target:
        item["target"] = target
    mapped = str(detail.get("mapped_project_root") or "")
    if mapped:
        item["mapped_project_root"] = mapped
    return item


def _scripts_dir() -> Path:
    # data_modules/webnovel.py -> data_modules -> scripts
    return Path(__file__).resolve().parent.parent


def _resolve_root(explicit_project_root: Optional[str]) -> Path:
    # 允许显式传入工作区根目录或书项目根目录
    raw = explicit_project_root
    if raw:
        return resolve_project_root(raw)
    return resolve_project_root()


def _is_extract_context_root(path: Path) -> bool:
    return any((path / marker).exists() for marker in (".webnovel", "正文", "大纲"))


def _resolve_root_for_extract_context(explicit_project_root: Optional[str]) -> Path:
    """
    extract-context 允许在 state.json 缺失时降级执行，
    由子脚本输出结构化警告而非直接中断。
    """
    try:
        return _resolve_root(explicit_project_root)
    except Exception:
        pass

    if explicit_project_root:
        candidate = _normalize_path(explicit_project_root)
        if not candidate.exists():
            raise FileNotFoundError(f"extract-context project_root 不存在: {candidate}")
        if _is_extract_context_root(candidate):
            return candidate
        raise FileNotFoundError(
            "extract-context project_root 无效（需包含 .webnovel/ 或 正文/ 或 大纲/）: "
            f"{candidate}"
        )

    cwd = Path.cwd().resolve()
    if _is_extract_context_root(cwd):
        return cwd
    return _resolve_root(explicit_project_root)


def _strip_project_root_args(argv: list[str]) -> list[str]:
    """
    下游工具统一由本入口注入 `--project-root`，避免重复传参导致 argparse 报错/歧义。
    """
    out: list[str] = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == "--project-root":
            i += 2
            continue
        if tok.startswith("--project-root="):
            i += 1
            continue
        out.append(tok)
        i += 1
    return out


def _run_data_module(module: str, argv: list[str]) -> int:
    """
    Import `data_modules.<module>` and call its main(), while isolating sys.argv.
    """
    mod = importlib.import_module(f"data_modules.{module}")
    main = getattr(mod, "main", None)
    if not callable(main):
        raise RuntimeError(f"data_modules.{module} 缺少可调用的 main()")

    old_argv = sys.argv
    try:
        sys.argv = [f"data_modules.{module}"] + argv
        try:
            main()
            return 0
        except SystemExit as e:
            return int(e.code or 0)
    finally:
        sys.argv = old_argv


def _run_script(script_name: str, argv: list[str]) -> int:
    """
    Run a script under `scripts/` via a subprocess.

    用途：兼容没有 main() 的脚本（例如 workflow_manager.py）。
    """
    script_path = _scripts_dir() / script_name
    if not script_path.is_file():
        raise FileNotFoundError(f"未找到脚本: {script_path}")
    proc = subprocess.run([sys.executable, str(script_path), *argv])
    return int(proc.returncode or 0)


def cmd_where(args: argparse.Namespace) -> int:
    try:
        root = _resolve_root(args.project_root)
    except Exception as exc:
        print(f"ERROR project_root: {exc}", file=sys.stderr)
        return 1
    print(str(root))
    return 0


def _build_preflight_report(explicit_project_root: Optional[str]) -> dict:
    scripts_dir = _scripts_dir().resolve()
    plugin_root = scripts_dir.parent
    skill_root = plugin_root / "skills" / "webnovel-write"
    entry_script = scripts_dir / "webnovel.py"
    extract_script = scripts_dir / "extract_chapter_context.py"

    checks: list[dict[str, object]] = [
        {"name": "scripts_dir", "ok": scripts_dir.is_dir(), "path": str(scripts_dir)},
        {"name": "entry_script", "ok": entry_script.is_file(), "path": str(entry_script)},
        {"name": "extract_context_script", "ok": extract_script.is_file(), "path": str(extract_script)},
        {"name": "skill_root", "ok": skill_root.is_dir(), "path": str(skill_root)},
    ]

    project_root = ""
    project_root_error = ""
    resolved_root: Optional[Path] = None
    try:
        resolved_root = _resolve_root(explicit_project_root)
        project_root = str(resolved_root)
        checks.append({"name": "project_root", "ok": True, "required": True, "path": project_root})
    except Exception as exc:
        project_root_error = str(exc)
        checks.append(
            {
                "name": "project_root",
                "ok": False,
                "required": True,
                "path": explicit_project_root or "",
                "error": project_root_error,
            }
        )

    explicit_hint: Optional[Path] = None
    if explicit_project_root:
        explicit_hint = _normalize_path(explicit_project_root)
    workspace_root = _resolve_workspace_root_for_binding(
        project_root=resolved_root,
        explicit_workspace_root=explicit_hint,
    )
    pointer_state = _inspect_pointer_state(resolved_root, workspace_root)
    registry_state = _inspect_registry_state(resolved_root, workspace_root)
    root_state = {
        "ok": bool(resolved_root is not None),
        "status": "valid" if resolved_root is not None else "invalid",
        "path": project_root if resolved_root is not None else (explicit_project_root or ""),
        "reason": "" if resolved_root is not None else "project_root_unresolved",
        "suggestion": "" if resolved_root is not None else "run `webnovel where --project-root <project_root>` to diagnose",
    }

    checks.append(_binding_check_item("root_state", root_state, required=True))
    checks.append(_binding_check_item("workspace_pointer", pointer_state, required=False))
    checks.append(_binding_check_item("global_registry", registry_state, required=False))

    return {
        "ok": all(bool(item["ok"]) for item in checks if bool(item.get("required", True))),
        "project_root": project_root,
        "scripts_dir": str(scripts_dir),
        "skill_root": str(skill_root),
        "workspace_root": str(workspace_root) if workspace_root is not None else "",
        "binding": {
            "project_root": root_state,
            "pointer": pointer_state,
            "registry": registry_state,
        },
        "checks": checks,
        "project_root_error": project_root_error,
    }


def cmd_preflight(args: argparse.Namespace) -> int:
    report = _build_preflight_report(args.project_root)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for item in report["checks"]:
            required = bool(item.get("required", True))
            if item["ok"]:
                status = "OK"
            else:
                status = "ERROR" if required else "WARN"
            path = item.get("path") or ""
            status_detail = item.get("status")
            if status_detail:
                print(f"{status} {item['name']} ({status_detail}): {path}")
            else:
                print(f"{status} {item['name']}: {path}")
            if item.get("error"):
                print(f"  detail: {item['error']}")
            if item.get("reason"):
                print(f"  reason: {item['reason']}")
            if item.get("target"):
                print(f"  target: {item['target']}")
            if item.get("mapped_project_root"):
                print(f"  mapped_project_root: {item['mapped_project_root']}")
            if item.get("suggestion"):
                print(f"  action: {item['suggestion']}")
    return 0 if report["ok"] else 1


def cmd_use(args: argparse.Namespace) -> int:
    project_root = _normalize_path(args.project_root)
    if not _is_project_root(project_root):
        print(
            f"ERROR project_root: Not a webnovel project root (missing .webnovel/state.json): {project_root}",
            file=sys.stderr,
        )
        return USE_EXIT_INVALID_PROJECT_ROOT

    explicit_workspace_root: Optional[Path] = None
    if args.workspace_root:
        explicit_workspace_root = _normalize_path(args.workspace_root)
    workspace_root = _resolve_workspace_root_for_binding(
        project_root=project_root,
        explicit_workspace_root=explicit_workspace_root,
    )

    context_dir = _first_context_dir(workspace_root)
    pointer_file: Optional[Path] = None
    pointer_reason = ""
    pointer_action = ""
    if context_dir is None:
        pointer_reason, pointer_action = _pointer_skip_detail(reason="context_dir_missing", workspace_root=workspace_root)
    else:
        try:
            pointer_file = write_current_project_pointer(project_root, workspace_root=workspace_root)
        except Exception:
            pointer_file = None
        if pointer_file is None:
            pointer_reason, pointer_action = _pointer_skip_detail(reason="pointer_write_failed", workspace_root=workspace_root)

    if pointer_file is not None:
        print(f"workspace pointer: {pointer_file}")
    else:
        if not pointer_reason:
            pointer_reason, pointer_action = _pointer_skip_detail(
                reason="workspace_root_unavailable",
                workspace_root=workspace_root,
            )
        print(f"workspace pointer: (skipped: reason={pointer_reason}; action={pointer_action})")

    try:
        reg_path = update_global_registry_current_project(workspace_root=workspace_root, project_root=project_root)
    except Exception as exc:
        print(
            f"global registry: (error: reason=write_failed:{type(exc).__name__}; "
            "action=check registry path permissions and rerun)",
            file=sys.stderr,
        )
        return USE_EXIT_REGISTRY_FAILED

    if reg_path is not None:
        print(f"global registry: {reg_path}")
        return USE_EXIT_OK

    print("global registry: (skipped: reason=workspace_root_unavailable; action=pass --workspace-root <workspace>)")
    return USE_EXIT_REGISTRY_FAILED


def cmd_dashboard(args: argparse.Namespace) -> int:
    """从统一 CLI 启动 Dashboard（适配 Codex/Claude 任意工作目录）。"""
    project_root = _resolve_root(args.project_root)
    plugin_root = _scripts_dir().parent

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    if existing_pythonpath:
        env["PYTHONPATH"] = f"{plugin_root}{os.pathsep}{existing_pythonpath}"
    else:
        env["PYTHONPATH"] = str(plugin_root)

    cmd = [
        sys.executable,
        "-m",
        "dashboard.server",
        "--project-root",
        str(project_root),
        "--host",
        str(args.host),
        "--port",
        str(args.port),
    ]
    if args.no_browser:
        cmd.append("--no-browser")
    if args.no_bootstrap_index:
        cmd.append("--no-bootstrap-index")

    proc = subprocess.run(cmd, cwd=str(plugin_root), env=env)
    return int(proc.returncode or 0)


def _parse_migrate_codex_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="webnovel migrate codex",
        description="迁移历史 .claude 痕迹到 .codex 优先路径",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅生成迁移报告，不实际改动文件")
    return parser.parse_args(argv)


def _resolve_workspace_hint(explicit_project_root: Optional[str]) -> Optional[Path]:
    if not explicit_project_root:
        return None
    hint = normalize_windows_path(explicit_project_root).expanduser()
    if not hint.is_absolute():
        hint = (Path.cwd().resolve() / hint).resolve()
    else:
        hint = hint.resolve()
    return hint


def _run_codex_migration(*, project_root: Path, dry_run: bool, workspace_hint: Optional[Path]) -> int:
    from migrations.codex_migration import migrate_codex_runtime

    report = migrate_codex_runtime(
        project_root=project_root,
        dry_run=dry_run,
        workspace_hint=workspace_hint,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="webnovel unified CLI")
    parser.add_argument("--project-root", help="书项目根目录或工作区根目录（可选，默认自动检测）")

    sub = parser.add_subparsers(dest="tool", required=True)

    p_where = sub.add_parser("where", help="打印解析出的 project_root")
    p_where.set_defaults(func=cmd_where)

    p_preflight = sub.add_parser("preflight", help="校验统一 CLI 运行环境与 project_root")
    p_preflight.add_argument("--format", choices=["text", "json"], default="text", help="输出格式")
    p_preflight.set_defaults(func=cmd_preflight)

    p_use = sub.add_parser("use", help="绑定当前工作区使用的书项目（写入指针/registry）")
    p_use.add_argument("project_root", help="书项目根目录（必须包含 .webnovel/state.json）")
    p_use.add_argument("--workspace-root", help="工作区根目录（可选；默认由运行环境推断）")
    p_use.set_defaults(func=cmd_use)

    p_dashboard = sub.add_parser("dashboard", help="启动只读 Dashboard（自动解析 project_root）")
    p_dashboard.add_argument("--host", default="127.0.0.1", help="监听地址")
    p_dashboard.add_argument("--port", type=int, default=8765, help="监听端口")
    p_dashboard.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    p_dashboard.add_argument(
        "--no-bootstrap-index",
        action="store_true",
        help="不自动初始化缺失的 .webnovel/index.db",
    )
    p_dashboard.set_defaults(func=cmd_dashboard)

    # Pass-through to data modules
    p_index = sub.add_parser("index", help="转发到 index_manager")
    p_index.add_argument("args", nargs=argparse.REMAINDER)

    p_state = sub.add_parser("state", help="转发到 state_manager")
    p_state.add_argument("args", nargs=argparse.REMAINDER)

    p_rag = sub.add_parser("rag", help="转发到 rag_adapter")
    p_rag.add_argument("args", nargs=argparse.REMAINDER)

    p_style = sub.add_parser("style", help="转发到 style_sampler")
    p_style.add_argument("args", nargs=argparse.REMAINDER)

    p_entity = sub.add_parser("entity", help="转发到 entity_linker")
    p_entity.add_argument("args", nargs=argparse.REMAINDER)

    p_context = sub.add_parser("context", help="转发到 context_manager")
    p_context.add_argument("args", nargs=argparse.REMAINDER)

    p_migrate = sub.add_parser("migrate", help="迁移工具（支持 `migrate codex` 与旧透传模式）")
    p_migrate.add_argument("args", nargs=argparse.REMAINDER)

    # Pass-through to scripts
    p_workflow = sub.add_parser("workflow", help="转发到 workflow_manager.py")
    p_workflow.add_argument("args", nargs=argparse.REMAINDER)

    p_status = sub.add_parser("status", help="转发到 status_reporter.py")
    p_status.add_argument("args", nargs=argparse.REMAINDER)

    p_update_state = sub.add_parser("update-state", help="转发到 update_state.py")
    p_update_state.add_argument("args", nargs=argparse.REMAINDER)

    p_backup = sub.add_parser("backup", help="转发到 backup_manager.py")
    p_backup.add_argument("args", nargs=argparse.REMAINDER)

    p_archive = sub.add_parser("archive", help="转发到 archive_manager.py")
    p_archive.add_argument("args", nargs=argparse.REMAINDER)

    p_init = sub.add_parser("init", help="转发到 init_project.py（初始化项目）")
    p_init.add_argument("args", nargs=argparse.REMAINDER)

    p_extract_context = sub.add_parser(
        "extract-context",
        help="提取章节上下文（章节缺失报错，state 缺失给出警告）",
    )
    p_extract_context.add_argument(
        "--chapter",
        type=int,
        required=True,
        help="目标章节号（必须可在正文目录定位到对应章节文件）",
    )
    p_extract_context.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="输出格式：text=可读摘要，json=结构化数据",
    )

    # 兼容：允许 `--project-root` 出现在任意位置（减少 agents/skills 拼命令的出错率）
    from .cli_args import normalize_global_project_root

    argv = normalize_global_project_root(sys.argv[1:])
    args = parser.parse_args(argv)

    # where/use 直接执行
    if hasattr(args, "func"):
        code = int(args.func(args) or 0)
        raise SystemExit(code)

    tool = args.tool
    rest = list(getattr(args, "args", []) or [])
    # argparse.REMAINDER 可能以 `--` 开头占位，这里去掉
    if rest[:1] == ["--"]:
        rest = rest[1:]
    rest = _strip_project_root_args(rest)

    # init 是创建项目，不应该依赖/注入已存在 project_root
    if tool == "init":
        raise SystemExit(_run_script("init_project.py", rest))

    if tool == "extract-context":
        try:
            project_root = _resolve_root_for_extract_context(args.project_root)
        except Exception as exc:
            print(f"ERROR project_root (extract-context): {exc}", file=sys.stderr)
            raise SystemExit(1)
        return_args = [
            "--project-root",
            str(project_root),
            "--chapter",
            str(args.chapter),
            "--format",
            str(args.format),
        ]
        raise SystemExit(_run_script("extract_chapter_context.py", return_args))

    # 其余工具：统一解析 project_root 后前置给下游
    project_root = _resolve_root(args.project_root)
    forward_args = ["--project-root", str(project_root)]

    if tool == "index":
        raise SystemExit(_run_data_module("index_manager", [*forward_args, *rest]))
    if tool == "state":
        raise SystemExit(_run_data_module("state_manager", [*forward_args, *rest]))
    if tool == "rag":
        raise SystemExit(_run_data_module("rag_adapter", [*forward_args, *rest]))
    if tool == "style":
        raise SystemExit(_run_data_module("style_sampler", [*forward_args, *rest]))
    if tool == "entity":
        raise SystemExit(_run_data_module("entity_linker", [*forward_args, *rest]))
    if tool == "context":
        raise SystemExit(_run_data_module("context_manager", [*forward_args, *rest]))
    if tool == "migrate":
        if rest[:1] == ["codex"]:
            codex_args = _parse_migrate_codex_args(rest[1:])
            workspace_hint = _resolve_workspace_hint(args.project_root)
            raise SystemExit(
                _run_codex_migration(
                    project_root=project_root,
                    dry_run=bool(codex_args.dry_run),
                    workspace_hint=workspace_hint,
                )
            )
        raise SystemExit(_run_data_module("migrate_state_to_sqlite", [*forward_args, *rest]))

    if tool == "workflow":
        raise SystemExit(_run_script("workflow_manager.py", [*forward_args, *rest]))
    if tool == "status":
        raise SystemExit(_run_script("status_reporter.py", [*forward_args, *rest]))
    if tool == "update-state":
        raise SystemExit(_run_script("update_state.py", [*forward_args, *rest]))
    if tool == "backup":
        raise SystemExit(_run_script("backup_manager.py", [*forward_args, *rest]))
    if tool == "archive":
        raise SystemExit(_run_script("archive_manager.py", [*forward_args, *rest]))
    raise SystemExit(2)


if __name__ == "__main__":
    main()
