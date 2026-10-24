"""Tests on the committed sample project (story 04, T12). Every test skips when the sample file is absent."""

from __future__ import annotations

import hashlib
import json
import time
import zipfile
from pathlib import Path

import pytest
from conftest import load_fixture

from knx_agent.application.graph_store import serialize_graph
from knx_agent.application.project_importer import import_project
from knx_agent.sdk import KnxSessionClient

SAMPLE = Path(__file__).parent / "lifedata" / "20261010-EFH-Armbruster.knxproj"
COUNTS = load_fixture("sample_project_counts.yaml")
IMPORT_TIME_TARGET_S = 30.0
IMPORT_TIME_BOUND_S = 120.0

pytestmark = pytest.mark.skipif(
    not SAMPLE.exists(), reason=f"sample project {SAMPLE.name} is absent; sample-based tests are skipped"
)


@pytest.fixture(scope="module")
def imported():
    started = time.perf_counter()
    result = import_project(SAMPLE)
    return result, time.perf_counter() - started


def test_golden_counts(imported):
    summary = imported[0].summary
    assert summary.file_name == COUNTS["sample_file"]
    assert summary.project_id == COUNTS["project_id"]
    assert summary.ets_tool_version == COUNTS["ets_tool_version"]
    assert summary.schema_namespace == COUNTS["schema_namespace"]
    assert summary.created_by == COUNTS["created_by"]
    assert summary.group_address_style == COUNTS["group_address_style"]
    assert summary.archive_entry_count == COUNTS["archive_entry_count"]
    assert summary.node_counts == COUNTS["node_counts"]
    assert summary.relation_counts == COUNTS["relation_counts"]
    assert summary.component_type_counts == COUNTS["component_type_counts"]
    assert summary.application_programs.model_dump() == COUNTS["application_programs"]
    assert summary.warning_total == COUNTS["warning_total"]
    assert summary.warning_counts == COUNTS["warning_counts"]


def test_expected_warnings_all_belong_to_one_component(imported):
    result = imported[0]
    assert len(result.warnings) == COUNTS["warning_total"]
    assert all(COUNTS["warning_component"] in warning.location for warning in result.warnings)


def test_program_xmls_are_opened_only_when_referenced(monkeypatch):
    opened: list[str] = []
    original = zipfile.ZipFile.open

    def recording(self, name, *args, **kwargs):
        opened.append(getattr(name, "filename", name))
        return original(self, name, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "open", recording)
    result = import_project(SAMPLE)
    with zipfile.ZipFile(SAMPLE) as archive:
        program_entries = [n for n in archive.namelist() if n.count("/") == 1 and "_A-" in n and n.endswith(".xml")]
    assert len(program_entries) == COUNTS["application_programs"]["read"] + 1  # 13 in the archive
    assert COUNTS["unreferenced_program_entry"] in program_entries
    assert COUNTS["unreferenced_program_entry"] not in opened
    # each referenced program is opened twice: once by the XML guard scan, once by the parser
    opened_programs = [name for name in opened if name in program_entries]
    assert len(set(opened_programs)) == COUNTS["application_programs"]["read"]
    assert len(opened_programs) == 2 * COUNTS["application_programs"]["read"]
    program_ids = {node.id for node in result.graph.nodes_of("application_program")}
    assert COUNTS["unreferenced_program_id"] not in program_ids


def test_stable_ids_and_byte_identical_graph(imported):
    first = imported[0]
    second = import_project(SAMPLE)
    assert [n.id for n in first.graph.source_facts.nodes] == [n.id for n in second.graph.source_facts.nodes]
    assert serialize_graph(first.graph) == serialize_graph(second.graph)
    component_ids = {node.id for node in first.graph.nodes_of("component")}
    assert set(COUNTS["example_component_ids"]) <= component_ids
    assert len({n.id for n in first.graph.source_facts.nodes}) == len(first.graph.source_facts.nodes)


def test_component_typing_is_derived_only(imported):
    graph = imported[0].graph
    typing = graph.derived_facts.component_typing
    components = graph.nodes_of("component")
    assert set(typing) == {component.id for component in components}
    for node in graph.source_facts.nodes:
        dumped = node.model_dump()
        assert "component_type" not in dumped and "rule_id" not in dumped
    assert all(entry.rule_id and entry.basis is not None for entry in typing.values())


def test_import_time_bound(imported):
    elapsed = imported[1]
    print(f"\nsample import (hash, guard, parse, derive): {elapsed:.2f} s (target {IMPORT_TIME_TARGET_S:.0f} s)")
    assert elapsed <= IMPORT_TIME_BOUND_S


def test_session_flow_on_the_sample(tmp_path):
    client = KnxSessionClient(session_root=tmp_path / "sessions")
    started = time.perf_counter()
    created = client.create_session(project_path=SAMPLE, session_label="sample")
    elapsed = time.perf_counter() - started
    graph_file = Path(created.work_directory) / "project-graph.json"
    print(f"\nsample create_session end to end: {elapsed:.2f} s, graph file {graph_file.stat().st_size} bytes")
    assert elapsed <= IMPORT_TIME_BOUND_S
    assert created.project_import_summary.node_counts == COUNTS["node_counts"]
    assert len(created.envelope.limitation_notes) == COUNTS["warning_total"]
    assert all(note.startswith("[") for note in created.envelope.limitation_notes)
    fingerprint = hashlib.sha256(SAMPLE.read_bytes()).hexdigest()
    persisted = json.loads(graph_file.read_text(encoding="utf-8"))
    assert persisted["fingerprint"] == fingerprint and persisted["graph_schema_version"] == 1

    described = client.describe_session(session_label="sample")
    assert described.project_import.fingerprint == fingerprint
    assert described.project_import.graph_file == str(graph_file)
    assert described.project_refresh.last_status == "UNCHANGED" and described.project_refresh.reimport_count == 0

    reimported = client.reimport_system_definition(session_label="sample")
    assert reimported.project_refresh_status == "UNCHANGED"
    assert reimported.changes == [] and reimported.invalidated_references == []
    assert reimported.project_import_summary == created.project_import_summary
    assert json.loads(graph_file.read_text(encoding="utf-8")) == persisted
