from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..models.chat import (
    ChatResponse,
    CreateChatRequest,
    MessageResponse,
    SendMessageRequest,
    SkillResponse,
    StreamMessageRequest,
    UpdateChatSkillsRequest,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _get_service(request: Request) -> "ChatOrchestrationService":
    project_root = getattr(request.app.state, "project_root", None)
    if not project_root:
        raise HTTPException(status_code=500, detail="project_root not configured")
    from ..services.chat import ChatOrchestrationService

    return ChatOrchestrationService(project_root)


@router.get("/chats")
def list_chats(request: Request) -> list[ChatResponse]:
    return _get_service(request).list_chats()


@router.post("/chats", status_code=201)
def create_chat(request: Request, body: CreateChatRequest) -> ChatResponse:
    return _get_service(request).create_chat(body)


@router.get("/chats/{chat_id}")
def get_chat(request: Request, chat_id: str) -> ChatResponse:
    result = _get_service(request).get_chat(chat_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return result


@router.delete("/chats/{chat_id}", status_code=204)
def delete_chat(request: Request, chat_id: str):
    if not _get_service(request).delete_chat(chat_id):
        raise HTTPException(status_code=404, detail="Chat not found")
    return None


@router.get("/chats/{chat_id}/messages")
def get_messages(request: Request, chat_id: str) -> list[MessageResponse]:
    service = _get_service(request)
    try:
        return service.get_history(chat_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Chat not found") from exc


@router.post("/chats/{chat_id}/messages")
def send_message(request: Request, chat_id: str, body: SendMessageRequest) -> MessageResponse:
    service = _get_service(request)
    try:
        return service.send_message(chat_id, body.content)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Chat not found") from exc


@router.post("/chats/{chat_id}/stream")
def stream_message(request: Request, chat_id: str, body: StreamMessageRequest):
    service = _get_service(request)
    try:
        service._require_chat(chat_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Chat not found") from exc

    def event_generator():
        yield from service.send_and_stream(chat_id, body.content)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/skills")
def list_skills(request: Request) -> list[SkillResponse]:
    from core.skill_system import ChatSkillRegistry

    project_root = getattr(request.app.state, "project_root", None)
    registry = ChatSkillRegistry(project_root)
    return registry.list_all()


@router.get("/chats/{chat_id}/skills")
def get_chat_skills(request: Request, chat_id: str) -> list[SkillResponse]:
    service = _get_service(request)
    try:
        return service.get_chat_skills(chat_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Chat not found") from exc


@router.patch("/chats/{chat_id}/skills")
def update_chat_skills(request: Request, chat_id: str, body: UpdateChatSkillsRequest) -> list[SkillResponse]:
    service = _get_service(request)
    try:
        return service.update_chat_skills(chat_id, [item.model_dump() for item in body.skills])
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Chat not found") from exc
