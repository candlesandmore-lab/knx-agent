"""SDK-first tests: call KnxSessionClient directly, without CLI or MCP.

describe_session cases come from tests/fixtures/describe_session_cases.yaml via tests/conftest.py.
"""

import pytest

from knx_agent.contracts import DescribeSessionResponse, KnxAgentError
from knx_agent.sdk import KnxSessionClient


def test_describe_session_returns_response_model(valid_case, client, project, session_root):
    label = valid_case["session_label"]
    client.create_session(project_path=project, session_label=label)
    response = client.describe_session(session_label=label)
    assert isinstance(response, DescribeSessionResponse)
    assert response.session_label == label
    assert response.work_directory == str(session_root.resolve() / label)
    assert response.source_project_absolute_path == str(project.resolve())
    assert response.active_setup == valid_case["expected_active_setup"]
    assert response.envelope.setup == valid_case["expected_setup"]
    assert [s.kind.value for s in response.envelope.evidence_sources] == valid_case["expected_evidence_kinds"]
    assert response.envelope.limitation_notes == valid_case["expected_limitation_notes"]
    assert response.project_import.fingerprint is not None and len(response.project_import.fingerprint) == 64
    assert response.project_import.project_import_summary.node_counts["component"] == 3
    assert response.log_book_references == ["session-log-book.jsonl"]
    assert response.trace_artifacts == []
    assert [s.name for s in response.setups] == ["default"]


def test_describe_session_errors(invalid_case, client):
    with pytest.raises(KnxAgentError) as excinfo:
        client.describe_session(session_label=invalid_case["session_label"])
    assert excinfo.value.error.code == invalid_case["expected_error_code"]
    assert excinfo.value.error.message


def test_client_defaults():
    assert isinstance(KnxSessionClient(), KnxSessionClient)


# --- story 05: component inspection capabilities, SDK first -------------------------------------------
import json  # noqa: E402

from knx_agent.contracts import (  # noqa: E402
    ComponentFullView,
    ComponentMediumView,
    ComponentSummaryView,
    DescribeComponentResponse,
    DetailLevel,
    ListComponentsResponse,
    SelectorKind,
    SummarizeTopologyResponse,
    TopologySummaryBasic,
    TopologySummaryFull,
    TopologySummaryMedium,
    TraceGroupFlowResponse,
)

VIEW_CLASS = {"SUMMARY": ComponentSummaryView, "MEDIUM": ComponentMediumView, "FULL": ComponentFullView}
TOPOLOGY_CLASS = {"SUMMARY": TopologySummaryBasic, "MEDIUM": TopologySummaryMedium, "FULL": TopologySummaryFull}


@pytest.fixture
def sdk_session(client, project):
    client.create_session(project_path=project, session_label="s1")
    return "s1"


@pytest.mark.parametrize("level", ["SUMMARY", "MEDIUM", "FULL"])
def test_list_and_describe_return_the_class_of_the_level(client, sdk_session, level):
    listed = client.list_components(sdk_session, detail_level=level)
    assert isinstance(listed, ListComponentsResponse) and listed.match_count == 3
    assert all(type(match) is VIEW_CLASS[level] for match in listed.matches)
    assert listed.envelope.detail_level.value == level
    described = client.describe_component(sdk_session, "Controller", detail_level=DetailLevel(level))
    assert isinstance(described, DescribeComponentResponse)
    assert type(described.components[0]) is VIEW_CLASS[level]
    dumped = json.loads(described.model_dump_json())["components"][0]
    assert ("communication_objects" in dumped) == (level == "FULL")
    assert ("topology" in dumped) == (level != "SUMMARY")


def test_list_components_selectors_on_the_default_project(client, sdk_session):
    by_name = client.list_components(sdk_session, "SENSOR", detail_level="SUMMARY")
    assert [m.identity.individual_address for m in by_name.matches] == ["1.1.1"] and by_name.matches[0].match_kinds == ["NAME"]
    by_address = client.list_components(sdk_session, "1.1.3", selector_kind=SelectorKind.INDIVIDUAL_ADDRESS)
    assert by_address.matches[0].identity.name == "Actuator" and by_address.matches[0].identity.instance_path is None
    by_id = client.list_components(sdk_session, "P-0001-0_DI-2", selector_kind="ets_id", detail_level="summary")
    assert by_id.matches[0].identity.name == "Controller"
    by_path = client.list_components(sdk_session, "House/Ground floor/Hall/Controller")
    assert by_path.matches[0].match_kinds == ["INSTANCE_PATH"]
    ambiguous = client.list_components(sdk_session, "o")
    assert ambiguous.ambiguous and ambiguous.match_count == 3
    empty = client.list_components(sdk_session, "zzz")
    assert empty.matches == [] and empty.match_count == 0 and not empty.ambiguous
    broad = client.list_components(sdk_session)
    assert not broad.ambiguous and all("match_kinds" not in json.loads(m.model_dump_json()) for m in broad.matches)


@pytest.mark.parametrize("level", ["SUMMARY", "MEDIUM", "FULL"])
def test_summarize_topology_levels(client, sdk_session, level):
    response = client.summarize_topology(sdk_session, detail_level=level)
    assert isinstance(response, SummarizeTopologyResponse)
    assert type(response.topology_summary) is TOPOLOGY_CLASS[level]
    assert response.component_counts.total == 3 and response.component_counts.unplaced == 1
    assert response.topology_summary.counts.locations == 3


@pytest.mark.parametrize("level", ["SUMMARY", "MEDIUM", "FULL"])
def test_trace_group_flow_levels(client, sdk_session, level):
    response = client.trace_group_flow(sdk_session, group_address_selector="0/0/3", detail_level=level)
    assert isinstance(response, TraceGroupFlowResponse) and response.match_count == 1
    entry = response.group_addresses[0]
    assert [(p.component.ets_id, p.direction) for p in entry.participants] == [("P-0001-0_DI-2", "RECEIVER")]
    assert entry.current_value == "unknown"
    assert ("roles" in json.loads(entry.model_dump_json())["participants"][0]) == (level != "SUMMARY")


def test_all_four_capabilities_leave_the_session_state_untouched(client, sdk_session, session_root):
    from conftest import state_bytes

    before = state_bytes(session_root, sdk_session)
    client.list_components(sdk_session)
    client.describe_component(sdk_session, "Sensor")
    client.summarize_topology(sdk_session)
    client.trace_group_flow(sdk_session, group_address_selector="Light")
    assert state_bytes(session_root, sdk_session) == before


def test_query_errors_are_knx_agent_errors(client, sdk_session):
    with pytest.raises(KnxAgentError) as excinfo:
        client.describe_component(sdk_session, "nothing")
    assert excinfo.value.error.code == "SELECTOR_UNRESOLVED"
    with pytest.raises(KnxAgentError) as excinfo:
        client.list_components(sdk_session, mutation_name="night")
    assert excinfo.value.error.code == "MUTATION_NOT_FOUND"
    with pytest.raises(KnxAgentError) as excinfo:
        client.trace_group_flow(sdk_session)
    assert excinfo.value.error.details["reason"] == "SELECTOR_MISSING"
    with pytest.raises(KnxAgentError) as excinfo:
        client.summarize_topology("ghost")
    assert excinfo.value.error.code == "SESSION_NOT_FOUND"


def test_responses_round_trip_through_json(client, sdk_session):
    for level in ("SUMMARY", "MEDIUM", "FULL"):
        for response in (
            client.list_components(sdk_session, detail_level=level),
            client.describe_component(sdk_session, "Sensor", detail_level=level),
            client.summarize_topology(sdk_session, detail_level=level),
            client.trace_group_flow(sdk_session, group_address_selector="Light", detail_level=level),
        ):
            assert type(response).model_validate_json(response.model_dump_json()) == response
