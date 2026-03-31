# pyright: reportMissingImports=false, reportImplicitRelativeImport=false

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from core.book_hierarchy.models import BookHierarchyError

from ..models.common import ApiErrorResponse
from ..models.hierarchy import (
    CreateBookRequest,
    CreateHierarchyEntityRequest,
    MarkIndexStaleRequest,
    PreviewProposalRequest,
    ReorderPlotsRequest,
    RevisionDiffResponse,
    RollbackRevisionRequest,
    UpdateHierarchyEntityRequest,
)
from ..services.hierarchy import HierarchyApiService, HierarchyApiServiceError

ERROR_RESPONSES = {
    400: {"model": ApiErrorResponse, "description": "Bad request."},
    404: {"model": ApiErrorResponse, "description": "Resource not found."},
    409: {"model": ApiErrorResponse, "description": "Conflict."},
    500: {"model": ApiErrorResponse, "description": "Internal server error."},
}

router = APIRouter(prefix="/api/hierarchy", tags=["hierarchy"])


def _get_service(request: Request) -> HierarchyApiService:
    project_root = getattr(request.app.state, "project_root", None)
    if not project_root:
        raise HierarchyApiServiceError(
            status_code=500,
            error_code="project_root_unavailable",
            message="Project root is not configured.",
        )
    return HierarchyApiService(Path(project_root))


def _error_response(error: BookHierarchyError | HierarchyApiServiceError, request: Request) -> JSONResponse:
    payload = ApiErrorResponse(
        error_code=error.error_code,
        message=error.message,
        details=error.details,
        request_id=request.headers.get("x-request-id"),
    )
    return JSONResponse(status_code=error.status_code, content=payload.model_dump())


@router.post("/books", status_code=201, responses=ERROR_RESPONSES)
def create_book(request: Request, body: CreateBookRequest):
    try:
        return _get_service(request).create_book(title=body.title, synopsis=body.synopsis)
    except (BookHierarchyError, HierarchyApiServiceError) as exc:
        return _error_response(exc, request)


@router.get("/workspace", responses=ERROR_RESPONSES)
def get_workspace(request: Request):
    try:
        return _get_service(request).get_workspace()
    except (BookHierarchyError, HierarchyApiServiceError) as exc:
        return _error_response(exc, request)


@router.post("/books/{book_id}/entities/{entity_type}", status_code=201, responses=ERROR_RESPONSES)
def create_entity(request: Request, book_id: str, entity_type: str, body: CreateHierarchyEntityRequest):
    try:
        return _get_service(request).create_entity(
            book_id,
            entity_type,
            parent_id=body.parent_id,
            title=body.title,
            body=body.body,
            metadata=body.metadata,
        )
    except (BookHierarchyError, HierarchyApiServiceError) as exc:
        return _error_response(exc, request)


@router.get("/books/{book_id}/entities/{entity_type}/{entity_id}", responses=ERROR_RESPONSES)
def get_entity(request: Request, book_id: str, entity_type: str, entity_id: str):
    try:
        return _get_service(request).get_entity(book_id, entity_type, entity_id)
    except (BookHierarchyError, HierarchyApiServiceError) as exc:
        return _error_response(exc, request)


@router.patch("/books/{book_id}/entities/{entity_type}/{entity_id}", responses=ERROR_RESPONSES)
def update_entity(request: Request, book_id: str, entity_type: str, entity_id: str, body: UpdateHierarchyEntityRequest):
    try:
        return _get_service(request).update_entity(
            book_id,
            entity_type,
            entity_id,
            expected_version=body.expected_version,
            title=body.title,
            body=body.body,
            metadata=body.metadata,
        )
    except (BookHierarchyError, HierarchyApiServiceError) as exc:
        return _error_response(exc, request)


@router.delete("/books/{book_id}/entities/{entity_type}/{entity_id}", status_code=204, responses=ERROR_RESPONSES)
def delete_entity(request: Request, book_id: str, entity_type: str, entity_id: str):
    try:
        _get_service(request).delete_entity(book_id, entity_type, entity_id)
        return None
    except (BookHierarchyError, HierarchyApiServiceError) as exc:
        return _error_response(exc, request)


@router.post("/books/{book_id}/entities/plot/reorder", responses=ERROR_RESPONSES)
def reorder_plots(request: Request, book_id: str, body: ReorderPlotsRequest):
    try:
        return _get_service(request).reorder_plots(book_id, body.parent_id, body.ordered_ids)
    except (BookHierarchyError, HierarchyApiServiceError) as exc:
        return _error_response(exc, request)


@router.post("/books/{book_id}/proposals/preview", status_code=201, responses=ERROR_RESPONSES)
def preview_proposal(request: Request, book_id: str, body: PreviewProposalRequest):
    try:
        return _get_service(request).preview_proposal(book_id, body.model_dump())
    except (BookHierarchyError, HierarchyApiServiceError) as exc:
        return _error_response(exc, request)


@router.get("/books/{book_id}/proposals/{proposal_id}", responses=ERROR_RESPONSES)
def get_proposal(request: Request, book_id: str, proposal_id: str):
    try:
        return _get_service(request).get_proposal(book_id, proposal_id)
    except (BookHierarchyError, HierarchyApiServiceError) as exc:
        return _error_response(exc, request)


@router.post("/books/{book_id}/proposals/{proposal_id}/confirm", responses=ERROR_RESPONSES)
def confirm_proposal(request: Request, book_id: str, proposal_id: str):
    try:
        return _get_service(request).confirm_proposal(book_id, proposal_id)
    except (BookHierarchyError, HierarchyApiServiceError) as exc:
        return _error_response(exc, request)


@router.post("/books/{book_id}/proposals/{proposal_id}/reject", responses=ERROR_RESPONSES)
def reject_proposal(request: Request, book_id: str, proposal_id: str):
    try:
        return _get_service(request).reject_proposal(book_id, proposal_id)
    except (BookHierarchyError, HierarchyApiServiceError) as exc:
        return _error_response(exc, request)


@router.get("/books/{book_id}/revisions/{entity_type}/{entity_id}", responses=ERROR_RESPONSES)
def list_revisions(request: Request, book_id: str, entity_type: str, entity_id: str):
    try:
        return _get_service(request).list_revisions(book_id, entity_type, entity_id)
    except (BookHierarchyError, HierarchyApiServiceError) as exc:
        return _error_response(exc, request)


@router.get(
    "/books/{book_id}/revisions/{entity_type}/{entity_id}/diff",
    response_model=RevisionDiffResponse,
    responses=ERROR_RESPONSES,
)
def diff_revisions(
    request: Request,
    book_id: str,
    entity_type: str,
    entity_id: str,
    from_revision: int = Query(..., ge=1),
    to_revision: int = Query(..., ge=1),
):
    try:
        return _get_service(request).diff_revisions(
            book_id,
            entity_type,
            entity_id,
            from_revision=from_revision,
            to_revision=to_revision,
        )
    except (BookHierarchyError, HierarchyApiServiceError) as exc:
        return _error_response(exc, request)


@router.post("/books/{book_id}/revisions/{entity_type}/{entity_id}/rollback", responses=ERROR_RESPONSES)
def rollback_revision(request: Request, book_id: str, entity_type: str, entity_id: str, body: RollbackRevisionRequest):
    try:
        return _get_service(request).rollback_revision(
            book_id,
            entity_type,
            entity_id,
            target_revision=body.target_revision,
            expected_version=body.expected_version,
        )
    except (BookHierarchyError, HierarchyApiServiceError) as exc:
        return _error_response(exc, request)


@router.post("/books/{book_id}/index/mark-stale", responses=ERROR_RESPONSES)
def mark_index_stale(request: Request, book_id: str, body: MarkIndexStaleRequest):
    try:
        return _get_service(request).mark_index_stale(book_id, reason=body.reason)
    except (BookHierarchyError, HierarchyApiServiceError) as exc:
        return _error_response(exc, request)


@router.post("/books/{book_id}/index/rebuild", responses=ERROR_RESPONSES)
def rebuild_index(request: Request, book_id: str):
    try:
        return _get_service(request).rebuild_index(book_id)
    except (BookHierarchyError, HierarchyApiServiceError) as exc:
        return _error_response(exc, request)
