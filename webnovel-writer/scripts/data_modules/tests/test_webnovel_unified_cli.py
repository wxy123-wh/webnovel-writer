#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path

import pytest


def _ensure_scripts_on_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def _load_webnovel_module():
    _ensure_scripts_on_path()
    import data_modules.webnovel as webnovel_module

    return webnovel_module


def test_init_does_not_resolve_existing_project_root(monkeypatch):
    module = _load_webnovel_module()

    called = {}

    def _fake_run_script(script_name, argv):
        called["script_name"] = script_name
        called["argv"] = list(argv)
        return 0

    def _fail_resolve(_explicit_project_root=None):
        raise AssertionError("init 子命令不应触发 project_root 解析")

    monkeypatch.setenv("WEBNOVEL_PROJECT_ROOT", r"D:\invalid\root")
    monkeypatch.setattr(module, "_run_script", _fake_run_script)
    monkeypatch.setattr(module, "_resolve_root", _fail_resolve)
    monkeypatch.setattr(sys, "argv", ["webnovel", "init", "proj-dir", "测试书", "修仙"])

    with pytest.raises(SystemExit) as exc:
        module.main()

    assert int(exc.value.code or 0) == 0
    assert called["script_name"] == "init_project.py"
    assert called["argv"] == ["proj-dir", "测试书", "修仙"]


def test_extract_context_forwards_with_resolved_project_root(monkeypatch, tmp_path):
    module = _load_webnovel_module()

    book_root = (tmp_path / "book").resolve()
    called = {}

    def _fake_resolve(explicit_project_root=None):
        return book_root

    def _fake_run_script(script_name, argv):
        called["script_name"] = script_name
        called["argv"] = list(argv)
        return 0

    monkeypatch.setattr(module, "_resolve_root", _fake_resolve)
    monkeypatch.setattr(module, "_run_script", _fake_run_script)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "webnovel",
            "--project-root",
            str(tmp_path),
            "extract-context",
            "--chapter",
            "12",
            "--format",
            "json",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        module.main()

    assert int(exc.value.code or 0) == 0
    assert called["script_name"] == "extract_chapter_context.py"
    assert called["argv"] == [
        "--project-root",
        str(book_root),
        "--chapter",
        "12",
        "--format",
        "json",
    ]


def test_extract_context_accepts_marker_root_when_state_missing(monkeypatch, tmp_path):
    module = _load_webnovel_module()

    marker_root = (tmp_path / "book").resolve()
    (marker_root / "正文").mkdir(parents=True, exist_ok=True)
    called = {}

    def _fake_resolve(_explicit_project_root=None):
        raise FileNotFoundError("missing .webnovel/state.json")

    def _fake_run_script(script_name, argv):
        called["script_name"] = script_name
        called["argv"] = list(argv)
        return 0

    monkeypatch.setattr(module, "_resolve_root", _fake_resolve)
    monkeypatch.setattr(module, "_run_script", _fake_run_script)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "webnovel",
            "--project-root",
            str(marker_root),
            "extract-context",
            "--chapter",
            "7",
            "--format",
            "text",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        module.main()

    assert int(exc.value.code or 0) == 0
    assert called["script_name"] == "extract_chapter_context.py"
    assert called["argv"][0:2] == ["--project-root", str(marker_root)]


def test_extract_context_reports_project_root_error(monkeypatch, tmp_path, capsys):
    module = _load_webnovel_module()

    invalid_root = (tmp_path / "workspace").resolve()

    def _fake_resolve_root_for_extract_context(_explicit_project_root=None):
        raise FileNotFoundError(f"extract-context project_root 不存在: {invalid_root}")

    def _fake_run_script(*_args, **_kwargs):
        raise AssertionError("project_root 解析失败时不应继续转发子脚本")

    monkeypatch.setattr(module, "_resolve_root_for_extract_context", _fake_resolve_root_for_extract_context)
    monkeypatch.setattr(module, "_run_script", _fake_run_script)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "webnovel",
            "--project-root",
            str(invalid_root),
            "extract-context",
            "--chapter",
            "3",
            "--format",
            "json",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        module.main()

    captured = capsys.readouterr()
    assert int(exc.value.code) == 1
    assert "ERROR project_root (extract-context):" in captured.err
    assert "extract-context project_root 不存在" in captured.err


def test_migrate_codex_dispatches_to_runtime_migration(monkeypatch, tmp_path, capsys):
    module = _load_webnovel_module()

    book_root = (tmp_path / "book").resolve()
    (book_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (book_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    called = {}

    def _fake_resolve(explicit_project_root=None):
        called["resolve_arg"] = explicit_project_root
        return book_root

    def _fake_run_codex_migration(*, project_root, dry_run, workspace_hint):
        called["project_root"] = project_root
        called["dry_run"] = dry_run
        called["workspace_hint"] = workspace_hint
        print("{}")
        return 0

    workspace_root = (tmp_path / "workspace").resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(module, "_resolve_root", _fake_resolve)
    monkeypatch.setattr(module, "_run_codex_migration", _fake_run_codex_migration)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "webnovel",
            "migrate",
            "codex",
            "--project-root",
            str(workspace_root),
            "--dry-run",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        module.main()

    captured = capsys.readouterr()
    assert int(exc.value.code or 0) == 0
    assert captured.out.strip() == "{}"
    assert called["resolve_arg"] == str(workspace_root)
    assert called["project_root"] == book_root
    assert called["dry_run"] is True
    assert called["workspace_hint"] == workspace_root


def test_preflight_succeeds_for_valid_project_root(monkeypatch, tmp_path, capsys):
    module = _load_webnovel_module()

    project_root = tmp_path / "book"
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["webnovel", "--project-root", str(project_root), "preflight"])

    with pytest.raises(SystemExit) as exc:
        module.main()

    captured = capsys.readouterr()
    assert int(exc.value.code or 0) == 0
    assert "OK project_root" in captured.out
    assert str(project_root.resolve()) in captured.out


def test_preflight_fails_when_required_scripts_are_missing(monkeypatch, tmp_path, capsys):
    module = _load_webnovel_module()

    project_root = tmp_path / "book"
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    fake_scripts_dir = tmp_path / "fake-scripts"
    fake_scripts_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(module, "_scripts_dir", lambda: fake_scripts_dir)
    monkeypatch.setattr(sys, "argv", ["webnovel", "--project-root", str(project_root), "preflight", "--format", "json"])

    with pytest.raises(SystemExit) as exc:
        module.main()

    captured = capsys.readouterr()
    assert int(exc.value.code or 0) == 1
    assert '"ok": false' in captured.out
    assert '"name": "entry_script"' in captured.out


def test_preflight_json_includes_binding_details(monkeypatch, tmp_path, capsys):
    module = _load_webnovel_module()

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / ".codex").mkdir(parents=True, exist_ok=True)

    project_root = workspace_root / "book"
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    pointer_file = workspace_root / ".codex" / ".webnovel-current-project"
    pointer_file.write_text(str(project_root.resolve()), encoding="utf-8")

    registry_home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(registry_home))
    registry_path = registry_home / "webnovel-writer" / "registry.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "workspaces": {
                    str(workspace_root.resolve()).lower(): {
                        "workspace_root": str(workspace_root.resolve()),
                        "current_project_root": str(project_root.resolve()),
                        "updated_at": "2026-03-25T00:00:00",
                    }
                },
                "last_used_project_root": str(project_root.resolve()),
                "updated_at": "2026-03-25T00:00:00",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        ["webnovel", "--project-root", str(workspace_root), "preflight", "--format", "json"],
    )

    with pytest.raises(SystemExit) as exc:
        module.main()

    captured = capsys.readouterr()
    assert int(exc.value.code or 0) == 0
    payload = json.loads(captured.out)
    assert "binding" in payload
    assert "pointer" in payload["binding"]
    assert "registry" in payload["binding"]
    assert payload["binding"]["project_root"]["ok"] is True


def test_where_fails_with_clear_reason_when_state_json_missing(monkeypatch, tmp_path, capsys):
    module = _load_webnovel_module()

    invalid_root = tmp_path / "workspace"
    (invalid_root / ".webnovel").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(sys, "argv", ["webnovel", "--project-root", str(invalid_root), "where"])

    with pytest.raises(SystemExit) as exc:
        module.main()

    captured = capsys.readouterr()
    assert int(exc.value.code or 0) == 1
    assert "missing .webnovel/state.json" in captured.err


def test_use_writes_registry_and_reports_pointer_skip_reason(monkeypatch, tmp_path, capsys):
    module = _load_webnovel_module()

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)

    project_root = workspace_root / "book"
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    registry_home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(registry_home))

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "webnovel",
            "use",
            str(project_root),
            "--workspace-root",
            str(workspace_root),
        ],
    )

    with pytest.raises(SystemExit) as exc:
        module.main()

    captured = capsys.readouterr()
    assert int(exc.value.code or 0) == 0
    assert "workspace pointer: (skipped: reason=context_dir_missing" in captured.out
    assert "global registry:" in captured.out

    registry_path = registry_home / "webnovel-writer" / "registry.json"
    assert registry_path.is_file()

def test_quality_trend_report_writes_to_book_root_when_input_is_workspace_root(tmp_path, monkeypatch):
    _ensure_scripts_on_path()
    import quality_trend_report as quality_trend_report_module

    workspace_root = (tmp_path / "workspace").resolve()
    book_root = (workspace_root / "凡人资本论").resolve()

    (workspace_root / ".claude").mkdir(parents=True, exist_ok=True)
    (workspace_root / ".claude" / ".webnovel-current-project").write_text(str(book_root), encoding="utf-8")

    (book_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (book_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    output_path = workspace_root / "report.md"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "quality_trend_report",
            "--project-root",
            str(workspace_root),
            "--limit",
            "1",
            "--output",
            str(output_path),
        ],
    )

    quality_trend_report_module.main()

    assert output_path.is_file()
    assert (book_root / ".webnovel" / "index.db").is_file()
    assert not (workspace_root / ".webnovel" / "index.db").exists()
