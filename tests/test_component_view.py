"""Component view, detail level projections, list/describe assembly and notes (story 05, T3)."""

from __future__ import annotations

import json

import pytest
from conftest import fixture_cases
from graph_factory import graph_for_case, graphs_of
from json_subset import assert_subset, has_path

from knx_agent.contracts import DetailLevel, KnxAgentError, SelectorKind
from knx_agent.domain.component_view import (
    ComponentView,
    build_view,
    component_notes,
    describe_components,
    list_components,
)
from knx_agent.domain.graph_index import GraphIndex

DETAIL_GRAPHS = graphs_of("component_detail_level_cases.yaml")
DESCRIBE_GRAPHS = graphs_of("describe_component_cases.yaml")
LEVELS = [DetailLevel.SUMMARY, DetailLevel.MEDIUM, DetailLevel.FULL]


@pytest.mark.parametrize("case", fixture_cases("component_detail_level_cases.yaml", "cases"))
def test_detail_levels(case):
    index = GraphIndex.build(graph_for_case(DETAIL_GRAPHS, case))
    component = index.component_by_id[case["component"]]
    dumped = {}
    for level in LEVELS:
        kinds = tuple(case["match_kinds"]) if "match_kinds" in case else None
        view = build_view(index, component, level, kinds).project(level)
        data = json.loads(view.model_dump_json())
        dumped[level.value] = data
        assert set(data) == set(case["keys"][level.value]), level
        assert_subset(data, case.get(level.value, {}))
        for path in case["absent"][level.value]:
            assert not has_path(data, path), f"{level.value}: {path} must be absent"
        assert not any("purpose" in key for key in data)
    # the levels are strictly nested and distinct
    assert set(dumped["SUMMARY"]) < set(dumped["MEDIUM"]) < set(dumped["FULL"])
    for key in dumped["SUMMARY"]:
        if key != "derived":
            assert dumped["SUMMARY"][key] == dumped["MEDIUM"][key] == dumped["FULL"][key]
    assert set(dumped["SUMMARY"]["derived"]) < set(dumped["FULL"]["derived"])


def test_projection_is_a_function_of_the_internal_view_only():
    case = {"graph": "detail"}
    index = GraphIndex.build(graph_for_case(DETAIL_GRAPHS, case))
    component = index.component_by_id["P-1-0_DI-1"]
    full = build_view(index, component, DetailLevel.FULL)
    assert isinstance(full, ComponentView)
    # projecting a FULL internal view to a lower level gives the same JSON as building that level directly
    for level in (DetailLevel.SUMMARY, DetailLevel.MEDIUM):
        assert full.project(level).model_dump_json() == build_view(index, component, level).project(level).model_dump_json()


@pytest.mark.parametrize("case", fixture_cases("describe_component_cases.yaml", "cases"))
def test_list_and_describe_cases(case):
    index = GraphIndex.build(graph_for_case(DESCRIBE_GRAPHS, case))
    operation = list_components if case["op"] == "list" else describe_components
    kind = SelectorKind(case["kind"]) if "kind" in case else None
    level = DetailLevel(case.get("level", "MEDIUM"))
    expect = case["expect"]
    if "error" in expect:
        with pytest.raises(KnxAgentError) as excinfo:
            operation(index, case.get("selector"), kind, level)
        info = excinfo.value.error
        assert info.code == expect["error"]["code"]
        if "reason" in expect["error"]:
            assert info.details["reason"] == expect["error"]["reason"]
        if "details" in expect["error"]:
            assert_subset(info.details, expect["error"]["details"])
        return
    result = operation(index, case.get("selector"), kind, level)
    assert [view.identity.ets_id for view in result.views] == expect["ids"]
    assert result.match_count == expect["match_count"] == len(result.views)
    assert result.ambiguous is expect["ambiguous"]
    for view in result.views:
        dumped = json.loads(view.model_dump_json())
        if expect.get("no_match_kinds") or case.get("selector") is None:
            assert "match_kinds" not in dumped
        elif "match_kinds" in expect:
            assert dumped["match_kinds"] == expect["match_kinds"][view.identity.ets_id]
        else:
            assert "match_kinds" in dumped


@pytest.mark.parametrize("case", fixture_cases("component_detail_level_cases.yaml", "notes_cases"))
def test_limitation_notes(case):
    index = GraphIndex.build(graph_for_case(DETAIL_GRAPHS, case))
    level = DetailLevel(case["level"])
    result = list_components(index, case.get("selector"), None, level)
    assert result.limitation_notes == case["notes"]
    assert component_notes(index, [index.component_by_id[v.identity.ets_id] for v in result.views], level) == case["notes"]


def test_levels_build_only_what_they_need():
    index = GraphIndex.build(graph_for_case(DETAIL_GRAPHS, {"graph": "detail"}))
    component = index.component_by_id["P-1-0_DI-1"]
    summary = build_view(index, component, DetailLevel.SUMMARY)
    assert summary.topology is None and summary.communication_objects == [] and summary.product is None
    medium = build_view(index, component, DetailLevel.MEDIUM)
    assert medium.topology is not None and medium.communication_objects == [] and medium.application is None
