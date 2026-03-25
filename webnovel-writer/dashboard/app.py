"""
Webnovel Dashboard - FastAPI 主应用

提供现有只读接口 + OpenSpec 冻结写接口骨架；所有文件读取经过 path_guard 防穿越校验。
"""

import asyncio
import json
import sqlite3
from contextlib import asynccontextmanager, closing
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .models.common import ApiErrorResponse
from .path_guard import safe_resolve
from .routers import (
    edit_assist_router,
    outlines_router,
    runtime_router,
    settings_dictionary_router,
    settings_files_router,
    skills_router,
)
from .watcher import FileWatcher

# ---------------------------------------------------------------------------
# 全局状态
# ---------------------------------------------------------------------------
_project_root: Path | None = None
_watcher = FileWatcher()

STATIC_DIR = Path(__file__).parent / "frontend" / "dist"

READ_ERROR_RESPONSES = {
    404: {"model": ApiErrorResponse, "description": "Resource not found."},
    409: {"model": ApiErrorResponse, "description": "Conflict."},
    500: {"model": ApiErrorResponse, "description": "Internal server error."},
}


def _default_error_code(status_code: int) -> str:
    return {
        400: "bad_request",
        403: "forbidden",
        404: "resource_not_found",
        409: "resource_conflict",
        500: "internal_error",
    }.get(status_code, f"http_{status_code}")


def _api_error_payload(
    *,
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    payload = ApiErrorResponse(
        error_code=error_code,
        message=message,
        details=details,
        request_id=request_id,
    )
    return payload.model_dump()


def _normalize_api_error(status_code: int, detail: Any, request_id: str | None) -> dict[str, Any]:
    if hasattr(detail, "model_dump"):
        detail = detail.model_dump()

    if isinstance(detail, dict):
        error_code = str(detail.get("error_code") or _default_error_code(status_code))
        message = str(detail.get("message") or detail.get("detail") or "请求处理失败")
        details = detail.get("details")
        if details is None:
            extras = {
                key: value
                for key, value in detail.items()
                if key not in {"error_code", "message", "details", "request_id"}
            }
            details = extras or None
        req_id = detail.get("request_id") or request_id
        return _api_error_payload(
            error_code=error_code,
            message=message,
            details=details,
            request_id=req_id,
        )

    if isinstance(detail, str):
        return _api_error_payload(
            error_code=_default_error_code(status_code),
            message=detail,
            details=None,
            request_id=request_id,
        )

    if detail is None:
        return _api_error_payload(
            error_code=_default_error_code(status_code),
            message="请求处理失败",
            details=None,
            request_id=request_id,
        )

    return _api_error_payload(
        error_code=_default_error_code(status_code),
        message="请求处理失败",
        details={"detail": detail},
        request_id=request_id,
    )


def _raise_api_error(
    status_code: int,
    *,
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=_api_error_payload(error_code=error_code, message=message, details=details),
    )


def _is_missing_table_error(exc: sqlite3.OperationalError) -> bool:
    return "no such table" in str(exc).lower()


def _get_project_root() -> Path:
    if _project_root is None:
        _raise_api_error(
            500,
            error_code="runtime_project_root_unavailable",
            message="项目根目录未配置",
        )
    return _project_root


def _webnovel_dir() -> Path:
    return _get_project_root() / ".webnovel"


# ---------------------------------------------------------------------------
# 应用工厂
# ---------------------------------------------------------------------------

def create_app(project_root: str | Path | None = None) -> FastAPI:
    global _project_root

    if project_root:
        _project_root = Path(project_root).resolve()

    @asynccontextmanager
    async def _lifespan(_: FastAPI):
        webnovel = _webnovel_dir()
        if webnovel.is_dir():
            _watcher.start(webnovel, asyncio.get_running_loop())
        try:
            yield
        finally:
            _watcher.stop()

    app = FastAPI(title="Webnovel Dashboard", version="0.1.0", lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def _api_http_exception_handler(request: Request, exc: HTTPException):
        if not request.url.path.startswith("/api/"):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

        payload = _normalize_api_error(
            status_code=exc.status_code,
            detail=exc.detail,
            request_id=request.headers.get("x-request-id"),
        )
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(Exception)
    async def _api_unexpected_exception_handler(request: Request, exc: Exception):
        if not request.url.path.startswith("/api/"):
            return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

        if isinstance(exc, sqlite3.OperationalError):
            if _is_missing_table_error(exc):
                payload = _api_error_payload(
                    error_code="db_table_missing",
                    message="数据库缺少必需数据表",
                    details={"error": str(exc)},
                    request_id=request.headers.get("x-request-id"),
                )
            else:
                payload = _api_error_payload(
                    error_code="db_operational_error",
                    message="数据库操作失败",
                    details={"error": str(exc)},
                    request_id=request.headers.get("x-request-id"),
                )
        else:
            payload = _api_error_payload(
                error_code="internal_error",
                message="服务器内部错误",
                details={"error": str(exc)},
                request_id=request.headers.get("x-request-id"),
            )

        return JSONResponse(status_code=500, content=payload)

    # OpenSpec 冻结新增能力路由骨架（T02）
    app.include_router(runtime_router)
    app.include_router(skills_router)
    app.include_router(settings_files_router)
    app.include_router(settings_dictionary_router)
    app.include_router(outlines_router)
    app.include_router(edit_assist_router)

    # ===========================================================
    # API：项目元信息
    # ===========================================================

    @app.get("/api/project/info")
    def project_info():
        """返回 state.json 完整内容（只读）。"""
        state_path = _webnovel_dir() / "state.json"
        if not state_path.is_file():
            raise HTTPException(404, "state.json 不存在")
        return json.loads(state_path.read_text(encoding="utf-8"))

    # ===========================================================
    # API：实体数据库（index.db 只读查询）
    # ===========================================================

    def _get_db() -> sqlite3.Connection:
        db_path = _webnovel_dir() / "index.db"
        if not db_path.is_file():
            _raise_api_error(
                404,
                error_code="index_db_not_found",
                message="index.db 不存在",
                details={"path": str(db_path)},
            )
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _handle_db_error(exc: sqlite3.OperationalError, table: str | None = None) -> None:
        if _is_missing_table_error(exc):
            _raise_api_error(
                500,
                error_code="db_table_missing",
                message="数据库缺少必需数据表",
                details={"table": table, "error": str(exc)},
            )
        _raise_api_error(
            500,
            error_code="db_query_failed",
            message="数据库查询失败",
            details={"table": table, "error": str(exc)},
        )

    def _query_rows_strict(
        conn: sqlite3.Connection,
        query: str,
        params: tuple = (),
        *,
        table: str | None = None,
    ) -> list[dict]:
        try:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError as exc:
            _handle_db_error(exc, table=table)

    def _query_scalar_strict(
        conn: sqlite3.Connection,
        query: str,
        params: tuple = (),
        *,
        table: str | None = None,
    ) -> Any:
        try:
            row = conn.execute(query, params).fetchone()
        except sqlite3.OperationalError as exc:
            _handle_db_error(exc, table=table)
        if not row:
            return None
        return row[0]

    def _content_file_count(root: Path) -> int:
        total = 0
        for folder_name in ("正文", "大纲", "设定集"):
            folder = root / folder_name
            if not folder.is_dir():
                continue
            total += sum(1 for item in folder.rglob("*") if item.is_file())
        return total

    def _fetchall_safe(conn: sqlite3.Connection, query: str, params: tuple = ()) -> list[dict]:
        """执行只读查询；若目标表不存在（旧库），返回空列表。"""
        try:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                return []
            _raise_api_error(
                500,
                error_code="db_query_failed",
                message="数据库查询失败",
                details={"error": str(exc)},
            )

    @app.get("/api/entities")
    def list_entities(
        entity_type: Optional[str] = Query(None, alias="type"),
        include_archived: bool = False,
    ):
        """列出所有实体（可按类型过滤）。"""
        with closing(_get_db()) as conn:
            q = "SELECT * FROM entities"
            params: list = []
            clauses: list[str] = []
            if entity_type:
                clauses.append("type = ?")
                params.append(entity_type)
            if not include_archived:
                clauses.append("is_archived = 0")
            if clauses:
                q += " WHERE " + " AND ".join(clauses)
            q += " ORDER BY last_appearance DESC"
            rows = conn.execute(q, params).fetchall()
            return [dict(r) for r in rows]

    @app.get("/api/entities/{entity_id}")
    def get_entity(entity_id: str):
        with closing(_get_db()) as conn:
            row = conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()
            if not row:
                _raise_api_error(
                    404,
                    error_code="entity_not_found",
                    message="实体不存在",
                    details={"entity_id": entity_id},
                )
            return dict(row)

    @app.get("/api/relationships")
    def list_relationships(entity: Optional[str] = None, limit: int = 200):
        with closing(_get_db()) as conn:
            if entity:
                rows = conn.execute(
                    "SELECT * FROM relationships WHERE from_entity = ? OR to_entity = ? ORDER BY chapter DESC LIMIT ?",
                    (entity, entity, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM relationships ORDER BY chapter DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    @app.get("/api/relationship-events")
    def list_relationship_events(
        entity: Optional[str] = None,
        from_chapter: Optional[int] = None,
        to_chapter: Optional[int] = None,
        limit: int = 200,
    ):
        with closing(_get_db()) as conn:
            q = "SELECT * FROM relationship_events"
            params: list = []
            clauses: list[str] = []
            if entity:
                clauses.append("(from_entity = ? OR to_entity = ?)")
                params.extend([entity, entity])
            if from_chapter is not None:
                clauses.append("chapter >= ?")
                params.append(from_chapter)
            if to_chapter is not None:
                clauses.append("chapter <= ?")
                params.append(to_chapter)
            if clauses:
                q += " WHERE " + " AND ".join(clauses)
            q += " ORDER BY chapter DESC, id DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(q, params).fetchall()
            return [dict(r) for r in rows]

    @app.get("/api/chapters")
    def list_chapters():
        with closing(_get_db()) as conn:
            rows = conn.execute("SELECT * FROM chapters ORDER BY chapter ASC").fetchall()
            return [dict(r) for r in rows]

    @app.get("/api/scenes")
    def list_scenes(chapter: Optional[int] = None, limit: int = 500):
        with closing(_get_db()) as conn:
            if chapter is not None:
                rows = conn.execute(
                    "SELECT * FROM scenes WHERE chapter = ? ORDER BY scene_index ASC", (chapter,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM scenes ORDER BY chapter ASC, scene_index ASC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    @app.get("/api/reading-power")
    def list_reading_power(limit: int = 50):
        with closing(_get_db()) as conn:
            rows = conn.execute(
                "SELECT * FROM chapter_reading_power ORDER BY chapter DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    @app.get("/api/review-metrics")
    def list_review_metrics(limit: int = 20):
        with closing(_get_db()) as conn:
            rows = conn.execute(
                "SELECT * FROM review_metrics ORDER BY end_chapter DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    @app.get("/api/state-changes")
    def list_state_changes(entity: Optional[str] = None, limit: int = 100):
        with closing(_get_db()) as conn:
            if entity:
                rows = conn.execute(
                    "SELECT * FROM state_changes WHERE entity_id = ? ORDER BY chapter DESC LIMIT ?",
                    (entity, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM state_changes ORDER BY chapter DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    @app.get("/api/aliases")
    def list_aliases(entity: Optional[str] = None):
        with closing(_get_db()) as conn:
            if entity:
                rows = conn.execute(
                    "SELECT * FROM aliases WHERE entity_id = ?", (entity,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM aliases").fetchall()
            return [dict(r) for r in rows]

    @app.get("/api/dashboard/overview", responses=READ_ERROR_RESPONSES)
    def dashboard_overview():
        with closing(_get_db()) as conn:
            entity_count = int(
                _query_scalar_strict(
                    conn,
                    "SELECT COUNT(*) FROM entities WHERE is_archived = 0",
                    table="entities",
                )
                or 0
            )
            relationship_count = int(
                _query_scalar_strict(conn, "SELECT COUNT(*) FROM relationships", table="relationships")
                or 0
            )
            chapter_count = int(_query_scalar_strict(conn, "SELECT COUNT(*) FROM chapters", table="chapters") or 0)

            reading_base = _query_rows_strict(
                conn,
                """
                SELECT
                    COUNT(*) AS total_rows,
                    MAX(chapter) AS latest_chapter,
                    SUM(CASE WHEN is_transition = 1 THEN 1 ELSE 0 END) AS transition_chapters,
                    AVG(debt_balance) AS avg_debt_balance
                FROM chapter_reading_power
                """,
                table="chapter_reading_power",
            )
            reading_agg = reading_base[0] if reading_base else {}

            hook_rows = _query_rows_strict(
                conn,
                """
                SELECT COALESCE(NULLIF(LOWER(hook_strength), ''), 'unknown') AS hook_strength, COUNT(*) AS count
                FROM chapter_reading_power
                GROUP BY COALESCE(NULLIF(LOWER(hook_strength), ''), 'unknown')
                """,
                table="chapter_reading_power",
            )

        hook_strength_distribution: dict[str, int] = {
            "strong": 0,
            "medium": 0,
            "weak": 0,
            "unknown": 0,
        }
        for item in hook_rows:
            key = item.get("hook_strength") or "unknown"
            hook_strength_distribution[key] = int(item.get("count") or 0)

        avg_debt_balance = reading_agg.get("avg_debt_balance")
        if avg_debt_balance is not None:
            avg_debt_balance = round(float(avg_debt_balance), 4)

        return {
            "status": "ok",
            "counts": {
                "entities": entity_count,
                "relationships": relationship_count,
                "chapters": chapter_count,
                "files": _content_file_count(_get_project_root()),
            },
            "reading_power": {
                "total_rows": int(reading_agg.get("total_rows") or 0),
                "latest_chapter": reading_agg.get("latest_chapter"),
                "transition_chapters": int(reading_agg.get("transition_chapters") or 0),
                "avg_debt_balance": avg_debt_balance,
                "hook_strength_distribution": hook_strength_distribution,
            },
        }

    @app.get("/api/graph", responses=READ_ERROR_RESPONSES)
    def graph(include_archived: bool = False, limit: int = Query(1000, ge=1, le=5000)):
        with closing(_get_db()) as conn:
            entity_query = (
                "SELECT id, canonical_name, type, tier, is_archived, is_protagonist, first_appearance, last_appearance "
                "FROM entities"
            )
            params: tuple = ()
            if not include_archived:
                entity_query += " WHERE is_archived = 0"
            entity_query += " ORDER BY last_appearance DESC, id ASC"

            entity_rows = _query_rows_strict(conn, entity_query, params, table="entities")
            edges_raw = _query_rows_strict(
                conn,
                """
                SELECT id, from_entity, to_entity, type, description, chapter
                FROM relationships
                ORDER BY chapter DESC, id DESC
                LIMIT ?
                """,
                (limit,),
                table="relationships",
            )

        node_by_id: dict[str, dict] = {}
        for row in entity_rows:
            node_id = row["id"]
            node_by_id[node_id] = {
                "id": node_id,
                "label": row.get("canonical_name") or node_id,
                "name": row.get("canonical_name") or node_id,
                "type": row.get("type"),
                "tier": row.get("tier"),
                "is_archived": bool(row.get("is_archived", 0)),
                "is_protagonist": bool(row.get("is_protagonist", 0)),
                "first_appearance": row.get("first_appearance"),
                "last_appearance": row.get("last_appearance"),
            }

        edges: list[dict] = []
        for row in edges_raw:
            source = row.get("from_entity")
            target = row.get("to_entity")
            if not source or not target:
                continue
            if not include_archived and (source not in node_by_id or target not in node_by_id):
                continue
            edges.append(
                {
                    "id": row.get("id"),
                    "source": source,
                    "target": target,
                    "type": row.get("type"),
                    "label": row.get("type"),
                    "description": row.get("description"),
                    "chapter": row.get("chapter"),
                }
            )

        if include_archived:
            missing_node_ids = {
                endpoint
                for edge in edges
                for endpoint in (edge["source"], edge["target"])
                if endpoint not in node_by_id
            }
            for node_id in sorted(missing_node_ids):
                node_by_id[node_id] = {
                    "id": node_id,
                    "label": node_id,
                    "name": node_id,
                    "type": "unknown",
                    "tier": None,
                    "is_archived": False,
                    "is_protagonist": False,
                    "first_appearance": None,
                    "last_appearance": None,
                }

        nodes = list(node_by_id.values())

        return {
            "status": "ok",
            "nodes": nodes,
            "edges": edges,
            "meta": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "include_archived": include_archived,
            },
        }

    # ===========================================================
    # API：扩展表（v5.3+ / v5.4+）
    # ===========================================================

    @app.get("/api/overrides")
    def list_overrides(status: Optional[str] = None, limit: int = 100):
        with closing(_get_db()) as conn:
            if status:
                return _fetchall_safe(
                    conn,
                    "SELECT * FROM override_contracts WHERE status = ? ORDER BY chapter DESC LIMIT ?",
                    (status, limit),
                )
            return _fetchall_safe(
                conn,
                "SELECT * FROM override_contracts ORDER BY chapter DESC LIMIT ?",
                (limit,),
            )

    @app.get("/api/debts")
    def list_debts(status: Optional[str] = None, limit: int = 100):
        with closing(_get_db()) as conn:
            if status:
                return _fetchall_safe(
                    conn,
                    "SELECT * FROM chase_debt WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                    (status, limit),
                )
            return _fetchall_safe(
                conn,
                "SELECT * FROM chase_debt ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )

    @app.get("/api/debt-events")
    def list_debt_events(debt_id: Optional[int] = None, limit: int = 200):
        with closing(_get_db()) as conn:
            if debt_id is not None:
                return _fetchall_safe(
                    conn,
                    "SELECT * FROM debt_events WHERE debt_id = ? ORDER BY chapter DESC, id DESC LIMIT ?",
                    (debt_id, limit),
                )
            return _fetchall_safe(
                conn,
                "SELECT * FROM debt_events ORDER BY chapter DESC, id DESC LIMIT ?",
                (limit,),
            )

    @app.get("/api/invalid-facts")
    def list_invalid_facts(status: Optional[str] = None, limit: int = 100):
        with closing(_get_db()) as conn:
            if status:
                return _fetchall_safe(
                    conn,
                    "SELECT * FROM invalid_facts WHERE status = ? ORDER BY marked_at DESC LIMIT ?",
                    (status, limit),
                )
            return _fetchall_safe(
                conn,
                "SELECT * FROM invalid_facts ORDER BY marked_at DESC LIMIT ?",
                (limit,),
            )

    @app.get("/api/rag-queries")
    def list_rag_queries(query_type: Optional[str] = None, limit: int = 100):
        with closing(_get_db()) as conn:
            if query_type:
                return _fetchall_safe(
                    conn,
                    "SELECT * FROM rag_query_log WHERE query_type = ? ORDER BY created_at DESC LIMIT ?",
                    (query_type, limit),
                )
            return _fetchall_safe(
                conn,
                "SELECT * FROM rag_query_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )

    @app.get("/api/tool-stats")
    def list_tool_stats(tool_name: Optional[str] = None, limit: int = 200):
        with closing(_get_db()) as conn:
            if tool_name:
                return _fetchall_safe(
                    conn,
                    "SELECT * FROM tool_call_stats WHERE tool_name = ? ORDER BY created_at DESC LIMIT ?",
                    (tool_name, limit),
                )
            return _fetchall_safe(
                conn,
                "SELECT * FROM tool_call_stats ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )

    @app.get("/api/checklist-scores")
    def list_checklist_scores(limit: int = 100):
        with closing(_get_db()) as conn:
            return _fetchall_safe(
                conn,
                "SELECT * FROM writing_checklist_scores ORDER BY chapter DESC LIMIT ?",
                (limit,),
            )

    # ===========================================================
    # API：文档浏览（正文/大纲/设定集 —— 只读）
    # ===========================================================

    @app.get("/api/files/tree")
    def file_tree():
        """列出 正文/、大纲/、设定集/ 三个目录的树结构。"""
        root = _get_project_root()
        result = {}
        for folder_name in ("正文", "大纲", "设定集"):
            folder = root / folder_name
            if not folder.is_dir():
                result[folder_name] = []
                continue
            result[folder_name] = _walk_tree(folder, root)
        return result

    @app.get("/api/files/read")
    def file_read(path: str):
        """只读读取一个文件内容（限 正文/大纲/设定集 目录）。"""
        root = _get_project_root()
        resolved = safe_resolve(root, path)

        # 二次限制：只允许三大目录
        allowed_parents = [root / n for n in ("正文", "大纲", "设定集")]
        if not any(_is_child(resolved, p) for p in allowed_parents):
            _raise_api_error(
                403,
                error_code="file_access_forbidden",
                message="仅允许读取 正文/大纲/设定集 目录下的文件",
                details={"path": path},
            )

        if not resolved.is_file():
            _raise_api_error(
                404,
                error_code="file_not_found",
                message="文件不存在",
                details={"path": path},
            )

        # 文本文件直接读；其他情况返回占位信息
        try:
            content = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = "[二进制文件，无法预览]"

        return {"path": path, "content": content}

    # ===========================================================
    # SSE：实时变更推送
    # ===========================================================

    @app.get("/api/events")
    async def sse():
        """Server-Sent Events 端点，推送 .webnovel/ 下的文件变更。"""
        q = _watcher.subscribe()

        async def _gen():
            try:
                while True:
                    msg = await q.get()
                    yield f"data: {msg}\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                _watcher.unsubscribe(q)

        return StreamingResponse(_gen(), media_type="text/event-stream")

    # ===========================================================
    # 前端静态文件托管
    # ===========================================================

    if STATIC_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

        @app.get("/{full_path:path}")
        def serve_spa(full_path: str):
            """SPA fallback：任何非 /api 路径都返回 index.html。"""
            index = STATIC_DIR / "index.html"
            if index.is_file():
                return FileResponse(str(index))
            raise HTTPException(404, "前端尚未构建")
    else:
        @app.get("/")
        def no_frontend():
            return HTMLResponse(
                "<h2>Webnovel Dashboard API is running</h2>"
                "<p>前端尚未构建。请先在 <code>dashboard/frontend</code> 目录执行 <code>npm run build</code>。</p>"
                '<p>API 文档：<a href="/docs">/docs</a></p>'
            )

    return app


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _walk_tree(folder: Path, root: Path) -> list[dict]:
    items = []
    for child in sorted(folder.iterdir()):
        rel = str(child.relative_to(root)).replace("\\", "/")
        if child.is_dir():
            items.append({"name": child.name, "type": "dir", "path": rel, "children": _walk_tree(child, root)})
        else:
            items.append({"name": child.name, "type": "file", "path": rel, "size": child.stat().st_size})
    return items


def _is_child(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False
