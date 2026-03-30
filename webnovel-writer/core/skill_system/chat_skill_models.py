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

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "enabled": self.enabled,
            "needs_approval": self.needs_approval,
        }
