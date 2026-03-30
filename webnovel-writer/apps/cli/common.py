from __future__ import annotations

import json
import sys
from typing import Any, TextIO


def emit_json(payload: dict[str, Any], *, exit_code: int = 0, stream: TextIO | None = None) -> int:
    target = stream or sys.stdout
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=target)
    return exit_code


def emit_error(error_code: str, message: str, *, exit_code: int = 1, stream: TextIO | None = None) -> int:
    return emit_json({"status": "error", "error_code": error_code, "message": message}, exit_code=exit_code, stream=stream or sys.stderr)
