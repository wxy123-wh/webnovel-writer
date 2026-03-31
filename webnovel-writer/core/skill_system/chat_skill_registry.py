from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .chat_skill_models import ChatSkill


SKILL_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class WorkspaceSkillValidationError(ValueError):
    def __init__(self, field_errors: dict[str, str]):
        super().__init__("invalid workspace skill payload")
        self.field_errors = field_errors


class WorkspaceSkillConflictError(ValueError):
    def __init__(self, skill_id: str):
        super().__init__(skill_id)
        self.skill_id = skill_id


class WorkspaceSkillNotFoundError(KeyError):
    def __init__(self, skill_id: str):
        super().__init__(skill_id)
        self.skill_id = skill_id


class ChatSkillRegistry:
    def __init__(self, project_root: Path | None = None):
        self.project_root = Path(project_root) if project_root is not None else None
        self._base = Path(__file__).resolve().parents[2]

    def get_skill_content(self, skill_id: str, *, source: str = "system") -> str | None:
        content_path: Path | None = None
        if source == "system":
            content_path = self._base / "skills" / skill_id / "SKILL.md"
        elif source == "workspace" and self.project_root is not None:
            content_path = self.project_root / ".webnovel" / "skills" / skill_id / "SKILL.md"
        elif source == "profile":
            content_path = self._base / "scripts" / "codex_skill_profiles" / skill_id / "README.md"

        if content_path is None or not content_path.is_file():
            return None

        try:
            return content_path.read_text(encoding="utf-8")
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

        for item in self.list_workspace():
            skill_id = str(item.get("skill_id") or "").strip()
            if not skill_id:
                continue
            skills[f"workspace:{skill_id}"] = ChatSkill(
                skill_id=skill_id,
                name=str(item.get("name") or skill_id),
                description=str(item.get("description") or ""),
                source="workspace",
                enabled=bool(item.get("enabled", True)),
                needs_approval=bool(item.get("needs_approval", False)),
                updated_at=str(item.get("updated_at") or "") or None,
            )

        return [skill.to_dict() for skill in skills.values()]

    def list_workspace(self) -> list[dict[str, Any]]:
        items = self._load_workspace_registry_items()
        normalized: list[dict[str, Any]] = []
        for item in items:
            skill_id = str(item.get("id") or item.get("skill_id") or "").strip()
            if not skill_id:
                continue
            normalized.append(
                {
                    "skill_id": skill_id,
                    "name": str(item.get("name") or skill_id),
                    "description": str(item.get("description") or ""),
                    "source": "workspace",
                    "enabled": bool(item.get("enabled", True)),
                    "needs_approval": bool(item.get("needs_approval", False)),
                    "updated_at": str(item.get("updated_at") or "") or None,
                }
            )
        normalized.sort(key=lambda item: (str(item.get("name") or "").lower(), str(item.get("skill_id") or "").lower()))
        return normalized

    def create_workspace_skill(
        self,
        *,
        skill_id: str,
        name: str,
        description: str = "",
        instruction_template: str,
    ) -> dict[str, Any]:
        if self.project_root is None:
            raise RuntimeError("project_root is required for workspace skill writes")

        normalized_skill_id = skill_id.strip().lower()
        normalized_name = name.strip()
        normalized_description = description.strip()
        normalized_template = instruction_template.strip()

        field_errors: dict[str, str] = {}
        if not normalized_skill_id or not SKILL_ID_RE.fullmatch(normalized_skill_id):
            field_errors["skill_id"] = "Use lowercase letters, numbers, and hyphens only."
        if not normalized_name:
            field_errors["name"] = "Name is required."
        if not normalized_template:
            field_errors["instruction_template"] = "Instruction template is required."
        if field_errors:
            raise WorkspaceSkillValidationError(field_errors)

        items = self._load_workspace_registry_items()
        if any(str(item.get("id") or item.get("skill_id") or "").strip() == normalized_skill_id for item in items):
            raise WorkspaceSkillConflictError(normalized_skill_id)

        skill_dir = self._workspace_skills_dir() / normalized_skill_id
        if skill_dir.exists():
            raise WorkspaceSkillConflictError(normalized_skill_id)

        updated_at = self._utc_now_iso()
        skill_dir.mkdir(parents=True, exist_ok=False)
        (skill_dir / "SKILL.md").write_text(f"{normalized_template}\n", encoding="utf-8")

        items.append(
            {
                "id": normalized_skill_id,
                "name": normalized_name,
                "description": normalized_description,
                "enabled": True,
                "needs_approval": False,
                "updated_at": updated_at,
            }
        )
        self._write_workspace_registry_items(items)

        return {
            "skill_id": normalized_skill_id,
            "name": normalized_name,
            "description": normalized_description,
            "source": "workspace",
            "enabled": True,
            "needs_approval": False,
            "updated_at": updated_at,
        }

    def delete_workspace_skill(self, skill_id: str) -> None:
        if self.project_root is None:
            raise RuntimeError("project_root is required for workspace skill writes")

        normalized_skill_id = skill_id.strip().lower()
        items = self._load_workspace_registry_items()
        remaining = [
            item
            for item in items
            if str(item.get("id") or item.get("skill_id") or "").strip() != normalized_skill_id
        ]
        if len(remaining) == len(items):
            raise WorkspaceSkillNotFoundError(normalized_skill_id)

        skill_dir = self._workspace_skills_dir() / normalized_skill_id
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
        self._write_workspace_registry_items(remaining)

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

    def _workspace_skills_dir(self) -> Path:
        if self.project_root is None:
            raise RuntimeError("project_root is required for workspace skills")
        return self.project_root / ".webnovel" / "skills"

    def _workspace_registry_path(self) -> Path:
        return self._workspace_skills_dir() / "registry.json"

    def _load_workspace_registry_items(self) -> list[dict[str, Any]]:
        if self.project_root is None:
            return []

        registry_path = self._workspace_registry_path()
        if not registry_path.is_file():
            return []

        try:
            data = json.loads(registry_path.read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else data.get("items", data.get("skills", []))
        except (json.JSONDecodeError, AttributeError, TypeError, ValueError, OSError):
            return []

        return [item for item in items if isinstance(item, dict)]

    def _write_workspace_registry_items(self, items: list[dict[str, Any]]) -> None:
        skills_dir = self._workspace_skills_dir()
        skills_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "items": sorted(
                items,
                key=lambda item: str(item.get("name") or item.get("id") or item.get("skill_id") or "").lower(),
            ),
        }
        self._workspace_registry_path().write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
