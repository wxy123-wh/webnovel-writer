from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass(slots=True)
class ChatToolDefinition:
    """Represents a single tool the LLM can invoke during a chat session."""

    name: str
    description: str
    parameters: dict[str, Any]

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


_ENTITY_TYPE_ENUM = {
    "type": "string",
    "enum": ["outline", "setting", "canon_entry"],
    "description": "The type of hierarchy entity.",
}

HIERARCHY_TOOLS: list[ChatToolDefinition] = [
    ChatToolDefinition(
        name="hierarchy_list",
        description="List all entities of a given type in the current project. Returns an array of {id, title, synopsis}.",
        parameters={
            "type": "object",
            "properties": {
                "entity_type": _ENTITY_TYPE_ENUM,
            },
            "required": ["entity_type"],
        },
    ),
    ChatToolDefinition(
        name="hierarchy_read",
        description="Read the full title and body of a specific hierarchy entity by its type and ID.",
        parameters={
            "type": "object",
            "properties": {
                "entity_type": _ENTITY_TYPE_ENUM,
                "entity_id": {
                    "type": "string",
                    "description": "The unique ID of the entity to read.",
                },
            },
            "required": ["entity_type", "entity_id"],
        },
    ),
    ChatToolDefinition(
        name="hierarchy_update",
        description="Update the title and/or body of an existing hierarchy entity.",
        parameters={
            "type": "object",
            "properties": {
                "entity_type": _ENTITY_TYPE_ENUM,
                "entity_id": {
                    "type": "string",
                    "description": "The unique ID of the entity to update.",
                },
                "title": {
                    "type": "string",
                    "description": "New title for the entity (optional).",
                },
                "body": {
                    "type": "string",
                    "description": "New body content for the entity (optional).",
                },
            },
            "required": ["entity_type", "entity_id"],
        },
    ),
    ChatToolDefinition(
        name="hierarchy_create",
        description="Create a new hierarchy entity with a title and body.",
        parameters={
            "type": "object",
            "properties": {
                "entity_type": _ENTITY_TYPE_ENUM,
                "title": {
                    "type": "string",
                    "description": "Title for the new entity.",
                },
                "body": {
                    "type": "string",
                    "description": "Body content for the new entity.",
                },
            },
            "required": ["entity_type", "title"],
        },
    ),
]


def get_hierarchy_tool_definitions() -> list[dict[str, Any]]:
    """Return the 4 hierarchy tools in OpenAI function-calling format."""
    return [tool.to_openai_tool() for tool in HIERARCHY_TOOLS]
