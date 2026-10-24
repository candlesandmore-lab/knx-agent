"""Project graph model (story 04): source facts, derived facts, warnings, stable ID helpers.

Pure model, no I/O and no framework imports beyond pydantic. The graph has two separate parts:
``source_facts`` (nodes and relations imported without interpretation) and ``derived_facts`` (component
typing, reverse indexes, counts). No derived value is ever written into a source node.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

GRAPH_SCHEMA_VERSION = 1

# -- vocabulary ---------------------------------------------------------------------------------
IdOrigin = Literal["ETS_ID", "ETS_COMPOSITE", "STRUCTURAL_FALLBACK"]
FactOrigin = Literal["PROJECT", "CATALOG", "MASTER"]

ID_ORIGIN_ETS_ID: IdOrigin = "ETS_ID"
ID_ORIGIN_ETS_COMPOSITE: IdOrigin = "ETS_COMPOSITE"
ID_ORIGIN_STRUCTURAL_FALLBACK: IdOrigin = "STRUCTURAL_FALLBACK"

FACT_ORIGIN_PROJECT: FactOrigin = "PROJECT"
FACT_ORIGIN_CATALOG: FactOrigin = "CATALOG"
FACT_ORIGIN_MASTER: FactOrigin = "MASTER"

NODE_KINDS: tuple[str, ...] = (
    "installation",
    "area",
    "line",
    "space",
    "component",
    "communication_object",
    "group_address",
    "group_range",
    "parameter",
    "scene",
    "application_program",
)
RELATION_KINDS: tuple[str, ...] = ("membership", "placed_in")

COMPONENT_TYPES: tuple[str, ...] = (
    "IP_COUPLER_OR_INTERFACE",
    "COUPLER",
    "SENSOR",
    "ACTUATOR",
    "CONTROLLER",
    "UNTYPED",
)
RULE_CT0_OVERRIDE = "CT0_OVERRIDE"
RULE_CT1_IP = "CT1_IP"
RULE_CT2_COUPLER = "CT2_COUPLER"
RULE_CT3_NO_OBJECTS = "CT3_NO_OBJECTS"
RULE_CT4_DIRECTION = "CT4_DIRECTION"
TYPING_RULE_IDS: tuple[str, ...] = (
    RULE_CT0_OVERRIDE,
    RULE_CT1_IP,
    RULE_CT2_COUPLER,
    RULE_CT3_NO_OBJECTS,
    RULE_CT4_DIRECTION,
)

GROUP_ADDRESS_STYLES: tuple[str, ...] = ("ThreeLevel", "TwoLevel", "Free")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# -- warnings -----------------------------------------------------------------------------------
class ImportWarning(_Model):  # noqa: A001 - name fixed by the spec; contracts has the same-shaped model
    """One import warning: code, one-sentence message and location (zip entry or entry#ets-id)."""

    code: str
    message: str
    location: str


# -- nodes (source facts) -----------------------------------------------------------------------
class GraphNode(_Model):
    """Common node fields: stable ID, kind, id origin and provenance."""

    id: str
    kind: str
    id_origin: IdOrigin
    source_part: str
    source_locator: str
    fact_origin: FactOrigin


class InstallationNode(GraphNode):
    kind: Literal["installation"] = "installation"
    project_id: str | None = None
    project_name: str | None = None
    group_address_style: str | None = None
    default_line_id: str | None = None
    last_modified: str | None = None
    completion_status: str | None = None
    ets_tool_version: str | None = None
    created_by: str | None = None
    schema_namespace: str | None = None


class AreaNode(GraphNode):
    kind: Literal["area"] = "area"
    installation_id: str | None = None
    address: int | None = None
    name: str | None = None


class LineNode(GraphNode):
    kind: Literal["line"] = "line"
    area_id: str | None = None
    address: int | None = None
    name: str | None = None
    description: str | None = None
    medium_type_refs: list[str] = Field(default_factory=list)


class SpaceNode(GraphNode):
    kind: Literal["space"] = "space"
    parent_id: str | None = None
    space_type: str | None = None
    name: str | None = None
    usage_ref: str | None = None


class LoadState(_Model):
    """The five '...Loaded' booleans of a DeviceInstance (null when the attribute is absent)."""

    application_program_loaded: bool | None = None
    communication_part_loaded: bool | None = None
    individual_address_loaded: bool | None = None
    medium_config_loaded: bool | None = None
    parameters_loaded: bool | None = None


class ComponentNode(GraphNode):
    kind: Literal["component"] = "component"
    line_id: str | None = None
    segment_id: str | None = None
    medium_type_ref: str | None = None
    address: int | None = None
    individual_address: str | None = None
    name: str | None = None
    description: str | None = None
    comment: str | None = None
    product_ref_id: str | None = None
    hardware2program_ref_id: str | None = None
    application_program_id: str | None = None
    manufacturer_id: str | None = None
    product_text: str | None = None
    order_number: str | None = None
    has_ip_config: bool = False
    serial_number: str | None = None
    last_modified: str | None = None
    last_download: str | None = None
    load_state: LoadState = Field(default_factory=LoadState)


class CommunicationObjectNode(GraphNode):
    kind: Literal["communication_object"] = "communication_object"
    component_id: str | None = None
    ref_id: str | None = None
    object_number: int | None = None
    function_text: str | None = None
    text: str | None = None
    object_size: str | None = None
    read_flag: str | None = None
    write_flag: str | None = None
    communication_flag: str | None = None
    transmit_flag: str | None = None
    update_flag: str | None = None
    read_on_init_flag: str | None = None
    datapoint_types: list[str] = Field(default_factory=list)
    channel_id: str | None = None
    description: str | None = None
    instance_text: str | None = None
    definition_resolved: bool = False


class GroupAddressNode(GraphNode):
    kind: Literal["group_address"] = "group_address"
    address_raw: int | None = None
    address: str | None = None
    name: str | None = None
    description: str | None = None
    datapoint_type: str | None = None
    range_id: str | None = None


class GroupRangeNode(GraphNode):
    kind: Literal["group_range"] = "group_range"
    parent_id: str | None = None
    range_start: int | None = None
    range_end: int | None = None
    name: str | None = None
    description: str | None = None


class ParameterNode(GraphNode):
    kind: Literal["parameter"] = "parameter"
    component_id: str | None = None
    ref_id: str | None = None
    parameter_id: str | None = None
    name: str | None = None
    text: str | None = None
    parameter_type_id: str | None = None
    value: str | None = None
    definition_resolved: bool = False


class SceneNode(GraphNode):
    kind: Literal["scene"] = "scene"
    name: str | None = None
    scene_number: int | None = None
    members: list[str] = Field(default_factory=list)


class ApplicationProgramNode(GraphNode):
    kind: Literal["application_program"] = "application_program"
    manufacturer_id: str | None = None
    application_number: int | None = None
    application_version: int | None = None
    mask_version: str | None = None
    name: str | None = None
    source_loaded: bool = False


Node = Annotated[
    InstallationNode
    | AreaNode
    | LineNode
    | SpaceNode
    | ComponentNode
    | CommunicationObjectNode
    | GroupAddressNode
    | GroupRangeNode
    | ParameterNode
    | SceneNode
    | ApplicationProgramNode,
    Field(discriminator="kind"),
]

NODE_CLASSES: dict[str, type[GraphNode]] = {
    "installation": InstallationNode,
    "area": AreaNode,
    "line": LineNode,
    "space": SpaceNode,
    "component": ComponentNode,
    "communication_object": CommunicationObjectNode,
    "group_address": GroupAddressNode,
    "group_range": GroupRangeNode,
    "parameter": ParameterNode,
    "scene": SceneNode,
    "application_program": ApplicationProgramNode,
}


# -- relations (source facts) -------------------------------------------------------------------
class MembershipRelation(_Model):
    """A communication object is linked to a group address; ``order`` is the 0-based position in Links."""

    communication_object_id: str
    group_address_id: str
    order: int


class PlacedInRelation(_Model):
    """A component is placed in a space (Space/DeviceInstanceRef)."""

    space_id: str
    component_id: str


class Relations(_Model):
    membership: list[MembershipRelation] = Field(default_factory=list)
    placed_in: list[PlacedInRelation] = Field(default_factory=list)


class SourceFacts(_Model):
    nodes: list[Node] = Field(default_factory=list)
    relations: Relations = Field(default_factory=Relations)


# -- derived facts ------------------------------------------------------------------------------
class ComponentTypingBasis(_Model):
    """Inputs of a component typing decision (always all fields)."""

    product_ref_id: str | None = None
    application_program_id: str | None = None
    receive_object_count: int = 0  # R: objects with write_flag Enabled
    transmit_object_count: int = 0  # T: objects with transmit_flag Enabled
    object_count: int = 0
    datapoint_main_types: list[str] = Field(default_factory=list)


class ComponentTyping(_Model):
    component_type: str
    rule_id: str
    basis: ComponentTypingBasis


class MembershipIndex(_Model):
    group_address_to_communication_objects: dict[str, list[str]] = Field(default_factory=dict)
    component_to_group_addresses: dict[str, list[str]] = Field(default_factory=dict)


class DerivedCounts(_Model):
    component_type_counts: dict[str, int] = Field(default_factory=dict)


class DerivedFacts(_Model):
    component_typing: dict[str, ComponentTyping] = Field(default_factory=dict)
    membership_index: MembershipIndex = Field(default_factory=MembershipIndex)
    derived_counts: DerivedCounts = Field(default_factory=DerivedCounts)


class ProjectGraph(_Model):
    """The project graph: source facts, derived facts, warnings, fingerprint and schema version."""

    graph_schema_version: int = GRAPH_SCHEMA_VERSION
    fingerprint: str | None = None
    source_facts: SourceFacts = Field(default_factory=SourceFacts)
    derived_facts: DerivedFacts = Field(default_factory=DerivedFacts)
    warnings: list[ImportWarning] = Field(default_factory=list)

    def nodes_of(self, kind: str) -> list[GraphNode]:
        """Source nodes of one kind in stored order."""
        return [node for node in self.source_facts.nodes if node.kind == kind]

    def node_index(self) -> dict[str, GraphNode]:
        """Source nodes by stable ID."""
        return {node.id: node for node in self.source_facts.nodes}


# -- stable ID helpers (rules 1-6 of 003 'Stable ID rules') -------------------------------------
@dataclass(frozen=True)
class StableId:
    """A stable ID and how it was obtained."""

    id: str
    origin: IdOrigin


def ets_id(value: str) -> StableId:
    """Rule 1: the ETS Id attribute value as is."""
    return StableId(value, ID_ORIGIN_ETS_ID)


def installation_id(project_folder_id: str, installation_file_stem: str) -> StableId:
    """Rule 2: '<project folder id>-<installation file stem>', for example P-051B-0."""
    return StableId(f"{project_folder_id}-{installation_file_stem}", ID_ORIGIN_ETS_COMPOSITE)


def communication_object_id(component_id: str, ref_id: str) -> StableId:
    """Rule 3: '<component id>/co/<RefId>'."""
    return StableId(f"{component_id}/co/{ref_id}", ID_ORIGIN_ETS_COMPOSITE)


def parameter_node_id(component_id: str, ref_id: str) -> StableId:
    """Rule 3: '<component id>/pa/<RefId>'."""
    return StableId(f"{component_id}/pa/{ref_id}", ID_ORIGIN_ETS_COMPOSITE)


def application_program_node_id(application_program_ref_id: str) -> StableId:
    """Rule 3: the ApplicationProgramRef RefId."""
    return StableId(application_program_ref_id, ID_ORIGIN_ETS_COMPOSITE)


def structural_key(address: object | None, name: str | None, position: int) -> str:
    """Rule 4 key: the Address if present, else the Name, else the 0-based position among same-kind siblings."""
    if address is not None and str(address) != "":
        return str(address)
    if name:
        return name
    return str(position)


def structural_fallback_id(parent_id: str, kind: str, key: str) -> StableId:
    """Rule 4: 's:' + parent id + '/' + kind + '[' + key + ']'."""
    return StableId(f"s:{parent_id}/{kind}[{key}]", ID_ORIGIN_STRUCTURAL_FALLBACK)


class IdAllocator:
    """Rule 5: hands out unique IDs; a repeated ID gets the suffix ~2, ~3, ... (first claim keeps the plain ID)."""

    def __init__(self) -> None:
        self._claimed: set[str] = set()
        self._next_suffix: dict[str, int] = {}

    def claim(self, stable: StableId) -> tuple[StableId, bool]:
        """Return (unique ID, collided). ``collided`` is true when a suffix had to be added."""
        if stable.id not in self._claimed:
            self._claimed.add(stable.id)
            return stable, False
        number = self._next_suffix.get(stable.id, 2)
        while f"{stable.id}~{number}" in self._claimed:
            number += 1
        self._next_suffix[stable.id] = number + 1
        unique = f"{stable.id}~{number}"
        self._claimed.add(unique)
        return StableId(unique, stable.origin), True


def node_sort_key(node: GraphNode) -> tuple[str, str]:
    """Rule 6: nodes are ordered by (kind, id)."""
    return (node.kind, node.id)


def sort_nodes(nodes: list[GraphNode]) -> list[GraphNode]:
    """Deterministic node order (rule 6)."""
    return sorted(nodes, key=node_sort_key)


def membership_sort_key(relation: MembershipRelation) -> tuple[str, int, str]:
    return (relation.communication_object_id, relation.order, relation.group_address_id)


def placed_in_sort_key(relation: PlacedInRelation) -> tuple[str, str]:
    return (relation.space_id, relation.component_id)


# -- group address text -------------------------------------------------------------------------
def format_group_address(raw: int, style: str | None) -> str:
    """Group address text: ThreeLevel 'main/middle/sub', TwoLevel 'main/sub', Free the plain number."""
    if style == "TwoLevel":
        return f"{(raw >> 11) & 0x1F}/{raw & 0x7FF}"
    if style == "Free":
        return str(raw)
    return f"{(raw >> 11) & 0x1F}/{(raw >> 8) & 0x07}/{raw & 0xFF}"


def individual_address_text(area: int | None, line: int | None, device: int | None) -> str | None:
    """'area.line.device' or None when a part is unknown."""
    if area is None or line is None or device is None:
        return None
    return f"{area}.{line}.{device}"
