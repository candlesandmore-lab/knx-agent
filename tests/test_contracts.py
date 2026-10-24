"""Contract model tests: envelope, evidence sources, error shape, core placeholder response."""

import pytest
from pydantic import ValidationError

from knx_agent.application import describe_session
from knx_agent.contracts import (
    DescribeSessionRequest,
    DescribeSessionResponse,
    DetailLevel,
    ErrorInfo,
    EvidenceSource,
    ResponseEnvelope,
)


@pytest.mark.parametrize(
    "kind", ["KNXPROJ", "TRACE", "USER_INPUT", "VENDOR_DOCUMENTATION", "SIMULATION_RULE"]
)
def test_evidence_source_accepts_known_kinds(kind):
    source = EvidenceSource(kind=kind, reference="r")
    assert source.kind.value == kind
    assert source.model_dump(mode="json") == {"kind": kind, "reference": "r"}


def test_evidence_source_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        EvidenceSource(kind="GUESS", reference="r")


def test_envelope_defaults():
    envelope = ResponseEnvelope()
    assert envelope.setup is None
    assert envelope.evidence_sources == []
    assert envelope.limitation_notes == []
    assert envelope.log_book_entry_id is None
    assert envelope.detail_level is None


def test_envelope_limitation_notes_never_null():
    with pytest.raises(ValidationError):
        ResponseEnvelope(limitation_notes=None)


def test_envelope_optional_fields_and_unknown_field_rejected():
    envelope = ResponseEnvelope(log_book_entry_id="e1", detail_level="FULL")
    assert envelope.detail_level is DetailLevel.FULL
    assert envelope.log_book_entry_id == "e1"
    with pytest.raises(ValidationError):
        ResponseEnvelope(extra_field=1)


def test_error_info_shape():
    error = ErrorInfo(code="INVALID_REQUEST", message="m")
    assert error.details is None
    assert set(ErrorInfo.model_json_schema()["properties"]) == {"code", "message", "details"}
    with pytest.raises(ValidationError):
        ErrorInfo(code="X")


def test_models_serialise_and_expose_json_schema():
    response = describe_session("abc")
    restored = DescribeSessionResponse.model_validate_json(response.model_dump_json())
    assert restored == response
    assert "envelope" in DescribeSessionResponse.model_json_schema()["properties"]
    assert DescribeSessionRequest(session_label="a").session_label == "a"


def test_core_placeholder_response_evidence_and_limitations():
    response = describe_session("abc")
    assert response.envelope.setup == "default"
    assert response.envelope.evidence_sources == []
    assert response.envelope.limitation_notes
    assert "not implemented" in response.envelope.limitation_notes[0]
