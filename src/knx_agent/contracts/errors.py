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
# Catalogue C7 codes first used by the query capabilities (story 05)
SELECTOR_UNRESOLVED = "SELECTOR_UNRESOLVED"
MUTATION_NOT_FOUND = "MUTATION_NOT_FOUND"
INVALID_DETAIL_LEVEL = "INVALID_DETAIL_LEVEL"

# details.reason values of INVALID_REQUEST for selector problems (story 05)
REASON_SELECTOR_BLANK = "SELECTOR_BLANK"
REASON_SELECTOR_MISSING = "SELECTOR_MISSING"
REASON_SELECTOR_CONFLICT = "SELECTOR_CONFLICT"
REASON_SELECTOR_KIND_UNKNOWN = "SELECTOR_KIND_UNKNOWN"
REASON_SELECTOR_KIND_MISMATCH = "SELECTOR_KIND_MISMATCH"
REASON_SELECTOR_KIND_WITHOUT_SELECTOR = "SELECTOR_KIND_WITHOUT_SELECTOR"
INVALID_REQUEST_SELECTOR_REASONS: tuple[str, ...] = (
    REASON_SELECTOR_BLANK,
    REASON_SELECTOR_MISSING,
    REASON_SELECTOR_CONFLICT,
    REASON_SELECTOR_KIND_UNKNOWN,
    REASON_SELECTOR_KIND_MISMATCH,
    REASON_SELECTOR_KIND_WITHOUT_SELECTOR,
)


class KnxAgentError(Exception):
    """Raised for core failures; adapters map the carried ErrorInfo to their surface unchanged."""

    def __init__(self, error: ErrorInfo) -> None:
        super().__init__(f"{error.code}: {error.message}")
        self.error = error


def error(code: str, message: str, **details: object) -> KnxAgentError:
    """Build a KnxAgentError with optional details."""
    return KnxAgentError(ErrorInfo(code=code, message=message, details=details or None))
