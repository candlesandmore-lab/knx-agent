"""Graph persistence (project-graph.json) and the session-state shape (story 04, T8)."""

from __future__ import annotations

import json
import os

import pytest
import yaml
from conftest import parse_archive

from knx_agent.application import graph_store
from knx_agent.application.graph_store import graph_path, read_graph, serialize_graph, write_graph
from knx_agent.application.session_paths import read_state, write_state
from knx_agent.contracts import KnxAgentError
from knx_agent.domain import (
    GRAPH_FILE_NAME,
    MAX_PERSISTED_WARNINGS,
    ImportWarning,
    ProjectGraph,
    ProjectImport,
    ProjectImportSummary,
    SessionState,
)
from knx_agent.domain.derivation import derive


@pytest.fixture
def graph(build) -> ProjectGraph:
    parsed, _ = parse_archive(build(mutations=[{"op": "remove", "entry": "master_xml"}]))
    return ProjectGraph(
        fingerprint="a" * 64,
        source_facts=parsed.source_facts,
        derived_facts=derive(parsed.source_facts),
        warnings=parsed.warnings,
    )


def test_file_name_and_top_level_keys(tmp_path, graph):
    path = write_graph(tmp_path, graph)
    assert path == tmp_path / "project-graph.json" == graph_path(tmp_path)
    assert GRAPH_FILE_NAME == "project-graph.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {"graph_schema_version", "fingerprint", "source_facts", "derived_facts", "warnings"}
    assert data["graph_schema_version"] == 1
    assert data["fingerprint"] == "a" * 64
    assert set(data["source_facts"]) == {"nodes", "relations"}


def test_format_is_utf8_sorted_keys_one_space_indent(tmp_path, graph):
    raw = write_graph(tmp_path, graph).read_bytes()
    text = raw.decode("utf-8")
    assert text.endswith("}\n")
    assert text.splitlines()[1].startswith(" \"") and not text.splitlines()[1].startswith("  ")  # 1-space indent
    keys = [line.strip().split('"')[1] for line in text.splitlines()[1:6] if line.startswith(' "')]
    assert keys == sorted(keys)


def test_json_contains_no_wall_clock_timestamps(tmp_path, graph):
    text = write_graph(tmp_path, graph).read_text(encoding="utf-8")
    for token in ("imported_at", "created_at", "duration"):
        assert token not in text


def test_round_trip_is_lossless(tmp_path, graph):
    write_graph(tmp_path, graph)
    result = read_graph(tmp_path)
    assert result.ok and result.problem is None
    assert result.graph == graph
    assert [type(n) for n in result.graph.source_facts.nodes] == [type(n) for n in graph.source_facts.nodes]


def test_rewrite_is_byte_identical(tmp_path, graph):
    first = write_graph(tmp_path, graph).read_bytes()
    again = write_graph(tmp_path, ProjectGraph.model_validate(json.loads(first))).read_bytes()
    assert again == first
    assert serialize_graph(graph) == first


def test_two_imports_of_the_same_archive_persist_identically(tmp_path, build):
    path = build()
    blobs = []
    for index in range(2):
        parsed, _ = parse_archive(path)
        directory = tmp_path / f"w{index}"
        directory.mkdir()
        graph = ProjectGraph(fingerprint="f" * 64, source_facts=parsed.source_facts, derived_facts=derive(parsed.source_facts), warnings=parsed.warnings)
        blobs.append(write_graph(directory, graph).read_bytes())
    assert blobs[0] == blobs[1]


def test_compact_serialisation_is_available(graph):
    compact, indented = serialize_graph(graph, indent=None), serialize_graph(graph)
    assert len(compact) < len(indented)
    assert json.loads(compact) == json.loads(indented)
    assert b"\n" not in compact.rstrip(b"\n")


@pytest.fixture
def work(tmp_path):
    """An empty work-directory next to the 'built' folder of the archive factory."""
    directory = tmp_path / "work"
    directory.mkdir()
    return directory


def test_no_temporary_file_is_left_behind(work, graph):
    write_graph(work, graph)
    assert sorted(p.name for p in work.iterdir()) == ["project-graph.json"]


def test_failed_write_leaves_the_previous_file_intact(work, graph, monkeypatch):
    write_graph(work, graph)
    before = (work / "project-graph.json").read_bytes()
    changed = graph.model_copy(update={"fingerprint": "b" * 64})

    def boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(graph_store.os, "replace", boom)
    with pytest.raises(OSError):
        write_graph(work, changed)
    assert (work / "project-graph.json").read_bytes() == before
    assert sorted(p.name for p in work.iterdir()) == ["project-graph.json"]  # temp file removed


def test_failed_serialisation_leaves_the_previous_file_intact(work, graph, monkeypatch):
    write_graph(work, graph)
    before = (work / "project-graph.json").read_bytes()
    monkeypatch.setattr(graph_store, "serialize_graph", lambda *_a, **_k: (_ for _ in ()).throw(ValueError("bad")))
    with pytest.raises(ValueError):
        write_graph(work, graph)
    assert (work / "project-graph.json").read_bytes() == before
    assert [p.name for p in work.iterdir()] == ["project-graph.json"]


@pytest.mark.parametrize(
    ("content", "problem"),
    [
        (None, "MISSING"),
        (b"", "INVALID"),
        (b"{not json", "INVALID"),
        (b"[]", "INVALID"),
        (b"\xff\xfe\x00", "INVALID"),
        (json.dumps({"graph_schema_version": 1, "source_facts": {"nodes": [{"kind": "alien", "id": "x"}]}}).encode(), "INVALID"),
        (json.dumps({"graph_schema_version": "one"}).encode(), "INVALID"),
    ],
)
def test_missing_or_corrupt_graph_is_a_result_not_an_exception(tmp_path, content, problem):
    if content is not None:
        (tmp_path / "project-graph.json").write_bytes(content)
    result = read_graph(tmp_path)
    assert result.graph is None and not result.ok
    assert result.problem == problem


def test_unreadable_graph_file_is_a_result(tmp_path):
    (tmp_path / "project-graph.json").mkdir()  # a directory cannot be read as a file
    result = read_graph(tmp_path)
    assert result.graph is None and result.problem in ("UNREADABLE", "INVALID")


# -- session-state.yaml shape -------------------------------------------------------------------
def _state(tmp_path, warnings=None) -> SessionState:
    summary = ProjectImportSummary(
        file_name="a.knxproj", archive_entry_count=7, ets_tool_version="6.1.5686.0", project_id="P-0001",
        node_counts={"component": 3}, relation_counts={"membership": 4}, component_type_counts={"SENSOR": 1},
        application_programs={"referenced": 2, "read": 2, "unreadable": 0}, warning_total=len(warnings or []),
        warning_counts={"DUPLICATE_ID": len(warnings or [])}, graph_file="project-graph.json", graph_schema_version=1,
    )  # fmt: skip
    return SessionState(
        session_label="s1", created_at="t", work_directory=str(tmp_path), source_project_absolute_path="/p/a.knxproj",
        project_import=ProjectImport(
            path="/p/a.knxproj", mtime=1, size=2, imported_at="t", fingerprint="c" * 64, graph_file="project-graph.json",
            graph_schema_version=1, project_import_summary=summary, warnings=warnings or [],
        ),
    )  # fmt: skip


def test_session_state_round_trip_with_the_new_project_import(tmp_path):
    state = _state(tmp_path, [ImportWarning(code="DUPLICATE_ID", message="m", location="l")])
    write_state(tmp_path, state)
    assert read_state(tmp_path) == state


def test_project_import_key_order_in_session_state_yaml(tmp_path):
    write_state(tmp_path, _state(tmp_path))
    data = yaml.safe_load((tmp_path / "session-state.yaml").read_text(encoding="utf-8"))
    assert list(data["project_import"]) == [
        "path", "mtime", "size", "imported_at", "fingerprint", "graph_file", "graph_schema_version",
        "project_import_summary", "warnings",
    ]  # fmt: skip
    assert list(data)[:5] == ["session_label", "created_at", "work_directory", "source_project_absolute_path", "project_import"]
    assert data["project_import"]["fingerprint"] == "c" * 64
    assert data["project_import"]["graph_file"] == "project-graph.json"


def test_summary_has_the_documented_fields_and_all_node_kinds_can_be_counted():
    fields = set(ProjectImportSummary.model_fields)
    assert fields >= {
        "file_name", "archive_entry_count", "ets_tool_version", "schema_namespace", "created_by", "project_id",
        "project_name", "group_address_style", "node_counts", "relation_counts", "component_type_counts",
        "application_programs", "warning_total", "warning_counts", "graph_file", "graph_schema_version",
    }  # fmt: skip
    assert MAX_PERSISTED_WARNINGS == 200


def test_state_write_stays_atomic(tmp_path, monkeypatch):
    state = _state(tmp_path)
    write_state(tmp_path, state)
    before = (tmp_path / "session-state.yaml").read_bytes()
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("fail")))
    with pytest.raises(OSError):
        write_state(tmp_path, state.model_copy(update={"active_setup": "other"}))
    assert (tmp_path / "session-state.yaml").read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["session-state.yaml"]


def test_story_03_state_files_are_not_migrated(tmp_path):
    legacy = {
        "session_label": "old", "created_at": "t", "work_directory": str(tmp_path),
        "source_project_absolute_path": "/p/a.knxproj",
        "project_import": {
            "path": "/p/a.knxproj", "mtime": 1, "size": 2, "imported_at": "t", "fingerprint": None,
            "project_import_summary": {"file_name": "a.knxproj", "archive_entry_count": 2, "limitation_note": "x"},
        },
    }  # fmt: skip
    (tmp_path / "session-state.yaml").write_text(yaml.safe_dump(legacy), encoding="utf-8")
    with pytest.raises(KnxAgentError) as excinfo:  # limitation_note is gone: story 03 sessions must be recreated
        read_state(tmp_path)
    assert excinfo.value.error.code == "SESSION_NOT_FOUND"
