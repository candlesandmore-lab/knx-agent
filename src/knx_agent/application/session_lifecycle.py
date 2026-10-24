"""SessionLifecycle: atomic create, lookup and loading of sessions under a session root."""

from __future__ import annotations

import os
import secrets
import shutil
from pathlib import Path

from knx_agent.contracts import SESSION_LABEL_EXISTS, LogLevel, error
from knx_agent.domain import SessionState

from .graph_store import write_graph
from .import_support import log_import_started, log_import_warnings, project_import_from
from .knxproj_guard import stat_project
from .log_book import SessionLogBook, utc_now
from .project_importer import import_project
from .session_paths import (
    find_work_directory,
    read_state,
    require_label_for_create,
    require_label_for_existing,
    write_state,
)


class SessionLifecycle:
    """Creates and finds sessions below one session root."""

    def __init__(self, session_root: Path) -> None:
        self.session_root = session_root

    def create(
        self, project_path: str | os.PathLike[str], session_label: str, log_level: LogLevel
    ) -> tuple[SessionState, Path, int | None]:
        """Create a session. Order: label, readability, archive, uniqueness; atomic via temp folder."""
        label = require_label_for_create(session_label)
        project = Path(project_path).expanduser().resolve()
        _mtime, size = stat_project(project)  # PROJECT_FILE_UNREADABLE
        result = import_project(project)  # PROJECT_FILE_UNREADABLE, then PROJECT_PARSE_ERROR
        final = self.session_root / label
        self._ensure_free(final, label)
        self.session_root.mkdir(parents=True, exist_ok=True)
        temp = self.session_root / f".{label}.creating-{secrets.token_hex(6)}"
        temp.mkdir()
        try:
            now = utc_now()
            state = SessionState(
                session_label=label,
                created_at=now,
                work_directory=str(final),
                source_project_absolute_path=str(project),
                project_import=project_import_from(result, str(project), now),
            )
            write_graph(temp, result.graph)
            write_state(temp, state)
            SessionLogBook.initialise(temp)
            log_book = SessionLogBook(temp, log_level)
            # The folder (and so the log book) exists only after the import; its entries are written now, in order.
            log_import_started(log_book, "create_session", state.active_setup, str(project), size)
            log_import_warnings(log_book, "create_session", state.active_setup, result.warnings)
            entry_id = log_book.write(
                "INFO",
                "create_session",
                state.active_setup,
                "Session created",
                {
                    "session_label": label,
                    "project_path": str(project),
                    "work_directory": str(final),
                    "fingerprint": result.fingerprint,
                    "node_counts": result.summary.node_counts,
                    "warning_total": len(result.warnings),
                    "duration_s": result.duration_s,
                },
            )
            self._ensure_free(final, label)
            try:
                os.rename(temp, final)
            except OSError as exc:
                if final.exists():
                    raise error(SESSION_LABEL_EXISTS, f"session_label {label!r} already exists.", session_label=label) from exc
                raise
        except BaseException:
            shutil.rmtree(temp, ignore_errors=True)
            raise
        return state, final, entry_id

    @staticmethod
    def _ensure_free(final: Path, label: str) -> None:
        if final.exists() or final.is_symlink():
            raise error(SESSION_LABEL_EXISTS, f"session_label {label!r} already exists.", session_label=label)

    def work_directory(self, session_label: object) -> Path:
        """Work-directory of an existing session (label rule, then SESSION_NOT_FOUND)."""
        label = require_label_for_existing(session_label)
        return find_work_directory(self.session_root, label)

    def load(self, work_directory: Path) -> SessionState:
        """Read the persisted session state."""
        return read_state(work_directory)
