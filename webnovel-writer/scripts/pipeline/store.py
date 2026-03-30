#!/usr/bin/env python3

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import PipelineRun, RevisionRecord, StageName
from .transitions import apply_publish, apply_stage_accepted, apply_stage_generated


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class PipelineArtifactStore:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.pipeline_root = self.project_root / ".webnovel" / "pipeline"
        self.runs_root = self.pipeline_root / "runs"
        self.runs_root.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        return self.runs_root / run_id

    def run_meta_path(self, run_id: str) -> Path:
        return self.run_dir(run_id) / "run.json"

    def save_run(self, run: PipelineRun) -> PipelineRun:
        run_dir = self.run_dir(run.run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        self.run_meta_path(run.run_id).write_text(
            json.dumps(run.to_dict(include_content=False), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return run

    def create_run(self, run: PipelineRun) -> PipelineRun:
        return self.save_run(run)

    def list_runs(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(self.runs_root.glob("*/run.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            payload = json.loads(path.read_text(encoding="utf-8"))
            items.append(payload)
        return items

    def latest_run_id(self) -> str | None:
        runs = self.list_runs()
        if not runs:
            return None
        return str(runs[0]["run_id"])

    def load_run(self, run_id: str, *, include_content: bool = True) -> PipelineRun:
        path = self.run_meta_path(run_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        run = PipelineRun.from_dict(payload)
        if include_content:
            for stage_record in run.stages.values():
                for revision in stage_record.revisions:
                    revision.content = self.read_revision_content(run_id, revision)
        return run

    def read_revision_content(self, run_id: str, revision: RevisionRecord) -> Any:
        path = self.run_dir(run_id) / revision.content_path
        if revision.content_format == "json":
            return json.loads(path.read_text(encoding="utf-8"))
        return path.read_text(encoding="utf-8")

    def _write_revision_content(self, run_id: str, stage: StageName, revision_number: int, content_format: str, content: Any) -> str:
        stage_dir = self.run_dir(run_id) / stage
        stage_dir.mkdir(parents=True, exist_ok=True)
        extension = "md" if content_format == "markdown" else "json"
        path = stage_dir / f"rev-{revision_number:03d}.{extension}"
        if content_format == "json":
            path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            path.write_text(str(content), encoding="utf-8")
        return str(path.relative_to(self.run_dir(run_id)).as_posix())

    def add_revision(self, run_id: str, stage: StageName, *, content: Any, content_format: str, summary: str, variation_key: str = "") -> PipelineRun:
        run = self.load_run(run_id, include_content=False)
        stage_record = run.stage(stage)
        revision_number = len(stage_record.revisions) + 1
        revision_id = f"{stage}-rev-{revision_number:03d}-{uuid4().hex[:8]}"
        content_path = self._write_revision_content(run_id, stage, revision_number, content_format, content)
        revision = RevisionRecord(
            revision_id=revision_id,
            revision_number=revision_number,
            stage=stage,
            created_at=utc_now_iso(),
            content_format=content_format,
            content_path=content_path,
            summary=summary,
            variation_key=variation_key,
        )
        apply_stage_generated(run, stage, revision, timestamp=utc_now_iso())
        self.save_run(run)
        return self.load_run(run_id, include_content=True)

    def accept_stage(self, run_id: str, stage: StageName) -> PipelineRun:
        run = self.load_run(run_id, include_content=False)
        apply_stage_accepted(run, stage, timestamp=utc_now_iso())
        self.save_run(run)
        return self.load_run(run_id, include_content=True)

    def select_revision(self, run_id: str, stage: StageName, revision_id: str) -> PipelineRun:
        run = self.load_run(run_id, include_content=False)
        stage_record = run.stage(stage)
        revision = stage_record.get_revision(revision_id)
        if revision is None:
            raise ValueError(f"revision '{revision_id}' not found for stage '{stage}'")
        stage_record.current_revision_id = revision.revision_id
        stage_record.failure_message = ""
        run.updated_at = utc_now_iso()
        self.save_run(run)
        return self.load_run(run_id, include_content=True)

    def accept_revision(self, run_id: str, stage: StageName, revision_id: str) -> PipelineRun:
        run = self.select_revision(run_id, stage, revision_id)
        return self.accept_stage(run.run_id, stage)

    def mark_published(self, run_id: str, published_path: str) -> PipelineRun:
        run = self.load_run(run_id, include_content=False)
        apply_publish(run, timestamp=utc_now_iso(), published_path=published_path)
        self.save_run(run)
        return self.load_run(run_id, include_content=True)
