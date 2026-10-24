"""QueryService on synthetic archives (story 05, T6): refresh check, read-only logging, errors, envelope."""

from __future__ import annotations

import json
import logging

import pytest
from conftest import apply_change, fixture_cases, load_fixture, read_log_book, rebuild_project, state_bytes
from json_subset import assert_subset

from knx_agent.application import QueryService
from knx_agent.contracts import KnxAgentError
from knx_agent.sdk import KnxSessionClient

LOG_CASES = load_fixture("query_log_cases.yaml")
LABEL = "s1"


@pytest.fixture
def service(session_root) -> QueryService:
    return QueryService(session_root=session_root)


@pytest.fixture
def session(client: KnxSessionClient, project, session_root):
    client.create_session(project_path=project, session_label=LABEL)
    return LABEL


def call(service: QueryService, session: str, case: dict, **extra):
    args = {**case.get("args", {}), **extra}
    return getattr(service, case["method"])(session_label=session, **args)


def entries(session_root, label=LABEL):
    return read_log_book(session_root, label)


# -- envelope ---------------------------------------------------------------------------------------------
def test_envelope_content_and_detail_level_echo(service, session, project):
    response = service.list_components(session, detail_level="full")
    envelope = response.envelope
    assert envelope.setup == "default"
    assert [(s.kind.value, s.reference) for s in envelope.evidence_sources] == [("KNXPROJ", str(project.resolve()))]
    assert envelope.detail_level.value == "FULL"
    assert envelope.log_book_entry_id is None  # unchanged check at INFO writes nothing
    assert envelope.limitation_notes[0].startswith("Component type is a derived fact")
    assert service.list_components(session).envelope.detail_level.value == "MEDIUM"  # default
    assert service.summarize_topology(session, detail_level="summary").envelope.detail_level.value == "SUMMARY"


def test_envelope_notes_are_query_notes_not_import_warnings(service, session_root, client, build):
    project = build(edits=[{"path": "areas.0.lines.0.components.0.objects.0.links", "value": ["GA-999"]}])
    client.create_session(project_path=project, session_label="warned")
    notes = service.summarize_topology("warned").envelope.limitation_notes
    assert not any(note.startswith("[") for note in notes)  # import warnings stay in describe_session


def test_log_book_entry_id_is_the_refresh_entry_at_debug(service, session, session_root):
    response = service.describe_component(session, "Sensor", log_level="DEBUG")
    written = entries(session_root)[-1]
    assert response.envelope.log_book_entry_id == written["entry_id"]
    assert written["level"] == "DEBUG" and written["capability"] == "describe_component"
    assert written["summary"] == "Project refresh check: unchanged"


def test_results_are_identical_for_two_consecutive_calls(service, session):
    for method, kwargs in (
        ("list_components", {}),
        ("describe_component", {"component_selector": "Controller", "detail_level": "FULL"}),
        ("summarize_topology", {"detail_level": "FULL"}),
        ("trace_group_flow", {"group_address_selector": "0/0/1", "detail_level": "FULL"}),
    ):
        first = getattr(service, method)(session, **kwargs).model_dump_json()
        second = getattr(service, method)(session, **kwargs).model_dump_json()
        assert first == second


def test_default_project_shapes(service, session):
    listed = service.list_components(session, detail_level="SUMMARY")
    assert listed.match_count == 3 and listed.ambiguous is False
    assert [m.identity.individual_address for m in listed.matches] == ["1.1.1", "1.1.2", "1.1.3"]
    paths = [m.identity.instance_path for m in listed.matches]
    assert paths == ["House/Ground floor/Hall/Sensor", "House/Ground floor/Hall/Controller", None]
    assert any("not placed in a location" in note for note in listed.envelope.limitation_notes)
    flow = service.trace_group_flow(session, group_address_selector="0/0/1", detail_level="MEDIUM")
    entry = flow.group_addresses[0]
    assert [(p.component.ets_id, p.direction) for p in entry.participants] == [
        ("P-0001-0_DI-1", "SENDER"), ("P-0001-0_DI-2", "RECEIVER"),
    ]  # fmt: skip
    assert entry.current_value == "unknown"


# -- logging: read-only ---------------------------------------------------------------------------------
@pytest.mark.parametrize("level", ["INFO", "DEBUG", "FULL"])
@pytest.mark.parametrize("case", fixture_cases("query_log_cases.yaml", "calls"))
def test_successful_queries_write_only_the_refresh_entry(service, session, session_root, case, level):
    before = entries(session_root)
    call(service, session, case, log_level=level)
    new = entries(session_root)[len(before):]
    assert len(new) == LOG_CASES["unchanged_entries"][level]
    for entry in new:  # nothing of the capability itself: the only entry is the refresh check
        assert entry["level"] == "DEBUG" and entry["summary"] == "Project refresh check: unchanged"
        assert entry["capability"] == case["method"]


@pytest.mark.parametrize("case", fixture_cases("query_log_cases.yaml", "calls"))
def test_session_state_is_byte_identical_after_queries_on_an_unchanged_project(service, session, session_root, case):
    before = state_bytes(session_root, LABEL)
    call(service, session, case)
    call(service, session, case, log_level="DEBUG")
    assert state_bytes(session_root, LABEL) == before


# -- refresh check ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("case", fixture_cases("query_log_cases.yaml", "calls"))
def test_changed_project_is_reimported_before_the_query(service, session, session_root, project, case):
    apply_change(project, "both")
    before = entries(session_root)
    response = call(service, session, case)
    new = entries(session_root)[len(before):]
    assert [(e["level"], e["capability"], e["summary"]) for e in new] == [
        ("INFO", case["method"], "Project refresh check: changed, automatic re-import done")
    ]
    assert response.envelope.log_book_entry_id == new[0]["entry_id"]
    assert new[0]["details"]["status"] == "CHANGED"


def test_result_reflects_the_reimported_project(service, session, project):
    assert service.list_components(session, "Renamed").match_count == 0
    rebuild_project(project, edits=[{"path": "areas.0.lines.0.components.0.name", "value": "Renamed"}])
    response = service.list_components(session, "Renamed", detail_level="SUMMARY")
    assert [m.identity.name for m in response.matches] == ["Renamed"]
    assert service.list_components(session, "Sensor").match_count == 0


def test_reimport_debug_entries_carry_the_calling_capability(service, session, session_root, project):
    apply_change(project, "both")
    service.trace_group_flow(session, group_address_selector="0/0/1", log_level="DEBUG")
    new = entries(session_root)[1:]
    assert [e["capability"] for e in new] == ["trace_group_flow"] * len(new)
    assert [e["summary"] for e in new] == ["Import started", "Project refresh check: changed, automatic re-import done"]


def test_refresh_runs_before_request_validation(service, session, session_root, project):
    apply_change(project, "both")
    with pytest.raises(KnxAgentError) as excinfo:
        service.describe_component(session, "Sensor", detail_level="HUGE")
    assert excinfo.value.error.code == "INVALID_DETAIL_LEVEL"
    log = entries(session_root)
    assert [e["level"] for e in log[1:]] == ["INFO", "ERROR"]  # re-import happened, then the rejected request
    assert "changed, automatic re-import done" in log[1]["summary"]


def test_deleted_project_is_an_error_entry(service, session, session_root, project):
    project.unlink()
    with pytest.raises(KnxAgentError) as excinfo:
        service.list_components(session)
    assert excinfo.value.error.code == "PROJECT_FILE_UNREADABLE"
    last = entries(session_root)[-1]
    assert last["level"] == "ERROR" and last["capability"] == "list_components"
    assert last["details"]["code"] == "PROJECT_FILE_UNREADABLE"
    assert [e["level"] for e in entries(session_root)] == ["INFO", "ERROR"]


def test_unreadable_project_after_change_keeps_graph_and_state(service, session, session_root, project):
    before = state_bytes(session_root, LABEL)
    apply_change(project, "not_zip")
    with pytest.raises(KnxAgentError) as excinfo:
        service.summarize_topology(session)
    assert excinfo.value.error.code == "PROJECT_PARSE_ERROR"
    assert state_bytes(session_root, LABEL) == before
    assert entries(session_root)[-1]["level"] == "ERROR"


# -- errors ---------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("case", fixture_cases("query_error_cases.yaml", "cases"))
def test_failures_are_one_error_entry(service, session, session_root, case, caplog):
    before = entries(session_root)
    with caplog.at_level(logging.ERROR):
        with pytest.raises(KnxAgentError) as excinfo:
            call(service, session, case)
    info = excinfo.value.error
    assert info.code == case["code"]
    if "reason" in case:
        assert info.details["reason"] == case["reason"]
    if "details" in case:
        assert_subset(info.details, case["details"])
    new = entries(session_root)[len(before):]
    if case.get("no_log_book_entry"):
        assert new == []
    else:
        assert len(new) == 1  # INFO level: the unchanged refresh check is a DEBUG entry and is filtered
        assert new[0]["level"] == "ERROR" and new[0]["capability"] == case["method"]
        assert new[0]["details"]["code"] == case["code"]
        assert new[0]["details"].get("reason") == case.get("reason")
    records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(records) == 1 and case["code"] in records[0].getMessage() and case["method"] in records[0].getMessage()


@pytest.mark.parametrize("level", ["DEBUG", "FULL"])
def test_failure_after_a_debug_refresh_entry_still_writes_exactly_one_error(service, session, session_root, level):
    before = entries(session_root)
    with pytest.raises(KnxAgentError):
        service.describe_component(session, "Nothing", log_level=level)
    new = entries(session_root)[len(before):]
    assert [e["level"] for e in new] == ["DEBUG", "ERROR"]


def test_error_is_written_whatever_the_log_level(service, session, session_root):
    with pytest.raises(KnxAgentError):
        service.list_components(session, detail_level="x", log_level="INFO")
    assert entries(session_root)[-1]["level"] == "ERROR"


@pytest.mark.parametrize("name", [None, "", "default"])
def test_mutation_name_default_targets_the_default_setup(service, session, name):
    for method, kwargs in (
        ("list_components", {}),
        ("describe_component", {"component_selector": "Sensor"}),
        ("summarize_topology", {}),
        ("trace_group_flow", {"group_address_selector": "0/0/1"}),
    ):
        assert getattr(service, method)(session, mutation_name=name, **kwargs).envelope.setup == "default"


def test_unknown_session_is_session_not_found_without_log_book(service, session_root, caplog):
    with caplog.at_level(logging.ERROR):
        with pytest.raises(KnxAgentError) as excinfo:
            service.list_components("ghost")
    assert excinfo.value.error.code == "SESSION_NOT_FOUND"
    assert not (session_root / "ghost").exists()
    assert any("SESSION_NOT_FOUND" in r.getMessage() for r in caplog.records)


def test_invalid_session_label_is_reported(service):
    with pytest.raises(KnxAgentError) as excinfo:
        service.summarize_topology("not a label!")
    assert excinfo.value.error.code in {"SESSION_LABEL_INVALID", "SESSION_NOT_FOUND"}


# -- corrupt graph -----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("content", ["not json at all", "{}", '{"graph_schema_version": 1, "source_facts": 5}', ""])
def test_corrupt_graph_file_is_graph_file_invalid_without_hidden_reimport(service, session, session_root, content):
    graph_file = session_root / LABEL / "project-graph.json"
    graph_file.write_text(content, encoding="utf-8")
    if content == "{}":  # an empty object validates (all fields default): the graph is simply empty
        assert service.list_components(session).match_count == 0
        return
    before = entries(session_root)
    with pytest.raises(KnxAgentError) as excinfo:
        service.list_components(session)
    info = excinfo.value.error
    assert info.code == "PROJECT_PARSE_ERROR" and info.details["reason"] == "GRAPH_FILE_INVALID"
    assert info.details["path"].endswith("project-graph.json") and "reimport_system_definition" in info.message
    assert graph_file.read_text(encoding="utf-8") == content  # not repaired behind the caller's back
    new = entries(session_root)[len(before):]
    assert [e["level"] for e in new] == ["ERROR"] and new[0]["details"]["reason"] == "GRAPH_FILE_INVALID"
    # the explicit capability repairs it
    KnxSessionClient(session_root=session_root).reimport_system_definition(session)
    assert service.list_components(session).match_count == 3


def test_missing_graph_file_counts_as_changed_and_is_reimported(service, session, session_root):
    (session_root / LABEL / "project-graph.json").unlink()
    response = service.list_components(session)
    assert response.match_count == 3
    assert (session_root / LABEL / "project-graph.json").exists()
    assert json.loads(json.dumps(entries(session_root)[-1]))["summary"].startswith("Project refresh check: changed")
