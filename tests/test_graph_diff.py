"""Graph diff: re-import changes and invalidated references from compact graph descriptions (story 04, T7)."""

from __future__ import annotations

import copy

import pytest
from conftest import fixture_cases, load_fixture

from knx_agent.domain.graph_diff import diff_graphs, invalidated_references
from knx_agent.domain.project_graph import (
    CommunicationObjectNode,
    ComponentNode,
    GroupAddressNode,
    MembershipRelation,
    ParameterNode,
    ProjectGraph,
    Relations,
    SourceFacts,
)

DEFAULTS = load_fixture("reimport_change_cases.yaml")["defaults"]


def _common(node_id: str) -> dict:
    return {"id": node_id, "id_origin": "ETS_ID", "source_part": "0.xml", "source_locator": "x", "fact_origin": "PROJECT"}


def graph_from(description: dict | None) -> ProjectGraph:
    """Compact description (see reimport_change_cases.yaml) -> ProjectGraph."""
    description = description or {}
    nodes, membership = [], []
    for item in description.get("components", []):
        fields = {**DEFAULTS["component"], **{k: v for k, v in item.items() if k not in ("id", "parameters", "group_addresses")}}
        if "name" not in item and "individual_address" not in item:
            fields["name"], fields["individual_address"] = item["id"], None
        nodes.append(ComponentNode(**_common(item["id"]), **fields))
        for ref, value in item.get("parameters", {}).items():
            nodes.append(ParameterNode(**_common(f"{item['id']}/pa/{ref}"), component_id=item["id"], ref_id=ref, value=value))
        for order, ga in enumerate(item.get("group_addresses", [])):
            object_id = f"{item['id']}/co/{ga}"
            nodes.append(CommunicationObjectNode(**_common(object_id), component_id=item["id"], ref_id=ga))
            membership.append(MembershipRelation(communication_object_id=object_id, group_address_id=ga, order=order))
    for item in description.get("group_addresses", []):
        fields = {**DEFAULTS["group_address"], **{k: v for k, v in item.items() if k != "id"}}
        nodes.append(GroupAddressNode(**_common(item["id"]), **fields))
    return ProjectGraph(source_facts=SourceFacts(nodes=nodes, relations=Relations(membership=membership)))


@pytest.mark.parametrize("case", fixture_cases("reimport_change_cases.yaml", "cases"))
def test_reimport_change_cases(case):
    old, new = graph_from(case.get("old")), graph_from(case.get("new"))
    if "expected_changes" in case:
        assert diff_graphs(old, new) == case["expected_changes"]
    if "expected_invalidated" in case:
        found = invalidated_references(old, new, case.get("scenario_state", []), case.get("mutations", []))
        assert found == case["expected_invalidated"]


def test_diff_does_not_mutate_its_inputs():
    case = next(p.values[0] for p in fixture_cases("reimport_change_cases.yaml", "cases") if p.values[0]["id"] == "component-several-fields")
    old, new = graph_from(case["old"]), graph_from(case["new"])
    before = (copy.deepcopy(old), copy.deepcopy(new))
    diff_graphs(old, new)
    assert (old, new) == before


def test_diff_of_identical_graphs_is_empty_and_symmetric_for_add_remove():
    graph = graph_from({"components": [{"id": "DI-1"}], "group_addresses": [{"id": "GA-1"}]})
    empty = graph_from({})
    assert diff_graphs(graph, graph) == []
    added = diff_graphs(empty, graph)
    removed = diff_graphs(graph, empty)
    assert [(c["entity"], c["id"], c["change"]) for c in added] == [("component", "DI-1", "added"), ("group_address", "GA-1", "added")]
    assert [(c["entity"], c["id"], c["change"]) for c in removed] == [("component", "DI-1", "removed"), ("group_address", "GA-1", "removed")]


def test_only_components_and_group_addresses_are_reported():
    old = graph_from({"components": [{"id": "DI-1", "parameters": {"P": "1"}}]})
    new = graph_from({"components": [{"id": "DI-1", "parameters": {"P": "1"}}]})
    new.source_facts.nodes.append(CommunicationObjectNode(**_common("DI-1/co/x"), component_id="DI-1", ref_id="x"))
    assert diff_graphs(old, new) == []  # a new communication object without a link is not a reported entity


def test_invalidated_references_do_not_modify_scenario_state_or_mutations():
    old, new = graph_from({"components": [{"id": "DI-1"}]}), graph_from({})
    scenario, mutations = [{"component_id": "DI-1"}], [{"name": "m", "component_id": "DI-1"}]
    before = copy.deepcopy((scenario, mutations))
    assert len(invalidated_references(old, new, scenario, mutations)) == 2
    assert (scenario, mutations) == before
