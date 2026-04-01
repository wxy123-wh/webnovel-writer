from __future__ import annotations

import shutil
import sys
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from dashboard.app import create_app

TEST_TMP_ROOT = PACKAGE_ROOT / ".tmp" / "provider-settings-api-tests"


def _new_project_root(test_name: str) -> Path:
    workspace_root = TEST_TMP_ROOT / f"{test_name}-{uuid4().hex[:8]}"
    project_root = workspace_root / "凡人资本论"
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")
    return project_root


def test_get_provider_masks_api_key_and_reports_local_as_unconfigured(monkeypatch):
    project_root = _new_project_root("provider-get")
    try:
        monkeypatch.delenv("GENERATION_API_TYPE", raising=False)
        monkeypatch.delenv("GENERATION_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        app = create_app(project_root=project_root)
        with TestClient(app) as client:
            response = client.get("/api/settings/provider")

        assert response.status_code == 200
        payload = response.json()
        assert payload == {
            "provider": "local",
            "configured": False,
            "api_key_configured": False,
            "model": "local-assist-v1",
            "base_url": "",
        }
        assert "api_key" not in payload
    finally:
        shutil.rmtree(project_root.parent, ignore_errors=True)


def test_patch_provider_writes_project_env_and_preserves_unrelated_entries(monkeypatch):
    project_root = _new_project_root("provider-patch")
    try:
        monkeypatch.delenv("GENERATION_API_TYPE", raising=False)
        monkeypatch.delenv("GENERATION_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GENERATION_MODEL", raising=False)
        monkeypatch.delenv("GENERATION_BASE_URL", raising=False)
        (project_root / ".env").write_text("KEEP_ME=1\nGENERATION_API_KEY=old-key\n", encoding="utf-8")

        app = create_app(project_root=project_root)
        with TestClient(app) as client:
            response = client.patch(
                "/api/settings/provider",
                json={
                    "provider": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "model": "gpt-4.1-mini",
                    "api_key": "sk-new",
                    "clear_api_key": False,
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"] == "openai"
        assert payload["configured"] is True
        assert payload["api_key_configured"] is True
        env_text = (project_root / ".env").read_text(encoding="utf-8")
        assert "KEEP_ME=1" in env_text
        assert "GENERATION_API_TYPE=openai" in env_text
        assert "GENERATION_BASE_URL=https://api.openai.com/v1" in env_text
        assert "GENERATION_MODEL=gpt-4.1-mini" in env_text
        assert "GENERATION_API_KEY=sk-new" in env_text
    finally:
        shutil.rmtree(project_root.parent, ignore_errors=True)


def test_patch_provider_can_clear_saved_api_key_without_returning_secret(monkeypatch):
    project_root = _new_project_root("provider-clear")
    try:
        monkeypatch.delenv("GENERATION_API_TYPE", raising=False)
        monkeypatch.delenv("GENERATION_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        (project_root / ".env").write_text(
            "GENERATION_API_TYPE=openai\nGENERATION_API_KEY=sk-old\nGENERATION_MODEL=gpt-4o-mini\n",
            encoding="utf-8",
        )

        app = create_app(project_root=project_root)
        with TestClient(app) as client:
            response = client.patch(
                "/api/settings/provider",
                json={
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "base_url": "",
                    "api_key": "",
                    "clear_api_key": True,
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"] == "openai"
        assert payload["configured"] is False
        assert payload["api_key_configured"] is False
        env_text = (project_root / ".env").read_text(encoding="utf-8")
        assert "GENERATION_API_KEY" not in env_text
        assert "api_key" not in payload
    finally:
        shutil.rmtree(project_root.parent, ignore_errors=True)
