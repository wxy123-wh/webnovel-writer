#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pipeline.orchestrator import PipelineOrchestrator


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pipeline-cli")
    parser.add_argument("--project-root", required=True)
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start-run")
    start.add_argument("--chapter", required=True, type=int)

    get_run = sub.add_parser("get-run")
    get_run.add_argument("--run-id", required=True)

    latest = sub.add_parser("latest-run")

    list_runs = sub.add_parser("list-runs")

    generate = sub.add_parser("generate")
    generate.add_argument("--run-id", required=True)
    generate.add_argument("--stage", required=True, choices=["plot", "events", "scenes", "chapter"])

    accept = sub.add_parser("accept")
    accept.add_argument("--run-id", required=True)
    accept.add_argument("--stage", required=True, choices=["plot", "events", "scenes", "chapter"])

    select_revision = sub.add_parser("select-revision")
    select_revision.add_argument("--run-id", required=True)
    select_revision.add_argument("--stage", required=True, choices=["plot", "events", "scenes", "chapter"])
    select_revision.add_argument("--revision-id", required=True)

    accept_revision = sub.add_parser("accept-revision")
    accept_revision.add_argument("--run-id", required=True)
    accept_revision.add_argument("--stage", required=True, choices=["plot", "events", "scenes", "chapter"])
    accept_revision.add_argument("--revision-id", required=True)

    publish = sub.add_parser("publish")
    publish.add_argument("--run-id", required=True)
    publish.add_argument("--use-volume-layout", action="store_true")

    return parser


def _emit(payload: dict, *, exit_code: int = 0) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return exit_code


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    orchestrator = PipelineOrchestrator(Path(args.project_root))

    try:
        if args.command == "start-run":
            run = orchestrator.start_run(args.chapter)
            return _emit({"ok": True, "run": run.to_dict(include_content=True)})
        if args.command == "get-run":
            run = orchestrator.get_run(args.run_id)
            return _emit({"ok": True, "run": run.to_dict(include_content=True)})
        if args.command == "latest-run":
            run = orchestrator.latest_run()
            return _emit({"ok": True, "run": None if run is None else run.to_dict(include_content=True)})
        if args.command == "list-runs":
            return _emit({"ok": True, "runs": orchestrator.list_runs()})
        if args.command == "generate":
            run = orchestrator.generate_stage(args.run_id, args.stage)
            return _emit({"ok": True, "run": run.to_dict(include_content=True)})
        if args.command == "accept":
            run = orchestrator.accept_stage(args.run_id, args.stage)
            return _emit({"ok": True, "run": run.to_dict(include_content=True)})
        if args.command == "select-revision":
            run = orchestrator.select_revision(args.run_id, args.stage, args.revision_id)
            return _emit({"ok": True, "run": run.to_dict(include_content=True)})
        if args.command == "accept-revision":
            run = orchestrator.accept_revision(args.run_id, args.stage, args.revision_id)
            return _emit({"ok": True, "run": run.to_dict(include_content=True)})
        if args.command == "publish":
            run = orchestrator.publish_chapter(args.run_id, use_volume_layout=bool(args.use_volume_layout))
            return _emit({"ok": True, "run": run.to_dict(include_content=True)})
    except Exception as exc:
        return _emit({"ok": False, "error": str(exc)}, exit_code=1)

    return _emit({"ok": False, "error": "unsupported command"}, exit_code=2)


if __name__ == "__main__":
    raise SystemExit(main())
