"""SDK-first tests: call KnxSessionClient directly, without CLI or MCP.

Cases come from tests/fixtures/describe_session_cases.yaml via tests/conftest.py.
"""

import pytest

from knx_agent.contracts import DescribeSessionResponse, KnxAgentError
from knx_agent.sdk import KnxSessionClient


def test_describe_session_returns_response_model(valid_case):
    response = KnxSessionClient().describe_session(session_label=valid_case["session_label"])
    assert isinstance(response, DescribeSessionResponse)
    assert response.session_label == valid_case["session_label"]
    assert response.active_setup == valid_case["expected_active_setup"]
    assert response.envelope.setup == valid_case["expected_setup"]
    assert response.envelope.evidence_sources == valid_case["expected_evidence_sources"]
    assert any(
        valid_case["expected_limitation_note_contains"] in note
        for note in response.envelope.limitation_notes
    )


def test_blank_label_raises_invalid_request(invalid_case):
    with pytest.raises(KnxAgentError) as excinfo:
        KnxSessionClient().describe_session(session_label=invalid_case["session_label"])
    assert excinfo.value.error.code == invalid_case["expected_error_code"]
    assert excinfo.value.error.message
