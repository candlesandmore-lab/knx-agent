"""Contracts of the component inspection capabilities 6-9 (story 05).

One contract class per detail level (SUMMARY -> MEDIUM -> FULL, each extending the previous), so that the JSON of a
level contains exactly the fields of that level: fields of a higher level are ABSENT, never ``null``. The response
models hold the level-dependent parts as a union wrapped in ``SerializeAsAny``; ``extra="forbid"`` makes the union
resolve to the class of the level when a JSON document is parsed again. No purpose fields exist (todo 14).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny

from .errors import (
    INVALID_DETAIL_LEVEL,
    INVALID_REQUEST,
    REASON_SELECTOR_KIND_UNKNOWN,
    error,
)
from .models import DetailLevel, ResponseEnvelope


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SelectorKind(StrEnum):
    """Kind of a component selector value (C3). ``ANY`` auto-detects."""

    ANY = "ANY"
    NAME = "NAME"
    INSTANCE_PATH = "INSTANCE_PATH"
    INDIVIDUAL_ADDRESS = "INDIVIDUAL_ADDRESS"
    ETS_ID = "ETS_ID"


# Kinds that can appear in ``match_kinds`` (ANY never does), in sorted order.
MATCH_KIND_VALUES: tuple[str, ...] = ("ETS_ID", "INDIVIDUAL_ADDRESS", "INSTANCE_PATH", "NAME")
DIRECTION_LABELS: tuple[str, ...] = ("SENDER", "RECEIVER", "SENDER_RECEIVER", "UNDETERMINED")
FLOW_ROLES: tuple[str, ...] = ("ACCEPTS_UPDATE", "ACCEPTS_WRITE", "ANSWERS_READ", "TRANSMITS")
CURRENT_VALUE_UNKNOWN = "unknown"
PROPAGATION_SCOPE = "DIRECT_PARTICIPANTS"

DirectionLabel = Literal["SENDER", "RECEIVER", "SENDER_RECEIVER", "UNDETERMINED"]


# -- requests (all values are plain strings; the core validates them) --------------------------------
class ListComponentsRequest(_Model):
    session_label: str
    component_selector: str | None = None
    selector_kind: str | None = None
    detail_level: str | None = None
    mutation_name: str | None = None


class DescribeComponentRequest(_Model):
    session_label: str
    component_selector: str | None = None
    selector_kind: str | None = None
    detail_level: str | None = None
    mutation_name: str | None = None


class SummarizeTopologyRequest(_Model):
    session_label: str
    detail_level: str | None = None
    mutation_name: str | None = None


class TraceGroupFlowRequest(_Model):
    session_label: str
    group_address_selector: str | None = None
    communication_object_ref: str | None = None
    detail_level: str | None = None
    mutation_name: str | None = None


# -- component view blocks ----------------------------------------------------------------------------
class AreaRef(_Model):
    ets_id: str
    address: int | None = None
    name: str | None = None


class LineRef(_Model):
    ets_id: str
    address: int | None = None
    address_text: str | None = None
    name: str | None = None


class LocationRef(_Model):
    ets_id: str
    name: str | None = None
    space_type: str | None = None


class ComponentIdentity(_Model):
    name: str | None = None
    individual_address: str | None = None
    ets_id: str
    instance_path: str | None = None
    other_instance_paths: list[str] = Field(default_factory=list)


class TypingBasisView(_Model):
    product_ref_id: str | None = None
    application_program_id: str | None = None
    receive_object_count: int = 0
    transmit_object_count: int = 0
    object_count: int = 0
    datapoint_main_types: list[str] = Field(default_factory=list)


class ComponentDerived(_Model):
    """Derived facts (never mixed into ``identity``); labelled by ``fact_kind``."""

    fact_kind: Literal["DERIVED"] = "DERIVED"
    component_type: str


class ComponentDerivedFull(ComponentDerived):
    typing_rule_id: str
    typing_basis: TypingBasisView


class ComponentTopology(_Model):
    area: AreaRef | None = None
    line: LineRef | None = None
    location_path: list[LocationRef] = Field(default_factory=list)


class ComponentParameter(_Model):
    parameter_ref_id: str | None = None
    name: str | None = None
    text: str | None = None
    value: str | None = None
    definition_resolved: bool = False


class ComponentParameterFull(ComponentParameter):
    parameter_type_id: str | None = None


class GroupAddressRef(_Model):
    ets_id: str
    address: str | None = None
    name: str | None = None
    datapoint_type: str | None = None


class LinkedGroupAddress(GroupAddressRef):
    link_order: int


class ObjectFlags(_Model):
    """The six ETS flags as stored (``Enabled`` / ``Disabled`` / null when the definition is unresolved)."""

    read: str | None = None
    write: str | None = None
    communication: str | None = None
    transmit: str | None = None
    update: str | None = None
    read_on_init: str | None = None


class CommunicationObjectView(_Model):
    ets_id: str
    ref_id: str | None = None
    object_number: int | None = None
    label: str | None = None
    function_text: str | None = None
    text: str | None = None
    instance_text: str | None = None
    description: str | None = None
    object_size: str | None = None
    flags: ObjectFlags
    datapoint_types: list[str] = Field(default_factory=list)
    definition_resolved: bool = False
    group_addresses: list[LinkedGroupAddress] = Field(default_factory=list)


class ProductView(_Model):
    product_ref_id: str | None = None
    product_text: str | None = None
    order_number: str | None = None
    manufacturer_id: str | None = None
    hardware2program_ref_id: str | None = None


class ApplicationView(_Model):
    application_program_id: str | None = None
    application_number: int | None = None
    application_version: int | None = None
    mask_version: str | None = None
    name: str | None = None
    source_loaded: bool | None = None


class LoadStateView(_Model):
    application_program_loaded: bool | None = None
    communication_part_loaded: bool | None = None
    individual_address_loaded: bool | None = None
    medium_config_loaded: bool | None = None
    parameters_loaded: bool | None = None


class EngineeringMetadata(_Model):
    description: str | None = None
    comment: str | None = None
    serial_number: str | None = None
    medium_type_ref: str | None = None
    has_ip_config: bool = False
    last_modified: str | None = None
    last_download: str | None = None
    load_state: LoadStateView = Field(default_factory=LoadStateView)


# -- component views per detail level -----------------------------------------------------------------
class ComponentSummaryView(_Model):
    """SUMMARY: identity, derived component type and (only when a selector was given) match_kinds."""

    identity: ComponentIdentity
    derived: ComponentDerived
    match_kinds: list[str] | None = Field(default=None, exclude_if=lambda value: value is None)


class ComponentMediumView(ComponentSummaryView):
    """MEDIUM adds topology and component parameters."""

    topology: ComponentTopology
    component_parameters: list[ComponentParameter] = Field(default_factory=list)


class ComponentFullView(ComponentMediumView):
    """FULL adds typing details, group addresses, communication objects, product, application and metadata."""

    derived: ComponentDerivedFull
    component_parameters: list[ComponentParameterFull] = Field(default_factory=list)
    group_addresses: list[GroupAddressRef] = Field(default_factory=list)
    communication_objects: list[CommunicationObjectView] = Field(default_factory=list)
    product: ProductView
    application: ApplicationView
    engineering_metadata: EngineeringMetadata


ComponentViewAny = SerializeAsAny[ComponentFullView | ComponentMediumView | ComponentSummaryView]


class ListComponentsResponse(_Model):
    matches: list[ComponentViewAny] = Field(default_factory=list)
    match_count: int = 0
    ambiguous: bool = False
    envelope: ResponseEnvelope


class DescribeComponentResponse(_Model):
    components: list[ComponentViewAny] = Field(default_factory=list)
    match_count: int = 0
    ambiguous: bool = False
    envelope: ResponseEnvelope


# -- topology -----------------------------------------------------------------------------------------
class ComponentCounts(_Model):
    total: int = 0
    placed: int = 0
    unplaced: int = 0
    by_component_type: dict[str, int] = Field(default_factory=dict)


class TopologyCounts(_Model):
    areas: int = 0
    lines: int = 0
    locations: int = 0


class ComponentListItem(_Model):
    ets_id: str
    name: str | None = None
    individual_address: str | None = None


class LineEntry(_Model):
    ets_id: str
    address: int | None = None
    address_text: str | None = None
    name: str | None = None
    component_count: int = 0


class LineEntryFull(LineEntry):
    components: list[ComponentListItem] = Field(default_factory=list)


class AreaEntry(_Model):
    ets_id: str
    address: int | None = None
    name: str | None = None
    component_count: int = 0
    lines: list[LineEntry] = Field(default_factory=list)


class AreaEntryFull(AreaEntry):
    lines: list[LineEntryFull] = Field(default_factory=list)


class LocationEntry(_Model):
    ets_id: str
    name: str | None = None
    space_type: str | None = None
    path: str
    depth: int
    component_count: int = 0
    component_count_total: int = 0


class LocationEntryFull(LocationEntry):
    components: list[ComponentListItem] = Field(default_factory=list)


class TopologySummaryBasic(_Model):
    """SUMMARY: counts and the distribution of locations by type."""

    counts: TopologyCounts
    locations_by_type: dict[str, int] = Field(default_factory=dict)


class TopologySummaryMedium(TopologySummaryBasic):
    # Level fields are required (no defaults) so that parsing a JSON document picks the class of its level.
    areas: list[AreaEntry]
    locations: list[LocationEntry]
    unplaced_component_count: int
    unassigned_to_line: int


class TopologySummaryFull(TopologySummaryMedium):
    areas: list[AreaEntryFull]
    locations: list[LocationEntryFull]
    unplaced_components: list[ComponentListItem]
    unassigned_components: list[ComponentListItem]


class SummarizeTopologyResponse(_Model):
    topology_summary: SerializeAsAny[TopologySummaryFull | TopologySummaryMedium | TopologySummaryBasic]
    component_counts: ComponentCounts
    envelope: ResponseEnvelope


# -- group address flow -------------------------------------------------------------------------------
class FlowGroupAddressSummary(_Model):
    ets_id: str
    address: str | None = None
    name: str | None = None


class FlowGroupAddressMedium(FlowGroupAddressSummary):
    datapoint_type: str | None  # required (nullable): see TopologySummaryMedium
    description: str | None


class FlowGroupAddressFull(FlowGroupAddressMedium):
    address_raw: int | None
    range_id: str | None
    range_path: list[str]


class FlowComponentSummary(_Model):
    ets_id: str
    name: str | None = None
    individual_address: str | None = None


class FlowComponentMedium(FlowComponentSummary):
    instance_path: str | None = None
    component_type: str | None = None


class FlowObjectMedium(_Model):
    ets_id: str
    object_number: int | None = None
    label: str | None = None
    datapoint_types: list[str] = Field(default_factory=list)


class FlowObjectFull(FlowObjectMedium):
    function_text: str | None = None
    text: str | None = None
    instance_text: str | None = None
    description: str | None = None
    object_size: str | None = None
    flags: ObjectFlags
    definition_resolved: bool = False


class FlowParticipantSummary(_Model):
    component: FlowComponentSummary
    direction: DirectionLabel


class FlowParticipantMedium(FlowParticipantSummary):
    component: FlowComponentMedium
    communication_object: FlowObjectMedium
    roles: list[str] = Field(default_factory=list)


class FlowParticipantFull(FlowParticipantMedium):
    communication_object: FlowObjectFull
    link_order: int


class PropagationPath(_Model):
    scope: Literal["DIRECT_PARTICIPANTS"] = "DIRECT_PARTICIPANTS"
    senders: list[str] = Field(default_factory=list)
    receivers: list[str] = Field(default_factory=list)


class UnresolvedLinkSummary(_Model):
    code: str
    communication_object_id: str
    component_id: str | None = None


class UnresolvedLinkMedium(UnresolvedLinkSummary):
    message: str
    location: str


class FlowEntrySummary(_Model):
    group_address: FlowGroupAddressSummary
    participants: list[FlowParticipantSummary] = Field(default_factory=list)
    propagation_path: PropagationPath
    unresolved_links: list[UnresolvedLinkSummary] = Field(default_factory=list)
    current_value: Literal["unknown"] = "unknown"


class FlowEntryMedium(FlowEntrySummary):
    group_address: FlowGroupAddressMedium
    participants: list[FlowParticipantMedium] = Field(default_factory=list)
    unresolved_links: list[UnresolvedLinkMedium] = Field(default_factory=list)


class FlowEntryFull(FlowEntryMedium):
    group_address: FlowGroupAddressFull
    participants: list[FlowParticipantFull] = Field(default_factory=list)


FlowEntryAny = SerializeAsAny[FlowEntryFull | FlowEntryMedium | FlowEntrySummary]


class TraceGroupFlowResponse(_Model):
    group_addresses: list[FlowEntryAny] = Field(default_factory=list)
    match_count: int = 0
    ambiguous: bool = False
    envelope: ResponseEnvelope


# -- parsing helpers ----------------------------------------------------------------------------------
def parse_detail_level(value: object) -> DetailLevel:
    """Case-insensitive detail level; ``None`` is the default MEDIUM, anything else invalid is INVALID_DETAIL_LEVEL."""
    if value is None:
        return DetailLevel.MEDIUM
    if isinstance(value, DetailLevel):
        return value
    try:
        return DetailLevel(str(value).upper())
    except ValueError as exc:
        allowed = [level.value for level in DetailLevel]
        raise error(
            INVALID_DETAIL_LEVEL,
            f"detail_level must be one of {', '.join(allowed)}, got {value!r}.",
            allowed=allowed,
            detail_level=str(value),
        ) from exc


def parse_selector_kind(value: object) -> SelectorKind:
    """Case-insensitive selector kind; ``None`` is ANY, an unknown value is INVALID_REQUEST (SELECTOR_KIND_UNKNOWN)."""
    if value is None:
        return SelectorKind.ANY
    if isinstance(value, SelectorKind):
        return value
    try:
        return SelectorKind(str(value).upper())
    except ValueError as exc:
        allowed = [kind.value for kind in SelectorKind]
        raise error(
            INVALID_REQUEST,
            f"selector_kind must be one of {', '.join(allowed)}, got {value!r}.",
            reason=REASON_SELECTOR_KIND_UNKNOWN,
            allowed=allowed,
            selector_kind=str(value),
        ) from exc
