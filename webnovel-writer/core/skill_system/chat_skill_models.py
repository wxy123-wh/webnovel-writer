from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ChatSkill:
    skill_id: str
    name: str
    description: str
    source: str
    enabled: bool = True
    input_schema: dict[str, Any] | None = None
    needs_approval: bool = False
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "enabled": self.enabled,
            "needs_approval": self.needs_approval,
        }
        if self.updated_at:
            payload["updated_at"] = self.updated_at
        return payload
