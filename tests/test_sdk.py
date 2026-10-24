"""SDK-first tests: call KnxSessionClient directly, without CLI or MCP.

describe_session cases come from tests/fixtures/describe_session_cases.yaml via tests/conftest.py.
"""

import pytest

from knx_agent.contracts import DescribeSessionResponse, KnxAgentError
from knx_agent.sdk import KnxSessionClient


def test_describe_session_returns_response_model(valid_case, client, project, session_root):
    label = valid_case["session_label"]
    client.create_session(project_path=project, session_label=label)
    response = client.describe_session(session_label=label)
    assert isinstance(response, DescribeSessionResponse)
    assert response.session_label == label
    assert response.work_directory == str(session_root.resolve() / label)
    assert response.source_project_absolute_path == str(project.resolve())
    assert response.active_setup == valid_case["expected_active_setup"]
    assert response.envelope.setup == valid_case["expected_setup"]
    assert [s.kind.value for s in response.envelope.evidence_sources] == valid_case["expected_evidence_kinds"]
    assert response.envelope.limitation_notes == valid_case["expected_limitation_notes"]
    assert response.project_import.fingerprint is not None and len(response.project_import.fingerprint) == 64
    assert response.project_import.project_import_summary.node_counts["component"] == 3
    assert response.log_book_references == ["session-log-book.jsonl"]
    assert response.trace_artifacts == []
    assert [s.name for s in response.setups] == ["default"]


def test_describe_session_errors(invalid_case, client):
    with pytest.raises(KnxAgentError) as excinfo:
        client.describe_session(session_label=invalid_case["session_label"])
    assert excinfo.value.error.code == invalid_case["expected_error_code"]
    assert excinfo.value.error.message


def test_client_defaults():
    assert isinstance(KnxSessionClient(), KnxSessionClient)
