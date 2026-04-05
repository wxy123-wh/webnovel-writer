from __future__ import annotations

import os
from pathlib import Path

from core.pipeline.orchestrator import PipelineOrchestrator, STAGE_SEQUENCE
from core.skill_system import SessionManager


def activate_profile(profile: str | None) -> tuple[str | None, str | None]:
    if not profile:
        return None, None

    SessionManager.validate_profile(profile)
    previous = os.environ.get("WEBNOVEL_CHAT_PROFILE")
    os.environ["WEBNOVEL_CHAT_PROFILE"] = profile
    return profile, previous


def restore_profile(previous: str | None) -> None:
    if previous is None:
        os.environ.pop("WEBNOVEL_CHAT_PROFILE", None)
    else:
        os.environ["WEBNOVEL_CHAT_PROFILE"] = previous


def run_pipeline_for_chapter(*, project_root: Path, chapter_num: int, publish: bool):
    orchestrator = PipelineOrchestrator(project_root)
    run = orchestrator.start_run(chapter_num)
    for stage in STAGE_SEQUENCE:
        run = orchestrator.generate_stage(run.run_id, stage)
        run = orchestrator.accept_stage(run.run_id, stage)
    if publish:
        run = orchestrator.publish_chapter(run.run_id)
    return run
