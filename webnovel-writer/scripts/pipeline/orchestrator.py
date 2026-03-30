#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .adapters import load_context_payload, load_outline_target, refresh_index
from .generators import generate_chapter_markdown, generate_events, generate_plot, generate_scenes, summarize_content
from .models import PipelineRun, STAGE_SEQUENCE, StageName
from .store import PipelineArtifactStore, utc_now_iso
from .transitions import can_accept, can_generate


class PipelineOrchestrator:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.store = PipelineArtifactStore(self.project_root)

    def start_run(self, chapter_num: int) -> PipelineRun:
        outline = load_outline_target(self.project_root, chapter_num)
        run = PipelineRun(
            run_id=f"run-ch{chapter_num:04d}-{uuid4().hex[:8]}",
            project_root=str(self.project_root),
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
            chapter_num=chapter_num,
            outline=outline,
        )
        self.store.create_run(run)
        return self.store.load_run(run.run_id, include_content=True)

    def get_run(self, run_id: str) -> PipelineRun:
        return self.store.load_run(run_id, include_content=True)

    def latest_run(self) -> PipelineRun | None:
        run_id = self.store.latest_run_id()
        return None if run_id is None else self.get_run(run_id)

    def list_runs(self) -> list[dict]:
        return self.store.list_runs()

    def generate_stage(self, run_id: str, stage: StageName) -> PipelineRun:
        run = self.get_run(run_id)
        allowed, reason = can_generate(run, stage)
        if not allowed:
            raise ValueError(reason)

        next_revision_number = len(run.stage(stage).revisions) + 1
        if stage == "plot":
            content = generate_plot(
                chapter_num=run.chapter_num,
                title=run.outline.title,
                outline_text=run.outline.content,
                revision_number=next_revision_number,
            )
            content_format = "json"
        elif stage == "events":
            plot_revision = run.stage("plot").get_revision(run.stage("plot").accepted_revision_id)
            if plot_revision is None or not isinstance(plot_revision.content, dict):
                raise ValueError("accepted plot revision not found")
            content = generate_events(plot_payload=plot_revision.content, revision_number=next_revision_number)
            content_format = "json"
        elif stage == "scenes":
            events_revision = run.stage("events").get_revision(run.stage("events").accepted_revision_id)
            if events_revision is None or not isinstance(events_revision.content, dict):
                raise ValueError("accepted events revision not found")
            content = generate_scenes(events_payload=events_revision.content, revision_number=next_revision_number)
            content_format = "json"
        elif stage == "chapter":
            scenes_revision = run.stage("scenes").get_revision(run.stage("scenes").accepted_revision_id)
            if scenes_revision is None or not isinstance(scenes_revision.content, dict):
                raise ValueError("accepted scenes revision not found")
            context_payload = load_context_payload(self.project_root, run.chapter_num)
            content = generate_chapter_markdown(
                title=run.outline.title,
                chapter_num=run.chapter_num,
                scenes_payload=scenes_revision.content,
                context_payload=context_payload,
                revision_number=next_revision_number,
            )
            content_format = "markdown"
        else:  # pragma: no cover
            raise ValueError(f"unsupported stage: {stage}")

        summary = summarize_content(stage, content)
        return self.store.add_revision(
            run_id,
            stage,
            content=content,
            content_format=content_format,
            summary=summary,
            variation_key=f"variant-{next_revision_number}",
        )

    def accept_stage(self, run_id: str, stage: StageName) -> PipelineRun:
        run = self.get_run(run_id)
        allowed, reason = can_accept(run, stage)
        if not allowed:
            raise ValueError(reason)
        return self.store.accept_stage(run_id, stage)

    def select_revision(self, run_id: str, stage: StageName, revision_id: str) -> PipelineRun:
        return self.store.select_revision(run_id, stage, revision_id)

    def accept_revision(self, run_id: str, stage: StageName, revision_id: str) -> PipelineRun:
        return self.store.accept_revision(run_id, stage, revision_id)

    def publish_chapter(self, run_id: str, *, use_volume_layout: bool = False) -> PipelineRun:
        run = self.get_run(run_id)
        chapter_revision = run.stage("chapter").get_revision(run.stage("chapter").accepted_revision_id)
        if chapter_revision is None or not isinstance(chapter_revision.content, str):
            raise ValueError("accepted chapter revision not found")

        try:
            from chapter_paths import default_chapter_draft_path
        except ImportError:  # pragma: no cover
            from scripts.chapter_paths import default_chapter_draft_path

        draft_path = default_chapter_draft_path(self.project_root, run.chapter_num, use_volume_layout=use_volume_layout)
        draft_path.parent.mkdir(parents=True, exist_ok=True)
        draft_path.write_text(chapter_revision.content, encoding="utf-8")
        refresh_index(self.project_root)
        return self.store.mark_published(run_id, str(draft_path))

    def stage_status_matrix(self, run_id: str) -> dict[str, dict[str, object]]:
        run = self.get_run(run_id)
        return {
            stage: {
                "has_current": run.stage(stage).current_revision_id is not None,
                "has_accepted": run.stage(stage).accepted_revision_id is not None,
                "stale": run.stage(stage).stale,
                "revision_count": len(run.stage(stage).revisions),
                "can_generate": can_generate(run, stage)[0],
                "can_accept": can_accept(run, stage)[0],
            }
            for stage in STAGE_SEQUENCE
        }
