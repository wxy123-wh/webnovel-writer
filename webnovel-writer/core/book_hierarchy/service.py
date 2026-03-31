from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import Any

from .models import (
    BookHierarchyConflictError,
    BookHierarchyGuardedDeleteError,
    BookHierarchyNotFoundError,
    BookHierarchyValidationError,
    BookHierarchyVersionMismatchError,
    IndexRebuild,
)
from .repository import BookHierarchyRepository, canonical_fingerprint
from .schema import get_hierarchy_db_path


class BookHierarchyService:
    _STRUCTURAL_CHILD_TYPES = {
        "outline": "plot",
        "plot": "event",
        "event": "scene",
        "scene": "chapter",
    }

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.db_path = get_hierarchy_db_path(self.project_root)
        self.repository = BookHierarchyRepository(self.db_path)
        self._index_invalidation_suspensions = 0

    def create_book_root(self, title: str, *, synopsis: str = ""):
        try:
            return self.repository.create_book_root(project_root=str(self.project_root), title=title, synopsis=synopsis)
        except sqlite3.IntegrityError as exc:
            if "idx_book_roots_single_active_per_project" in str(exc) or "UNIQUE constraint failed: book_roots.project_root" in str(exc):
                raise BookHierarchyConflictError(
                    "book_root_conflict",
                    "Only one active book root is allowed per project.",
                    details={"project_root": str(self.project_root)},
                ) from exc
            raise

    def create_outline(self, book_id: str, *, title: str, body: str = "", metadata: dict[str, Any] | None = None):
        self._require_book(book_id)
        outline = self.repository.create_outline(book_id=book_id, title=title, body=body, metadata=metadata)
        self._mark_index_stale(book_id, reason="outline_created")
        return outline

    def create_plot(self, book_id: str, outline_id: str, *, title: str, body: str = "", metadata: dict[str, Any] | None = None):
        outline = self._require_outline(outline_id)
        self._validate_same_book(book_id, outline.book_id, entity_type="outline", entity_id=outline_id)
        plot = self.repository.create_plot(book_id=book_id, outline_id=outline_id, title=title, body=body, metadata=metadata)
        self._mark_index_stale(book_id, reason="plot_created")
        return plot

    def create_event(self, book_id: str, plot_id: str, *, title: str, body: str = "", metadata: dict[str, Any] | None = None):
        plot = self._require_plot(plot_id)
        self._validate_same_book(book_id, plot.book_id, entity_type="plot", entity_id=plot_id)
        event = self.repository.create_event(book_id=book_id, plot_id=plot_id, title=title, body=body, metadata=metadata)
        self._mark_index_stale(book_id, reason="event_created")
        return event

    def create_scene(self, book_id: str, event_id: str, *, title: str, body: str = "", metadata: dict[str, Any] | None = None):
        event = self._require_event(event_id)
        self._validate_same_book(book_id, event.book_id, entity_type="event", entity_id=event_id)
        scene = self.repository.create_scene(book_id=book_id, event_id=event_id, title=title, body=body, metadata=metadata)
        self._mark_index_stale(book_id, reason="scene_created")
        return scene

    def create_chapter(self, book_id: str, scene_id: str, *, title: str, body: str = "", metadata: dict[str, Any] | None = None):
        scene = self._require_scene(scene_id)
        self._validate_same_book(book_id, scene.book_id, entity_type="scene", entity_id=scene_id)
        chapter = self.repository.create_chapter(book_id=book_id, scene_id=scene_id, title=title, body=body, metadata=metadata)
        self._mark_index_stale(book_id, reason="chapter_created")
        return chapter

    def create_setting(self, book_id: str, *, title: str, body: str = "", metadata: dict[str, Any] | None = None):
        self._require_book(book_id)
        setting = self.repository.create_setting(book_id=book_id, title=title, body=body, metadata=metadata)
        self._mark_index_stale(book_id, reason="setting_created")
        return setting

    def create_canon_entry(self, book_id: str, *, title: str, body: str = "", metadata: dict[str, Any] | None = None):
        self._require_book(book_id)
        canon = self.repository.create_canon_entry(book_id=book_id, title=title, body=body, metadata=metadata)
        self._mark_index_stale(book_id, reason="canon_entry_created")
        return canon

    def create_proposal(
        self,
        book_id: str,
        *,
        proposal_type: str,
        target_type: str,
        status: str = "pending",
        payload: dict[str, Any] | None = None,
        base_version: int | None = None,
    ):
        self._require_book(book_id)
        return self.repository.create_proposal(
            book_id=book_id,
            proposal_type=proposal_type,
            target_type=target_type,
            status=status,
            payload=payload,
            base_version=base_version,
        )

    def create_chapter_edit_proposal(
        self,
        book_id: str,
        *,
        chapter_id: str,
        summary: str = "",
        proposed_update: dict[str, Any] | None = None,
        proposal_type: str = "chapter_edit",
    ):
        chapter = self._require_chapter(chapter_id)
        self._validate_same_book(book_id, chapter.book_id, entity_type="chapter", entity_id=chapter_id)
        normalized_update = self._normalize_child_payload(
            {
                "title": (proposed_update or {}).get("title", chapter.title),
                "body": (proposed_update or {}).get("body", chapter.body),
                "metadata": (proposed_update or {}).get("metadata", {}),
            }
        )
        base_fingerprint = self._fingerprint_entity("chapter", chapter)
        return self.repository.create_proposal(
            book_id=book_id,
            proposal_type=proposal_type,
            target_type="chapter",
            payload={
                "kind": "chapter_edit",
                "chapter_id": chapter_id,
                "summary": str(summary or ""),
                "proposed_update": normalized_update,
                "applied_chapter_version": None,
            },
            base_version=chapter.version,
            base_fingerprint=base_fingerprint,
            current_head_fingerprint=base_fingerprint,
        )

    def create_structural_proposal(
        self,
        book_id: str,
        *,
        parent_type: str,
        parent_id: str,
        child_type: str,
        proposal_type: str,
        proposed_children: list[dict[str, Any]],
    ):
        parent = self._require_entity(parent_type, parent_id)
        self._validate_same_book(book_id, parent.book_id, entity_type=parent_type, entity_id=parent_id)
        self._validate_structural_target(parent_type=parent_type, child_type=child_type)
        normalized_children = [self._normalize_child_payload(item) for item in proposed_children]
        if not normalized_children:
            raise BookHierarchyValidationError(
                "invalid_proposal_payload",
                "Structural proposals require at least one proposed child.",
                details={"parent_type": parent_type, "parent_id": parent_id, "child_type": child_type},
            )
        base_fingerprint = self._fingerprint_entity(parent_type, parent)
        return self.repository.create_proposal(
            book_id=book_id,
            proposal_type=proposal_type,
            target_type=child_type,
            payload={
                "kind": "structural_children",
                "parent_type": parent_type,
                "parent_id": parent_id,
                "child_type": child_type,
                "proposed_children": normalized_children,
                "applied_entity_ids": [],
            },
            base_version=parent.version,
            base_fingerprint=base_fingerprint,
            current_head_fingerprint=base_fingerprint,
        )

    def create_canon_extraction_proposal(
        self,
        book_id: str,
        *,
        source_type: str,
        source_id: str,
        title: str,
        body: str = "",
        metadata: dict[str, Any] | None = None,
        proposal_type: str = "canon_extract",
    ):
        source = self._require_entity(source_type, source_id)
        self._validate_same_book(book_id, source.book_id, entity_type=source_type, entity_id=source_id)
        candidate = self._normalize_child_payload({"title": title, "body": body, "metadata": metadata or {}})
        candidate_fingerprint = self._fingerprint_canon_candidate(candidate)
        duplicate_canon_id = self._find_duplicate_canon_entry(book_id, candidate_fingerprint)
        base_fingerprint = self._fingerprint_entity(source_type, source)
        return self.repository.create_proposal(
            book_id=book_id,
            proposal_type=proposal_type,
            target_type="canon_entry",
            payload={
                "kind": "canon_candidate",
                "source_type": source_type,
                "source_id": source_id,
                "candidate": candidate,
                "candidate_fingerprint": candidate_fingerprint,
                "duplicate_canon_id": duplicate_canon_id,
                "duplicate_detected": duplicate_canon_id is not None,
                "applied_canon_id": None,
            },
            base_version=source.version,
            base_fingerprint=base_fingerprint,
            current_head_fingerprint=base_fingerprint,
        )

    def get_proposal(self, book_id: str, proposal_id: str):
        proposal = self.repository.get_proposal(proposal_id)
        if proposal is None or proposal.book_id != book_id:
            raise BookHierarchyNotFoundError(
                "proposal_not_found",
                "Proposal was not found.",
                details={"book_id": book_id, "proposal_id": proposal_id},
            )
        return proposal

    def approve_proposal(self, book_id: str, proposal_id: str):
        proposal = self.get_proposal(book_id, proposal_id)
        if proposal.status == "approved":
            return proposal
        if proposal.status == "stale":
            raise self._stale_proposal_error(proposal, current_version=None)
        if proposal.status != "pending":
            raise BookHierarchyValidationError(
                "proposal_not_pending",
                "Only pending proposals can be approved.",
                details={"proposal_id": proposal_id, "status": proposal.status},
            )
        source_type, source_id = self._proposal_source(proposal)
        source = self._require_entity(source_type, source_id)
        self._validate_same_book(book_id, source.book_id, entity_type=source_type, entity_id=source_id)
        current_head_fingerprint = self._fingerprint_entity(source_type, source)
        if source.version != proposal.base_version or current_head_fingerprint != proposal.base_fingerprint:
            stale = self.repository.update_proposal(
                proposal_id=proposal.proposal_id,
                status="stale",
                payload=proposal.payload,
                current_head_fingerprint=current_head_fingerprint,
                decision_reason="stale_base",
            )
            raise self._stale_proposal_error(stale, current_version=source.version)
        with self._suspend_index_invalidation():
            if proposal.payload.get("kind") == "structural_children":
                payload, decision_reason = self._approve_structural_proposal(book_id, proposal)
                invalidation_reason = "structural_proposal_approved"
            elif proposal.payload.get("kind") == "canon_candidate":
                payload, decision_reason = self._approve_canon_proposal(book_id, proposal)
                invalidation_reason = "canon_proposal_approved"
            elif proposal.payload.get("kind") == "chapter_edit":
                payload, decision_reason = self._approve_chapter_edit_proposal(book_id, proposal)
                invalidation_reason = "chapter_edit_proposal_approved"
            else:
                raise BookHierarchyValidationError(
                    "invalid_proposal_payload",
                    "Proposal payload kind is not supported.",
                    details={"proposal_id": proposal_id},
                )
        approved = self.repository.update_proposal(
            proposal_id=proposal.proposal_id,
            status="approved",
            payload=payload,
            current_head_fingerprint=current_head_fingerprint,
            decision_reason=decision_reason,
        )
        self._mark_index_stale(book_id, reason=invalidation_reason)
        return approved

    def reject_proposal(self, book_id: str, proposal_id: str):
        return self._resolve_proposal_without_commit(book_id, proposal_id, status="rejected", decision_reason="rejected")

    def cancel_proposal(self, book_id: str, proposal_id: str):
        return self._resolve_proposal_without_commit(book_id, proposal_id, status="cancelled", decision_reason="cancelled")

    def upsert_index_state(
        self,
        book_id: str,
        *,
        generation: int,
        status: str,
        source_fingerprint: str,
        details: dict[str, Any] | None = None,
    ):
        self._require_book(book_id)
        return self.repository.upsert_index_state(
            book_id=book_id,
            generation=generation,
            status=status,
            source_fingerprint=source_fingerprint,
            details=details,
        )

    def start_index_rebuild(self, book_id: str) -> IndexRebuild:
        self._require_book(book_id)
        current = self.repository.get_index_state(book_id)
        if current is not None and current.status == "building":
            raise BookHierarchyConflictError(
                "index_rebuild_active",
                "A rebuild is already active for this book.",
                details={
                    "book_id": book_id,
                    "active_generation": current.details.get("active_generation", current.generation),
                    "source_fingerprint": current.source_fingerprint,
                },
            )
        source = self._build_index_source(book_id)
        generation = 1 if current is None else current.generation
        details = self._merged_index_details(current)
        details["active_generation"] = generation
        state = self.repository.upsert_index_state(
            book_id=book_id,
            generation=generation,
            status="building",
            source_fingerprint=source["source_fingerprint"],
            details=details,
        )
        return IndexRebuild(
            book_id=book_id,
            generation=generation,
            source_fingerprint=source["source_fingerprint"],
            source=source["payload"],
            state=state,
        )

    def publish_index_rebuild(
        self,
        book_id: str,
        *,
        generation: int,
        source_fingerprint: str,
        result: dict[str, Any] | None = None,
    ):
        self._require_book(book_id)
        current = self.repository.get_index_state(book_id)
        if (
            current is None
            or current.status != "building"
            or current.generation != generation
            or current.source_fingerprint != source_fingerprint
        ):
            current_generation = None if current is None else current.generation
            current_fingerprint = "" if current is None else current.source_fingerprint
            raise BookHierarchyConflictError(
                "stale_index_generation",
                "Only the newest valid rebuild can be published.",
                details={
                    "book_id": book_id,
                    "attempted_generation": generation,
                    "current_generation": current_generation,
                    "attempted_source_fingerprint": source_fingerprint,
                    "current_source_fingerprint": current_fingerprint,
                },
            )
        details = self._merged_index_details(current)
        details["active_generation"] = None
        details["published_generation"] = generation
        details["result"] = dict(result or {})
        return self.repository.upsert_index_state(
            book_id=book_id,
            generation=generation,
            status="fresh",
            source_fingerprint=source_fingerprint,
            details=details,
        )

    def list_plots(self, book_id: str, outline_id: str):
        outline = self._require_outline(outline_id)
        self._validate_same_book(book_id, outline.book_id, entity_type="outline", entity_id=outline_id)
        return self.repository.list_plots(book_id=book_id, outline_id=outline_id)

    def reorder_plots(self, book_id: str, outline_id: str, ordered_ids: list[str]) -> None:
        outline = self._require_outline(outline_id)
        self._validate_same_book(book_id, outline.book_id, entity_type="outline", entity_id=outline_id)
        try:
            self.repository.reorder_children(
                table="plots",
                id_column="plot_id",
                parent_column="outline_id",
                parent_value=outline_id,
                ordered_ids=[str(item_id) for item_id in ordered_ids],
            )
        except ValueError as exc:
            raise BookHierarchyValidationError(
                "invalid_reorder_set",
                "The provided sibling order must contain exactly the persisted siblings.",
                details={"outline_id": outline_id},
            ) from exc
        self._mark_index_stale(book_id, reason="plots_reordered")

    def update_outline(
        self,
        book_id: str,
        outline_id: str,
        *,
        expected_version: int,
        title: str | None = None,
        body: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        outline = self._require_outline(outline_id)
        self._validate_same_book(book_id, outline.book_id, entity_type="outline", entity_id=outline_id)
        return self._update_versioned_entity(
            entity_type="outline",
            entity_id=outline_id,
            expected_version=expected_version,
            invalidation_reason="outline_updated",
            update_operation=lambda: self.repository.update_outline(
                outline_id=outline_id,
                expected_version=expected_version,
                title=title,
                body=body,
                metadata=metadata,
            ),
        )

    def update_plot(
        self,
        book_id: str,
        plot_id: str,
        *,
        expected_version: int,
        title: str | None = None,
        body: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        plot = self._require_plot(plot_id)
        self._validate_same_book(book_id, plot.book_id, entity_type="plot", entity_id=plot_id)
        return self._update_versioned_entity(
            entity_type="plot",
            entity_id=plot_id,
            expected_version=expected_version,
            invalidation_reason="plot_updated",
            update_operation=lambda: self.repository.update_plot(
                plot_id=plot_id,
                expected_version=expected_version,
                title=title,
                body=body,
                metadata=metadata,
            ),
        )

    def update_event(
        self,
        book_id: str,
        event_id: str,
        *,
        expected_version: int,
        title: str | None = None,
        body: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        event = self._require_event(event_id)
        self._validate_same_book(book_id, event.book_id, entity_type="event", entity_id=event_id)
        return self._update_current_state_entity(
            entity_type="event",
            entity_id=event_id,
            expected_version=expected_version,
            invalidation_reason="event_updated",
            update_operation=lambda: self.repository.update_event(
                event_id=event_id,
                expected_version=expected_version,
                title=title,
                body=body,
                metadata=metadata,
            ),
        )

    def update_scene(
        self,
        book_id: str,
        scene_id: str,
        *,
        expected_version: int,
        title: str | None = None,
        body: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        scene = self._require_scene(scene_id)
        self._validate_same_book(book_id, scene.book_id, entity_type="scene", entity_id=scene_id)
        return self._update_current_state_entity(
            entity_type="scene",
            entity_id=scene_id,
            expected_version=expected_version,
            invalidation_reason="scene_updated",
            update_operation=lambda: self.repository.update_scene(
                scene_id=scene_id,
                expected_version=expected_version,
                title=title,
                body=body,
                metadata=metadata,
            ),
        )

    def update_chapter(
        self,
        book_id: str,
        chapter_id: str,
        *,
        expected_version: int,
        title: str | None = None,
        body: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        chapter = self._require_chapter(chapter_id)
        self._validate_same_book(book_id, chapter.book_id, entity_type="chapter", entity_id=chapter_id)
        return self._update_versioned_entity(
            entity_type="chapter",
            entity_id=chapter_id,
            expected_version=expected_version,
            invalidation_reason="chapter_updated",
            update_operation=lambda: self.repository.update_chapter(
                chapter_id=chapter_id,
                expected_version=expected_version,
                title=title,
                body=body,
                metadata=metadata,
            ),
        )

    def update_setting(
        self,
        book_id: str,
        setting_id: str,
        *,
        expected_version: int,
        title: str | None = None,
        body: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        setting = self._require_setting(setting_id)
        self._validate_same_book(book_id, setting.book_id, entity_type="setting", entity_id=setting_id)
        return self._update_versioned_entity(
            entity_type="setting",
            entity_id=setting_id,
            expected_version=expected_version,
            invalidation_reason="setting_updated",
            update_operation=lambda: self.repository.update_setting(
                setting_id=setting_id,
                expected_version=expected_version,
                title=title,
                body=body,
                metadata=metadata,
            ),
        )

    def update_canon_entry(
        self,
        book_id: str,
        canon_id: str,
        *,
        expected_version: int,
        title: str | None = None,
        body: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        canon = self._require_canon_entry(canon_id)
        self._validate_same_book(book_id, canon.book_id, entity_type="canon_entry", entity_id=canon_id)
        return self._update_current_state_entity(
            entity_type="canon_entry",
            entity_id=canon_id,
            expected_version=expected_version,
            invalidation_reason="canon_entry_updated",
            update_operation=lambda: self.repository.update_canon_entry(
                canon_id=canon_id,
                expected_version=expected_version,
                title=title,
                body=body,
                metadata=metadata,
            ),
        )

    def list_revisions(self, entity_type: str, entity_id: str):
        self.repository.ensure_baseline_revision(entity_type=entity_type, entity_id=entity_id)
        return self.repository.list_revisions(entity_type=entity_type, entity_id=entity_id)

    def diff_revisions(self, entity_type: str, entity_id: str, *, from_revision: int, to_revision: int) -> str:
        self.repository.ensure_baseline_revision(entity_type=entity_type, entity_id=entity_id)
        return self.repository.diff_revisions(entity_type=entity_type, entity_id=entity_id, from_revision=from_revision, to_revision=to_revision)

    def rollback_to_revision(
        self,
        book_id: str,
        entity_type: str,
        entity_id: str,
        *,
        target_revision: int,
        expected_version: int,
    ):
        current = self._require_entity(entity_type, entity_id)
        self._validate_same_book(book_id, current.book_id, entity_type=entity_type, entity_id=entity_id)
        self.repository.ensure_baseline_revision(entity_type=entity_type, entity_id=entity_id)
        revision = self.repository.get_revision(entity_type=entity_type, entity_id=entity_id, revision_number=target_revision)
        if revision is None:
            raise BookHierarchyValidationError(
                "revision_not_found",
                "Requested revision was not found.",
                details={"entity_type": entity_type, "entity_id": entity_id, "target_revision": target_revision},
            )
        changed = self.repository.apply_revision_snapshot(
            entity_type=entity_type,
            entity_id=entity_id,
            expected_version=expected_version,
            snapshot=deepcopy(revision.snapshot),
        )
        if changed == 0:
            latest = self._require_entity(entity_type, entity_id)
            raise BookHierarchyVersionMismatchError(
                "version_mismatch",
                "The record was modified by another write and must be reloaded.",
                details={"entity_id": entity_id, "expected_version": expected_version, "current_version": latest.version},
            )
        self.repository.create_revision(entity_type=entity_type, entity_id=entity_id, parent_revision_number=target_revision)
        restored = self._require_entity(entity_type, entity_id)
        self._mark_index_stale(book_id, reason=f"{entity_type}_rolled_back")
        return restored

    def delete_plot(self, book_id: str, plot_id: str) -> None:
        plot = self._require_plot(plot_id)
        self._validate_same_book(book_id, plot.book_id, entity_type="plot", entity_id=plot_id)
        child_count = self.repository.child_count(table="plots", id_value=plot_id)
        if child_count > 0:
            raise BookHierarchyGuardedDeleteError(
                "children_exist",
                "Cannot delete a parent node while it still has children.",
                details={"plot_id": plot_id, "child_count": child_count},
            )
        self.repository.delete_record(table="plots", id_column="plot_id", id_value=plot_id)
        self._mark_index_stale(book_id, reason="plot_deleted")

    def get_book_snapshot(self, book_id: str) -> dict[str, Any]:
        self._require_book(book_id)
        return {
            "settings": self.repository.list_settings(book_id=book_id),
            "canon_entries": self.repository.list_canon_entries(book_id=book_id),
            "proposals": self.repository.list_proposals(book_id=book_id),
            "index_state": self.repository.get_index_state(book_id),
        }

    def mark_index_stale(self, book_id: str, *, reason: str = "manual_reset"):
        self._require_book(book_id)
        return self._mark_index_stale(book_id, reason=reason or "manual_reset")

    def rebuild_index(self, book_id: str):
        rebuild = self.start_index_rebuild(book_id)
        refresh_index = import_module("scripts.pipeline.adapters").refresh_index
        try:
            refresh_result = refresh_index(self.project_root)
        except Exception as exc:
            failed_state = self.repository.upsert_index_state(
                book_id=book_id,
                generation=rebuild.generation,
                status="failed",
                source_fingerprint=rebuild.source_fingerprint,
                details={
                    **self._merged_index_details(rebuild.state),
                    "active_generation": None,
                    "published_generation": rebuild.state.details.get("published_generation"),
                    "error": str(exc),
                    "source_summary": self._index_source_summary(rebuild.source),
                },
            )
            raise BookHierarchyConflictError(
                "index_rebuild_failed",
                "Index rebuild failed before publish completed.",
                details={
                    "book_id": book_id,
                    "generation": rebuild.generation,
                    "error": str(exc),
                    "status": failed_state.status,
                },
            ) from exc

        return self.publish_index_rebuild(
            book_id,
            generation=rebuild.generation,
            source_fingerprint=rebuild.source_fingerprint,
            result={
                "refresh_result": refresh_result,
                "current_heads": self._index_source_summary(rebuild.source)["current_heads"],
                "canon_entries": self._index_source_summary(rebuild.source)["canon_entries"],
            },
        )

    def _require_book(self, book_id: str):
        book = self.repository.get_book_root(book_id)
        if book is None:
            raise BookHierarchyNotFoundError(
                "book_root_not_found",
                "Book root was not found.",
                details={"book_id": book_id},
            )
        return book

    def _require_outline(self, outline_id: str):
        outline = self.repository.get_outline(outline_id)
        if outline is None:
            raise BookHierarchyValidationError(
                "invalid_parent",
                "Outline parent is required and must exist.",
                details={"outline_id": outline_id},
            )
        return outline

    def _require_plot(self, plot_id: str):
        plot = self.repository.get_plot(plot_id)
        if plot is None:
            raise BookHierarchyValidationError(
                "invalid_parent",
                "Plot parent is required and must exist.",
                details={"plot_id": plot_id},
            )
        return plot

    def _require_event(self, event_id: str):
        event = self.repository.get_event(event_id)
        if event is None:
            raise BookHierarchyValidationError(
                "invalid_parent",
                "Event parent is required and must exist.",
                details={"event_id": event_id},
            )
        return event

    def _require_scene(self, scene_id: str):
        scene = self.repository.get_scene(scene_id)
        if scene is None:
            raise BookHierarchyValidationError(
                "invalid_parent",
                "Scene parent is required and must exist.",
                details={"scene_id": scene_id},
            )
        return scene

    def _require_chapter(self, chapter_id: str):
        chapter = self.repository.get_chapter(chapter_id)
        if chapter is None:
            raise BookHierarchyValidationError(
                "invalid_parent",
                "Chapter record is required and must exist.",
                details={"chapter_id": chapter_id},
            )
        return chapter

    def _require_setting(self, setting_id: str):
        setting = self.repository.get_setting(setting_id)
        if setting is None:
            raise BookHierarchyValidationError(
                "invalid_parent",
                "Setting record is required and must exist.",
                details={"setting_id": setting_id},
            )
        return setting

    def _require_canon_entry(self, canon_id: str):
        canon = self.repository.get_canon_entry(canon_id)
        if canon is None:
            raise BookHierarchyValidationError(
                "invalid_parent",
                "Canon entry record is required and must exist.",
                details={"canon_id": canon_id},
            )
        return canon

    def _require_entity(self, entity_type: str, entity_id: str):
        match entity_type:
            case "outline":
                return self._require_outline(entity_id)
            case "plot":
                return self._require_plot(entity_id)
            case "event":
                return self._require_event(entity_id)
            case "scene":
                return self._require_scene(entity_id)
            case "chapter":
                return self._require_chapter(entity_id)
            case "setting":
                return self._require_setting(entity_id)
            case "canon_entry":
                return self._require_canon_entry(entity_id)
            case _:
                raise BookHierarchyValidationError(
                    "invalid_entity_type",
                    "Entity type is not supported.",
                    details={"entity_type": entity_type},
                )

    def _resolve_proposal_without_commit(self, book_id: str, proposal_id: str, *, status: str, decision_reason: str):
        proposal = self.get_proposal(book_id, proposal_id)
        if proposal.status == status:
            return proposal
        if proposal.status == "approved":
            raise BookHierarchyValidationError(
                "proposal_already_approved",
                "Approved proposals cannot be changed.",
                details={"proposal_id": proposal_id, "status": proposal.status},
            )
        source_type, source_id = self._proposal_source(proposal)
        current_head_fingerprint = proposal.current_head_fingerprint
        source = self.repository.get_entity(source_type, source_id)
        if source is not None:
            current_head_fingerprint = self._fingerprint_entity(source_type, source)
        return self.repository.update_proposal(
            proposal_id=proposal.proposal_id,
            status=status,
            payload=proposal.payload,
            current_head_fingerprint=current_head_fingerprint,
            decision_reason=decision_reason,
        )

    def _approve_structural_proposal(self, book_id: str, proposal):
        payload = deepcopy(proposal.payload)
        applied_entity_ids = [str(item) for item in payload.get("applied_entity_ids", [])]
        if applied_entity_ids:
            return payload, "applied"
        child_type = str(payload["child_type"])
        parent_id = str(payload["parent_id"])
        created_ids: list[str] = []
        for child in payload.get("proposed_children", []):
            normalized_child = self._normalize_child_payload(dict(child))
            match child_type:
                case "plot":
                    created = self.create_plot(book_id, parent_id, title=normalized_child["title"], body=normalized_child["body"], metadata=normalized_child["metadata"])
                    created_ids.append(created.plot_id)
                case "event":
                    created = self.create_event(book_id, parent_id, title=normalized_child["title"], body=normalized_child["body"], metadata=normalized_child["metadata"])
                    created_ids.append(created.event_id)
                case "scene":
                    created = self.create_scene(book_id, parent_id, title=normalized_child["title"], body=normalized_child["body"], metadata=normalized_child["metadata"])
                    created_ids.append(created.scene_id)
                case "chapter":
                    created = self.create_chapter(book_id, parent_id, title=normalized_child["title"], body=normalized_child["body"], metadata=normalized_child["metadata"])
                    created_ids.append(created.chapter_id)
                case _:
                    raise BookHierarchyValidationError(
                        "invalid_proposal_payload",
                        "Structural proposal target type is not supported.",
                        details={"proposal_id": proposal.proposal_id, "child_type": child_type},
                    )
        payload["applied_entity_ids"] = created_ids
        return payload, "applied"

    def _approve_canon_proposal(self, book_id: str, proposal):
        payload = deepcopy(proposal.payload)
        applied_canon_id = payload.get("applied_canon_id")
        if isinstance(applied_canon_id, str) and applied_canon_id:
            return payload, "duplicate_existing" if payload.get("duplicate_detected") else "applied"
        candidate = self._normalize_child_payload(dict(payload.get("candidate", {})))
        candidate_fingerprint = str(payload.get("candidate_fingerprint") or self._fingerprint_canon_candidate(candidate))
        duplicate_canon_id = self._find_duplicate_canon_entry(book_id, candidate_fingerprint)
        if duplicate_canon_id is not None:
            payload["duplicate_canon_id"] = duplicate_canon_id
            payload["duplicate_detected"] = True
            payload["applied_canon_id"] = duplicate_canon_id
            return payload, "duplicate_existing"
        canon = self.create_canon_entry(book_id, title=candidate["title"], body=candidate["body"], metadata=candidate["metadata"])
        payload["duplicate_detected"] = False
        payload["duplicate_canon_id"] = None
        payload["applied_canon_id"] = canon.canon_id
        return payload, "applied"

    def _approve_chapter_edit_proposal(self, book_id: str, proposal):
        payload = deepcopy(proposal.payload)
        applied_chapter_version = payload.get("applied_chapter_version")
        if isinstance(applied_chapter_version, int) and applied_chapter_version > 0:
            return payload, "applied"
        chapter_id = str(payload.get("chapter_id") or "")
        proposed_update = self._normalize_child_payload(dict(payload.get("proposed_update") or {}))
        updated = self.update_chapter(
            book_id,
            chapter_id,
            expected_version=int(proposal.base_version or 0),
            title=proposed_update["title"],
            body=proposed_update["body"],
            metadata=proposed_update["metadata"],
        )
        payload["applied_chapter_version"] = int(updated.version)
        return payload, "applied"

    def _proposal_source(self, proposal) -> tuple[str, str]:
        payload = proposal.payload
        if payload.get("kind") == "structural_children":
            return str(payload["parent_type"]), str(payload["parent_id"])
        if payload.get("kind") == "canon_candidate":
            return str(payload["source_type"]), str(payload["source_id"])
        if payload.get("kind") == "chapter_edit":
            return "chapter", str(payload["chapter_id"])
        raise BookHierarchyValidationError(
            "invalid_proposal_payload",
            "Proposal payload kind is not supported.",
            details={"proposal_id": proposal.proposal_id},
        )

    def _validate_structural_target(self, *, parent_type: str, child_type: str) -> None:
        expected_child_type = self._STRUCTURAL_CHILD_TYPES.get(parent_type)
        if expected_child_type == child_type:
            return
        raise BookHierarchyValidationError(
            "invalid_proposal_target",
            "Structural proposal target does not match the hierarchy.",
            details={"parent_type": parent_type, "child_type": child_type, "expected_child_type": expected_child_type},
        )

    @staticmethod
    def _normalize_child_payload(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": str(payload.get("title", "")),
            "body": str(payload.get("body", "")),
            "metadata": dict(payload.get("metadata", {})),
        }

    def _fingerprint_entity(self, entity_type: str, entity: Any) -> str:
        return canonical_fingerprint(
            {
                "entity_type": entity_type,
                "entity_id": self._entity_id(entity_type, entity),
                "version": int(entity.version),
                "snapshot": {
                    "title": str(entity.title),
                    "body": str(entity.body),
                    "metadata": dict(entity.metadata),
                },
            }
        )

    def _fingerprint_canon_candidate(self, candidate: dict[str, Any]) -> str:
        return canonical_fingerprint(candidate)

    def _find_duplicate_canon_entry(self, book_id: str, candidate_fingerprint: str) -> str | None:
        for entry in self.repository.list_canon_entries(book_id=book_id):
            if self._fingerprint_canon_candidate(
                {"title": entry.title, "body": entry.body, "metadata": dict(entry.metadata)}
            ) == candidate_fingerprint:
                return entry.canon_id
        return None

    @staticmethod
    def _entity_id(entity_type: str, entity: Any) -> str:
        match entity_type:
            case "outline":
                return str(entity.outline_id)
            case "plot":
                return str(entity.plot_id)
            case "event":
                return str(entity.event_id)
            case "scene":
                return str(entity.scene_id)
            case "chapter":
                return str(entity.chapter_id)
            case "setting":
                return str(entity.setting_id)
            case "canon_entry":
                return str(entity.canon_id)
            case _:
                raise BookHierarchyValidationError(
                    "invalid_entity_type",
                    "Entity type is not supported.",
                    details={"entity_type": entity_type},
                )

    def _stale_proposal_error(self, proposal, *, current_version: int | None):
        details = {
            "proposal_id": proposal.proposal_id,
            "base_version": proposal.base_version,
            "base_fingerprint": proposal.base_fingerprint,
            "current_head_fingerprint": proposal.current_head_fingerprint,
        }
        if current_version is not None:
            details["current_version"] = current_version
        return BookHierarchyConflictError(
            "stale_proposal_base",
            "The proposal base no longer matches the current head.",
            details=details,
        )

    def _update_versioned_entity(self, *, entity_type: str, entity_id: str, expected_version: int, invalidation_reason: str, update_operation):
        self.repository.ensure_baseline_revision(entity_type=entity_type, entity_id=entity_id)
        changed = update_operation()
        if changed == 0:
            current = self._require_entity(entity_type, entity_id)
            raise BookHierarchyVersionMismatchError(
                "version_mismatch",
                "The record was modified by another write and must be reloaded.",
                details={"entity_id": entity_id, "expected_version": expected_version, "current_version": current.version},
            )
        self.repository.create_revision(entity_type=entity_type, entity_id=entity_id, parent_revision_number=None)
        updated = self._require_entity(entity_type, entity_id)
        self._mark_index_stale(updated.book_id, reason=invalidation_reason)
        return updated

    def _update_current_state_entity(self, *, entity_type: str, entity_id: str, expected_version: int, invalidation_reason: str, update_operation):
        changed = update_operation()
        if changed == 0:
            current = self._require_entity(entity_type, entity_id)
            raise BookHierarchyVersionMismatchError(
                "version_mismatch",
                "The record was modified by another write and must be reloaded.",
                details={"entity_id": entity_id, "expected_version": expected_version, "current_version": current.version},
            )
        updated = self._require_entity(entity_type, entity_id)
        self._mark_index_stale(updated.book_id, reason=invalidation_reason)
        return updated

    def _mark_index_stale(self, book_id: str, *, reason: str):
        if self._index_invalidation_suspensions > 0:
            return None
        source = self._build_index_source(book_id)
        current = self.repository.get_index_state(book_id)
        next_generation = 1 if current is None else current.generation + 1
        details = self._merged_index_details(current)
        details["reason"] = reason
        details["active_generation"] = None
        details["source_summary"] = self._index_source_summary(source["payload"])
        return self.repository.upsert_index_state(
            book_id=book_id,
            generation=next_generation,
            status="stale",
            source_fingerprint=source["source_fingerprint"],
            details=details,
        )

    def _build_index_source(self, book_id: str) -> dict[str, Any]:
        payload = {
            "book_id": book_id,
            "canon_entries": [self._serialize_canon(entry) for entry in self.repository.list_canon_entries(book_id=book_id)],
            "current_heads": {
                "outlines": [self._serialize_outline(item) for item in self.repository.list_outlines(book_id=book_id)],
                "plots": [self._serialize_plot(item) for item in self._list_all_plots(book_id)],
                "events": [self._serialize_event(item) for item in self.repository.list_events(book_id=book_id)],
                "scenes": [self._serialize_scene(item) for item in self.repository.list_scenes(book_id=book_id)],
                "chapters": [self._serialize_chapter(item) for item in self.repository.list_chapters(book_id=book_id)],
                "settings": [self._serialize_setting(item) for item in self.repository.list_settings(book_id=book_id)],
            },
        }
        return {"payload": payload, "source_fingerprint": canonical_fingerprint(payload)}

    def _list_all_plots(self, book_id: str) -> list[Any]:
        plots: list[Any] = []
        for outline in self.repository.list_outlines(book_id=book_id):
            plots.extend(self.repository.list_plots(book_id=book_id, outline_id=outline.outline_id))
        return plots

    @staticmethod
    def _merged_index_details(state: Any) -> dict[str, Any]:
        if state is None:
            return {}
        return deepcopy(dict(state.details))

    @staticmethod
    def _index_source_summary(source: dict[str, Any]) -> dict[str, Any]:
        current_heads = dict(source.get("current_heads", {}))
        return {
            "canon_entries": len(list(source.get("canon_entries", []))),
            "current_heads": {key: len(list(value)) for key, value in current_heads.items()},
        }

    @staticmethod
    def _serialize_outline(item: Any) -> dict[str, Any]:
        return {
            "outline_id": item.outline_id,
            "title": item.title,
            "body": item.body,
            "metadata": dict(item.metadata),
            "position": item.position,
            "version": item.version,
        }

    @staticmethod
    def _serialize_plot(item: Any) -> dict[str, Any]:
        return {
            "plot_id": item.plot_id,
            "outline_id": item.outline_id,
            "title": item.title,
            "body": item.body,
            "metadata": dict(item.metadata),
            "position": item.position,
            "version": item.version,
        }

    @staticmethod
    def _serialize_event(item: Any) -> dict[str, Any]:
        return {
            "event_id": item.event_id,
            "plot_id": item.plot_id,
            "title": item.title,
            "body": item.body,
            "metadata": dict(item.metadata),
            "position": item.position,
            "version": item.version,
        }

    @staticmethod
    def _serialize_scene(item: Any) -> dict[str, Any]:
        return {
            "scene_id": item.scene_id,
            "event_id": item.event_id,
            "title": item.title,
            "body": item.body,
            "metadata": dict(item.metadata),
            "position": item.position,
            "version": item.version,
        }

    @staticmethod
    def _serialize_chapter(item: Any) -> dict[str, Any]:
        return {
            "chapter_id": item.chapter_id,
            "scene_id": item.scene_id,
            "title": item.title,
            "body": item.body,
            "metadata": dict(item.metadata),
            "position": item.position,
            "version": item.version,
        }

    @staticmethod
    def _serialize_setting(item: Any) -> dict[str, Any]:
        return {
            "setting_id": item.setting_id,
            "title": item.title,
            "body": item.body,
            "metadata": dict(item.metadata),
            "position": item.position,
            "version": item.version,
        }

    @staticmethod
    def _serialize_canon(item: Any) -> dict[str, Any]:
        return {
            "canon_id": item.canon_id,
            "title": item.title,
            "body": item.body,
            "metadata": dict(item.metadata),
            "position": item.position,
            "version": item.version,
        }

    @contextmanager
    def _suspend_index_invalidation(self):
        self._index_invalidation_suspensions += 1
        try:
            yield
        finally:
            self._index_invalidation_suspensions -= 1

    @staticmethod
    def _validate_same_book(book_id: str, actual_book_id: str, *, entity_type: str, entity_id: str) -> None:
        if book_id == actual_book_id:
            return
        raise BookHierarchyValidationError(
            "invalid_parent",
            "Parent record does not belong to the requested book root.",
            details={"book_id": book_id, "entity_type": entity_type, "entity_id": entity_id, "actual_book_id": actual_book_id},
        )
