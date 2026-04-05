from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

MessageRole = Literal["user", "assistant", "system"]
MessageStatus = Literal["streaming", "complete", "error"]
PartType = Literal["text", "tool_call", "tool_result", "error", "reasoning"]


@dataclass(slots=True)
class Chat:
    chat_id: str
    project_root: str
    title: str
    profile: str | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "chat_id": self.chat_id,
            "project_root": self.project_root,
            "title": self.title,
            "profile": self.profile,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Chat":
        return cls(
            chat_id=str(data["chat_id"]),
            project_root=str(data["project_root"]),
            title=str(data.get("title") or ""),
            profile=str(data["profile"]) if data.get("profile") is not None else None,
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
        )


@dataclass(slots=True)
class Message:
    message_id: str
    chat_id: str
    role: MessageRole
    status: MessageStatus
    created_at: str
    parts: list["MessagePart"] = field(default_factory=list)

    def to_dict(self, *, include_parts: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "message_id": self.message_id,
            "chat_id": self.chat_id,
            "role": self.role,
            "status": self.status,
            "created_at": self.created_at,
        }
        if include_parts:
            payload["parts"] = [part.to_dict() for part in self.parts]
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        return cls(
            message_id=str(data["message_id"]),
            chat_id=str(data["chat_id"]),
            role=str(data["role"]),
            status=str(data.get("status") or "complete"),
            created_at=str(data["created_at"]),
            parts=[MessagePart.from_dict(item) for item in data.get("parts", [])],
        )


@dataclass(slots=True)
class MessagePart:
    part_id: str
    message_id: str
    seq: int
    type: PartType
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "part_id": self.part_id,
            "message_id": self.message_id,
            "seq": self.seq,
            "type": self.type,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MessagePart":
        payload = data.get("payload")
        return cls(
            part_id=str(data["part_id"]),
            message_id=str(data["message_id"]),
            seq=int(data["seq"]),
            type=str(data["type"]),
            payload=dict(payload) if isinstance(payload, dict) else {},
        )
