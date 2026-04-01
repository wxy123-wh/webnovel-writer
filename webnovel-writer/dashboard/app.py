"""
Webnovel Dashboard - FastAPI 主应用

提供当前主线的只读接口；所有文件读取经过 path_guard 防穿越校验。
"""

import asyncio
import base64
import binascii
import json
import re
import secrets
import sqlite3
from contextlib import asynccontextmanager, closing, suppress
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .models.common import ApiErrorResponse
from .models.skills import CreateSkillRequest, SkillDraftRequest, SkillDraftResponse
from .path_guard import safe_resolve
from .routers.chat import router as chat_router
from .routers import hierarchy_router, runtime_router
from .services.runtime import service as runtime_service_module
from .watcher import FileWatcher

# ---------------------------------------------------------------------------
# 全局状态
# ---------------------------------------------------------------------------
# P0-B 修复：移除全局 _project_root，改用 app.state.project_root 传递
# 避免线程不安全和多 worker 时内存不共享问题
_watcher = FileWatcher()

STATIC_DIR = Path(__file__).parent / "frontend" / "dist"
ENV_ASSIGNMENT_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=.*$")
GENERATION_ENV_KEYS = (
    "GENERATION_API_TYPE",
    "GENERATION_BASE_URL",
    "GENERATION_MODEL",
    "GENERATION_API_KEY",
)

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


def _unauthorized_response(request: Request) -> JSONResponse:
    payload = _api_error_payload(
        error_code="unauthorized",
        message="需要有效的 Basic Auth 凭据",
        details=None,
        request_id=request.headers.get("x-request-id"),
    )
    return JSONResponse(
        status_code=401,
        content=payload,
        headers={"WWW-Authenticate": 'Basic realm="Webnovel Dashboard"'},
    )


def _parse_basic_auth_header(header_value: str | None) -> tuple[str, str] | None:
    if not header_value:
        return None
    scheme, _, token = header_value.partition(" ")
    if scheme.lower() != "basic" or not token:
        return None
    try:
        decoded = base64.b64decode(token).decode("utf-8")
    except (ValueError, UnicodeDecodeError, binascii.Error):
        return None
    username, sep, password = decoded.partition(":")
    if not sep:
        return None
    return username, password


def _is_missing_table_error(exc: sqlite3.OperationalError) -> bool:
    return "no such table" in str(exc).lower()


def _get_project_root_from_app(app: "FastAPI") -> Path:
    """P0-B 修复：从 app.state 读取 project_root，保证线程安全。"""
    root = getattr(app.state, "project_root", None)
    if root is None:
        _raise_api_error(
            500,
            error_code="runtime_project_root_unavailable",
            message="项目根目录未配置",
        )
    return root  # type: ignore[return-value]


def _webnovel_dir_from_app(app: "FastAPI") -> Path:
    """P0-B 修复：返回 .webnovel 目录路径，依赖 app.state 而非全局变量。"""
    return _get_project_root_from_app(app) / ".webnovel"


def _resolve_project_root_from_pointer() -> Path | None:
    """P0-B 修复保留：从 `.codex` 目录下的 pointer 文件自动恢复 project_root。

    在 uvicorn --reload 场景下，app.state 会被重置，
    通过此函数可以从持久化的 pointer 文件恢复，无需重启服务或重新传参。
    """
    cwd = Path.cwd()
    for dirname in (".codex",):
        pointer = cwd / dirname / ".webnovel-current-project"
        if not pointer.is_file():
            continue
        try:
            target_str = pointer.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if not target_str:
            continue
        target = Path(target_str).expanduser()
        if not target.is_absolute():
            target = cwd / target
        with suppress(OSError):
            target = target.resolve()
        if target.is_dir() and (target / ".webnovel" / "state.json").is_file():
            return target
    return None


def _resolve_workspace_root_for_pointer(project_root: Path) -> Path:
    for candidate in (project_root, *project_root.parents):
        if (candidate / ".codex").is_dir():
            return candidate
    if project_root.parent != project_root:
        return project_root.parent
    return project_root


def _write_project_root_pointer(project_root: Path) -> None:
    pointer_paths = {
        Path.cwd() / ".codex" / ".webnovel-current-project",
        _resolve_workspace_root_for_pointer(project_root) / ".codex" / ".webnovel-current-project",
    }
    for pointer in pointer_paths:
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text(str(project_root), encoding="utf-8")


def _copy_generation_settings(source_root: Path | None, target_root: Path) -> None:
    if source_root is None or source_root == target_root:
        return

    settings = runtime_service_module._resolve_generation_settings(project_root=source_root)
    updates = {
        key: _normalize_optional_env_value(settings.get(key))
        for key in GENERATION_ENV_KEYS
    }
    if any(value is not None for value in updates.values()):
        _write_project_env_values(target_root, updates)


def _rebind_project_root(app: FastAPI, project_root: Path) -> None:
    normalized_root = project_root.resolve()
    app.state.project_root = normalized_root
    _write_project_root_pointer(normalized_root)

    _watcher.stop()
    webnovel_path = normalized_root / ".webnovel"
    if webnovel_path.is_dir():
        _watcher.start(webnovel_path, asyncio.get_running_loop())


def create_app(
    project_root: str | Path | None = None,
    allowed_origins: list[str] | None = None,
    basic_auth_credentials: tuple[str, str] | None = None,
) -> FastAPI:
    """创建 FastAPI 应用。

    Args:
        project_root: 项目根目录路径，优先级高于 pointer 文件。
        allowed_origins: P0-A 修复 —— 允许的 CORS 来源列表。
            生产环境应传入具体来源如 ["http://localhost:8765"]，
            None 时默认为 localhost 本地地址。
    """
    # P0-A 修复：CORS 来源不再硬编码为 "*"
    _allowed_origins: list[str] = allowed_origins if allowed_origins is not None else [
        "http://localhost:8765",
        "http://127.0.0.1:8765",
    ]

    # P0-B 修复：将 project_root 存入局部变量，后续通过 app.state 传递
    _initial_root: Path | None = Path(project_root).resolve() if project_root else None

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        # P0-B 修复：优先使用启动时传入的路径，热重载后尝试从 pointer 文件恢复
        if app.state.project_root is None:
            recovered = _resolve_project_root_from_pointer()
            if recovered is not None:
                app.state.project_root = recovered
        webnovel_path = app.state.project_root / ".webnovel" if app.state.project_root else None
        if webnovel_path and webnovel_path.is_dir():
            _watcher.start(webnovel_path, asyncio.get_running_loop())
        try:
            yield
        finally:
            _watcher.stop()

    app = FastAPI(title="Webnovel Dashboard", version="0.1.0", lifespan=_lifespan)
    # P0-B 修复：project_root 存入 app.state，线程安全且多 worker 友好
    app.state.project_root = _initial_root
    app.state.basic_auth_credentials = basic_auth_credentials

    # P0-A 修复：使用参数控制的 CORS 来源，避免全开放
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _basic_auth_guard(request: Request, call_next):
        credentials = getattr(app.state, "basic_auth_credentials", None)
        if not credentials or request.url.path == "/health":
            return await call_next(request)

        provided = _parse_basic_auth_header(request.headers.get("authorization"))
        if provided is None:
            return _unauthorized_response(request)

        expected_user, expected_password = credentials
        provided_user, provided_password = provided
        if not (
            secrets.compare_digest(provided_user, expected_user)
            and secrets.compare_digest(provided_password, expected_password)
        ):
            return _unauthorized_response(request)

        return await call_next(request)

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

    app.include_router(runtime_router)
    app.include_router(hierarchy_router)
    app.include_router(chat_router)

    # ===========================================================
    # API：项目元信息
    # ===========================================================

    # P1-F：标准健康检查端点，无需项目根目录，供 Docker/K8s 存活探针使用
    @app.get("/health")
    def health():
        """健康检查端点，始终返回 200，无依赖关系。"""
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/api/project/root")
    def project_root_status():
        """P0-B 修复：返回当前配置的项目根目录和就绪状态，供前端健康检查。

        - status="ok"：项目根目录已配置且 state.json 存在
        - status="unavailable"：project_root 未配置（如 uvicorn --reload 后自动恢复失败）
        - status="invalid"：目录存在但 state.json 缺失（项目未初始化）
        """
        root = app.state.project_root
        if root is None:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unavailable",
                    "project_root": None,
                    "index_db_exists": False,
                    "message": "项目根目录未配置，请重启 Dashboard 并传入 --project-root 参数",
                },
            )
        state_path = root / ".webnovel" / "state.json"
        index_db = root / ".webnovel" / "index.db"
        if not state_path.is_file():
            return JSONResponse(
                status_code=503,
                content={
                    "status": "invalid",
                    "project_root": str(root),
                    "index_db_exists": index_db.is_file(),
                    "message": "项目根目录缺少 .webnovel/state.json，请先执行 /webnovel-init",
                },
            )
        return {
            "status": "ok",
            "project_root": str(root),
            "index_db_exists": index_db.is_file(),
        }

    @app.get("/api/project/info")
    def project_info():
        """返回 state.json 完整内容（只读）。"""
        state_path = _webnovel_dir_from_app(app) / "state.json"
        if not state_path.is_file():
            raise HTTPException(404, "state.json 不存在")
        return json.loads(state_path.read_text(encoding="utf-8"))

    # ===========================================================
    # API：实体数据库（index.db 只读查询）
    # ===========================================================

    def _get_db() -> sqlite3.Connection:
        db_path = _webnovel_dir_from_app(app) / "index.db"
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
        entity_type: str | None = Query(None, alias="type"),
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
    def list_relationships(entity: str | None = None, limit: int = 200):
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
        entity: str | None = None,
        from_chapter: int | None = None,
        to_chapter: int | None = None,
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
    def list_scenes(chapter: int | None = None, limit: int = 500):
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
    def list_state_changes(entity: str | None = None, limit: int = 100):
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
    def list_aliases(entity: str | None = None):
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
                "files": _content_file_count(_get_project_root_from_app(app)),
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
    def list_overrides(status: str | None = None, limit: int = 100):
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
    def list_debts(status: str | None = None, limit: int = 100):
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
    def list_debt_events(debt_id: int | None = None, limit: int = 200):
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
    def list_invalid_facts(status: str | None = None, limit: int = 100):
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
    def list_rag_queries(query_type: str | None = None, limit: int = 100):
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
    def list_tool_stats(tool_name: str | None = None, limit: int = 200):
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

    @app.get("/api/skills")
    def list_skills_workspace(
        workspace_id: str = Query(""),
        project_root: str = Query(""),
        enabled: bool | None = Query(None),
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        """Workspace-level skill listing for Skills management page."""
        from core.skill_system import ChatSkillRegistry

        del workspace_id, project_root

        root = _get_project_root_from_app(app)
        registry = ChatSkillRegistry(root)
        all_items = registry.list_workspace()

        filtered = all_items
        if enabled is not None:
            filtered = [item for item in filtered if bool(item.get("enabled", True)) == enabled]

        total = len(filtered)
        paginated = filtered[offset:offset + limit]

        return {
            "status": "ok",
            "items": paginated,
            "total": total,
        }

    @app.post("/api/skills", status_code=201)
    def create_workspace_skill(body: CreateSkillRequest):
        from core.skill_system.chat_skill_registry import (
            ChatSkillRegistry,
            WorkspaceSkillConflictError,
            WorkspaceSkillValidationError,
        )

        root = _get_project_root_from_app(app)
        registry = ChatSkillRegistry(root)
        try:
            return registry.create_workspace_skill(
                skill_id=body.skill_id,
                name=body.name,
                description=body.description,
                instruction_template=body.instruction_template,
            )
        except WorkspaceSkillValidationError as exc:
            _raise_api_error(
                400,
                error_code="invalid_skill_payload",
                message="Skill payload is invalid.",
                details={"field_errors": exc.field_errors},
            )
        except WorkspaceSkillConflictError as exc:
            _raise_api_error(
                409,
                error_code="skill_conflict",
                message="A skill with this id already exists.",
                details={"skill_id": exc.skill_id},
            )

    @app.post("/api/skills/draft", response_model=SkillDraftResponse)
    def generate_workspace_skill_draft(body: SkillDraftRequest):
        from .services.chat import ChatOrchestrationService

        root = _get_project_root_from_app(app)
        service = ChatOrchestrationService(root)
        try:
            return SkillDraftResponse.model_validate(
                service.generate_skill_draft(
                    body.prompt,
                    body.current_draft.model_dump(),
                )
            )
        except service.WorkflowChatError as exc:
            _raise_api_error(
                exc.status_code,
                error_code=exc.error_code,
                message=exc.message,
                details=exc.details,
            )

    @app.delete("/api/skills/{skill_id}", status_code=204)
    def delete_workspace_skill(skill_id: str):
        from core.agent_runtime.chat_service import ChatService
        from core.skill_system.chat_skill_registry import ChatSkillRegistry, WorkspaceSkillNotFoundError

        root = _get_project_root_from_app(app)
        registry = ChatSkillRegistry(root)
        try:
            registry.delete_workspace_skill(skill_id)
        except WorkspaceSkillNotFoundError as exc:
            _raise_api_error(
                404,
                error_code="skill_not_found",
                message="Skill was not found.",
                details={"skill_id": exc.skill_id},
            )

        chat_service = ChatService(root)
        chat_service.repository.unmount_skill_everywhere(skill_id.strip().lower(), source="workspace")
        return None

    # ===========================================================
    # API：项目初始化
    # ===========================================================

    @app.post("/api/books/init", status_code=201)
    async def init_book(request: Request):
        """创建新的 webnovel 项目，调用 scripts/init_project.init_project()。

        请求体 JSON 必须包含 title、genre、project_dir，其余为可选参数。
        成功时返回 { "project_root", "book_id", "title" }。
        """
        from scripts.init_project import init_project
        from core.book_hierarchy.schema import get_hierarchy_db_path

        try:
            payload: Any = await request.json()
        except json.JSONDecodeError:
            _raise_api_error(
                400,
                error_code="invalid_json_body",
                message="请求体必须是合法 JSON",
            )

        if not isinstance(payload, dict):
            _raise_api_error(
                400,
                error_code="invalid_request_body",
                message="请求体必须是 JSON 对象",
            )

        # --- 必填字段校验 ---
        title = payload.get("title")
        genre = payload.get("genre")
        project_dir = payload.get("project_dir")

        missing: list[str] = []
        if not title or not isinstance(title, str) or not title.strip():
            missing.append("title")
        if not genre or not isinstance(genre, str) or not genre.strip():
            missing.append("genre")
        if not project_dir or not isinstance(project_dir, str) or not project_dir.strip():
            missing.append("project_dir")

        if missing:
            _raise_api_error(
                400,
                error_code="missing_required_fields",
                message=f"缺少必填字段: {', '.join(missing)}",
                details={"missing_fields": missing},
            )

        # validated — guaranteed non-empty str after the check above
        assert isinstance(title, str) and isinstance(genre, str) and isinstance(project_dir, str)
        _title = title.strip()
        _genre = genre.strip()
        _project_dir = project_dir.strip()

        # --- 可选参数（与 init_project 签名对齐） ---
        optional_keys = [
            "protagonist_name",
            "target_words",
            "target_chapters",
            "golden_finger_name",
            "golden_finger_type",
            "golden_finger_style",
            "core_selling_points",
            "protagonist_structure",
            "heroine_config",
            "heroine_names",
            "heroine_role",
            "co_protagonists",
            "co_protagonist_roles",
            "antagonist_tiers",
            "world_scale",
            "factions",
            "power_system_type",
            "social_class",
            "resource_distribution",
            "gf_visibility",
            "gf_irreversible_cost",
            "protagonist_desire",
            "protagonist_flaw",
            "protagonist_archetype",
            "antagonist_level",
            "target_reader",
            "platform",
            "currency_system",
            "currency_exchange",
            "sect_hierarchy",
            "cultivation_chain",
            "cultivation_subtiers",
        ]

        kwargs: dict[str, Any] = {}
        for key in optional_keys:
            if key in payload:
                kwargs[key] = payload[key]

        # --- 检查项目是否已存在（state.json 存在视为冲突） ---
        target_path = Path(_project_dir).expanduser().resolve()
        state_file = target_path / ".webnovel" / "state.json"
        if state_file.is_file():
            _raise_api_error(
                409,
                error_code="project_already_exists",
                message="该项目目录已存在 state.json，不能重复初始化",
                details={"project_dir": str(target_path)},
            )

        previous_project_root = getattr(request.app.state, "project_root", None)

        # --- 调用 init_project ---
        try:
            init_project(_project_dir, _title, _genre, **kwargs)
        except FileExistsError as exc:
            _raise_api_error(
                409,
                error_code="project_already_exists",
                message="项目目录已存在",
                details={"error": str(exc)},
            )
        except ValueError as exc:
            _raise_api_error(
                400,
                error_code="invalid_params",
                message=str(exc),
            )
        except SystemExit as exc:
            _raise_api_error(
                400,
                error_code="init_project_error",
                message=str(exc),
            )

        # --- 读取 book_id from hierarchy.db ---
        project_root = Path(_project_dir).expanduser().resolve()
        hierarchy_db = get_hierarchy_db_path(project_root)
        book_id: str | None = None
        if hierarchy_db.is_file():
            with closing(sqlite3.connect(str(hierarchy_db))) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT book_id FROM book_roots WHERE status = 'active' LIMIT 1"
                ).fetchone()
                if row:
                    book_id = row["book_id"]

        _copy_generation_settings(previous_project_root, project_root)
        _rebind_project_root(request.app, project_root)

        return {
            "project_root": str(project_root),
            "book_id": book_id,
            "title": _title,
        }

    # ===========================================================
    # API：文档浏览（正文/大纲/设定集 —— 只读）
    # ===========================================================

    @app.get("/api/files/tree")
    def file_tree():
        """列出 正文/、大纲/、设定集/ 三个目录的树结构。"""
        root = _get_project_root_from_app(app)
        result = {}
        for folder_name in ("正文", "大纲", "设定集"):
            folder = root / folder_name
            if not folder.is_dir():
                result[folder_name] = []
                continue
            # P0-C 修复：传入 max_depth 限制防止深层目录引发栈溢出
            result[folder_name] = _walk_tree(folder, root, max_depth=20)
        return result

    @app.get("/api/files/read")
    def file_read(path: str):
        """只读读取一个文件内容（限 正文/大纲/设定集 目录）。"""
        root = _get_project_root_from_app(app)
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

    @app.get("/api/outlines")
    def outlines(workspace_id: str = "", project_root: str = ""):
        """读取总纲与最新细纲内容。"""
        del workspace_id, project_root

        root = _get_project_root_from_app(app)
        outline_dir = root / "大纲"
        total_outline = ""
        detailed_outline = ""

        total_path = outline_dir / "总纲.md"
        if total_path.is_file():
            total_outline = total_path.read_text(encoding="utf-8")

        if outline_dir.is_dir():
            detailed_files = sorted(outline_dir.glob("*-详细大纲.md"), reverse=True)
            if detailed_files:
                detailed_outline = detailed_files[0].read_text(encoding="utf-8")

        return {
            "status": "ok",
            "total_outline": total_outline,
            "detailed_outline": detailed_outline,
        }

    @app.get("/api/outlines/splits")
    def outline_splits(
        workspace_id: str = "",
        project_root: str = "",
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        """返回大纲拆分历史（当前以节拍表文件作为近似记录）。"""
        del workspace_id, project_root

        root = _get_project_root_from_app(app)
        outline_dir = root / "大纲"
        items = []

        if outline_dir.is_dir():
            for file in sorted(outline_dir.glob("*-节拍表.md"), reverse=True):
                items.append({
                    "id": file.stem,
                    "created_at": "",
                    "segment_count": 0,
                    "status": "completed",
                })

        total = len(items)
        paginated = items[offset:offset + limit]

        return {
            "status": "ok",
            "items": paginated,
            "total": total,
        }

    @app.get("/api/settings/files/tree")
    def settings_file_tree(workspace_id: str = "", project_root: str = ""):
        del workspace_id, project_root
        root = _get_project_root_from_app(app)
        settings_dir = root / "设定集"
        if not settings_dir.is_dir():
            return {"status": "ok", "nodes": []}
        return {"status": "ok", "nodes": _walk_tree(settings_dir, root, max_depth=20)}

    @app.get("/api/settings/provider")
    def settings_provider(workspace_id: str = "", project_root: str = ""):
        del workspace_id, project_root
        root = _get_project_root_from_app(app)
        return runtime_service_module._collect_generation_state(project_root=root)

    @app.patch("/api/settings/provider")
    async def settings_provider_update(request: Request, workspace_id: str = "", project_root: str = ""):
        del workspace_id, project_root
        root = _get_project_root_from_app(app)
        payload: Any = {}
        try:
            payload = await request.json()
        except json.JSONDecodeError:
            _raise_api_error(
                400,
                error_code="invalid_json_body",
                message="请求体必须是合法 JSON",
            )

        if not isinstance(payload, dict):
            _raise_api_error(
                400,
                error_code="invalid_request_body",
                message="请求体必须是 JSON 对象",
            )

        provider = str(payload.get("provider") or "").strip()
        if not provider:
            _raise_api_error(
                400,
                error_code="provider_required",
                message="provider 不能为空",
            )
        if provider.lower() in {"local", "stub"}:
            _raise_api_error(
                400,
                error_code="provider_not_supported",
                message="Web 端只支持配置真实 provider，local/stub 已不再提供。",
                details={"provider": provider},
            )

        updates: dict[str, str | None] = {
            "GENERATION_API_TYPE": provider,
            "GENERATION_BASE_URL": _normalize_optional_env_value(payload.get("base_url")),
            "GENERATION_MODEL": _normalize_optional_env_value(payload.get("model")),
        }

        clear_api_key = bool(payload.get("clear_api_key"))
        api_key = payload.get("api_key") if isinstance(payload.get("api_key"), str) else ""
        if clear_api_key:
            updates["GENERATION_API_KEY"] = None
        elif api_key:
            updates["GENERATION_API_KEY"] = api_key

        _write_project_env_values(root, updates)
        return runtime_service_module._collect_generation_state(project_root=root)

    @app.get("/api/settings/files/read")
    def settings_file_read(path: str, workspace_id: str = "", project_root: str = ""):
        del workspace_id, project_root
        root = _get_project_root_from_app(app)
        resolved = safe_resolve(root, path)
        settings_dir = root / "设定集"
        if not _is_child(resolved, settings_dir):
            _raise_api_error(
                403,
                error_code="file_access_forbidden",
                message="仅允许读取设定集目录下的文件",
                details={"path": path},
            )
        if not resolved.is_file():
            _raise_api_error(
                404,
                error_code="file_not_found",
                message="文件不存在",
                details={"path": path},
            )
        try:
            content = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = "[二进制文件，无法预览]"
        return {"status": "ok", "path": path, "content": content}

    @app.get("/api/settings/dictionary")
    def settings_dictionary(
        term: str | None = Query(None),
        type: str | None = Query(None),
        status: str | None = Query(None),
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        workspace_id: str = "",
        project_root: str = "",
    ):
        del workspace_id, project_root
        with closing(_get_db()) as conn:
            q = "SELECT id, canonical_name, type, tier, first_appearance, last_appearance FROM entities"
            params: list[Any] = []
            clauses: list[str] = []
            if term:
                clauses.append("canonical_name LIKE ?")
                params.append(f"%{term}%")
            if type:
                clauses.append("type = ?")
                params.append(type)
            if clauses:
                q += " WHERE " + " AND ".join(clauses)
            q += " ORDER BY last_appearance DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = _fetchall_safe(conn, q, tuple(params))
            items = [{
                "id": r.get("id", ""),
                "term": r.get("canonical_name", ""),
                "type": r.get("type", "concept"),
                "attrs": {},
                "source_file": "",
                "source_span": "0-0",
                "status": "confirmed",
                "fingerprint": "",
            } for r in rows]
            if status:
                items = [item for item in items if item["status"] == status]
            return {"status": "ok", "items": items, "total": len(items)}

    # ===========================================================
    # SSE：实时变更推送
    # ===========================================================

    @app.get("/api/events")
    async def sse():
        """P1-C 修复：Server-Sent Events 端点，推送 .webnovel/ 下的文件变更。

        连接数超过 MAX_SSE_CLIENTS（50）时返回 503，防止 DoS 攻击导致内存耗尽。
        """
        # P1-C 修复：订阅前检查连接数上限
        q = _watcher.subscribe()
        if q is None:
            return JSONResponse(
                status_code=503,
                content={
                    "error_code": "sse_clients_limit_reached",
                    "message": f"SSE 连接已满（上限 {_watcher.DEFAULT_MAX_SSE_CLIENTS}），请稍后重试",
                },
            )

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
                "<p>前端尚未构建。请回到仓库根目录，使用规范启动命令："
                "<code>powershell -ExecutionPolicy Bypass -File running/init.ps1 -ProjectRoot &lt;PROJECT_ROOT&gt; -StartDashboard</code>。"
                "</p>"
                "<p>如果你已经完成前端依赖安装，也可以使用："
                "<code>python -X utf8 webnovel-writer/scripts/webnovel.py dashboard --project-root &lt;PROJECT_ROOT&gt;</code>。"
                "</p>"
                '<p>API 文档：<a href="/docs">/docs</a></p>'
            )

    return app


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _get_project_root_from_app(app: FastAPI) -> Path:
    root = getattr(app.state, "project_root", None)
    if isinstance(root, Path) and root.is_dir():
        return root
    recovered = _resolve_project_root_from_pointer()
    if recovered is not None:
        app.state.project_root = recovered
        return recovered
    _raise_api_error(
        503,
        error_code="project_root_unavailable",
        message="当前未绑定小说项目，请重新通过规范启动命令启动 Dashboard。",
    )
    raise AssertionError("unreachable")


def _normalize_optional_env_value(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value).strip() or None
    normalized = value.strip()
    return normalized or None


def _write_project_env_values(project_root: Path, updates: dict[str, str | None]) -> None:
    env_path = project_root / ".env"
    existing_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    remaining_updates = {key: value for key, value in updates.items() if key in GENERATION_ENV_KEYS}
    next_lines: list[str] = []

    for line in existing_lines:
        match = ENV_ASSIGNMENT_RE.match(line)
        if not match:
            next_lines.append(line)
            continue

        key = match.group(1)
        if key not in remaining_updates:
            next_lines.append(line)
            continue

        value = remaining_updates.pop(key)
        if value is not None:
            next_lines.append(f"{key}={value}")

    for key, value in remaining_updates.items():
        if value is not None:
            next_lines.append(f"{key}={value}")

    content = "\n".join(next_lines)
    if next_lines:
        content += "\n"
    env_path.write_text(content, encoding="utf-8")

# P0-C 修复：添加 max_depth 参数防止深层目录引发 RecursionError
def _walk_tree(folder: Path, root: Path, max_depth: int = 20, _current_depth: int = 0) -> list[dict]:
    """递归遍历目录树。

    Args:
        folder: 要遍历的目录。
        root: 项目根目录（用于计算相对路径）。
        max_depth: 最大递归深度，超过后截断并标记 truncated=True，默认 20。
        _current_depth: 当前深度（内部递归使用）。
    """
    items = []
    for child in sorted(folder.iterdir()):
        rel = str(child.relative_to(root)).replace("\\", "/")
        if child.is_dir():
            if _current_depth >= max_depth:
                # 已达最大深度，截断子目录，标记 truncated
                items.append({
                    "name": child.name,
                    "type": "dir",
                    "path": rel,
                    "children": [],
                    "truncated": True,
                })
            else:
                items.append({
                    "name": child.name,
                    "type": "dir",
                    "path": rel,
                    "children": _walk_tree(child, root, max_depth=max_depth, _current_depth=_current_depth + 1),
                })
        else:
            items.append({"name": child.name, "type": "file", "path": rel, "size": child.stat().st_size})
    return items


def _is_child(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False
