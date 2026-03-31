from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CreateChatRequest(BaseModel):
    title: str = Field(default="")
    profile: str | None = Field(default=None)
    skill_ids: list[str] | None = Field(default=None)


class ChatResponse(BaseModel):
    chat_id: str
    title: str
    profile: str | None
    created_at: str
    updated_at: str


class SendMessageRequest(BaseModel):
    content: str
    role: Literal["user"] = "user"


class MessagePartResponse(BaseModel):
    part_id: str
    type: str
    payload: dict[str, Any]


class MessageResponse(BaseModel):
    message_id: str
    role: str
    status: str
    parts: list[MessagePartResponse]
    created_at: str


class StreamMessageRequest(BaseModel):
    content: str


class SkillMount(BaseModel):
    skill_id: str
    enabled: bool = True
    source: str = "system"


class UpdateChatSkillsRequest(BaseModel):
    skills: list[SkillMount]


class SkillResponse(BaseModel):
    skill_id: str
    name: str
    description: str
    enabled: bool
    source: str
    needs_approval: bool = False


class ApiErrorResponse(BaseModel):
    error_code: str
    message: str
    details: dict[str, Any] | None = None
