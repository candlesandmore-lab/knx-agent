"""KnxSessionClient: SDK entry point; delegates to the application layer."""

from __future__ import annotations

import os

from knx_agent.application import SessionService
from knx_agent.contracts import (
    CreateSessionResponse,
    DescribeSessionResponse,
    LogLevel,
    ReimportSystemDefinitionResponse,
)


class KnxSessionClient:
    """SDK client exposing catalogue capabilities as methods.

    session_root: folder holding all work-directories (default ./.knx-agent/sessions); the only
    way to set it besides the CLI option and MCP startup argument. No environment variable is read.
    log_level: default INFO/DEBUG/FULL of this client; every method also accepts a per-call log_level.
    """

    def __init__(
        self,
        session_root: str | os.PathLike[str] | None = None,
        log_level: LogLevel | str = LogLevel.INFO,
    ) -> None:
        self._service = SessionService(session_root=session_root, log_level=log_level)

    def create_session(
        self, project_path: str | os.PathLike[str], session_label: str, log_level: LogLevel | str | None = None
    ) -> CreateSessionResponse:
        """Create an investigation session bound to a .knxproj file."""
        return self._service.create_session(os.fspath(project_path), session_label, log_level)

    def describe_session(
        self, session_label: str, log_level: LogLevel | str | None = None
    ) -> DescribeSessionResponse:
        """Describe an investigation session (runs the project refresh check first)."""
        return self._service.describe_session(session_label, log_level)

    def reimport_system_definition(
        self, session_label: str, log_level: LogLevel | str | None = None
    ) -> ReimportSystemDefinitionResponse:
        """Explicitly re-read the bound .knxproj of a session."""
        return self._service.reimport_system_definition(session_label, log_level)
