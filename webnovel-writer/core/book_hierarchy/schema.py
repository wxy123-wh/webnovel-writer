from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS book_roots (
        book_id TEXT PRIMARY KEY,
        project_root TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        synopsis TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'archived')),
        version INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_book_roots_single_active_per_project ON book_roots(project_root) WHERE status = 'active'",
    """
    CREATE TABLE IF NOT EXISTS outlines (
        outline_id TEXT PRIMARY KEY,
        book_id TEXT NOT NULL REFERENCES book_roots(book_id) ON DELETE RESTRICT,
        title TEXT NOT NULL DEFAULT '',
        body TEXT NOT NULL DEFAULT '',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        position INTEGER NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_outlines_book_position ON outlines(book_id, position, outline_id)",
    """
    CREATE TABLE IF NOT EXISTS plots (
        plot_id TEXT PRIMARY KEY,
        book_id TEXT NOT NULL REFERENCES book_roots(book_id) ON DELETE RESTRICT,
        outline_id TEXT NOT NULL REFERENCES outlines(outline_id) ON DELETE RESTRICT,
        title TEXT NOT NULL DEFAULT '',
        body TEXT NOT NULL DEFAULT '',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        position INTEGER NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_plots_parent_position ON plots(outline_id, position, plot_id)",
    """
    CREATE TABLE IF NOT EXISTS events (
        event_id TEXT PRIMARY KEY,
        book_id TEXT NOT NULL REFERENCES book_roots(book_id) ON DELETE RESTRICT,
        plot_id TEXT NOT NULL REFERENCES plots(plot_id) ON DELETE RESTRICT,
        title TEXT NOT NULL DEFAULT '',
        body TEXT NOT NULL DEFAULT '',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        position INTEGER NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_events_parent_position ON events(plot_id, position, event_id)",
    """
    CREATE TABLE IF NOT EXISTS scenes (
        scene_id TEXT PRIMARY KEY,
        book_id TEXT NOT NULL REFERENCES book_roots(book_id) ON DELETE RESTRICT,
        event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE RESTRICT,
        title TEXT NOT NULL DEFAULT '',
        body TEXT NOT NULL DEFAULT '',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        position INTEGER NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_scenes_parent_position ON scenes(event_id, position, scene_id)",
    """
    CREATE TABLE IF NOT EXISTS chapters (
        chapter_id TEXT PRIMARY KEY,
        book_id TEXT NOT NULL REFERENCES book_roots(book_id) ON DELETE RESTRICT,
        scene_id TEXT NOT NULL REFERENCES scenes(scene_id) ON DELETE RESTRICT,
        title TEXT NOT NULL DEFAULT '',
        body TEXT NOT NULL DEFAULT '',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        position INTEGER NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_chapters_parent_position ON chapters(scene_id, position, chapter_id)",
    """
    CREATE TABLE IF NOT EXISTS settings (
        setting_id TEXT PRIMARY KEY,
        book_id TEXT NOT NULL REFERENCES book_roots(book_id) ON DELETE RESTRICT,
        title TEXT NOT NULL DEFAULT '',
        body TEXT NOT NULL DEFAULT '',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        position INTEGER NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_settings_book_position ON settings(book_id, position, setting_id)",
    """
    CREATE TABLE IF NOT EXISTS canon_entries (
        canon_id TEXT PRIMARY KEY,
        book_id TEXT NOT NULL REFERENCES book_roots(book_id) ON DELETE RESTRICT,
        title TEXT NOT NULL DEFAULT '',
        body TEXT NOT NULL DEFAULT '',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        position INTEGER NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_canon_book_position ON canon_entries(book_id, position, canon_id)",
    """
    CREATE TABLE IF NOT EXISTS hierarchy_proposals (
        proposal_id TEXT PRIMARY KEY,
        book_id TEXT NOT NULL REFERENCES book_roots(book_id) ON DELETE RESTRICT,
        proposal_type TEXT NOT NULL,
        target_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected', 'cancelled', 'stale')),
        payload_json TEXT NOT NULL DEFAULT '{}',
        base_version INTEGER,
        base_fingerprint TEXT NOT NULL DEFAULT '',
        current_head_fingerprint TEXT NOT NULL DEFAULT '',
        decision_reason TEXT NOT NULL DEFAULT '',
        version INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_proposals_book_created ON hierarchy_proposals(book_id, created_at, proposal_id)",
    """
    CREATE TABLE IF NOT EXISTS index_states (
        index_state_id TEXT PRIMARY KEY,
        book_id TEXT NOT NULL UNIQUE REFERENCES book_roots(book_id) ON DELETE RESTRICT,
        generation INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'stale' CHECK(status IN ('fresh', 'stale', 'building', 'failed')),
        source_fingerprint TEXT NOT NULL DEFAULT '',
        details_json TEXT NOT NULL DEFAULT '{}',
        version INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS hierarchy_revisions (
        revision_id TEXT PRIMARY KEY,
        entity_type TEXT NOT NULL CHECK(entity_type IN ('outline', 'plot', 'chapter', 'setting')),
        entity_id TEXT NOT NULL,
        book_id TEXT NOT NULL REFERENCES book_roots(book_id) ON DELETE RESTRICT,
        revision_number INTEGER NOT NULL,
        entity_version INTEGER NOT NULL,
        parent_revision_number INTEGER,
        snapshot_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        UNIQUE(entity_type, entity_id, revision_number)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_hierarchy_revisions_entity ON hierarchy_revisions(entity_type, entity_id, revision_number)",
)


def get_hierarchy_db_path(project_root: Path) -> Path:
    return project_root / ".webnovel" / "hierarchy.db"


def ensure_schema(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path))
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        _ensure_hierarchy_proposals_columns(connection)
        connection.commit()
    finally:
        connection.close()


def _ensure_hierarchy_proposals_columns(connection: sqlite3.Connection) -> None:
    columns = {
        str(row[1]): row
        for row in connection.execute("PRAGMA table_info(hierarchy_proposals)").fetchall()
    }
    if not columns:
        return
    if "base_fingerprint" not in columns:
        connection.execute("ALTER TABLE hierarchy_proposals ADD COLUMN base_fingerprint TEXT NOT NULL DEFAULT ''")
    if "current_head_fingerprint" not in columns:
        connection.execute("ALTER TABLE hierarchy_proposals ADD COLUMN current_head_fingerprint TEXT NOT NULL DEFAULT ''")
    if "decision_reason" not in columns:
        connection.execute("ALTER TABLE hierarchy_proposals ADD COLUMN decision_reason TEXT NOT NULL DEFAULT ''")
    create_sql_row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'hierarchy_proposals'"
    ).fetchone()
    create_sql = "" if create_sql_row is None or create_sql_row[0] is None else str(create_sql_row[0])
    if "'stale'" in create_sql and "base_fingerprint" in create_sql and "current_head_fingerprint" in create_sql and "decision_reason" in create_sql:
        return
    connection.execute("ALTER TABLE hierarchy_proposals RENAME TO hierarchy_proposals_legacy")
    connection.execute(SCHEMA_STATEMENTS[16])
    connection.execute(
        "INSERT INTO hierarchy_proposals (proposal_id, book_id, proposal_type, target_type, status, payload_json, base_version, base_fingerprint, current_head_fingerprint, decision_reason, version, created_at, updated_at) "
        "SELECT proposal_id, book_id, proposal_type, target_type, CASE WHEN status = 'pending' THEN status ELSE status END, payload_json, base_version, COALESCE(base_fingerprint, ''), COALESCE(current_head_fingerprint, COALESCE(base_fingerprint, '')), COALESCE(decision_reason, ''), version, created_at, updated_at FROM hierarchy_proposals_legacy"
    )
    connection.execute("DROP TABLE hierarchy_proposals_legacy")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_proposals_book_created ON hierarchy_proposals(book_id, created_at, proposal_id)")
