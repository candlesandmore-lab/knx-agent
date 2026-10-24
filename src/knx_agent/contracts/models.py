"""Common response envelope (C7), error shape and the describe_session contract."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


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
    log_book_entry_id: str | None = None
    detail_level: DetailLevel | None = None


class ErrorInfo(BaseModel):
    """Error shape: code, message and optional details."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: dict[str, object] | None = None


class DescribeSessionRequest(BaseModel):
    """Request of the describe_session capability."""

    model_config = ConfigDict(extra="forbid")

    session_label: str


class DescribeSessionResponse(BaseModel):
    """Response of describe_session, limited to fields the placeholder can honestly fill."""

    model_config = ConfigDict(extra="forbid")

    session_label: str
    active_setup: str = "default"
    envelope: ResponseEnvelope
