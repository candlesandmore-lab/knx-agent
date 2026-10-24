"""Derived facts (story 04, T7): component typing, membership indexes, derived counts. Pure, no I/O.

Source facts are never modified. ``overrides`` (rule CT0) is a function parameter, empty by default; only tests
inject entries. It is never read from a file, the environment or the project and never persisted.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from .project_graph import (
    RULE_CT0_OVERRIDE,
    RULE_CT1_IP,
    RULE_CT2_COUPLER,
    RULE_CT3_NO_OBJECTS,
    RULE_CT4_DIRECTION,
    CommunicationObjectNode,
    ComponentNode,
    ComponentTyping,
    ComponentTypingBasis,
    DerivedCounts,
    DerivedFacts,
    MembershipIndex,
    SourceFacts,
)

ENABLED = "Enabled"
MEDIUM_IP = "MT-5"
OVERRIDE_KEYS: tuple[str, ...] = ("product_ref_id", "hardware2program_ref_id", "application_program_id")

_DPT_MAIN = re.compile(r"^DP(?:ST|T)-(\d+)(?:-\d+)?$")  # DPT-<n> or DPST-<n>-<m>


@dataclass(frozen=True)
class TypeOverride:
    """One entry of the curated override table: exact match of one component field -> component type."""

    match: str  # one of OVERRIDE_KEYS
    value: str
    component_type: str

    def __post_init__(self) -> None:
        if self.match not in OVERRIDE_KEYS:
            raise ValueError(f"override match must be one of {OVERRIDE_KEYS}, got {self.match!r}")


def datapoint_main_types(objects: Sequence[CommunicationObjectNode]) -> list[str]:
    """Sorted unique main numbers (numeric order) parsed from the objects' datapoint type ids."""
    numbers = set()
    for obj in objects:
        for token in obj.datapoint_types:
            match = _DPT_MAIN.match(token.strip())
            if match:
                numbers.add(int(match.group(1)))
    return [str(number) for number in sorted(numbers)]


def _basis(component: ComponentNode, objects: Sequence[CommunicationObjectNode]) -> ComponentTypingBasis:
    resolved = [obj for obj in objects if obj.definition_resolved]
    return ComponentTypingBasis(
        product_ref_id=component.product_ref_id,
        application_program_id=component.application_program_id,
        receive_object_count=sum(1 for obj in resolved if obj.write_flag == ENABLED),
        transmit_object_count=sum(1 for obj in resolved if obj.transmit_flag == ENABLED),
        object_count=len(objects),
        datapoint_main_types=datapoint_main_types(objects),
    )


def classify_component(
    component: ComponentNode,
    objects: Sequence[CommunicationObjectNode],
    overrides: Sequence[TypeOverride] = (),
) -> ComponentTyping:
    """Apply CT0..CT4 strictly in order; the first rule whose condition holds decides."""
    basis = _basis(component, objects)
    for entry in overrides:  # CT0
        if getattr(component, entry.match) == entry.value:
            return ComponentTyping(component_type=entry.component_type, rule_id=RULE_CT0_OVERRIDE, basis=basis)
    if component.has_ip_config or component.medium_type_ref == MEDIUM_IP:  # CT1
        return ComponentTyping(component_type="IP_COUPLER_OR_INTERFACE", rule_id=RULE_CT1_IP, basis=basis)
    if component.address == 0:  # CT2
        return ComponentTyping(component_type="COUPLER", rule_id=RULE_CT2_COUPLER, basis=basis)
    if not any(obj.definition_resolved for obj in objects):  # CT3
        return ComponentTyping(component_type="UNTYPED", rule_id=RULE_CT3_NO_OBJECTS, basis=basis)
    receive, transmit = basis.receive_object_count, basis.transmit_object_count  # CT4
    if receive == 0 and transmit == 0:
        component_type = "UNTYPED"
    elif transmit == 0:
        component_type = "ACTUATOR"
    elif receive == 0:
        component_type = "SENSOR"
    elif receive >= 2 * transmit:
        component_type = "ACTUATOR"
    elif transmit >= 2 * receive:
        component_type = "SENSOR"
    else:
        component_type = "CONTROLLER"
    return ComponentTyping(component_type=component_type, rule_id=RULE_CT4_DIRECTION, basis=basis)


def derive(source_facts: SourceFacts, overrides: Sequence[TypeOverride] = ()) -> DerivedFacts:
    """Compute all derived facts from source facts (idempotent, does not mutate the input)."""
    components: list[ComponentNode] = []
    objects_by_component: dict[str, list[CommunicationObjectNode]] = {}
    object_component: dict[str, str | None] = {}
    for node in source_facts.nodes:
        if isinstance(node, ComponentNode):
            components.append(node)
        elif isinstance(node, CommunicationObjectNode):
            object_component[node.id] = node.component_id
            if node.component_id is not None:
                objects_by_component.setdefault(node.component_id, []).append(node)

    typing = {
        component.id: classify_component(component, objects_by_component.get(component.id, []), overrides)
        for component in sorted(components, key=lambda c: c.id)
    }
    counts: dict[str, int] = {}
    for entry in typing.values():
        counts[entry.component_type] = counts.get(entry.component_type, 0) + 1

    ga_to_objects: dict[str, set[str]] = {}
    component_to_gas: dict[str, set[str]] = {}
    for relation in source_facts.relations.membership:
        ga_to_objects.setdefault(relation.group_address_id, set()).add(relation.communication_object_id)
        owner = object_component.get(relation.communication_object_id)
        if owner is not None:
            component_to_gas.setdefault(owner, set()).add(relation.group_address_id)

    return DerivedFacts(
        component_typing=typing,
        membership_index=MembershipIndex(
            group_address_to_communication_objects={key: sorted(ga_to_objects[key]) for key in sorted(ga_to_objects)},
            component_to_group_addresses={key: sorted(component_to_gas[key]) for key in sorted(component_to_gas)},
        ),
        derived_counts=DerivedCounts(component_type_counts={key: counts[key] for key in sorted(counts)}),
    )
