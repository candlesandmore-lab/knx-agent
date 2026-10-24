"""Selector parsing and matching on factory graphs (story 05, T2). Cases live in tests/fixtures/*.yaml."""

from __future__ import annotations

import pytest
from conftest import fixture_cases, load_fixture
from graph_factory import build_graph, graph_for_case, graphs_of

from knx_agent.contracts import KnxAgentError, SelectorKind
from knx_agent.domain.graph_index import GraphIndex
from knx_agent.domain.selectors import (
    evaluated_kinds,
    individual_address_syntax,
    ets_id_syntax,
    match_components,
    parse_communication_object_ref,
    parse_group_address_selector,
    strip_selector,
)

SELECTOR_GRAPHS = graphs_of("selector_cases.yaml")
OVERLAP_GRAPHS = graphs_of("selector_overlap_cases.yaml")


def _run(index: GraphIndex, case: dict):
    kind = SelectorKind(case.get("kind", "ANY"))
    value = strip_selector(case["selector"])
    return value, kind, match_components(index, value, kind)


def _check(graphs: dict, case: dict) -> None:
    index = GraphIndex.build(graph_for_case(graphs, case))
    if "error" in case:
        with pytest.raises(KnxAgentError) as excinfo:
            _run(index, case)
        assert excinfo.value.error.code == case["error"]["code"]
        assert excinfo.value.error.details["reason"] == case["error"]["reason"]
        return
    value, kind, matches = _run(index, case)
    assert [(m.component.id, list(m.match_kinds)) for m in matches] == [
        (item["id"], item["kinds"]) for item in case["expect"]
    ]
    assert len({m.component.id for m in matches}) == len(matches)  # de-duplicated
    for match in matches:
        assert list(match.match_kinds) == sorted(set(match.match_kinds))  # sorted, no duplicates
        if kind is not SelectorKind.ANY:
            assert match.match_kinds == (kind.value,)  # explicit kinds never overlap
    if "match_count" in case:
        assert len(matches) == case["match_count"]
    if "evaluated" in case:
        assert evaluated_kinds(value, kind) == case["evaluated"]


@pytest.mark.parametrize("case", fixture_cases("selector_cases.yaml", "cases"))
def test_selector_cases(case):
    _check(SELECTOR_GRAPHS, case)


@pytest.mark.parametrize("case", fixture_cases("selector_overlap_cases.yaml", "cases"))
def test_any_overlap_cases(case):
    _check(OVERLAP_GRAPHS, case)


@pytest.mark.parametrize("value", load_fixture("selector_overlap_cases.yaml")["exclusive_values"])
def test_individual_address_and_ets_id_syntax_never_both_fit(value):
    assert not (individual_address_syntax(value) is not None and ets_id_syntax(value))
    kinds = evaluated_kinds(value, SelectorKind.ANY)
    assert "NAME" in kinds
    assert not {"INDIVIDUAL_ADDRESS", "ETS_ID"} <= set(kinds)
    assert ("INSTANCE_PATH" in kinds) == ("/" in value)
    if "/" in value:
        assert not {"INDIVIDUAL_ADDRESS", "ETS_ID"} & set(kinds)


def test_graph_index_build_does_not_mutate_the_graph():
    graph = graph_for_case(SELECTOR_GRAPHS, {"graph": "base"})
    before = graph.model_dump_json()
    GraphIndex.build(graph)
    assert graph.model_dump_json() == before


@pytest.mark.parametrize("case", fixture_cases("group_address_selector_cases.yaml", "address_cases"))
def test_group_address_selector_parsing(case):
    if "error" in case:
        with pytest.raises(KnxAgentError) as excinfo:
            parse_group_address_selector(case["value"], case["style"])
        assert excinfo.value.error.code == case["error"]["code"]
        assert excinfo.value.error.details["reason"] == case["error"]["reason"]
        return
    query = parse_group_address_selector(case["value"], case["style"])
    if "address_raw" in case:
        assert query.address_raw == case["address_raw"] and query.name_needle is None
    else:
        assert query.address_raw is None and query.name_needle == case["name"]


@pytest.mark.parametrize("case", fixture_cases("group_address_selector_cases.yaml", "object_ref_cases"))
def test_communication_object_ref_parsing(case):
    if "error" in case:
        with pytest.raises(KnxAgentError) as excinfo:
            parse_communication_object_ref(case["value"])
        assert excinfo.value.error.code == case["error"]["code"]
        assert excinfo.value.error.details["reason"] == case["error"]["reason"]
    else:
        assert parse_communication_object_ref(case["value"]) == case["expected"]


def test_factory_builds_the_documented_base_graph():
    index = GraphIndex.build(build_graph(SELECTOR_GRAPHS["base"]))
    assert [c.individual_address for c in index.components] == ["1.1.1", "1.1.2", "1.1.5", "1.1.6", "1.2.1"]
    assert index.instance_paths("P-1-0_DI-1") == ["House/EG/Living room/Wall Switch"]
    assert index.instance_paths("P-1-0_DI-5") == []
