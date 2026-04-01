from __future__ import annotations

import json
import inspect
import re
from collections.abc import Callable, Generator, Iterator
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, cast

from core.book_hierarchy import BookHierarchyConflictError, BookHierarchyService, BookHierarchyValidationError
from core.agent_runtime.chat_models import Message
from core.agent_runtime.chat_repository import generate_id
from core.skill_system import ChatSkillRegistry
from core.skill_system.chat_skill_models import get_hierarchy_tool_definitions
from scripts.data_modules.config import DataModulesConfig

from .streaming import (
    EVENT_MESSAGE_COMPLETE,
    EVENT_MESSAGE_ERROR,
    EVENT_TEXT_DELTA,
    EVENT_TOOL_CALL,
    EVENT_TOOL_RESULT,
    ChatStreamAdapter,
)


class ChatOrchestrationService:
    """Coordinate chat persistence, generation, and skill metadata."""

    _BASE_SYSTEM_PROMPT = "你是网文写作助手。根据项目设定和大纲辅助创作。严格遵循已挂载 Skill 的指令。"
    _HIERARCHY_TOOL_PROMPT = """当用户要求读取、列出、新建或修改层级内容时，不要依赖记忆或自行假设当前数据，必须优先通过 hierarchy 工具读取最新内容后再回答或执行。

适用场景包括但不限于：大纲（outline）、设定（setting）、canon，以及章节/正文相关的层级内容查询与改写请求。

具体要求：
1. 需要查看当前层级内容时，先调用 hierarchy_list 或 hierarchy_read。
2. 需要新建设定/大纲/canon 时，调用 hierarchy_create。
3. 需要修改现有设定/大纲/canon 时，先读取再调用 hierarchy_update，避免覆盖错误内容。
4. 如果工具返回错误、缺少 ID、或当前请求不在工具支持范围内，要明确告知用户缺少什么信息，不要伪造结果。
5. 严禁删除层级内容。"""
    _MAX_SKILL_INSTRUCTION_CHARS = 4000
    _SKILL_DRAFT_SYSTEM_PROMPT = """你是一个 Skill 设计助手。你的任务是根据用户要求，产出一个可保存到 Skills Registry 的结构化 skill 草稿。\n\n输出必须是严格 JSON 对象，且只能包含这些字段：\n- reply: 中文简短说明，告诉用户你生成或更新了什么\n- skill_id: 仅使用小写字母、数字、连字符，形如 scene-beats\n- name: 给用户看的技能名称\n- description: 一句简洁说明这个技能做什么\n- instruction_template: 完整的技能模板指令，使用 Markdown 文本\n\n要求：\n1. 如果当前草稿已有字段，优先在其基础上迭代，不要无故清空已有内容。\n2. 如果用户只要求修改部分内容，只更新相关字段，其余字段尽量保留。\n3. instruction_template 必须是可以直接保存的完整内容，不要输出解释性前后缀。\n4. 不要输出 Markdown 代码块，不要输出 JSON 之外的任何文字。"""
    _IMMEDIATE_CHILDREN = {
        "outline": "plot",
        "plot": "event",
        "event": "scene",
        "scene": "chapter",
    }

    class WorkflowChatError(Exception):
        def __init__(self, *, status_code: int, error_code: str, message: str, details: dict[str, Any] | None = None):
            super().__init__(message)
            self.status_code = status_code
            self.error_code = error_code
            self.message = message
            self.details = details or {}

    _VALID_ENTITY_TYPES = {"outline", "setting", "canon_entry"}

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        from core.agent_runtime.chat_service import ChatService

        self.chat_service = ChatService(self.project_root)
        self.registry = ChatSkillRegistry(self.project_root)
        self.hierarchy_service = BookHierarchyService(self.project_root)

    def create_chat(self, request: Any) -> dict[str, Any]:
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

    def send_message(self, chat_id: str, content: str, workflow: dict[str, Any] | None = None) -> dict:
        assistant_message = self._run_completion(chat_id, content, workflow=workflow)
        return assistant_message.to_dict(include_parts=True)

    def send_and_stream(self, chat_id: str, content: str, workflow: dict[str, Any] | None = None) -> Generator[str, None, None]:
        self._require_chat(chat_id)
        prepared_workflow = self.prepare_workflow(workflow) if workflow else None
        self.chat_service.add_user_message(chat_id, content)
        assistant_message_id = generate_id("msg")
        self._create_streaming_message(chat_id, assistant_message_id)

        adapter = ChatStreamAdapter(config=DataModulesConfig(project_root=self.project_root))
        collected_text = ""
        collected_parts: list[dict[str, object]] = []
        completed = False
        error_payload: dict[str, str] | None = None
        for event_str in self._stream_chat_events(
            adapter=adapter,
            chat_id=chat_id,
            message_id=assistant_message_id,
            messages=self._messages_for_llm(chat_id, prepared_workflow),
            workflow=prepared_workflow,
        ):
            event_type, payload = self._parse_sse_event(event_str)
            if event_type == EVENT_TEXT_DELTA:
                collected_text += str(payload.get("delta") or "")
            elif event_type == EVENT_TOOL_CALL:
                collected_parts.append({"type": "tool_call", "payload": dict(payload)})
            elif event_type == EVENT_TOOL_RESULT:
                collected_parts.append({"type": "tool_result", "payload": dict(payload)})
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
                parts=self._finalize_response_parts(prepared_workflow, collected_text, collected_parts),
            )

    def get_chat_skills(self, chat_id: str) -> list[dict]:
        self._require_chat(chat_id)
        mounted = self.chat_service.get_chat_skills(chat_id)
        return self._enrich_skills(mounted)

    def update_chat_skills(self, chat_id: str, skills: list[dict]) -> list[dict]:
        self._require_chat(chat_id)
        mounted = self.chat_service.mount_skills(chat_id, skills)
        return self._enrich_skills(mounted)

    def generate_skill_draft(self, prompt: str, current_draft: dict[str, Any] | None = None) -> dict[str, Any]:
        normalized_prompt = str(prompt or "").strip()
        if not normalized_prompt:
            raise self.WorkflowChatError(
                status_code=400,
                error_code="skill_draft_prompt_required",
                message="Skill draft prompt is required.",
            )

        config = DataModulesConfig(project_root=self.project_root)
        provider = str(getattr(config, "generation_api_type", "local") or "local").strip().lower()
        api_key = str(getattr(config, "generation_api_key", "") or "").strip()
        if provider in {"", "local", "stub"} or not api_key:
            raise self.WorkflowChatError(
                status_code=503,
                error_code="generation_unavailable",
                message="Generation provider is not configured for real skill draft generation.",
                details={"provider": provider or "local"},
            )

        from scripts.data_modules.generation_client import GenerationAPIClient

        messages = self._skill_draft_messages(normalized_prompt, current_draft or {})
        try:
            payload = GenerationAPIClient(config).complete_json(messages=messages)
        except Exception as exc:
            raise self.WorkflowChatError(
                status_code=502,
                error_code="skill_draft_generation_failed",
                message="Skill draft generation failed.",
                details={"error": str(exc)},
            ) from exc

        draft = self._normalize_skill_draft_payload(payload, current_draft or {})
        field_errors = self._validate_generated_skill_draft(draft)
        if field_errors:
            raise self.WorkflowChatError(
                status_code=422,
                error_code="skill_draft_invalid",
                message="Generated skill draft is incomplete.",
                details={"field_errors": field_errors},
            )
        return {
            "reply": str(payload.get("reply") or "已基于你的要求生成新的 skill 草稿。"),
            "draft": draft,
        }

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

    def _messages_for_llm(self, chat_id: str, workflow: dict[str, Any] | None = None) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        system_prompt = self._build_system_prompt(chat_id, workflow)
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for message in self.chat_service.get_chat_history(chat_id):
            text = self._extract_text(message)
            if text:
                messages.append({"role": message.role, "content": text})
        return messages

    def _build_system_prompt(self, chat_id: str, workflow: dict[str, Any] | None = None) -> str:
        sections = [self._BASE_SYSTEM_PROMPT]

        project_context = self._project_context_text()
        if project_context:
            sections.append(f"项目上下文：\n{project_context}")

        skill_instructions = self._skill_instruction_text(chat_id)
        if skill_instructions:
            sections.append(f"已挂载 Skill 指令：\n{skill_instructions}")

        workflow_context = self._workflow_context_text(workflow)
        if workflow_context:
            sections.append(workflow_context)

        hierarchy_tool_guidance = self._hierarchy_tool_guidance_text(workflow)
        if hierarchy_tool_guidance:
            sections.append(hierarchy_tool_guidance)

        return "\n\n".join(section for section in sections if section)

    def prepare_workflow(self, workflow: dict[str, Any] | None) -> dict[str, Any] | None:
        if workflow is None:
            return None
        action = str(workflow.get("action") or "").strip()
        book_id = str(workflow.get("book_id") or "").strip()
        node_type = str(workflow.get("node_type") or "").strip()
        node_id = str(workflow.get("node_id") or "").strip()
        target_type = str(workflow.get("target_type") or "").strip()

        if not node_type or not node_id:
            raise self.WorkflowChatError(
                status_code=400,
                error_code="workflow_node_required",
                message="Workflow actions require a selected hierarchy node.",
                details={"action": action},
            )

        node = self.hierarchy_service.repository.get_entity(node_type, node_id)
        if node is None or getattr(node, "book_id", None) != book_id:
            raise self.WorkflowChatError(
                status_code=404,
                error_code="workflow_node_not_found",
                message="Workflow node was not found.",
                details={"book_id": book_id, "node_type": node_type, "node_id": node_id},
            )

        parent = self._workflow_parent(node_type, node)
        expected_target_type = self._IMMEDIATE_CHILDREN.get(node_type)
        if action == "split":
            if target_type != expected_target_type:
                raise self.WorkflowChatError(
                    status_code=400,
                    error_code="invalid_workflow_target",
                    message="Workflow target does not match the allowed immediate child type.",
                    details={
                        "action": action,
                        "node_type": node_type,
                        "target_type": target_type,
                        "expected_target_type": expected_target_type,
                    },
                )
        elif action == "edit":
            if node_type != "chapter":
                raise self.WorkflowChatError(
                    status_code=400,
                    error_code="invalid_workflow_target",
                    message="Workflow target does not match the allowed immediate child type.",
                    details={
                        "action": action,
                        "node_type": node_type,
                        "target_type": node_type,
                        "expected_target_type": "chapter",
                    },
                )

        return {
            "action": action,
            "book_id": book_id,
            "node_type": node_type,
            "node_id": node_id,
            "target_type": target_type or expected_target_type,
            "node": node,
            "parent": parent,
        }

    def _workflow_context_text(self, workflow: dict[str, Any] | None) -> str:
        if workflow is None:
            return ""
        canon_entries = self.hierarchy_service.repository.list_canon_entries(book_id=str(workflow["book_id"]))
        sections: list[str] = []
        if canon_entries:
            canon_lines = ["已批准 Canon："]
            for entry in canon_entries:
                canon_lines.append(f"- 标题：{entry.title}")
                canon_lines.append(f"  内容：{entry.body}")
            sections.append("\n".join(canon_lines))

        node = workflow["node"]
        node_lines = ["当前节点：", f"- 类型：{workflow['node_type']}", f"- 标题：{node.title}"]
        if getattr(node, "body", ""):
            node_lines.append(f"- 内容：{node.body}")
        sections.append("\n".join(node_lines))

        parent = workflow.get("parent")
        if parent is not None:
            parent_type = self._parent_type(str(workflow["node_type"]))
            parent_lines = ["直接父节点：", f"- 类型：{parent_type}", f"- 标题：{parent.title}"]
            if getattr(parent, "body", ""):
                parent_lines.append(f"- 内容：{parent.body}")
            sections.append("\n".join(parent_lines))
        return "\n\n".join(sections)

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

    def _skill_draft_messages(self, prompt: str, current_draft: dict[str, Any]) -> list[dict[str, str]]:
        sections = [self._SKILL_DRAFT_SYSTEM_PROMPT]
        project_context = self._project_context_text()
        if project_context:
            sections.append(f"当前项目上下文：\n{project_context}")
        normalized_draft = self._normalize_skill_draft_payload(current_draft, {})
        sections.append(
            "当前草稿：\n" + json.dumps(normalized_draft, ensure_ascii=False, indent=2)
        )
        return [
            {"role": "system", "content": "\n\n".join(section for section in sections if section)},
            {"role": "user", "content": prompt},
        ]

    @staticmethod
    def _normalize_skill_draft_payload(payload: dict[str, Any], current_draft: dict[str, Any]) -> dict[str, str]:
        merged = {
            "skill_id": str(payload.get("skill_id") or current_draft.get("skill_id") or "").strip(),
            "name": str(payload.get("name") or current_draft.get("name") or "").strip(),
            "description": str(payload.get("description") or current_draft.get("description") or "").strip(),
            "instruction_template": str(
                payload.get("instruction_template")
                or current_draft.get("instruction_template")
                or ""
            ).strip(),
        }
        merged["skill_id"] = ChatOrchestrationService._normalize_skill_id(merged["skill_id"])
        return merged

    @staticmethod
    def _validate_generated_skill_draft(draft: dict[str, str]) -> dict[str, str]:
        field_errors: dict[str, str] = {}
        if not str(draft.get("skill_id") or "").strip():
            field_errors["skill_id"] = "Skill ID is required."
        if not str(draft.get("name") or "").strip():
            field_errors["name"] = "Name is required."
        if not str(draft.get("instruction_template") or "").strip():
            field_errors["instruction_template"] = "Instruction template is required."
        return field_errors

    @staticmethod
    def _normalize_skill_id(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9-]+", "-", str(value or "").strip().lower())
        normalized = re.sub(r"-{2,}", "-", normalized)
        return normalized.strip("-")

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
            full_content = (self.registry.get_skill_content(skill_id, source=source) or "").strip()

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
                payload = part.get("payload")
                normalized_payload = dict(payload) if isinstance(payload, dict) else {}
                created_parts.append(
                    repository._insert_part(
                        connection,
                        part_id=generate_id("part"),
                        message_id=message_id,
                        seq=index,
                        part_type=cast(Any, str(part["type"])),
                        payload=normalized_payload,
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

    def _run_completion(self, chat_id: str, content: str, workflow: dict[str, Any] | None = None) -> Message:
        self._require_chat(chat_id)
        prepared_workflow = self.prepare_workflow(workflow) if workflow else None
        self.chat_service.add_user_message(chat_id, content)
        assistant_message_id = generate_id("msg")
        self._create_streaming_message(chat_id, assistant_message_id)

        adapter = ChatStreamAdapter(config=DataModulesConfig(project_root=self.project_root))
        collected_text = ""
        collected_parts: list[dict[str, object]] = []
        completed = False
        error_payload: dict[str, str] | None = None
        for event_str in self._stream_chat_events(
            adapter=adapter,
            chat_id=chat_id,
            message_id=assistant_message_id,
            messages=self._messages_for_llm(chat_id, prepared_workflow),
            workflow=prepared_workflow,
        ):
            event_type, payload = self._parse_sse_event(event_str)
            if event_type == EVENT_TEXT_DELTA:
                collected_text += str(payload.get("delta") or "")
            elif event_type == EVENT_TOOL_CALL:
                collected_parts.append({"type": "tool_call", "payload": dict(payload)})
            elif event_type == EVENT_TOOL_RESULT:
                collected_parts.append({"type": "tool_result", "payload": dict(payload)})
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
            parts=self._finalize_response_parts(prepared_workflow, collected_text, collected_parts),
        )

    def _finalize_response_parts(
        self,
        workflow: dict[str, Any] | None,
        collected_text: str,
        collected_parts: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        parts = list(collected_parts)
        if collected_text or not parts:
            parts.append({"type": "text", "payload": {"text": collected_text}})
        if workflow is None:
            return parts
        payload = self._parse_workflow_payload(collected_text)
        proposal = self._create_workflow_proposal(workflow, payload)
        parts.append(
            {
                "type": "tool_result",
                "payload": {
                    "action": workflow["action"],
                    "proposal": self._serialize(proposal),
                },
            }
        )
        return parts

    @staticmethod
    def _hierarchy_tools_for_chat(workflow: dict[str, Any] | None) -> list[dict[str, Any]] | None:
        if workflow is not None:
            return None
        return get_hierarchy_tool_definitions()

    def _hierarchy_tool_dispatcher(
        self,
        workflow: dict[str, Any] | None,
    ) -> Callable[[str, dict[str, Any]], dict[str, Any]] | None:
        if workflow is not None:
            return None
        return self.dispatch_hierarchy_tool

    def _stream_chat_events(
        self,
        *,
        adapter: ChatStreamAdapter,
        chat_id: str,
        message_id: str,
        messages: list[dict[str, str]],
        workflow: dict[str, Any] | None,
    ) -> Iterator[str]:
        tools = self._hierarchy_tools_for_chat(workflow)
        tool_dispatcher = self._hierarchy_tool_dispatcher(workflow)
        stream_parameters = inspect.signature(adapter.stream_chat).parameters
        supports_tool_kwargs = "tools" in stream_parameters and "tool_dispatcher" in stream_parameters
        if tools and tool_dispatcher is not None and supports_tool_kwargs:
            return adapter.stream_chat(
                messages=messages,
                message_id=message_id,
                chat_id=chat_id,
                tools=tools,
                tool_dispatcher=tool_dispatcher,
            )
        return adapter.stream_chat(
            messages=messages,
            message_id=message_id,
            chat_id=chat_id,
        )

    def _hierarchy_tool_guidance_text(self, workflow: dict[str, Any] | None) -> str:
        if workflow is not None:
            return ""
        return self._HIERARCHY_TOOL_PROMPT

    @staticmethod
    def _parse_workflow_payload(text: str) -> dict[str, Any]:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _create_workflow_proposal(self, workflow: dict[str, Any], payload: dict[str, Any]):
        action = str(workflow["action"])
        book_id = str(workflow["book_id"])
        node_type = str(workflow["node_type"])
        node_id = str(workflow["node_id"])
        if action == "split":
            proposed_children = payload.get("proposed_children")
            if not isinstance(proposed_children, list) or not proposed_children:
                raise self.WorkflowChatError(
                    status_code=400,
                    error_code="workflow_generation_invalid",
                    message="Workflow generation result is missing proposed children.",
                    details={"action": action, "node_type": node_type},
                )
            return self.hierarchy_service.create_structural_proposal(
                book_id,
                parent_type=node_type,
                parent_id=node_id,
                child_type=str(workflow["target_type"]),
                proposal_type=f"{node_type}_split",
                proposed_children=[dict(item) for item in proposed_children if isinstance(item, dict)],
            )
        if action == "extract":
            return self.hierarchy_service.create_canon_extraction_proposal(
                book_id,
                source_type=node_type,
                source_id=node_id,
                title=str(payload.get("title") or ""),
                body=str(payload.get("body") or ""),
                metadata=dict(payload.get("metadata") or {}),
            )
        if action == "edit":
            return self.hierarchy_service.create_chapter_edit_proposal(
                book_id,
                chapter_id=node_id,
                summary=str(payload.get("summary") or ""),
                proposed_update={
                    "title": str(payload.get("title") or getattr(workflow["node"], "title", "")),
                    "body": str(payload.get("body") or getattr(workflow["node"], "body", "")),
                    "metadata": dict(payload.get("metadata") or {}),
                },
            )
        raise self.WorkflowChatError(
            status_code=400,
            error_code="invalid_workflow_action",
            message="Workflow action is not supported.",
            details={"action": action},
        )

    def _workflow_parent(self, node_type: str, node: Any):
        parent_type = self._parent_type(node_type)
        if parent_type is None:
            return None
        parent_id = getattr(node, f"{parent_type}_id", None)
        if not isinstance(parent_id, str):
            return None
        return self.hierarchy_service.repository.get_entity(parent_type, parent_id)

    @staticmethod
    def _parent_type(node_type: str) -> str | None:
        return {
            "plot": "outline",
            "event": "plot",
            "scene": "event",
            "chapter": "scene",
        }.get(node_type)

    @staticmethod
    def _serialize(value: Any) -> Any:
        if is_dataclass(value):
            return asdict(cast(Any, value))
        if isinstance(value, list):
            return [ChatOrchestrationService._serialize(item) for item in value]
        if isinstance(value, dict):
            return {key: ChatOrchestrationService._serialize(item) for key, item in value.items()}
        return value

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

    # ── Hierarchy tool dispatch ─────────────────────────────────────

    def dispatch_hierarchy_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a hierarchy CRUD tool call and return the result."""
        try:
            match tool_name:
                case "hierarchy_list":
                    return self._tool_hierarchy_list(arguments)
                case "hierarchy_read":
                    return self._tool_hierarchy_read(arguments)
                case "hierarchy_update":
                    return self._tool_hierarchy_update(arguments)
                case "hierarchy_create":
                    return self._tool_hierarchy_create(arguments)
                case _:
                    return {"error": f"Unknown tool: {tool_name}"}
        except Exception as exc:
            return {"error": str(exc)}

    def _tool_hierarchy_list(self, arguments: dict[str, Any]) -> dict[str, Any]:
        entity_type = str(arguments.get("entity_type") or "").strip()
        if entity_type not in self._VALID_ENTITY_TYPES:
            return {"error": f"Invalid entity_type '{entity_type}'. Must be one of: {', '.join(sorted(self._VALID_ENTITY_TYPES))}"}

        book_id = self._require_active_book_id()
        repo = self.hierarchy_service.repository
        match entity_type:
            case "outline":
                items = repo.list_outlines(book_id=book_id)
            case "setting":
                items = repo.list_settings(book_id=book_id)
            case "canon_entry":
                items = repo.list_canon_entries(book_id=book_id)
            case _:
                items = []

        result = []
        for item in items:
            entity_id = str(getattr(item, f"{entity_type}_id", "") or getattr(item, "canon_id", ""))
            synopsis = str(item.body or "")[:200]
            result.append({"id": entity_id, "entity_type": entity_type, "title": str(item.title or ""), "synopsis": synopsis})
        return {"entity_type": entity_type, "items": result}

    def _tool_hierarchy_read(self, arguments: dict[str, Any]) -> dict[str, Any]:
        entity_type = str(arguments.get("entity_type") or "").strip()
        entity_id = str(arguments.get("entity_id") or "").strip()

        if entity_type not in self._VALID_ENTITY_TYPES:
            return {"error": f"Invalid entity_type '{entity_type}'. Must be one of: {', '.join(sorted(self._VALID_ENTITY_TYPES))}"}
        if not entity_id:
            return {"error": "entity_id is required."}

        entity = self.hierarchy_service.repository.get_entity(entity_type, entity_id)
        if entity is None:
            return {"error": f"{entity_type} '{entity_id}' not found."}

        return {
            "id": entity_id,
            "entity_type": entity_type,
            "title": str(entity.title or ""),
            "body": str(entity.body or ""),
            "version": entity.version,
        }

    def _tool_hierarchy_update(self, arguments: dict[str, Any]) -> dict[str, Any]:
        entity_type = str(arguments.get("entity_type") or "").strip()
        entity_id = str(arguments.get("entity_id") or "").strip()
        title = arguments.get("title")
        body = arguments.get("body")

        if entity_type not in self._VALID_ENTITY_TYPES:
            return {"error": f"Invalid entity_type '{entity_type}'. Must be one of: {', '.join(sorted(self._VALID_ENTITY_TYPES))}"}
        if not entity_id:
            return {"error": "entity_id is required."}
        if title is None and body is None:
            return {"error": "At least one of 'title' or 'body' must be provided."}

        entity = self.hierarchy_service.repository.get_entity(entity_type, entity_id)
        if entity is None:
            return {"error": f"{entity_type} '{entity_id}' not found."}

        book_id = str(entity.book_id)
        previous_title = str(entity.title or "")
        previous_body = str(entity.body or "")
        update_title = str(title) if title is not None else None
        update_body = str(body) if body is not None else None

        match entity_type:
            case "outline":
                self.hierarchy_service.update_outline(
                    book_id, entity_id,
                    expected_version=entity.version,
                    title=update_title,
                    body=update_body,
                )
            case "setting":
                self.hierarchy_service.update_setting(
                    book_id, entity_id,
                    expected_version=entity.version,
                    title=update_title,
                    body=update_body,
                )
            case "canon_entry":
                self.hierarchy_service.update_canon_entry(
                    book_id, entity_id,
                    expected_version=entity.version,
                    title=update_title,
                    body=update_body,
                )

        updated = self.hierarchy_service.repository.get_entity(entity_type, entity_id)
        next_title = str(updated.title or "") if updated else ""
        next_body = str(updated.body or "") if updated else ""
        changes: dict[str, dict[str, str]] = {}
        if update_title is not None and previous_title != next_title:
            changes["title"] = {"before": previous_title, "after": next_title}
        if update_body is not None and previous_body != next_body:
            changes["body"] = {"before": previous_body, "after": next_body}
        return {
            "id": entity_id,
            "entity_type": entity_type,
            "title": next_title,
            "body": next_body,
            "version": updated.version if updated else None,
            "updated": True,
            "changes": changes,
            "change_summary": f"Updated {entity_type} '{entity_id}' with {', '.join(changes.keys()) or 'no field changes' }.",
        }

    def _tool_hierarchy_create(self, arguments: dict[str, Any]) -> dict[str, Any]:
        entity_type = str(arguments.get("entity_type") or "").strip()
        title = str(arguments.get("title") or "").strip()
        body = str(arguments.get("body") or "")

        if entity_type not in self._VALID_ENTITY_TYPES:
            return {"error": f"Invalid entity_type '{entity_type}'. Must be one of: {', '.join(sorted(self._VALID_ENTITY_TYPES))}"}
        if not title:
            return {"error": "title is required."}

        book_id = self._require_active_book_id()

        match entity_type:
            case "outline":
                created = self.hierarchy_service.create_outline(book_id, title=title, body=body)
                entity_id = created.outline_id
            case "setting":
                created = self.hierarchy_service.create_setting(book_id, title=title, body=body)
                entity_id = created.setting_id
            case "canon_entry":
                created = self.hierarchy_service.create_canon_entry(book_id, title=title, body=body)
                entity_id = created.canon_id
            case _:
                return {"error": f"Unsupported entity_type '{entity_type}'."}

        return {
            "id": entity_id,
            "entity_type": entity_type,
            "title": title,
            "body": body,
            "created": True,
            "change_summary": f"Created new {entity_type} '{title}' ({entity_id}).",
        }

    def _require_active_book_id(self) -> str:
        """Get the active book root ID for the current project."""
        book = self.hierarchy_service.repository.get_active_book_root(str(self.project_root))
        if book is None:
            raise self.WorkflowChatError(
                status_code=404,
                error_code="book_root_not_found",
                message="No active book root found for this project.",
            )
        return str(book.book_id)
