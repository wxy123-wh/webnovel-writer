from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BookHierarchyError(Exception):
    error_code: str
    message: str
    status_code: int
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


class BookHierarchyConflictError(BookHierarchyError):
    def __init__(self, error_code: str, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(error_code=error_code, message=message, status_code=409, details=details or {})


class BookHierarchyValidationError(BookHierarchyError):
    def __init__(self, error_code: str, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(error_code=error_code, message=message, status_code=400, details=details or {})


class BookHierarchyGuardedDeleteError(BookHierarchyError):
    def __init__(self, error_code: str, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(error_code=error_code, message=message, status_code=409, details=details or {})


class BookHierarchyVersionMismatchError(BookHierarchyError):
    def __init__(self, error_code: str, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(error_code=error_code, message=message, status_code=409, details=details or {})


class BookHierarchyNotFoundError(BookHierarchyError):
    def __init__(self, error_code: str, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(error_code=error_code, message=message, status_code=404, details=details or {})


@dataclass(slots=True)
class BookRoot:
    book_id: str
    project_root: str
    title: str
    synopsis: str
    status: str
    version: int
    created_at: str
    updated_at: str


@dataclass(slots=True)
class Outline:
    outline_id: str
    book_id: str
    title: str
    body: str
    metadata: dict[str, Any]
    position: int
    version: int
    created_at: str
    updated_at: str


@dataclass(slots=True)
class Plot:
    plot_id: str
    book_id: str
    outline_id: str
    title: str
    body: str
    metadata: dict[str, Any]
    position: int
    version: int
    created_at: str
    updated_at: str


@dataclass(slots=True)
class Event:
    event_id: str
    book_id: str
    plot_id: str
    title: str
    body: str
    metadata: dict[str, Any]
    position: int
    version: int
    created_at: str
    updated_at: str


@dataclass(slots=True)
class Scene:
    scene_id: str
    book_id: str
    event_id: str
    title: str
    body: str
    metadata: dict[str, Any]
    position: int
    version: int
    created_at: str
    updated_at: str


@dataclass(slots=True)
class Chapter:
    chapter_id: str
    book_id: str
    scene_id: str
    title: str
    body: str
    metadata: dict[str, Any]
    position: int
    version: int
    created_at: str
    updated_at: str


@dataclass(slots=True)
class Setting:
    setting_id: str
    book_id: str
    title: str
    body: str
    metadata: dict[str, Any]
    position: int
    version: int
    created_at: str
    updated_at: str


@dataclass(slots=True)
class CanonEntry:
    canon_id: str
    book_id: str
    title: str
    body: str
    metadata: dict[str, Any]
    position: int
    version: int
    created_at: str
    updated_at: str


@dataclass(slots=True)
class Proposal:
    proposal_id: str
    book_id: str
    proposal_type: str
    target_type: str
    status: str
    payload: dict[str, Any]
    base_version: int | None
    base_fingerprint: str
    current_head_fingerprint: str
    decision_reason: str
    version: int
    created_at: str
    updated_at: str


@dataclass(slots=True)
class IndexState:
    index_state_id: str
    book_id: str
    generation: int
    status: str
    source_fingerprint: str
    details: dict[str, Any]
    version: int
    created_at: str
    updated_at: str


@dataclass(slots=True)
class IndexRebuild:
    book_id: str
    generation: int
    source_fingerprint: str
    source: dict[str, Any]
    state: IndexState


@dataclass(slots=True)
class HierarchyRevision:
    revision_id: str
    entity_type: str
    entity_id: str
    book_id: str
    revision_number: int
    entity_version: int
    parent_revision_number: int | None
    snapshot: dict[str, Any]
    created_at: str
