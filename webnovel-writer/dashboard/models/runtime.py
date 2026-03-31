"""
Runtime API models - M1 阶段：仅保留只读查询模型。

写接口（迁移相关）已全部删除。
"""

from typing import Any

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


class RuntimeGenerationState(BaseModel):
    provider: str = Field(default="local")
    configured: bool = Field(default=True)
    api_key_configured: bool = Field(default=False)
    model: str = Field(default="")
    base_url: str = Field(default="")


class RuntimeProjectSummary(BaseModel):
    title: str = Field(default="")
    genre: str = Field(default="")
    current_chapter: str = Field(default="")


class RuntimeMigrationPreview(BaseModel):
    moved: list[dict[str, Any]] = Field(default_factory=list)
    removed: list[dict[str, Any]] = Field(default_factory=list)
    skipped: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: str = Field(default="")
    dry_run: bool = Field(default=True)
    project_root: str = Field(default="")
    migratable_items: int = Field(default=0, ge=0)


class RuntimeProfileResponse(BaseModel):
    runtime_name: str = Field(default="codex")
    workspace: WorkspaceContext
    pointer: RuntimePointerState
    legacy: RuntimeLegacyState
    generation: RuntimeGenerationState
    project: RuntimeProjectSummary
    migration_preview: RuntimeMigrationPreview
