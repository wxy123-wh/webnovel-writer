#!/usr/bin/env python3

import sys
from pathlib import Path


def _ensure_scripts_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def test_accepting_upstream_stage_invalidates_downstream_acceptance():
    _ensure_scripts_path()

    from pipeline.models import OutlineTarget, PipelineRun, RevisionRecord
    from pipeline.transitions import apply_stage_accepted, apply_stage_generated

    run = PipelineRun(
        run_id="run-1",
        project_root="D:/tmp/project",
        created_at="2026-03-30T00:00:00+00:00",
        updated_at="2026-03-30T00:00:00+00:00",
        chapter_num=3,
        outline=OutlineTarget(chapter_num=3, title="测试", source_path="大纲", content="内容"),
    )

    plot = RevisionRecord("plot-rev-1", 1, "plot", run.created_at, "json", "plot/rev-001.json", "plot")
    events = RevisionRecord("events-rev-1", 1, "events", run.created_at, "json", "events/rev-001.json", "events")

    apply_stage_generated(run, "plot", plot, timestamp=run.created_at)
    apply_stage_accepted(run, "plot", timestamp=run.created_at)
    apply_stage_generated(run, "events", events, timestamp=run.created_at)
    apply_stage_accepted(run, "events", timestamp=run.created_at)

    plot2 = RevisionRecord("plot-rev-2", 2, "plot", run.created_at, "json", "plot/rev-002.json", "plot v2")
    apply_stage_generated(run, "plot", plot2, timestamp=run.created_at)
    apply_stage_accepted(run, "plot", timestamp=run.created_at)

    assert run.stage("events").accepted_revision_id is None
    assert run.stage("events").stale is True
    assert run.stage("events").stale_reason == "upstream:plot"


def test_cannot_generate_events_without_accepted_plot():
    _ensure_scripts_path()

    from pipeline.models import OutlineTarget, PipelineRun
    from pipeline.transitions import can_generate

    run = PipelineRun(
        run_id="run-1",
        project_root="D:/tmp/project",
        created_at="2026-03-30T00:00:00+00:00",
        updated_at="2026-03-30T00:00:00+00:00",
        chapter_num=3,
        outline=OutlineTarget(chapter_num=3, title="测试", source_path="大纲", content="内容"),
    )
    allowed, reason = can_generate(run, "events")
    assert allowed is False
    assert "requires an accepted 'plot'" in reason
