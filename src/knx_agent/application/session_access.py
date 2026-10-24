"""SessionAccess: the construction shared by SessionService and QueryService.

Holds the session root argument, the default log level and the ProjectRefreshGuard, and opens existing sessions
(label rule, SESSION_NOT_FOUND, state load). One place, so both services behave identically.
"""

from __future__ import annotations

import os
from pathlib import Path

from knx_agent.contracts import LogLevel
from knx_agent.domain import SessionState

from .log_book import parse_log_level
from .project_refresh_guard import ProjectRefreshGuard
from .session_lifecycle import SessionLifecycle
from .session_paths import resolve_session_root


class SessionAccess:
    """Session root, default log level, refresh guard and session opening."""

    def __init__(
        self, session_root: str | os.PathLike[str] | None = None, log_level: LogLevel | str = LogLevel.INFO
    ) -> None:
        self.root_arg = session_root
        self.default_level = log_level
        self.guard = ProjectRefreshGuard()

    def level(self, log_level: LogLevel | str | None) -> LogLevel:
        """The effective log level of a call (INVALID_LOG_LEVEL for an unknown value)."""
        return parse_log_level(self.default_level if log_level is None else log_level)

    def lifecycle(self) -> SessionLifecycle:
        return SessionLifecycle(resolve_session_root(self.root_arg))

    def open(self, session_label: object) -> tuple[Path, SessionState]:
        """Work-directory and persisted state of an existing session (SESSION_NOT_FOUND otherwise)."""
        lifecycle = self.lifecycle()
        work_directory = lifecycle.work_directory(session_label)
        return work_directory, lifecycle.load(work_directory)
