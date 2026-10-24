"""Importer orchestration (story 04, T9): fingerprint, archive guard, parser, derivation, summary.

``import_project`` reads a .knxproj and returns an ``ImportResult``. It writes nothing: persisting the graph and
the session state is the caller's job (ProjectRefreshGuard, SessionLifecycle).
"""

from __future__ import annotations

import hashlib
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from knx_agent.contracts import PROJECT_FILE_UNREADABLE, error
from knx_agent.contracts.import_codes import REASON_CHANGED_DURING_IMPORT
from knx_agent.domain import (
    GRAPH_FILE_NAME,
    GRAPH_SCHEMA_VERSION,
    NODE_KINDS,
    RELATION_KINDS,
    ImportWarning,
    ProjectGraph,
    ProjectImportSummary,
)
from knx_agent.domain.derivation import TypeOverride, derive
from knx_agent.domain.project_graph import InstallationNode

from .knxproj_archive import ArchiveLimits, KnxprojArchive
from .knxproj_guard import stat_project
from .knxproj_parser import parse_project

HASH_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class ImportResult:
    """Everything one import produced; nothing of it has been persisted yet."""

    graph: ProjectGraph
    fingerprint: str
    mtime_ns: int
    size: int
    summary: ProjectImportSummary
    warnings: list[ImportWarning]
    duration_s: float


def file_fingerprint(path: Path) -> str:
    """SHA-256 of the file bytes (lowercase hex), read in 1 MiB chunks."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(HASH_CHUNK_BYTES):
                digest.update(chunk)
    except OSError as exc:
        raise error(PROJECT_FILE_UNREADABLE, f"Project file {path} cannot be read.", path=str(path)) from exc
    return digest.hexdigest()


def build_summary(
    file_name: str,
    archive_entry_count: int,
    graph: ProjectGraph,
    application_programs,  # noqa: ANN001 - ApplicationProgramCounts
) -> ProjectImportSummary:
    """The project_import_summary of 003 from a finished graph."""
    nodes = graph.source_facts.nodes
    installation = next((node for node in nodes if isinstance(node, InstallationNode)), None)
    kind_counts = Counter(node.kind for node in nodes)
    relations = graph.source_facts.relations
    relation_counts = {"membership": len(relations.membership), "placed_in": len(relations.placed_in)}
    warning_counts = Counter(warning.code for warning in graph.warnings)
    return ProjectImportSummary(
        file_name=file_name,
        archive_entry_count=archive_entry_count,
        ets_tool_version=installation.ets_tool_version if installation else None,
        schema_namespace=installation.schema_namespace if installation else None,
        created_by=installation.created_by if installation else None,
        project_id=installation.project_id if installation else None,
        project_name=installation.project_name if installation else None,
        group_address_style=installation.group_address_style if installation else None,
        node_counts={kind: kind_counts.get(kind, 0) for kind in NODE_KINDS},
        relation_counts={kind: relation_counts[kind] for kind in RELATION_KINDS},
        component_type_counts=dict(graph.derived_facts.derived_counts.component_type_counts),
        application_programs=application_programs,
        warning_total=len(graph.warnings),
        warning_counts={code: warning_counts[code] for code in sorted(warning_counts)},
        graph_file=GRAPH_FILE_NAME,
        graph_schema_version=GRAPH_SCHEMA_VERSION,
    )


def import_project(
    path: Path,
    limits: ArchiveLimits | None = None,
    overrides: tuple[TypeOverride, ...] | list[TypeOverride] = (),
) -> ImportResult:
    """Import a .knxproj: stat, fingerprint, archive guard, parser, derivation, summary.

    Raises PROJECT_FILE_UNREADABLE (also ``CHANGED_DURING_IMPORT`` when mtime or size changed while the import
    ran) and PROJECT_PARSE_ERROR (with ``details.reason``). Nothing is written.
    """
    started = time.perf_counter()
    path = Path(path)
    mtime_ns, size = stat_project(path)
    fingerprint = file_fingerprint(path)
    with KnxprojArchive(path, limits) as archive:
        entry_count = archive.entry_count
        parsed = parse_project(archive)
    source_facts = parsed.source_facts
    derived = derive(source_facts, overrides)
    graph = ProjectGraph(
        fingerprint=fingerprint,
        source_facts=source_facts,
        derived_facts=derived,
        warnings=list(parsed.warnings),
    )
    after_mtime, after_size = stat_project(path)
    if (after_mtime, after_size) != (mtime_ns, size):
        raise error(
            PROJECT_FILE_UNREADABLE,
            f"Project file {path} changed while it was being imported.",
            path=str(path),
            reason=REASON_CHANGED_DURING_IMPORT,
        )
    summary = build_summary(path.name, entry_count, graph, parsed.application_programs)
    return ImportResult(
        graph=graph,
        fingerprint=fingerprint,
        mtime_ns=mtime_ns,
        size=size,
        summary=summary,
        warnings=list(parsed.warnings),
        duration_s=round(time.perf_counter() - started, 3),
    )
