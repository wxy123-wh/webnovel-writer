# pyright: reportMissingImports=false

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateBookRequest(BaseModel):
    title: str = Field(default="")
    synopsis: str = Field(default="")


class CreateHierarchyEntityRequest(BaseModel):
    parent_id: str | None = Field(default=None)
    title: str = Field(default="")
    body: str = Field(default="")
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateHierarchyEntityRequest(BaseModel):
    expected_version: int = Field(..., ge=1)
    title: str | None = Field(default=None)
    body: str | None = Field(default=None)
    metadata: dict[str, Any] | None = Field(default=None)


class ReorderPlotsRequest(BaseModel):
    parent_id: str
    ordered_ids: list[str] = Field(default_factory=list)


class ProposalChildPayload(BaseModel):
    title: str = Field(default="")
    body: str = Field(default="")
    metadata: dict[str, Any] = Field(default_factory=dict)


class PreviewProposalRequest(BaseModel):
    kind: str
    proposal_type: str = Field(default="")
    parent_type: str | None = Field(default=None)
    parent_id: str | None = Field(default=None)
    child_type: str | None = Field(default=None)
    proposed_children: list[ProposalChildPayload] = Field(default_factory=list)
    source_type: str | None = Field(default=None)
    source_id: str | None = Field(default=None)
    chapter_id: str | None = Field(default=None)
    summary: str = Field(default="")
    proposed_update: ProposalChildPayload | None = Field(default=None)
    title: str = Field(default="")
    body: str = Field(default="")
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarkIndexStaleRequest(BaseModel):
    reason: str = Field(default="manual_reset")


class RollbackRevisionRequest(BaseModel):
    target_revision: int = Field(..., ge=1)
    expected_version: int = Field(..., ge=1)


class RevisionDiffResponse(BaseModel):
    diff: str
