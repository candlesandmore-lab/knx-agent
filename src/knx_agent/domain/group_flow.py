"""Group address flow: direct participants of a group address or communication object (story 05, capability 9).

Direction comes ONLY from the ETS communication object flags (transmit, write, update; read adds the role
ANSWERS_READ); the order of group address links is never consulted. No line or area routing; the current value is
always ``unknown``. Pure, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from knx_agent.contracts import (
    CURRENT_VALUE_UNKNOWN,
    INVALID_REQUEST,
    REASON_SELECTOR_CONFLICT,
    REASON_SELECTOR_MISSING,
    SELECTOR_UNRESOLVED,
    DetailLevel,
    FlowComponentMedium,
    FlowComponentSummary,
    FlowEntryFull,
    FlowEntryMedium,
    FlowEntrySummary,
    FlowGroupAddressFull,
    FlowGroupAddressMedium,
    FlowGroupAddressSummary,
    FlowObjectFull,
    FlowObjectMedium,
    FlowParticipantFull,
    FlowParticipantMedium,
    FlowParticipantSummary,
    PropagationPath,
    UnresolvedLinkMedium,
    UnresolvedLinkSummary,
    error,
)

from .component_view import object_flags, object_label
from .graph_index import LINK_WARNING_CODES, GraphIndex
from .project_graph import CommunicationObjectNode, ComponentNode, GroupAddressNode
from .selectors import parse_communication_object_ref, parse_group_address_selector, strip_selector

ENABLED = "Enabled"
NOTE_DIRECTION = "Direction is derived from the ETS communication object flags only; the order of group address links is not used."
NOTE_DIRECT_ONLY = "Only direct participants are listed; line and area routing is not evaluated."
NOTE_CURRENT_VALUE = "current_value is unknown; no simulation exists yet."
NOTE_OBJECT_WITHOUT_LINK = "The communication object is not linked to any group address."
UNRESOLVED_OBJECT_MESSAGE = "The definition of the communication object could not be resolved; its flags are unknown."
_LAST = 1 << 30

FlowEntryType = FlowEntrySummary | FlowEntryMedium | FlowEntryFull


def roles_of(obj: CommunicationObjectNode) -> list[str]:
    """Sorted roles from the flags: TRANSMITS, ACCEPTS_WRITE, ACCEPTS_UPDATE, ANSWERS_READ."""
    roles = []
    if obj.transmit_flag == ENABLED:
        roles.append("TRANSMITS")
    if obj.write_flag == ENABLED:
        roles.append("ACCEPTS_WRITE")
    if obj.update_flag == ENABLED:
        roles.append("ACCEPTS_UPDATE")
    if obj.read_flag == ENABLED:
        roles.append("ANSWERS_READ")
    return sorted(roles)


def direction_of(roles: list[str]) -> str:
    """SENDER / RECEIVER / SENDER_RECEIVER / UNDETERMINED from the roles (link order is not an input)."""
    sends = "TRANSMITS" in roles
    receives = "ACCEPTS_WRITE" in roles or "ACCEPTS_UPDATE" in roles
    if sends and receives:
        return "SENDER_RECEIVER"
    if sends:
        return "SENDER"
    if receives:
        return "RECEIVER"
    return "UNDETERMINED"


@dataclass(frozen=True)
class FlowResult:
    entries: list[FlowEntryType]
    match_count: int
    ambiguous: bool
    limitation_notes: list[str]


@dataclass(frozen=True)
class _Participant:
    component: ComponentNode
    obj: CommunicationObjectNode
    link_order: int
    roles: list[str]
    direction: str


def _participants(index: GraphIndex, ga: GroupAddressNode) -> list[_Participant]:
    found = []
    for relation in index.memberships_by_group_address.get(ga.id, []):
        obj = index.object_by_id.get(relation.communication_object_id)
        component = index.component_by_id.get(obj.component_id) if obj is not None and obj.component_id else None
        if obj is None or component is None:
            continue
        roles = roles_of(obj)
        found.append(_Participant(component, obj, relation.order, roles, direction_of(roles)))
    found.sort(
        key=lambda p: (
            index.component_position[p.component.id],
            p.obj.object_number if p.obj.object_number is not None else _LAST,
            p.obj.id,
        )
    )
    return found


def _unresolved_links(participants: list[_Participant], index: GraphIndex) -> list[tuple[str, str, str | None, str, str]]:
    """(object id, code, component id, message, location) for the linked objects, sorted by object id then code."""
    items: dict[tuple[str, str, str, str], tuple[str, str, str | None, str, str]] = {}
    for obj in {p.obj.id: p.obj for p in participants}.values():
        warnings = [w for w in index.warnings_by_object.get(obj.id, []) if w.code in LINK_WARNING_CODES]
        for warning in warnings:
            items[(obj.id, warning.code, warning.message, warning.location)] = (
                obj.id, warning.code, obj.component_id, warning.message, warning.location,
            )
        if not obj.definition_resolved and not any(w.code == "COMOBJECT_DEFINITION_UNRESOLVED" for w in warnings):
            location = f"{obj.source_part}#{obj.id}"
            items[(obj.id, "COMOBJECT_DEFINITION_UNRESOLVED", UNRESOLVED_OBJECT_MESSAGE, location)] = (
                obj.id, "COMOBJECT_DEFINITION_UNRESOLVED", obj.component_id, UNRESOLVED_OBJECT_MESSAGE, location,
            )
    return sorted(items.values(), key=lambda item: (item[0], item[1], item[3], item[4]))


def _entry(index: GraphIndex, ga: GroupAddressNode, level: DetailLevel) -> FlowEntryType:
    participants = _participants(index, ga)
    summary_address = {"ets_id": ga.id, "address": ga.address, "name": ga.name}
    senders, receivers = [], []
    for p in participants:
        if p.direction in ("SENDER", "SENDER_RECEIVER") and p.component.id not in senders:
            senders.append(p.component.id)
        if p.direction in ("RECEIVER", "SENDER_RECEIVER") and p.component.id not in receivers:
            receivers.append(p.component.id)
    order = index.component_position
    path = PropagationPath(senders=sorted(senders, key=order.get), receivers=sorted(receivers, key=order.get))
    unresolved = _unresolved_links(participants, index)

    def component_summary(p: _Participant) -> FlowComponentSummary:
        return FlowComponentSummary(ets_id=p.component.id, name=p.component.name or None, individual_address=p.component.individual_address)

    def component_medium(p: _Participant) -> FlowComponentMedium:
        paths = index.instance_paths(p.component.id)
        typing = index.typing.get(p.component.id)
        return FlowComponentMedium(
            **component_summary(p).model_dump(),
            instance_path=paths[0] if paths else None,
            component_type=typing.component_type if typing is not None else None,
        )

    def object_medium(p: _Participant) -> dict:
        return {
            "ets_id": p.obj.id,
            "object_number": p.obj.object_number,
            "label": object_label(p.obj),
            "datapoint_types": list(p.obj.datapoint_types),
        }

    if level is DetailLevel.SUMMARY:
        return FlowEntrySummary(
            group_address=FlowGroupAddressSummary(**summary_address),
            participants=[FlowParticipantSummary(component=component_summary(p), direction=p.direction) for p in participants],  # type: ignore[arg-type]
            propagation_path=path,
            unresolved_links=[
                UnresolvedLinkSummary(code=code, communication_object_id=obj_id, component_id=component_id)
                for obj_id, code, component_id, _message, _location in unresolved
            ],
            current_value=CURRENT_VALUE_UNKNOWN,
        )
    medium_address = {**summary_address, "datapoint_type": ga.datapoint_type, "description": ga.description}
    medium_links = [
        UnresolvedLinkMedium(code=code, communication_object_id=obj_id, component_id=component_id, message=message, location=location)
        for obj_id, code, component_id, message, location in unresolved
    ]
    if level is DetailLevel.MEDIUM:
        return FlowEntryMedium(
            group_address=FlowGroupAddressMedium(**medium_address),
            participants=[
                FlowParticipantMedium(
                    component=component_medium(p),
                    communication_object=FlowObjectMedium(**object_medium(p)),
                    direction=p.direction,  # type: ignore[arg-type]
                    roles=p.roles,
                )
                for p in participants
            ],
            propagation_path=path,
            unresolved_links=medium_links,
            current_value=CURRENT_VALUE_UNKNOWN,
        )
    return FlowEntryFull(
        group_address=FlowGroupAddressFull(
            **medium_address,
            address_raw=ga.address_raw,
            range_id=ga.range_id,
            range_path=[r.name or r.id for r in index.range_chain(ga.range_id)],
        ),
        participants=[
            FlowParticipantFull(
                component=component_medium(p),
                communication_object=FlowObjectFull(
                    **object_medium(p),
                    function_text=p.obj.function_text,
                    text=p.obj.text,
                    instance_text=p.obj.instance_text,
                    description=p.obj.description,
                    object_size=p.obj.object_size,
                    flags=object_flags(p.obj),
                    definition_resolved=p.obj.definition_resolved,
                ),
                direction=p.direction,  # type: ignore[arg-type]
                roles=p.roles,
                link_order=p.link_order,
            )
            for p in participants
        ],
        propagation_path=path,
        unresolved_links=medium_links,
        current_value=CURRENT_VALUE_UNKNOWN,
    )


def _base_notes() -> list[str]:
    return [NOTE_DIRECTION, NOTE_DIRECT_ONLY, NOTE_CURRENT_VALUE]


def validate_flow_request(group_address_selector: str | None, communication_object_ref: str | None) -> None:
    """Request rules of trace_group_flow: exactly one selector, not blank, object ref well formed."""
    if group_address_selector is not None and communication_object_ref is not None:
        raise error(
            INVALID_REQUEST,
            "Give exactly one of group_address_selector and communication_object_ref, not both.",
            reason=REASON_SELECTOR_CONFLICT,
        )
    if group_address_selector is None and communication_object_ref is None:
        raise error(
            INVALID_REQUEST,
            "Give exactly one of group_address_selector and communication_object_ref.",
            reason=REASON_SELECTOR_MISSING,
        )
    if group_address_selector is not None:
        strip_selector(group_address_selector)  # SELECTOR_BLANK
    else:
        parse_communication_object_ref(communication_object_ref)  # type: ignore[arg-type]


def trace(
    index: GraphIndex,
    group_address_selector: str | None,
    communication_object_ref: str | None,
    level: DetailLevel,
) -> FlowResult:
    """trace_group_flow: exactly one of the two selectors; flow entries are ordered by raw address."""
    validate_flow_request(group_address_selector, communication_object_ref)
    notes = _base_notes()
    if group_address_selector is not None:
        query = parse_group_address_selector(group_address_selector, index.group_address_style)
        if query.address_raw is not None:
            matched = list(index.group_addresses_by_raw.get(query.address_raw, []))
            kinds = ["ADDRESS"]
            extra: dict[str, object] = {"address_raw": query.address_raw}
        else:
            matched = [g for g in index.group_addresses if g.name and query.name_needle in g.name.casefold()]  # type: ignore[operator]
            kinds = ["NAME"]
            extra = {}
        if not matched:
            raise error(
                SELECTOR_UNRESOLVED,
                f"No group address matches {query.text!r}.",
                selector=query.text,
                selector_kind="GROUP_ADDRESS",
                evaluated_kinds=kinds,
                **extra,
            )
    else:
        reference = parse_communication_object_ref(communication_object_ref)  # type: ignore[arg-type]
        obj = index.object_by_id.get(reference)
        if obj is None:
            raise error(
                SELECTOR_UNRESOLVED,
                f"No communication object has the id {reference!r}.",
                selector=reference,
                selector_kind="COMMUNICATION_OBJECT_REF",
                evaluated_kinds=["COMMUNICATION_OBJECT_REF"],
            )
        linked = {
            index.group_address_by_id[r.group_address_id].id: index.group_address_by_id[r.group_address_id]
            for r in index.memberships_by_object.get(obj.id, [])
            if r.group_address_id in index.group_address_by_id
        }
        matched = list(linked.values())
        if not matched:
            notes.append(NOTE_OBJECT_WITHOUT_LINK)
    matched.sort(key=lambda g: (g.address_raw if g.address_raw is not None else _LAST, g.id))
    entries = [_entry(index, ga, level) for ga in matched]
    return FlowResult(entries, len(entries), len(entries) > 1, notes)


__all__ = ["FlowResult", "direction_of", "roles_of", "trace", "validate_flow_request"]
