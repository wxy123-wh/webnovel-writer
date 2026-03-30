from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

from core.agent_runtime.chat_models import Message
from core.agent_runtime.chat_repository import generate_id
from core.skill_system import ChatSkillRegistry
from scripts.data_modules.config import DataModulesConfig

from .streaming import (
    EVENT_MESSAGE_COMPLETE,
    EVENT_MESSAGE_ERROR,
    EVENT_TEXT_DELTA,
    ChatStreamAdapter,
)


class ChatOrchestrationService:
    """Coordinate chat persistence, generation, and skill metadata."""

    _BASE_SYSTEM_PROMPT = "你是网文写作助手。根据项目设定和大纲辅助创作。严格遵循已挂载 Skill 的指令。"
    _MAX_SKILL_INSTRUCTION_CHARS = 4000

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        from core.agent_runtime.chat_service import ChatService

        self.chat_service = ChatService(self.project_root)
        self.registry = ChatSkillRegistry(self.project_root)

    def create_chat(self, request: "CreateChatRequest") -> dict:
        chat = self.chat_service.create_chat(
            title=request.title,
            profile=request.profile,
            skill_ids=request.skill_ids,
        )
        return chat.to_dict()

    def get_chat(self, chat_id: str) -> dict | None:
        chat = self.chat_service.get_chat(chat_id)
        return chat.to_dict() if chat else None

    def list_chats(self) -> list[dict]:
        return [chat.to_dict() for chat in self.chat_service.list_chats()]

    def delete_chat(self, chat_id: str) -> bool:
        return self.chat_service.delete_chat(chat_id)

    def get_history(self, chat_id: str) -> list[dict]:
        self._require_chat(chat_id)
        return [message.to_dict(include_parts=True) for message in self.chat_service.get_chat_history(chat_id)]

    def send_message(self, chat_id: str, content: str) -> dict:
        assistant_message = self._run_completion(chat_id, content)
        return assistant_message.to_dict(include_parts=True)

    def send_and_stream(self, chat_id: str, content: str) -> Generator[str, None, None]:
        self._require_chat(chat_id)
        self.chat_service.add_user_message(chat_id, content)
        assistant_message_id = generate_id("msg")
        self._create_streaming_message(chat_id, assistant_message_id)

        adapter = ChatStreamAdapter(config=DataModulesConfig(project_root=self.project_root))
        collected_text = ""
        completed = False
        error_payload: dict[str, str] | None = None

        for event_str in adapter.stream_chat(
            messages=self._messages_for_llm(chat_id),
            message_id=assistant_message_id,
            chat_id=chat_id,
        ):
            event_type, payload = self._parse_sse_event(event_str)
            if event_type == EVENT_TEXT_DELTA:
                collected_text += str(payload.get("delta") or "")
            elif event_type == EVENT_MESSAGE_COMPLETE:
                completed = True
            elif event_type == EVENT_MESSAGE_ERROR:
                error_payload = {
                    "error": str(payload.get("error") or "generation failed"),
                    "code": str(payload.get("code") or "provider_error"),
                }

            yield event_str

        if error_payload is not None:
            self._finalize_streaming_message(
                chat_id=chat_id,
                message_id=assistant_message_id,
                status="error",
                parts=[{"type": "error", "payload": error_payload}],
            )
            return

        if completed:
            self._finalize_streaming_message(
                chat_id=chat_id,
                message_id=assistant_message_id,
                status="complete",
                parts=[{"type": "text", "payload": {"text": collected_text}}],
            )

    def get_chat_skills(self, chat_id: str) -> list[dict]:
        self._require_chat(chat_id)
        mounted = self.chat_service.get_chat_skills(chat_id)
        return self._enrich_skills(mounted)

    def update_chat_skills(self, chat_id: str, skills: list[dict]) -> list[dict]:
        self._require_chat(chat_id)
        mounted = self.chat_service.mount_skills(chat_id, skills)
        return self._enrich_skills(mounted)

    def _require_chat(self, chat_id: str) -> None:
        if self.chat_service.get_chat(chat_id) is None:
            raise KeyError(chat_id)

    @staticmethod
    def _extract_text(message: Message) -> str:
        chunks: list[str] = []
        for part in message.parts:
            if part.type != "text":
                continue
            text = part.payload.get("text")
            if not isinstance(text, str):
                text = part.payload.get("content")
            if isinstance(text, str) and text:
                chunks.append(text)
        return "\n".join(chunks)

    def _messages_for_llm(self, chat_id: str) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        system_prompt = self._build_system_prompt(chat_id)
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for message in self.chat_service.get_chat_history(chat_id):
            text = self._extract_text(message)
            if text:
                messages.append({"role": message.role, "content": text})
        return messages

    def _build_system_prompt(self, chat_id: str) -> str:
        sections = [self._BASE_SYSTEM_PROMPT]

        project_context = self._project_context_text()
        if project_context:
            sections.append(f"项目上下文：\n{project_context}")

        skill_instructions = self._skill_instruction_text(chat_id)
        if skill_instructions:
            sections.append(f"已挂载 Skill 指令：\n{skill_instructions}")

        return "\n\n".join(section for section in sections if section)

    def _project_context_text(self) -> str:
        state = self._load_project_state()
        if not state:
            return ""

        project_info = state.get("project_info")
        progress = state.get("progress")
        if not isinstance(project_info, dict):
            project_info = {}
        if not isinstance(progress, dict):
            progress = {}

        lines: list[str] = []
        title = project_info.get("title")
        genre = project_info.get("genre")
        current_chapter = progress.get("current_chapter")

        if isinstance(title, str) and title.strip():
            lines.append(f"- 作品标题：{title.strip()}")
        if isinstance(genre, str) and genre.strip():
            lines.append(f"- 作品类型：{genre.strip()}")
        if current_chapter is not None and str(current_chapter).strip():
            lines.append(f"- 当前章节：{current_chapter}")

        return "\n".join(lines)

    def _load_project_state(self) -> dict[str, Any]:
        state_path = self.project_root / ".webnovel" / "state.json"
        if not state_path.is_file():
            return {}
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return state if isinstance(state, dict) else {}

    def _skill_instruction_text(self, chat_id: str) -> str:
        mounted_skills = self.chat_service.get_chat_skills(chat_id)
        if not mounted_skills:
            return ""

        registry_items = self.registry.list_all()
        registry_by_key = {
            (str(item.get("source") or "system"), str(item.get("skill_id") or "")): item for item in registry_items
        }
        registry_by_id = {str(item.get("skill_id") or ""): item for item in registry_items if item.get("skill_id")}

        skill_entries: list[tuple[str, str, str]] = []

        for mounted_skill in mounted_skills:
            if not bool(mounted_skill.get("enabled", True)):
                continue

            source = str(mounted_skill.get("source") or "system")
            skill_id = str(mounted_skill.get("skill_id") or "").strip()
            if not skill_id:
                continue

            registry_item = registry_by_key.get((source, skill_id)) or registry_by_id.get(skill_id) or {}
            header = f"[{source}:{skill_id}]"
            full_content = ""
            if source == "system":
                full_content = (self.registry.get_skill_content(skill_id) or "").strip()

            description = registry_item.get("description")
            short_content = description.strip() if isinstance(description, str) else ""

            if not full_content and not short_content:
                continue

            skill_entries.append((header, full_content, short_content))

        full_segments = [self._format_skill_segment(header, content) for header, content, _ in skill_entries if content]
        full_prompt = "\n\n".join(full_segments)
        if full_prompt and len(full_prompt) <= self._MAX_SKILL_INSTRUCTION_CHARS:
            return full_prompt

        summary_segments = [
            self._format_skill_segment(header, summary or content)
            for header, content, summary in skill_entries
            if summary or content
        ]
        summary_prompt = "\n\n".join(summary_segments)
        if len(summary_prompt) <= self._MAX_SKILL_INSTRUCTION_CHARS:
            return summary_prompt

        return self._truncate_skill_segments(summary_segments)

    @staticmethod
    def _format_skill_segment(header: str, content: str) -> str:
        return f"{header}\n{content.strip()}"

    def _truncate_skill_segments(self, segments: list[str]) -> str:
        kept_segments: list[str] = []
        used_chars = 0
        limit = self._MAX_SKILL_INSTRUCTION_CHARS

        for segment in segments:
            remaining = limit - used_chars
            if remaining <= 0:
                break
            if len(segment) <= remaining:
                kept_segments.append(segment)
                used_chars += len(segment)
                continue
            if remaining <= 3:
                break
            kept_segments.append(f"{segment[: remaining - 3].rstrip()}...")
            break

        return "\n\n".join(kept_segments)

    @staticmethod
    def _parse_sse_event(event_str: str) -> tuple[str | None, dict[str, object]]:
        event_type: str | None = None
        payload: dict[str, object] = {}
        for line in event_str.splitlines():
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                payload = json.loads(line[6:])
        return event_type, payload

    def _create_streaming_message(self, chat_id: str, message_id: str) -> None:
        repository = self.chat_service.repository
        with repository._connect() as connection:
            repository._insert_message(
                connection,
                message_id=message_id,
                chat_id=chat_id,
                role="assistant",
                status="streaming",
            )
            connection.commit()

    def _finalize_streaming_message(
        self,
        *,
        chat_id: str,
        message_id: str,
        status: str,
        parts: list[dict[str, object]],
    ) -> Message:
        repository = self.chat_service.repository
        with repository._connect() as connection:
            created_parts = []
            for index, part in enumerate(parts):
                created_parts.append(
                    repository._insert_part(
                        connection,
                        part_id=generate_id("part"),
                        message_id=message_id,
                        seq=index,
                        part_type=str(part["type"]),
                        payload=dict(part.get("payload") or {}),
                    )
                )
            connection.execute(
                "UPDATE messages SET status = ? WHERE message_id = ?",
                (status, message_id),
            )
            repository._touch_chat(connection, chat_id)
            connection.commit()
        message = repository.get_full_message(message_id)
        if message is None:
            raise RuntimeError(f"chat message not found after finalize: {message_id}")
        return message

    def _run_completion(self, chat_id: str, content: str) -> Message:
        self._require_chat(chat_id)
        self.chat_service.add_user_message(chat_id, content)
        assistant_message_id = generate_id("msg")
        self._create_streaming_message(chat_id, assistant_message_id)

        adapter = ChatStreamAdapter(config=DataModulesConfig(project_root=self.project_root))
        collected_text = ""
        completed = False
        error_payload: dict[str, str] | None = None
        for event_str in adapter.stream_chat(
            messages=self._messages_for_llm(chat_id),
            message_id=assistant_message_id,
            chat_id=chat_id,
        ):
            event_type, payload = self._parse_sse_event(event_str)
            if event_type == EVENT_TEXT_DELTA:
                collected_text += str(payload.get("delta") or "")
            elif event_type == EVENT_MESSAGE_COMPLETE:
                completed = True
            elif event_type == EVENT_MESSAGE_ERROR:
                error_payload = {
                    "error": str(payload.get("error") or "generation failed"),
                    "code": str(payload.get("code") or "provider_error"),
                }

        if error_payload is not None:
            return self._finalize_streaming_message(
                chat_id=chat_id,
                message_id=assistant_message_id,
                status="error",
                parts=[{"type": "error", "payload": error_payload}],
            )

        if not completed:
            raise RuntimeError("chat completion ended without terminal SSE event")

        return self._finalize_streaming_message(
            chat_id=chat_id,
            message_id=assistant_message_id,
            status="complete",
            parts=[{"type": "text", "payload": {"text": collected_text}}],
        )

    def _enrich_skills(self, mounted_skills: list[dict]) -> list[dict]:
        registry_items = self.registry.list_all()
        registry_by_key = {(item["source"], item["skill_id"]): item for item in registry_items}
        registry_by_id: dict[str, dict] = {}
        for item in registry_items:
            registry_by_id.setdefault(str(item["skill_id"]), item)

        enriched: list[dict] = []
        for item in mounted_skills:
            source = str(item.get("source") or "system")
            skill_id = str(item.get("skill_id") or "")
            registry_item = registry_by_key.get((source, skill_id)) or registry_by_id.get(skill_id)
            enriched.append(
                {
                    "skill_id": skill_id,
                    "name": str((registry_item or {}).get("name") or skill_id),
                    "description": str((registry_item or {}).get("description") or ""),
                    "enabled": bool(item.get("enabled", True)),
                    "source": source,
                    "needs_approval": bool((registry_item or {}).get("needs_approval", False)),
                }
            )
        return enriched
