"""Shared helpers for the import integration: persisted shape, log points, limitation notes.

Import warnings are NOT issues under the story 03 ERROR rule: they produce one Python WARNING record per import
(counts only) and DEBUG log book entries, never ERROR entries.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Sequence

from knx_agent.domain import MAX_PERSISTED_WARNINGS, ImportWarning, ProjectImport

from .log_book import SessionLogBook
from .project_importer import ImportResult

logger = logging.getLogger("knx_agent.application")

MAX_WARNING_LOG_ENTRIES = 200
MAX_LIMITATION_NOTES = 50


def project_import_from(result: ImportResult, path: str, imported_at: str) -> ProjectImport:
    """The ``project_import`` block of session-state.yaml for one import result."""
    return ProjectImport(
        path=path,
        mtime=result.mtime_ns,
        size=result.size,
        imported_at=imported_at,
        fingerprint=result.fingerprint,
        graph_file=result.summary.graph_file,
        graph_schema_version=result.summary.graph_schema_version,
        project_import_summary=result.summary,
        warnings=list(result.warnings[:MAX_PERSISTED_WARNINGS]),
    )


def log_import_started(log_book: SessionLogBook, capability: str, setup: str, path: str, size: int | None) -> None:
    """DEBUG: an import is about to run."""
    log_book.write("DEBUG", capability, setup, "Import started", {"project_path": path, "size": size})


def log_import_warnings(
    log_book: SessionLogBook, capability: str, setup: str, warnings: Sequence[ImportWarning]
) -> None:
    """One Python WARNING record (counts) and one DEBUG entry per warning (at most 200, then an omitted count)."""
    if not warnings:
        return
    counts = Counter(warning.code for warning in warnings)
    logger.warning(
        "%s: import finished with %d warnings (%s)",
        capability,
        len(warnings),
        ", ".join(f"{code}: {counts[code]}" for code in sorted(counts)),
    )
    for warning in warnings[:MAX_WARNING_LOG_ENTRIES]:
        log_book.write(
            "DEBUG",
            capability,
            setup,
            f"Import warning {warning.code}",
            {"code": warning.code, "message": warning.message, "location": warning.location},
        )
    omitted = len(warnings) - MAX_WARNING_LOG_ENTRIES
    if omitted > 0:
        log_book.write(
            "DEBUG", capability, setup, f"{omitted} further import warnings not logged individually", {"omitted": omitted}
        )


def change_counts(changes: Sequence[dict[str, object]]) -> dict[str, int]:
    """Counts of changes keyed '<entity>_<change>' (for example component_added)."""
    counted = Counter(f"{change['entity']}_{change['change']}" for change in changes)
    return {key: counted[key] for key in sorted(counted)}


def limitation_notes(
    project_import: ProjectImport, invalidated: Sequence[dict[str, object]] = ()
) -> list[str]:
    """Envelope limitation_notes: import warnings '[code] message (location)' (max 50 plus a count entry), then
    one note per invalidated reference."""
    total = project_import.project_import_summary.warning_total
    notes = [f"[{w.code}] {w.message} ({w.location})" for w in project_import.warnings[:MAX_LIMITATION_NOTES]]
    if total > MAX_LIMITATION_NOTES:
        notes.append(
            f"{total - MAX_LIMITATION_NOTES} more import warnings not listed; "
            "see project_import_summary.warning_counts and project-graph.json"
        )
    for reference in invalidated:
        target = reference.get("component_id") or reference.get("group_address_id")
        notes.append(
            f"Invalidated reference ({reference['reason']}): {reference['reference_kind']} entry "
            f"'{reference['owner']}' names {target}, which no longer exists in the project; the entry is retained."
        )
    return notes
