"""KnxSessionClient: SDK entry point; delegates to the application layer."""

from __future__ import annotations

from knx_agent import application
from knx_agent.contracts import DescribeSessionResponse


class KnxSessionClient:
    """SDK client exposing catalogue capabilities as methods."""

    def describe_session(self, session_label: str) -> DescribeSessionResponse:
        """Describe an investigation session (delegates to the core API)."""
        return application.describe_session(session_label)
