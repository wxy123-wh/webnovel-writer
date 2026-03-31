# pyright: reportMissingImports=false, reportImplicitRelativeImport=false

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from core.book_hierarchy import BookHierarchyService
from dashboard.app import create_app


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    webnovel_dir = tmp_path / ".webnovel"
    webnovel_dir.mkdir()
    (webnovel_dir / "state.json").write_text("{}", encoding="utf-8")
    return tmp_path


@pytest.fixture
def client(project_root: Path) -> TestClient:
    app = create_app(project_root=project_root)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def hierarchy_service(project_root: Path) -> BookHierarchyService:
    return BookHierarchyService(project_root)


def _create_book(client: TestClient, title: str = "测试作品") -> dict[str, object]:
    response = client.post("/api/hierarchy/books", json={"title": title, "synopsis": "简介"})
    assert response.status_code == 201
    return response.json()


def _create_entity(
    client: TestClient,
    book_id: str,
    entity_type: str,
    *,
    parent_id: str | None = None,
    title: str,
    body: str = "",
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    payload = {
        "parent_id": parent_id,
        "title": title,
        "body": body,
        "metadata": metadata or {},
    }
    response = client.post(f"/api/hierarchy/books/{book_id}/entities/{entity_type}", json=payload)
    assert response.status_code == 201, response.json()
    return response.json()


def _seed_outline_plot(client: TestClient) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    book = _create_book(client)
    outline = _create_entity(client, str(book["book_id"]), "outline", title="总纲", body="初始总纲")
    plot = _create_entity(client, str(book["book_id"]), "plot", parent_id=str(outline["outline_id"]), title="主线", body="初始主线")
    return book, outline, plot


def test_hierarchy_crud_ordering_and_revisions(client: TestClient):
    book, outline, plot = _seed_outline_plot(client)
    book_id = str(book["book_id"])
    plot_id = str(plot["plot_id"])

    get_response = client.get(f"/api/hierarchy/books/{book_id}/entities/plot/{plot_id}")
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "主线"

    update_response = client.patch(
        f"/api/hierarchy/books/{book_id}/entities/plot/{plot_id}",
        json={"expected_version": 1, "body": "第二版主线", "metadata": {"status": "approved"}},
    )
    assert update_response.status_code == 200
    updated_plot = update_response.json()
    assert updated_plot["version"] == 2
    assert updated_plot["body"] == "第二版主线"

    second_plot = _create_entity(client, book_id, "plot", parent_id=str(outline["outline_id"]), title="支线", body="支线正文")
    reorder_response = client.post(
        f"/api/hierarchy/books/{book_id}/entities/plot/reorder",
        json={"parent_id": outline["outline_id"], "ordered_ids": [second_plot["plot_id"], plot_id]},
    )
    assert reorder_response.status_code == 200
    reordered = reorder_response.json()
    assert [item["plot_id"] for item in reordered] == [second_plot["plot_id"], plot_id]
    assert [item["position"] for item in reordered] == [0, 1]
    reordered_plot = next(item for item in reordered if item["plot_id"] == plot_id)
    assert reordered_plot["version"] == 3

    revisions_response = client.get(f"/api/hierarchy/books/{book_id}/revisions/plot/{plot_id}")
    assert revisions_response.status_code == 200
    revisions = revisions_response.json()
    assert [item["revision_number"] for item in revisions] == [1, 2]

    diff_response = client.get(
        f"/api/hierarchy/books/{book_id}/revisions/plot/{plot_id}/diff",
        params={"from_revision": 1, "to_revision": 2},
    )
    assert diff_response.status_code == 200
    assert '"body": "第二版主线"' in diff_response.json()["diff"]

    rollback_response = client.post(
        f"/api/hierarchy/books/{book_id}/revisions/plot/{plot_id}/rollback",
        json={"target_revision": 1, "expected_version": 3},
    )
    assert rollback_response.status_code == 200
    rolled_back = rollback_response.json()
    assert rolled_back["version"] == 4
    assert rolled_back["body"] == "初始主线"

    delete_response = client.delete(f"/api/hierarchy/books/{book_id}/entities/plot/{second_plot['plot_id']}")
    assert delete_response.status_code == 204

    missing_response = client.get(f"/api/hierarchy/books/{book_id}/entities/plot/{second_plot['plot_id']}")
    assert missing_response.status_code == 404
    assert missing_response.json()["error_code"] == "entity_not_found"


def test_proposal_preview_confirm_and_reject_keep_service_guards_authoritative(
    client: TestClient,
    hierarchy_service: BookHierarchyService,
):
    book, outline, plot = _seed_outline_plot(client)
    book_id = str(book["book_id"])
    target_plot_id = str(plot["plot_id"])

    preview_response = client.post(
        f"/api/hierarchy/books/{book_id}/proposals/preview",
        json={
            "kind": "structural_children",
            "parent_type": "plot",
            "parent_id": target_plot_id,
            "child_type": "event",
            "proposal_type": "plot_split",
            "proposed_children": [{"title": "提议事件", "body": "草案", "metadata": {"beat": 1}}],
        },
    )
    assert preview_response.status_code == 201
    proposal = preview_response.json()
    assert proposal["status"] == "pending"
    assert proposal["payload"]["applied_entity_ids"] == []
    assert hierarchy_service.repository.child_count(table="plots", id_value=str(target_plot_id)) == 0

    confirm_response = client.post(f"/api/hierarchy/books/{book_id}/proposals/{proposal['proposal_id']}/confirm")
    assert confirm_response.status_code == 200
    approved = confirm_response.json()
    assert approved["status"] == "approved"
    assert len(approved["payload"]["applied_entity_ids"]) == 1
    assert hierarchy_service.repository.child_count(table="plots", id_value=str(target_plot_id)) == 1

    reject_target = _create_entity(client, book_id, "plot", parent_id=str(outline["outline_id"]), title="待拒绝支线")
    reject_preview_response = client.post(
        f"/api/hierarchy/books/{book_id}/proposals/preview",
        json={
            "kind": "structural_children",
            "parent_type": "plot",
            "parent_id": reject_target["plot_id"],
            "child_type": "event",
            "proposal_type": "plot_split",
            "proposed_children": [{"title": "不会落库的事件", "body": "草案", "metadata": {}}],
        },
    )
    assert reject_preview_response.status_code == 201
    reject_proposal = reject_preview_response.json()

    reject_response = client.post(f"/api/hierarchy/books/{book_id}/proposals/{reject_proposal['proposal_id']}/reject")
    assert reject_response.status_code == 200
    rejected = reject_response.json()
    assert rejected["status"] == "rejected"
    assert hierarchy_service.repository.child_count(table="plots", id_value=str(reject_target["plot_id"])) == 0


def test_stale_write_conflict_returns_stable_error_payload(client: TestClient):
    book, _outline, plot = _seed_outline_plot(client)
    book_id = str(book["book_id"])
    plot_id = str(plot["plot_id"])

    first_update = client.patch(
        f"/api/hierarchy/books/{book_id}/entities/plot/{plot_id}",
        json={"expected_version": 1, "body": "第一次更新"},
    )
    assert first_update.status_code == 200

    stale_update = client.patch(
        f"/api/hierarchy/books/{book_id}/entities/plot/{plot_id}",
        json={"expected_version": 1, "body": "过期更新"},
    )
    assert stale_update.status_code == 409
    payload = stale_update.json()
    assert payload == {
        "error_code": "version_mismatch",
        "message": "The record was modified by another write and must be reloaded.",
        "details": {
            "entity_id": plot_id,
            "expected_version": 1,
            "current_version": 2,
        },
        "request_id": None,
    }


def test_delete_with_children_returns_machine_readable_conflict(client: TestClient):
    book, outline, plot = _seed_outline_plot(client)
    _event = _create_entity(client, str(book["book_id"]), "event", parent_id=str(plot["plot_id"]), title="事件")

    response = client.delete(f"/api/hierarchy/books/{book['book_id']}/entities/plot/{plot['plot_id']}")
    assert response.status_code == 409
    payload = response.json()
    assert payload["error_code"] == "children_exist"
    assert payload["details"] == {"plot_id": plot["plot_id"], "child_count": 1}


def test_create_scene_enforces_immediate_parent(client: TestClient):
    book, _outline, plot = _seed_outline_plot(client)

    response = client.post(
        f"/api/hierarchy/books/{book['book_id']}/entities/scene",
        json={"parent_id": plot["plot_id"], "title": "非法场景", "body": "", "metadata": {}},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "invalid_parent"
    assert payload["details"] == {"event_id": plot["plot_id"]}


def test_stale_proposal_approval_returns_stable_conflict_payload(client: TestClient):
    book, _outline, plot = _seed_outline_plot(client)
    book_id = str(book["book_id"])
    plot_id = str(plot["plot_id"])

    preview_response = client.post(
        f"/api/hierarchy/books/{book_id}/proposals/preview",
        json={
            "kind": "structural_children",
            "parent_type": "plot",
            "parent_id": plot_id,
            "child_type": "event",
            "proposal_type": "plot_split",
            "proposed_children": [{"title": "过期事件", "body": "旧版本", "metadata": {}}],
        },
    )
    assert preview_response.status_code == 201
    proposal = preview_response.json()

    update_response = client.patch(
        f"/api/hierarchy/books/{book_id}/entities/plot/{plot_id}",
        json={"expected_version": 1, "body": "新版本正文"},
    )
    assert update_response.status_code == 200

    confirm_response = client.post(f"/api/hierarchy/books/{book_id}/proposals/{proposal['proposal_id']}/confirm")
    assert confirm_response.status_code == 409
    payload = confirm_response.json()
    assert payload["error_code"] == "stale_proposal_base"
    assert payload["details"]["proposal_id"] == proposal["proposal_id"]
    assert payload["details"]["base_version"] == 1
    assert payload["details"]["current_version"] == 2

    refreshed = client.get(f"/api/hierarchy/books/{book_id}/proposals/{proposal['proposal_id']}")
    assert refreshed.status_code == 200
    assert refreshed.json()["status"] == "stale"


def test_workspace_snapshot_exposes_active_book_tree_and_reviewables(client: TestClient):
    book, outline, plot = _seed_outline_plot(client)
    book_id = str(book["book_id"])
    event = _create_entity(client, book_id, "event", parent_id=str(plot["plot_id"]), title="守夜人报信")
    scene = _create_entity(client, book_id, "scene", parent_id=str(event["event_id"]), title="雪夜对峙")
    chapter = _create_entity(client, book_id, "chapter", parent_id=str(scene["scene_id"]), title="第一章")
    setting = _create_entity(client, book_id, "setting", title="天穹城", body="夜间宵禁")

    proposal_response = client.post(
        f"/api/hierarchy/books/{book_id}/proposals/preview",
        json={
            "kind": "structural_children",
            "parent_type": "plot",
            "parent_id": str(plot["plot_id"]),
            "child_type": "event",
            "proposal_type": "plot_split",
            "proposed_children": [{"title": "候选事件", "body": "草案", "metadata": {}}],
        },
    )
    assert proposal_response.status_code == 201

    workspace_response = client.get("/api/hierarchy/workspace")
    assert workspace_response.status_code == 200
    payload = workspace_response.json()

    assert payload["book"]["book_id"] == book_id
    assert [item["outline_id"] for item in payload["outlines"]] == [outline["outline_id"]]
    assert [item["plot_id"] for item in payload["plots"]] == [plot["plot_id"]]
    assert [item["event_id"] for item in payload["events"]] == [event["event_id"]]
    assert [item["scene_id"] for item in payload["scenes"]] == [scene["scene_id"]]
    assert [item["chapter_id"] for item in payload["chapters"]] == [chapter["chapter_id"]]
    assert [item["setting_id"] for item in payload["settings"]] == [setting["setting_id"]]
    assert payload["canon_entries"] == []
    assert payload["proposals"][0]["proposal_id"] == proposal_response.json()["proposal_id"]


def test_chapter_edit_proposal_can_be_confirmed_and_updates_chapter_head(client: TestClient):
    book, _outline, plot = _seed_outline_plot(client)
    book_id = str(book["book_id"])
    event = _create_entity(client, book_id, "event", parent_id=str(plot["plot_id"]), title="事件")
    scene = _create_entity(client, book_id, "scene", parent_id=str(event["event_id"]), title="场景")
    chapter = _create_entity(client, book_id, "chapter", parent_id=str(scene["scene_id"]), title="章节", body="章节初稿")

    preview_response = client.post(
        f"/api/hierarchy/books/{book_id}/proposals/preview",
        json={
            "kind": "chapter_edit",
            "chapter_id": str(chapter["chapter_id"]),
            "summary": "强化结尾",
            "proposed_update": {
                "title": "章节（修订）",
                "body": "修订后的章节正文",
                "metadata": {"tone": "grim"},
            },
        },
    )
    assert preview_response.status_code == 201, preview_response.json()
    proposal = preview_response.json()
    assert proposal["payload"]["kind"] == "chapter_edit"

    confirm_response = client.post(f"/api/hierarchy/books/{book_id}/proposals/{proposal['proposal_id']}/confirm")
    assert confirm_response.status_code == 200, confirm_response.json()
    approved = confirm_response.json()
    assert approved["status"] == "approved"
    assert approved["payload"]["applied_chapter_version"] == 2

    chapter_response = client.get(f"/api/hierarchy/books/{book_id}/entities/chapter/{chapter['chapter_id']}")
    assert chapter_response.status_code == 200
    assert chapter_response.json()["title"] == "章节（修订）"
    assert chapter_response.json()["body"] == "修订后的章节正文"
    assert chapter_response.json()["version"] == 2


def test_workspace_snapshot_includes_canon_entries_and_index_state(client: TestClient, hierarchy_service: BookHierarchyService):
    book, _outline, plot = _seed_outline_plot(client)
    book_id = str(book["book_id"])
    event = _create_entity(client, book_id, "event", parent_id=str(plot["plot_id"]), title="事件")
    scene = _create_entity(client, book_id, "scene", parent_id=str(event["event_id"]), title="场景")
    _chapter = _create_entity(client, book_id, "chapter", parent_id=str(scene["scene_id"]), title="章节")
    canon = _create_entity(client, book_id, "canon_entry", title="正式设定", body="主角不会飞行")
    hierarchy_service.upsert_index_state(
        book_id,
        generation=3,
        status="failed",
        source_fingerprint="fp-3",
        details={"reason": "manual_retry", "active_generation": None, "published_generation": 2},
    )

    workspace_response = client.get("/api/hierarchy/workspace")
    assert workspace_response.status_code == 200
    payload = workspace_response.json()

    assert [item["canon_id"] for item in payload["canon_entries"]] == [canon["canon_id"]]
    assert payload["index_state"]["status"] == "failed"
    assert payload["index_state"]["generation"] == 3
    assert payload["index_state"]["details"]["published_generation"] == 2


def test_reindex_endpoints_surface_backend_truth_and_duplicate_click_conflict(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    book, outline, plot = _seed_outline_plot(client)
    book_id = str(book["book_id"])

    monkeypatch.setattr(
        "scripts.pipeline.adapters.refresh_index",
        lambda project_root: {"artifact": "codex-v3", "project_root": str(project_root)},
    )

    mark_stale_response = client.post(f"/api/hierarchy/books/{book_id}/index/mark-stale", json={"reason": "manual_reset"})
    assert mark_stale_response.status_code == 200, mark_stale_response.json()
    marked = mark_stale_response.json()
    assert marked["status"] == "stale"
    assert marked["details"]["reason"] == "manual_reset"

    rebuild_response = client.post(f"/api/hierarchy/books/{book_id}/index/rebuild")
    assert rebuild_response.status_code == 200, rebuild_response.json()
    rebuilt = rebuild_response.json()
    assert rebuilt["status"] == "fresh"
    assert rebuilt["details"]["active_generation"] is None
    assert rebuilt["details"]["published_generation"] == rebuilt["generation"]
    assert rebuilt["details"]["result"]["current_heads"]["plots"] >= 1

    hierarchy_service = BookHierarchyService(Path(client.app.state.project_root))
    hierarchy_service.start_index_rebuild(book_id)

    duplicate_response = client.post(f"/api/hierarchy/books/{book_id}/index/rebuild")
    assert duplicate_response.status_code == 409
    duplicate_payload = duplicate_response.json()
    assert duplicate_payload["error_code"] == "index_rebuild_active"
    assert duplicate_payload["details"]["active_generation"] >= rebuilt["generation"]
