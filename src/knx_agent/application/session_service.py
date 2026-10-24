"""SessionService: composes SessionLifecycle and ProjectRefreshGuard (capabilities 1-3).

Every public session-scoped operation runs the refresh check first. Every issue is logged as
ERROR to the standard logger 'knx_agent.*' and, when a session exists, to the session log book.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from knx_agent.contracts import (
    ERROR_LEVEL,
    CreateSessionResponse,
    DescribeSessionResponse,
    EvidenceKind,
    EvidenceSource,
    KnxAgentError,
    LogLevel,
    ProjectImportSummary,
    ProjectRefreshInfo,
    ReimportSystemDefinitionResponse,
    ResponseEnvelope,
    SetupSummary,
)
from knx_agent.domain import SessionState

from .log_book import SessionLogBook, parse_log_level
from .project_refresh_guard import ProjectRefreshGuard
from .session_lifecycle import SessionLifecycle
from .session_paths import resolve_session_root, state_path

logger = logging.getLogger(__name__)


def _envelope(state: SessionState, entry_id: int | None) -> ResponseEnvelope:
    return ResponseEnvelope(
        setup=state.active_setup,
        evidence_sources=[
            EvidenceSource(kind=EvidenceKind.KNXPROJ, reference=state.source_project_absolute_path)
        ],
        limitation_notes=[state.project_import.project_import_summary.limitation_note],
        log_book_entry_id=entry_id,
    )


class SessionService:
    """Core session operations for one session root and a default log level."""

    def __init__(
        self,
        session_root: str | os.PathLike[str] | None = None,
        log_level: LogLevel | str = LogLevel.INFO,
    ) -> None:
        self._root_arg = session_root
        self._default_level = log_level
        self.guard = ProjectRefreshGuard()

    # -- error reporting -------------------------------------------------------------------
    def _report_error(
        self, exc: BaseException, capability: str, work_directory: Path | None, level: LogLevel
    ) -> None:
        code = exc.error.code if isinstance(exc, KnxAgentError) else type(exc).__name__
        message = exc.error.message if isinstance(exc, KnxAgentError) else str(exc)
        logger.error("%s failed: %s: %s", capability, code, message)
        if work_directory is not None and state_path(work_directory).exists():
            try:
                SessionLogBook(work_directory, level).write(
                    ERROR_LEVEL, capability, "default", f"{code}: {message}", {"code": code, "message": message}
                )
            except OSError:
                logger.exception("Could not write ERROR entry to the session log book")

    def _level(self, log_level: LogLevel | str | None) -> LogLevel:
        return parse_log_level(self._default_level if log_level is None else log_level)

    # -- capabilities ----------------------------------------------------------------------
    def create_session(
        self, project_path: str, session_label: str, log_level: LogLevel | str | None = None
    ) -> CreateSessionResponse:
        """create_session: guard the .knxproj, create the work-directory atomically."""
        level = LogLevel.INFO
        try:
            level = self._level(log_level)
            lifecycle = SessionLifecycle(resolve_session_root(self._root_arg))
            state, work_directory, entry_id = lifecycle.create(project_path, session_label, level)
        except Exception as exc:
            # Failed create leaves no folder, so only the Python logger receives the ERROR.
            self._report_error(exc, "create_session", None, level)
            raise
        return CreateSessionResponse(
            session_label=state.session_label,
            work_directory=str(work_directory),
            session_state_path=str(state_path(work_directory)),
            source_project_absolute_path=state.source_project_absolute_path,
            project_import_summary=ProjectImportSummary(
                **state.project_import.project_import_summary.model_dump()
            ),
            active_setup=state.active_setup,
            envelope=_envelope(state, entry_id),
        )

    def _open(self, session_label: object) -> tuple[Path, SessionState]:
        lifecycle = SessionLifecycle(resolve_session_root(self._root_arg))
        work_directory = lifecycle.work_directory(session_label)
        return work_directory, lifecycle.load(work_directory)

    def describe_session(
        self, session_label: str, log_level: LogLevel | str | None = None
    ) -> DescribeSessionResponse:
        """describe_session: refresh check first, then the persisted metadata (read-only, no own entry)."""
        work_directory: Path | None = None
        level = LogLevel.INFO
        try:
            level = self._level(log_level)
            work_directory, state = self._open(session_label)
            state, entry_id = self.guard.check(
                state, work_directory, SessionLogBook(work_directory, level), "describe_session"
            )
        except Exception as exc:
            self._report_error(exc, "describe_session", work_directory, level)
            raise
        return DescribeSessionResponse(
            session_label=state.session_label,
            work_directory=state.work_directory,
            source_project_absolute_path=state.source_project_absolute_path,
            project_refresh=ProjectRefreshInfo(**state.project_refresh.model_dump()),
            active_setup=state.active_setup,
            setups=[SetupSummary(name="default", current_system_state_summary="unknown")],
            trace_artifacts=list(state.trace_artifacts),
            log_book_references=list(state.log_book_references),
            envelope=_envelope(state, entry_id),
        )

    def reimport_system_definition(
        self, session_label: str, log_level: LogLevel | str | None = None
    ) -> ReimportSystemDefinitionResponse:
        """reimport_system_definition: forced re-read of the bound .knxproj (replaces the refresh check)."""
        work_directory: Path | None = None
        level = LogLevel.INFO
        try:
            level = self._level(log_level)
            work_directory, state = self._open(session_label)
            state, status, entry_id = self.guard.force(
                state, work_directory, SessionLogBook(work_directory, level)
            )
        except Exception as exc:
            self._report_error(exc, "reimport_system_definition", work_directory, level)
            raise
        return ReimportSystemDefinitionResponse(
            project_refresh_status=status,  # type: ignore[arg-type]
            project_import_summary=ProjectImportSummary(
                **state.project_import.project_import_summary.model_dump()
            ),
            changes=[],
            invalidated_references=[],
            envelope=_envelope(state, entry_id),
        )
