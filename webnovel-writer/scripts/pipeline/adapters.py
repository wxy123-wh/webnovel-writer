#!/usr/bin/env python3
# pyright: reportMissingImports=false, reportImplicitRelativeImport=false

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from .models import OutlineTarget


def load_outline_target(project_root: Path, chapter_num: int) -> OutlineTarget:
    try:
        from chapter_outline_loader import load_chapter_outline
        from chapter_paths import extract_chapter_title
    except ImportError:  # pragma: no cover
        from scripts.chapter_outline_loader import load_chapter_outline
        from scripts.chapter_paths import extract_chapter_title

    outline = load_chapter_outline(project_root, chapter_num, max_chars=None)
    if outline.startswith("⚠️"):
        raise ValueError(outline)
    title = extract_chapter_title(project_root, chapter_num) or f"第{chapter_num}章"
    return OutlineTarget(
        chapter_num=chapter_num,
        title=title,
        source_path="大纲",
        content=outline,
    )


def load_context_payload(project_root: Path, chapter_num: int) -> dict[str, Any]:
    try:
        from extract_chapter_context import build_chapter_context_payload
    except ImportError:  # pragma: no cover
        from scripts.extract_chapter_context import build_chapter_context_payload

    try:
        payload = build_chapter_context_payload(project_root, chapter_num)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return {
        "chapter": chapter_num,
        "outline": "",
        "previous_summaries": [],
        "state_summary": "",
        "writing_guidance": {"guidance_items": [], "checklist": []},
        "genre_profile": {},
    }


def refresh_index(project_root: Path) -> dict[str, Any]:
    try:
        from data_modules.incremental_indexer import IncrementalIndexer
        from data_modules.rag_adapter import index_hierarchy_content
    except ImportError:  # pragma: no cover
        from scripts.data_modules.incremental_indexer import IncrementalIndexer
        from scripts.data_modules.rag_adapter import index_hierarchy_content

    file_result = IncrementalIndexer(project_root).index_incremental()
    hierarchy_result = asyncio.run(index_hierarchy_content(project_root))
    return {
        **file_result,
        "file_result": file_result,
        "hierarchy_result": hierarchy_result,
    }
