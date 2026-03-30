from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .chat_skill_models import ChatSkill


class ChatSkillRegistry:
    def __init__(self, project_root: Path | None = None):
        self.project_root = Path(project_root) if project_root is not None else None
        self._base = Path(__file__).resolve().parents[2]

    def get_skill_content(self, skill_id: str) -> str | None:
        skill_md = self._base / "skills" / skill_id / "SKILL.md"
        if not skill_md.is_file():
            return None
        try:
            return skill_md.read_text(encoding="utf-8")
        except OSError:
            return None

    def list_all(self) -> list[dict[str, Any]]:
        skills: dict[str, ChatSkill] = {}

        skills_dir = self._base / "skills"
        if skills_dir.exists():
            for directory in sorted(skills_dir.iterdir(), key=lambda item: item.name.lower()):
                if not directory.is_dir() or directory.name.startswith((".", "_")):
                    continue
                skill_md = directory / "SKILL.md"
                if not skill_md.is_file():
                    continue
                name, desc = self._parse_skill_md(skill_md)
                skills[f"system:{directory.name}"] = ChatSkill(
                    skill_id=directory.name,
                    name=name,
                    description=desc,
                    source="system",
                )

        profiles_dir = self._base / "scripts" / "codex_skill_profiles"
        if profiles_dir.exists():
            for directory in sorted(profiles_dir.iterdir(), key=lambda item: item.name.lower()):
                if not directory.is_dir() or directory.name.startswith((".", "_")):
                    continue
                readme = directory / "README.md"
                description = ""
                if readme.is_file():
                    lines = readme.read_text(encoding="utf-8").strip().splitlines()
                    description = next((line.strip() for line in lines if line.strip() and not line.startswith("#")), "")
                skills[f"profile:{directory.name}"] = ChatSkill(
                    skill_id=directory.name,
                    name=directory.name.title(),
                    description=description,
                    source="profile",
                )

        if self.project_root is not None:
            registry_path = self.project_root / ".webnovel" / "skills" / "registry.json"
            if registry_path.is_file():
                try:
                    data = json.loads(registry_path.read_text(encoding="utf-8"))
                    items = data if isinstance(data, list) else data.get("skills", [])
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        skill_id = str(item.get("id") or "").strip()
                        if not skill_id:
                            continue
                        skills[f"workspace:{skill_id}"] = ChatSkill(
                            skill_id=skill_id,
                            name=str(item.get("name") or skill_id),
                            description=str(item.get("description") or ""),
                            source="workspace",
                            enabled=bool(item.get("enabled", True)),
                            needs_approval=bool(item.get("needs_approval", False)),
                        )
                except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
                    pass

        return [skill.to_dict() for skill in skills.values()]

    def _parse_skill_md(self, path: Path) -> tuple[str, str]:
        content = path.read_text(encoding="utf-8")
        name = path.parent.name
        description = ""

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().splitlines():
                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip().strip('"\'')
                    elif line.startswith("description:"):
                        description = line.split(":", 1)[1].strip().strip('"\'')

        return name, description
