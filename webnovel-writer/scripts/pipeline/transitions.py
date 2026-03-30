#!/usr/bin/env python3

from __future__ import annotations

from .models import PipelineRun, RevisionRecord, STAGE_SEQUENCE, StageName


def previous_stage(stage: StageName) -> StageName | None:
    index = STAGE_SEQUENCE.index(stage)
    if index == 0:
        return None
    return STAGE_SEQUENCE[index - 1]


def downstream_stages(stage: StageName) -> tuple[StageName, ...]:
    index = STAGE_SEQUENCE.index(stage)
    return STAGE_SEQUENCE[index + 1 :]


def can_generate(run: PipelineRun, stage: StageName) -> tuple[bool, str]:
    prev = previous_stage(stage)
    if prev is None:
        return True, ""
    if run.stage(prev).accepted_revision_id:
        return True, ""
    return False, f"stage '{stage}' requires an accepted '{prev}' revision"


def can_accept(run: PipelineRun, stage: StageName) -> tuple[bool, str]:
    if run.stage(stage).current_revision_id:
        return True, ""
    return False, f"stage '{stage}' has no current revision to accept"


def apply_stage_generated(run: PipelineRun, stage: StageName, revision: RevisionRecord, *, timestamp: str) -> PipelineRun:
    stage_record = run.stage(stage)
    stage_record.revisions.append(revision)
    stage_record.current_revision_id = revision.revision_id
    stage_record.stale = False
    stage_record.stale_reason = ""
    stage_record.failure_message = ""
    run.updated_at = timestamp
    return run


def apply_stage_accepted(run: PipelineRun, stage: StageName, *, timestamp: str) -> PipelineRun:
    stage_record = run.stage(stage)
    current_revision_id = stage_record.current_revision_id
    if current_revision_id is None:
        raise ValueError(f"stage '{stage}' has no current revision to accept")
    stage_record.accepted_revision_id = current_revision_id
    stage_record.stale = False
    stage_record.stale_reason = ""

    for downstream in downstream_stages(stage):
        downstream_record = run.stage(downstream)
        downstream_record.accepted_revision_id = None
        downstream_record.stale = len(downstream_record.revisions) > 0
        downstream_record.stale_reason = f"upstream:{stage}"
        if downstream == "chapter":
            downstream_record.published_revision_id = None
    run.updated_at = timestamp
    return run


def apply_publish(run: PipelineRun, *, timestamp: str, published_path: str) -> PipelineRun:
    chapter_record = run.stage("chapter")
    if chapter_record.accepted_revision_id is None:
        raise ValueError("cannot publish without an accepted chapter revision")
    chapter_record.published_revision_id = chapter_record.accepted_revision_id
    run.published_path = published_path
    run.status = "published"
    run.updated_at = timestamp
    return run
