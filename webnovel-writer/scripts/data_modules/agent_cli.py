#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_project_root_on_path() -> None:
    project_root = Path(__file__).resolve().parents[2]
    scripts_dir = project_root / "scripts"
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


def main(argv: list[str] | None = None) -> int:
    _ensure_project_root_on_path()
    from apps.cli.agent import main as app_main

    return app_main(argv)


if __name__ == "__main__":
    sys.exit(main())
