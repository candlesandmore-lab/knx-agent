"""Build a ProjectGraph from a compact description (tests only; story 05, T2).

Domain tests use this instead of archives. The description is plain data (usually from a YAML fixture)::

    style: ThreeLevel                      # group address style of the installation (default ThreeLevel)
    areas: [{id: A1, address: 1, name: Area}]
    lines: [{id: L1, area: A1, address: 1, name: Line}]
    spaces:                                # a tree; children nest; "type" is the space type
      - {id: S1, type: Building, name: House, children: [{id: S2, type: Floor, name: EG, children: [...]}]}
    components:                            # id is the ETS id (for example P-1-0_DI-1)
      - {id: P-1-0_DI-1, line: L1, address: 5, name: Switch, in: [S2], product: PR-1, program: APP-1}
        # individual_address defaults to '<area>.<line>.<address>'; give individual_address: null/text to override;
        # typing: {component_type: SENSOR, rule_id: CT0_OVERRIDE} overrides the derived typing; other keys that
        # are ComponentNode fields (description, comment, serial_number, has_ip_config, ...) are copied.
    objects:                               # communication objects; node id is '<component>/co/<ref>'
      - {component: P-1-0_DI-1, ref: O-0_R-1, number: 0, text: Switch, flags: tx, dpt: [DPST-1-1], links: [G1, G2]}
        # flags: tx | rx | both | none | rd | a mapping {read, write, communication, transmit, update, read_on_init};
        # resolved: false gives definition_resolved false and null flags; links are group address ids in order.
    group_addresses:
      - {id: G1, address: "1/0/1", name: Light, dpt: DPST-1-1, range: R1}      # or raw: 2305
    group_ranges: [{id: R1, name: Lights, parent: null}]
    parameters: [{component: P-1-0_DI-1, ref: P-1_R-1, name: Delay, text: Delay time, value: "5", type: PT-1}]
    programs: [{id: APP-1, number: 1, version: 1, mask: MV-0705, name: App, source_loaded: true}]
    warnings: [{code: ..., message: ..., location: "0.xml#<node id>"}]

Typing is derived with ``domain.derivation.derive`` (the real rules) unless a component gives ``typing``.
"""

from __future__ import annotations

from conftest import load_fixture

from knx_agent.domain.derivation import derive
from knx_agent.domain.project_graph import (
    RULE_CT0_OVERRIDE,
    AreaNode,
    CommunicationObjectNode,
    ComponentNode,
    ComponentTyping,
    ComponentTypingBasis,
    GroupAddressNode,
    GroupRangeNode,
    ImportWarning,
    InstallationNode,
    LineNode,
    MembershipRelation,
    ParameterNode,
    PlacedInRelation,
    ProjectGraph,
    Relations,
    SourceFacts,
    SpaceNode,
    ApplicationProgramNode,
    format_group_address,
)

_COMMON = {"id_origin": "ETS_ID", "source_part": "0.xml", "source_locator": "factory", "fact_origin": "PROJECT"}
_FLAG_KEYS = ("read", "write", "communication", "transmit", "update", "read_on_init")


def _flags(spec) -> dict[str, str]:
    base = {key: "Disabled" for key in _FLAG_KEYS}
    base["communication"] = "Enabled"
    if isinstance(spec, dict):
        base.update(spec)
        return base
    if spec in ("tx", "both"):
        base["transmit"] = "Enabled"
    if spec in ("rx", "both"):
        base["write"] = "Enabled"
    if spec == "rd":
        base["read"] = "Enabled"
    if spec == "upd":
        base["update"] = "Enabled"
    return base


def _address_raw(text: str, style: str) -> int:
    parts = [int(p) for p in str(text).split("/")]
    if len(parts) == 3:
        return (parts[0] << 11) | (parts[1] << 8) | parts[2]
    if len(parts) == 2:
        return (parts[0] << 11) | parts[1]
    return parts[0]


def build_graph(description: dict) -> ProjectGraph:
    """The ProjectGraph described by ``description`` (see module docstring)."""
    style = description.get("style", "ThreeLevel")
    nodes: list = [InstallationNode(id="P-1-0", group_address_style=style, **_COMMON)]
    area_address: dict[str, int | None] = {}
    line_address: dict[str, int | None] = {}
    line_area: dict[str, str | None] = {}
    for area in description.get("areas", []):
        area_address[area["id"]] = area.get("address")
        nodes.append(AreaNode(id=area["id"], address=area.get("address"), name=area.get("name"), installation_id="P-1-0", **_COMMON))
    for line in description.get("lines", []):
        line_address[line["id"]] = line.get("address")
        line_area[line["id"]] = line.get("area")
        nodes.append(LineNode(id=line["id"], area_id=line.get("area"), address=line.get("address"), name=line.get("name"), **_COMMON))

    placed: list[PlacedInRelation] = []

    def add_space(space: dict, parent: str | None) -> None:
        nodes.append(
            SpaceNode(id=space["id"], parent_id=space.get("parent", parent), space_type=space.get("type"), name=space.get("name"), **_COMMON)
        )
        for child in space.get("children", []):
            add_space(child, space["id"])

    for space in description.get("spaces", []):
        add_space(space, None)

    overrides: dict[str, ComponentTyping] = {}
    for component in description.get("components", []):
        fields = {
            key: value
            for key, value in component.items()
            if key in ComponentNode.model_fields and key not in ("id", "name", "line_id", "address", "individual_address")
        }
        line_id = component.get("line")
        address = component.get("address")
        if "individual_address" in component:
            individual = component["individual_address"]
        else:
            area_part = area_address.get(line_area.get(line_id)) if line_id else None
            line_part = line_address.get(line_id) if line_id else None
            individual = (
                f"{area_part}.{line_part}.{address}" if None not in (area_part, line_part, address) else None
            )
        if "program" in component:
            fields["application_program_id"] = component["program"]
        if "product" in component:
            fields["product_ref_id"] = component["product"]
        nodes.append(
            ComponentNode(
                id=component["id"], name=component.get("name"), line_id=line_id, address=address,
                individual_address=individual, **fields, **_COMMON,
            )
        )
        for space_id in component.get("in", []):
            placed.append(PlacedInRelation(space_id=space_id, component_id=component["id"]))
        if "typing" in component:
            typing = component["typing"]
            overrides[component["id"]] = ComponentTyping(
                component_type=typing["component_type"],
                rule_id=typing.get("rule_id", RULE_CT0_OVERRIDE),
                basis=ComponentTypingBasis(**typing.get("basis", {})),
            )

    memberships: list[MembershipRelation] = []
    for obj in description.get("objects", []):
        node_id = f"{obj['component']}/co/{obj['ref']}"
        resolved = obj.get("resolved", True)
        flags = _flags(obj.get("flags", "none")) if resolved else {}
        nodes.append(
            CommunicationObjectNode(
                id=node_id,
                component_id=obj["component"],
                ref_id=obj["ref"],
                object_number=obj.get("number"),
                function_text=obj.get("function_text"),
                text=obj.get("text"),
                instance_text=obj.get("instance_text"),
                description=obj.get("description"),
                object_size=obj.get("size", "1 Bit" if resolved else None),
                read_flag=flags.get("read"),
                write_flag=flags.get("write"),
                communication_flag=flags.get("communication"),
                transmit_flag=flags.get("transmit"),
                update_flag=flags.get("update"),
                read_on_init_flag=flags.get("read_on_init"),
                datapoint_types=obj.get("dpt", []),
                definition_resolved=resolved,
                **_COMMON,
            )
        )
        for order, group_address_id in enumerate(obj.get("links", [])):
            memberships.append(MembershipRelation(communication_object_id=node_id, group_address_id=group_address_id, order=order))

    for group_range in description.get("group_ranges", []):
        nodes.append(GroupRangeNode(id=group_range["id"], parent_id=group_range.get("parent"), name=group_range.get("name"), **_COMMON))
    for ga in description.get("group_addresses", []):
        raw = ga["raw"] if "raw" in ga else _address_raw(ga["address"], style)
        nodes.append(
            GroupAddressNode(
                id=ga["id"], address_raw=raw, address=format_group_address(raw, style), name=ga.get("name"),
                description=ga.get("description"), datapoint_type=ga.get("dpt"), range_id=ga.get("range"), **_COMMON,
            )
        )
    for parameter in description.get("parameters", []):
        resolved = parameter.get("resolved", True)
        nodes.append(
            ParameterNode(
                id=f"{parameter['component']}/pa/{parameter['ref']}",
                component_id=parameter["component"],
                ref_id=parameter["ref"],
                name=parameter.get("name"),
                text=parameter.get("text"),
                parameter_type_id=parameter.get("type"),
                value=parameter.get("value"),
                definition_resolved=resolved,
                **_COMMON,
            )
        )
    for program in description.get("programs", []):
        nodes.append(
            ApplicationProgramNode(
                id=program["id"], application_number=program.get("number"), application_version=program.get("version"),
                mask_version=program.get("mask"), name=program.get("name"), source_loaded=program.get("source_loaded", True),
                **_COMMON,
            )
        )

    source = SourceFacts(nodes=nodes, relations=Relations(membership=memberships, placed_in=placed))
    derived = derive(source)
    derived.component_typing.update(overrides)
    return ProjectGraph(
        source_facts=source,
        derived_facts=derived,
        warnings=[ImportWarning(**w) for w in description.get("warnings", [])],
    )


def graphs_of(fixture_name: str) -> dict[str, dict]:
    """The named graph descriptions (top-level key ``graphs``) of a YAML fixture file."""
    return load_fixture(fixture_name).get("graphs", {})


def graph_for_case(graphs: dict[str, dict], case: dict) -> ProjectGraph:
    """The graph of a case: ``graph`` is a name in ``graphs`` or an inline description."""
    description = case["graph"]
    return build_graph(graphs[description] if isinstance(description, str) else description)
