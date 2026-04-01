#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportImplicitRelativeImport=false

from __future__ import annotations

from pathlib import Path

from core.book_hierarchy import BookHierarchyService


def _build_service(tmp_path: Path) -> BookHierarchyService:
    return BookHierarchyService(tmp_path)


def _seed_versioned_entities(service: BookHierarchyService):
    book = service.create_book_root(title="测试作品")
    outline = service.create_outline(
        book.book_id,
        title="总纲",
        body="初始总纲",
        metadata={"tags": ["setup"], "priority": 1},
    )
    plot = service.create_plot(
        book.book_id,
        outline.outline_id,
        title="主线",
        body="初始主线",
        metadata={"status": "draft", "beats": ["a", "b"]},
    )
    event = service.create_event(book.book_id, plot.plot_id, title="事件", body="当前事件")
    scene = service.create_scene(book.book_id, event.event_id, title="场景", body="当前场景")
    chapter = service.create_chapter(
        book.book_id,
        scene.scene_id,
        title="第一章",
        body="初始章节",
        metadata={"notes": {"tone": "calm"}, "keywords": ["moon", "road"]},
    )
    setting = service.create_setting(
        book.book_id,
        title="世界规则",
        body="初始设定",
        metadata={"rank": 2, "domains": ["fire", "water"]},
    )
    return book, outline, plot, event, scene, chapter, setting


def test_versioned_entities_get_baseline_revision_for_current_state(tmp_path: Path):
    service = _build_service(tmp_path)
    _book, outline, plot, _event, _scene, chapter, setting = _seed_versioned_entities(service)

    outline_revisions = service.list_revisions("outline", outline.outline_id)
    plot_revisions = service.list_revisions("plot", plot.plot_id)
    chapter_revisions = service.list_revisions("chapter", chapter.chapter_id)
    setting_revisions = service.list_revisions("setting", setting.setting_id)

    assert [item.revision_number for item in outline_revisions] == [1]
    assert outline_revisions[0].snapshot["body"] == "初始总纲"
    assert [item.revision_number for item in plot_revisions] == [1]
    assert plot_revisions[0].snapshot["metadata"] == {"beats": ["a", "b"], "status": "draft"}
    assert [item.revision_number for item in chapter_revisions] == [1]
    assert [item.revision_number for item in setting_revisions] == [1]


def test_versioned_updates_append_immutable_revisions(tmp_path: Path):
    service = _build_service(tmp_path)
    book, outline, plot, _event, _scene, chapter, setting = _seed_versioned_entities(service)

    original_plot_revisions = service.list_revisions("plot", plot.plot_id)

    updated_outline = service.update_outline(book.book_id, outline.outline_id, expected_version=outline.version, body="第二版总纲")
    updated_plot = service.update_plot(
        book.book_id,
        plot.plot_id,
        expected_version=plot.version,
        body="第二版主线",
        metadata={"status": "approved", "beats": ["a", "c"]},
    )
    updated_chapter = service.update_chapter(book.book_id, chapter.chapter_id, expected_version=chapter.version, body="第二版章节")
    updated_setting = service.update_setting(book.book_id, setting.setting_id, expected_version=setting.version, body="第二版设定")

    outline_revisions = service.list_revisions("outline", outline.outline_id)
    plot_revisions = service.list_revisions("plot", plot.plot_id)
    chapter_revisions = service.list_revisions("chapter", chapter.chapter_id)
    setting_revisions = service.list_revisions("setting", setting.setting_id)

    assert updated_outline.version == 2
    assert updated_plot.version == 2
    assert updated_chapter.version == 2
    assert updated_setting.version == 2
    assert [item.revision_number for item in outline_revisions] == [1, 2]
    assert [item.revision_number for item in plot_revisions] == [1, 2]
    assert [item.revision_number for item in chapter_revisions] == [1, 2]
    assert [item.revision_number for item in setting_revisions] == [1, 2]
    assert plot_revisions[0].snapshot["body"] == "初始主线"
    assert plot_revisions[1].snapshot["body"] == "第二版主线"
    assert service.list_revisions("plot", plot.plot_id)[0].snapshot == original_plot_revisions[0].snapshot


def test_revision_diff_output_is_deterministic(tmp_path: Path):
    service = _build_service(tmp_path)
    book, _outline, plot, _event, _scene, _chapter, _setting = _seed_versioned_entities(service)

    service.update_plot(
        book.book_id,
        plot.plot_id,
        expected_version=plot.version,
        body="第二版主线",
        metadata={"status": "approved", "beats": ["c", "a"], "nested": {"beta": 2, "alpha": 1}},
    )

    first = service.diff_revisions("plot", plot.plot_id, from_revision=1, to_revision=2)
    second = service.diff_revisions("plot", plot.plot_id, from_revision=1, to_revision=2)

    assert first == second
    assert '"alpha": 1' in first
    assert '"beta": 2' in first
    assert '"body": "第二版主线"' in first


def test_rollback_creates_new_head_without_mutating_history(tmp_path: Path):
    service = _build_service(tmp_path)
    book, _outline, plot, _event, _scene, _chapter, _setting = _seed_versioned_entities(service)

    updated_plot = service.update_plot(book.book_id, plot.plot_id, expected_version=plot.version, body="第二版主线")
    rolled_back = service.rollback_to_revision(
        book.book_id,
        "plot",
        plot.plot_id,
        target_revision=1,
        expected_version=updated_plot.version,
    )

    revisions = service.list_revisions("plot", plot.plot_id)

    assert rolled_back.version == 3
    assert rolled_back.body == "初始主线"
    assert [item.revision_number for item in revisions] == [1, 2, 3]
    assert revisions[0].snapshot["body"] == "初始主线"
    assert revisions[1].snapshot["body"] == "第二版主线"
    assert revisions[2].snapshot["body"] == "初始主线"
    assert revisions[2].parent_revision_number == 1


def test_event_and_scene_remain_current_state_only(tmp_path: Path):
    service = _build_service(tmp_path)
    book, _outline, _plot, event, scene, _chapter, _setting = _seed_versioned_entities(service)

    updated_event = service.update_event(book.book_id, event.event_id, expected_version=event.version, body="第二版事件")
    updated_scene = service.update_scene(book.book_id, scene.scene_id, expected_version=scene.version, body="第二版场景")

    assert updated_event.version == 2
    assert updated_scene.version == 2
    assert service.list_revisions("event", event.event_id) == []
    assert service.list_revisions("scene", scene.scene_id) == []
