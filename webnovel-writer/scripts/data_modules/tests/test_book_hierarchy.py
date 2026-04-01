#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportImplicitRelativeImport=false

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.book_hierarchy import (
    BookHierarchyConflictError,
    BookHierarchyGuardedDeleteError,
    BookHierarchyService,
    BookHierarchyValidationError,
    BookHierarchyVersionMismatchError,
)
from core.book_hierarchy.models import BookRoot, Chapter, Event, Outline, Plot, Scene


def _build_service(tmp_path: Path) -> BookHierarchyService:
    return BookHierarchyService(tmp_path)


def _seed_chain(service: BookHierarchyService) -> tuple[BookRoot, Outline, Plot, Event, Scene, Chapter]:
    book = service.create_book_root(title="测试作品")
    outline = service.create_outline(book.book_id, title="总纲")
    plot = service.create_plot(book.book_id, outline.outline_id, title="主线")
    event = service.create_event(book.book_id, plot.plot_id, title="事件")
    scene = service.create_scene(book.book_id, event.event_id, title="场景")
    chapter = service.create_chapter(book.book_id, scene.scene_id, title="第一章")
    return book, outline, plot, event, scene, chapter


def test_cannot_create_second_active_book_root_for_project(tmp_path: Path):
    service = _build_service(tmp_path)

    first = service.create_book_root(title="第一本书")

    with pytest.raises(BookHierarchyConflictError) as exc_info:
        service.create_book_root(title="第二本书")

    assert first.status == "active"
    assert exc_info.value.error_code == "book_root_conflict"


def test_create_scene_requires_immediate_event_parent(tmp_path: Path):
    service = _build_service(tmp_path)
    book, _outline, _plot, _event, _scene, _chapter = _seed_chain(service)

    with pytest.raises(BookHierarchyValidationError) as exc_info:
        service.create_scene(book.book_id, "missing-event", title="非法场景")

    assert exc_info.value.error_code == "invalid_parent"


def test_reorder_siblings_persists_across_reload(tmp_path: Path):
    service = _build_service(tmp_path)
    book, outline, seeded_plot, _event, _scene, _chapter = _seed_chain(service)
    book_id = book.book_id
    outline_id = outline.outline_id

    first = service.create_plot(book_id, outline_id, title="第一支线")
    second = service.create_plot(book_id, outline_id, title="第二支线")

    service.reorder_plots(book_id, outline_id, [second.plot_id, first.plot_id, seeded_plot.plot_id])

    reloaded = _build_service(tmp_path)
    items = reloaded.list_plots(book_id, outline_id)
    assert [item.plot_id for item in items] == [second.plot_id, first.plot_id, seeded_plot.plot_id]
    assert [item.position for item in items] == [0, 1, 2]


def test_delete_parent_with_children_is_guarded(tmp_path: Path):
    service = _build_service(tmp_path)
    book, _outline, plot, _event, _scene, _chapter = _seed_chain(service)

    with pytest.raises(BookHierarchyGuardedDeleteError) as exc_info:
        service.delete_plot(book.book_id, plot.plot_id)

    assert exc_info.value.error_code == "children_exist"


def test_update_requires_matching_version(tmp_path: Path):
    service = _build_service(tmp_path)
    book, _outline, plot, _event, _scene, _chapter = _seed_chain(service)

    updated = service.update_plot(
        book.book_id,
        plot.plot_id,
        expected_version=plot.version,
        title="已更新主线",
    )
    assert updated.version == plot.version + 1

    with pytest.raises(BookHierarchyVersionMismatchError) as exc_info:
        service.update_plot(
            book.book_id,
            plot.plot_id,
            expected_version=plot.version,
            title="过期更新",
        )

    assert exc_info.value.error_code == "version_mismatch"


def test_auxiliary_entities_persist_for_future_tasks(tmp_path: Path):
    service = _build_service(tmp_path)
    book, _outline, _plot, _event, _scene, _chapter = _seed_chain(service)
    book_id = book.book_id

    setting = service.create_setting(book_id, title="世界规则", body="灵气稀薄")
    canon = service.create_canon_entry(book_id, title="事实", body="主角不会飞行")
    proposal = service.create_proposal(book_id, proposal_type="scene_split", target_type="scene")
    index_state = service.upsert_index_state(book_id, generation=1, status="stale", source_fingerprint="fp-1")

    reloaded = _build_service(tmp_path)
    snapshot = reloaded.get_book_snapshot(book_id)

    assert [item.setting_id for item in snapshot["settings"]] == [setting.setting_id]
    assert [item.canon_id for item in snapshot["canon_entries"]] == [canon.canon_id]
    assert [item.proposal_id for item in snapshot["proposals"]] == [proposal.proposal_id]
    assert snapshot["index_state"].index_state_id == index_state.index_state_id


def test_structural_proposal_persists_preview_and_applies_exactly_once(tmp_path: Path):
    service = _build_service(tmp_path)
    book, outline, _plot, _event, _scene, _chapter = _seed_chain(service)
    target_plot = service.create_plot(book.book_id, outline.outline_id, title="待扩写支线")

    proposal = service.create_structural_proposal(
        book.book_id,
        parent_type="plot",
        parent_id=target_plot.plot_id,
        child_type="event",
        proposal_type="plot_split",
        proposed_children=[
            {"title": "提议事件一", "body": "第一段", "metadata": {"beat": 1}},
            {"title": "提议事件二", "body": "第二段", "metadata": {"beat": 2}},
        ],
    )

    assert proposal.status == "pending"
    assert proposal.base_version == target_plot.version
    assert proposal.base_fingerprint == proposal.current_head_fingerprint
    assert proposal.payload["parent_id"] == target_plot.plot_id
    assert proposal.payload["proposed_children"][0]["title"] == "提议事件一"
    assert service.repository.child_count(table="plots", id_value=target_plot.plot_id) == 0

    approved = service.approve_proposal(book.book_id, proposal.proposal_id)
    approved_again = service.approve_proposal(book.book_id, proposal.proposal_id)

    assert approved.status == "approved"
    assert approved.payload["applied_entity_ids"] == approved_again.payload["applied_entity_ids"]
    assert len(approved.payload["applied_entity_ids"]) == 2
    assert service.repository.child_count(table="plots", id_value=target_plot.plot_id) == 2


def test_reject_and_cancel_proposals_leave_committed_state_unchanged(tmp_path: Path):
    service = _build_service(tmp_path)
    book, outline, _plot, event, scene, _chapter = _seed_chain(service)
    target_plot = service.create_plot(book.book_id, outline.outline_id, title="待处理支线")

    structural = service.create_structural_proposal(
        book.book_id,
        parent_type="plot",
        parent_id=target_plot.plot_id,
        child_type="event",
        proposal_type="plot_split",
        proposed_children=[{"title": "不会落库的事件", "body": "草案", "metadata": {}}],
    )
    canon_candidate = service.create_canon_extraction_proposal(
        book.book_id,
        source_type="scene",
        source_id=scene.scene_id,
        title="候选事实",
        body="仅存在于提案中",
        metadata={"source_event_id": event.event_id},
    )

    rejected = service.reject_proposal(book.book_id, structural.proposal_id)
    cancelled = service.cancel_proposal(book.book_id, canon_candidate.proposal_id)

    assert rejected.status == "rejected"
    assert cancelled.status == "cancelled"
    assert service.repository.child_count(table="plots", id_value=target_plot.plot_id) == 0
    assert service.repository.list_canon_entries(book_id=book.book_id) == []


def test_stale_proposal_approval_fails_with_machine_readable_error(tmp_path: Path):
    service = _build_service(tmp_path)
    book, outline, _plot, _event, _scene, _chapter = _seed_chain(service)
    target_plot = service.create_plot(book.book_id, outline.outline_id, title="会过期的支线")
    proposal = service.create_structural_proposal(
        book.book_id,
        parent_type="plot",
        parent_id=target_plot.plot_id,
        child_type="event",
        proposal_type="plot_split",
        proposed_children=[{"title": "过期事件", "body": "旧版本", "metadata": {}}],
    )

    service.update_plot(book.book_id, target_plot.plot_id, expected_version=target_plot.version, body="新版本正文")

    with pytest.raises(BookHierarchyConflictError) as exc_info:
        service.approve_proposal(book.book_id, proposal.proposal_id)

    refreshed = service.get_proposal(book.book_id, proposal.proposal_id)

    assert exc_info.value.error_code == "stale_proposal_base"
    assert exc_info.value.details["proposal_id"] == proposal.proposal_id
    assert refreshed.status == "stale"
    assert refreshed.current_head_fingerprint != refreshed.base_fingerprint
    assert service.repository.child_count(table="plots", id_value=target_plot.plot_id) == 0


def test_duplicate_canon_candidate_is_detected_and_confirmed_without_duplicate_write(tmp_path: Path):
    service = _build_service(tmp_path)
    book, _outline, _plot, _event, scene, _chapter = _seed_chain(service)
    canon = service.create_canon_entry(
        book.book_id,
        title="既有事实",
        body="主角不会飞行",
        metadata={"kind": "rule", "severity": 1},
    )

    proposal = service.create_canon_extraction_proposal(
        book.book_id,
        source_type="scene",
        source_id=scene.scene_id,
        title="既有事实",
        body="主角不会飞行",
        metadata={"kind": "rule", "severity": 1},
    )

    approved = service.approve_proposal(book.book_id, proposal.proposal_id)
    approved_again = service.approve_proposal(book.book_id, proposal.proposal_id)
    canon_entries = service.repository.list_canon_entries(book_id=book.book_id)

    assert proposal.payload["duplicate_canon_id"] == canon.canon_id
    assert approved.status == "approved"
    assert approved.payload["duplicate_detected"] is True
    assert approved.payload["applied_canon_id"] == canon.canon_id
    assert approved_again.payload["applied_canon_id"] == canon.canon_id
    assert [item.canon_id for item in canon_entries] == [canon.canon_id]


def test_retrieval_state_marks_stale_when_current_heads_or_canon_change(tmp_path: Path):
    service = _build_service(tmp_path)
    book, outline, plot, _event, _scene, _chapter = _seed_chain(service)

    started = service.start_index_rebuild(book.book_id)
    published = service.publish_index_rebuild(
        book.book_id,
        generation=started.generation,
        source_fingerprint=started.source_fingerprint,
        result={"artifact": "initial"},
    )

    service.update_plot(book.book_id, plot.plot_id, expected_version=plot.version, body="已更新主线")
    stale_after_head_change = service.repository.get_index_state(book.book_id)
    assert stale_after_head_change is not None
    assert stale_after_head_change.status == "stale"
    assert stale_after_head_change.generation == published.generation + 1
    assert stale_after_head_change.details["reason"] == "plot_updated"

    service.create_canon_entry(book.book_id, title="已采纳事实", body="主角不会飞行")
    stale_after_canon_change = service.repository.get_index_state(book.book_id)
    assert stale_after_canon_change is not None
    assert stale_after_canon_change.status == "stale"
    assert stale_after_canon_change.generation == stale_after_head_change.generation + 1
    assert stale_after_canon_change.details["reason"] == "canon_entry_created"
    assert stale_after_canon_change.source_fingerprint != stale_after_head_change.source_fingerprint


def test_duplicate_rebuild_start_is_rejected_while_same_generation_is_active(tmp_path: Path):
    service = _build_service(tmp_path)
    book, _outline, _plot, _event, _scene, _chapter = _seed_chain(service)

    started = service.start_index_rebuild(book.book_id)

    with pytest.raises(BookHierarchyConflictError) as exc_info:
        service.start_index_rebuild(book.book_id)

    assert exc_info.value.error_code == "index_rebuild_active"
    assert exc_info.value.details["active_generation"] == started.generation


def test_successful_rebuild_publish_marks_generation_fresh(tmp_path: Path):
    service = _build_service(tmp_path)
    book, _outline, _plot, _event, _scene, _chapter = _seed_chain(service)

    started = service.start_index_rebuild(book.book_id)
    published = service.publish_index_rebuild(
        book.book_id,
        generation=started.generation,
        source_fingerprint=started.source_fingerprint,
        result={"artifact": "codex-v1", "document_count": 6},
    )

    assert published.status == "fresh"
    assert published.generation == started.generation
    assert published.source_fingerprint == started.source_fingerprint
    assert published.details["active_generation"] is None
    assert published.details["published_generation"] == started.generation
    assert published.details["result"] == {"artifact": "codex-v1", "document_count": 6}


def test_stale_generation_cannot_publish_over_newer_invalidation(tmp_path: Path):
    service = _build_service(tmp_path)
    book, outline, plot, _event, _scene, _chapter = _seed_chain(service)
    target_plot = service.create_plot(book.book_id, outline.outline_id, title="新支线")

    build_a = service.start_index_rebuild(book.book_id)

    service.update_plot(book.book_id, target_plot.plot_id, expected_version=target_plot.version, body="第二版支线")
    build_b = service.start_index_rebuild(book.book_id)
    published_b = service.publish_index_rebuild(
        book.book_id,
        generation=build_b.generation,
        source_fingerprint=build_b.source_fingerprint,
        result={"artifact": "codex-v2"},
    )

    with pytest.raises(BookHierarchyConflictError) as exc_info:
        service.publish_index_rebuild(
            book.book_id,
            generation=build_a.generation,
            source_fingerprint=build_a.source_fingerprint,
            result={"artifact": "codex-stale"},
        )

    current = service.repository.get_index_state(book.book_id)
    assert exc_info.value.error_code == "stale_index_generation"
    assert exc_info.value.details["attempted_generation"] == build_a.generation
    assert current is not None
    assert current.status == "fresh"
    assert current.generation == published_b.generation
    assert current.details["result"] == {"artifact": "codex-v2"}


def test_rebuild_source_uses_only_approved_canon_and_current_heads(tmp_path: Path):
    service = _build_service(tmp_path)
    book, outline, plot, event, scene, chapter = _seed_chain(service)
    approved_canon = service.create_canon_entry(book.book_id, title="已采纳事实", body="这是正式事实")
    service.create_canon_extraction_proposal(
        book.book_id,
        source_type="scene",
        source_id=scene.scene_id,
        title="候选事实",
        body="只存在于提案中",
        metadata={"status": "pending"},
    )
    service.create_structural_proposal(
        book.book_id,
        parent_type="plot",
        parent_id=plot.plot_id,
        child_type="event",
        proposal_type="plot_split",
        proposed_children=[{"title": "待审批事件", "body": "仅提案可见", "metadata": {}}],
    )

    started = service.start_index_rebuild(book.book_id)
    source_dump = json.dumps(started.source, ensure_ascii=False, sort_keys=True)

    assert started.source["canon_entries"] == [
        {
            "canon_id": approved_canon.canon_id,
            "title": "已采纳事实",
            "body": "这是正式事实",
            "metadata": {},
            "position": 0,
            "version": approved_canon.version,
        }
    ]
    assert [item["outline_id"] for item in started.source["current_heads"]["outlines"]] == [outline.outline_id]
    assert [item["plot_id"] for item in started.source["current_heads"]["plots"]] == [plot.plot_id]
    assert [item["event_id"] for item in started.source["current_heads"]["events"]] == [event.event_id]
    assert [item["scene_id"] for item in started.source["current_heads"]["scenes"]] == [scene.scene_id]
    assert [item["chapter_id"] for item in started.source["current_heads"]["chapters"]] == [chapter.chapter_id]
    assert "候选事实" not in source_dump
    assert "待审批事件" not in source_dump
