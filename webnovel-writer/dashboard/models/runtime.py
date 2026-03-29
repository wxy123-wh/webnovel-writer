"""
Runtime API models - M1 阶段：仅保留只读查询模型。

写接口（迁移相关）已全部删除。
"""

from pydantic import BaseModel, Field

from .common import WorkspaceContext


class RuntimeProfileQuery(BaseModel):
    workspace_id: str = Field(default="workspace-default")
    project_root: str = Field(default="")


class RuntimePointerFileState(BaseModel):
    path: str
    exists: bool = Field(default=False)
    target: str | None = Field(default=None)
    target_exists: bool | None = Field(default=None)
    target_is_project_root: bool | None = Field(default=None)
    read_error: str | None = Field(default=None)


class RuntimePointerState(BaseModel):
    workspace_root: str
    status: str
    has_conflict: bool = Field(default=False)
    codex: RuntimePointerFileState
    legacy: RuntimePointerFileState


class RuntimeLegacyState(BaseModel):
    workspace_legacy_dir: str
    workspace_legacy_dir_exists: bool = Field(default=False)
    project_legacy_dir: str
    project_legacy_dir_exists: bool = Field(default=False)
    project_legacy_references_dir: str
    project_legacy_references_exists: bool = Field(default=False)
    project_legacy_reference_files: int = Field(default=0, ge=0)


class RuntimeProfileResponse(BaseModel):
    runtime_name: str = Field(default="codex")
    workspace: WorkspaceContext
    pointer: RuntimePointerState
    legacy: RuntimeLegacyState
