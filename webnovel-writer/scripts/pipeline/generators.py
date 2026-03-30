#!/usr/bin/env python3

from __future__ import annotations

import re
from typing import Any


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


def generate_plot(*, chapter_num: int, title: str, outline_text: str, revision_number: int) -> dict[str, Any]:
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


def generate_events(*, plot_payload: dict[str, Any], revision_number: int) -> dict[str, Any]:
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


def generate_scenes(*, events_payload: dict[str, Any], revision_number: int) -> dict[str, Any]:
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


def generate_chapter_markdown(*, title: str, chapter_num: int, scenes_payload: dict[str, Any], context_payload: dict[str, Any], revision_number: int) -> str:
    lines = [f"# 第{chapter_num}章：{title}", "", f"> Pipeline Draft v{revision_number}", ""]
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
