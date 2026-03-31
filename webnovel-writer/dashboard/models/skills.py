from __future__ import annotations

from pydantic import BaseModel, Field


class CreateSkillRequest(BaseModel):
    skill_id: str = Field(default="")
    name: str = Field(default="")
    description: str = Field(default="")
    instruction_template: str = Field(default="")


class SkillDraftRequest(BaseModel):
    prompt: str = Field(default="")
    current_draft: CreateSkillRequest = Field(default_factory=CreateSkillRequest)


class SkillDraftResponse(BaseModel):
    reply: str = Field(default="")
    draft: CreateSkillRequest = Field(default_factory=CreateSkillRequest)
