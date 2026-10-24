"""Component view model and detail level projections; list/describe assembly (story 05).

One internal ``ComponentView`` holds the blocks needed for a level; SUMMARY, MEDIUM and FULL are projections to the
contract classes (``ComponentSummaryView`` -> ``ComponentMediumView`` -> ``ComponentFullView``). Higher-level fields
are absent from the lower-level class, not null. Derived facts only live in the ``derived`` block. Pure, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from knx_agent.contracts import (
    INVALID_REQUEST,
    REASON_SELECTOR_KIND_WITHOUT_SELECTOR,
    REASON_SELECTOR_MISSING,
    SELECTOR_UNRESOLVED,
    ApplicationView,
    AreaRef,
    CommunicationObjectView,
    ComponentDerived,
    ComponentDerivedFull,
    ComponentFullView,
    ComponentIdentity,
    ComponentMediumView,
    ComponentParameter,
    ComponentParameterFull,
    ComponentSummaryView,
    ComponentTopology,
    DetailLevel,
    EngineeringMetadata,
    GroupAddressRef,
    LineRef,
    LinkedGroupAddress,
    LoadStateView,
    LocationRef,
    ObjectFlags,
    ProductView,
    SelectorKind,
    TypingBasisView,
    error,
)

from .derivation import classify_component
from .graph_index import GraphIndex
from .project_graph import CommunicationObjectNode, ComponentNode, ComponentTyping
from .selectors import ComponentMatch, evaluated_kinds, match_components, require_kind_fits, strip_selector

NOTE_COMPONENT_TYPE = "Component type is a derived fact (coarse rule-based typing), not a project fact."
NOTE_RAW_PARAMETERS = "Parameter values are raw ETS strings; they are not interpreted through parameter types."
NO_LOCATIONS_NOTE = "The project encodes no locations; instance_path is absent for all components."

ComponentViewType = ComponentSummaryView | ComponentMediumView | ComponentFullView


def unresolved_note(parameters: int, objects: int) -> str:
    return (
        f"{parameters} parameters and {objects} communication objects of the returned components "
        "have unresolved definitions (see the import warnings)."
    )


def unplaced_note(count: int) -> str:
    return f"{count} returned components are not placed in a location and have no instance_path."


def object_label(obj: CommunicationObjectNode) -> str | None:
    """First non-empty of instance_text, text, function_text."""
    return obj.instance_text or obj.text or obj.function_text or None


@dataclass
class ComponentView:
    """All blocks of one component that the requested level needs (None/empty = not computed for the level)."""

    identity: ComponentIdentity
    derived: ComponentDerivedFull
    match_kinds: list[str] | None = None
    topology: ComponentTopology | None = None
    parameters: list[ComponentParameterFull] = field(default_factory=list)
    group_addresses: list[GroupAddressRef] = field(default_factory=list)
    communication_objects: list[CommunicationObjectView] = field(default_factory=list)
    product: ProductView | None = None
    application: ApplicationView | None = None
    engineering_metadata: EngineeringMetadata | None = None

    def project(self, level: DetailLevel) -> ComponentViewType:
        """The contract view of ``level`` (blocks beyond the level are not part of the class)."""
        derived = ComponentDerived(component_type=self.derived.component_type)
        if level is DetailLevel.SUMMARY:
            return ComponentSummaryView(identity=self.identity, derived=derived, match_kinds=self.match_kinds)
        assert self.topology is not None
        if level is DetailLevel.MEDIUM:
            return ComponentMediumView(
                identity=self.identity,
                derived=derived,
                match_kinds=self.match_kinds,
                topology=self.topology,
                component_parameters=[
                    ComponentParameter(**p.model_dump(exclude={"parameter_type_id"})) for p in self.parameters
                ],
            )
        assert self.product is not None and self.application is not None and self.engineering_metadata is not None
        return ComponentFullView(
            identity=self.identity,
            derived=self.derived,
            match_kinds=self.match_kinds,
            topology=self.topology,
            component_parameters=self.parameters,
            group_addresses=self.group_addresses,
            communication_objects=self.communication_objects,
            product=self.product,
            application=self.application,
            engineering_metadata=self.engineering_metadata,
        )


# -- block builders ------------------------------------------------------------------------------------
def _typing(index: GraphIndex, component: ComponentNode) -> ComponentTyping:
    typing = index.typing.get(component.id)
    if typing is None:  # a graph without derived facts for this component: derive it on the fly
        typing = classify_component(component, index.objects_by_component.get(component.id, []))
    return typing


def _identity(index: GraphIndex, component: ComponentNode) -> ComponentIdentity:
    paths = index.instance_paths(component.id)
    return ComponentIdentity(
        name=component.name or None,
        individual_address=component.individual_address,
        ets_id=component.id,
        instance_path=paths[0] if paths else None,
        other_instance_paths=paths[1:],
    )


def _derived(index: GraphIndex, component: ComponentNode) -> ComponentDerivedFull:
    typing = _typing(index, component)
    return ComponentDerivedFull(
        component_type=typing.component_type,
        typing_rule_id=typing.rule_id,
        typing_basis=TypingBasisView(**typing.basis.model_dump()),
    )


def _topology(index: GraphIndex, component: ComponentNode) -> ComponentTopology:
    area = index.component_area(component)
    line = index.component_line(component)
    address_text = None
    if area is not None and line is not None and area.address is not None and line.address is not None:
        address_text = f"{area.address}.{line.address}"
    return ComponentTopology(
        area=AreaRef(ets_id=area.id, address=area.address, name=area.name) if area is not None else None,
        line=(
            LineRef(ets_id=line.id, address=line.address, address_text=address_text, name=line.name)
            if line is not None
            else None
        ),
        location_path=[
            LocationRef(ets_id=s.id, name=s.name, space_type=s.space_type) for s in index.location_path(component.id)
        ],
    )


def _parameters(index: GraphIndex, component: ComponentNode) -> list[ComponentParameterFull]:
    return [
        ComponentParameterFull(
            parameter_ref_id=p.ref_id,
            name=p.name,
            text=p.text,
            value=p.value,
            definition_resolved=p.definition_resolved,
            parameter_type_id=p.parameter_type_id,
        )
        for p in index.parameters_by_component.get(component.id, [])
    ]


def _linked_group_addresses(index: GraphIndex, obj: CommunicationObjectNode) -> list[LinkedGroupAddress]:
    linked = []
    for relation in index.memberships_by_object.get(obj.id, []):
        ga = index.group_address_by_id.get(relation.group_address_id)
        if ga is not None:
            linked.append(
                (
                    relation.order,
                    ga.address_raw if ga.address_raw is not None else 1 << 30,
                    LinkedGroupAddress(
                        ets_id=ga.id, address=ga.address, name=ga.name, datapoint_type=ga.datapoint_type,
                        link_order=relation.order,
                    ),
                )
            )
    return [item for _order, _raw, item in sorted(linked, key=lambda entry: (entry[0], entry[1]))]


def _communication_objects(index: GraphIndex, component: ComponentNode) -> list[CommunicationObjectView]:
    return [
        CommunicationObjectView(
            ets_id=obj.id,
            ref_id=obj.ref_id,
            object_number=obj.object_number,
            label=object_label(obj),
            function_text=obj.function_text,
            text=obj.text,
            instance_text=obj.instance_text,
            description=obj.description,
            object_size=obj.object_size,
            flags=object_flags(obj),
            datapoint_types=list(obj.datapoint_types),
            definition_resolved=obj.definition_resolved,
            group_addresses=_linked_group_addresses(index, obj),
        )
        for obj in index.objects_by_component.get(component.id, [])
    ]


def object_flags(obj: CommunicationObjectNode) -> ObjectFlags:
    return ObjectFlags(
        read=obj.read_flag,
        write=obj.write_flag,
        communication=obj.communication_flag,
        transmit=obj.transmit_flag,
        update=obj.update_flag,
        read_on_init=obj.read_on_init_flag,
    )


def _component_group_addresses(index: GraphIndex, component: ComponentNode) -> list[GroupAddressRef]:
    seen: dict[str, GroupAddressRef] = {}
    for obj in index.objects_by_component.get(component.id, []):
        for relation in index.memberships_by_object.get(obj.id, []):
            ga = index.group_address_by_id.get(relation.group_address_id)
            if ga is not None and ga.id not in seen:
                seen[ga.id] = GroupAddressRef(ets_id=ga.id, address=ga.address, name=ga.name, datapoint_type=ga.datapoint_type)
    ordered = sorted(seen, key=lambda ga_id: (index.group_address_by_id[ga_id].address_raw if index.group_address_by_id[ga_id].address_raw is not None else 1 << 30, ga_id))
    return [seen[ga_id] for ga_id in ordered]


def _application(index: GraphIndex, component: ComponentNode) -> ApplicationView:
    program = index.program_by_id.get(component.application_program_id) if component.application_program_id else None
    if program is None:
        return ApplicationView(application_program_id=component.application_program_id)
    return ApplicationView(
        application_program_id=component.application_program_id,
        application_number=program.application_number,
        application_version=program.application_version,
        mask_version=program.mask_version,
        name=program.name,
        source_loaded=program.source_loaded,
    )


def build_view(
    index: GraphIndex, component: ComponentNode, level: DetailLevel, match_kinds: tuple[str, ...] | None = None
) -> ComponentView:
    """The internal view of one component with the blocks required by ``level``."""
    view = ComponentView(
        identity=_identity(index, component),
        derived=_derived(index, component),
        match_kinds=list(match_kinds) if match_kinds is not None else None,
    )
    if level is DetailLevel.SUMMARY:
        return view
    view.topology = _topology(index, component)
    view.parameters = _parameters(index, component)
    if level is DetailLevel.MEDIUM:
        return view
    view.group_addresses = _component_group_addresses(index, component)
    view.communication_objects = _communication_objects(index, component)
    view.product = ProductView(
        product_ref_id=component.product_ref_id,
        product_text=component.product_text,
        order_number=component.order_number,
        manufacturer_id=component.manufacturer_id,
        hardware2program_ref_id=component.hardware2program_ref_id,
    )
    view.application = _application(index, component)
    load = component.load_state
    view.engineering_metadata = EngineeringMetadata(
        description=component.description,
        comment=component.comment,
        serial_number=component.serial_number,
        medium_type_ref=component.medium_type_ref,
        has_ip_config=component.has_ip_config,
        last_modified=component.last_modified,
        last_download=component.last_download,
        load_state=LoadStateView(**load.model_dump()),
    )
    return view


# -- limitation notes ----------------------------------------------------------------------------------
def component_notes(index: GraphIndex, components: list[ComponentNode], level: DetailLevel) -> list[str]:
    """Limitation notes for list/describe results (exact sentences of 003)."""
    notes = [NOTE_COMPONENT_TYPE]
    if level is not DetailLevel.SUMMARY:
        if any(index.parameters_by_component.get(c.id) for c in components):
            notes.append(NOTE_RAW_PARAMETERS)
        parameters = sum(
            1 for c in components for p in index.parameters_by_component.get(c.id, []) if not p.definition_resolved
        )
        objects = sum(
            1 for c in components for o in index.objects_by_component.get(c.id, []) if not o.definition_resolved
        )
        if parameters or objects:
            notes.append(unresolved_note(parameters, objects))
    unplaced = sum(1 for c in components if not index.is_placed(c.id))
    if unplaced:
        notes.append(unplaced_note(unplaced))
    if not index.has_locations:
        notes.append(NO_LOCATIONS_NOTE)
    return notes


# -- list / describe -----------------------------------------------------------------------------------
@dataclass(frozen=True)
class ComponentQueryResult:
    views: list[ComponentViewType]
    match_count: int
    ambiguous: bool
    limitation_notes: list[str]


def _assemble(index: GraphIndex, matches: list[ComponentMatch], level: DetailLevel, with_kinds: bool, selector_given: bool) -> ComponentQueryResult:
    views = [
        build_view(index, m.component, level, m.match_kinds if with_kinds else None).project(level) for m in matches
    ]
    components = [m.component for m in matches]
    return ComponentQueryResult(
        views=views,
        match_count=len(views),
        ambiguous=selector_given and len(views) > 1,
        limitation_notes=component_notes(index, components, level),
    )


def validate_list_request(selector: str | None, kind: SelectorKind | None) -> str | None:
    """Request rules of list_components; returns the stripped selector (None = broad listing)."""
    if selector is None:
        if kind is not None:
            raise error(
                INVALID_REQUEST,
                "selector_kind was given without a component_selector.",
                reason=REASON_SELECTOR_KIND_WITHOUT_SELECTOR,
                selector_kind=kind.value,
            )
        return None
    value = strip_selector(selector)
    require_kind_fits(value, kind or SelectorKind.ANY)
    return value


def validate_describe_request(selector: str | None, kind: SelectorKind | None) -> str:
    """Request rules of describe_component; returns the stripped selector."""
    if selector is None:
        raise error(INVALID_REQUEST, "component_selector is required.", reason=REASON_SELECTOR_MISSING)
    value = strip_selector(selector)
    require_kind_fits(value, kind or SelectorKind.ANY)
    return value


def list_components(
    index: GraphIndex, selector: str | None, kind: SelectorKind | None, level: DetailLevel
) -> ComponentQueryResult:
    """list_components: no selector lists all components; ``kind`` None means "not given"."""
    value = validate_list_request(selector, kind)
    if value is None:
        everything = [ComponentMatch(c, ()) for c in index.components]
        return _assemble(index, everything, level, with_kinds=False, selector_given=False)
    matches = match_components(index, value, kind or SelectorKind.ANY)
    return _assemble(index, matches, level, with_kinds=True, selector_given=True)


def describe_components(
    index: GraphIndex, selector: str | None, kind: SelectorKind | None, level: DetailLevel
) -> ComponentQueryResult:
    """describe_component: a selector is required; no match is SELECTOR_UNRESOLVED."""
    value = validate_describe_request(selector, kind)
    effective = kind or SelectorKind.ANY
    matches = match_components(index, value, effective)
    if not matches:
        raise error(
            SELECTOR_UNRESOLVED,
            f"No component matches {value!r} (selector_kind {effective.value}).",
            selector=value,
            selector_kind=effective.value,
            evaluated_kinds=evaluated_kinds(value, effective),
        )
    return _assemble(index, matches, level, with_kinds=True, selector_given=True)
