from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS chats (
        chat_id     TEXT PRIMARY KEY,
        project_root TEXT NOT NULL,
        title       TEXT NOT NULL DEFAULT '',
        profile     TEXT,
        created_at  TEXT NOT NULL,
        updated_at  TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        message_id  TEXT PRIMARY KEY,
        chat_id     TEXT NOT NULL REFERENCES chats(chat_id),
        role        TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
        status      TEXT NOT NULL DEFAULT 'complete' CHECK(status IN ('streaming', 'complete', 'error')),
        created_at  TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id)",
    """
    CREATE TABLE IF NOT EXISTS message_parts (
        part_id     TEXT PRIMARY KEY,
        message_id  TEXT NOT NULL REFERENCES messages(message_id),
        seq         INTEGER NOT NULL,
        type        TEXT NOT NULL CHECK(type IN ('text', 'tool_call', 'tool_result', 'error', 'reasoning')),
        payload     TEXT NOT NULL DEFAULT '{}'
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_parts_message_id ON message_parts(message_id)",
    """
    CREATE TABLE IF NOT EXISTS chat_skills (
        chat_id     TEXT NOT NULL REFERENCES chats(chat_id),
        skill_id    TEXT NOT NULL,
        enabled     INTEGER NOT NULL DEFAULT 1,
        source      TEXT NOT NULL DEFAULT 'built-in',
        attached_at TEXT NOT NULL,
        PRIMARY KEY (chat_id, skill_id)
    )
    """,
)


def get_chat_db_path(project_root: Path) -> Path:
    return project_root / ".webnovel" / "chat.db"


def ensure_schema(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.commit()
