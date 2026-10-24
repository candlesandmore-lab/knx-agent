"""Pure session-state model and session_label rule (no I/O)."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .project_graph import ImportWarning

MAX_PERSISTED_WARNINGS = 200
GRAPH_FILE_NAME = "project-graph.json"
DEFAULT_SETUP = "default"
LOG_BOOK_FILE_NAME = "session-log-book.jsonl"

_LABEL_PATTERN = re.compile(r"[A-Za-z0-9_-]+")


def is_valid_session_label(label: object) -> bool:
    """A session_label is non-empty and uses ASCII letters, digits, '-' and '_' only."""
    return isinstance(label, str) and _LABEL_PATTERN.fullmatch(label) is not None


class ApplicationProgramCounts(BaseModel):
    """Distinct application programs referenced by components, read, and unreadable."""

    model_config = ConfigDict(extra="forbid")

    referenced: int = 0
    read: int = 0
    unreadable: int = 0


class ProjectImportSummary(BaseModel):
    """What the import recorded about the .knxproj (003 'project_import_summary').

    Same field names as the contracts model. Sessions of story 03 (which stored ``limitation_note``) are not
    migrated: their state file no longer validates and the session must be recreated.
    """

    model_config = ConfigDict(extra="forbid")

    file_name: str
    archive_entry_count: int
    ets_tool_version: str | None = None
    schema_namespace: str | None = None
    created_by: str | None = None
    project_id: str | None = None
    project_name: str | None = None
    group_address_style: str | None = None
    node_counts: dict[str, int] = Field(default_factory=dict)
    relation_counts: dict[str, int] = Field(default_factory=dict)
    component_type_counts: dict[str, int] = Field(default_factory=dict)
    application_programs: ApplicationProgramCounts = Field(default_factory=ApplicationProgramCounts)
    warning_total: int = 0
    warning_counts: dict[str, int] = Field(default_factory=dict)
    graph_file: str | None = None
    graph_schema_version: int | None = None


class ProjectImport(BaseModel):
    """Metadata of the bound .knxproj as last imported (story 04 shape, 003 'Persistence')."""

    model_config = ConfigDict(extra="forbid")

    path: str
    mtime: int  # integer nanoseconds
    size: int  # bytes
    imported_at: str
    fingerprint: str | None = None  # SHA-256 hex of the file bytes; null is treated as CHANGED by the refresh check
    graph_file: str | None = None  # relative name inside the work-directory
    graph_schema_version: int | None = None
    project_import_summary: ProjectImportSummary
    warnings: list[ImportWarning] = Field(default_factory=list)  # first MAX_PERSISTED_WARNINGS


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
