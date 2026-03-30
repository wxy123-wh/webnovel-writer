#!/usr/bin/env python3

import json
import os
import subprocess
import sys
from pathlib import Path


def _webnovel_cli_path() -> Path:
    return Path(__file__).resolve().parents[2] / "webnovel.py"


def _run_agent(project_root: Path, *args: str) -> dict:
    env = os.environ.copy()
    env["GENERATION_API_TYPE"] = "stub"
    result = subprocess.run(
        [sys.executable, str(_webnovel_cli_path()), "--project-root", str(project_root), "agent", *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    payload = json.loads(result.stdout)
    payload["_exit_code"] = result.returncode
    return payload


def test_agent_cli_run_vertical_slice(tmp_path):
    outline_dir = tmp_path / "大纲"
    outline_dir.mkdir(parents=True, exist_ok=True)
    (outline_dir / "第1卷-详细大纲.md").write_text(
        "### 第1章：风起\n- 主角被迫卷入风波\n- 冲突升级\n- 局势反转\n- 留下钩子",
        encoding="utf-8",
    )
    (tmp_path / ".webnovel").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    payload = _run_agent(tmp_path, "run", "--chapter", "1", "--profile", "battle", "--publish", "--cleanup-session")

    assert payload["_exit_code"] == 0
    assert payload["status"] == "ok"
    assert payload["run"]["published_path"].replace("\\", "/").endswith("正文/第0001章-风起.md")
    assert (tmp_path / "正文" / "第0001章-风起.md").exists()


def test_agent_cli_session_start_and_stop(tmp_path):
    (tmp_path / ".webnovel").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    started = _run_agent(tmp_path, "session", "start", "--profile", "battle")
    assert started["_exit_code"] == 0
    session_id = started["session_id"]

    stopped = _run_agent(tmp_path, "session", "stop", "--session-id", session_id)
    assert stopped["_exit_code"] == 0
    assert stopped["session_id"] == session_id
