"""ProjectRefreshGuard: compares the bound .knxproj with project_import and re-imports on change."""

from __future__ import annotations

from pathlib import Path

from knx_agent.domain import ProjectImport, SessionState

from .knxproj_guard import ProjectFileInfo, inspect_project, stat_project
from .log_book import SessionLogBook, utc_now
from .session_paths import write_state


def _apply_import(state: SessionState, info: ProjectFileInfo, status: str, now: str) -> SessionState:
    """Return a new state with project_import and project_refresh updated for a re-import."""
    new = state.model_copy(deep=True)
    new.project_import = ProjectImport(
        path=state.project_import.path,
        mtime=info.mtime_ns,
        size=info.size,
        imported_at=now,
        project_import_summary=info.summary,
    )
    new.project_refresh.last_status = status  # type: ignore[assignment]
    new.project_refresh.last_reimported_at = now
    new.project_refresh.reimport_count += 1
    return new


class ProjectRefreshGuard:
    """Refresh check (every session-scoped call) and forced re-import (reimport_system_definition)."""

    def check(
        self, state: SessionState, work_directory: Path, log_book: SessionLogBook, capability: str
    ) -> tuple[SessionState, int | None]:
        """Compare existence/mtime/size; unchanged writes no state, changed re-imports atomically."""
        old = state.project_import
        mtime, size = stat_project(Path(old.path))  # PROJECT_FILE_UNREADABLE, state untouched
        compared = {"old_mtime": old.mtime, "old_size": old.size, "new_mtime": mtime, "new_size": size}
        if (mtime, size) == (old.mtime, old.size):
            entry_id = log_book.write(
                "DEBUG", capability, state.active_setup, "Project refresh check: unchanged", compared
            )
            return state, entry_id
        info = inspect_project(Path(old.path))  # PROJECT_PARSE_ERROR / UNREADABLE, state untouched
        new_state = _apply_import(state, info, "CHANGED", utc_now())
        write_state(work_directory, new_state)
        entry_id = log_book.write(
            "INFO",
            capability,
            state.active_setup,
            "Project refresh check: changed, automatic re-import done",
            {**compared, "new_mtime": info.mtime_ns, "new_size": info.size},
        )
        return new_state, entry_id

    def force(
        self, state: SessionState, work_directory: Path, log_book: SessionLogBook
    ) -> tuple[SessionState, str, int | None]:
        """Re-read the project regardless; report CHANGED (metadata differed) or UNCHANGED."""
        old = state.project_import
        info = inspect_project(Path(old.path))
        status = "UNCHANGED" if (info.mtime_ns, info.size) == (old.mtime, old.size) else "CHANGED"
        new_state = _apply_import(state, info, status, utc_now())
        write_state(work_directory, new_state)
        entry_id = log_book.write(
            "INFO",
            "reimport_system_definition",
            state.active_setup,
            f"Explicit re-import done: {status}",
            {
                "status": status,
                "old_mtime": old.mtime,
                "old_size": old.size,
                "new_mtime": info.mtime_ns,
                "new_size": info.size,
            },
        )
        return new_state, status, entry_id
