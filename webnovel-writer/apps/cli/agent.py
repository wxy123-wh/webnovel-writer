from __future__ import annotations

import argparse
import sys

from apps.cli.common import emit_error, emit_json
from core.agent_runtime.service import activate_profile, restore_profile, run_pipeline_for_chapter
from core.pipeline.orchestrator import PipelineOrchestrator, STAGE_SEQUENCE
from core.project_state import resolve_project_root
from core.skill_system import SessionManager


def cmd_session_start(args: argparse.Namespace) -> int:
    try:
        project_root = resolve_project_root(args.project_root)
        SessionManager.validate_profile(args.profile)
        manager = SessionManager(project_root)
        session_id = manager.create_session(args.profile)
        return emit_json(
            {
                "status": "ok",
                "session_id": session_id,
                "profile": args.profile,
                "project_root": str(project_root),
                "message": f"agent 会话已启动: {session_id}",
            }
        )
    except Exception as exc:
        return emit_error("agent_session_start_failed", str(exc))


def cmd_session_stop(args: argparse.Namespace) -> int:
    try:
        project_root = resolve_project_root(args.project_root)
        manager = SessionManager(project_root)
        manager.destroy_session(args.session_id)
        return emit_json({"status": "ok", "session_id": args.session_id, "message": f"agent 会话已停止: {args.session_id}"})
    except Exception as exc:
        return emit_error("agent_session_stop_failed", str(exc))


def cmd_run(args: argparse.Namespace) -> int:
    session_id: str | None = None
    created_session = False
    previous_profile: str | None = None
    try:
        project_root = resolve_project_root(args.project_root)
        profile = args.profile
        if args.session_id:
            info = SessionManager(project_root).get_session_info(args.session_id)
            profile = str(info.get("profile") or profile or "") or None
            session_id = args.session_id
        elif profile:
            manager = SessionManager(project_root)
            session_id = manager.create_session(profile)
            created_session = True

        _, previous_profile = activate_profile(profile)
        run = run_pipeline_for_chapter(project_root=project_root, chapter_num=args.chapter, publish=args.publish)
        return emit_json(
            {
                "status": "ok",
                "project_root": str(project_root),
                "session_id": session_id,
                "run": run.to_dict(include_content=True),
            }
        )
    except Exception as exc:
        return emit_error("agent_run_failed", str(exc))
    finally:
        restore_profile(previous_profile)
        if created_session and session_id and args.cleanup_session:
            try:
                SessionManager(resolve_project_root(args.project_root)).destroy_session(session_id)
            except Exception:
                pass


def cmd_get_run(args: argparse.Namespace) -> int:
    try:
        project_root = resolve_project_root(args.project_root)
        run = PipelineOrchestrator(project_root).get_run(args.run_id)
        return emit_json({"status": "ok", "run": run.to_dict(include_content=True)})
    except Exception as exc:
        return emit_error("agent_get_run_failed", str(exc))


def cmd_latest_run(args: argparse.Namespace) -> int:
    try:
        project_root = resolve_project_root(args.project_root)
        run = PipelineOrchestrator(project_root).latest_run()
        return emit_json({"status": "ok", "run": None if run is None else run.to_dict(include_content=True)})
    except Exception as exc:
        return emit_error("agent_latest_run_failed", str(exc))


def cmd_list_runs(args: argparse.Namespace) -> int:
    try:
        project_root = resolve_project_root(args.project_root)
        runs = PipelineOrchestrator(project_root).list_runs()
        return emit_json({"status": "ok", "runs": runs})
    except Exception as exc:
        return emit_error("agent_list_runs_failed", str(exc))


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


__all__ = ["STAGE_SEQUENCE", "main"]


if __name__ == "__main__":
    sys.exit(main())
