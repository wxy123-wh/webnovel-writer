#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from .session_manager import SessionManager
except ImportError:  # pragma: no cover
    from session_manager import SessionManager

try:
    from pipeline.orchestrator import PipelineOrchestrator
    from pipeline.models import STAGE_SEQUENCE
except ImportError:  # pragma: no cover
    from scripts.pipeline.orchestrator import PipelineOrchestrator
    from scripts.pipeline.models import STAGE_SEQUENCE


def _resolve_project_root(explicit_root: str | None) -> Path:
    if explicit_root:
        root = Path(explicit_root).expanduser().resolve()
        if not (root / ".webnovel" / "state.json").exists():
            raise FileNotFoundError(f"项目根目录无效（缺少 .webnovel/state.json）: {root}")
        return root

    cwd = Path.cwd()
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".webnovel" / "state.json").exists():
            return candidate
    raise FileNotFoundError("无法找到项目根目录，请使用 --project-root 指定")


def _emit(payload: dict[str, object], *, exit_code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


def _activate_profile(profile: str | None) -> tuple[str | None, str | None]:
    if not profile:
        return None, None

    SessionManager.validate_profile(profile)
    previous = os.environ.get("WEBNOVEL_AGENT_PROFILE")
    os.environ["WEBNOVEL_AGENT_PROFILE"] = profile
    return profile, previous


def _restore_profile(previous: str | None) -> None:
    if previous is None:
        os.environ.pop("WEBNOVEL_AGENT_PROFILE", None)
    else:
        os.environ["WEBNOVEL_AGENT_PROFILE"] = previous


def cmd_session_start(args: argparse.Namespace) -> int:
    try:
        project_root = _resolve_project_root(args.project_root)
        SessionManager.validate_profile(args.profile)
        manager = SessionManager(project_root)
        session_id = manager.create_session(args.profile)
        return _emit(
            {
                "status": "ok",
                "session_id": session_id,
                "profile": args.profile,
                "project_root": str(project_root),
                "message": f"agent 会话已启动: {session_id}",
            }
        )
    except Exception as exc:
        return _emit({"status": "error", "error_code": "agent_session_start_failed", "message": str(exc)}, exit_code=1)


def cmd_session_stop(args: argparse.Namespace) -> int:
    try:
        project_root = _resolve_project_root(args.project_root)
        manager = SessionManager(project_root)
        manager.destroy_session(args.session_id)
        return _emit({"status": "ok", "session_id": args.session_id, "message": f"agent 会话已停止: {args.session_id}"})
    except Exception as exc:
        return _emit({"status": "error", "error_code": "agent_session_stop_failed", "message": str(exc)}, exit_code=1)


def cmd_run(args: argparse.Namespace) -> int:
    session_id: str | None = None
    created_session = False
    previous_profile: str | None = None
    try:
        project_root = _resolve_project_root(args.project_root)
        profile = args.profile
        if args.session_id:
            info = SessionManager(project_root).get_session_info(args.session_id)
            profile = str(info.get("profile") or profile or "") or None
            session_id = args.session_id
        elif profile:
            manager = SessionManager(project_root)
            session_id = manager.create_session(profile)
            created_session = True

        _, previous_profile = _activate_profile(profile)

        orchestrator = PipelineOrchestrator(project_root)
        run = orchestrator.start_run(args.chapter)
        for stage in STAGE_SEQUENCE:
            run = orchestrator.generate_stage(run.run_id, stage)
            run = orchestrator.accept_stage(run.run_id, stage)
        if args.publish:
            run = orchestrator.publish_chapter(run.run_id)

        payload: dict[str, object] = {
            "status": "ok",
            "project_root": str(project_root),
            "session_id": session_id,
            "run": run.to_dict(include_content=True),
        }
        return _emit(payload)
    except Exception as exc:
        return _emit({"status": "error", "error_code": "agent_run_failed", "message": str(exc)}, exit_code=1)
    finally:
        _restore_profile(previous_profile)
        if created_session and session_id and args.cleanup_session:
            try:
                SessionManager(_resolve_project_root(args.project_root)).destroy_session(session_id)
            except Exception:
                pass


def cmd_get_run(args: argparse.Namespace) -> int:
    try:
        project_root = _resolve_project_root(args.project_root)
        run = PipelineOrchestrator(project_root).get_run(args.run_id)
        return _emit({"status": "ok", "run": run.to_dict(include_content=True)})
    except Exception as exc:
        return _emit({"status": "error", "error_code": "agent_get_run_failed", "message": str(exc)}, exit_code=1)


def cmd_latest_run(args: argparse.Namespace) -> int:
    try:
        project_root = _resolve_project_root(args.project_root)
        run = PipelineOrchestrator(project_root).latest_run()
        return _emit({"status": "ok", "run": None if run is None else run.to_dict(include_content=True)})
    except Exception as exc:
        return _emit({"status": "error", "error_code": "agent_latest_run_failed", "message": str(exc)}, exit_code=1)


def cmd_list_runs(args: argparse.Namespace) -> int:
    try:
        project_root = _resolve_project_root(args.project_root)
        runs = PipelineOrchestrator(project_root).list_runs()
        return _emit({"status": "ok", "runs": runs})
    except Exception as exc:
        return _emit({"status": "error", "error_code": "agent_list_runs_failed", "message": str(exc)}, exit_code=1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="webnovel agent", description="内嵌 LLM API 的 agent 运行入口")
    parser.add_argument("--project-root", help="项目根目录")
    subparsers = parser.add_subparsers(dest="command")

    session_parser = subparsers.add_parser("session", help="agent 会话管理")
    session_subparsers = session_parser.add_subparsers(dest="session_command")

    start_parser = session_subparsers.add_parser("start", help="启动 agent 会话")
    start_parser.add_argument("--profile", required=True, help="Skill profile")
    start_parser.set_defaults(func=cmd_session_start)

    stop_parser = session_subparsers.add_parser("stop", help="停止 agent 会话")
    stop_parser.add_argument("--session-id", required=True, help="会话 ID")
    stop_parser.set_defaults(func=cmd_session_stop)

    run_parser = subparsers.add_parser("run", help="执行整章 agent pipeline")
    run_parser.add_argument("--chapter", required=True, type=int, help="章节号")
    run_parser.add_argument("--profile", help="可选 profile，用于加载题材/规则提示")
    run_parser.add_argument("--session-id", help="复用已有会话")
    run_parser.add_argument("--publish", action="store_true", help="完成后直接发布章节草稿")
    run_parser.add_argument("--cleanup-session", action="store_true", help="运行结束后自动清理临时会话")
    run_parser.set_defaults(func=cmd_run)

    get_run_parser = subparsers.add_parser("get-run", help="获取 run 详情")
    get_run_parser.add_argument("--run-id", required=True)
    get_run_parser.set_defaults(func=cmd_get_run)

    latest_parser = subparsers.add_parser("latest-run", help="获取最新 run")
    latest_parser.set_defaults(func=cmd_latest_run)

    list_parser = subparsers.add_parser("list-runs", help="列出 run")
    list_parser.set_defaults(func=cmd_list_runs)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
