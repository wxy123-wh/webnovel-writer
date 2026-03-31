"""Tests for the chat API router."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from dashboard.app import create_app


@pytest.fixture
def client(tmp_path: Path):
    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir()
    (webnovel_dir / "state.json").write_text("{}", encoding="utf-8")

    app = create_app(project_root=tmp_path)
    with TestClient(app) as test_client:
        yield test_client


class TestChatAPI:
    def test_list_chats_empty(self, client: TestClient):
        response = client.get("/api/chat/chats")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_and_get_chat(self, client: TestClient):
        response = client.post("/api/chat/chats", json={"title": "Test Chat"})
        assert response.status_code == 201
        payload = response.json()
        assert payload["title"] == "Test Chat"
        chat_id = payload["chat_id"]

        follow_up = client.get(f"/api/chat/chats/{chat_id}")
        assert follow_up.status_code == 200
        assert follow_up.json()["title"] == "Test Chat"

    def test_delete_chat(self, client: TestClient):
        create_response = client.post("/api/chat/chats", json={"title": "To Delete"})
        chat_id = create_response.json()["chat_id"]

        delete_response = client.delete(f"/api/chat/chats/{chat_id}")
        assert delete_response.status_code == 204

        missing_response = client.get(f"/api/chat/chats/{chat_id}")
        assert missing_response.status_code == 404

    def test_chat_not_found(self, client: TestClient):
        response = client.get("/api/chat/chats/nonexistent")
        assert response.status_code == 404

    def test_list_skills(self, client: TestClient):
        response = client.get("/api/chat/skills")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_workspace_skills(self, client: TestClient):
        response = client.get("/api/skills")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert isinstance(payload["items"], list)
        assert isinstance(payload["total"], int)
        assert payload["total"] >= len(payload["items"])

    def test_send_message_persists_history(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        create_response = client.post("/api/chat/chats", json={"title": "Conversation"})
        chat_id = create_response.json()["chat_id"]

        monkeypatch.setattr(
            "dashboard.services.chat.streaming.ChatStreamAdapter.stream_chat",
            lambda self, *, messages, message_id, chat_id: iter(
                [
                    f"event: message_start\ndata: {{\"message_id\": \"{message_id}\", \"chat_id\": \"{chat_id}\"}}\n\n",
                    'event: text_delta\ndata: {"delta": "Hello back"}\n\n',
                    f"event: message_complete\ndata: {{\"message_id\": \"{message_id}\", \"usage\": {{}}}}\n\n",
                ]
            ),
        )

        send_response = client.post(f"/api/chat/chats/{chat_id}/messages", json={"content": "Hello"})
        assert send_response.status_code == 200
        payload = send_response.json()
        assert payload["role"] == "assistant"
        assert payload["parts"][0]["payload"]["text"] == "Hello back"

        history_response = client.get(f"/api/chat/chats/{chat_id}/messages")
        history = history_response.json()
        assert history_response.status_code == 200
        assert [item["role"] for item in history] == ["user", "assistant"]
        assert history[0]["parts"][0]["payload"]["text"] == "Hello"

    def test_send_message_prepends_system_context_and_skill_instructions(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ):
        project_root = Path(client.app.state.project_root)
        state_path = project_root / ".webnovel" / "state.json"
        state_path.write_text(
            '{"project_info": {"title": "血色天平", "genre": "黑暗热血"}, "progress": {"current_chapter": 12}}',
            encoding="utf-8",
        )

        create_response = client.post("/api/chat/chats", json={"title": "Contextual Chat"})
        chat_id = create_response.json()["chat_id"]

        update_response = client.patch(
            f"/api/chat/chats/{chat_id}/skills",
            json={"skills": [{"skill_id": "webnovel-write", "enabled": True}]},
        )
        assert update_response.status_code == 200

        captured_messages: list[list[dict[str, str]]] = []

        def fake_stream_chat(self, *, messages, message_id, chat_id):
            captured_messages.append(messages)
            return iter(
                [
                    f"event: message_start\ndata: {{\"message_id\": \"{message_id}\", \"chat_id\": \"{chat_id}\"}}\n\n",
                    'event: text_delta\ndata: {"delta": "收到"}\n\n',
                    f"event: message_complete\ndata: {{\"message_id\": \"{message_id}\", \"usage\": {{}}}}\n\n",
                ]
            )

        monkeypatch.setattr(
            "dashboard.services.chat.streaming.ChatStreamAdapter.stream_chat",
            fake_stream_chat,
        )

        send_response = client.post(f"/api/chat/chats/{chat_id}/messages", json={"content": "开头怎么写？"})
        assert send_response.status_code == 200
        assert captured_messages

        messages = captured_messages[0]
        assert messages[0]["role"] == "system"
        assert "你是网文写作助手。根据项目设定和大纲辅助创作。严格遵循已挂载 Skill 的指令。" in messages[0]["content"]
        assert "- 作品标题：血色天平" in messages[0]["content"]
        assert "- 作品类型：黑暗热血" in messages[0]["content"]
        assert "- 当前章节：12" in messages[0]["content"]
        assert "[system:webnovel-write]" in messages[0]["content"]
        assert "Writes webnovel chapters" in messages[0]["content"]
        assert messages[1:] == [{"role": "user", "content": "开头怎么写？"}]

    def test_update_chat_skills(self, client: TestClient):
        create_response = client.post("/api/chat/chats", json={"title": "Skills"})
        chat_id = create_response.json()["chat_id"]

        update_response = client.patch(
            f"/api/chat/chats/{chat_id}/skills",
            json={"skills": [{"skill_id": "webnovel-write", "enabled": True}]},
        )
        assert update_response.status_code == 200
        payload = update_response.json()
        assert payload[0]["skill_id"] == "webnovel-write"
        assert payload[0]["source"] == "system"

        get_response = client.get(f"/api/chat/chats/{chat_id}/skills")
        assert get_response.status_code == 200
        assert get_response.json()[0]["name"] == "webnovel-write"

    def test_update_chat_skills_preserves_source(self, client: TestClient):
        create_response = client.post("/api/chat/chats", json={"title": "Profile Skills"})
        chat_id = create_response.json()["chat_id"]

        update_response = client.patch(
            f"/api/chat/chats/{chat_id}/skills",
            json={"skills": [{"skill_id": "battle", "source": "profile", "enabled": True}]},
        )
        assert update_response.status_code == 200
        payload = update_response.json()
        assert payload[0]["skill_id"] == "battle"
        assert payload[0]["source"] == "profile"

    def test_list_workspace_skills_reads_items_registry_shape(self, client: TestClient):
        project_root = Path(client.app.state.project_root)
        skills_dir = project_root / ".webnovel" / "skills"
        skill_dir = skills_dir / "ulw"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# ULW\n\nWorkspace long writing mode", encoding="utf-8")
        (skills_dir / "registry.json").write_text(
            '{"schema_version":1,"items":[{"id":"ulw","name":"ULW","description":"Workspace mode","enabled":true}]}',
            encoding="utf-8",
        )

        response = client.get("/api/chat/skills")
        assert response.status_code == 200
        payload = response.json()
        workspace_skill = next(item for item in payload if item["skill_id"] == "ulw")
        assert workspace_skill["source"] == "workspace"
        assert workspace_skill["name"] == "ULW"

    def test_send_message_includes_workspace_skill_markdown(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        project_root = Path(client.app.state.project_root)
        skills_dir = project_root / ".webnovel" / "skills"
        skill_dir = skills_dir / "ulw"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# ULW\n\n必须输出长篇细腻正文。", encoding="utf-8")
        (skills_dir / "registry.json").write_text(
            '{"schema_version":1,"items":[{"id":"ulw","name":"ULW","description":"Workspace mode","enabled":true}]}',
            encoding="utf-8",
        )

        create_response = client.post("/api/chat/chats", json={"title": "Workspace Context"})
        chat_id = create_response.json()["chat_id"]

        update_response = client.patch(
            f"/api/chat/chats/{chat_id}/skills",
            json={"skills": [{"skill_id": "ulw", "source": "workspace", "enabled": True}]},
        )
        assert update_response.status_code == 200

        captured_messages: list[list[dict[str, str]]] = []

        def fake_stream_chat(self, *, messages, message_id, chat_id):
            captured_messages.append(messages)
            return iter(
                [
                    f"event: message_start\ndata: {{\"message_id\": \"{message_id}\", \"chat_id\": \"{chat_id}\"}}\n\n",
                    'event: text_delta\ndata: {"delta": "收到"}\n\n',
                    f"event: message_complete\ndata: {{\"message_id\": \"{message_id}\", \"usage\": {{}}}}\n\n",
                ]
            )

        monkeypatch.setattr(
            "dashboard.services.chat.streaming.ChatStreamAdapter.stream_chat",
            fake_stream_chat,
        )

        send_response = client.post(f"/api/chat/chats/{chat_id}/messages", json={"content": "开始写"})
        assert send_response.status_code == 200
        assert captured_messages
        assert "[workspace:ulw]" in captured_messages[0][0]["content"]
        assert "必须输出长篇细腻正文。" in captured_messages[0][0]["content"]
