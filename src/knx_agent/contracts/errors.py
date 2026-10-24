"""The single SDK-facing exception carrying ErrorInfo."""

from __future__ import annotations

from .models import ErrorInfo


class KnxAgentError(Exception):
    """Raised for core failures; adapters map the carried ErrorInfo to their surface unchanged."""

    def __init__(self, error: ErrorInfo) -> None:
        super().__init__(f"{error.code}: {error.message}")
        self.error = error
