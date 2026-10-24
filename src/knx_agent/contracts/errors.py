"""The single SDK-facing exception carrying ErrorInfo, plus the error code constants."""

from __future__ import annotations

from .models import ErrorInfo

INVALID_REQUEST = "INVALID_REQUEST"
SESSION_LABEL_INVALID = "SESSION_LABEL_INVALID"
SESSION_LABEL_EXISTS = "SESSION_LABEL_EXISTS"
SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
PROJECT_FILE_UNREADABLE = "PROJECT_FILE_UNREADABLE"
PROJECT_PARSE_ERROR = "PROJECT_PARSE_ERROR"
INVALID_LOG_LEVEL = "INVALID_LOG_LEVEL"


class KnxAgentError(Exception):
    """Raised for core failures; adapters map the carried ErrorInfo to their surface unchanged."""

    def __init__(self, error: ErrorInfo) -> None:
        super().__init__(f"{error.code}: {error.message}")
        self.error = error


def error(code: str, message: str, **details: object) -> KnxAgentError:
    """Build a KnxAgentError with optional details."""
    return KnxAgentError(ErrorInfo(code=code, message=message, details=details or None))
