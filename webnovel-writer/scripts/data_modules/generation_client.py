#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import time
from collections.abc import Generator
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

    @staticmethod
    def _latest_user_message(messages: list[dict[str, str]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user":
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
        return ""

    @staticmethod
    def _system_prompt(messages: list[dict[str, str]]) -> str:
        for message in messages:
            if message.get("role") == "system":
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content
        return ""

    @staticmethod
    def _extract_context_line(system_prompt: str, label: str) -> str:
        pattern = rf"-\s*{re.escape(label)}：\s*(.+)"
        match = re.search(pattern, system_prompt)
        if not match:
            return ""
        return match.group(1).strip()

    @staticmethod
    def _extract_skill_headers(system_prompt: str) -> list[str]:
        return [match.strip() for match in re.findall(r"\[(?:system|profile|workspace):[^\]]+\]", system_prompt)]

    @staticmethod
    def _has_skill(skill_headers: list[str], skill_id: str) -> bool:
        needle = f":{skill_id}]"
        return any(needle in header for header in skill_headers)

    def _build_local_write_plan(self, *, user_message: str, project_summary: list[str]) -> str:
        context_text = "；".join(project_summary)
        return "\n".join([
            "这是本地模式下生成的真实辅助回复。",
            f"我已经读取到的当前项目信息：{context_text}。",
            f"你这次要处理的问题是：{user_message}",
            "当前已进入写作型辅助模式，我先给你一个可直接落笔的章节开头方案：",
            "一、开头钩子：先让主角在第一页就面对一个必须马上回应的问题，避免从背景介绍起手。",
            "二、第一段场景：用一个具体动作把人物、场景和当下压力绑在一起，例如‘他刚做完某件事，就立刻被新的变故打断’。",
            "三、第二段推进：把主角最想达成的短期目标说清楚，同时让阻碍立刻出现，不要让冲突延后。",
            "四、第三段收束：在段尾留一个逼读者继续看的悬念、代价或误判，形成自然翻页动力。",
            "五、落笔提示：先写 300-500 字试段，只保留一个主冲突和一个情绪主色，写完后再继续扩章。",
            "如果你愿意，我下一轮可以直接把这个方案展开成三段正文试写。",
        ])

    def _complete_local_text(self, *, messages: list[dict[str, str]]) -> str:
        system_prompt = self._system_prompt(messages)
        user_message = self._latest_user_message(messages)
        title = self._extract_context_line(system_prompt, "作品标题")
        genre = self._extract_context_line(system_prompt, "作品类型")
        chapter = self._extract_context_line(system_prompt, "当前章节")
        skill_headers = self._extract_skill_headers(system_prompt)

        project_summary: list[str] = []
        if title:
            project_summary.append(f"作品《{title}》")
        if genre:
            project_summary.append(f"类型是{genre}")
        if chapter:
            project_summary.append(f"当前推进到第{chapter}章")
        if not project_summary:
            project_summary.append("当前工作区已经接入 Chat 创作台")

        if self._has_skill(skill_headers, "webnovel-write"):
            return self._build_local_write_plan(user_message=user_message or "请给我一个章节写作方案", project_summary=project_summary)

        suggestions: list[str]
        normalized = user_message.lower()
        if any(keyword in user_message for keyword in ("开头", "第一章", "起手", "首章")):
            suggestions = [
                "先用一句话点明主角当前最想解决的问题，再立刻给出阻碍。",
                "首个场景只放一条主冲突，避免信息一次性铺太满。",
                "结尾补一个会逼读者继续看的悬念或代价。",
            ]
        elif any(keyword in user_message for keyword in ("大纲", "结构", "剧情", "主线")):
            suggestions = [
                "先拆出主线目标、阶段阻碍、阶段收益三段。",
                "每个关键节点都要对应一次角色选择，而不是纯事件推动。",
                "把下一章能直接落笔的场景顺序先列出来。",
            ]
        elif any(keyword in user_message for keyword in ("人物", "角色", "设定")):
            suggestions = [
                "先固定角色当前欲望、恐惧和对外展示出来的面具。",
                "每个关键角色最好只保留一个最能被读者记住的反差点。",
                "把角色设定和当前章节冲突绑在一起，而不是单独罗列。",
            ]
        elif any(keyword in normalized for keyword in ("summary", "summarize")) or "总结" in user_message:
            suggestions = [
                "先用一句话总结当前任务，再补三条最值得继续推进的点。",
                "如果你愿意，我下一轮可以把这份总结改写成章节计划。",
                "也可以直接把要处理的正文或设定贴过来，我会继续细化。",
            ]
        else:
            suggestions = [
                "先把你的目标压成一句最明确的写作任务。",
                "再补充这次最在意的限制，例如语气、篇幅、人物视角或剧情节点。",
                "我会基于当前项目上下文，继续把它展开成可直接落笔的内容。",
            ]

        lines = [
            "这是本地模式下生成的真实辅助回复。",
            f"我已经读取到的当前项目信息：{'；'.join(project_summary)}。",
        ]

        if user_message:
            lines.append(f"你这次要处理的问题是：{user_message}")

        if skill_headers:
            lines.append(f"当前已挂载的技能约束：{', '.join(skill_headers)}。")

        lines.append("建议你直接按下面三步继续：")
        for index, suggestion in enumerate(suggestions, start=1):
            lines.append(f"{index}. {suggestion}")

        lines.append("如果你继续发来更具体的片段、设定或目标，我会基于同一项目上下文继续往下细化。")
        return "\n".join(lines)

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
            elif self.config.generation_api_type == "local":
                result = self._complete_local_text(messages=messages)
            else:
                result = self._request_openai(messages=messages, expect_json=False)
            self.stats.total_calls += 1
            self.stats.total_time += time.time() - start
            return result
        except Exception:
            self.stats.errors += 1
            raise

    def complete_text_stream(
        self,
        *,
        messages: list[dict[str, str]],
        stub_text: str = "",
    ) -> Generator[str, None, None]:
        """Stream text completion, yielding content chunks as they arrive."""
        start = time.time()
        try:
            if self.config.generation_api_type == "stub":
                if stub_text:
                    yield stub_text
                self.stats.total_calls += 1
                self.stats.total_time += time.time() - start
                return

            if self.config.generation_api_type == "local":
                result = self._complete_local_text(messages=messages)
                for index in range(0, len(result), 80):
                    chunk = result[index:index + 80]
                    if chunk:
                        yield chunk
                self.stats.total_calls += 1
                self.stats.total_time += time.time() - start
                return

            if not self.config.generation_api_key:
                raise ValueError("GENERATION_API_KEY / OPENAI_API_KEY is required for openai generation mode")

            url = self._build_url()
            headers = self._build_headers()
            payload = self._build_payload(messages=messages, expect_json=False)
            payload["stream"] = True
            max_retries = getattr(self.config, "api_max_retries", 3)
            base_delay = getattr(self.config, "api_retry_delay", 1.0)

            yielded_any = False
            for attempt in range(max_retries):
                req = request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                try:
                    with request.urlopen(req, timeout=self.config.normal_timeout) as resp:
                        for raw_line in resp:
                            line = raw_line.decode("utf-8", errors="ignore").strip()
                            if not line or not line.startswith("data: "):
                                continue

                            data_str = line[6:]
                            if data_str.strip() == "[DONE]":
                                self.stats.total_calls += 1
                                self.stats.total_time += time.time() - start
                                return

                            try:
                                chunk = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue

                            choices = chunk.get("choices")
                            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                                continue

                            delta = choices[0].get("delta")
                            if not isinstance(delta, dict):
                                continue

                            content = delta.get("content")
                            if isinstance(content, str) and content:
                                yielded_any = True
                                yield content

                    self.stats.total_calls += 1
                    self.stats.total_time += time.time() - start
                    return
                except error.HTTPError as exc:
                    body = exc.read().decode("utf-8", errors="ignore")
                    if not yielded_any and exc.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                        time.sleep(base_delay * (2 ** attempt))
                        continue
                    if not yielded_any:
                        yield self.complete_text(messages=messages, stub_text=stub_text)
                        return
                    raise RuntimeError(f"generation HTTP {exc.code}: {body[:200]}") from exc
                except Exception:
                    if not yielded_any and attempt < max_retries - 1:
                        time.sleep(base_delay * (2 ** attempt))
                        continue
                    if not yielded_any:
                        yield self.complete_text(messages=messages, stub_text=stub_text)
                        return
                    raise

            if not yielded_any:
                yield self.complete_text(messages=messages, stub_text=stub_text)
                return
            raise RuntimeError("generation request exhausted retries")
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
            elif self.config.generation_api_type == "local":
                result = {
                    "mode": "local",
                    "reply": self._complete_local_text(messages=messages),
                }
            else:
                raw = self._request_openai(messages=messages, expect_json=True)
                result = _extract_json_object(raw)
            self.stats.total_calls += 1
            self.stats.total_time += time.time() - start
            return result
        except Exception:
            self.stats.errors += 1
            raise
