"""Importer orchestration (story 04, T9): fingerprint, summary, errors and warnings end to end, no writes."""

from __future__ import annotations

import hashlib
import logging

import pytest
from conftest import build_case, fixture_cases

import knx_agent.application.project_importer as importer
from knx_agent.application.import_support import limitation_notes, log_import_warnings
from knx_agent.application.knxproj_archive import ArchiveLimits
from knx_agent.application.log_book import SessionLogBook
from knx_agent.application.project_importer import file_fingerprint, import_project
from knx_agent.contracts import PROJECT_FILE_UNREADABLE, PROJECT_PARSE_ERROR, LogLevel
from knx_agent.contracts import KnxAgentError
from knx_agent.domain import ImportWarning, ProjectImport, ProjectImportSummary
from knx_agent.domain.derivation import TypeOverride


def test_summary_of_the_default_archive(build):
    path = build()
    result = import_project(path)
    summary = result.summary
    assert summary.file_name == path.name and summary.archive_entry_count > 0
    assert summary.ets_tool_version == "6.1.5686.0"
    assert summary.schema_namespace == "http://knx.org/xml/project/22"
    assert (summary.project_id, summary.project_name) == ("P-0001", "Synthetic house")
    assert summary.group_address_style == "ThreeLevel"
    assert summary.node_counts == {
        "installation": 1, "area": 1, "line": 1, "space": 3, "component": 3, "communication_object": 6,
        "group_address": 3, "group_range": 2, "parameter": 2, "scene": 0, "application_program": 2,
    }  # fmt: skip
    assert summary.relation_counts == {"membership": 4, "placed_in": 2}
    assert sum(summary.component_type_counts.values()) == 3
    assert summary.application_programs.referenced == 2 and summary.application_programs.read == 2
    assert (summary.warning_total, summary.warning_counts) == (0, {})
    assert (summary.graph_file, summary.graph_schema_version) == ("project-graph.json", 1)
    assert result.graph.fingerprint == result.fingerprint
    assert result.warnings == [] and result.duration_s >= 0


def test_fingerprint_is_sha256_of_the_file_bytes(build):
    path = build()
    result = import_project(path)
    assert result.fingerprint == hashlib.sha256(path.read_bytes()).hexdigest() == file_fingerprint(path)
    assert (result.mtime_ns, result.size) == (path.stat().st_mtime_ns, path.stat().st_size)


def test_fingerprint_reads_in_chunks(build, monkeypatch):
    path = build()
    monkeypatch.setattr(importer, "HASH_CHUNK_BYTES", 7)
    assert file_fingerprint(path) == hashlib.sha256(path.read_bytes()).hexdigest()


def test_same_archive_twice_gives_identical_graph_and_summary(build):
    path = build()
    first, second = import_project(path), import_project(path)
    assert first.graph == second.graph and first.summary == second.summary
    assert first.graph.model_dump_json() == second.graph.model_dump_json()


def test_importer_writes_nothing(build, tmp_path):
    path = build(mutations=[{"op": "doctype", "entry": "master_xml"}])
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    import_project(path)
    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")) == before


@pytest.mark.parametrize("case", fixture_cases("import_error_cases.yaml", "cases"))
def test_import_error_cases_end_to_end(build, case):
    path = build_case(build, case)
    with pytest.raises(KnxAgentError) as excinfo:
        import_project(path)
    assert excinfo.value.error.code == PROJECT_PARSE_ERROR
    assert excinfo.value.error.details["reason"] == case["expected_reason"]


@pytest.mark.parametrize("case", fixture_cases("import_warning_cases.yaml", "cases"))
def test_import_warning_cases_end_to_end(build, case):
    result = import_project(build_case(build, case))
    assert result.summary.warning_counts == case["expected_codes"]
    assert result.summary.warning_total == len(result.warnings) == len(result.graph.warnings)
    assert [w.code for w in result.warnings] == [w.code for w in result.graph.warnings]


def test_missing_and_unreadable_file(tmp_path):
    with pytest.raises(KnxAgentError) as excinfo:
        import_project(tmp_path / "missing.knxproj")
    assert excinfo.value.error.code == PROJECT_FILE_UNREADABLE
    with pytest.raises(KnxAgentError) as excinfo:
        import_project(tmp_path)  # a directory
    assert excinfo.value.error.code == PROJECT_FILE_UNREADABLE


def test_archive_limits_are_passed_through(build):
    with pytest.raises(KnxAgentError) as excinfo:
        import_project(build(), ArchiveLimits(max_entries=2))
    assert excinfo.value.error.details["reason"] == "ARCHIVE_TOO_MANY_ENTRIES"


@pytest.mark.parametrize("changed", ["mtime", "size"])
def test_file_changed_during_import(build, monkeypatch, changed):
    path = build()
    original = importer.stat_project
    calls = {"n": 0}

    def shifting(p):
        mtime, size = original(p)
        calls["n"] += 1
        if calls["n"] == 1:
            return mtime, size
        return (mtime + 1, size) if changed == "mtime" else (mtime, size + 1)

    monkeypatch.setattr(importer, "stat_project", shifting)
    with pytest.raises(KnxAgentError) as excinfo:
        import_project(path)
    assert excinfo.value.error.code == PROJECT_FILE_UNREADABLE
    assert excinfo.value.error.details["reason"] == "CHANGED_DURING_IMPORT"


def test_type_overrides_are_a_parameter_only(build):
    path = build()
    default = import_project(path)
    component_id = "P-0001-0_DI-3"  # the only component with product M-0001_H-2_P-S2
    override = TypeOverride(match="product_ref_id", value="M-0001_H-2_P-S2", component_type="COUPLER")
    overridden = import_project(path, overrides=[override])
    assert overridden.graph.derived_facts.component_typing[component_id].component_type == "COUPLER"
    assert overridden.graph.derived_facts.component_typing[component_id].rule_id == "CT0_OVERRIDE"
    assert import_project(path).graph == default.graph  # nothing persisted or remembered


# --- warnings: limitation notes and log points ----------------------------------------------------------
def _warnings(count: int) -> list[ImportWarning]:
    return [ImportWarning(code="PARAMETER_DEFINITION_UNRESOLVED", message=f"m{i}", location=f"loc{i}") for i in range(count)]


def _import_block(total: int, persisted: int) -> ProjectImport:
    return ProjectImport(
        path="/p.knxproj", mtime=1, size=2, imported_at="t",
        project_import_summary=ProjectImportSummary(file_name="p.knxproj", archive_entry_count=1, warning_total=total),
        warnings=_warnings(persisted),
    )  # fmt: skip


@pytest.mark.parametrize(
    ("total", "persisted", "expected_count", "expect_more"),
    [(0, 0, 0, None), (3, 3, 3, None), (50, 50, 50, None), (51, 51, 51, 1), (250, 200, 51, 200)],
)
def test_limitation_notes_cap_at_50_with_a_count_entry(total, persisted, expected_count, expect_more):
    notes = limitation_notes(_import_block(total, persisted))
    if expect_more is None:
        assert len(notes) == expected_count
    else:
        assert len(notes) == 51 and notes[-1].startswith(f"{expect_more} more import warnings not listed;")
        assert "warning_counts" in notes[-1] and "project-graph.json" in notes[-1]
    if notes and expect_more is None:
        assert notes[0] == "[PARAMETER_DEFINITION_UNRESOLVED] m0 (loc0)"


def test_limitation_notes_append_invalidated_references():
    reference = {
        "reference_kind": "mutation_delta", "owner": "m1", "component_id": "DI-1", "group_address_id": None,
        "reason": "COMPONENT_REMOVED",
    }  # fmt: skip
    notes = limitation_notes(_import_block(0, 0), [reference])
    assert len(notes) == 1 and "COMPONENT_REMOVED" in notes[0] and "m1" in notes[0] and "DI-1" in notes[0]


def test_warning_debug_entries_are_capped_at_200(tmp_path, caplog):
    SessionLogBook.initialise(tmp_path)
    book = SessionLogBook(tmp_path, LogLevel.DEBUG)
    with caplog.at_level(logging.DEBUG, logger="knx_agent"):
        log_import_warnings(book, "create_session", "default", _warnings(250))
    lines = (tmp_path / "session-log-book.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 201
    assert "50 further import warnings" in lines[-1]
    python_warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(python_warnings) == 1 and "250 warnings" in python_warnings[0].getMessage()
    assert python_warnings[0].name == "knx_agent.application"


def test_no_warnings_means_no_logging(tmp_path, caplog):
    SessionLogBook.initialise(tmp_path)
    with caplog.at_level(logging.DEBUG, logger="knx_agent"):
        log_import_warnings(SessionLogBook(tmp_path, LogLevel.FULL), "create_session", "default", [])
    assert caplog.records == [] and (tmp_path / "session-log-book.jsonl").read_text() == ""
