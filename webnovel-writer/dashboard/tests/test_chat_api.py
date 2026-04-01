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


def _create_book(client: TestClient, title: str = "测试作品") -> dict[str, object]:
    response = client.post("/api/hierarchy/books", json={"title": title, "synopsis": "简介"})
    assert response.status_code == 201, response.json()
    return response.json()


def _create_entity(
    client: TestClient,
    book_id: str,
    entity_type: str,
    *,
    parent_id: str | None = None,
    title: str,
    body: str = "",
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    response = client.post(
        f"/api/hierarchy/books/{book_id}/entities/{entity_type}",
        json={
            "parent_id": parent_id,
            "title": title,
            "body": body,
            "metadata": metadata or {},
        },
    )
    assert response.status_code == 201, response.json()
    return response.json()


def _seed_story_chain(client: TestClient) -> dict[str, dict[str, object]]:
    book = _create_book(client)
    outline = _create_entity(client, str(book["book_id"]), "outline", title="总纲", body="总纲正文")
    plot = _create_entity(client, str(book["book_id"]), "plot", parent_id=str(outline["outline_id"]), title="主线", body="主线正文")
    event = _create_entity(client, str(book["book_id"]), "event", parent_id=str(plot["plot_id"]), title="事件", body="事件正文")
    scene = _create_entity(client, str(book["book_id"]), "scene", parent_id=str(event["event_id"]), title="场景", body="场景正文")
    chapter = _create_entity(client, str(book["book_id"]), "chapter", parent_id=str(scene["scene_id"]), title="章节", body="章节初稿")
    return {
        "book": book,
        "outline": outline,
        "plot": plot,
        "event": event,
        "scene": scene,
        "chapter": chapter,
    }


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

    def test_send_message_uses_local_provider_without_api_key(self, client: TestClient):
        project_root = Path(client.app.state.project_root)
        state_path = project_root / ".webnovel" / "state.json"
        state_path.write_text(
            '{"project_info": {"title": "凡人修仙账本", "genre": "东方幻想"}, "progress": {"current_chapter": 3}}',
            encoding="utf-8",
        )

        create_response = client.post("/api/chat/chats", json={"title": "Local Mode"})
        chat_id = create_response.json()["chat_id"]

        send_response = client.post(f"/api/chat/chats/{chat_id}/messages", json={"content": "帮我想一下第一章怎么开头"})
        assert send_response.status_code == 200
        payload = send_response.json()
        assert payload["role"] == "assistant"
        text = payload["parts"][0]["payload"]["text"]
        assert "本地模式" in text
        assert "凡人修仙账本" in text
        assert "第一章怎么开头" in text

    def test_local_mode_with_webnovel_write_skill_returns_structured_write_plan(self, client: TestClient):
        project_root = Path(client.app.state.project_root)
        state_path = project_root / ".webnovel" / "state.json"
        state_path.write_text(
            '{"project_info": {"title": "血色天平", "genre": "黑暗热血"}, "progress": {"current_chapter": 1}}',
            encoding="utf-8",
        )

        create_response = client.post("/api/chat/chats", json={"title": "Write Plan"})
        chat_id = create_response.json()["chat_id"]

        update_response = client.patch(
            f"/api/chat/chats/{chat_id}/skills",
            json={"skills": [{"skill_id": "webnovel-write", "enabled": True}]},
        )
        assert update_response.status_code == 200

        send_response = client.post(
            f"/api/chat/chats/{chat_id}/messages",
            json={"content": "帮我写一个章节开头方案"},
        )
        assert send_response.status_code == 200
        text = send_response.json()["parts"][0]["payload"]["text"]
        assert "写作型辅助模式" in text
        assert "章节开头方案" in text
        assert "下一轮可以直接把这个方案展开成三段正文试写" in text

    def test_workflow_message_requires_selected_node_context(self, client: TestClient):
        story = _seed_story_chain(client)
        chat_id = client.post("/api/chat/chats", json={"title": "Workflow Chat"}).json()["chat_id"]

        response = client.post(
            f"/api/chat/chats/{chat_id}/messages",
            json={
                "content": "请拆分成下一层",
                "workflow": {
                    "action": "split",
                    "book_id": story["book"]["book_id"],
                },
            },
        )

        assert response.status_code == 400
        assert response.json() == {
            "error_code": "workflow_node_required",
            "message": "Workflow actions require a selected hierarchy node.",
            "details": {"action": "split"},
        }

    def test_workflow_message_rejects_invalid_level_jump(self, client: TestClient):
        story = _seed_story_chain(client)
        chat_id = client.post("/api/chat/chats", json={"title": "Workflow Chat"}).json()["chat_id"]

        response = client.post(
            f"/api/chat/chats/{chat_id}/messages",
            json={
                "content": "直接拆成场景",
                "workflow": {
                    "action": "split",
                    "book_id": story["book"]["book_id"],
                    "node_type": "outline",
                    "node_id": story["outline"]["outline_id"],
                    "target_type": "scene",
                },
            },
        )

        assert response.status_code == 400
        assert response.json() == {
            "error_code": "invalid_workflow_target",
            "message": "Workflow target does not match the allowed immediate child type.",
            "details": {
                "action": "split",
                "node_type": "outline",
                "target_type": "scene",
                "expected_target_type": "plot",
            },
        }

    def test_split_workflow_creates_only_allowed_child_proposal(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        story = _seed_story_chain(client)
        chat_id = client.post("/api/chat/chats", json={"title": "Workflow Chat"}).json()["chat_id"]

        monkeypatch.setattr(
            "dashboard.services.chat.streaming.ChatStreamAdapter.stream_chat",
            lambda self, *, messages, message_id, chat_id: iter(
                [
                    f"event: message_start\ndata: {{\"message_id\": \"{message_id}\", \"chat_id\": \"{chat_id}\"}}\n\n",
                    'event: text_delta\ndata: {"delta": "{\\"summary\\": \\\"拆分为两个情节点\\\", \\\"proposed_children\\\": [{\\"title\\": \\\"情节一\\\", \\\"body\\\": \\\"推进主线\\\", \\\"metadata\\\": {\\"beat\\": 1}}]}"}\n\n',
                    f"event: message_complete\ndata: {{\"message_id\": \"{message_id}\", \"usage\": {{}}}}\n\n",
                ]
            ),
        )

        response = client.post(
            f"/api/chat/chats/{chat_id}/messages",
            json={
                "content": "把这个总纲拆成下一层",
                "workflow": {
                    "action": "split",
                    "book_id": story["book"]["book_id"],
                    "node_type": "outline",
                    "node_id": story["outline"]["outline_id"],
                    "target_type": "plot",
                },
            },
        )

        assert response.status_code == 200, response.json()
        payload = response.json()
        tool_result = next(part for part in payload["parts"] if part["type"] == "tool_result")
        proposal = tool_result["payload"]["proposal"]
        assert proposal["status"] == "pending"
        assert proposal["target_type"] == "plot"
        assert proposal["proposal_type"] == "outline_split"
        assert proposal["payload"]["child_type"] == "plot"
        assert proposal["payload"]["parent_id"] == story["outline"]["outline_id"]
        assert proposal["payload"]["applied_entity_ids"] == []
        get_plot = client.get(f"/api/hierarchy/books/{story['book']['book_id']}/entities/plot/{story['plot']['plot_id']}")
        assert get_plot.status_code == 200

    def test_chapter_edit_workflow_returns_proposal_instead_of_overwrite(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        story = _seed_story_chain(client)
        chat_id = client.post("/api/chat/chats", json={"title": "Workflow Chat"}).json()["chat_id"]

        monkeypatch.setattr(
            "dashboard.services.chat.streaming.ChatStreamAdapter.stream_chat",
            lambda self, *, messages, message_id, chat_id: iter(
                [
                    f"event: message_start\ndata: {{\"message_id\": \"{message_id}\", \"chat_id\": \"{chat_id}\"}}\n\n",
                    'event: text_delta\ndata: {"delta": "{\\"summary\\": \\\"强化章节收束\\\", \\\"title\\\": \\\"章节（修订）\\\", \\\"body\\\": \\\"修订后的章节正文\\\", \\\"metadata\\\": {\\"tone\\\": \\\"grim\\\"}}"}\n\n',
                    f"event: message_complete\ndata: {{\"message_id\": \"{message_id}\", \"usage\": {{}}}}\n\n",
                ]
            ),
        )

        response = client.post(
            f"/api/chat/chats/{chat_id}/messages",
            json={
                "content": "润色这个章节并强化结尾",
                "workflow": {
                    "action": "edit",
                    "book_id": story["book"]["book_id"],
                    "node_type": "chapter",
                    "node_id": story["chapter"]["chapter_id"],
                },
            },
        )

        assert response.status_code == 200, response.json()
        payload = response.json()
        tool_result = next(part for part in payload["parts"] if part["type"] == "tool_result")
        proposal = tool_result["payload"]["proposal"]
        assert proposal["status"] == "pending"
        assert proposal["target_type"] == "chapter"
        assert proposal["proposal_type"] == "chapter_edit"
        assert proposal["payload"]["kind"] == "chapter_edit"
        assert proposal["payload"]["chapter_id"] == story["chapter"]["chapter_id"]
        assert proposal["payload"]["proposed_update"]["body"] == "修订后的章节正文"

        chapter_response = client.get(
            f"/api/hierarchy/books/{story['book']['book_id']}/entities/chapter/{story['chapter']['chapter_id']}"
        )
        assert chapter_response.status_code == 200
        assert chapter_response.json()["title"] == "章节"
        assert chapter_response.json()["body"] == "章节初稿"

    def test_workflow_context_includes_approved_canon_mounted_skills_and_immediate_parent(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ):
        story = _seed_story_chain(client)
        _create_entity(client, str(story["book"]["book_id"]), "canon_entry", title="正式设定", body="主角不会飞行")
        chat_id = client.post("/api/chat/chats", json={"title": "Workflow Context"}).json()["chat_id"]

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
                    'event: text_delta\ndata: {"delta": "{\\"summary\\": \\\"提取正式事实\\\", \\\"title\\\": \\\"新事实\\\", \\\"body\\\": \\\"主角讨厌雨天\\\", \\\"metadata\\\": {\\"kind\\\": \\\"character\\\"}}"}\n\n',
                    f"event: message_complete\ndata: {{\"message_id\": \"{message_id}\", \"usage\": {{}}}}\n\n",
                ]
            )

        monkeypatch.setattr("dashboard.services.chat.streaming.ChatStreamAdapter.stream_chat", fake_stream_chat)

        response = client.post(
            f"/api/chat/chats/{chat_id}/messages",
            json={
                "content": "提取这段中的稳定设定",
                "workflow": {
                    "action": "extract",
                    "book_id": story["book"]["book_id"],
                    "node_type": "scene",
                    "node_id": story["scene"]["scene_id"],
                },
            },
        )

        assert response.status_code == 200, response.json()
        assert captured_messages
        system_prompt = captured_messages[0][0]["content"]
        assert "已批准 Canon：" in system_prompt
        assert "- 标题：正式设定" in system_prompt
        assert "主角不会飞行" in system_prompt
        assert "当前节点：" in system_prompt
        assert "- 类型：scene" in system_prompt
        assert "- 标题：场景" in system_prompt
        assert "直接父节点：" in system_prompt
        assert "- 类型：event" in system_prompt
        assert "- 标题：事件" in system_prompt
        assert "[system:webnovel-write]" in system_prompt
