from __future__ import annotations

import shutil
import sys
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from dashboard.routers.runtime import router as runtime_router
from dashboard.services.runtime import service as runtime_service_module

TEST_TMP_ROOT = PACKAGE_ROOT / ".tmp" / "runtime-api-tests"


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(runtime_router)
    return app


def _new_workspace_root(test_name: str) -> tuple[Path, Path]:
    workspace_root = TEST_TMP_ROOT / f"{test_name}-{uuid4().hex[:8]}"
    project_root = workspace_root / "凡人资本论"
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")
    return workspace_root, project_root


def _workspace_payload(project_root: Path) -> dict[str, str]:
    return {"workspace_id": "workspace-default", "project_root": str(project_root)}


def _legacy_context_dir() -> str:
    return runtime_service_module._legacy_context_dir_name()


def _create_legacy_pointer(workspace_root: Path, project_root: Path) -> Path:
    pointer = workspace_root / _legacy_context_dir() / ".webnovel-current-project"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(str(project_root), encoding="utf-8")
    return pointer


def _create_codex_pointer(workspace_root: Path, project_root: Path) -> Path:
    pointer = workspace_root / ".codex" / ".webnovel-current-project"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(str(project_root), encoding="utf-8")
    return pointer


def _create_legacy_reference(project_root: Path) -> Path:
    legacy_file = project_root / _legacy_context_dir() / "references" / "world.md"
    legacy_file.parent.mkdir(parents=True, exist_ok=True)
    legacy_file.write_text("# world", encoding="utf-8")
    return legacy_file


def test_runtime_profile_returns_detected_state_and_preview():
    workspace_root, project_root = _new_workspace_root("runtime-profile")
    try:
        _create_codex_pointer(workspace_root, project_root)
        _create_legacy_reference(project_root)

        app = _build_app()
        with TestClient(app) as client:
            response = client.get(
                "/api/runtime/profile",
                params={"workspace_id": "workspace-default", "project_root": str(project_root)},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["runtime_name"] == "codex"
        assert payload["workspace"]["project_root"] == str(project_root)
        assert payload["pointer"]["workspace_root"] == str(workspace_root)
        assert payload["pointer"]["status"] == "codex_only"
        assert payload["legacy"]["project_legacy_reference_files"] == 1
        assert payload["migration_preview"]["dry_run"] is True
        assert payload["migration_preview"]["migratable_items"] >= 1
        assert any(item["kind"] == "references_directory" for item in payload["migration_preview"]["moved"])
    finally:
        shutil.rmtree(workspace_root, ignore_errors=True)


def test_runtime_profile_reports_pointer_conflict():
    workspace_root, project_root = _new_workspace_root("runtime-pointer-conflict")
    try:
        _create_legacy_pointer(workspace_root, project_root)

        other_project = workspace_root / "另一部作品"
        (other_project / ".webnovel").mkdir(parents=True, exist_ok=True)
        (other_project / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")
        codex_pointer = workspace_root / ".codex" / ".webnovel-current-project"
        codex_pointer.parent.mkdir(parents=True, exist_ok=True)
        codex_pointer.write_text(str(other_project), encoding="utf-8")

        app = _build_app()
        with TestClient(app) as client:
            response = client.get(
                "/api/runtime/profile",
                params={"workspace_id": "workspace-default", "project_root": str(project_root)},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["pointer"]["status"] == "conflict"
        assert payload["pointer"]["has_conflict"] is True
        assert payload["pointer"]["legacy"]["exists"] is True
        assert payload["pointer"]["codex"]["exists"] is True
    finally:
        shutil.rmtree(workspace_root, ignore_errors=True)


def test_runtime_migrate_dry_run_keeps_legacy_files():
    workspace_root, project_root = _new_workspace_root("runtime-migrate-dry-run")
    try:
        legacy_pointer = _create_legacy_pointer(project_root, project_root)
        legacy_reference = _create_legacy_reference(project_root)

        app = _build_app()
        with TestClient(app) as client:
            response = client.post(
                "/api/runtime/migrate",
                json={"workspace": _workspace_payload(project_root), "dry_run": True},
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["dry_run"] is True
        assert payload["project_root"] == str(project_root)
        assert payload["moved"]
        assert payload["report_path"]
        assert Path(payload["report_path"]).is_file()

        assert legacy_pointer.is_file()
        assert legacy_reference.is_file()
        assert not (project_root / ".codex" / ".webnovel-current-project").exists()
        assert not (project_root / ".codex" / "references" / "world.md").exists()
    finally:
        shutil.rmtree(workspace_root, ignore_errors=True)


def test_runtime_migrate_returns_501_when_backend_lacks_api_mode(monkeypatch):
    workspace_root, project_root = _new_workspace_root("runtime-migrate-501")
    try:
        _create_legacy_pointer(workspace_root, project_root)
        _create_legacy_reference(project_root)

        def legacy_backend(*, project_root: Path, dry_run: bool = False, workspace_hint: Path | None = None):
            return {
                "moved": [],
                "removed": [],
                "skipped": [],
                "warnings": [],
                "created_at": "1970-01-01T00:00:00",
                "dry_run": bool(dry_run),
                "project_root": str(project_root),
                "report_path": "",
            }

        monkeypatch.setattr(runtime_service_module, "_load_migrate_codex_runtime", lambda: legacy_backend)

        app = _build_app()
        with TestClient(app) as client:
            response = client.post(
                "/api/runtime/migrate",
                json={"workspace": _workspace_payload(project_root), "dry_run": True},
            )

        assert response.status_code == 501
        payload = response.json()
        assert payload["error_code"] == "RUNTIME_NOT_IMPLEMENTED"
    finally:
        shutil.rmtree(workspace_root, ignore_errors=True)
