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
