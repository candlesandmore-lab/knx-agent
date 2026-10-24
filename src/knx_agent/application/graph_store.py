"""Persistence of the project graph as project-graph.json in the work-directory (story 04, T8).

UTF-8 JSON, sorted keys, 1-space indent, no timestamps (an unchanged project re-imports to byte-identical
content), written atomically: temporary file in the same folder, then ``os.replace``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from knx_agent.domain import GRAPH_FILE_NAME, ProjectGraph

JSON_INDENT = 1  # compact (None) only if the measured sample graph file exceeds 20 MB (003 'Persistence')


@dataclass(frozen=True)
class GraphReadResult:
    """Outcome of reading project-graph.json. A missing or corrupt file is a result, not an exception."""

    graph: ProjectGraph | None
    problem: str | None = None  # 'MISSING', 'UNREADABLE' or 'INVALID' when graph is None

    @property
    def ok(self) -> bool:
        return self.graph is not None


def graph_path(work_directory: Path) -> Path:
    """Path of project-graph.json inside a work-directory."""
    return work_directory / GRAPH_FILE_NAME


def serialize_graph(graph: ProjectGraph, indent: int | None = JSON_INDENT) -> bytes:
    """Deterministic UTF-8 JSON bytes of a graph (sorted keys, trailing newline)."""
    text = json.dumps(
        graph.model_dump(mode="json"),
        sort_keys=True,
        indent=indent,
        ensure_ascii=False,
        separators=None if indent is not None else (",", ":"),
    )
    return (text + "\n").encode("utf-8")


def write_graph(work_directory: Path, graph: ProjectGraph, indent: int | None = JSON_INDENT) -> Path:
    """Write project-graph.json atomically; a failure leaves the previous file intact."""
    target = graph_path(work_directory)
    temp = work_directory / f".{GRAPH_FILE_NAME}.tmp-{os.getpid()}"
    try:
        with temp.open("wb") as handle:
            handle.write(serialize_graph(graph, indent))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    return target


def read_graph(work_directory: Path) -> GraphReadResult:
    """Read and validate project-graph.json; missing or corrupt files give a result with a problem."""
    path = graph_path(work_directory)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return GraphReadResult(None, "MISSING")
    except OSError:
        return GraphReadResult(None, "UNREADABLE")
    try:
        return GraphReadResult(ProjectGraph.model_validate(json.loads(raw.decode("utf-8"))))
    except (ValueError, ValidationError):  # UnicodeDecodeError and JSONDecodeError are ValueErrors
        return GraphReadResult(None, "INVALID")
