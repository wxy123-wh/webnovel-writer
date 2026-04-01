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


def test_create_workspace_skill_persists_registry_and_markdown(client: TestClient):
    response = client.post(
        "/api/skills",
        json={
            "skill_id": "scene-beats",
            "name": "Scene Beats",
            "description": "Generate beat-first chapter scaffolds.",
            "instruction_template": "# Scene Beats\n\nAlways propose three escalating beats before drafting.",
        },
    )

    assert response.status_code == 201, response.json()
    payload = response.json()
    assert payload["skill_id"] == "scene-beats"
    assert payload["name"] == "Scene Beats"
    assert payload["source"] == "workspace"

    list_response = client.get("/api/skills")
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert [item["skill_id"] for item in items] == ["scene-beats"]

    project_root = Path(client.app.state.project_root)
    registry_path = project_root / ".webnovel" / "skills" / "registry.json"
    skill_md_path = project_root / ".webnovel" / "skills" / "scene-beats" / "SKILL.md"
    assert registry_path.is_file()
    assert skill_md_path.is_file()
    assert "Always propose three escalating beats" in skill_md_path.read_text(encoding="utf-8")


def test_create_workspace_skill_rejects_validation_errors(client: TestClient):
    response = client.post(
        "/api/skills",
        json={
            "skill_id": "Bad Skill!",
            "name": "",
            "description": "",
            "instruction_template": "   ",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "error_code": "invalid_skill_payload",
        "message": "Skill payload is invalid.",
        "details": {
            "field_errors": {
                "skill_id": "Use lowercase letters, numbers, and hyphens only.",
                "name": "Name is required.",
                "instruction_template": "Instruction template is required.",
            }
        },
        "request_id": None,
    }


def test_create_workspace_skill_rejects_conflicts(client: TestClient):
    payload = {
        "skill_id": "scene-beats",
        "name": "Scene Beats",
        "description": "Generate beat-first chapter scaffolds.",
        "instruction_template": "# Scene Beats\n\nAlways propose three escalating beats before drafting.",
    }

    first = client.post("/api/skills", json=payload)
    assert first.status_code == 201

    duplicate = client.post("/api/skills", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "error_code": "skill_conflict",
        "message": "A skill with this id already exists.",
        "details": {"skill_id": "scene-beats"},
        "request_id": None,
    }


def test_generate_workspace_skill_draft_returns_structured_payload(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GENERATION_API_TYPE", "openai")
    monkeypatch.setenv("GENERATION_API_KEY", "test-key")

    def fake_complete_json(self, *, messages):
        assert messages[-1]["content"] == "帮我生成一个章节节拍技能"
        return {
            "reply": "我已经生成了一版偏向章节节拍拆解的 skill 草稿。",
            "skill_id": "scene-beats",
            "name": "Scene Beats",
            "description": "Generate beat-first chapter scaffolds.",
            "instruction_template": "# Scene Beats\n\nAlways propose three escalating beats before drafting.",
        }

    monkeypatch.setattr(
        "scripts.data_modules.generation_client.GenerationAPIClient.complete_json",
        fake_complete_json,
    )

    response = client.post(
        "/api/skills/draft",
        json={
            "prompt": "帮我生成一个章节节拍技能",
            "current_draft": {
                "skill_id": "",
                "name": "",
                "description": "",
                "instruction_template": "",
            },
        },
    )

    assert response.status_code == 200, response.json()
    assert response.json() == {
        "reply": "我已经生成了一版偏向章节节拍拆解的 skill 草稿。",
        "draft": {
            "skill_id": "scene-beats",
            "name": "Scene Beats",
            "description": "Generate beat-first chapter scaffolds.",
            "instruction_template": "# Scene Beats\n\nAlways propose three escalating beats before drafting.",
        },
    }


def test_generate_workspace_skill_draft_requires_real_generation_provider(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GENERATION_API_TYPE", raising=False)
    monkeypatch.delenv("GENERATION_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = client.post(
        "/api/skills/draft",
        json={
            "prompt": "帮我生成一个章节节拍技能",
            "current_draft": {
                "skill_id": "",
                "name": "",
                "description": "",
                "instruction_template": "",
            },
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "error_code": "generation_unavailable",
        "message": "Generation provider is not configured for real skill draft generation.",
        "details": {"provider": "local"},
        "request_id": None,
    }


def test_generate_workspace_skill_draft_rejects_incomplete_model_output(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GENERATION_API_TYPE", "openai")
    monkeypatch.setenv("GENERATION_API_KEY", "test-key")

    monkeypatch.setattr(
        "scripts.data_modules.generation_client.GenerationAPIClient.complete_json",
        lambda self, *, messages: {
            "reply": "我试着生成了一版，但还不完整。",
            "skill_id": "",
            "name": "Half Draft",
            "description": "",
            "instruction_template": "",
        },
    )

    response = client.post(
        "/api/skills/draft",
        json={
            "prompt": "帮我生成一个章节节拍技能",
            "current_draft": {
                "skill_id": "",
                "name": "",
                "description": "",
                "instruction_template": "",
            },
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "error_code": "skill_draft_invalid",
        "message": "Generated skill draft is incomplete.",
        "details": {
            "field_errors": {
                "skill_id": "Skill ID is required.",
                "instruction_template": "Instruction template is required.",
            }
        },
        "request_id": None,
    }


def test_delete_workspace_skill_unmounts_it_from_chats(client: TestClient):
    create_skill = client.post(
        "/api/skills",
        json={
            "skill_id": "scene-beats",
            "name": "Scene Beats",
            "description": "Generate beat-first chapter scaffolds.",
            "instruction_template": "# Scene Beats\n\nAlways propose three escalating beats before drafting.",
        },
    )
    assert create_skill.status_code == 201

    create_chat = client.post("/api/chat/chats", json={"title": "Skill Delete Rule"})
    assert create_chat.status_code == 201
    chat_id = create_chat.json()["chat_id"]

    mount_response = client.patch(
        f"/api/chat/chats/{chat_id}/skills",
        json={"skills": [{"skill_id": "scene-beats", "source": "workspace", "enabled": True}]},
    )
    assert mount_response.status_code == 200
    assert [item["skill_id"] for item in mount_response.json()] == ["scene-beats"]

    delete_response = client.delete("/api/skills/scene-beats")
    assert delete_response.status_code == 204

    list_response = client.get("/api/skills")
    assert list_response.status_code == 200
    assert list_response.json()["items"] == []

    mounted_after_delete = client.get(f"/api/chat/chats/{chat_id}/skills")
    assert mounted_after_delete.status_code == 200
    assert mounted_after_delete.json() == []

    project_root = Path(client.app.state.project_root)
    skill_dir = project_root / ".webnovel" / "skills" / "scene-beats"
    assert not skill_dir.exists()
