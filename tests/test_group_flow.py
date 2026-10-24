"""trace_group_flow in the domain (story 05, T5); cases in tests/fixtures/group_flow_cases.yaml."""

from __future__ import annotations

import json

import pytest
from conftest import fixture_cases, load_fixture
from graph_factory import build_graph, graph_for_case, graphs_of
from json_subset import assert_subset, has_path

from knx_agent.contracts import DetailLevel, KnxAgentError
from knx_agent.domain.graph_index import GraphIndex
from knx_agent.domain.group_flow import direction_of, roles_of, trace

GRAPHS = graphs_of("group_flow_cases.yaml")
LEVELS = [DetailLevel.SUMMARY, DetailLevel.MEDIUM, DetailLevel.FULL]
ALWAYS_NOTES = [
    "Direction is derived from the ETS communication object flags only; the order of group address links is not used.",
    "Only direct participants are listed; line and area routing is not evaluated.",
    "current_value is unknown; no simulation exists yet.",
]


def _trace(case, level=DetailLevel.MEDIUM):
    index = GraphIndex.build(graph_for_case(GRAPHS, case))
    return trace(index, case.get("selector"), case.get("object_ref"), level)


@pytest.mark.parametrize("case", fixture_cases("group_flow_cases.yaml", "cases"))
def test_flow_cases(case):
    expect = case["expect"]
    if "error" in expect:
        with pytest.raises(KnxAgentError) as excinfo:
            _trace(case)
        info = excinfo.value.error
        assert info.code == expect["error"]["code"]
        if "reason" in expect["error"]:
            assert info.details["reason"] == expect["error"]["reason"]
        if "details" in expect["error"]:
            assert_subset(info.details, expect["error"]["details"])
        return
    result = _trace(case)
    assert result.match_count == expect["count"] == len(result.entries)
    assert result.ambiguous is expect["ambiguous"]
    assert [entry.group_address.ets_id for entry in result.entries] == expect["addresses"]
    assert result.limitation_notes == ALWAYS_NOTES + ([expect["extra_note"]] if "extra_note" in expect else [])
    for entry, expected in zip(result.entries, expect.get("entries", []), strict=False):
        assert_subset(json.loads(entry.model_dump_json()), expected)


ENTRY_CASES = [
    pytest.param(case, id=case["id"])
    for case in load_fixture("group_flow_cases.yaml")["cases"]
    if "error" not in case["expect"] and case["expect"].get("count")
]


@pytest.mark.parametrize("case", ENTRY_CASES)
def test_entries_carry_only_the_fields_of_their_level(case):
    shapes = {}
    for level in LEVELS:
        entries = [json.loads(e.model_dump_json()) for e in _trace(case, level).entries]
        shapes[level] = entries
        for entry in entries:
            assert set(entry) == {"group_address", "participants", "propagation_path", "unresolved_links", "current_value"}
            assert entry["current_value"] == "unknown"
            assert entry["propagation_path"]["scope"] == "DIRECT_PARTICIPANTS"
            assert set(entry["group_address"]) == LevelKeys.group_address[level]
            for participant in entry["participants"]:
                assert set(participant) == LevelKeys.participant[level]
                assert set(participant["component"]) == LevelKeys.component[level]
                assert not any("purpose" in key for key in participant)
                if level is not DetailLevel.SUMMARY:
                    assert set(participant["communication_object"]) == LevelKeys.object[level]
                else:
                    assert not has_path(participant, "communication_object") and not has_path(participant, "roles")
            for link in entry["unresolved_links"]:
                assert set(link) == LevelKeys.link[level]
    # directions are identical on all levels
    directions = [
        [[p["direction"] for p in entry["participants"]] for entry in shapes[level]] for level in LEVELS
    ]
    assert directions[0] == directions[1] == directions[2]


class LevelKeys:
    group_address = {
        DetailLevel.SUMMARY: {"ets_id", "address", "name"},
        DetailLevel.MEDIUM: {"ets_id", "address", "name", "datapoint_type", "description"},
        DetailLevel.FULL: {"ets_id", "address", "name", "datapoint_type", "description", "address_raw", "range_id", "range_path"},
    }
    participant = {
        DetailLevel.SUMMARY: {"component", "direction"},
        DetailLevel.MEDIUM: {"component", "communication_object", "direction", "roles"},
        DetailLevel.FULL: {"component", "communication_object", "direction", "roles", "link_order"},
    }
    component = {
        DetailLevel.SUMMARY: {"ets_id", "name", "individual_address"},
        DetailLevel.MEDIUM: {"ets_id", "name", "individual_address", "instance_path", "component_type"},
        DetailLevel.FULL: {"ets_id", "name", "individual_address", "instance_path", "component_type"},
    }
    object = {
        DetailLevel.MEDIUM: {"ets_id", "object_number", "label", "datapoint_types"},
        DetailLevel.FULL: {
            "ets_id", "object_number", "label", "datapoint_types", "function_text", "text", "instance_text",
            "description", "object_size", "flags", "definition_resolved",
        },
    }  # fmt: skip
    link = {
        DetailLevel.SUMMARY: {"code", "communication_object_id", "component_id"},
        DetailLevel.MEDIUM: {"code", "communication_object_id", "component_id", "message", "location"},
        DetailLevel.FULL: {"code", "communication_object_id", "component_id", "message", "location"},
    }


def test_full_level_adds_flags_range_path_and_link_order():
    result = trace(GraphIndex.build(build_graph(GRAPHS["flow"])), "1/0/3", None, DetailLevel.FULL)
    data = json.loads(result.entries[0].model_dump_json())
    assert data["group_address"]["range_path"] == ["Main", "Middle"]
    assert data["group_address"]["address_raw"] == 2051
    first = data["participants"][0]  # DI-1 O-1 links [G4, G3]: G3 is its second link
    assert first["link_order"] == 1
    assert first["communication_object"]["flags"] == {
        "read": "Disabled", "write": "Disabled", "communication": "Enabled",
        "transmit": "Enabled", "update": "Disabled", "read_on_init": "Disabled",
    }  # fmt: skip


@pytest.mark.parametrize("case", load_fixture("group_flow_cases.yaml")["link_order_independence"], ids=lambda c: c["id"])
def test_link_order_is_not_a_sender_rule(case):
    outcomes = {}
    for name in ("link_order_a", "link_order_b"):
        index = GraphIndex.build(build_graph(GRAPHS[name]))
        entry = trace(index, case["selector"], None, DetailLevel.FULL).entries[0]
        outcomes[name] = {p.component.ets_id: p.direction for p in entry.participants}
        assert outcomes[name] == case["expected_directions"]
        assert entry.propagation_path.senders == [k for k, v in case["expected_directions"].items() if v == "SENDER"]
    # the stored link order really differs between the two graphs (FULL shows it), the directions do not
    a = trace(GraphIndex.build(build_graph(GRAPHS["link_order_a"])), "1/0/1", None, DetailLevel.FULL).entries[0]
    b = trace(GraphIndex.build(build_graph(GRAPHS["link_order_b"])), "1/0/1", None, DetailLevel.FULL).entries[0]
    assert {p.component.ets_id: p.link_order for p in a.participants} != {p.component.ets_id: p.link_order for p in b.participants}


@pytest.mark.parametrize(
    "flags, roles, direction",
    [
        ({"transmit": "Enabled"}, ["TRANSMITS"], "SENDER"),
        ({"write": "Enabled"}, ["ACCEPTS_WRITE"], "RECEIVER"),
        ({"update": "Enabled"}, ["ACCEPTS_UPDATE"], "RECEIVER"),
        ({"transmit": "Enabled", "write": "Enabled"}, ["ACCEPTS_WRITE", "TRANSMITS"], "SENDER_RECEIVER"),
        ({"transmit": "Enabled", "update": "Enabled"}, ["ACCEPTS_UPDATE", "TRANSMITS"], "SENDER_RECEIVER"),
        ({"read": "Enabled"}, ["ANSWERS_READ"], "UNDETERMINED"),
        ({"transmit": "Enabled", "read": "Enabled"}, ["ANSWERS_READ", "TRANSMITS"], "SENDER"),
        ({"write": "Enabled", "read": "Enabled"}, ["ACCEPTS_WRITE", "ANSWERS_READ"], "RECEIVER"),
        ({"communication": "Enabled"}, [], "UNDETERMINED"),
        ({}, [], "UNDETERMINED"),
    ],
)
def test_direction_rule(flags, roles, direction):
    from knx_agent.domain.project_graph import CommunicationObjectNode

    obj = CommunicationObjectNode(
        id="x/co/y", id_origin="ETS_COMPOSITE", source_part="0.xml", source_locator="l", fact_origin="PROJECT",
        read_flag=flags.get("read"), write_flag=flags.get("write"), communication_flag=flags.get("communication"),
        transmit_flag=flags.get("transmit"), update_flag=flags.get("update"),
    )  # fmt: skip
    assert roles_of(obj) == roles
    assert direction_of(roles) == direction


def test_trace_does_not_mutate_the_graph():
    graph = build_graph(GRAPHS["flow"])
    before = graph.model_dump_json()
    for level in LEVELS:
        trace(GraphIndex.build(graph), "light", None, level)
    assert graph.model_dump_json() == before
