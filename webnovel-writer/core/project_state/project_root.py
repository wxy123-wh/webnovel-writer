from __future__ import annotations

from pathlib import Path


def resolve_project_root(explicit_root: str | None) -> Path:
    if explicit_root:
        root = Path(explicit_root).expanduser().resolve()
        if not (root / ".webnovel" / "state.json").exists():
            raise FileNotFoundError(f"项目根目录无效（缺少 .webnovel/state.json）: {root}")
        return root

    cwd = Path.cwd()
    for candidate in (cwd, *cwd.parents):
        if (candidate / ".webnovel" / "state.json").exists():
            return candidate.resolve()
    raise FileNotFoundError("无法找到项目根目录，请使用 --project-root 指定")
