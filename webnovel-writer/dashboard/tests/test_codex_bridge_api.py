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

import dashboard.routers.codex_bridge as codex_bridge_module
from dashboard.routers.codex_bridge import router as codex_bridge_router


def _new_temp_project_root() -> Path:
    tests_dir = PACKAGE_ROOT / "dashboard" / "tests" / "_t_codex_bridge_runtime"
    tests_dir.mkdir(parents=True, exist_ok=True)
    project_root = tests_dir / f"t-codex-bridge-{uuid4().hex[:10]}"
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text("{}\n", encoding="utf-8")
    (project_root / "设定集").mkdir(parents=True, exist_ok=True)
    (project_root / "设定集" / "角色.md").write_text(
        "林昭(角色): 阵营=游侠; 目标=追查星图\n",
        encoding="utf-8",
    )
    (project_root / "大纲").mkdir(parents=True, exist_ok=True)
    (project_root / "大纲" / "总纲.md").write_text("第一段剧情推进。", encoding="utf-8")
    return project_root


def _workspace_payload(project_root: Path) -> dict:
    return {"workspace_id": "workspace-default", "project_root": str(project_root)}


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(codex_bridge_router)
    return app


def test_codex_file_edit_open_launches_cli_and_writes_prompt(monkeypatch):
    project_root = _new_temp_project_root()
    calls: list[dict] = []

    def _fake_popen(command, cwd=None, creationflags=0):  # noqa: ANN001
        calls.append({"command": command, "cwd": cwd, "creationflags": creationflags})

        class _Process:
            returncode = None

        return _Process()

    monkeypatch.setattr(codex_bridge_module.subprocess, "Popen", _fake_popen)

    app = _build_app()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/codex/file-edit/open",
                json={
                    "workspace": _workspace_payload(project_root),
                    "file_path": "设定集/角色.md",
                    "selection_start": 0,
                    "selection_end": 4,
                    "selection_text": "林昭(角",
                    "instruction": "改得更凝练",
                    "source_id": "settings.editor.textarea",
                },
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["status"] == "ok"
            assert payload["launched"] is True
            assert payload["target_file"] == "设定集/角色.md"

            prompt_path = Path(payload["prompt_file"])
            assert prompt_path.is_file()
            prompt_text = prompt_path.read_text(encoding="utf-8")
            assert "目标文件(相对路径): 设定集/角色.md" in prompt_text
            assert "林昭(角" in prompt_text
            assert "改得更凝练" in prompt_text

            assert len(calls) == 1
            assert calls[0]["cwd"] == str(project_root)
            assert calls[0]["command"][0] == "powershell"
            assert calls[0]["command"][1] == "-NoExit"
    finally:
        shutil.rmtree(project_root, ignore_errors=True)


def test_codex_file_edit_open_rejects_invalid_selection():
    project_root = _new_temp_project_root()
    app = _build_app()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/codex/file-edit/open",
                json={
                    "workspace": _workspace_payload(project_root),
                    "file_path": "设定集/角色.md",
                    "selection_start": 8,
                    "selection_end": 8,
                    "selection_text": "",
                },
            )
            assert response.status_code == 400
            payload = response.json()
            assert payload["error_code"] == "CODEX_FILE_EDIT_SELECTION_INVALID"
    finally:
        shutil.rmtree(project_root, ignore_errors=True)


def test_codex_file_edit_open_rejects_path_traversal():
    project_root = _new_temp_project_root()
    app = _build_app()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/codex/file-edit/open",
                json={
                    "workspace": _workspace_payload(project_root),
                    "file_path": "../outside.md",
                    "selection_start": 0,
                    "selection_end": 2,
                    "selection_text": "xx",
                },
            )
            assert response.status_code == 403
            payload = response.json()
            assert payload["error_code"] == "CODEX_FILE_EDIT_PATH_FORBIDDEN"
    finally:
        shutil.rmtree(project_root, ignore_errors=True)
