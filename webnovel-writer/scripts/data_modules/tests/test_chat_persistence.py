#!/usr/bin/env python3

from __future__ import annotations

from core.agent_runtime import ChatRepository, ChatService
from core.agent_runtime.chat_repository import generate_id
from core.agent_runtime.chat_schema import ensure_schema, get_chat_db_path


def test_schema_bootstrap_is_idempotent(tmp_path):
    db_path = get_chat_db_path(tmp_path)

    ensure_schema(db_path)
    ensure_schema(db_path)

    assert db_path.exists()


def test_create_chat_and_retrieve_it(tmp_path):
    repository = ChatRepository(get_chat_db_path(tmp_path))
    chat = repository.create_chat(
        chat_id=generate_id("chat"),
        project_root=str(tmp_path),
        title="Draft session",
        profile="default",
    )

    fetched = repository.get_chat(chat.chat_id)

    assert fetched is not None
    assert fetched.to_dict() == chat.to_dict()


def test_list_chats_filtered_by_project_root(tmp_path):
    project_one = tmp_path / "project-one"
    project_two = tmp_path / "project-two"
    repository = ChatRepository(get_chat_db_path(project_one))

    first = repository.create_chat(generate_id("chat"), str(project_one), "One", None)
    second = repository.create_chat(generate_id("chat"), str(project_one), "Two", None)
    repository.create_chat(generate_id("chat"), str(project_two), "Ignored", None)

    chats = repository.list_chats(str(project_one))

    assert {chat.chat_id for chat in chats} == {first.chat_id, second.chat_id}
    assert all(chat.project_root == str(project_one) for chat in chats)


def test_delete_chat_removes_messages_parts_and_skills(tmp_path):
    repository = ChatRepository(get_chat_db_path(tmp_path))
    chat = repository.create_chat(generate_id("chat"), str(tmp_path), "Delete me", None)
    message = repository.add_message(generate_id("msg"), chat.chat_id, "user")
    repository.add_part(generate_id("part"), message.message_id, 0, "text", {"text": "hello"})
    repository.mount_skill(chat.chat_id, "summarize")

    deleted = repository.delete_chat(chat.chat_id)

    assert deleted is True
    assert repository.get_chat(chat.chat_id) is None
    assert repository.get_message(message.message_id) is None
    assert repository.list_parts(message.message_id) == []
    assert repository.list_chat_skills(chat.chat_id) == []


def test_add_user_message_with_text_part_reconstructs_full_message(tmp_path):
    service = ChatService(tmp_path)
    chat = service.create_chat("User chat")

    message = service.add_user_message(chat.chat_id, "Hello writer")
    full_message = service.repository.get_full_message(message.message_id)

    assert full_message is not None
    assert full_message.role == "user"
    assert full_message.status == "complete"
    assert len(full_message.parts) == 1
    assert full_message.parts[0].type == "text"
    assert full_message.parts[0].payload == {"text": "Hello writer"}


def test_add_assistant_message_with_multiple_parts(tmp_path):
    service = ChatService(tmp_path)
    chat = service.create_chat("Assistant chat")

    message = service.add_assistant_message(
        chat.chat_id,
        [
            {"type": "text", "payload": {"text": "Looking up context"}},
            {"type": "tool_call", "payload": {"tool": "search", "args": {"q": "alchemy"}}},
            {"type": "tool_result", "payload": {"tool": "search", "result": ["alchemy notes"]}},
        ],
    )

    history = service.get_chat_history(chat.chat_id)

    assert message.role == "assistant"
    assert [part.type for part in history[0].parts] == ["text", "tool_call", "tool_result"]
    assert history[0].parts[1].payload["tool"] == "search"
    assert history[0].parts[2].payload["result"] == ["alchemy notes"]


def test_parts_are_returned_in_sequence_order(tmp_path):
    repository = ChatRepository(get_chat_db_path(tmp_path))
    chat = repository.create_chat(generate_id("chat"), str(tmp_path), "Ordering", None)
    message = repository.add_message(generate_id("msg"), chat.chat_id, "assistant")

    repository.add_part(generate_id("part"), message.message_id, 2, "tool_result", {"step": 2})
    repository.add_part(generate_id("part"), message.message_id, 0, "text", {"step": 0})
    repository.add_part(generate_id("part"), message.message_id, 1, "tool_call", {"step": 1})

    parts = repository.list_parts(message.message_id)
    full_message = repository.get_full_message(message.message_id)

    assert [part.seq for part in parts] == [0, 1, 2]
    assert full_message is not None
    assert [part.seq for part in full_message.parts] == [0, 1, 2]


def test_message_status_transitions_from_streaming_to_complete(tmp_path):
    repository = ChatRepository(get_chat_db_path(tmp_path))
    chat = repository.create_chat(generate_id("chat"), str(tmp_path), "Streaming", None)
    message = repository.add_message(generate_id("msg"), chat.chat_id, "assistant", status="streaming")

    updated = repository.update_message_status(message.message_id, "complete")
    fetched = repository.get_message(message.message_id)

    assert updated is True
    assert fetched is not None
    assert fetched.status == "complete"


def test_mount_and_unmount_skills(tmp_path):
    service = ChatService(tmp_path)
    chat = service.create_chat("Skills chat")

    mounted = service.mount_skills(
        chat.chat_id,
        [
            {"skill_id": "search", "enabled": True},
            {"skill_id": "planner", "enabled": False, "source": "user"},
        ],
    )
    service.repository.unmount_skill(chat.chat_id, "search")
    remaining = service.get_chat_skills(chat.chat_id)

    assert {skill["skill_id"] for skill in mounted} == {"search", "planner"}
    assert next(skill for skill in mounted if skill["skill_id"] == "planner")["enabled"] is False
    assert remaining == [
        {
            "chat_id": chat.chat_id,
            "skill_id": "planner",
            "enabled": False,
            "source": "user",
            "attached_at": remaining[0]["attached_at"],
        }
    ]


def test_empty_chat_has_no_messages(tmp_path):
    service = ChatService(tmp_path)
    chat = service.create_chat("Empty")

    assert service.get_chat_history(chat.chat_id) == []
