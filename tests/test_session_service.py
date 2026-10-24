"""Session service tests, SDK-first: create, describe, reimport, refresh guard, log book, ERROR logging."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import pytest
import yaml
from conftest import apply_change, fixture_cases, read_log_book, state_bytes

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
    assert response.project_import_summary.file_name == "house.knxproj"
    assert response.project_import_summary.archive_entry_count == 2
    assert "not implemented" in response.project_import_summary.limitation_note
    assert response.envelope.evidence_sources[0].kind.value == "KNXPROJ"
    assert response.envelope.log_book_entry_id == 1
    assert sorted(p.name for p in work.iterdir()) == ["session-log-book.jsonl", "session-state.yaml"]


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
    assert imported["fingerprint"] is None
    assert imported["project_import_summary"]["file_name"] == "house.knxproj"
    assert imported["project_import_summary"]["archive_entry_count"] == 2
    assert imported["project_import_summary"]["limitation_note"] == ".knxproj content import is not implemented yet"
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
    apply_change(project, "both")

    def boom(*_a, **_k):
        raise OSError("replace failed")

    monkeypatch.setattr("knx_agent.application.session_paths.os.replace", boom)
    with pytest.raises(OSError):
        client.describe_session(session_label="s1")
    assert state_bytes(session_root, "s1") == before
    assert sorted(p.name for p in (session_root / "s1").iterdir()) == ["session-log-book.jsonl", "session-state.yaml"]


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
    assert [e["level"] for e in read_log_book(session_root, "s1")] == ["INFO", "DEBUG"]
    debug_client.describe_session(session_label="s1", log_level="INFO")  # per-call override
    assert len(read_log_book(session_root, "s1")) == 2


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
