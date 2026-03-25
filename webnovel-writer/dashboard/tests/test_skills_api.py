from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from dashboard.routers.skills import router as skills_router

TEST_TMP_ROOT = PACKAGE_ROOT / ".tmp" / "skills-api-tests"


def _build_app(project_root: Path) -> FastAPI:
    app = FastAPI()
    app.state.project_root = str(project_root.resolve())
    app.include_router(skills_router)
    return app


def _new_project_root(test_name: str) -> Path:
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    project_root = TEST_TMP_ROOT / f"{test_name}-{uuid4().hex[:8]}"
    project_root.mkdir(parents=True, exist_ok=False)
    return project_root


def _workspace_payload(project_root: Path, workspace_id: str = "workspace-default") -> dict:
    return {
        "workspace": {
            "workspace_id": workspace_id,
            "project_root": str(project_root),
        }
    }


def _query_workspace(project_root: Path, workspace_id: str = "workspace-default") -> dict:
    return {
        "workspace_id": workspace_id,
        "project_root": str(project_root),
    }


def test_skills_create_conflicts_and_validation():
    project_root = _new_project_root("skills-validation")
    try:
        app = _build_app(project_root)
        with TestClient(app) as client:
            create_first = client.post(
                "/api/skills",
                json={
                    **_workspace_payload(project_root),
                    "id": "scene.splitter",
                    "name": "Scene Splitter",
                    "description": "split",
                    "enabled": True,
                },
            )
            assert create_first.status_code == 200

            duplicate_id = client.post(
                "/api/skills",
                json={
                    **_workspace_payload(project_root),
                    "id": "scene.splitter",
                    "name": "Another Name",
                    "description": "",
                    "enabled": False,
                },
            )
            assert duplicate_id.status_code == 409
            assert duplicate_id.json()["error_code"] == "skill_id_conflict"

            duplicate_name = client.post(
                "/api/skills",
                json={
                    **_workspace_payload(project_root),
                    "id": "scene.helper",
                    "name": "scene splitter",
                    "description": "",
                    "enabled": False,
                },
            )
            assert duplicate_name.status_code == 409
            assert duplicate_name.json()["error_code"] == "skill_name_conflict"

            invalid_id = client.post(
                "/api/skills",
                json={
                    **_workspace_payload(project_root),
                    "id": "invalid id",
                    "name": "Invalid Skill",
                    "description": "",
                    "enabled": False,
                },
            )
            assert invalid_id.status_code == 400
            assert invalid_id.json()["error_code"] == "invalid_skill_id"

            invalid_name = client.post(
                "/api/skills",
                json={
                    **_workspace_payload(project_root),
                    "id": "valid.id",
                    "name": "   ",
                    "description": "",
                    "enabled": False,
                },
            )
            assert invalid_name.status_code == 400
            assert invalid_name.json()["error_code"] == "invalid_skill_name"

            create_second = client.post(
                "/api/skills",
                json={
                    **_workspace_payload(project_root),
                    "id": "scene.editor",
                    "name": "Scene Editor",
                    "description": "",
                    "enabled": True,
                },
            )
            assert create_second.status_code == 200

            update_name_conflict = client.patch(
                "/api/skills/scene.editor",
                json={
                    **_workspace_payload(project_root),
                    "name": "Scene Splitter",
                },
            )
            assert update_name_conflict.status_code == 409
            assert update_name_conflict.json()["error_code"] == "skill_name_conflict"
    finally:
        shutil.rmtree(project_root, ignore_errors=True)


def test_skills_audit_supports_filters_and_pagination():
    project_root = _new_project_root("skills-audit")
    try:
        logs_dir = project_root / ".webnovel" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        audit_path = logs_dir / "skill-audit.jsonl"
        entries = [
            {
                "id": "a1",
                "action": "create",
                "skill_id": "scene.splitter",
                "actor": "api",
                "created_at": "2026-03-25T10:00:00Z",
                "details": {
                    "workspace_id": "workspace-default",
                    "project_root": str(project_root),
                },
            },
            {
                "id": "a2",
                "action": "disable",
                "skill_id": "scene.splitter",
                "actor": "ui",
                "created_at": "2026-03-25T10:05:00Z",
                "details": {
                    "workspace_id": "workspace-default",
                    "project_root": str(project_root),
                },
            },
            {
                "id": "a3",
                "action": "delete",
                "skill_id": "scene.splitter",
                "actor": "api",
                "created_at": "2026-03-25T11:00:00Z",
                "details": {
                    "workspace_id": "workspace-default",
                    "project_root": str(project_root),
                },
            },
            {
                "id": "other-ws",
                "action": "create",
                "skill_id": "other.skill",
                "actor": "api",
                "created_at": "2026-03-25T10:10:00Z",
                "details": {
                    "workspace_id": "workspace-other",
                    "project_root": str(project_root),
                },
            },
        ]
        audit_path.write_text("\n".join(json.dumps(item) for item in entries) + "\n", encoding="utf-8")

        app = _build_app(project_root)
        with TestClient(app) as client:
            by_action = client.get(
                "/api/skills/audit",
                params={**_query_workspace(project_root), "action": "disable"},
            )
            assert by_action.status_code == 200
            assert by_action.json()["total"] == 1
            assert by_action.json()["items"][0]["id"] == "a2"

            by_actor = client.get(
                "/api/skills/audit",
                params={**_query_workspace(project_root), "actor": "api"},
            )
            assert by_actor.status_code == 200
            assert by_actor.json()["total"] == 2

            by_start_time = client.get(
                "/api/skills/audit",
                params={**_query_workspace(project_root), "start_time": "2026-03-25T10:30:00Z"},
            )
            assert by_start_time.status_code == 200
            assert by_start_time.json()["total"] == 1
            assert by_start_time.json()["items"][0]["id"] == "a3"

            by_end_time = client.get(
                "/api/skills/audit",
                params={**_query_workspace(project_root), "end_time": "2026-03-25T10:30:00Z"},
            )
            assert by_end_time.status_code == 200
            assert by_end_time.json()["total"] == 2

            paged = client.get(
                "/api/skills/audit",
                params={**_query_workspace(project_root), "limit": 1, "offset": 1},
            )
            assert paged.status_code == 200
            assert paged.json()["total"] == 3
            assert len(paged.json()["items"]) == 1
            assert paged.json()["items"][0]["id"] == "a2"

            invalid_time_range = client.get(
                "/api/skills/audit",
                params={
                    **_query_workspace(project_root),
                    "start_time": "2026-03-25T12:00:00Z",
                    "end_time": "2026-03-25T10:00:00Z",
                },
            )
            assert invalid_time_range.status_code == 400
            assert invalid_time_range.json()["error_code"] == "invalid_audit_time_range"
    finally:
        shutil.rmtree(project_root, ignore_errors=True)


def test_skills_requests_create_webnovel_state_file_if_missing():
    project_root = _new_project_root("skills-state-file")
    try:
        app = _build_app(project_root)
        with TestClient(app) as client:
            response = client.get("/api/skills", params=_query_workspace(project_root))

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        state_path = project_root / ".webnovel" / "state.json"
        assert state_path.is_file()
        assert json.loads(state_path.read_text(encoding="utf-8")) == {}
    finally:
        shutil.rmtree(project_root, ignore_errors=True)
