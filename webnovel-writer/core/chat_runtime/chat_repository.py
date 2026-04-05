from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .chat_models import Chat, Message, MessagePart, MessageRole, MessageStatus, PartType
from .chat_schema import ensure_schema


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ChatRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        ensure_schema(db_path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _row_to_chat(row: sqlite3.Row) -> Chat:
        return Chat.from_dict(dict(row))

    @staticmethod
    def _row_to_message(row: sqlite3.Row, *, parts: list[MessagePart] | None = None) -> Message:
        payload = dict(row)
        if parts is not None:
            payload["parts"] = [part.to_dict() for part in parts]
        return Message.from_dict(payload)

    @staticmethod
    def _row_to_part(row: sqlite3.Row) -> MessagePart:
        payload = dict(row)
        payload["payload"] = json.loads(str(row["payload"]))
        return MessagePart.from_dict(payload)

    def _touch_chat(self, connection: sqlite3.Connection, chat_id: str) -> None:
        connection.execute(
            "UPDATE chats SET updated_at = ? WHERE chat_id = ?",
            (utc_now_iso(), chat_id),
        )

    def _insert_message(
        self,
        connection: sqlite3.Connection,
        *,
        message_id: str,
        chat_id: str,
        role: MessageRole,
        status: MessageStatus,
    ) -> Message:
        created_at = utc_now_iso()
        connection.execute(
            "INSERT INTO messages (message_id, chat_id, role, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (message_id, chat_id, role, status, created_at),
        )
        self._touch_chat(connection, chat_id)
        return Message(
            message_id=message_id,
            chat_id=chat_id,
            role=role,
            status=status,
            created_at=created_at,
        )

    def _insert_part(
        self,
        connection: sqlite3.Connection,
        *,
        part_id: str,
        message_id: str,
        seq: int,
        part_type: PartType,
        payload: dict[str, object],
    ) -> MessagePart:
        normalized_payload = dict(payload)
        connection.execute(
            "INSERT INTO message_parts (part_id, message_id, seq, type, payload) VALUES (?, ?, ?, ?, ?)",
            (part_id, message_id, seq, part_type, json.dumps(normalized_payload, ensure_ascii=False, sort_keys=True)),
        )
        return MessagePart(
            part_id=part_id,
            message_id=message_id,
            seq=seq,
            type=part_type,
            payload=normalized_payload,
        )

    # Chat CRUD
    def create_chat(self, chat_id: str, project_root: str, title: str, profile: str | None) -> Chat:
        timestamp = utc_now_iso()
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO chats (chat_id, project_root, title, profile, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (chat_id, project_root, title, profile, timestamp, timestamp),
            )
            connection.commit()
        return Chat(
            chat_id=chat_id,
            project_root=project_root,
            title=title,
            profile=profile,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def get_chat(self, chat_id: str) -> Chat | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT chat_id, project_root, title, profile, created_at, updated_at FROM chats WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
        return self._row_to_chat(row) if row else None

    def list_chats(self, project_root: str) -> list[Chat]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT chat_id, project_root, title, profile, created_at, updated_at FROM chats WHERE project_root = ? ORDER BY updated_at DESC, created_at DESC",
                (project_root,),
            ).fetchall()
        return [self._row_to_chat(row) for row in rows]

    def delete_chat(self, chat_id: str) -> bool:
        with self._connection() as connection:
            message_ids = [
                str(row["message_id"])
                for row in connection.execute(
                    "SELECT message_id FROM messages WHERE chat_id = ?",
                    (chat_id,),
                ).fetchall()
            ]
            for message_id in message_ids:
                connection.execute("DELETE FROM message_parts WHERE message_id = ?", (message_id,))
            connection.execute("DELETE FROM chat_skills WHERE chat_id = ?", (chat_id,))
            connection.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
            cursor = connection.execute("DELETE FROM chats WHERE chat_id = ?", (chat_id,))
            connection.commit()
            return cursor.rowcount > 0

    def update_chat_title(self, chat_id: str, title: str) -> bool:
        updated_at = utc_now_iso()
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE chats SET title = ?, updated_at = ? WHERE chat_id = ?",
                (title, updated_at, chat_id),
            )
            connection.commit()
            return cursor.rowcount > 0

    # Message CRUD
    def add_message(self, message_id: str, chat_id: str, role: MessageRole, status: MessageStatus = "complete") -> Message:
        with self._connection() as connection:
            message = self._insert_message(
                connection,
                message_id=message_id,
                chat_id=chat_id,
                role=role,
                status=status,
            )
            connection.commit()
        return message

    def get_message(self, message_id: str) -> Message | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT message_id, chat_id, role, status, created_at FROM messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
        return self._row_to_message(row) if row else None

    def list_messages(self, chat_id: str) -> list[Message]:
        with self._connection() as connection:
            message_rows = connection.execute(
                "SELECT message_id, chat_id, role, status, created_at FROM messages WHERE chat_id = ? ORDER BY created_at ASC, message_id ASC",
                (chat_id,),
            ).fetchall()
            message_ids = [str(row["message_id"]) for row in message_rows]
            parts_by_message: dict[str, list[MessagePart]] = {message_id: [] for message_id in message_ids}
            if message_rows:
                part_rows = connection.execute(
                    """
                    SELECT part_id, message_id, seq, type, payload
                    FROM message_parts
                    WHERE message_id IN (
                        SELECT message_id FROM messages WHERE chat_id = ?
                    )
                    ORDER BY message_id ASC, seq ASC, part_id ASC
                    """,
                    (chat_id,),
                ).fetchall()
                for row in part_rows:
                    part = self._row_to_part(row)
                    parts_by_message.setdefault(part.message_id, []).append(part)
        return [
            self._row_to_message(row, parts=parts_by_message.get(str(row["message_id"]), []))
            for row in message_rows
        ]

    def update_message_status(self, message_id: str, status: MessageStatus) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT chat_id FROM messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
            if row is None:
                return False
            cursor = connection.execute(
                "UPDATE messages SET status = ? WHERE message_id = ?",
                (status, message_id),
            )
            self._touch_chat(connection, str(row["chat_id"]))
            connection.commit()
            return cursor.rowcount > 0

    # MessagePart CRUD
    def add_part(self, part_id: str, message_id: str, seq: int, part_type: PartType, payload: dict[str, object]) -> MessagePart:
        with self._connection() as connection:
            part = self._insert_part(
                connection,
                part_id=part_id,
                message_id=message_id,
                seq=seq,
                part_type=part_type,
                payload=payload,
            )
            row = connection.execute(
                "SELECT chat_id FROM messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
            if row is not None:
                self._touch_chat(connection, str(row["chat_id"]))
            connection.commit()
        return part

    def list_parts(self, message_id: str) -> list[MessagePart]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT part_id, message_id, seq, type, payload FROM message_parts WHERE message_id = ? ORDER BY seq ASC, part_id ASC",
                (message_id,),
            ).fetchall()
        return [self._row_to_part(row) for row in rows]

    def get_full_message(self, message_id: str) -> Message | None:
        with self._connection() as connection:
            message_row = connection.execute(
                "SELECT message_id, chat_id, role, status, created_at FROM messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
            if message_row is None:
                return None
            part_rows = connection.execute(
                "SELECT part_id, message_id, seq, type, payload FROM message_parts WHERE message_id = ? ORDER BY seq ASC, part_id ASC",
                (message_id,),
            ).fetchall()
        return self._row_to_message(message_row, parts=[self._row_to_part(row) for row in part_rows])

    # ChatSkills CRUD
    def mount_skill(self, chat_id: str, skill_id: str, source: str = "built-in") -> None:
        attached_at = utc_now_iso()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO chat_skills (chat_id, skill_id, enabled, source, attached_at)
                VALUES (?, ?, 1, ?, ?)
                ON CONFLICT(chat_id, skill_id) DO UPDATE SET
                    enabled = 1,
                    source = excluded.source,
                    attached_at = excluded.attached_at
                """,
                (chat_id, skill_id, source, attached_at),
            )
            self._touch_chat(connection, chat_id)
            connection.commit()

    def unmount_skill(self, chat_id: str, skill_id: str) -> None:
        with self._connection() as connection:
            connection.execute(
                "DELETE FROM chat_skills WHERE chat_id = ? AND skill_id = ?",
                (chat_id, skill_id),
            )
            self._touch_chat(connection, chat_id)
            connection.commit()

    def unmount_skill_everywhere(self, skill_id: str, *, source: str | None = None) -> None:
        with self._connection() as connection:
            if source:
                connection.execute(
                    "DELETE FROM chat_skills WHERE skill_id = ? AND source = ?",
                    (skill_id, source),
                )
            else:
                connection.execute(
                    "DELETE FROM chat_skills WHERE skill_id = ?",
                    (skill_id,),
                )
            connection.commit()

    def list_chat_skills(self, chat_id: str) -> list[dict[str, object]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT chat_id, skill_id, enabled, source, attached_at FROM chat_skills WHERE chat_id = ? ORDER BY attached_at ASC, skill_id ASC",
                (chat_id,),
            ).fetchall()
        return [
            {
                "chat_id": str(row["chat_id"]),
                "skill_id": str(row["skill_id"]),
                "enabled": bool(row["enabled"]),
                "source": str(row["source"]),
                "attached_at": str(row["attached_at"]),
            }
            for row in rows
        ]

    def set_skill_enabled(self, chat_id: str, skill_id: str, enabled: bool) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE chat_skills SET enabled = ? WHERE chat_id = ? AND skill_id = ?",
                (1 if enabled else 0, chat_id, skill_id),
            )
            self._touch_chat(connection, chat_id)
            connection.commit()
