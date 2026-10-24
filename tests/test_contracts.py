"""Contract model tests: envelope, evidence sources, error shape, log levels, session contracts."""

import pytest
from pydantic import ValidationError

from knx_agent.contracts import (
    CreateSessionResponse,
    DescribeSessionRequest,
    DescribeSessionResponse,
    DetailLevel,
    ErrorInfo,
    EvidenceSource,
    LogLevel,
    ReimportSystemDefinitionResponse,
    ResponseEnvelope,
)
from knx_agent.contracts import errors as error_codes


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
    envelope = ResponseEnvelope(log_book_entry_id=7, detail_level="FULL")
    assert envelope.detail_level is DetailLevel.FULL
    assert envelope.log_book_entry_id == 7
    with pytest.raises(ValidationError):
        ResponseEnvelope(extra_field=1)


def test_error_info_shape():
    error = ErrorInfo(code="INVALID_REQUEST", message="m")
    assert error.details is None
    assert set(ErrorInfo.model_json_schema()["properties"]) == {"code", "message", "details"}
    with pytest.raises(ValidationError):
        ErrorInfo(code="X")


def test_error_code_constants():
    assert error_codes.SESSION_LABEL_INVALID == "SESSION_LABEL_INVALID"
    for name in (
        "SESSION_LABEL_EXISTS",
        "SESSION_NOT_FOUND",
        "PROJECT_FILE_UNREADABLE",
        "PROJECT_PARSE_ERROR",
        "INVALID_LOG_LEVEL",
        "INVALID_REQUEST",
    ):
        assert getattr(error_codes, name) == name


def test_log_level_ordering():
    assert LogLevel.INFO < LogLevel.DEBUG < LogLevel.FULL
    assert LogLevel.FULL >= LogLevel.DEBUG >= LogLevel.INFO
    assert [lv.value for lv in LogLevel] == ["INFO", "DEBUG", "FULL"]
    with pytest.raises(ValueError):
        LogLevel("ERROR")


def test_project_import_contract_shapes(client, project):
    from knx_agent.contracts import (
        ImportWarning,
        InvalidatedReference,
        ProjectChange,
        ProjectImportInfo,
        ProjectImportSummary,
    )

    assert set(ProjectImportSummary.model_fields) == {
        "file_name", "archive_entry_count", "ets_tool_version", "schema_namespace", "created_by", "project_id",
        "project_name", "group_address_style", "node_counts", "relation_counts", "component_type_counts",
        "application_programs", "warning_total", "warning_counts", "graph_file", "graph_schema_version",
    }  # fmt: skip  (limitation_note of story 03 is gone)
    assert set(ProjectImportInfo.model_fields) == {"imported_at", "fingerprint", "graph_file", "project_import_summary"}
    assert set(ImportWarning.model_fields) == {"code", "message", "location"}
    assert set(ProjectChange.model_fields) == {"entity", "change", "id", "label", "details"}
    assert set(InvalidatedReference.model_fields) == {
        "reference_kind", "owner", "component_id", "group_address_id", "reason",
    }  # fmt: skip
    with pytest.raises(ValidationError):
        ProjectChange(entity="parameter", change="added", id="x", label="x")
    with pytest.raises(ValidationError):
        ProjectImportSummary(file_name="a", archive_entry_count=1, limitation_note="gone")
    client.create_session(project_path=project, session_label="abc")
    described = client.describe_session(session_label="abc")
    assert described.project_import.project_import_summary.node_counts["component"] == 3
    with pytest.raises(ValidationError):
        DescribeSessionResponse.model_validate(
            {**described.model_dump(mode="json"), "project_import": None}
        )  # project_import is part of every describe_session response


def test_models_serialise_and_expose_json_schema(client, project):
    created = client.create_session(project_path=project, session_label="abc")
    described = client.describe_session(session_label="abc")
    reimported = client.reimport_system_definition(session_label="abc")
    for response in (created, described, reimported):
        assert type(response).model_validate_json(response.model_dump_json()) == response
    assert "envelope" in DescribeSessionResponse.model_json_schema()["properties"]
    assert DescribeSessionRequest(session_label="a").session_label == "a"
    assert set(DescribeSessionResponse.model_fields) == {
        "session_label", "work_directory", "source_project_absolute_path", "project_refresh",
        "project_import", "active_setup", "setups", "trace_artifacts", "log_book_references", "envelope",
    }  # fmt: skip
    assert set(CreateSessionResponse.model_fields) == {
        "session_label", "work_directory", "session_state_path", "source_project_absolute_path",
        "project_import_summary", "active_setup", "envelope",
    }  # fmt: skip
    assert set(ReimportSystemDefinitionResponse.model_fields) == {
        "project_refresh_status", "project_import_summary", "changes", "invalidated_references", "envelope",
    }  # fmt: skip
