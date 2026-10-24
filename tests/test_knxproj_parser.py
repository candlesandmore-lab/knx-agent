"""ETS 6 parser: nodes, relations, provenance, IDs, warnings, errors, program resolution (story 04, T6)."""

from __future__ import annotations

import collections
import json

import pytest
from conftest import build_case, fixture_cases, parse_archive

from knx_agent.application.knxproj_archive import ArchiveLimits, KnxprojArchive
from knx_agent.application.knxproj_parser import (
    derive_program_id_from_hardware2program,
    parse_project,
    reference_program_prefix,
)
from knx_agent.contracts import KnxAgentError, PROJECT_PARSE_ERROR
from knx_agent.contracts.import_codes import IMPORT_WARNING_CODES
from knx_agent.domain.project_graph import NODE_KINDS

PF = "P-0001"
ZERO = "P-0001/0.xml"
APP1, APP2, APP3 = "M-0001_A-0001-01-AAAA", "M-0001_A-0002-01-BBBB", "M-0001_A-0003-01-CCCC"


def nodes_by_id(parsed):
    return {node.id: node for node in parsed.source_facts.nodes}


def of_kind(parsed, kind):
    return [node for node in parsed.source_facts.nodes if node.kind == kind]


def codes(parsed) -> dict[str, int]:
    return dict(collections.Counter(w.code for w in parsed.warnings))


@pytest.fixture
def default_parsed(build):
    return parse_archive(build())[0]


# -- node kinds ---------------------------------------------------------------------------------
def test_default_archive_node_and_relation_counts(default_parsed):
    counts = collections.Counter(node.kind for node in default_parsed.source_facts.nodes)
    assert {kind: counts.get(kind, 0) for kind in NODE_KINDS} == {
        "installation": 1, "area": 1, "line": 1, "space": 3, "component": 3, "communication_object": 6,
        "group_address": 3, "group_range": 2, "parameter": 2, "scene": 0, "application_program": 2,
    }  # fmt: skip
    assert len(default_parsed.source_facts.relations.membership) == 4
    assert len(default_parsed.source_facts.relations.placed_in) == 2
    assert default_parsed.warnings == []
    assert {n.kind for n in default_parsed.source_facts.nodes} <= set(NODE_KINDS)


def test_installation_node(default_parsed):
    (installation,) = of_kind(default_parsed, "installation")
    assert installation.id == "P-0001-0"
    assert installation.id_origin == "ETS_COMPOSITE"
    assert installation.project_id == "P-0001"
    assert installation.project_name == "Synthetic house"
    assert installation.group_address_style == "ThreeLevel"
    assert installation.default_line_id == "P-0001-0_L-1"
    assert installation.completion_status == "Editing"
    assert installation.ets_tool_version == "6.1.5686.0"
    assert installation.created_by == "ETS6"
    assert installation.schema_namespace == "http://knx.org/xml/project/22"
    assert (installation.source_part, installation.source_locator, installation.fact_origin) == (ZERO, "Installation", "PROJECT")


def test_area_and_line_nodes(default_parsed):
    (area,) = of_kind(default_parsed, "area")
    (line,) = of_kind(default_parsed, "line")
    assert (area.id, area.installation_id, area.address, area.name) == ("P-0001-0_A-1", "P-0001-0", 1, "Area one")
    assert area.source_locator == "Area[@Id=P-0001-0_A-1]"
    assert (line.id, line.area_id, line.address, line.name) == ("P-0001-0_L-1", "P-0001-0_A-1", 1, "Line one")
    assert line.medium_type_refs == ["MT-0"]


def test_component_nodes(default_parsed):
    components = {n.id: n for n in of_kind(default_parsed, "component")}
    first = components["P-0001-0_DI-1"]
    assert first.id_origin == "ETS_ID"
    assert first.line_id == "P-0001-0_L-1"
    assert first.segment_id == "P-0001-0_S-1"
    assert first.medium_type_ref == "MT-0"
    assert (first.address, first.individual_address, first.name) == (1, "1.1.1", "Sensor")
    assert first.product_ref_id == "M-0001_H-1_P-S1"
    assert first.hardware2program_ref_id == "M-0001_H-1_HP-0001-01-AAAA"
    assert first.application_program_id == APP1
    assert first.manufacturer_id == "M-0001"
    assert (first.product_text, first.order_number) == ("Sensor product", "SW-1")
    assert first.has_ip_config is False
    assert first.load_state.application_program_loaded is True
    assert first.load_state.parameters_loaded is True
    assert first.last_modified == "2026-01-01T00:00:00Z"
    assert first.last_download is None and first.serial_number is None
    assert first.source_locator == "DeviceInstance[@Id=P-0001-0_DI-1]"
    assert components["P-0001-0_DI-3"].application_program_id == APP2
    assert components["P-0001-0_DI-3"].product_text == "Actuator product"


def test_communication_object_nodes_merge_definition_and_instance(default_parsed):
    objects = nodes_by_id(default_parsed)
    switch = objects["P-0001-0_DI-1/co/O-0_R-1"]
    assert switch.id_origin == "ETS_COMPOSITE"
    assert switch.component_id == "P-0001-0_DI-1"
    assert switch.ref_id == "O-0_R-1"
    assert switch.definition_resolved is True
    assert (switch.object_number, switch.text, switch.function_text, switch.object_size) == (0, "Switch input", "Switch input", "1 Bit")
    assert (switch.transmit_flag, switch.write_flag, switch.read_flag, switch.communication_flag) == ("Enabled", "Disabled", "Disabled", "Enabled")
    assert (switch.update_flag, switch.read_on_init_flag) == ("Disabled", "Disabled")
    assert switch.datapoint_types == ["DPST-1-1"]
    assert switch.source_part == ZERO
    assert switch.source_locator == "DeviceInstance[@Id=P-0001-0_DI-1]/ComObjectInstanceRef[@RefId=O-0_R-1]"
    assert switch.fact_origin == "PROJECT"
    output = objects["P-0001-0_DI-2/co/O-2_R-3"]
    assert (output.write_flag, output.transmit_flag) == ("Enabled", "Disabled")


def test_parameter_nodes(default_parsed):
    parameter = nodes_by_id(default_parsed)[f"P-0001-0_DI-2/pa/{APP1}_P-1_R-1"]
    assert parameter.id_origin == "ETS_COMPOSITE"
    assert parameter.component_id == "P-0001-0_DI-2"
    assert parameter.ref_id == f"{APP1}_P-1_R-1"
    assert parameter.parameter_id == f"{APP1}_P-1"
    assert (parameter.name, parameter.text, parameter.parameter_type_id) == ("Delay", "Delay time", f"{APP1}_PT-Time")
    assert parameter.value == "5"  # the raw instance value
    assert parameter.definition_resolved is True


def test_group_address_and_range_nodes(default_parsed):
    nodes = nodes_by_id(default_parsed)
    light = nodes["P-0001-0_GA-1"]
    assert (light.address_raw, light.address, light.name, light.datapoint_type) == (1, "0/0/1", "Light", "DPST-1-1")
    assert light.range_id == "P-0001-0_GR-2"
    assert nodes["P-0001-0_GA-3"].datapoint_type is None
    inner, outer = nodes["P-0001-0_GR-2"], nodes["P-0001-0_GR-1"]
    assert (inner.parent_id, inner.range_start, inner.range_end) == ("P-0001-0_GR-1", 0, 255)
    assert (outer.parent_id, outer.range_start, outer.range_end, outer.name) == (None, 0, 2047, "Main group")


def test_space_nodes_and_placed_in_relations(default_parsed):
    nodes = nodes_by_id(default_parsed)
    building, floor, room = nodes["P-0001-0_BP-1"], nodes["P-0001-0_BP-2"], nodes["P-0001-0_BP-3"]
    assert (building.parent_id, building.space_type, building.name) == (None, "Building", "House")
    assert (floor.parent_id, floor.space_type) == ("P-0001-0_BP-1", "Floor")
    assert (room.parent_id, room.space_type, room.usage_ref) == ("P-0001-0_BP-2", "Room", "SU-1")
    placed = [(r.space_id, r.component_id) for r in default_parsed.source_facts.relations.placed_in]
    assert placed == [("P-0001-0_BP-3", "P-0001-0_DI-1"), ("P-0001-0_BP-3", "P-0001-0_DI-2")]


def test_membership_relations_keep_the_links_order(default_parsed):
    memberships = [(m.communication_object_id, m.group_address_id, m.order) for m in default_parsed.source_facts.relations.membership]
    assert memberships == [
        ("P-0001-0_DI-1/co/O-0_R-1", "P-0001-0_GA-1", 0),
        ("P-0001-0_DI-1/co/O-1_R-2", "P-0001-0_GA-2", 0),
        ("P-0001-0_DI-2/co/O-2_R-3", "P-0001-0_GA-1", 0),
        ("P-0001-0_DI-2/co/O-2_R-3", "P-0001-0_GA-3", 1),
    ]


def test_application_program_nodes(default_parsed):
    programs = {n.id: n for n in of_kind(default_parsed, "application_program")}
    assert set(programs) == {APP1, APP2}  # the unreferenced APP3 has no node
    first = programs[APP1]
    assert first.id_origin == "ETS_COMPOSITE"
    assert first.fact_origin == "CATALOG"
    assert first.source_part == f"M-0001/{APP1}.xml"
    assert (first.manufacturer_id, first.application_number, first.application_version) == ("M-0001", 1, 1)
    assert (first.mask_version, first.name, first.source_loaded) == ("MV-0705", "Sensor application", True)


def test_nodes_are_sorted_by_kind_and_id_and_relations_by_key(default_parsed):
    nodes = default_parsed.source_facts.nodes
    assert [(n.kind, n.id) for n in nodes] == sorted((n.kind, n.id) for n in nodes)
    relations = default_parsed.source_facts.relations
    assert relations.membership == sorted(relations.membership, key=lambda r: (r.communication_object_id, r.order, r.group_address_id))
    assert relations.placed_in == sorted(relations.placed_in, key=lambda r: (r.space_id, r.component_id))


def test_every_node_has_provenance(default_parsed):
    for node in default_parsed.source_facts.nodes:
        assert node.source_part and node.source_locator
        assert node.fact_origin in ("PROJECT", "CATALOG")
        assert node.id_origin in ("ETS_ID", "ETS_COMPOSITE", "STRUCTURAL_FALLBACK")


def test_parser_returns_source_facts_only(default_parsed):
    dumped = json.dumps([n.model_dump() for n in default_parsed.source_facts.nodes])
    assert "component_type" not in dumped and "rule_id" not in dumped


def test_two_parses_of_the_same_archive_give_identical_source_facts_and_warnings(build):
    path = build(mutations=[{"op": "remove", "entry": "master_xml"}])
    first, _ = parse_archive(path)
    second, _ = parse_archive(path)
    assert first.source_facts.model_dump() == second.source_facts.model_dump()
    assert first.warnings == second.warnings


def test_two_independent_archives_of_one_description_give_identical_graphs(build):
    first, _ = parse_archive(build())
    second, _ = parse_archive(build())
    assert first.source_facts == second.source_facts


# -- description variants ----------------------------------------------------------------------
def test_two_level_and_free_group_address_styles(build):
    two, _ = parse_archive(build(edits=[{"path": "address_style", "value": "TwoLevel"}]))
    free, _ = parse_archive(build(edits=[{"path": "address_style", "value": "Free"}]))
    assert nodes_by_id(two)["P-0001-0_GA-1"].address == "0/1"
    assert nodes_by_id(free)["P-0001-0_GA-1"].address == "1"
    assert of_kind(two, "installation")[0].group_address_style == "TwoLevel"


def test_ip_component_and_multiple_lines(build):
    line = {
        "address": 2, "name": "IP line", "medium": "MT-5",
        "components": [{"address": 0, "name": "IP router", "product": "M-0001_H-1_P-S1", "ip_config": True, "objects": [], "parameters": []}],
    }  # fmt: skip
    parsed, _ = parse_archive(build(edits=[{"path": "areas.0.lines", "append": line}]))
    router = next(n for n in of_kind(parsed, "component") if n.name == "IP router")
    assert router.has_ip_config is True
    assert router.medium_type_ref == "MT-5"
    assert router.individual_address == "1.2.0"
    assert router.application_program_id is None
    assert {n.id: n.medium_type_refs for n in of_kind(parsed, "line")} == {"P-0001-0_L-1": ["MT-0"], "P-0001-0_L-2": ["MT-5"]}


def test_object_reference_attributes_override_the_object_definition(build):
    path = build(edits=[{
        "path": "catalog.manufacturers.0.applications.0.objects.0.ref_overrides",
        "value": {"WriteFlag": "Enabled", "Text": "Overridden", "DatapointType": "DPST-1-2 DPST-5-1"},
    }])  # fmt: skip
    parsed, _ = parse_archive(path)
    switch = nodes_by_id(parsed)["P-0001-0_DI-1/co/O-0_R-1"]
    assert (switch.write_flag, switch.transmit_flag, switch.text) == ("Enabled", "Enabled", "Overridden")
    assert switch.datapoint_types == ["DPST-1-2", "DPST-5-1"]


def test_instance_attributes_are_kept_on_communication_objects(build):
    edits = [{"path": "areas.0.lines.0.components.0.objects.0.channel", "value": "CH-1"},
             {"path": "areas.0.lines.0.components.0.objects.0.description", "value": "instance description"},
             {"path": "areas.0.lines.0.components.0.objects.0.text", "value": "instance text"}]  # fmt: skip
    obj = nodes_by_id(parse_archive(build(edits=edits))[0])["P-0001-0_DI-1/co/O-0_R-1"]
    assert (obj.channel_id, obj.description, obj.instance_text) == ("CH-1", "instance description", "instance text")


def test_scene_is_mapped_from_a_scene_element(build):
    parsed, _ = parse_archive(build(edits=[{"path": "scenes", "value": [{"name": "Evening", "number": 3, "members": ["P-0001-0_DI-1", "P-0001-0_DI-2"]}]}]))
    (scene,) = of_kind(parsed, "scene")
    assert (scene.name, scene.scene_number, scene.members) == ("Evening", 3, ["P-0001-0_DI-1", "P-0001-0_DI-2"])
    assert scene.id == "s:P-0001-0/scene[3]"
    assert scene.id_origin == "STRUCTURAL_FALLBACK"
    assert codes(parsed) == {"STRUCTURAL_ID_FALLBACK": 1}
    assert "UNSUPPORTED_ELEMENT" not in codes(parsed)  # SceneMember inside a mapped Scene is not unsupported


def test_fallback_ids_use_address_name_or_position(build):
    parsed, _ = parse_archive(build(edits=[
        {"path": "areas.0.omit_id", "value": True},
        {"path": "areas.0.lines.0.omit_id", "value": True},
        {"path": "areas.0.lines.0.components.0.omit_id", "value": True},
        {"path": "spaces.0.omit_id", "value": True},
    ]))  # fmt: skip
    ids = {n.kind: n.id for n in parsed.source_facts.nodes if n.id_origin == "STRUCTURAL_FALLBACK"}
    assert ids["area"] == "s:P-0001-0/area[1]"
    assert ids["line"] == "s:s:P-0001-0/area[1]/line[1]"
    assert ids["component"] == "s:s:s:P-0001-0/area[1]/line[1]/component[1]"
    assert ids["space"] == "s:P-0001-0/space[House]"
    line = next(n for n in of_kind(parsed, "line"))
    assert line.area_id == "s:P-0001-0/area[1]"


def test_duplicate_ids_get_the_suffix_and_stay_deterministic(build):
    path = build(edits=[{"path": "areas.0.lines.0.components.1.id", "value": "DI-1"}])
    first, _ = parse_archive(path)
    ids = sorted(n.id for n in of_kind(first, "component"))
    assert ids == ["P-0001-0_DI-1", "P-0001-0_DI-1~2", "P-0001-0_DI-3"]
    assert parse_archive(path)[0].source_facts == first.source_facts


def test_object_and_parameter_composite_id_collisions_get_a_suffix(build):
    duplicate = {"ref": "O-0_R-1", "links": []}
    path = build(edits=[{"path": "areas.0.lines.0.components.0.objects", "append": duplicate}])
    parsed, _ = parse_archive(path)
    ids = sorted(n.id for n in of_kind(parsed, "communication_object") if n.component_id == "P-0001-0_DI-1")
    assert ids == ["P-0001-0_DI-1/co/O-0_R-1", "P-0001-0_DI-1/co/O-0_R-1~2", "P-0001-0_DI-1/co/O-1_R-2"]
    assert codes(parsed) == {"DUPLICATE_ID": 1}


def test_large_application_program_is_streamed(build):
    path = build(edits=[{"path": "catalog.manufacturers.0.applications.0.filler", "value": 6000}])
    parsed, _ = parse_archive(path)
    assert parsed.warnings == []
    assert nodes_by_id(parsed)["P-0001-0_DI-1/co/O-0_R-1"].definition_resolved is True


# -- helpers ------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("hardware2program", "expected"),
    [
        ("M-0083_H-88-1_HP-0056-11-A826", "M-0083_A-0056-11-A826"),
        ("M-0083_H-2.2E37-1_HP-008A-22-33A1", "M-0083_A-008A-22-33A1"),
        ("M-0083_H-159-1-O00EF_HP-0052-10-586E-O00EF", "M-0083_A-0052-10-586E-O00EF"),
        ("M-0083_H-1-1", None),
        ("nonsense", None),
        ("M-0083_H-1-1_HP-", None),
    ],
)
def test_textual_program_derivation(hardware2program, expected):
    assert derive_program_id_from_hardware2program(hardware2program) == expected


@pytest.mark.parametrize(
    ("ref_id", "expected"),
    [
        ("M-0083_A-0028-34-2692_P-14000_R-14000", "M-0083_A-0028-34-2692"),
        ("M-0083_A-0028-34-2692_UP-5_R-6", "M-0083_A-0028-34-2692"),
        ("M-0083_A-013C-32-51EA_MD-2_M-1_MI-1_P-1_R-1", "M-0083_A-013C-32-51EA"),
        ("O-0_R-1", None),
    ],
)
def test_parameter_reference_program_prefix(ref_id, expected):
    assert reference_program_prefix(ref_id) == expected


# -- data driven: errors, warnings, program resolution -----------------------------------------
@pytest.mark.parametrize("case", fixture_cases("import_error_cases.yaml", "cases"))
def test_import_error_cases(build, case):
    path = build_case(build, case)
    with pytest.raises(KnxAgentError) as exc_info:
        with KnxprojArchive(path) as archive:
            parse_project(archive)
    error = exc_info.value.error
    assert error.code == PROJECT_PARSE_ERROR
    assert error.details["reason"] == case["expected_reason"]
    assert error.details["path"] == str(path)
    if "expected_entry" in case:
        assert error.details["entry"] == case["expected_entry"]


def test_unsupported_namespace_and_tool_version_details(build):
    with pytest.raises(KnxAgentError) as exc_info:
        parse_archive(build(edits=[{"path": "namespace", "value": "http://knx.org/xml/project/20"}]))
    assert exc_info.value.error.details["namespace"] == "http://knx.org/xml/project/20"
    with pytest.raises(KnxAgentError) as exc_info:
        parse_archive(build(edits=[{"path": "tool_version", "value": "5.7.1.0"}]))
    assert exc_info.value.error.details["tool_version"] == "5.7.1.0"


@pytest.mark.parametrize("case", fixture_cases("import_warning_cases.yaml", "cases"))
def test_import_warning_cases(build, case):
    parsed, _ = parse_archive(build_case(build, case))
    assert codes(parsed) == case["expected_codes"]
    assert set(codes(parsed)) <= set(IMPORT_WARNING_CODES)
    for code, location in case.get("expected_locations", {}).items():
        assert next(w for w in parsed.warnings if w.code == code).location == location
    for code, text in case.get("expected_message_contains", {}).items():
        assert text in next(w for w in parsed.warnings if w.code == code).message
    for warning in parsed.warnings:
        assert warning.message and warning.location


@pytest.mark.parametrize("case", fixture_cases("application_program_resolution_cases.yaml", "cases"))
def test_application_program_resolution_cases(build, case):
    parsed, opened = parse_archive(build_case(build, case))
    components = {n.id: n for n in of_kind(parsed, "component")}
    for component_id, expected in case["components"].items():
        assert components[component_id].application_program_id == expected, component_id
    assert parsed.application_programs.referenced == case["programs"]["referenced"]
    assert parsed.application_programs.read == case["programs"]["read"]
    assert parsed.application_programs.unreadable == case["programs"]["unreadable"]
    opened_programs = {name for name in opened if "_A-" in name and name.endswith(".xml")}
    assert opened_programs == set(case["opened_programs"])
    for name in case.get("not_opened", []):
        assert name not in opened
    assert codes(parsed) == case["warning_counts"]
    program_nodes = {n.id: n for n in of_kind(parsed, "application_program")}
    assert len(program_nodes) == case["programs"]["referenced"]
    assert sum(1 for n in program_nodes.values() if n.source_loaded) == case["programs"]["read"]


def test_unreferenced_program_has_no_node_and_is_never_read(build):
    parsed, opened = parse_archive(build())
    assert f"M-0001/{APP3}.xml" not in opened
    assert APP3 not in nodes_by_id(parsed)


# -- optional parts that are rejected are not used ---------------------------------------------
@pytest.mark.parametrize("op", ["doctype", "entity", "utf16", "malform"])
def test_rejected_application_program_contributes_nothing_and_does_not_affect_others(build, op):
    parsed, _ = parse_archive(build(mutations=[{"op": op, "entry": f"application_xml:{APP1}"}]))
    nodes = nodes_by_id(parsed)
    for component in ("P-0001-0_DI-1", "P-0001-0_DI-2"):
        for node in parsed.source_facts.nodes:
            if getattr(node, "component_id", None) == component and node.kind in ("communication_object", "parameter"):
                assert node.definition_resolved is False
                if node.kind == "communication_object":
                    assert node.datapoint_types == [] and node.transmit_flag is None and node.text is None
                else:
                    assert node.name is None and node.parameter_id is None
    other = nodes["P-0001-0_DI-3/co/O-0_R-1"]
    assert other.definition_resolved is True and other.write_flag == "Enabled"
    assert nodes[APP1].source_loaded is False and nodes[APP2].source_loaded is True
    assert nodes["P-0001-0_DI-1"].application_program_id == APP1  # the reference is known, the content is not
    assert len(parsed.source_facts.relations.membership) == 4  # memberships come from the project, not the program


@pytest.mark.parametrize("op", ["doctype", "entity", "utf16"])
def test_rejected_hardware_xml_is_not_used_for_product_texts(build, op):
    parsed, _ = parse_archive(build(mutations=[{"op": op, "entry": "hardware_xml"}]))
    component = nodes_by_id(parsed)["P-0001-0_DI-1"]
    assert component.product_text is None and component.order_number is None
    assert component.application_program_id == APP1  # via P2 (the entry exists)
    assert len(of_kind(parsed, "communication_object")) == 6


@pytest.mark.parametrize("op", ["doctype", "entity", "utf16"])
def test_rejected_master_means_datapoint_types_are_not_verified(build, op):
    parsed, _ = parse_archive(build(mutations=[{"op": op, "entry": "master_xml"}], edits=[{"path": "master_datapoints", "value": ["DPT-1"]}]))
    assert codes(parsed) == {"OPTIONAL_PART_UNREADABLE": 1}  # no DATAPOINT_TYPE_UNKNOWN: the master was never used


def test_required_part_limits_do_not_apply_to_streaming_source_facts(build):
    parsed, _ = parse_archive(build(), ArchiveLimits(max_entries=7))
    assert len(of_kind(parsed, "component")) == 3
