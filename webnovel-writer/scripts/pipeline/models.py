#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

StageName = Literal["plot", "events", "scenes", "chapter"]
STAGE_SEQUENCE: tuple[StageName, ...] = ("plot", "events", "scenes", "chapter")


@dataclass(slots=True)
class OutlineTarget:
    chapter_num: int
    title: str
    source_path: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter_num": self.chapter_num,
            "title": self.title,
            "source_path": self.source_path,
            "content": self.content,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OutlineTarget":
        return cls(
            chapter_num=int(payload["chapter_num"]),
            title=str(payload.get("title") or ""),
            source_path=str(payload.get("source_path") or ""),
            content=str(payload.get("content") or ""),
        )


@dataclass(slots=True)
class RevisionRecord:
    revision_id: str
    revision_number: int
    stage: StageName
    created_at: str
    content_format: str
    content_path: str
    summary: str
    variation_key: str = ""
    content: Any | None = None

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        payload = {
            "revision_id": self.revision_id,
            "revision_number": self.revision_number,
            "stage": self.stage,
            "created_at": self.created_at,
            "content_format": self.content_format,
            "content_path": self.content_path,
            "summary": self.summary,
            "variation_key": self.variation_key,
        }
        if include_content:
            payload["content"] = self.content
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RevisionRecord":
        return cls(
            revision_id=str(payload["revision_id"]),
            revision_number=int(payload["revision_number"]),
            stage=str(payload["stage"]),
            created_at=str(payload["created_at"]),
            content_format=str(payload.get("content_format") or "json"),
            content_path=str(payload.get("content_path") or ""),
            summary=str(payload.get("summary") or ""),
            variation_key=str(payload.get("variation_key") or ""),
            content=payload.get("content"),
        )


@dataclass(slots=True)
class StageRecord:
    stage: StageName
    current_revision_id: str | None = None
    accepted_revision_id: str | None = None
    published_revision_id: str | None = None
    stale: bool = False
    stale_reason: str = ""
    failure_message: str = ""
    revisions: list[RevisionRecord] = field(default_factory=list)

    def get_revision(self, revision_id: str | None) -> RevisionRecord | None:
        if not revision_id:
            return None
        for revision in self.revisions:
            if revision.revision_id == revision_id:
                return revision
        return None

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "current_revision_id": self.current_revision_id,
            "accepted_revision_id": self.accepted_revision_id,
            "published_revision_id": self.published_revision_id,
            "stale": self.stale,
            "stale_reason": self.stale_reason,
            "failure_message": self.failure_message,
            "revisions": [item.to_dict(include_content=include_content) for item in self.revisions],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StageRecord":
        return cls(
            stage=str(payload["stage"]),
            current_revision_id=payload.get("current_revision_id"),
            accepted_revision_id=payload.get("accepted_revision_id"),
            published_revision_id=payload.get("published_revision_id"),
            stale=bool(payload.get("stale", False)),
            stale_reason=str(payload.get("stale_reason") or ""),
            failure_message=str(payload.get("failure_message") or ""),
            revisions=[RevisionRecord.from_dict(item) for item in payload.get("revisions", [])],
        )


def default_stage_records() -> dict[str, StageRecord]:
    return {stage: StageRecord(stage=stage) for stage in STAGE_SEQUENCE}


@dataclass(slots=True)
class PipelineRun:
    run_id: str
    project_root: str
    created_at: str
    updated_at: str
    chapter_num: int
    outline: OutlineTarget
    status: str = "active"
    published_path: str = ""
    stages: dict[str, StageRecord] = field(default_factory=default_stage_records)

    def stage(self, stage: StageName) -> StageRecord:
        return self.stages[stage]

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "project_root": self.project_root,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "chapter_num": self.chapter_num,
            "status": self.status,
            "published_path": self.published_path,
            "outline": self.outline.to_dict(),
            "stages": {
                key: value.to_dict(include_content=include_content)
                for key, value in self.stages.items()
            },
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PipelineRun":
        stage_payload = payload.get("stages") or {}
        stages = default_stage_records()
        for stage_name in STAGE_SEQUENCE:
            if stage_name in stage_payload:
                stages[stage_name] = StageRecord.from_dict(stage_payload[stage_name])
        return cls(
            run_id=str(payload["run_id"]),
            project_root=str(payload["project_root"]),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            chapter_num=int(payload["chapter_num"]),
            status=str(payload.get("status") or "active"),
            published_path=str(payload.get("published_path") or ""),
            outline=OutlineTarget.from_dict(payload["outline"]),
            stages=stages,
        )
