"""Pure session-state model and session_label rule (no I/O)."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LIMITATION_NOTE = ".knxproj content import is not implemented yet"
DEFAULT_SETUP = "default"
LOG_BOOK_FILE_NAME = "session-log-book.jsonl"

_LABEL_PATTERN = re.compile(r"[A-Za-z0-9_-]+")


def is_valid_session_label(label: object) -> bool:
    """A session_label is non-empty and uses ASCII letters, digits, '-' and '_' only."""
    return isinstance(label, str) and _LABEL_PATTERN.fullmatch(label) is not None


class ProjectImportSummary(BaseModel):
    """What the import recorded about the .knxproj archive (no content parsing yet)."""

    model_config = ConfigDict(extra="forbid")

    file_name: str
    archive_entry_count: int
    limitation_note: str = LIMITATION_NOTE


class ProjectImport(BaseModel):
    """Metadata of the bound .knxproj as last imported."""

    model_config = ConfigDict(extra="forbid")

    path: str
    mtime: int  # integer nanoseconds
    size: int  # bytes
    imported_at: str
    project_import_summary: ProjectImportSummary
    fingerprint: None = None  # stays null until todo 04


class ProjectRefresh(BaseModel):
    """Outcome bookkeeping of the project refresh check."""

    model_config = ConfigDict(extra="forbid")

    last_status: Literal["CHANGED", "UNCHANGED"] = "UNCHANGED"
    last_reimported_at: str | None = None
    reimport_count: int = 0


class SessionState(BaseModel):
    """Content of session-state.yaml (field order is the file's key order)."""

    model_config = ConfigDict(extra="forbid")

    session_label: str
    created_at: str
    work_directory: str
    source_project_absolute_path: str
    project_import: ProjectImport
    project_refresh: ProjectRefresh = Field(default_factory=ProjectRefresh)
    active_setup: str = DEFAULT_SETUP
    trace_artifacts: list[dict[str, object]] = Field(default_factory=list)
    scenario_state: list[dict[str, object]] = Field(default_factory=list)
    mutations: list[dict[str, object]] = Field(default_factory=list)
    log_book_references: list[str] = Field(default_factory=lambda: [LOG_BOOK_FILE_NAME])
    mutation_log_book_references: dict[str, str] = Field(default_factory=dict)
