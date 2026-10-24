"""KNX session log book: append-only JSON Lines writer with level filtering.

ERROR entries are always written, whatever log_level is configured.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from knx_agent.contracts import ERROR_LEVEL, INVALID_LOG_LEVEL, LogLevel, error
from knx_agent.domain import LOG_BOOK_FILE_NAME


def utc_now() -> str:
    """UTC ISO 8601 timestamp with second precision."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_log_level(value: object) -> LogLevel:
    """Accept a LogLevel or its (case-insensitive) name; anything else is INVALID_LOG_LEVEL."""
    try:
        return value if isinstance(value, LogLevel) else LogLevel(str(value).upper())
    except ValueError as exc:
        raise error(INVALID_LOG_LEVEL, f"log_level must be one of INFO, DEBUG, FULL, got {value!r}.") from exc


class SessionLogBook:
    """Writer for session-log-book.jsonl in a work-directory."""

    def __init__(self, work_directory: Path, log_level: LogLevel) -> None:
        self.path = work_directory / LOG_BOOK_FILE_NAME
        self.log_level = log_level

    @staticmethod
    def initialise(work_directory: Path) -> None:
        """Create the empty log book file."""
        (work_directory / LOG_BOOK_FILE_NAME).touch()

    def _next_entry_id(self) -> int:
        try:
            lines = [line for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except FileNotFoundError:
            return 1
        return json.loads(lines[-1])["entry_id"] + 1 if lines else 1

    def write(
        self,
        level: str,
        capability: str,
        setup: str,
        summary: str,
        details: dict[str, object] | None = None,
    ) -> int | None:
        """Append an entry if its level passes the filter; return entry_id or None."""
        if level != ERROR_LEVEL and LogLevel(level) > self.log_level:
            return None
        entry_id = self._next_entry_id()
        entry = {
            "entry_id": entry_id,
            "timestamp": utc_now(),
            "level": level,
            "capability": capability,
            "setup": setup,
            "summary": summary,
            "details": details or {},
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry_id
