"""Topology summary per level (story 05, T4); cases in tests/fixtures/topology_summary_cases.yaml."""

from __future__ import annotations

import json

import pytest
from conftest import fixture_cases
from graph_factory import graph_for_case, graphs_of
from json_subset import assert_subset

from knx_agent.contracts import DetailLevel
from knx_agent.domain.graph_index import GraphIndex
from knx_agent.domain.topology_summary import summarize

GRAPHS = graphs_of("topology_summary_cases.yaml")
LEVELS = [DetailLevel.SUMMARY, DetailLevel.MEDIUM, DetailLevel.FULL]


@pytest.mark.parametrize("case", fixture_cases("topology_summary_cases.yaml", "cases"))
def test_topology_cases(case):
    index = GraphIndex.build(graph_for_case(GRAPHS, case))
    dumped = {}
    for level in LEVELS:
        result = summarize(index, level)
        data = json.loads(result.topology_summary.model_dump_json())
        dumped[level.value] = data
        assert set(data) == set(case["keys"][level.value]), level
        assert_subset(data, case[level.value])
        assert result.component_counts.model_dump() == case["component_counts"]
        assert result.limitation_notes == case["notes"]
        assert not any("purpose" in key for key in data)
    assert set(dumped["SUMMARY"]) < set(dumped["MEDIUM"]) < set(dumped["FULL"])


@pytest.mark.parametrize("case", fixture_cases("topology_summary_cases.yaml", "cases"))
def test_counts_add_up(case):
    index = GraphIndex.build(graph_for_case(GRAPHS, case))
    medium = summarize(index, DetailLevel.MEDIUM)
    counts = medium.component_counts
    topology = medium.topology_summary
    assert counts.placed + counts.unplaced == counts.total
    assert sum(counts.by_component_type.values()) == counts.total
    line_sum = sum(line.component_count for area in topology.areas for line in area.lines)
    assert line_sum + topology.unassigned_to_line == counts.total
    assert sum(area.component_count for area in topology.areas) == line_sum
    assert topology.unplaced_component_count == counts.unplaced
    # no component is placed twice in these fixtures except the dedicated multi-placement case
    if case["id"] != "component_in_two_locations_is_counted_in_each_and_once_in_totals":
        direct = sum(location.component_count for location in topology.locations)
        assert direct + counts.unplaced == counts.total
    assert topology.counts.locations == len(topology.locations)
    assert topology.counts.areas == len(topology.areas)
    assert topology.counts.lines == sum(len(area.lines) for area in topology.areas)
    for location in topology.locations:
        assert location.component_count_total >= location.component_count


@pytest.mark.parametrize("case", fixture_cases("topology_summary_cases.yaml", "cases"))
def test_full_lists_every_component_once_under_its_line_or_unassigned(case):
    index = GraphIndex.build(graph_for_case(GRAPHS, case))
    full = summarize(index, DetailLevel.FULL).topology_summary
    listed = [c.ets_id for area in full.areas for line in area.lines for c in line.components]
    listed += [c.ets_id for c in full.unassigned_components]
    assert sorted(listed) == sorted(c.id for c in index.components)
    assert len(listed) == len(set(listed))


def test_summarize_does_not_mutate_the_graph():
    graph = graph_for_case(GRAPHS, {"graph": "nested"})
    before = graph.model_dump_json()
    for level in LEVELS:
        summarize(GraphIndex.build(graph), level)
    assert graph.model_dump_json() == before
