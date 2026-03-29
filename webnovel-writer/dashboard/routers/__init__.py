"""
Dashboard API routers package - M1 阶段：仅保留只读路由。

写接口已全部删除，由 CLI 统一入口 `webnovel codex` 承载。
"""

from .runtime import router as runtime_router

__all__ = [
    "runtime_router",
]
