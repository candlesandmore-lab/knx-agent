"""ProjectRefreshGuard: compares the bound .knxproj with project_import and re-imports on change.

Check order (003 'Fingerprint and refresh check'): existence, mtime, size, fingerprint. A difference in mtime,
size, fingerprint or a missing graph file means CHANGED and an automatic re-import. Write order of a re-import:
parse completely first (a failure writes nothing), then project-graph.json, then session-state.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from knx_agent.domain import SessionState
from knx_agent.domain.graph_diff import diff_graphs, invalidated_references

from .graph_store import graph_path, read_graph, write_graph
from .import_support import (
    change_counts,
    log_import_started,
    log_import_warnings,
    project_import_from,
)
from .knxproj_guard import stat_project
from .log_book import SessionLogBook, utc_now
from .project_importer import ImportResult, file_fingerprint, import_project
from .session_paths import write_state


@dataclass(frozen=True)
class ReimportOutcome:
    """Result of a re-import: the new state, the import result and the comparison with the old graph."""

    state: SessionState
    result: ImportResult
    changes: list[dict[str, object]]
    invalidated: list[dict[str, object]]
    old_graph_found: bool


def _apply_import(state: SessionState, result: ImportResult, status: str, now: str) -> SessionState:
    """Return a new state with project_import and project_refresh updated for a re-import."""
    new = state.model_copy(deep=True)
    new.project_import = project_import_from(result, state.project_import.path, now)
    new.project_refresh.last_status = status  # type: ignore[assignment]
    new.project_refresh.last_reimported_at = now
    new.project_refresh.reimport_count += 1
    return new


class ProjectRefreshGuard:
    """Refresh check (every session-scoped call) and forced re-import (reimport_system_definition)."""

    def _reimport(
        self, state: SessionState, work_directory: Path, log_book: SessionLogBook, capability: str, status: str | None
    ) -> tuple[ReimportOutcome, str]:
        """Import, compare with the old graph, write graph then state. ``status`` None derives CHANGED/UNCHANGED."""
        old = state.project_import
        path = Path(old.path)
        _mtime, size = stat_project(path)
        log_import_started(log_book, capability, state.active_setup, str(path), size)
        graph_missing = not graph_path(work_directory).exists()
        result = import_project(path)  # PROJECT_FILE_UNREADABLE / PROJECT_PARSE_ERROR: nothing written yet
        if status is None:
            differs = (
                result.mtime_ns != old.mtime
                or result.size != old.size
                or result.fingerprint != old.fingerprint
                or graph_missing
            )
            status = "CHANGED" if differs else "UNCHANGED"
        old_graph = read_graph(work_directory).graph
        if old_graph is None:
            changes: list[dict[str, object]] = []
            invalidated: list[dict[str, object]] = []
        else:
            changes = diff_graphs(old_graph, result.graph)
            invalidated = invalidated_references(old_graph, result.graph, state.scenario_state, state.mutations)
        write_graph(work_directory, result.graph)
        new_state = _apply_import(state, result, status, utc_now())
        write_state(work_directory, new_state)
        return ReimportOutcome(new_state, result, changes, invalidated, old_graph is not None), status

    @staticmethod
    def _summary_details(old_state: SessionState, outcome: ReimportOutcome, status: str) -> dict[str, object]:
        old = old_state.project_import
        return {
            "status": status,
            "old_mtime": old.mtime,
            "old_size": old.size,
            "new_mtime": outcome.result.mtime_ns,
            "new_size": outcome.result.size,
            "old_fingerprint": old.fingerprint,
            "new_fingerprint": outcome.result.fingerprint,
            "warning_total": len(outcome.result.warnings),
            "changes": change_counts(outcome.changes),
            "invalidated_references": len(outcome.invalidated),
            "duration_s": outcome.result.duration_s,
        }

    def check(
        self, state: SessionState, work_directory: Path, log_book: SessionLogBook, capability: str
    ) -> tuple[SessionState, int | None]:
        """Compare existence, mtime, size, fingerprint; unchanged writes no state, changed re-imports atomically."""
        old = state.project_import
        path = Path(old.path)
        mtime, size = stat_project(path)  # PROJECT_FILE_UNREADABLE, state untouched
        compared: dict[str, object] = {
            "old_mtime": old.mtime,
            "old_size": old.size,
            "new_mtime": mtime,
            "new_size": size,
        }
        changed = (
            (mtime, size) != (old.mtime, old.size)
            or old.fingerprint is None
            or not graph_path(work_directory).exists()
        )
        if not changed:
            fingerprint = file_fingerprint(path)  # only reached when mtime and size are equal
            compared["old_fingerprint"] = old.fingerprint
            compared["new_fingerprint"] = fingerprint
            changed = fingerprint != old.fingerprint
        if not changed:
            entry_id = log_book.write(
                "DEBUG", capability, state.active_setup, "Project refresh check: unchanged", compared
            )
            return state, entry_id
        outcome, status = self._reimport(state, work_directory, log_book, capability, "CHANGED")
        log_import_warnings(log_book, capability, state.active_setup, outcome.result.warnings)
        entry_id = log_book.write(
            "INFO",
            capability,
            state.active_setup,
            "Project refresh check: changed, automatic re-import done",
            self._summary_details(state, outcome, status),
        )
        return outcome.state, entry_id

    def force(
        self, state: SessionState, work_directory: Path, log_book: SessionLogBook
    ) -> tuple[ReimportOutcome, str, int | None]:
        """Re-read the project regardless; report CHANGED (anything differed) or UNCHANGED."""
        outcome, status = self._reimport(state, work_directory, log_book, "reimport_system_definition", None)
        log_import_warnings(log_book, "reimport_system_definition", state.active_setup, outcome.result.warnings)
        entry_id = log_book.write(
            "INFO",
            "reimport_system_definition",
            state.active_setup,
            f"Explicit re-import done: {status}",
            self._summary_details(state, outcome, status),
        )
        return outcome, status, entry_id
