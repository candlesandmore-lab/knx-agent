"""GraphIndex: component order, instance paths, memberships, warnings (story 05, T2)."""

from __future__ import annotations

import pytest
from conftest import fixture_cases
from graph_factory import build_graph, graphs_of

from knx_agent.domain.graph_index import GraphIndex, parse_individual_address

GRAPHS = graphs_of("graph_index_cases.yaml")


@pytest.mark.parametrize("case", fixture_cases("graph_index_cases.yaml", "cases"))
def test_graph_index_cases(case):
    index = GraphIndex.build(build_graph(GRAPHS[case["graph"]]))
    if "component_order" in case:
        assert [c.id for c in index.components] == case["component_order"]
    for component_id, paths in case.get("instance_paths", {}).items():
        assert index.instance_paths(component_id) == paths
    for component_id, names in case.get("location_path", {}).items():
        assert [s.name for s in index.location_path(component_id)] == names
    if "unplaced" in case:
        assert sorted(c.id for c in index.components if not index.is_placed(c.id)) == sorted(case["unplaced"])
    for ga_id, objects in case.get("memberships_by_group_address", {}).items():
        assert [r.communication_object_id for r in index.memberships_by_group_address.get(ga_id, [])] == objects
    for object_id, expected in case.get("warnings_by_object", {}).items():
        assert [w.code for w in index.warnings_by_object.get(object_id, [])] == expected
    for range_id, names in case.get("range_chain", {}).items():
        assert [r.name for r in index.range_chain(range_id)] == names
    for component_id, refs in case.get("parameter_order", {}).items():
        assert [p.ref_id for p in index.parameters_by_component[component_id]] == refs
    for component_id, numbers in case.get("object_order", {}).items():
        assert [o.object_number for o in index.objects_by_component[component_id]] == numbers
    if "group_address_order" in case:
        assert [g.id for g in index.group_addresses] == case["group_address_order"]
    if "style" in case:
        assert index.group_address_style == case["style"]


@pytest.mark.parametrize(
    "text, parsed",
    [("1.2.3", (1, 2, 3)), ("15.15.255", (15, 15, 255)), (None, None), ("", None), ("x.y", None), ("1.2", None), ("1.2.z", None)],
)
def test_parse_individual_address(text, parsed):
    assert parse_individual_address(text) == parsed
