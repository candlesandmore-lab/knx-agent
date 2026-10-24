"""Session service tests, SDK-first: create, describe, reimport, refresh guard, log book, ERROR logging."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import zipfile
from pathlib import Path

import pytest
import yaml
from conftest import apply_change, fixture_cases, read_log_book, rebuild_project, state_bytes

import knx_agent.application.project_importer as importer
from knx_agent.contracts import KnxAgentError
from knx_agent.domain import SessionState
from knx_agent.sdk import KnxSessionClient

LABELS = "session_label_cases.yaml"
STATE_FIELDS = [
    "session_label",
    "created_at",
    "work_directory",
    "source_project_absolute_path",
    "project_import",
    "project_refresh",
    "active_setup",
    "trace_artifacts",
    "scenario_state",
    "mutations",
    "log_book_references",
    "mutation_log_book_references",
]


def code_of(excinfo) -> str:
    return excinfo.value.error.code


def folders(root: Path) -> list[str]:
    return sorted(p.name for p in root.iterdir()) if root.exists() else []


# --- labels -----------------------------------------------------------------------------------
@pytest.mark.parametrize("case", fixture_cases(LABELS, "valid_for_create"))
def test_valid_labels_create_session(case, client, project, session_root):
    response = client.create_session(project_path=project, session_label=case["label"])
    assert response.session_label == case["label"]
    assert folders(session_root) == [case["label"]]


@pytest.mark.parametrize("case", fixture_cases(LABELS, "invalid_for_create"))
def test_invalid_labels_rejected_on_create(case, client, project, session_root):
    with pytest.raises(KnxAgentError) as excinfo:
        client.create_session(project_path=project, session_label=case["label"])
    assert code_of(excinfo) == "SESSION_LABEL_INVALID"
    assert folders(session_root) == []


@pytest.mark.parametrize("case", fixture_cases(LABELS, "existing_session_calls"))
def test_label_rules_on_existing_session_calls(case, client):
    for call in (client.describe_session, client.reimport_system_definition):
        with pytest.raises(KnxAgentError) as excinfo:
            call(session_label=case["label"])
        assert code_of(excinfo) == case["expected_code"]


# --- create: error order and atomicity --------------------------------------------------------
@pytest.mark.parametrize("case", fixture_cases("create_session_error_cases.yaml", "cases"))
def test_create_error_order_and_no_leftovers(case, client, make_project, session_root):
    if case["label_exists"]:
        client.create_session(project_path=make_project("zip", "other.knxproj"), session_label=case["label"])
    before = folders(session_root)
    project = make_project(case["project"])
    with pytest.raises(KnxAgentError) as excinfo:
        client.create_session(project_path=project, session_label=case["label"])
    assert code_of(excinfo) == case["expected_code"]
    if "expected_reason" in case:
        assert excinfo.value.error.details["reason"] == case["expected_reason"]
    assert folders(session_root) == before  # no temporary or half-built folder survives


def test_failed_create_does_not_block_label(client, make_project, session_root):
    with pytest.raises(KnxAgentError):
        client.create_session(project_path=make_project("not_zip"), session_label="s1")
    assert folders(session_root) == []
    client.create_session(project_path=make_project("zip"), session_label="s1")
    assert folders(session_root) == ["s1"]


def test_create_cleans_up_when_state_write_fails(monkeypatch, client, project, session_root):
    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr("knx_agent.application.session_lifecycle.write_state", boom)
    with pytest.raises(OSError):
        client.create_session(project_path=project, session_label="s1")
    assert folders(session_root) == []


def test_create_cleans_up_when_rename_fails(monkeypatch, client, project, session_root):
    def boom(*_a, **_k):
        raise OSError("rename failed")

    monkeypatch.setattr("knx_agent.application.session_lifecycle.os.rename", boom)
    with pytest.raises(OSError):
        client.create_session(project_path=project, session_label="s1")
    assert folders(session_root) == []


def test_rename_race_maps_to_label_exists(monkeypatch, client, project, session_root):
    def lose_race(src, dst):
        Path(dst).mkdir()
        Path(dst, "x").write_text("other session")
        raise OSError("directory not empty")

    monkeypatch.setattr("knx_agent.application.session_lifecycle.os.rename", lose_race)
    with pytest.raises(KnxAgentError) as excinfo:
        client.create_session(project_path=project, session_label="s1")
    assert code_of(excinfo) == "SESSION_LABEL_EXISTS"
    assert folders(session_root) == ["s1"]  # only the winner's folder, temp folder removed


# --- create: success content --------------------------------------------------------------------
def test_create_session_response_and_files(client, project, session_root):
    response = client.create_session(project_path=project, session_label="house-1")
    work = session_root.resolve() / "house-1"
    assert response.work_directory == str(work)
    assert response.session_state_path == str(work / "session-state.yaml")
    assert response.source_project_absolute_path == str(project.resolve())
    assert response.active_setup == "default"
    summary = response.project_import_summary
    assert summary.file_name == "house.knxproj"
    assert summary.archive_entry_count == len(zipfile.ZipFile(project).namelist())
    assert summary.node_counts["component"] == 3 and summary.node_counts["scene"] == 0
    assert summary.relation_counts == {"membership": 4, "placed_in": 2}
    assert summary.warning_total == 0 and summary.graph_file == "project-graph.json"
    assert response.envelope.limitation_notes == []
    assert response.envelope.evidence_sources[0].kind.value == "KNXPROJ"
    assert response.envelope.log_book_entry_id == 1
    assert sorted(p.name for p in work.iterdir()) == ["project-graph.json", "session-log-book.jsonl", "session-state.yaml"]


def test_session_state_fields(client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    data = yaml.safe_load(state_bytes(session_root, "s1"))
    assert list(data) == STATE_FIELDS
    stat = project.stat()
    assert data["session_label"] == "s1"
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", data["created_at"])
    assert data["work_directory"] == str(session_root.resolve() / "s1")
    assert data["source_project_absolute_path"] == str(project.resolve())
    imported = data["project_import"]
    assert imported["path"] == str(project.resolve())
    assert imported["mtime"] == stat.st_mtime_ns and isinstance(imported["mtime"], int)
    assert imported["size"] == stat.st_size
    assert imported["imported_at"]
    assert imported["fingerprint"] == hashlib.sha256(project.read_bytes()).hexdigest()
    assert imported["graph_file"] == "project-graph.json" and imported["graph_schema_version"] == 1
    assert imported["warnings"] == []
    assert list(imported) == [
        "path", "mtime", "size", "imported_at", "fingerprint", "graph_file", "graph_schema_version",
        "project_import_summary", "warnings",
    ]  # fmt: skip
    assert imported["project_import_summary"]["file_name"] == "house.knxproj"
    assert imported["project_import_summary"]["archive_entry_count"] == len(zipfile.ZipFile(project).namelist())
    assert "limitation_note" not in imported["project_import_summary"]
    assert data["project_refresh"] == {"last_status": "UNCHANGED", "last_reimported_at": None, "reimport_count": 0}
    assert data["active_setup"] == "default"
    assert data["trace_artifacts"] == [] and data["scenario_state"] == [] and data["mutations"] == []
    assert data["log_book_references"] == ["session-log-book.jsonl"]
    assert data["mutation_log_book_references"] == {}
    assert "session_id" not in data
    assert SessionState.model_validate(data).model_dump(mode="json") == data  # lossless round trip


def test_default_session_root_is_relative_to_cwd(monkeypatch, tmp_path, project):
    monkeypatch.chdir(tmp_path)
    response = KnxSessionClient().create_session(project_path=project, session_label="s1")
    assert response.work_directory == str((tmp_path / ".knx-agent" / "sessions" / "s1").resolve())


def test_env_vars_have_no_effect(monkeypatch, tmp_path, project):
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    for name in ("KNX_AGENT_SESSION_ROOT", "KNX_AGENT_SESSIONS", "SESSION_ROOT", "KNX_SESSION_ROOT"):
        monkeypatch.setenv(name, str(tmp_path / "from-env"))
    for name in ("KNX_AGENT_LOG_LEVEL", "LOG_LEVEL", "KNX_LOG_LEVEL"):
        monkeypatch.setenv(name, "FULL")
    client = KnxSessionClient()
    response = client.create_session(project_path=project, session_label="s1")
    assert response.work_directory == str((work / ".knx-agent" / "sessions" / "s1").resolve())
    assert not (tmp_path / "from-env").exists()
    client.describe_session(session_label="s1")  # unchanged check is DEBUG; FULL from env must not apply
    assert [e["level"] for e in read_log_book(work / ".knx-agent" / "sessions", "s1")] == ["INFO"]


def test_source_does_not_read_environment():
    src = Path(__file__).resolve().parent.parent / "src" / "knx_agent"
    for path in src.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"os\.environ|getenv|from os import environ", text), path


# --- uniqueness, not found, describe -----------------------------------------------------------
def test_label_unique_and_unknown_session(client, make_project, session_root):
    client.create_session(project_path=make_project("zip"), session_label="s1")
    with pytest.raises(KnxAgentError) as excinfo:
        client.create_session(project_path=make_project("zip"), session_label="s1")
    assert code_of(excinfo) == "SESSION_LABEL_EXISTS"
    with pytest.raises(KnxAgentError) as excinfo:
        client.describe_session(session_label="s2")
    assert code_of(excinfo) == "SESSION_NOT_FOUND"


def test_folder_without_state_is_not_found(client, session_root):
    (session_root / "broken").mkdir(parents=True)
    with pytest.raises(KnxAgentError) as excinfo:
        client.describe_session(session_label="broken")
    assert code_of(excinfo) == "SESSION_NOT_FOUND"


def test_two_sessions_are_independent(client, make_project):
    client.create_session(project_path=make_project("zip", "a.knxproj"), session_label="a")
    client.create_session(project_path=make_project("zip", "b.knxproj"), session_label="b")
    assert client.describe_session(session_label="a").source_project_absolute_path.endswith("a.knxproj")
    assert client.describe_session(session_label="b").source_project_absolute_path.endswith("b.knxproj")


# --- refresh check -------------------------------------------------------------------------------
@pytest.mark.parametrize("case", fixture_cases("refresh_change_cases.yaml", "cases"))
def test_describe_runs_refresh_check(case, client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    before = state_bytes(session_root, "s1")
    apply_change(project, case["change"])
    if "describe_error" in case:
        with pytest.raises(KnxAgentError) as excinfo:
            client.describe_session(session_label="s1")
        assert code_of(excinfo) == case["describe_error"]
        assert state_bytes(session_root, "s1") == before  # state untouched
        return
    response = client.describe_session(session_label="s1")
    assert response.project_refresh.last_status == case["describe_status"]
    assert response.project_refresh.reimport_count == case["describe_reimport_count"]
    data = yaml.safe_load(state_bytes(session_root, "s1"))
    assert data["project_refresh"]["reimport_count"] == case["describe_reimport_count"]
    if case["describe_status"] == "CHANGED":
        stat = project.stat()
        assert (data["project_import"]["mtime"], data["project_import"]["size"]) == (stat.st_mtime_ns, stat.st_size)
        assert data["project_refresh"]["last_reimported_at"]


@pytest.mark.parametrize("case", fixture_cases("refresh_change_cases.yaml", "cases"))
def test_reimport_system_definition(case, client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    before = state_bytes(session_root, "s1")
    apply_change(project, case["change"])
    if "reimport_error" in case:
        with pytest.raises(KnxAgentError) as excinfo:
            client.reimport_system_definition(session_label="s1")
        assert code_of(excinfo) == case["reimport_error"]
        assert state_bytes(session_root, "s1") == before
        return
    response = client.reimport_system_definition(session_label="s1")
    assert response.project_refresh_status == case["reimport_status"]
    assert response.changes == [] and response.invalidated_references == []
    assert response.project_import_summary.file_name == "house.knxproj"
    data = yaml.safe_load(state_bytes(session_root, "s1"))
    assert data["project_refresh"]["last_status"] == case["reimport_status"]
    assert data["project_refresh"]["reimport_count"] == case["reimport_count_after_reimport"]
    assert response.envelope.log_book_entry_id == 2


def test_explicit_reimport_updates_imported_at_even_when_unchanged(monkeypatch, client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    monkeypatch.setattr("knx_agent.application.project_refresh_guard.utc_now", lambda: "2099-01-01T00:00:00Z")
    client.reimport_system_definition(session_label="s1")
    data = yaml.safe_load(state_bytes(session_root, "s1"))
    assert data["project_import"]["imported_at"] == "2099-01-01T00:00:00Z"


def test_refresh_check_is_idempotent(client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    before = state_bytes(session_root, "s1")
    first = client.describe_session(session_label="s1")
    second = client.describe_session(session_label="s1")
    assert state_bytes(session_root, "s1") == before == state_bytes(session_root, "s1")
    assert first.project_refresh == second.project_refresh
    assert first.project_refresh.reimport_count == 0


def test_changed_refresh_is_idempotent_afterwards(client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    apply_change(project, "both")
    client.describe_session(session_label="s1")
    after_first = state_bytes(session_root, "s1")
    client.describe_session(session_label="s1")
    assert state_bytes(session_root, "s1") == after_first  # no second re-import


def test_state_write_failure_keeps_previous_state(monkeypatch, client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    before = state_bytes(session_root, "s1")
    graph_before = (session_root / "s1" / "project-graph.json").read_bytes()
    apply_change(project, "both")

    def boom(*_a, **_k):
        raise OSError("replace failed")

    monkeypatch.setattr("knx_agent.application.session_paths.os.replace", boom)
    with pytest.raises(OSError):
        client.describe_session(session_label="s1")
    assert state_bytes(session_root, "s1") == before
    assert sorted(p.name for p in (session_root / "s1").iterdir()) == [
        "project-graph.json", "session-log-book.jsonl", "session-state.yaml",
    ]  # no temporary files; graph and state are those of the first import  # fmt: skip
    assert graph_before == (session_root / "s1" / "project-graph.json").read_bytes()


# --- log book ---------------------------------------------------------------------------------------
def _run_scenario(scenario, client, project, session_root, log_level):
    client.create_session(project_path=project, session_label="s1", log_level=log_level)
    change = {
        "describe_changed": "both",
        "describe_missing_file": "missing",
        "reimport_missing_file": "missing",
        "describe_not_zip": "not_zip",
    }.get(scenario, "none")
    apply_change(project, change)
    swallow = KnxAgentError
    try:
        if scenario.startswith("reimport"):
            client.reimport_system_definition(session_label="s1", log_level=log_level)
        elif scenario != "create":
            client.describe_session(session_label="s1", log_level=log_level)
    except swallow:
        pass


@pytest.mark.parametrize("case", fixture_cases("log_level_cases.yaml", "cases"))
def test_log_book_levels(case, client, project, session_root):
    _run_scenario(case["scenario"], client, project, session_root, case["log_level"])
    entries = read_log_book(session_root, "s1")
    assert [e["level"] for e in entries] == case["expected_levels"]
    assert [e["entry_id"] for e in entries] == list(range(1, len(entries) + 1))


def test_log_book_entry_shape_and_content(client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    apply_change(project, "both")
    described = client.describe_session(session_label="s1")
    reimported = client.reimport_system_definition(session_label="s1")
    entries = read_log_book(session_root, "s1")
    assert [e["capability"] for e in entries] == ["create_session", "describe_session", "reimport_system_definition"]
    for entry in entries:
        assert set(entry) == {"entry_id", "timestamp", "level", "capability", "setup", "summary", "details"}
        assert entry["setup"] == "default"
    assert entries[0]["details"]["session_label"] == "s1"
    assert {"old_mtime", "old_size", "new_mtime", "new_size"} <= set(entries[1]["details"])
    assert entries[2]["details"]["status"] == "UNCHANGED"
    assert described.envelope.log_book_entry_id == 2
    assert reimported.envelope.log_book_entry_id == 3


def test_log_book_is_append_only(client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    first_line = (session_root / "s1" / "session-log-book.jsonl").read_text().splitlines()[0]
    client.reimport_system_definition(session_label="s1")
    lines = (session_root / "s1" / "session-log-book.jsonl").read_text().splitlines()
    assert lines[0] == first_line and len(lines) == 2


def test_describe_writes_no_own_entry_at_info(client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    response = client.describe_session(session_label="s1")
    assert response.envelope.log_book_entry_id is None
    assert len(read_log_book(session_root, "s1")) == 1


def test_client_level_and_per_call_level(project, session_root):
    debug_client = KnxSessionClient(session_root=session_root, log_level="DEBUG")
    debug_client.create_session(project_path=project, session_label="s1")
    debug_client.describe_session(session_label="s1")
    assert [e["level"] for e in read_log_book(session_root, "s1")] == ["DEBUG", "INFO", "DEBUG"]
    debug_client.describe_session(session_label="s1", log_level="INFO")  # per-call override
    assert len(read_log_book(session_root, "s1")) == 3


@pytest.mark.parametrize("bad", ["TRACE", "ERROR", "", "verbose"])
def test_invalid_log_level(bad, client, project, session_root):
    with pytest.raises(KnxAgentError) as excinfo:
        client.create_session(project_path=project, session_label="s1", log_level=bad)
    assert code_of(excinfo) == "INVALID_LOG_LEVEL"
    assert folders(session_root) == []


# --- Python logging (ERROR) -------------------------------------------------------------------------------
def _error_records(caplog):
    return [r for r in caplog.records if r.levelno == logging.ERROR and r.name.startswith("knx_agent")]


def test_failed_create_logs_error_to_python_logger_only(caplog, client, make_project, session_root):
    with caplog.at_level(logging.DEBUG, logger="knx_agent"):
        with pytest.raises(KnxAgentError):
            client.create_session(project_path=make_project("not_zip"), session_label="s1")
    records = _error_records(caplog)
    assert len(records) == 1 and "PROJECT_PARSE_ERROR" in records[0].getMessage()
    assert folders(session_root) == []  # no log book exists for a failed create


@pytest.mark.parametrize("log_level", ["INFO", "DEBUG", "FULL"])
def test_error_goes_to_logger_and_log_book_at_every_level(log_level, caplog, client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    apply_change(project, "missing")
    with caplog.at_level(logging.INFO, logger="knx_agent"):
        with pytest.raises(KnxAgentError):
            client.describe_session(session_label="s1", log_level=log_level)
    records = _error_records(caplog)
    assert len(records) == 1 and "PROJECT_FILE_UNREADABLE" in records[0].getMessage()
    entry = read_log_book(session_root, "s1")[-1]
    assert entry["level"] == "ERROR" and entry["capability"] == "describe_session"
    assert entry["details"]["code"] == "PROJECT_FILE_UNREADABLE"


def test_session_not_found_logs_error_to_logger(caplog, client):
    with caplog.at_level(logging.INFO, logger="knx_agent"):
        with pytest.raises(KnxAgentError):
            client.reimport_system_definition(session_label="ghost")
    records = _error_records(caplog)
    assert len(records) == 1 and "SESSION_NOT_FOUND" in records[0].getMessage()
    assert records[0].name.startswith("knx_agent.")


def test_success_logs_no_error(caplog, client, project):
    with caplog.at_level(logging.DEBUG, logger="knx_agent"):
        client.create_session(project_path=project, session_label="s1")
        client.describe_session(session_label="s1")
    assert _error_records(caplog) == []


def test_unexpected_failure_is_logged_and_written(monkeypatch, caplog, client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    apply_change(project, "both")
    monkeypatch.setattr("knx_agent.application.session_paths.os.replace", lambda *a, **k: (_ for _ in ()).throw(OSError("x")))
    with caplog.at_level(logging.INFO, logger="knx_agent"):
        with pytest.raises(OSError):
            client.describe_session(session_label="s1")
    assert len(_error_records(caplog)) == 1
    assert read_log_book(session_root, "s1")[-1]["level"] == "ERROR"


def test_no_handler_configured_by_library():
    assert not [h for h in logging.getLogger("knx_agent").handlers if not isinstance(h, logging.NullHandler)]


# --- story 04: real import, fingerprint, graph file, changes, warnings ------------------------------------
COMPONENTS = "areas.0.lines.0.components"
GA_LIST = "group_ranges.0.ranges.0.addresses"
NEW_COMPONENT = {
    "address": 4,
    "name": "New",
    "product": "M-0001_H-2_P-S2",
    "hardware2program": "M-0001_H-2_HP-0002-01-BBBB",
    "objects": [{"ref": "O-0_R-1", "links": ["GA-2"]}],
    "parameters": [],
}
LINK_EDIT = [{"path": f"{COMPONENTS}.0.objects.0.links", "value": ["GA-999"]}]


def graph_bytes(session_root: Path, label: str) -> bytes:
    return (session_root / label / "project-graph.json").read_bytes()


def state_data(session_root: Path, label: str) -> dict:
    return yaml.safe_load(state_bytes(session_root, label))


def test_create_persists_graph_with_the_fingerprint(client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    graph = json.loads(graph_bytes(session_root, "s1"))
    assert graph["fingerprint"] == hashlib.sha256(project.read_bytes()).hexdigest()
    assert graph["graph_schema_version"] == 1
    assert {"source_facts", "derived_facts", "warnings"} <= set(graph)
    assert len([n for n in graph["source_facts"]["nodes"] if n["kind"] == "component"]) == 3


def test_describe_returns_project_import_from_state_only(client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    described = client.describe_session(session_label="s1")
    imported = described.project_import
    assert imported.graph_file == str(session_root.resolve() / "s1" / "project-graph.json")
    assert imported.fingerprint == hashlib.sha256(project.read_bytes()).hexdigest()
    assert imported.imported_at and imported.project_import_summary.node_counts["group_address"] == 3


def test_describe_does_not_read_the_graph(monkeypatch, client, project):
    client.create_session(project_path=project, session_label="s1")

    def boom(*_a, **_k):
        raise AssertionError("describe_session must not read the graph")

    monkeypatch.setattr("knx_agent.application.project_refresh_guard.read_graph", boom)
    client.describe_session(session_label="s1")  # unchanged check: hash only


def test_content_change_with_same_mtime_and_size_is_detected(client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    before = state_data(session_root, "s1")["project_import"]
    apply_change(project, "content_same_mtime_and_size")
    after_stat = project.stat()
    assert (after_stat.st_mtime_ns, after_stat.st_size) == (before["mtime"], before["size"])
    described = client.describe_session(session_label="s1")
    assert described.project_refresh.last_status == "CHANGED" and described.project_refresh.reimport_count == 1
    after = state_data(session_root, "s1")["project_import"]
    assert after["fingerprint"] != before["fingerprint"]
    assert after["fingerprint"] == hashlib.sha256(project.read_bytes()).hexdigest()


def test_unchanged_check_is_byte_identical_for_state_and_graph(client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    state, graph = state_bytes(session_root, "s1"), graph_bytes(session_root, "s1")
    for _ in range(2):
        client.describe_session(session_label="s1")
    assert (state_bytes(session_root, "s1"), graph_bytes(session_root, "s1")) == (state, graph)


def test_deleted_graph_file_is_restored_by_the_next_check(client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    graph = graph_bytes(session_root, "s1")
    (session_root / "s1" / "project-graph.json").unlink()
    described = client.describe_session(session_label="s1")
    assert described.project_refresh.last_status == "CHANGED" and described.project_refresh.reimport_count == 1
    assert graph_bytes(session_root, "s1") == graph  # byte-identical re-import
    again = client.describe_session(session_label="s1")
    assert again.project_refresh.reimport_count == 1


def test_stored_null_fingerprint_counts_as_changed(client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    data = state_data(session_root, "s1")
    data["project_import"]["fingerprint"] = None
    (session_root / "s1" / "session-state.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    described = client.describe_session(session_label="s1")
    assert described.project_refresh.last_status == "CHANGED"
    assert state_data(session_root, "s1")["project_import"]["fingerprint"] == hashlib.sha256(project.read_bytes()).hexdigest()


def test_reimport_of_unchanged_project_is_unchanged_with_empty_results(client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    graph = graph_bytes(session_root, "s1")
    response = client.reimport_system_definition(session_label="s1")
    assert response.project_refresh_status == "UNCHANGED"
    assert response.changes == [] and response.invalidated_references == []
    assert graph_bytes(session_root, "s1") == graph


def _change_view(response):
    return [(c.entity, c.change, c.id, c.label) for c in response.changes]


def test_reimport_reports_added_component(client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    rebuild_project(project, edits=[{"path": COMPONENTS, "append": NEW_COMPONENT}])
    response = client.reimport_system_definition(session_label="s1")
    assert response.project_refresh_status == "CHANGED"
    assert _change_view(response) == [("component", "added", "P-0001-0_DI-4", "New (1.1.4)")]
    assert response.project_import_summary.node_counts["component"] == 4
    assert response.invalidated_references == []


def test_reimport_reports_removed_and_changed_component(client, project):
    client.create_session(project_path=project, session_label="s1")
    rebuild_project(
        project,
        edits=[{"path": f"{COMPONENTS}.2", "delete": True}, {"path": f"{COMPONENTS}.0.name", "value": "Renamed"}],
    )
    response = client.reimport_system_definition(session_label="s1")
    assert _change_view(response) == [
        ("component", "changed", "P-0001-0_DI-1", "Renamed (1.1.1)"),
        ("component", "removed", "P-0001-0_DI-3", "Actuator (1.1.3)"),
    ]
    changed = response.changes[0].details
    assert changed["changed_fields"] == ["name"] and changed["old"] == {"name": "Sensor"}


def test_reimport_reports_group_address_changes_and_unresolved_link(client, project):
    client.create_session(project_path=project, session_label="s1")
    rebuild_project(
        project,
        edits=[
            {"path": f"{GA_LIST}.2", "delete": True},
            {"path": GA_LIST, "append": {"id": "GA-4", "address": 4, "name": "Added"}},
        ],
    )
    response = client.reimport_system_definition(session_label="s1")
    view = _change_view(response)
    assert ("component", "changed", "P-0001-0_DI-2", "Controller (1.1.2)") in view
    assert ("group_address", "added", "P-0001-0_GA-4", "0/0/4 Added") in view
    assert ("group_address", "removed", "P-0001-0_GA-3", "0/0/3 Status") in view
    assert "group_addresses" in response.changes[0].details["changed_fields"]
    assert any(note.startswith("[GROUP_ADDRESS_LINK_UNRESOLVED]") for note in response.envelope.limitation_notes)


def test_invalidated_references_from_injected_state(client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    data = state_data(session_root, "s1")
    data["scenario_state"] = [{"note": "ignored"}, {"component_id": "P-0001-0_DI-3"}]
    data["mutations"] = [{"name": "m1", "group_address_id": "P-0001-0_GA-3"}, {"name": "m2", "component_id": "P-0001-0_DI-1"}]
    (session_root / "s1" / "session-state.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    rebuild_project(project, edits=[{"path": f"{COMPONENTS}.2", "delete": True}, {"path": f"{GA_LIST}.2", "delete": True}])
    response = client.reimport_system_definition(session_label="s1")
    found = [(r.reference_kind, r.owner, r.component_id, r.group_address_id, r.reason) for r in response.invalidated_references]
    assert found == [
        ("scenario_state", "1", "P-0001-0_DI-3", None, "COMPONENT_REMOVED"),
        ("mutation_delta", "m1", None, "P-0001-0_GA-3", "GROUP_ADDRESS_REMOVED"),
    ]
    notes = response.envelope.limitation_notes
    assert sum(note.startswith("Invalidated reference") for note in notes) == 2
    after = state_data(session_root, "s1")
    assert after["scenario_state"] == data["scenario_state"] and after["mutations"] == data["mutations"]  # retained
    entry = [e for e in read_log_book(session_root, "s1") if e["capability"] == "reimport_system_definition"][-1]
    assert entry["details"]["invalidated_references"] == 2
    assert entry["details"]["changes"]["component_removed"] == 1 and entry["details"]["changes"]["group_address_removed"] == 1


def test_automatic_reimport_logs_change_counts(client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    rebuild_project(project, edits=[{"path": COMPONENTS, "append": NEW_COMPONENT}])
    client.describe_session(session_label="s1")
    entry = read_log_book(session_root, "s1")[-1]
    assert entry["level"] == "INFO" and entry["capability"] == "describe_session"
    assert entry["details"]["changes"] == {"component_added": 1}
    assert entry["details"]["old_fingerprint"] != entry["details"]["new_fingerprint"]
    assert entry["details"]["warning_total"] == 0 and "duration_s" in entry["details"]


def test_warnings_become_limitation_notes_and_are_counted(caplog, build, session_root):
    client = KnxSessionClient(session_root=session_root, log_level="DEBUG")
    project = build(edits=LINK_EDIT)
    with caplog.at_level(logging.DEBUG, logger="knx_agent"):
        created = client.create_session(project_path=project, session_label="s1")
        described = client.describe_session(session_label="s1")
    for response in (created, described):
        (note,) = response.envelope.limitation_notes
        assert note.startswith("[GROUP_ADDRESS_LINK_UNRESOLVED] ")
        assert note.endswith("(P-0001/0.xml#P-0001-0_DI-1/co/O-0_R-1)")
    assert created.project_import_summary.warning_total == 1
    assert created.project_import_summary.warning_counts == {"GROUP_ADDRESS_LINK_UNRESOLVED": 1}
    persisted = state_data(session_root, "s1")["project_import"]["warnings"]
    assert [w["code"] for w in persisted] == ["GROUP_ADDRESS_LINK_UNRESOLVED"]
    # one Python WARNING record per import with warnings (create only; describe was unchanged), no ERROR anywhere
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING and r.name == "knx_agent.application"]
    assert len(warnings) == 1 and "1 warnings" in warnings[0].getMessage()
    assert _error_records(caplog) == []
    entries = read_log_book(session_root, "s1")
    assert [e["level"] for e in entries] == ["DEBUG", "DEBUG", "INFO", "DEBUG"]
    assert entries[1]["summary"] == "Import warning GROUP_ADDRESS_LINK_UNRESOLVED"
    assert "ERROR" not in {e["level"] for e in entries}
    assert entries[2]["details"]["warning_total"] == 1


def test_warnings_are_not_logged_as_debug_entries_at_info(build, session_root):
    client = KnxSessionClient(session_root=session_root)
    client.create_session(project_path=build(edits=LINK_EDIT), session_label="s1")
    assert [e["level"] for e in read_log_book(session_root, "s1")] == ["INFO"]


def test_failed_reimport_keeps_previous_state_and_graph(caplog, client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    state, graph = state_bytes(session_root, "s1"), graph_bytes(session_root, "s1")
    rebuild_project(project, mutations=[{"op": "malform", "entry": "zero_xml"}])
    for call in (client.describe_session, client.reimport_system_definition):
        with caplog.at_level(logging.INFO, logger="knx_agent"):
            with pytest.raises(KnxAgentError) as excinfo:
                call(session_label="s1")
        assert code_of(excinfo) == "PROJECT_PARSE_ERROR"
        assert excinfo.value.error.details["reason"] == "REQUIRED_PART_MALFORMED"
        assert (state_bytes(session_root, "s1"), graph_bytes(session_root, "s1")) == (state, graph)
    errors = [e for e in read_log_book(session_root, "s1") if e["level"] == "ERROR"]
    assert len(errors) == 2 and errors[0]["details"]["reason"] == "REQUIRED_PART_MALFORMED"
    assert sorted(p.name for p in (session_root / "s1").iterdir()) == [
        "project-graph.json", "session-log-book.jsonl", "session-state.yaml",
    ]  # fmt: skip


def test_file_changed_during_import_writes_nothing(monkeypatch, client, project, session_root):
    client.create_session(project_path=project, session_label="s1")
    state, graph = state_bytes(session_root, "s1"), graph_bytes(session_root, "s1")
    calls = {"n": 0}
    original = importer.stat_project

    def shifting(path):
        mtime, size = original(path)
        calls["n"] += 1
        return (mtime, size) if calls["n"] == 1 else (mtime + 1, size)

    monkeypatch.setattr(importer, "stat_project", shifting)
    with pytest.raises(KnxAgentError) as excinfo:
        client.reimport_system_definition(session_label="s1")
    assert code_of(excinfo) == "PROJECT_FILE_UNREADABLE"
    assert excinfo.value.error.details["reason"] == "CHANGED_DURING_IMPORT"
    assert (state_bytes(session_root, "s1"), graph_bytes(session_root, "s1")) == (state, graph)
