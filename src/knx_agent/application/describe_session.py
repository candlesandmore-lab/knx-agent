"""Core API capability describe_session (catalogue capability 3)."""

from __future__ import annotations

from knx_agent.contracts import (
    DescribeSessionRequest,
    DescribeSessionResponse,
    ErrorInfo,
    KnxAgentError,
    ResponseEnvelope,
)

_PLACEHOLDER_NOTE = "Session service is not implemented yet (todo 03); this response is a placeholder."


def describe_session(session_label: str) -> DescribeSessionResponse:
    """Describe an investigation session.

    PLACEHOLDER: the body only validates the label and returns a fixed envelope; the real
    session service arrives with todo 03.
    """
    if not isinstance(session_label, str) or not session_label.strip():
        raise KnxAgentError(
            ErrorInfo(code="INVALID_REQUEST", message="session_label must be a non-empty string.")
        )
    request = DescribeSessionRequest(session_label=session_label)
    # PLACEHOLDER body: no session lookup happens yet.
    return DescribeSessionResponse(
        session_label=request.session_label,
        active_setup="default",
        envelope=ResponseEnvelope(
            setup="default",
            evidence_sources=[],
            limitation_notes=[_PLACEHOLDER_NOTE],
        ),
    )
