"""Session root resolution, label rules and the session state store (atomic YAML I/O).

No environment variable is read anywhere: the session root comes from the caller or the default.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from knx_agent.contracts import (
    INVALID_REQUEST,
    SESSION_LABEL_INVALID,
    SESSION_NOT_FOUND,
    error,
)
from knx_agent.domain import SessionState, is_valid_session_label

DEFAULT_SESSION_ROOT = Path(".knx-agent") / "sessions"
STATE_FILE_NAME = "session-state.yaml"


def resolve_session_root(session_root: str | os.PathLike[str] | None) -> Path:
    """Explicit session root, else ./.knx-agent/sessions relative to the current directory."""
    return Path(session_root if session_root is not None else DEFAULT_SESSION_ROOT).expanduser().resolve()


def require_label_for_create(label: object) -> str:
    """Label rule for create_session: blank or invalid characters -> SESSION_LABEL_INVALID."""
    if not is_valid_session_label(label):
        raise error(
            SESSION_LABEL_INVALID,
            "session_label must be non-empty and use letters, digits, '-' and '_' only.",
            session_label=label if isinstance(label, str) else None,
        )
    return label  # type: ignore[return-value]


def require_label_for_existing(label: object) -> str:
    """Label rule for existing sessions: blank -> INVALID_REQUEST, other invalid -> SESSION_NOT_FOUND."""
    if not isinstance(label, str) or not label.strip():
        raise error(INVALID_REQUEST, "session_label must be a non-empty string.")
    if not is_valid_session_label(label):
        raise error(SESSION_NOT_FOUND, f"No session with session_label {label!r}.", session_label=label)
    return label


def state_path(work_directory: Path) -> Path:
    """Path of session-state.yaml inside a work-directory."""
    return work_directory / STATE_FILE_NAME


def read_state(work_directory: Path) -> SessionState:
    """Read session-state.yaml; a missing or unreadable file means the session is not found."""
    path = state_path(work_directory)
    try:
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        return SessionState.model_validate(data)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        raise error(
            SESSION_NOT_FOUND,
            f"Session state {path} is missing or unreadable.",
            reason=str(exc),
        ) from exc


def write_state(work_directory: Path, state: SessionState) -> None:
    """Write session-state.yaml atomically: temporary file in the same folder, then os.replace."""
    target = state_path(work_directory)
    temp = work_directory / f".{STATE_FILE_NAME}.tmp-{os.getpid()}"
    try:
        with temp.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(state.model_dump(mode="json"), handle, sort_keys=False, allow_unicode=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def find_work_directory(session_root: Path, label: str) -> Path:
    """Work-directory of an existing session or SESSION_NOT_FOUND."""
    work_directory = session_root / label
    if not work_directory.is_dir():
        raise error(SESSION_NOT_FOUND, f"No session with session_label {label!r}.", session_label=label)
    return work_directory


__all__ = [
    "DEFAULT_SESSION_ROOT",
    "STATE_FILE_NAME",
    "find_work_directory",
    "read_state",
    "require_label_for_create",
    "require_label_for_existing",
    "resolve_session_root",
    "state_path",
    "write_state",
]
