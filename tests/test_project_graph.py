"""Domain graph model, stable ID helpers and group address formatter (story 04, T2)."""

from __future__ import annotations

import json

import pytest
from conftest import fixture_cases
from pydantic import ValidationError

from knx_agent.contracts import (
    PROJECT_PARSE_ERROR_REASONS,
    ImportWarning as ContractImportWarning,
    InvalidatedReference,
    ProjectChange,
    ProjectImportInfo,
    ProjectImportSummary as ContractSummary,
)
from knx_agent.contracts.import_codes import IMPORT_WARNING_CODES
from knx_agent.domain import (
    COMPONENT_TYPES,
    NODE_KINDS,
    RELATION_KINDS,
    ImportWarning,
    ProjectGraph,
)
from knx_agent.domain.project_graph import (
    NODE_CLASSES,
    AreaNode,
    ComponentNode,
    GraphNode,
    GroupAddressNode,
    IdAllocator,
    LoadState,
    MembershipRelation,
    SourceFacts,
    application_program_node_id,
    communication_object_id,
    ets_id,
    format_group_address,
    individual_address_text,
    installation_id,
    parameter_node_id,
    sort_nodes,
    structural_fallback_id,
    structural_key,
)

def _common(**extra):
    return {"id_origin": "ETS_ID", "source_part": "P-1/0.xml", "source_locator": "X", "fact_origin": "PROJECT", **extra}


# -- stable ID rules ----------------------------------------------------------------------------
@pytest.mark.parametrize("case", fixture_cases("stable_id_cases.yaml", "ets_id"))
def test_rule_1_ets_id(case):
    stable = ets_id(case["value"])
    assert (stable.id, stable.origin) == (case["expected"], case["origin"])


@pytest.mark.parametrize("case", fixture_cases("stable_id_cases.yaml", "installation"))
def test_rule_2_installation_id(case):
    stable = installation_id(case["folder"], case["stem"])
    assert (stable.id, stable.origin) == (case["expected"], case["origin"])


@pytest.mark.parametrize("case", fixture_cases("stable_id_cases.yaml", "composite"))
def test_rule_3_composite_ids(case):
    if case["kind"] == "communication_object":
        stable = communication_object_id(case["component"], case["ref"])
    elif case["kind"] == "parameter":
        stable = parameter_node_id(case["component"], case["ref"])
    else:
        stable = application_program_node_id(case["ref"])
    assert (stable.id, stable.origin) == (case["expected"], case["origin"])


@pytest.mark.parametrize("case", fixture_cases("stable_id_cases.yaml", "fallback"))
def test_rule_4_structural_fallback(case):
    key = structural_key(case["address"], case["name"], case["position"])
    stable = structural_fallback_id(case["parent"], case["kind"], key)
    assert stable.id == case["expected"]
    assert stable.origin == "STRUCTURAL_FALLBACK"


@pytest.mark.parametrize("case", fixture_cases("stable_id_cases.yaml", "collision"))
def test_rule_5_collision_suffix(case):
    allocator = IdAllocator()
    results = [allocator.claim(ets_id(claim)) for claim in case["claims"]]
    assert [stable.id for stable, _ in results] == case["expected"]
    assert [collided for _, collided in results] == case["collided"]
    assert all(stable.origin == "ETS_ID" for stable, _ in results)


@pytest.mark.parametrize("case", fixture_cases("stable_id_cases.yaml", "ordering"))
def test_rule_6_deterministic_ordering(case):
    nodes = [_node(item) for item in case["nodes"]]
    ordered = sort_nodes(nodes)
    if "expected" in case:
        assert [node.id for node in ordered] == case["expected"]
    else:
        assert [node.kind for node in ordered] == case["expected_kinds"]
    assert sort_nodes(list(reversed(nodes))) == ordered  # independent of the input order


def _node(item: dict) -> GraphNode:
    return NODE_CLASSES[item["kind"]](**_common(id=item["id"]))


@pytest.mark.parametrize("case", fixture_cases("stable_id_cases.yaml", "group_address_format"))
def test_group_address_text(case):
    assert format_group_address(case["raw"], case["style"]) == case["expected"]


@pytest.mark.parametrize("case", fixture_cases("stable_id_cases.yaml", "individual_address"))
def test_individual_address_text(case):
    assert individual_address_text(case["area"], case["line"], case["device"]) == case["expected"]


# -- model --------------------------------------------------------------------------------------
def test_node_and_relation_kinds_match_the_spec():
    assert NODE_KINDS == (
        "installation", "area", "line", "space", "component", "communication_object",
        "group_address", "group_range", "parameter", "scene", "application_program",
    )  # fmt: skip
    assert RELATION_KINDS == ("membership", "placed_in")
    assert set(NODE_CLASSES) == set(NODE_KINDS)
    assert COMPONENT_TYPES == (
        "IP_COUPLER_OR_INTERFACE", "COUPLER", "SENSOR", "ACTUATOR", "CONTROLLER", "UNTYPED"
    )  # fmt: skip


def test_every_node_kind_carries_the_common_fields():
    common = {"id", "kind", "id_origin", "source_part", "source_locator", "fact_origin"}
    for kind, cls in NODE_CLASSES.items():
        assert common <= set(cls.model_fields), kind
        assert cls(**_common(id="x")).kind == kind


def test_node_field_names_follow_the_spec_tables():
    expected = {
        "component": {
            "line_id", "segment_id", "medium_type_ref", "address", "individual_address", "name", "description",
            "comment", "product_ref_id", "hardware2program_ref_id", "application_program_id", "manufacturer_id",
            "product_text", "order_number", "has_ip_config", "serial_number", "last_modified", "last_download",
            "load_state",
        },
        "communication_object": {
            "component_id", "ref_id", "object_number", "function_text", "text", "object_size", "read_flag",
            "write_flag", "communication_flag", "transmit_flag", "update_flag", "read_on_init_flag",
            "datapoint_types", "channel_id", "description", "instance_text", "definition_resolved",
        },
        "group_address": {"address_raw", "address", "name", "description", "datapoint_type", "range_id"},
        "group_range": {"parent_id", "range_start", "range_end", "name", "description"},
        "parameter": {
            "component_id", "ref_id", "parameter_id", "name", "text", "parameter_type_id", "value",
            "definition_resolved",
        },
        "scene": {"name", "scene_number", "members"},
        "application_program": {
            "manufacturer_id", "application_number", "application_version", "mask_version", "name", "source_loaded"
        },
        "installation": {
            "project_id", "project_name", "group_address_style", "default_line_id", "last_modified",
            "completion_status", "ets_tool_version", "created_by", "schema_namespace",
        },
        "area": {"installation_id", "address", "name"},
        "line": {"area_id", "address", "name", "description", "medium_type_refs"},
        "space": {"parent_id", "space_type", "name", "usage_ref"},
    }  # fmt: skip
    common = {"id", "kind", "id_origin", "source_part", "source_locator", "fact_origin"}
    for kind, fields in expected.items():
        assert set(NODE_CLASSES[kind].model_fields) - common == fields, kind


def test_load_state_has_the_five_loaded_booleans():
    assert set(LoadState.model_fields) == {
        "application_program_loaded", "communication_part_loaded", "individual_address_loaded",
        "medium_config_loaded", "parameters_loaded",
    }  # fmt: skip


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        AreaNode(**_common(id="a"), surprise=1)


def _graph() -> ProjectGraph:
    component = ComponentNode(**_common(id="DI-1"), address=1, name="Sensor", load_state=LoadState(parameters_loaded=True))
    area = AreaNode(**_common(id="A-1"), address=1, name="Area")
    group_address = GroupAddressNode(**_common(id="GA-1"), address_raw=1, address="0/0/1", name="Light")
    return ProjectGraph(
        fingerprint="a" * 64,
        source_facts=SourceFacts(
            nodes=[area, component, group_address],
            relations={"membership": [MembershipRelation(communication_object_id="CO-1", group_address_id="GA-1", order=0)],
                       "placed_in": []},
        ),
        warnings=[ImportWarning(code="DUPLICATE_ID", message="m", location="P-1/0.xml#X")],
    )


def test_graph_serialises_to_the_documented_top_level_keys():
    dumped = _graph().model_dump(mode="json")
    assert set(dumped) == {"graph_schema_version", "fingerprint", "source_facts", "derived_facts", "warnings"}
    assert dumped["graph_schema_version"] == 1
    assert set(dumped["source_facts"]) == {"nodes", "relations"}
    assert set(dumped["source_facts"]["relations"]) == {"membership", "placed_in"}
    assert set(dumped["derived_facts"]) == {"component_typing", "membership_index", "derived_counts"}
    assert dumped["warnings"] == [{"code": "DUPLICATE_ID", "message": "m", "location": "P-1/0.xml#X"}]


def test_graph_round_trips_through_json_with_node_kinds_restored():
    graph = _graph()
    again = ProjectGraph.model_validate(json.loads(graph.model_dump_json()))
    assert again == graph
    assert [type(node) for node in again.source_facts.nodes] == [AreaNode, ComponentNode, GroupAddressNode]


def test_source_nodes_never_carry_derived_values():
    for cls in NODE_CLASSES.values():
        assert "component_type" not in cls.model_fields
    assert "component_type" not in ComponentNode.model_fields


def test_graph_helpers():
    graph = _graph()
    assert [n.id for n in graph.nodes_of("component")] == ["DI-1"]
    assert set(graph.node_index()) == {"A-1", "DI-1", "GA-1"}


# -- contracts ----------------------------------------------------------------------------------
def test_contract_warning_and_domain_warning_have_the_same_shape():
    assert set(ContractImportWarning.model_fields) == set(ImportWarning.model_fields) == {"code", "message", "location"}


def test_contract_summary_has_the_documented_fields():
    assert set(ContractSummary.model_fields) >= {
        "file_name", "archive_entry_count", "ets_tool_version", "schema_namespace", "created_by", "project_id",
        "project_name", "group_address_style", "node_counts", "relation_counts", "component_type_counts",
        "application_programs", "warning_total", "warning_counts", "graph_file", "graph_schema_version",
    }  # fmt: skip


def test_contract_change_reference_and_info_models():
    change = ProjectChange(entity="component", change="changed", id="DI-1", label="x (1.1.1)", details={"changed_fields": ["name"]})
    assert change.model_dump()["details"] == {"changed_fields": ["name"]}
    reference = InvalidatedReference(reference_kind="mutation_delta", owner="m", component_id="DI-1", reason="COMPONENT_REMOVED")
    assert reference.group_address_id is None
    info = ProjectImportInfo(
        imported_at="t", fingerprint="f", graph_file="/w/project-graph.json",
        project_import_summary=ContractSummary(file_name="a.knxproj", archive_entry_count=1),
    )  # fmt: skip
    assert set(info.model_dump()) == {"imported_at", "fingerprint", "graph_file", "project_import_summary"}
    with pytest.raises(ValidationError):
        ProjectChange(entity="parameter", change="added", id="x", label="x")
    with pytest.raises(ValidationError):
        InvalidatedReference(reference_kind="other", owner="m", reason="COMPONENT_REMOVED")


def test_reason_and_warning_code_constants_are_complete():
    assert set(PROJECT_PARSE_ERROR_REASONS) == {
        "NOT_A_ZIP", "ENCRYPTED", "ARCHIVE_TOO_MANY_ENTRIES", "ARCHIVE_ENTRY_TOO_LARGE", "ARCHIVE_TOTAL_TOO_LARGE",
        "ARCHIVE_COMPRESSION_RATIO", "ARCHIVE_DUPLICATE_ENTRY", "PROJECT_FOLDER_NOT_FOUND", "REQUIRED_PART_MISSING",
        "REQUIRED_PART_MALFORMED", "NOT_ETS_PROJECT", "UNSUPPORTED_NAMESPACE", "UNSUPPORTED_TOOL_VERSION",
        "XML_DTD_FORBIDDEN", "XML_ENTITY_FORBIDDEN", "XML_ENCODING_UNSUPPORTED",
    }  # fmt: skip
    assert set(IMPORT_WARNING_CODES) == {
        "OPTIONAL_PART_MISSING", "OPTIONAL_PART_UNREADABLE", "APPLICATION_PROGRAM_MISSING",
        "PRODUCT_REFERENCE_UNRESOLVED", "APPLICATION_PROGRAM_REFERENCE_MISMATCH", "COMOBJECT_DEFINITION_UNRESOLVED",
        "PARAMETER_DEFINITION_UNRESOLVED", "GROUP_ADDRESS_LINK_UNRESOLVED", "DEVICE_REFERENCE_UNRESOLVED",
        "DATAPOINT_TYPE_UNKNOWN", "INVALID_ATTRIBUTE_VALUE", "DUPLICATE_ID", "STRUCTURAL_ID_FALLBACK",
        "UNSUPPORTED_ELEMENT", "ADDITIONAL_INSTALLATION_IGNORED",
    }  # fmt: skip
