from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any

from scripts.data_modules.config import DataModulesConfig

EVENT_MESSAGE_START = "message_start"
EVENT_TEXT_DELTA = "text_delta"
EVENT_TOOL_CALL = "tool_call"
EVENT_TOOL_RESULT = "tool_result"
EVENT_MESSAGE_COMPLETE = "message_complete"
EVENT_MESSAGE_ERROR = "message_error"
EVENT_HEARTBEAT = "heartbeat"


def sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format a single SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class ChatStreamAdapter:
    """Bridge text generation responses into SSE events."""

    def __init__(self, config: DataModulesConfig | None = None):
        self.config = config

    def stream_chat(
        self,
        *,
        messages: list[dict[str, str]],
        message_id: str,
        chat_id: str,
    ) -> Generator[str, None, None]:
        provider = "stub" if (self.config and getattr(self.config, "generation_api_type", "") == "stub") else "openai"
        yield sse_event(
            EVENT_MESSAGE_START,
            {"message_id": message_id, "chat_id": chat_id, "provider": provider},
        )

        try:
            from scripts.data_modules.generation_client import GenerationAPIClient

            client = GenerationAPIClient(self.config)
            for chunk in client.complete_text_stream(messages=messages):
                yield sse_event(EVENT_TEXT_DELTA, {"delta": chunk})

            yield sse_event(EVENT_MESSAGE_COMPLETE, {"message_id": message_id, "usage": {}})
        except Exception as exc:
            yield sse_event(
                EVENT_MESSAGE_ERROR,
                {
                    "message_id": message_id,
                    "error": str(exc),
                    "code": "provider_error",
                },
            )
