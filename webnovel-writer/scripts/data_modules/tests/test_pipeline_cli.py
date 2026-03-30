#!/usr/bin/env python3

import json
import os
import subprocess
import sys
from pathlib import Path


def _pipeline_cli_path() -> Path:
    return Path(__file__).resolve().parents[2] / "pipeline_cli.py"


def _run_cli(project_root: Path, *args: str) -> dict:
    env = os.environ.copy()
    env["GENERATION_API_TYPE"] = "stub"
    result = subprocess.run(
        [sys.executable, str(_pipeline_cli_path()), "--project-root", str(project_root), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    payload = json.loads(result.stdout)
    payload["_exit_code"] = result.returncode
    return payload


def test_pipeline_cli_vertical_slice(tmp_path):
    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    (outline_dir / "第1卷-详细大纲.md").write_text(
        "### 第1章：风起\n- 主角被迫卷入风波\n- 冲突升级\n- 局势反转\n- 留下钩子",
        encoding="utf-8",
    )
    (tmp_path / ".webnovel").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    started = _run_cli(tmp_path, "start-run", "--chapter", "1")
    assert started["_exit_code"] == 0
    run_id = started["run"]["run_id"]

    for stage in ("plot", "events", "scenes", "chapter"):
        generated = _run_cli(tmp_path, "generate", "--run-id", run_id, "--stage", stage)
        assert generated["_exit_code"] == 0
        accepted = _run_cli(tmp_path, "accept", "--run-id", run_id, "--stage", stage)
        assert accepted["_exit_code"] == 0

    published = _run_cli(tmp_path, "publish", "--run-id", run_id)
    assert published["_exit_code"] == 0
    assert published["run"]["published_path"].replace("\\", "/").endswith("正文/第0001章-风起.md")
    assert (tmp_path / "正文" / "第0001章-风起.md").exists()


def test_pipeline_cli_can_accept_older_revision(tmp_path):
    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    (outline_dir / "第1卷-详细大纲.md").write_text(
        "### 第1章：风起\n- 主角被迫卷入风波\n- 冲突升级\n- 局势反转\n- 留下钩子",
        encoding="utf-8",
    )
    (tmp_path / ".webnovel").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    started = _run_cli(tmp_path, "start-run", "--chapter", "1")
    run_id = started["run"]["run_id"]
    first = _run_cli(tmp_path, "generate", "--run-id", run_id, "--stage", "plot")
    second = _run_cli(tmp_path, "generate", "--run-id", run_id, "--stage", "plot")

    first_revision_id = first["run"]["stages"]["plot"]["revisions"][0]["revision_id"]
    second_revision_id = second["run"]["stages"]["plot"]["revisions"][1]["revision_id"]

    selected = _run_cli(tmp_path, "select-revision", "--run-id", run_id, "--stage", "plot", "--revision-id", first_revision_id)
    assert selected["_exit_code"] == 0
    assert selected["run"]["stages"]["plot"]["current_revision_id"] == first_revision_id

    accepted = _run_cli(tmp_path, "accept-revision", "--run-id", run_id, "--stage", "plot", "--revision-id", second_revision_id)
    assert accepted["_exit_code"] == 0
    assert accepted["run"]["stages"]["plot"]["accepted_revision_id"] == second_revision_id
