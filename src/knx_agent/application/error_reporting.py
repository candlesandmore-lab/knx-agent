"""Shared ERROR reporting of the application services (extracted from SessionService, story 05).

Every issue is logged as ERROR to the Python logger and, when the session folder exists, to the session log book.
The log book entry is written regardless of the configured log level.
"""

from __future__ import annotations

import logging
from pathlib import Path

from knx_agent.contracts import ERROR_LEVEL, KnxAgentError, LogLevel

from .log_book import SessionLogBook
from .session_paths import state_path

logger = logging.getLogger("knx_agent.application.session_service")


def report_error(exc: BaseException, capability: str, work_directory: Path | None, level: LogLevel) -> None:
    """Log one failure as ERROR (Python logger plus, when a session exists, the log book)."""
    code = exc.error.code if isinstance(exc, KnxAgentError) else type(exc).__name__
    message = exc.error.message if isinstance(exc, KnxAgentError) else str(exc)
    reason = exc.error.details.get("reason") if isinstance(exc, KnxAgentError) and exc.error.details else None
    logger.error("%s failed: %s: %s", capability, code, message)
    if work_directory is not None and state_path(work_directory).exists():
        try:
            details: dict[str, object] = {"code": code, "message": message}
            if reason is not None:
                details["reason"] = reason
            SessionLogBook(work_directory, level).write(
                ERROR_LEVEL, capability, "default", f"{code}: {message}", details
            )
        except OSError:
            logger.exception("Could not write ERROR entry to the session log book")
