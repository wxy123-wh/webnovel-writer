from __future__ import annotations

import argparse
import sys

from apps.cli.common import emit_error, emit_json
from core.project_state import resolve_project_root
from core.rag_index import FileWatcher, IncrementalIndexer, RAGVerifier
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
                "message": f"会话已启动: {session_id}（profile: {args.profile}）",
            }
        )
    except ValueError as exc:
        return emit_error("invalid_profile", str(exc))
    except Exception as exc:
        return emit_error("session_start_failed", str(exc))


def cmd_session_stop(args: argparse.Namespace) -> int:
    try:
        session_id = args.session_id
        manager = SessionManager()
        manager.destroy_session(session_id)
        return emit_json({"status": "ok", "session_id": session_id, "message": f"会话已停止: {session_id}"})
    except Exception as exc:
        return emit_error("session_stop_failed", str(exc))


def cmd_index_status(args: argparse.Namespace) -> int:
    try:
        project_root = resolve_project_root(args.project_root)
        indexer = IncrementalIndexer(project_root)
        status = indexer.get_status()
        return emit_json({"status": "ok", "project_root": str(project_root), "index": status})
    except Exception as exc:
        return emit_error("index_status_failed", str(exc))


def cmd_index_watch(args: argparse.Namespace) -> int:
    try:
        if FileWatcher is None:
            return emit_error("watchdog_not_installed", "watchdog 未安装。请运行: pip install watchdog")

        project_root = resolve_project_root(args.project_root)
        indexer = IncrementalIndexer(project_root)
        watcher = FileWatcher(project_root, indexer)

        import time

        watcher.start()
        emit_json(
            {
                "status": "watching",
                "project_root": str(project_root),
                "watch_dir": str(project_root / "正文"),
                "message": "文件监听已启动，按 Ctrl+C 停止",
            }
        )

        try:
            while watcher.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            watcher.stop()
            emit_json({"status": "stopped", "message": "文件监听已停止"})

        return 0
    except Exception as exc:
        return emit_error("index_watch_failed", str(exc))


def cmd_rag_verify(args: argparse.Namespace) -> int:
    try:
        project_root = resolve_project_root(args.project_root)
        report_format = args.report or "json"
        report = RAGVerifier(project_root).verify()
        if report_format == "json":
            emit_json(report)
        else:
            print(f"RAG 验证报告 - {project_root}")
            print(f"连通性: {report.get('connectivity', {}).get('status', 'unknown')}")
            print(f"正确性: {report.get('correctness', {}).get('status', 'unknown')}")
            print(f"性能: {report.get('performance', {}).get('status', 'unknown')}")
        return 0 if report.get("passed", False) else 1
    except Exception as exc:
        return emit_error("rag_verify_failed", str(exc))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="webnovel codex", description="Codex 统一命令入口（兼容运行时命令面）")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    session_start_parser = subparsers.add_parser("session", help="会话管理")
    session_subparsers = session_start_parser.add_subparsers(dest="session_command")

    start_parser = session_subparsers.add_parser("start", help="启动会话")
    available_profiles = SessionManager.available_profiles()
    start_parser.add_argument("--profile", required=True, choices=available_profiles if available_profiles else None, help="Skill profile（自动发现可用 profiles）")
    start_parser.add_argument("--project-root", help="项目根目录")
    start_parser.set_defaults(func=cmd_session_start)

    stop_parser = session_subparsers.add_parser("stop", help="停止会话")
    stop_parser.add_argument("--session-id", required=True, help="会话 ID")
    stop_parser.set_defaults(func=cmd_session_stop)

    index_parser = subparsers.add_parser("index", help="索引管理")
    index_subparsers = index_parser.add_subparsers(dest="index_command")

    status_parser = index_subparsers.add_parser("status", help="查询索引状态")
    status_parser.add_argument("--project-root", help="项目根目录")
    status_parser.set_defaults(func=cmd_index_status)

    watch_parser = index_subparsers.add_parser("watch", help="监听文件变更并自动索引")
    watch_parser.add_argument("--project-root", help="项目根目录")
    watch_parser.set_defaults(func=cmd_index_watch)

    rag_parser = subparsers.add_parser("rag", help="RAG 管理")
    rag_subparsers = rag_parser.add_subparsers(dest="rag_command")

    verify_parser = rag_subparsers.add_parser("verify", help="验证 RAG 13档指标")
    verify_parser.add_argument("--project-root", help="项目根目录")
    verify_parser.add_argument("--report", choices=["json", "text"], default="json", help="报告格式")
    verify_parser.set_defaults(func=cmd_rag_verify)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
