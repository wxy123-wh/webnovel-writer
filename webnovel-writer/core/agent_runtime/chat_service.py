from __future__ import annotations

from pathlib import Path

from .chat_models import Chat, Message, MessageStatus
from .chat_repository import ChatRepository, generate_id
from .chat_schema import ensure_schema, get_chat_db_path


class ChatService:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.db_path = get_chat_db_path(project_root)
        ensure_schema(self.db_path)
        self.repository = ChatRepository(self.db_path)

    def create_chat(
        self,
        title: str,
        profile: str | None = None,
        skill_ids: list[str] | None = None,
    ) -> Chat:
        chat = self.repository.create_chat(
            chat_id=generate_id("chat"),
            project_root=str(self.project_root),
            title=title,
            profile=profile,
        )
        for skill_id in skill_ids or []:
            self.repository.mount_skill(chat.chat_id, skill_id)
        return self.get_chat(chat.chat_id) or chat

    def get_chat(self, chat_id: str) -> Chat | None:
        return self.repository.get_chat(chat_id)

    def list_chats(self) -> list[Chat]:
        return self.repository.list_chats(str(self.project_root))

    def delete_chat(self, chat_id: str) -> bool:
        return self.repository.delete_chat(chat_id)

    def add_user_message(self, chat_id: str, content: str) -> Message:
        message_id = generate_id("msg")
        part_id = generate_id("part")
        with self.repository._connection() as connection:
            message = self.repository._insert_message(
                connection,
                message_id=message_id,
                chat_id=chat_id,
                role="user",
                status="complete",
            )
            part = self.repository._insert_part(
                connection,
                part_id=part_id,
                message_id=message_id,
                seq=0,
                part_type="text",
                payload={"text": content},
            )
            connection.commit()
        message.parts.append(part)
        return message

    def add_assistant_message(
        self,
        chat_id: str,
        parts: list[dict],
        status: MessageStatus = "complete",
    ) -> Message:
        message_id = generate_id("msg")
        with self.repository._connection() as connection:
            message = self.repository._insert_message(
                connection,
                message_id=message_id,
                chat_id=chat_id,
                role="assistant",
                status=status,
            )
            created_parts = []
            for index, part in enumerate(parts):
                created_parts.append(
                    self.repository._insert_part(
                        connection,
                        part_id=generate_id("part"),
                        message_id=message_id,
                        seq=int(part.get("seq", index)),
                        part_type=str(part["type"]),
                        payload=dict(part.get("payload") or {}),
                    )
                )
            connection.commit()
        message.parts.extend(sorted(created_parts, key=lambda item: (item.seq, item.part_id)))
        return message

    def get_chat_history(self, chat_id: str) -> list[Message]:
        return self.repository.list_messages(chat_id)

    def mount_skills(self, chat_id: str, skills: list[dict]) -> list[dict]:
        for skill in skills:
            skill_id = str(skill["skill_id"])
            source = str(skill.get("source") or "system")
            self.repository.mount_skill(chat_id, skill_id, source=source)
            if "enabled" in skill:
                self.repository.set_skill_enabled(chat_id, skill_id, bool(skill["enabled"]))
        return self.repository.list_chat_skills(chat_id)

    def get_chat_skills(self, chat_id: str) -> list[dict]:
        return self.repository.list_chat_skills(chat_id)
