"""Derived facts: component typing rules CT0-CT4, indexes, counts (story 04, T7)."""

from __future__ import annotations

import copy
import inspect

import pytest
from conftest import fixture_cases, parse_archive

from knx_agent.domain import derivation
from knx_agent.domain.derivation import TypeOverride, classify_component, datapoint_main_types, derive
from knx_agent.domain.project_graph import (
    COMPONENT_TYPES,
    TYPING_RULE_IDS,
    CommunicationObjectNode,
    ComponentNode,
    MembershipRelation,
    Relations,
    SourceFacts,
)


def _common(node_id: str) -> dict:
    return {"id": node_id, "id_origin": "ETS_ID", "source_part": "0.xml", "source_locator": "x", "fact_origin": "PROJECT"}


def make_component(**fields) -> ComponentNode:
    base = {"address": 1, "medium_type_ref": "MT-0", "has_ip_config": False}
    return ComponentNode(**_common("DI-1"), **{**base, **fields})


def make_objects(spec: dict, datapoint_types: list[str] | None = None) -> list[CommunicationObjectNode]:
    """Objects from the compact fixture description (see typing_rule_cases.yaml)."""
    kinds = {
        "rx": dict(write_flag="Enabled", transmit_flag="Disabled", definition_resolved=True),
        "tx": dict(write_flag="Disabled", transmit_flag="Enabled", definition_resolved=True),
        "both": dict(write_flag="Enabled", transmit_flag="Enabled", definition_resolved=True),
        "none": dict(write_flag="Disabled", transmit_flag="Disabled", definition_resolved=True),
        "null_flags": dict(write_flag=None, transmit_flag=None, definition_resolved=True),
        "unresolved": dict(write_flag=None, transmit_flag=None, definition_resolved=False),
    }
    objects = []
    for kind, count in spec.items():
        for index in range(count):
            objects.append(
                CommunicationObjectNode(**_common(f"DI-1/co/{kind}{index}"), component_id="DI-1", ref_id=f"{kind}{index}", **kinds[kind])
            )
    if datapoint_types:
        objects.append(
            CommunicationObjectNode(
                **_common("DI-1/co/dpt"), component_id="DI-1", ref_id="dpt", definition_resolved=True, datapoint_types=datapoint_types
            )
        )
    return objects


@pytest.mark.parametrize("case", fixture_cases("typing_rule_cases.yaml", "cases"))
def test_typing_rule_cases(case):
    component = make_component(**case["component"])
    objects = make_objects(case["objects"], case.get("datapoint_types"))
    overrides = [TypeOverride(o["match"], o["value"], o["type"]) for o in case.get("overrides", [])]
    typing = classify_component(component, objects, overrides)
    expected = case["expected"]
    assert typing.component_type == expected["type"]
    assert typing.rule_id == expected["rule_id"]
    assert typing.basis.receive_object_count == expected["receive"]
    assert typing.basis.transmit_object_count == expected["transmit"]
    assert typing.basis.object_count == expected.get("object_count", len(objects))
    assert typing.basis.product_ref_id == component.product_ref_id
    assert typing.basis.application_program_id == component.application_program_id
    if "datapoint_main_types" in expected:
        assert typing.basis.datapoint_main_types == expected["datapoint_main_types"]


def test_fixture_covers_every_rule_and_every_type():
    cases = [p.values[0] for p in fixture_cases("typing_rule_cases.yaml", "cases")]
    assert {c["expected"]["rule_id"] for c in cases} == set(TYPING_RULE_IDS)
    assert {c["expected"]["type"] for c in cases} == set(COMPONENT_TYPES)


def test_override_table_is_empty_by_default_and_only_a_function_parameter():
    parameter = inspect.signature(derive).parameters["overrides"]
    assert parameter.default == ()
    assert inspect.signature(classify_component).parameters["overrides"].default == ()
    source = inspect.getsource(derivation)
    assert "os.environ" not in source and "getenv" not in source and "open(" not in source and "import os" not in source


def test_override_rejects_unknown_match_key():
    with pytest.raises(ValueError):
        TypeOverride("name", "x", "SENSOR")


def test_datapoint_main_types_ignore_unparsable_tokens_and_sort_numerically():
    objects = make_objects({}, ["DPST-10-1", "DPT-9", "DPST-1-1", "DPST-1-8", "junk", "DPST-5-"])
    assert datapoint_main_types(objects) == ["1", "9", "10"]


# -- derive() over a source-fact set -----------------------------------------------------------
def _facts() -> SourceFacts:
    components = [make_component(), ComponentNode(**_common("DI-2"), address=2, medium_type_ref="MT-0")]
    objects = [
        CommunicationObjectNode(**_common("DI-1/co/a"), component_id="DI-1", ref_id="a", write_flag="Enabled", transmit_flag="Disabled", definition_resolved=True),
        CommunicationObjectNode(**_common("DI-1/co/b"), component_id="DI-1", ref_id="b", write_flag="Enabled", transmit_flag="Disabled", definition_resolved=True),
        CommunicationObjectNode(**_common("DI-2/co/c"), component_id="DI-2", ref_id="c", write_flag="Disabled", transmit_flag="Enabled", definition_resolved=True),
    ]
    relations = Relations(
        membership=[
            MembershipRelation(communication_object_id="DI-1/co/b", group_address_id="GA-2", order=0),
            MembershipRelation(communication_object_id="DI-1/co/a", group_address_id="GA-1", order=0),
            MembershipRelation(communication_object_id="DI-2/co/c", group_address_id="GA-1", order=0),
            MembershipRelation(communication_object_id="DI-2/co/c", group_address_id="GA-2", order=1),
            MembershipRelation(communication_object_id="missing/co", group_address_id="GA-9", order=0),
        ]
    )
    return SourceFacts(nodes=[*components, *objects], relations=relations)


def test_derive_produces_typing_indexes_and_counts():
    derived = derive(_facts())
    assert {k: v.component_type for k, v in derived.component_typing.items()} == {"DI-1": "ACTUATOR", "DI-2": "SENSOR"}
    assert derived.derived_counts.component_type_counts == {"ACTUATOR": 1, "SENSOR": 1}
    index = derived.membership_index
    assert index.group_address_to_communication_objects == {
        "GA-1": ["DI-1/co/a", "DI-2/co/c"],
        "GA-2": ["DI-1/co/b", "DI-2/co/c"],
        "GA-9": ["missing/co"],
    }
    assert index.component_to_group_addresses == {"DI-1": ["GA-1", "GA-2"], "DI-2": ["GA-1", "GA-2"]}


def test_derive_does_not_mutate_its_input_and_is_idempotent():
    facts = _facts()
    before = copy.deepcopy(facts)
    first, second = derive(facts), derive(facts)
    assert facts == before
    assert first == second
    assert derive(before) == first


def test_derive_never_writes_into_source_nodes():
    facts = _facts()
    derive(facts)
    for node in facts.nodes:
        assert "component_type" not in node.model_dump()


def test_derive_applies_injected_overrides_only():
    facts = _facts()
    facts.nodes[0] = make_component(product_ref_id="P-X")
    plain = derive(facts)
    overridden = derive(facts, [TypeOverride("product_ref_id", "P-X", "CONTROLLER")])
    assert plain.component_typing["DI-1"].rule_id == "CT4_DIRECTION"
    assert overridden.component_typing["DI-1"].rule_id == "CT0_OVERRIDE"
    assert overridden.component_typing["DI-1"].component_type == "CONTROLLER"
    assert overridden.component_typing["DI-2"] == plain.component_typing["DI-2"]


def test_derive_on_a_parsed_archive_types_every_component(build):
    parsed, _ = parse_archive(build())
    derived = derive(parsed.source_facts)
    component_ids = {n.id for n in parsed.source_facts.nodes if n.kind == "component"}
    assert set(derived.component_typing) == component_ids
    assert {k: v.component_type for k, v in derived.component_typing.items()} == {
        "P-0001-0_DI-1": "SENSOR",
        "P-0001-0_DI-2": "CONTROLLER",
        "P-0001-0_DI-3": "ACTUATOR",
    }
    assert derived.component_typing["P-0001-0_DI-1"].basis.datapoint_main_types == ["1", "5"]
    assert derived.membership_index.component_to_group_addresses["P-0001-0_DI-2"] == ["P-0001-0_GA-1", "P-0001-0_GA-3"]
