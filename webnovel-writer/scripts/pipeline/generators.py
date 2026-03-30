#!/usr/bin/env python3

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

try:
    from data_modules.generation_client import GenerationAPIClient
except ImportError:  # pragma: no cover
    from scripts.data_modules.generation_client import GenerationAPIClient


def _clean_outline_lines(outline_text: str) -> list[str]:
    lines: list[str] = []
    for raw in outline_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        line = re.sub(r"^[-*+]\s*", "", line)
        line = re.sub(r"^\d+[.)、]\s*", "", line)
        if line:
            lines.append(line)
    return lines


def _pick(items: list[str], index: int, fallback: str) -> str:
    if not items:
        return fallback
    return items[index % len(items)]


def _active_profile_guidance() -> str:
    profile = (os.getenv("WEBNOVEL_AGENT_PROFILE") or "").strip()
    if not profile:
        return ""

    base_dir = Path(__file__).resolve().parents[1] / "codex_skill_profiles" / profile
    parts: list[str] = []
    for name in ("README.md", "rules.md"):
        file_path = base_dir / name
        if file_path.is_file():
            try:
                parts.append(file_path.read_text(encoding="utf-8").strip())
            except Exception:
                continue
    return "\n\n".join(part for part in parts if part)


def _messages(*, stage: str, body: str, expect_json: bool) -> list[dict[str, str]]:
    profile_guidance = _active_profile_guidance()
    system_parts = [
        "You are Webnovel Writer Agent, a long-form Chinese webnovel writing assistant.",
        "You must preserve chapter intent, avoid contradictions, and return production-ready content.",
    ]
    if expect_json:
        system_parts.append("Return strictly valid JSON only. Do not wrap the response in markdown fences.")
    else:
        system_parts.append("Return the requested chapter draft directly in markdown.")
    if profile_guidance:
        system_parts.append("Active profile guidance:\n" + profile_guidance)

    return [
        {"role": "system", "content": "\n\n".join(system_parts)},
        {"role": "user", "content": f"[STAGE]\n{stage}\n\n{body.strip()}"},
    ]


def _normalize_plot_payload(content: dict[str, Any], *, chapter_num: int, title: str, outline_text: str, revision_number: int) -> dict[str, Any]:
    fallback = _generate_plot_template(chapter_num=chapter_num, title=title, outline_text=outline_text, revision_number=revision_number)
    beats = content.get("beats") if isinstance(content.get("beats"), list) else fallback["beats"]
    normalized_beats: list[dict[str, str]] = []
    for index, raw in enumerate(beats[:4], start=1):
        item = raw if isinstance(raw, dict) else {}
        fallback_item = fallback["beats"][index - 1]
        normalized_beats.append(
            {
                "id": str(item.get("id") or fallback_item["id"]),
                "label": str(item.get("label") or fallback_item["label"]),
                "purpose": str(item.get("purpose") or fallback_item["purpose"]),
                "twist": str(item.get("twist") or fallback_item["twist"]),
            }
        )
    while len(normalized_beats) < 4:
        normalized_beats.append(fallback["beats"][len(normalized_beats)])

    return {
        "chapter": chapter_num,
        "title": title,
        "premise": str(content.get("premise") or fallback["premise"]),
        "central_conflict": str(content.get("central_conflict") or fallback["central_conflict"]),
        "target_emotion": str(content.get("target_emotion") or fallback["target_emotion"]),
        "beats": normalized_beats,
    }


def _normalize_events_payload(content: dict[str, Any], *, plot_payload: dict[str, Any], revision_number: int) -> dict[str, Any]:
    fallback = _generate_events_template(plot_payload=plot_payload, revision_number=revision_number)
    events = content.get("events") if isinstance(content.get("events"), list) else fallback["events"]
    normalized_events: list[dict[str, str]] = []
    for index, raw in enumerate(events[: len(fallback["events"])], start=1):
        item = raw if isinstance(raw, dict) else {}
        fallback_item = fallback["events"][index - 1]
        normalized_events.append(
            {
                "id": str(item.get("id") or fallback_item["id"]),
                "title": str(item.get("title") or fallback_item["title"]),
                "objective": str(item.get("objective") or fallback_item["objective"]),
                "conflict": str(item.get("conflict") or fallback_item["conflict"]),
                "turning_point": str(item.get("turning_point") or fallback_item["turning_point"]),
                "intensity": str(item.get("intensity") or fallback_item["intensity"]),
            }
        )
    while len(normalized_events) < len(fallback["events"]):
        normalized_events.append(fallback["events"][len(normalized_events)])

    return {
        "chapter": plot_payload.get("chapter"),
        "title": plot_payload.get("title"),
        "events": normalized_events,
    }


def _normalize_scenes_payload(content: dict[str, Any], *, events_payload: dict[str, Any], revision_number: int) -> dict[str, Any]:
    fallback = _generate_scenes_template(events_payload=events_payload, revision_number=revision_number)
    scenes = content.get("scenes") if isinstance(content.get("scenes"), list) else fallback["scenes"]
    normalized_scenes: list[dict[str, str]] = []
    for index, raw in enumerate(scenes[: len(fallback["scenes"])], start=1):
        item = raw if isinstance(raw, dict) else {}
        fallback_item = fallback["scenes"][index - 1]
        normalized_scenes.append(
            {
                "id": str(item.get("id") or fallback_item["id"]),
                "title": str(item.get("title") or fallback_item["title"]),
                "location": str(item.get("location") or fallback_item["location"]),
                "goal": str(item.get("goal") or fallback_item["goal"]),
                "conflict": str(item.get("conflict") or fallback_item["conflict"]),
                "outcome": str(item.get("outcome") or fallback_item["outcome"]),
                "transition": str(item.get("transition") or fallback_item["transition"]),
            }
        )
    while len(normalized_scenes) < len(fallback["scenes"]):
        normalized_scenes.append(fallback["scenes"][len(normalized_scenes)])

    return {
        "chapter": events_payload.get("chapter"),
        "title": events_payload.get("title"),
        "scenes": normalized_scenes,
    }


def _generate_plot_template(*, chapter_num: int, title: str, outline_text: str, revision_number: int) -> dict[str, Any]:
    lines = _clean_outline_lines(outline_text)
    base_points = lines[:4]
    if len(base_points) < 4:
        fallback = [
            "主角被迫进入新的局面",
            "冲突升级并暴露新的风险",
            "局势在关键节点发生转折",
            "结尾留下下一章钩子",
        ]
        while len(base_points) < 4:
            base_points.append(fallback[len(base_points)])

    tone_cycle = ["压迫感", "悬念感", "爽点感", "反差感"]
    return {
        "chapter": chapter_num,
        "title": title,
        "premise": _pick(base_points, revision_number - 1, "围绕章节目标推进剧情"),
        "central_conflict": _pick(base_points, revision_number, "主角必须在代价与收益之间做选择"),
        "target_emotion": tone_cycle[(revision_number - 1) % len(tone_cycle)],
        "beats": [
            {
                "id": f"beat-{index + 1}",
                "label": label,
                "purpose": point,
                "twist": f"第{index + 1}拍在信息或立场上制造偏移",
            }
            for index, (label, point) in enumerate(
                zip(["开场钩子", "推进冲突", "局势反转", "章末钩子"], base_points, strict=False)
            )
        ],
    }


def _generate_events_template(*, plot_payload: dict[str, Any], revision_number: int) -> dict[str, Any]:
    beats = plot_payload.get("beats") or []
    intensity_cycle = ["铺垫", "碰撞", "升级", "兑现"]
    events = []
    for index, beat in enumerate(beats, start=1):
        purpose = str(beat.get("purpose") or f"事件{index}推进剧情")
        events.append(
            {
                "id": f"event-{index}",
                "title": f"事件{index}：{purpose[:18]}",
                "objective": purpose,
                "conflict": f"围绕“{purpose[:12]}”产生阻力与代价",
                "turning_point": str(beat.get("twist") or "局势发生偏移"),
                "intensity": intensity_cycle[(index + revision_number - 2) % len(intensity_cycle)],
            }
        )
    return {
        "chapter": plot_payload.get("chapter"),
        "title": plot_payload.get("title"),
        "events": events,
    }


def _generate_scenes_template(*, events_payload: dict[str, Any], revision_number: int) -> dict[str, Any]:
    locations = ["当前地点", "过渡地点", "冲突现场", "余波现场"]
    scenes = []
    for index, event in enumerate(events_payload.get("events") or [], start=1):
        objective = str(event.get("objective") or f"推进事件{index}")
        scenes.append(
            {
                "id": f"scene-{index}",
                "title": f"场景{index}：{str(event.get('title') or objective)[:18]}",
                "location": locations[(index + revision_number - 2) % len(locations)],
                "goal": objective,
                "conflict": str(event.get("conflict") or "人物目标受到阻碍"),
                "outcome": f"场景{index}结束时，局势向下一事件推进",
                "transition": f"将读者带向第{index + 1}个节点",
            }
        )
    return {
        "chapter": events_payload.get("chapter"),
        "title": events_payload.get("title"),
        "scenes": scenes,
    }


def _generate_chapter_template(*, title: str, chapter_num: int, scenes_payload: dict[str, Any], context_payload: dict[str, Any], revision_number: int) -> str:
    lines = [f"# 第{chapter_num}章：{title}", "", f"> Agent Draft v{revision_number}", ""]
    state_summary = str(context_payload.get("state_summary") or "").strip()
    if state_summary:
        lines.extend(["## 上下文摘要", state_summary, ""])
    guidance_items = context_payload.get("writing_guidance", {}).get("guidance_items", [])
    if guidance_items:
        lines.append("## 写作提示")
        for item in guidance_items[:3]:
            text = item if isinstance(item, str) else str(item)
            lines.append(f"- {text}")
        lines.append("")

    for index, scene in enumerate(scenes_payload.get("scenes") or [], start=1):
        lines.extend(
            [
                f"## 场景{index}：{scene.get('title')}",
                f"地点：{scene.get('location')}",
                "",
                f"主角带着“{scene.get('goal')}”进入场景，先感受到环境与人物关系的变化。",
                f"随后冲突迅速显形：{scene.get('conflict')}。",
                f"在本场景的收束处，{scene.get('outcome')}，并自然衔接到下一段：{scene.get('transition')}。",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def generate_plot(*, chapter_num: int, title: str, outline_text: str, revision_number: int) -> dict[str, Any]:
    fallback = _generate_plot_template(
        chapter_num=chapter_num,
        title=title,
        outline_text=outline_text,
        revision_number=revision_number,
    )
    client = GenerationAPIClient()
    body = f"""
章节号：{chapter_num}
章节标题：{title}
章节大纲：
{outline_text}

请输出剧情设计 JSON，结构必须包含：
- premise: string
- central_conflict: string
- target_emotion: string
- beats: 4 items，每项包含 id,label,purpose,twist
"""
    content = client.complete_json(
        messages=_messages(stage="plot", body=body, expect_json=True),
        stub_payload=fallback,
    )
    return _normalize_plot_payload(
        content,
        chapter_num=chapter_num,
        title=title,
        outline_text=outline_text,
        revision_number=revision_number,
    )


def generate_events(*, plot_payload: dict[str, Any], revision_number: int) -> dict[str, Any]:
    fallback = _generate_events_template(plot_payload=plot_payload, revision_number=revision_number)
    client = GenerationAPIClient()
    body = f"""
当前 plot JSON：
{json_like(plot_payload)}

请输出事件设计 JSON，结构必须包含：
- events: array
- 每项包含 id,title,objective,conflict,turning_point,intensity
"""
    content = client.complete_json(
        messages=_messages(stage="events", body=body, expect_json=True),
        stub_payload=fallback,
    )
    return _normalize_events_payload(content, plot_payload=plot_payload, revision_number=revision_number)


def generate_scenes(*, events_payload: dict[str, Any], revision_number: int) -> dict[str, Any]:
    fallback = _generate_scenes_template(events_payload=events_payload, revision_number=revision_number)
    client = GenerationAPIClient()
    body = f"""
当前 events JSON：
{json_like(events_payload)}

请输出场景设计 JSON，结构必须包含：
- scenes: array
- 每项包含 id,title,location,goal,conflict,outcome,transition
"""
    content = client.complete_json(
        messages=_messages(stage="scenes", body=body, expect_json=True),
        stub_payload=fallback,
    )
    return _normalize_scenes_payload(content, events_payload=events_payload, revision_number=revision_number)


def generate_chapter_markdown(*, title: str, chapter_num: int, scenes_payload: dict[str, Any], context_payload: dict[str, Any], revision_number: int) -> str:
    fallback = _generate_chapter_template(
        title=title,
        chapter_num=chapter_num,
        scenes_payload=scenes_payload,
        context_payload=context_payload,
        revision_number=revision_number,
    )
    client = GenerationAPIClient()
    body = f"""
章节号：{chapter_num}
章节标题：{title}

当前 scenes JSON：
{json_like(scenes_payload)}

上下文 JSON：
{json_like(context_payload)}

请直接输出完整中文 Markdown 章节草稿。不要解释，不要输出 JSON。
"""
    result = client.complete_text(
        messages=_messages(stage="chapter", body=body, expect_json=False),
        stub_text=fallback,
    ).strip()
    return (result or fallback).rstrip() + "\n"


def summarize_content(stage: str, content: Any) -> str:
    if stage == "plot" and isinstance(content, dict):
        return str(content.get("premise") or "plot generated")
    if stage == "events" and isinstance(content, dict):
        events = content.get("events") or []
        return f"{len(events)} events"
    if stage == "scenes" and isinstance(content, dict):
        scenes = content.get("scenes") or []
        return f"{len(scenes)} scenes"
    if isinstance(content, str):
        first_line = content.strip().splitlines()[0] if content.strip() else "chapter draft"
        return first_line[:80]
    return f"{stage} revision"


def json_like(payload: Any) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2)
