"""
Dashboard API model package - M1 阶段：仅保留只读查询模型。

写接口模型已全部删除。
"""

from .common import ApiErrorResponse, PageQuery, WorkspaceContext
from .runtime import (
    RuntimeProfileQuery,
    RuntimeProfileResponse,
)

__all__ = [
    "ApiErrorResponse",
    "PageQuery",
    "WorkspaceContext",
    "RuntimeProfileQuery",
    "RuntimeProfileResponse",
]
