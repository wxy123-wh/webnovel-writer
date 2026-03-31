from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from difflib import unified_diff
from pathlib import Path
from typing import Any, Callable, TypeVar

from .models import (
    BookRoot,
    CanonEntry,
    Chapter,
    Event,
    HierarchyRevision,
    IndexState,
    Outline,
    Plot,
    Proposal,
    Scene,
    Setting,
)
from .schema import ensure_schema

T = TypeVar("T")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _decode_json(text: str | None) -> dict[str, Any]:
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _encode_json(payload: dict[str, Any] | None) -> str:
    return json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)


def canonical_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class BookHierarchyRepository:
    _REVISIONED_ENTITY_TYPES = {"outline", "plot", "chapter", "setting"}
    _ENTITY_TABLES = {
        "outline": ("outlines", "outline_id"),
        "plot": ("plots", "plot_id"),
        "event": ("events", "event_id"),
        "scene": ("scenes", "scene_id"),
        "chapter": ("chapters", "chapter_id"),
        "setting": ("settings", "setting_id"),
    }
    _CHILD_COUNT_QUERIES = {
        "book_roots": "SELECT (SELECT COUNT(*) FROM outlines WHERE book_id = ?) + (SELECT COUNT(*) FROM settings WHERE book_id = ?) + (SELECT COUNT(*) FROM canon_entries WHERE book_id = ?) + (SELECT COUNT(*) FROM hierarchy_proposals WHERE book_id = ?) + (SELECT COUNT(*) FROM index_states WHERE book_id = ?) AS child_count",
        "outlines": "SELECT COUNT(*) AS child_count FROM plots WHERE outline_id = ?",
        "plots": "SELECT COUNT(*) AS child_count FROM events WHERE plot_id = ?",
        "events": "SELECT COUNT(*) AS child_count FROM scenes WHERE event_id = ?",
        "scenes": "SELECT COUNT(*) AS child_count FROM chapters WHERE scene_id = ?",
    }

    def __init__(self, db_path: Path):
        self.db_path = db_path
        ensure_schema(db_path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _fetchone(connection: sqlite3.Connection, query: str, params: tuple[Any, ...]) -> sqlite3.Row | None:
        return connection.execute(query, params).fetchone()

    @staticmethod
    def _fetchall(connection: sqlite3.Connection, query: str, params: tuple[Any, ...]) -> list[sqlite3.Row]:
        return connection.execute(query, params).fetchall()

    @staticmethod
    def _require_row(row: sqlite3.Row | None, *, context: str) -> sqlite3.Row:
        if row is None:
            raise LookupError(context)
        return row

    @staticmethod
    def _book_from_row(row: sqlite3.Row) -> BookRoot:
        return BookRoot(
            book_id=str(row["book_id"]),
            project_root=str(row["project_root"]),
            title=str(row["title"]),
            synopsis=str(row["synopsis"]),
            status=str(row["status"]),
            version=int(row["version"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _outline_from_row(row: sqlite3.Row) -> Outline:
        return Outline(
            outline_id=str(row["outline_id"]),
            book_id=str(row["book_id"]),
            title=str(row["title"]),
            body=str(row["body"]),
            metadata=_decode_json(str(row["metadata_json"])),
            position=int(row["position"]),
            version=int(row["version"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _plot_from_row(row: sqlite3.Row) -> Plot:
        return Plot(
            plot_id=str(row["plot_id"]),
            book_id=str(row["book_id"]),
            outline_id=str(row["outline_id"]),
            title=str(row["title"]),
            body=str(row["body"]),
            metadata=_decode_json(str(row["metadata_json"])),
            position=int(row["position"]),
            version=int(row["version"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> Event:
        return Event(
            event_id=str(row["event_id"]),
            book_id=str(row["book_id"]),
            plot_id=str(row["plot_id"]),
            title=str(row["title"]),
            body=str(row["body"]),
            metadata=_decode_json(str(row["metadata_json"])),
            position=int(row["position"]),
            version=int(row["version"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _scene_from_row(row: sqlite3.Row) -> Scene:
        return Scene(
            scene_id=str(row["scene_id"]),
            book_id=str(row["book_id"]),
            event_id=str(row["event_id"]),
            title=str(row["title"]),
            body=str(row["body"]),
            metadata=_decode_json(str(row["metadata_json"])),
            position=int(row["position"]),
            version=int(row["version"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _chapter_from_row(row: sqlite3.Row) -> Chapter:
        return Chapter(
            chapter_id=str(row["chapter_id"]),
            book_id=str(row["book_id"]),
            scene_id=str(row["scene_id"]),
            title=str(row["title"]),
            body=str(row["body"]),
            metadata=_decode_json(str(row["metadata_json"])),
            position=int(row["position"]),
            version=int(row["version"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _setting_from_row(row: sqlite3.Row) -> Setting:
        return Setting(
            setting_id=str(row["setting_id"]),
            book_id=str(row["book_id"]),
            title=str(row["title"]),
            body=str(row["body"]),
            metadata=_decode_json(str(row["metadata_json"])),
            position=int(row["position"]),
            version=int(row["version"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _canon_from_row(row: sqlite3.Row) -> CanonEntry:
        return CanonEntry(
            canon_id=str(row["canon_id"]),
            book_id=str(row["book_id"]),
            title=str(row["title"]),
            body=str(row["body"]),
            metadata=_decode_json(str(row["metadata_json"])),
            position=int(row["position"]),
            version=int(row["version"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _proposal_from_row(row: sqlite3.Row) -> Proposal:
        return Proposal(
            proposal_id=str(row["proposal_id"]),
            book_id=str(row["book_id"]),
            proposal_type=str(row["proposal_type"]),
            target_type=str(row["target_type"]),
            status=str(row["status"]),
            payload=_decode_json(str(row["payload_json"])),
            base_version=None if row["base_version"] is None else int(row["base_version"]),
            base_fingerprint=str(row["base_fingerprint"]),
            current_head_fingerprint=str(row["current_head_fingerprint"]),
            decision_reason=str(row["decision_reason"]),
            version=int(row["version"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _index_state_from_row(row: sqlite3.Row) -> IndexState:
        return IndexState(
            index_state_id=str(row["index_state_id"]),
            book_id=str(row["book_id"]),
            generation=int(row["generation"]),
            status=str(row["status"]),
            source_fingerprint=str(row["source_fingerprint"]),
            details=_decode_json(str(row["details_json"])),
            version=int(row["version"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _revision_from_row(row: sqlite3.Row) -> HierarchyRevision:
        return HierarchyRevision(
            revision_id=str(row["revision_id"]),
            entity_type=str(row["entity_type"]),
            entity_id=str(row["entity_id"]),
            book_id=str(row["book_id"]),
            revision_number=int(row["revision_number"]),
            entity_version=int(row["entity_version"]),
            parent_revision_number=None if row["parent_revision_number"] is None else int(row["parent_revision_number"]),
            snapshot=_decode_json(str(row["snapshot_json"])),
            created_at=str(row["created_at"]),
        )

    def create_book_root(self, *, project_root: str, title: str, synopsis: str = "", status: str = "active") -> BookRoot:
        timestamp = utc_now_iso()
        book_id = generate_id("book")
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO book_roots (book_id, project_root, title, synopsis, status, version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (book_id, project_root, title, synopsis, status, timestamp, timestamp),
            )
            connection.commit()
            row = self._fetchone(
                connection,
                "SELECT book_id, project_root, title, synopsis, status, version, created_at, updated_at FROM book_roots WHERE book_id = ?",
                (book_id,),
            )
        return self._book_from_row(self._require_row(row, context=f"book root '{book_id}' was not created"))

    def get_book_root(self, book_id: str) -> BookRoot | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                "SELECT book_id, project_root, title, synopsis, status, version, created_at, updated_at FROM book_roots WHERE book_id = ?",
                (book_id,),
            )
        return None if row is None else self._book_from_row(row)

    def get_active_book_root(self, project_root: str) -> BookRoot | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                "SELECT book_id, project_root, title, synopsis, status, version, created_at, updated_at FROM book_roots WHERE project_root = ? AND status = 'active'",
                (project_root,),
            )
        return None if row is None else self._book_from_row(row)

    def create_outline(self, *, book_id: str, title: str, body: str = "", metadata: dict[str, Any] | None = None) -> Outline:
        return self._create_ordered_record(
            table="outlines",
            id_column="outline_id",
            id_value=generate_id("outline"),
            parent_column="book_id",
            parent_value=book_id,
            extra_columns={},
            row_loader=self._outline_from_row,
            title=title,
            body=body,
            metadata=metadata,
        )

    def create_plot(self, *, book_id: str, outline_id: str, title: str, body: str = "", metadata: dict[str, Any] | None = None) -> Plot:
        return self._create_ordered_record(
            table="plots",
            id_column="plot_id",
            id_value=generate_id("plot"),
            parent_column="outline_id",
            parent_value=outline_id,
            extra_columns={"book_id": book_id},
            row_loader=self._plot_from_row,
            title=title,
            body=body,
            metadata=metadata,
        )

    def create_event(self, *, book_id: str, plot_id: str, title: str, body: str = "", metadata: dict[str, Any] | None = None) -> Event:
        return self._create_ordered_record(
            table="events",
            id_column="event_id",
            id_value=generate_id("event"),
            parent_column="plot_id",
            parent_value=plot_id,
            extra_columns={"book_id": book_id},
            row_loader=self._event_from_row,
            title=title,
            body=body,
            metadata=metadata,
        )

    def create_scene(self, *, book_id: str, event_id: str, title: str, body: str = "", metadata: dict[str, Any] | None = None) -> Scene:
        return self._create_ordered_record(
            table="scenes",
            id_column="scene_id",
            id_value=generate_id("scene"),
            parent_column="event_id",
            parent_value=event_id,
            extra_columns={"book_id": book_id},
            row_loader=self._scene_from_row,
            title=title,
            body=body,
            metadata=metadata,
        )

    def create_chapter(self, *, book_id: str, scene_id: str, title: str, body: str = "", metadata: dict[str, Any] | None = None) -> Chapter:
        return self._create_ordered_record(
            table="chapters",
            id_column="chapter_id",
            id_value=generate_id("chapter"),
            parent_column="scene_id",
            parent_value=scene_id,
            extra_columns={"book_id": book_id},
            row_loader=self._chapter_from_row,
            title=title,
            body=body,
            metadata=metadata,
        )

    def create_setting(self, *, book_id: str, title: str, body: str = "", metadata: dict[str, Any] | None = None) -> Setting:
        return self._create_ordered_record(
            table="settings",
            id_column="setting_id",
            id_value=generate_id("setting"),
            parent_column="book_id",
            parent_value=book_id,
            extra_columns={},
            row_loader=self._setting_from_row,
            title=title,
            body=body,
            metadata=metadata,
        )

    def create_canon_entry(self, *, book_id: str, title: str, body: str = "", metadata: dict[str, Any] | None = None) -> CanonEntry:
        return self._create_ordered_record(
            table="canon_entries",
            id_column="canon_id",
            id_value=generate_id("canon"),
            parent_column="book_id",
            parent_value=book_id,
            extra_columns={},
            row_loader=self._canon_from_row,
            title=title,
            body=body,
            metadata=metadata,
        )

    def create_proposal(
        self,
        *,
        book_id: str,
        proposal_type: str,
        target_type: str,
        status: str = "pending",
        payload: dict[str, Any] | None = None,
        base_version: int | None = None,
        base_fingerprint: str = "",
        current_head_fingerprint: str = "",
        decision_reason: str = "",
    ) -> Proposal:
        timestamp = utc_now_iso()
        proposal_id = generate_id("proposal")
        payload_json = _encode_json(payload)
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO hierarchy_proposals (proposal_id, book_id, proposal_type, target_type, status, payload_json, base_version, base_fingerprint, current_head_fingerprint, decision_reason, version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
                (
                    proposal_id,
                    book_id,
                    proposal_type,
                    target_type,
                    status,
                    payload_json,
                    base_version,
                    base_fingerprint,
                    current_head_fingerprint,
                    decision_reason,
                    timestamp,
                    timestamp,
                ),
            )
            connection.commit()
            row = self._fetchone(
                connection,
                "SELECT proposal_id, book_id, proposal_type, target_type, status, payload_json, base_version, base_fingerprint, current_head_fingerprint, decision_reason, version, created_at, updated_at FROM hierarchy_proposals WHERE proposal_id = ?",
                (proposal_id,),
            )
        return self._proposal_from_row(self._require_row(row, context=f"proposal '{proposal_id}' was not created"))

    def get_proposal(self, proposal_id: str) -> Proposal | None:
        return self._get_record(
            query="SELECT proposal_id, book_id, proposal_type, target_type, status, payload_json, base_version, base_fingerprint, current_head_fingerprint, decision_reason, version, created_at, updated_at FROM hierarchy_proposals WHERE proposal_id = ?",
            params=(proposal_id,),
            row_loader=self._proposal_from_row,
        )

    def update_proposal(
        self,
        *,
        proposal_id: str,
        status: str,
        payload: dict[str, Any],
        current_head_fingerprint: str,
        decision_reason: str,
    ) -> Proposal:
        with self._connection() as connection:
            connection.execute(
                "UPDATE hierarchy_proposals SET status = ?, payload_json = ?, current_head_fingerprint = ?, decision_reason = ?, version = version + 1, updated_at = ? WHERE proposal_id = ?",
                (status, _encode_json(payload), current_head_fingerprint, decision_reason, utc_now_iso(), proposal_id),
            )
            connection.commit()
            row = self._fetchone(
                connection,
                "SELECT proposal_id, book_id, proposal_type, target_type, status, payload_json, base_version, base_fingerprint, current_head_fingerprint, decision_reason, version, created_at, updated_at FROM hierarchy_proposals WHERE proposal_id = ?",
                (proposal_id,),
            )
        return self._proposal_from_row(self._require_row(row, context=f"proposal '{proposal_id}' was not updated"))

    def upsert_index_state(
        self,
        *,
        book_id: str,
        generation: int,
        status: str,
        source_fingerprint: str,
        details: dict[str, Any] | None = None,
    ) -> IndexState:
        existing = self.get_index_state(book_id)
        timestamp = utc_now_iso()
        details_json = json.dumps(details or {}, ensure_ascii=False, sort_keys=True)
        with self._connection() as connection:
            if existing is None:
                index_state_id = generate_id("index")
                connection.execute(
                    "INSERT INTO index_states (index_state_id, book_id, generation, status, source_fingerprint, details_json, version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)",
                    (index_state_id, book_id, generation, status, source_fingerprint, details_json, timestamp, timestamp),
                )
            else:
                connection.execute(
                    "UPDATE index_states SET generation = ?, status = ?, source_fingerprint = ?, details_json = ?, version = version + 1, updated_at = ? WHERE book_id = ?",
                    (generation, status, source_fingerprint, details_json, timestamp, book_id),
                )
            connection.commit()
            row = self._fetchone(
                connection,
                "SELECT index_state_id, book_id, generation, status, source_fingerprint, details_json, version, created_at, updated_at FROM index_states WHERE book_id = ?",
                (book_id,),
            )
        return self._index_state_from_row(self._require_row(row, context=f"index state for '{book_id}' was not written"))

    def get_index_state(self, book_id: str) -> IndexState | None:
        with self._connection() as connection:
            row = self._fetchone(
                connection,
                "SELECT index_state_id, book_id, generation, status, source_fingerprint, details_json, version, created_at, updated_at FROM index_states WHERE book_id = ?",
                (book_id,),
            )
        return None if row is None else self._index_state_from_row(row)

    def list_plots(self, *, book_id: str, outline_id: str) -> list[Plot]:
        return self._list_records(
            query="SELECT plot_id, book_id, outline_id, title, body, metadata_json, position, version, created_at, updated_at FROM plots WHERE book_id = ? AND outline_id = ? ORDER BY position ASC, plot_id ASC",
            params=(book_id, outline_id),
            row_loader=self._plot_from_row,
        )

    def list_outlines(self, *, book_id: str) -> list[Outline]:
        return self._list_records(
            query="SELECT outline_id, book_id, title, body, metadata_json, position, version, created_at, updated_at FROM outlines WHERE book_id = ? ORDER BY position ASC, outline_id ASC",
            params=(book_id,),
            row_loader=self._outline_from_row,
        )

    def list_events(self, *, book_id: str) -> list[Event]:
        return self._list_records(
            query="SELECT event_id, book_id, plot_id, title, body, metadata_json, position, version, created_at, updated_at FROM events WHERE book_id = ? ORDER BY plot_id ASC, position ASC, event_id ASC",
            params=(book_id,),
            row_loader=self._event_from_row,
        )

    def list_scenes(self, *, book_id: str) -> list[Scene]:
        return self._list_records(
            query="SELECT scene_id, book_id, event_id, title, body, metadata_json, position, version, created_at, updated_at FROM scenes WHERE book_id = ? ORDER BY event_id ASC, position ASC, scene_id ASC",
            params=(book_id,),
            row_loader=self._scene_from_row,
        )

    def list_chapters(self, *, book_id: str) -> list[Chapter]:
        return self._list_records(
            query="SELECT chapter_id, book_id, scene_id, title, body, metadata_json, position, version, created_at, updated_at FROM chapters WHERE book_id = ? ORDER BY scene_id ASC, position ASC, chapter_id ASC",
            params=(book_id,),
            row_loader=self._chapter_from_row,
        )

    def list_settings(self, *, book_id: str) -> list[Setting]:
        return self._list_records(
            query="SELECT setting_id, book_id, title, body, metadata_json, position, version, created_at, updated_at FROM settings WHERE book_id = ? ORDER BY position ASC, setting_id ASC",
            params=(book_id,),
            row_loader=self._setting_from_row,
        )

    def list_canon_entries(self, *, book_id: str) -> list[CanonEntry]:
        return self._list_records(
            query="SELECT canon_id, book_id, title, body, metadata_json, position, version, created_at, updated_at FROM canon_entries WHERE book_id = ? ORDER BY position ASC, canon_id ASC",
            params=(book_id,),
            row_loader=self._canon_from_row,
        )

    def list_proposals(self, *, book_id: str) -> list[Proposal]:
        return self._list_records(
            query="SELECT proposal_id, book_id, proposal_type, target_type, status, payload_json, base_version, base_fingerprint, current_head_fingerprint, decision_reason, version, created_at, updated_at FROM hierarchy_proposals WHERE book_id = ? ORDER BY created_at ASC, proposal_id ASC",
            params=(book_id,),
            row_loader=self._proposal_from_row,
        )

    def get_outline(self, outline_id: str) -> Outline | None:
        return self._get_record(
            query="SELECT outline_id, book_id, title, body, metadata_json, position, version, created_at, updated_at FROM outlines WHERE outline_id = ?",
            params=(outline_id,),
            row_loader=self._outline_from_row,
        )

    def get_plot(self, plot_id: str) -> Plot | None:
        return self._get_record(
            query="SELECT plot_id, book_id, outline_id, title, body, metadata_json, position, version, created_at, updated_at FROM plots WHERE plot_id = ?",
            params=(plot_id,),
            row_loader=self._plot_from_row,
        )

    def get_event(self, event_id: str) -> Event | None:
        return self._get_record(
            query="SELECT event_id, book_id, plot_id, title, body, metadata_json, position, version, created_at, updated_at FROM events WHERE event_id = ?",
            params=(event_id,),
            row_loader=self._event_from_row,
        )

    def get_scene(self, scene_id: str) -> Scene | None:
        return self._get_record(
            query="SELECT scene_id, book_id, event_id, title, body, metadata_json, position, version, created_at, updated_at FROM scenes WHERE scene_id = ?",
            params=(scene_id,),
            row_loader=self._scene_from_row,
        )

    def get_chapter(self, chapter_id: str) -> Chapter | None:
        return self._get_record(
            query="SELECT chapter_id, book_id, scene_id, title, body, metadata_json, position, version, created_at, updated_at FROM chapters WHERE chapter_id = ?",
            params=(chapter_id,),
            row_loader=self._chapter_from_row,
        )

    def get_setting(self, setting_id: str) -> Setting | None:
        return self._get_record(
            query="SELECT setting_id, book_id, title, body, metadata_json, position, version, created_at, updated_at FROM settings WHERE setting_id = ?",
            params=(setting_id,),
            row_loader=self._setting_from_row,
        )

    def reorder_children(self, *, table: str, id_column: str, parent_column: str, parent_value: str, ordered_ids: list[str]) -> None:
        with self._connection() as connection:
            rows = self._fetchall(
                connection,
                f"SELECT {id_column} FROM {table} WHERE {parent_column} = ? ORDER BY position ASC, {id_column} ASC",
                (parent_value,),
            )
            existing_ids = [str(row[id_column]) for row in rows]
            if sorted(existing_ids) != sorted(ordered_ids):
                raise ValueError("ordered ids must match the persisted sibling set")
            for position, item_id in enumerate(ordered_ids):
                connection.execute(
                    f"UPDATE {table} SET position = ?, version = version + 1, updated_at = ? WHERE {id_column} = ?",
                    (position, utc_now_iso(), item_id),
                )
            connection.commit()

    def update_plot(self, *, plot_id: str, expected_version: int, title: str | None = None, body: str | None = None, metadata: dict[str, Any] | None = None) -> int:
        return self._update_content_record(
            table="plots",
            id_column="plot_id",
            id_value=plot_id,
            expected_version=expected_version,
            title=title,
            body=body,
            metadata=metadata,
        )

    def update_outline(self, *, outline_id: str, expected_version: int, title: str | None = None, body: str | None = None, metadata: dict[str, Any] | None = None) -> int:
        return self._update_content_record(
            table="outlines",
            id_column="outline_id",
            id_value=outline_id,
            expected_version=expected_version,
            title=title,
            body=body,
            metadata=metadata,
        )

    def update_event(self, *, event_id: str, expected_version: int, title: str | None = None, body: str | None = None, metadata: dict[str, Any] | None = None) -> int:
        return self._update_content_record(
            table="events",
            id_column="event_id",
            id_value=event_id,
            expected_version=expected_version,
            title=title,
            body=body,
            metadata=metadata,
        )

    def update_scene(self, *, scene_id: str, expected_version: int, title: str | None = None, body: str | None = None, metadata: dict[str, Any] | None = None) -> int:
        return self._update_content_record(
            table="scenes",
            id_column="scene_id",
            id_value=scene_id,
            expected_version=expected_version,
            title=title,
            body=body,
            metadata=metadata,
        )

    def update_chapter(self, *, chapter_id: str, expected_version: int, title: str | None = None, body: str | None = None, metadata: dict[str, Any] | None = None) -> int:
        return self._update_content_record(
            table="chapters",
            id_column="chapter_id",
            id_value=chapter_id,
            expected_version=expected_version,
            title=title,
            body=body,
            metadata=metadata,
        )

    def update_setting(self, *, setting_id: str, expected_version: int, title: str | None = None, body: str | None = None, metadata: dict[str, Any] | None = None) -> int:
        return self._update_content_record(
            table="settings",
            id_column="setting_id",
            id_value=setting_id,
            expected_version=expected_version,
            title=title,
            body=body,
            metadata=metadata,
        )

    def update_canon_entry(self, *, canon_id: str, expected_version: int, title: str | None = None, body: str | None = None, metadata: dict[str, Any] | None = None) -> int:
        return self._update_content_record(
            table="canon_entries",
            id_column="canon_id",
            id_value=canon_id,
            expected_version=expected_version,
            title=title,
            body=body,
            metadata=metadata,
        )

    def list_revisions(self, *, entity_type: str, entity_id: str) -> list[HierarchyRevision]:
        if entity_type not in self._REVISIONED_ENTITY_TYPES:
            return []
        return self._list_records(
            query="SELECT revision_id, entity_type, entity_id, book_id, revision_number, entity_version, parent_revision_number, snapshot_json, created_at FROM hierarchy_revisions WHERE entity_type = ? AND entity_id = ? ORDER BY revision_number ASC",
            params=(entity_type, entity_id),
            row_loader=self._revision_from_row,
        )

    def get_revision(self, *, entity_type: str, entity_id: str, revision_number: int) -> HierarchyRevision | None:
        if entity_type not in self._REVISIONED_ENTITY_TYPES:
            return None
        return self._get_record(
            query="SELECT revision_id, entity_type, entity_id, book_id, revision_number, entity_version, parent_revision_number, snapshot_json, created_at FROM hierarchy_revisions WHERE entity_type = ? AND entity_id = ? AND revision_number = ?",
            params=(entity_type, entity_id, revision_number),
            row_loader=self._revision_from_row,
        )

    def ensure_baseline_revision(self, *, entity_type: str, entity_id: str) -> list[HierarchyRevision]:
        revisions = self.list_revisions(entity_type=entity_type, entity_id=entity_id)
        if revisions or entity_type not in self._REVISIONED_ENTITY_TYPES:
            return revisions
        record = self.get_entity(entity_type, entity_id)
        if record is None:
            return []
        self.create_revision(entity_type=entity_type, entity_id=entity_id, parent_revision_number=None)
        return self.list_revisions(entity_type=entity_type, entity_id=entity_id)

    def create_revision(self, *, entity_type: str, entity_id: str, parent_revision_number: int | None) -> HierarchyRevision:
        if entity_type not in self._REVISIONED_ENTITY_TYPES:
            raise ValueError(f"unsupported revision entity type: {entity_type}")
        record = self.get_entity(entity_type, entity_id)
        if record is None:
            raise LookupError(f"entity '{entity_type}:{entity_id}' was not found")
        revisions = self.list_revisions(entity_type=entity_type, entity_id=entity_id)
        revision_number = len(revisions) + 1
        revision_id = generate_id("revision")
        snapshot_json = json.dumps(self._entity_snapshot(record), ensure_ascii=False, sort_keys=True, indent=2)
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO hierarchy_revisions (revision_id, entity_type, entity_id, book_id, revision_number, entity_version, parent_revision_number, snapshot_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (revision_id, entity_type, entity_id, record.book_id, revision_number, record.version, parent_revision_number, snapshot_json, utc_now_iso()),
            )
            connection.commit()
            row = self._fetchone(
                connection,
                "SELECT revision_id, entity_type, entity_id, book_id, revision_number, entity_version, parent_revision_number, snapshot_json, created_at FROM hierarchy_revisions WHERE revision_id = ?",
                (revision_id,),
            )
        return self._revision_from_row(self._require_row(row, context=f"revision '{revision_id}' was not created"))

    def diff_revisions(self, *, entity_type: str, entity_id: str, from_revision: int, to_revision: int) -> str:
        previous = self.get_revision(entity_type=entity_type, entity_id=entity_id, revision_number=from_revision)
        current = self.get_revision(entity_type=entity_type, entity_id=entity_id, revision_number=to_revision)
        if previous is None or current is None:
            raise LookupError(f"revision diff '{entity_type}:{entity_id}' could not be resolved")
        previous_text = json.dumps(previous.snapshot, ensure_ascii=False, sort_keys=True, indent=2)
        current_text = json.dumps(current.snapshot, ensure_ascii=False, sort_keys=True, indent=2)
        return "\n".join(
            unified_diff(
                previous_text.splitlines(),
                current_text.splitlines(),
                fromfile=f"{entity_type}:{entity_id}@{from_revision}",
                tofile=f"{entity_type}:{entity_id}@{to_revision}",
                lineterm="",
            )
        )

    def apply_revision_snapshot(self, *, entity_type: str, entity_id: str, expected_version: int, snapshot: dict[str, Any]) -> int:
        table, id_column = self._require_entity_table(entity_type)
        return self._update_content_record(
            table=table,
            id_column=id_column,
            id_value=entity_id,
            expected_version=expected_version,
            title=str(snapshot.get("title", "")),
            body=str(snapshot.get("body", "")),
            metadata=dict(snapshot.get("metadata", {})),
        )

    def get_entity(self, entity_type: str, entity_id: str):
        match entity_type:
            case "outline":
                return self.get_outline(entity_id)
            case "plot":
                return self.get_plot(entity_id)
            case "event":
                return self.get_event(entity_id)
            case "scene":
                return self.get_scene(entity_id)
            case "chapter":
                return self.get_chapter(entity_id)
            case "setting":
                return self.get_setting(entity_id)
            case "canon_entry":
                return self.get_canon_entry(entity_id)
            case _:
                return None

    def get_canon_entry(self, canon_id: str) -> CanonEntry | None:
        return self._get_record(
            query="SELECT canon_id, book_id, title, body, metadata_json, position, version, created_at, updated_at FROM canon_entries WHERE canon_id = ?",
            params=(canon_id,),
            row_loader=self._canon_from_row,
        )

    def delete_record(self, *, table: str, id_column: str, id_value: str) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(f"DELETE FROM {table} WHERE {id_column} = ?", (id_value,))
            connection.commit()
            return cursor.rowcount > 0

    def child_count(self, *, table: str, id_value: str) -> int:
        query = self._CHILD_COUNT_QUERIES.get(table)
        if not query:
            return 0
        with self._connection() as connection:
            if table == "book_roots":
                row = self._fetchone(connection, query, (id_value, id_value, id_value, id_value, id_value))
            else:
                row = self._fetchone(connection, query, (id_value,))
        return 0 if row is None else int(row["child_count"])

    def _create_ordered_record(
        self,
        *,
        table: str,
        id_column: str,
        id_value: str,
        parent_column: str,
        parent_value: str,
        extra_columns: dict[str, str],
        row_loader: Callable[[sqlite3.Row], T],
        title: str,
        body: str,
        metadata: dict[str, Any] | None,
    ) -> T:
        timestamp = utc_now_iso()
        encoded = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
        with self._connection() as connection:
            position_row = self._fetchone(
                connection,
                f"SELECT COALESCE(MAX(position), -1) + 1 AS next_position FROM {table} WHERE {parent_column} = ?",
                (parent_value,),
            )
            position = int(position_row["next_position"]) if position_row is not None else 0
            columns = [id_column, parent_column, *extra_columns.keys(), "title", "body", "metadata_json", "position", "version", "created_at", "updated_at"]
            values: list[Any] = [id_value, parent_value, *extra_columns.values(), title, body, encoded, position, 1, timestamp, timestamp]
            placeholders = ", ".join(["?"] * len(columns))
            connection.execute(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                tuple(values),
            )
            connection.commit()
            row = self._fetchone(connection, f"SELECT * FROM {table} WHERE {id_column} = ?", (id_value,))
        return row_loader(self._require_row(row, context=f"record '{id_value}' was not created in {table}"))

    def _update_content_record(
        self,
        *,
        table: str,
        id_column: str,
        id_value: str,
        expected_version: int,
        title: str | None,
        body: str | None,
        metadata: dict[str, Any] | None,
    ) -> int:
        assignments = ["version = version + 1", "updated_at = ?"]
        params: list[Any] = [utc_now_iso()]
        if title is not None:
            assignments.append("title = ?")
            params.append(title)
        if body is not None:
            assignments.append("body = ?")
            params.append(body)
        if metadata is not None:
            assignments.append("metadata_json = ?")
            params.append(json.dumps(metadata, ensure_ascii=False, sort_keys=True))
        params.extend([id_value, expected_version])
        with self._connection() as connection:
            cursor = connection.execute(
                f"UPDATE {table} SET {', '.join(assignments)} WHERE {id_column} = ? AND version = ?",
                tuple(params),
            )
            connection.commit()
            return cursor.rowcount

    @staticmethod
    def _entity_snapshot(record: Any) -> dict[str, Any]:
        return {
            "title": str(record.title),
            "body": str(record.body),
            "metadata": dict(record.metadata),
        }

    def _require_entity_table(self, entity_type: str) -> tuple[str, str]:
        table = self._ENTITY_TABLES.get(entity_type)
        if table is None:
            raise ValueError(f"unsupported entity type: {entity_type}")
        return table

    def _get_record(self, *, query: str, params: tuple[Any, ...], row_loader: Callable[[sqlite3.Row], T]) -> T | None:
        with self._connection() as connection:
            row = self._fetchone(connection, query, params)
        return None if row is None else row_loader(row)

    def _list_records(self, *, query: str, params: tuple[Any, ...], row_loader: Callable[[sqlite3.Row], T]) -> list[T]:
        with self._connection() as connection:
            rows = self._fetchall(connection, query, params)
        return [row_loader(row) for row in rows]
