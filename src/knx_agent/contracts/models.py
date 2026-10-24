"""Common response envelope (C7), error shape and the session capability contracts (1-3)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ERROR_LEVEL = "ERROR"  # log book level for issues; always written, not a configurable threshold


class EvidenceKind(StrEnum):
    """Origin kinds of an evidence source (C7)."""

    KNXPROJ = "KNXPROJ"
    TRACE = "TRACE"
    USER_INPUT = "USER_INPUT"
    VENDOR_DOCUMENTATION = "VENDOR_DOCUMENTATION"
    SIMULATION_RULE = "SIMULATION_RULE"


class DetailLevel(StrEnum):
    """Detail level of descriptive capabilities."""

    SUMMARY = "SUMMARY"
    MEDIUM = "MEDIUM"
    FULL = "FULL"


class LogLevel(StrEnum):
    """Configurable log level (C6): INFO < DEBUG < FULL."""

    INFO = "INFO"
    DEBUG = "DEBUG"
    FULL = "FULL"

    @property
    def rank(self) -> int:
        """Ordering value: INFO=1, DEBUG=2, FULL=3."""
        return {"INFO": 1, "DEBUG": 2, "FULL": 3}[self.value]

    def __lt__(self, other: object) -> bool:
        return self.rank < LogLevel(other).rank

    def __le__(self, other: object) -> bool:
        return self.rank <= LogLevel(other).rank

    def __gt__(self, other: object) -> bool:
        return self.rank > LogLevel(other).rank

    def __ge__(self, other: object) -> bool:
        return self.rank >= LogLevel(other).rank


class EvidenceSource(BaseModel):
    """One evidence source of a result element."""

    model_config = ConfigDict(extra="forbid")

    kind: EvidenceKind
    reference: str


class ResponseEnvelope(BaseModel):
    """Common response envelope: setup, evidence_sources, limitation_notes and optional echoes."""

    model_config = ConfigDict(extra="forbid")

    setup: str | None = None
    evidence_sources: list[EvidenceSource] = Field(default_factory=list)
    limitation_notes: list[str] = Field(default_factory=list)
    log_book_entry_id: int | None = None
    detail_level: DetailLevel | None = None


class ErrorInfo(BaseModel):
    """Error shape: code, message and optional details."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, object] | None = None


class ImportWarning(BaseModel):  # noqa: A001 - name fixed by the spec
    """One import warning: code, one-sentence message, location (zip entry or '<zip entry>#<ETS id>')."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    location: str


class ApplicationProgramCounts(BaseModel):
    """application_programs block of the summary: distinct programs referenced, read and unreadable."""

    model_config = ConfigDict(extra="forbid")

    referenced: int = 0
    read: int = 0
    unreadable: int = 0


class ProjectImportSummary(BaseModel):
    """Summary of the project import (003 'project_import_summary')."""

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


class ProjectChange(BaseModel):
    """One entry of reimport_system_definition.changes (component or group address)."""

    model_config = ConfigDict(extra="forbid")

    entity: Literal["component", "group_address"]
    change: Literal["added", "removed", "changed"]
    id: str
    label: str
    details: dict[str, object] = Field(default_factory=dict)


class InvalidatedReference(BaseModel):
    """A scenario_state or mutation entry that names a component or group address removed by a re-import."""

    model_config = ConfigDict(extra="forbid")

    reference_kind: Literal["scenario_state", "mutation_delta"]
    owner: str
    component_id: str | None = None
    group_address_id: str | None = None
    reason: Literal["COMPONENT_REMOVED", "GROUP_ADDRESS_REMOVED"]


class ProjectImportInfo(BaseModel):
    """project_import block of describe_session (read from session-state.yaml only)."""

    model_config = ConfigDict(extra="forbid")

    imported_at: str
    fingerprint: str | None = None
    graph_file: str | None = None  # absolute path
    project_import_summary: ProjectImportSummary


class ProjectRefreshInfo(BaseModel):
    """project_refresh block of describe_session."""

    model_config = ConfigDict(extra="forbid")

    last_status: Literal["CHANGED", "UNCHANGED"]
    last_reimported_at: str | None = None
    reimport_count: int = 0


class SetupSummary(BaseModel):
    """One setup (default plus mutations) with its current system state summary."""

    model_config = ConfigDict(extra="forbid")

    name: str
    current_system_state_summary: str


class CreateSessionRequest(BaseModel):
    """Request of create_session."""

    model_config = ConfigDict(extra="forbid")

    project_path: str
    session_label: str


class CreateSessionResponse(BaseModel):
    """Response of create_session."""

    model_config = ConfigDict(extra="forbid")

    session_label: str
    work_directory: str
    session_state_path: str
    source_project_absolute_path: str
    project_import_summary: ProjectImportSummary
    active_setup: str = "default"
    envelope: ResponseEnvelope


class ReimportSystemDefinitionRequest(BaseModel):
    """Request of reimport_system_definition."""

    model_config = ConfigDict(extra="forbid")

    session_label: str


class ReimportSystemDefinitionResponse(BaseModel):
    """Response of reimport_system_definition."""

    model_config = ConfigDict(extra="forbid")

    project_refresh_status: Literal["CHANGED", "UNCHANGED"]
    project_import_summary: ProjectImportSummary
    changes: list[ProjectChange] = Field(default_factory=list)
    invalidated_references: list[InvalidatedReference] = Field(default_factory=list)
    envelope: ResponseEnvelope


class DescribeSessionRequest(BaseModel):
    """Request of the describe_session capability."""

    model_config = ConfigDict(extra="forbid")

    session_label: str


class DescribeSessionResponse(BaseModel):
    """Response of describe_session (persisted session metadata)."""

    model_config = ConfigDict(extra="forbid")

    session_label: str
    work_directory: str
    source_project_absolute_path: str
    project_refresh: ProjectRefreshInfo
    project_import: ProjectImportInfo
    active_setup: str = "default"
    setups: list[SetupSummary] = Field(default_factory=list)
    trace_artifacts: list[dict[str, object]] = Field(default_factory=list)
    log_book_references: list[str] = Field(default_factory=list)
    envelope: ResponseEnvelope
