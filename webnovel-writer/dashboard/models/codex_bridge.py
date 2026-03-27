"""
Codex split dialog bridge models.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import WorkspaceContext


class CodexSplitDialogOpenRequest(BaseModel):
    workspace: WorkspaceContext = Field(default_factory=WorkspaceContext)
    selection_start: int = Field(default=0, ge=0)
    selection_end: int = Field(default=0, ge=0)
    selection_text: str = Field(default="")


class CodexSplitDialogOpenResponse(BaseModel):
    status: str = Field(default="ok")
    launched: bool = Field(default=True)
    message: str = Field(default="Codex CLI session launched")
    prompt_file: str = Field(default="")


class CodexFileEditDialogOpenRequest(BaseModel):
    workspace: WorkspaceContext = Field(default_factory=WorkspaceContext)
    file_path: str = Field(default="")
    selection_start: int = Field(default=0, ge=0)
    selection_end: int = Field(default=0, ge=0)
    selection_text: str = Field(default="")
    instruction: str = Field(default="")
    source_id: str = Field(default="")


class CodexFileEditDialogOpenResponse(BaseModel):
    status: str = Field(default="ok")
    launched: bool = Field(default=True)
    message: str = Field(default="Codex CLI file-edit session launched")
    prompt_file: str = Field(default="")
    target_file: str = Field(default="")
