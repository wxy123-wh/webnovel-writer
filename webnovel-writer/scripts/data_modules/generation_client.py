#!/usr/bin/env python3

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from .config import get_config


@dataclass
class GenerationStats:
    total_calls: int = 0
    total_time: float = 0.0
    errors: int = 0


def _extract_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("generation response missing choices")

    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        raise ValueError("generation response missing message")

    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
        if text_parts:
            return "\n".join(text_parts)
    raise ValueError("generation response missing text content")


def _extract_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        payload = json.loads(cleaned[start:end + 1])

    if not isinstance(payload, dict):
        raise ValueError("expected JSON object response")
    return payload


class GenerationAPIClient:
    def __init__(self, config=None):
        self.config = config or get_config()
        self.stats = GenerationStats()

    def _build_url(self) -> str:
        base_url = self.config.generation_base_url.rstrip("/")
        if self.config.generation_api_type == "openai":
            if base_url.endswith("/chat/completions"):
                return base_url
            if base_url.endswith("/v1"):
                return f"{base_url}/chat/completions"
            return f"{base_url}/v1/chat/completions"
        return base_url

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.generation_api_key:
            headers["Authorization"] = f"Bearer {self.config.generation_api_key}"
        return headers

    def _build_payload(
        self,
        *,
        messages: list[dict[str, str]],
        expect_json: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.generation_model,
            "messages": messages,
            "temperature": self.config.generation_temperature,
            "max_tokens": self.config.generation_max_tokens,
        }
        if expect_json:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _request_openai(self, *, messages: list[dict[str, str]], expect_json: bool) -> str:
        if not self.config.generation_api_key:
            raise ValueError("GENERATION_API_KEY / OPENAI_API_KEY is required for openai generation mode")

        url = self._build_url()
        headers = self._build_headers()
        payload = self._build_payload(messages=messages, expect_json=expect_json)
        max_retries = getattr(self.config, "api_max_retries", 3)
        base_delay = getattr(self.config, "api_retry_delay", 1.0)

        for attempt in range(max_retries):
            req = request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=self.config.normal_timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    return _extract_content(data)
            except error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="ignore")
                if exc.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                    time.sleep(base_delay * (2 ** attempt))
                    continue
                raise RuntimeError(f"generation HTTP {exc.code}: {body[:200]}") from exc
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(base_delay * (2 ** attempt))
                    continue
                raise

        raise RuntimeError("generation request exhausted retries")

    def complete_text(self, *, messages: list[dict[str, str]], stub_text: str = "") -> str:
        start = time.time()
        try:
            if self.config.generation_api_type == "stub":
                result = stub_text
            else:
                result = self._request_openai(messages=messages, expect_json=False)
            self.stats.total_calls += 1
            self.stats.total_time += time.time() - start
            return result
        except Exception:
            self.stats.errors += 1
            raise

    def complete_json(
        self,
        *,
        messages: list[dict[str, str]],
        stub_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        start = time.time()
        try:
            if self.config.generation_api_type == "stub":
                result = stub_payload or {}
            else:
                raw = self._request_openai(messages=messages, expect_json=True)
                result = _extract_json_object(raw)
            self.stats.total_calls += 1
            self.stats.total_time += time.time() - start
            return result
        except Exception:
            self.stats.errors += 1
            raise
