#!/usr/bin/env python3

import sys
from pathlib import Path


def _ensure_scripts_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def test_store_persists_revisions_and_reload_content(tmp_path):
    _ensure_scripts_path()

    from pipeline.models import OutlineTarget, PipelineRun
    from pipeline.store import PipelineArtifactStore, utc_now_iso

    run = PipelineRun(
        run_id="run-abc",
        project_root=str(tmp_path),
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
        chapter_num=5,
        outline=OutlineTarget(chapter_num=5, title="测试章节", source_path="大纲", content="### 第5章：测试章节"),
    )
    store = PipelineArtifactStore(tmp_path)
    store.create_run(run)
    updated = store.add_revision("run-abc", "plot", content={"premise": "测试"}, content_format="json", summary="测试")

    assert updated.stage("plot").current_revision_id is not None
    revision = updated.stage("plot").revisions[0]
    assert revision.content == {"premise": "测试"}
    reloaded = store.load_run("run-abc", include_content=True)
    assert reloaded.stage("plot").revisions[0].content == {"premise": "测试"}


def test_store_can_select_and_accept_specific_revision(tmp_path):
    _ensure_scripts_path()

    from pipeline.models import OutlineTarget, PipelineRun
    from pipeline.store import PipelineArtifactStore, utc_now_iso

    run = PipelineRun(
        run_id="run-abc",
        project_root=str(tmp_path),
        created_at=utc_now_iso(),
        updated_at=utc_now_iso(),
        chapter_num=5,
        outline=OutlineTarget(chapter_num=5, title="测试章节", source_path="大纲", content="### 第5章：测试章节"),
    )
    store = PipelineArtifactStore(tmp_path)
    store.create_run(run)
    first = store.add_revision("run-abc", "plot", content={"premise": "A"}, content_format="json", summary="A")
    second = store.add_revision("run-abc", "plot", content={"premise": "B"}, content_format="json", summary="B")

    first_revision_id = first.stage("plot").revisions[0].revision_id
    second_revision_id = second.stage("plot").revisions[-1].revision_id

    selected = store.select_revision("run-abc", "plot", first_revision_id)
    assert selected.stage("plot").current_revision_id == first_revision_id
    accepted = store.accept_revision("run-abc", "plot", second_revision_id)
    assert accepted.stage("plot").current_revision_id == second_revision_id
    assert accepted.stage("plot").accepted_revision_id == second_revision_id
