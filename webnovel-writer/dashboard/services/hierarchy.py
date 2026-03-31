# pyright: reportMissingImports=false, reportImplicitRelativeImport=false

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, cast

from core.book_hierarchy import BookHierarchyNotFoundError, BookHierarchyService


class HierarchyApiServiceError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        error_code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details


class HierarchyApiService:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.service = BookHierarchyService(self.project_root)

    def create_book(self, *, title: str, synopsis: str = "") -> dict[str, Any]:
        return self._serialize(self.service.create_book_root(title=title, synopsis=synopsis))

    def get_workspace(self) -> dict[str, Any]:
        book = self.service.repository.get_active_book_root(str(self.project_root))
        if book is None:
            raise BookHierarchyNotFoundError(
                "book_root_not_found",
                "Book root was not found.",
                details={"project_root": str(self.project_root)},
            )
        book_id = str(book.book_id)
        outlines = self.service.repository.list_outlines(book_id=book_id)
        plots = []
        for outline in outlines:
            plots.extend(self.service.repository.list_plots(book_id=book_id, outline_id=str(outline.outline_id)))
        snapshot = self.service.get_book_snapshot(book_id)
        return {
            "book": self._serialize(book),
            "outlines": self._serialize(outlines),
            "plots": self._serialize(plots),
            "events": self._serialize(self.service.repository.list_events(book_id=book_id)),
            "scenes": self._serialize(self.service.repository.list_scenes(book_id=book_id)),
            "chapters": self._serialize(self.service.repository.list_chapters(book_id=book_id)),
            "settings": self._serialize(snapshot["settings"]),
            "canon_entries": self._serialize(snapshot["canon_entries"]),
            "proposals": self._serialize(snapshot["proposals"]),
            "index_state": self._serialize(snapshot["index_state"]),
        }

    def create_entity(
        self,
        book_id: str,
        entity_type: str,
        *,
        parent_id: str | None,
        title: str,
        body: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = dict(metadata or {})
        match entity_type:
            case "outline":
                return self._serialize(self.service.create_outline(book_id, title=title, body=body, metadata=payload))
            case "plot":
                return self._serialize(self.service.create_plot(book_id, self._require_parent_id(parent_id, entity_type), title=title, body=body, metadata=payload))
            case "event":
                return self._serialize(self.service.create_event(book_id, self._require_parent_id(parent_id, entity_type), title=title, body=body, metadata=payload))
            case "scene":
                return self._serialize(self.service.create_scene(book_id, self._require_parent_id(parent_id, entity_type), title=title, body=body, metadata=payload))
            case "chapter":
                return self._serialize(self.service.create_chapter(book_id, self._require_parent_id(parent_id, entity_type), title=title, body=body, metadata=payload))
            case "setting":
                return self._serialize(self.service.create_setting(book_id, title=title, body=body, metadata=payload))
            case "canon_entry":
                return self._serialize(self.service.create_canon_entry(book_id, title=title, body=body, metadata=payload))
            case _:
                raise HierarchyApiServiceError(
                    status_code=400,
                    error_code="invalid_entity_type",
                    message="Entity type is not supported.",
                    details={"entity_type": entity_type},
                )

    def get_entity(self, book_id: str, entity_type: str, entity_id: str) -> dict[str, Any]:
        entity = self._lookup_entity(book_id, entity_type, entity_id)
        if entity is None or str(getattr(entity, "book_id", "")) != book_id:
            raise BookHierarchyNotFoundError(
                "entity_not_found",
                "Hierarchy entity was not found.",
                details={"book_id": book_id, "entity_type": entity_type, "entity_id": entity_id},
            )
        return self._serialize(entity)

    def update_entity(
        self,
        book_id: str,
        entity_type: str,
        entity_id: str,
        *,
        expected_version: int,
        title: str | None = None,
        body: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        match entity_type:
            case "outline":
                entity = self.service.update_outline(book_id, entity_id, expected_version=expected_version, title=title, body=body, metadata=metadata)
            case "plot":
                entity = self.service.update_plot(book_id, entity_id, expected_version=expected_version, title=title, body=body, metadata=metadata)
            case "event":
                entity = self.service.update_event(book_id, entity_id, expected_version=expected_version, title=title, body=body, metadata=metadata)
            case "scene":
                entity = self.service.update_scene(book_id, entity_id, expected_version=expected_version, title=title, body=body, metadata=metadata)
            case "chapter":
                entity = self.service.update_chapter(book_id, entity_id, expected_version=expected_version, title=title, body=body, metadata=metadata)
            case "setting":
                entity = self.service.update_setting(book_id, entity_id, expected_version=expected_version, title=title, body=body, metadata=metadata)
            case "canon_entry":
                entity = self.service.update_canon_entry(book_id, entity_id, expected_version=expected_version, title=title, body=body, metadata=metadata)
            case _:
                raise HierarchyApiServiceError(
                    status_code=400,
                    error_code="invalid_entity_type",
                    message="Entity type is not supported.",
                    details={"entity_type": entity_type},
                )
        return self._serialize(entity)

    def delete_entity(self, book_id: str, entity_type: str, entity_id: str) -> None:
        if entity_type != "plot":
            raise HierarchyApiServiceError(
                status_code=400,
                error_code="unsupported_delete_target",
                message="Delete is not supported for this hierarchy entity type.",
                details={"entity_type": entity_type},
            )
        self.service.delete_plot(book_id, entity_id)

    def reorder_plots(self, book_id: str, outline_id: str, ordered_ids: list[str]) -> list[dict[str, Any]]:
        self.service.reorder_plots(book_id, outline_id, ordered_ids)
        return [self._serialize(item) for item in self.service.list_plots(book_id, outline_id)]

    def preview_proposal(self, book_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        kind = str(payload.get("kind") or "")
        if kind == "structural_children":
            proposal = self.service.create_structural_proposal(
                book_id,
                parent_type=str(payload.get("parent_type") or ""),
                parent_id=str(payload.get("parent_id") or ""),
                child_type=str(payload.get("child_type") or ""),
                proposal_type=str(payload.get("proposal_type") or ""),
                proposed_children=[dict(item) for item in payload.get("proposed_children", [])],
            )
            return self._serialize(proposal)
        if kind == "canon_candidate":
            proposal = self.service.create_canon_extraction_proposal(
                book_id,
                source_type=str(payload.get("source_type") or ""),
                source_id=str(payload.get("source_id") or ""),
                title=str(payload.get("title") or ""),
                body=str(payload.get("body") or ""),
                metadata=dict(payload.get("metadata") or {}),
                proposal_type=str(payload.get("proposal_type") or "canon_extract"),
            )
            return self._serialize(proposal)
        if kind == "chapter_edit":
            proposal = self.service.create_chapter_edit_proposal(
                book_id,
                chapter_id=str(payload.get("chapter_id") or ""),
                summary=str(payload.get("summary") or ""),
                proposed_update=dict(payload.get("proposed_update") or {}),
                proposal_type=str(payload.get("proposal_type") or "chapter_edit"),
            )
            return self._serialize(proposal)
        raise HierarchyApiServiceError(
            status_code=400,
            error_code="invalid_proposal_kind",
            message="Proposal kind is not supported.",
            details={"kind": kind},
        )

    def get_proposal(self, book_id: str, proposal_id: str) -> dict[str, Any]:
        return self._serialize(self.service.get_proposal(book_id, proposal_id))

    def confirm_proposal(self, book_id: str, proposal_id: str) -> dict[str, Any]:
        return self._serialize(self.service.approve_proposal(book_id, proposal_id))

    def reject_proposal(self, book_id: str, proposal_id: str) -> dict[str, Any]:
        return self._serialize(self.service.reject_proposal(book_id, proposal_id))

    def list_revisions(self, book_id: str, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
        self.get_entity(book_id, entity_type, entity_id)
        return [self._serialize(item) for item in self.service.list_revisions(entity_type, entity_id)]

    def diff_revisions(self, book_id: str, entity_type: str, entity_id: str, *, from_revision: int, to_revision: int) -> dict[str, Any]:
        self.get_entity(book_id, entity_type, entity_id)
        return {"diff": self.service.diff_revisions(entity_type, entity_id, from_revision=from_revision, to_revision=to_revision)}

    def rollback_revision(
        self,
        book_id: str,
        entity_type: str,
        entity_id: str,
        *,
        target_revision: int,
        expected_version: int,
    ) -> dict[str, Any]:
        return self._serialize(
            self.service.rollback_to_revision(
                book_id,
                entity_type,
                entity_id,
                target_revision=target_revision,
                expected_version=expected_version,
            )
        )

    def mark_index_stale(self, book_id: str, *, reason: str) -> dict[str, Any]:
        return self._serialize(self.service.mark_index_stale(book_id, reason=reason))

    def rebuild_index(self, book_id: str) -> dict[str, Any]:
        return self._serialize(self.service.rebuild_index(book_id))

    def _lookup_entity(self, book_id: str, entity_type: str, entity_id: str):
        if entity_type == "canon_entry":
            for entry in self.service.repository.list_canon_entries(book_id=book_id):
                if entry.canon_id == entity_id:
                    return entry
            return None
        return self.service.repository.get_entity(entity_type, entity_id)

    @staticmethod
    def _require_parent_id(parent_id: str | None, entity_type: str) -> str:
        if parent_id:
            return parent_id
        raise HierarchyApiServiceError(
            status_code=400,
            error_code="parent_id_required",
            message="parent_id is required for this hierarchy entity type.",
            details={"entity_type": entity_type},
        )

    @staticmethod
    def _serialize(value: Any) -> Any:
        if is_dataclass(value):
            return asdict(cast(Any, value))
        if isinstance(value, list):
            return [HierarchyApiService._serialize(item) for item in value]
        if isinstance(value, dict):
            return {key: HierarchyApiService._serialize(item) for key, item in value.items()}
        return value
