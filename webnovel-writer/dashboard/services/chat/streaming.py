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

    _TOOL_TEXT_CHUNK_SIZE = 80
    _MAX_TOOL_ROUNDS = 8

    def __init__(self, config: DataModulesConfig | None = None):
        self.config = config

    def stream_chat(
        self,
        *,
        messages: list[dict[str, Any]],
        message_id: str,
        chat_id: str,
        tools: list[dict[str, Any]] | None = None,
        tool_dispatcher: Any | None = None,
    ) -> Generator[str, None, None]:
        provider = str(getattr(self.config, "generation_api_type", "local") or "local")
        yield sse_event(
            EVENT_MESSAGE_START,
            {"message_id": message_id, "chat_id": chat_id, "provider": provider},
        )

        try:
            from scripts.data_modules.generation_client import GenerationAPIClient

            client = GenerationAPIClient(self.config)
            if tools and tool_dispatcher is not None:
                yield from self._stream_chat_with_tools(
                    client=client,
                    messages=messages,
                    tools=tools,
                    tool_dispatcher=tool_dispatcher,
                    message_id=message_id,
                )
                return

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

    def _stream_chat_with_tools(
        self,
        *,
        client: Any,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_dispatcher: Any,
        message_id: str,
    ) -> Generator[str, None, None]:
        conversation: list[dict[str, Any]] = [dict(message) for message in messages]

        for round_index in range(self._MAX_TOOL_ROUNDS):
            text, raw_tool_calls = client.complete_with_tools(messages=conversation, tools=tools)
            tool_calls = self._normalize_tool_calls(raw_tool_calls, round_index)

            if not tool_calls:
                for chunk in self._chunk_text(text):
                    yield sse_event(EVENT_TEXT_DELTA, {"message_id": message_id, "delta": chunk})
                yield sse_event(EVENT_MESSAGE_COMPLETE, {"message_id": message_id, "usage": {"tool_rounds": round_index}})
                return

            conversation.append(
                {
                    "role": "assistant",
                    "content": text or "",
                    "tool_calls": [tool_call["raw"] for tool_call in tool_calls],
                }
            )

            for tool_call in tool_calls:
                yield sse_event(
                    EVENT_TOOL_CALL,
                    {
                        "message_id": message_id,
                        "tool_call_id": tool_call["id"],
                        "name": tool_call["name"],
                        "arguments": tool_call["arguments"],
                    },
                )

                result = tool_dispatcher(tool_call["name"], tool_call["arguments"])
                status = "error" if isinstance(result, dict) and result.get("error") else "success"
                yield sse_event(
                    EVENT_TOOL_RESULT,
                    {
                        "message_id": message_id,
                        "tool_call_id": tool_call["id"],
                        "name": tool_call["name"],
                        "status": status,
                        "output": result,
                    },
                )

                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

        raise RuntimeError("chat tool execution exceeded maximum tool rounds")

    @classmethod
    def _normalize_tool_calls(cls, tool_calls: list[dict[str, Any]], round_index: int) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, tool_call in enumerate(tool_calls):
            if not isinstance(tool_call, dict):
                continue
            function = tool_call.get("function")
            if not isinstance(function, dict):
                continue
            name = str(function.get("name") or "").strip()
            if not name:
                continue
            arguments = cls._parse_tool_arguments(function.get("arguments"))
            normalized.append(
                {
                    "id": str(tool_call.get("id") or f"toolcall-{round_index}-{index}"),
                    "name": name,
                    "arguments": arguments,
                    "raw": tool_call,
                }
            )
        return normalized

    @staticmethod
    def _parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
        if isinstance(raw_arguments, dict):
            return dict(raw_arguments)
        if not isinstance(raw_arguments, str) or not raw_arguments.strip():
            return {}
        try:
            payload = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    @classmethod
    def _chunk_text(cls, text: str) -> list[str]:
        if not text:
            return []
        return [text[index:index + cls._TOOL_TEXT_CHUNK_SIZE] for index in range(0, len(text), cls._TOOL_TEXT_CHUNK_SIZE)]
