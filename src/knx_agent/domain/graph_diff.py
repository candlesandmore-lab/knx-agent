"""Graph diff (story 04, T7): `changes` and `invalidated_references` of a re-import. Pure, no I/O.

Results are plain dicts shaped like the contracts models ProjectChange and InvalidatedReference, so the
application layer can validate them into the response models.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .project_graph import (
    ComponentNode,
    GroupAddressNode,
    ParameterNode,
    ProjectGraph,
)

_PROVENANCE_FIELDS = {"id", "kind", "id_origin", "source_part", "source_locator", "fact_origin"}
_GROUP_ADDRESS_FIELDS = ("address_raw", "name", "description", "datapoint_type")


def _component_fields(node: ComponentNode) -> dict[str, object]:
    return {key: value for key, value in node.model_dump().items() if key not in _PROVENANCE_FIELDS}


def _component_snapshot(graph: ProjectGraph) -> dict[str, dict[str, object]]:
    """Per component: compared fields plus 'parameters' (ref_id -> value) and 'group_addresses' (sorted ids)."""
    snapshot: dict[str, dict[str, object]] = {}
    parameters: dict[str, dict[str, str | None]] = {}
    for node in graph.source_facts.nodes:
        if isinstance(node, ComponentNode):
            snapshot[node.id] = _component_fields(node)
        elif isinstance(node, ParameterNode) and node.component_id is not None:
            parameters.setdefault(node.component_id, {})[node.ref_id or node.id] = node.value
    object_owner = {
        node.id: node.component_id
        for node in graph.source_facts.nodes
        if node.kind == "communication_object" and getattr(node, "component_id", None)
    }
    linked: dict[str, set[str]] = {}
    for relation in graph.source_facts.relations.membership:
        owner = object_owner.get(relation.communication_object_id)
        if owner is not None:
            linked.setdefault(owner, set()).add(relation.group_address_id)
    for component_id, fields in snapshot.items():
        fields["parameters"] = parameters.get(component_id, {})
        fields["group_addresses"] = sorted(linked.get(component_id, set()))
    return snapshot


def _group_address_snapshot(graph: ProjectGraph) -> dict[str, GroupAddressNode]:
    return {node.id: node for node in graph.source_facts.nodes if isinstance(node, GroupAddressNode)}


def _component_label(fields: Mapping[str, object]) -> str:
    return f"{fields.get('name')} ({fields.get('individual_address')})"


def _group_address_label(node: GroupAddressNode) -> str:
    return f"{node.address} {node.name}"


def diff_graphs(old: ProjectGraph, new: ProjectGraph) -> list[dict[str, object]]:
    """Components and group addresses added, removed or changed, sorted by (entity, id).

    Comparison is by stable ID; a node whose ID changed appears as removed plus added.
    """
    changes: list[dict[str, object]] = []

    old_components, new_components = _component_snapshot(old), _component_snapshot(new)
    for component_id in sorted(old_components.keys() | new_components.keys()):
        before, after = old_components.get(component_id), new_components.get(component_id)
        if before is None:
            assert after is not None
            changes.append(_entry("component", "added", component_id, _component_label(after), {}))
        elif after is None:
            changes.append(_entry("component", "removed", component_id, _component_label(before), {}))
        else:
            fields = sorted(key for key in before if before[key] != after[key])
            if fields:
                details: dict[str, object] = {
                    "changed_fields": fields,
                    "old": {key: before[key] for key in fields},
                    "new": {key: after[key] for key in fields},
                }
                if "parameters" in fields:
                    old_values, new_values = before["parameters"], after["parameters"]
                    assert isinstance(old_values, dict) and isinstance(new_values, dict)
                    changed = sorted(
                        ref for ref in old_values.keys() | new_values.keys() if old_values.get(ref, _ABSENT) != new_values.get(ref, _ABSENT)
                    )
                    details["old"]["parameters"] = {ref: old_values.get(ref) for ref in changed}  # type: ignore[index]
                    details["new"]["parameters"] = {ref: new_values.get(ref) for ref in changed}  # type: ignore[index]
                changes.append(_entry("component", "changed", component_id, _component_label(after), details))

    old_gas, new_gas = _group_address_snapshot(old), _group_address_snapshot(new)
    for ga_id in sorted(old_gas.keys() | new_gas.keys()):
        before_ga, after_ga = old_gas.get(ga_id), new_gas.get(ga_id)
        if before_ga is None:
            assert after_ga is not None
            changes.append(_entry("group_address", "added", ga_id, _group_address_label(after_ga), {}))
        elif after_ga is None:
            changes.append(_entry("group_address", "removed", ga_id, _group_address_label(before_ga), {}))
        else:
            fields = [key for key in _GROUP_ADDRESS_FIELDS if getattr(before_ga, key) != getattr(after_ga, key)]
            if fields:
                changes.append(
                    _entry(
                        "group_address",
                        "changed",
                        ga_id,
                        _group_address_label(after_ga),
                        {
                            "changed_fields": sorted(fields),
                            "old": {key: getattr(before_ga, key) for key in sorted(fields)},
                            "new": {key: getattr(after_ga, key) for key in sorted(fields)},
                        },
                    )
                )
    return sorted(changes, key=lambda item: (str(item["entity"]), str(item["id"])))


_ABSENT = object()


def _entry(entity: str, change: str, entity_id: str, label: str, details: dict[str, object]) -> dict[str, object]:
    return {"entity": entity, "change": change, "id": entity_id, "label": label, "details": details}


def invalidated_references(
    old: ProjectGraph,
    new: ProjectGraph,
    scenario_state: Sequence[object],
    mutations: Sequence[object],
) -> list[dict[str, object]]:
    """Scenario-state and mutation entries that name a component or group address removed by the re-import.

    An entry (a mapping) with ``component_id``, ``component_ids`` (list) or ``group_address_id`` naming an ID
    that existed in the old graph and is absent from the new graph yields one reference per removed ID. The
    owner is the mutation ``name`` for mutations, else the zero-based list index as text. Entries without
    these keys are ignored; state is never modified.
    """
    old_components = {n.id for n in old.source_facts.nodes if n.kind == "component"}
    new_components = {n.id for n in new.source_facts.nodes if n.kind == "component"}
    old_gas = {n.id for n in old.source_facts.nodes if n.kind == "group_address"}
    new_gas = {n.id for n in new.source_facts.nodes if n.kind == "group_address"}
    removed_components = old_components - new_components
    removed_gas = old_gas - new_gas

    found: list[dict[str, object]] = []

    def scan(kind: str, entries: Sequence[object], by_name: bool) -> None:
        for index, entry in enumerate(entries):
            if not isinstance(entry, Mapping):
                continue
            owner = str(entry["name"]) if by_name and "name" in entry else str(index)
            component_ids: list[str] = []
            if isinstance(entry.get("component_id"), str):
                component_ids.append(entry["component_id"])
            if isinstance(entry.get("component_ids"), list):
                component_ids.extend(item for item in entry["component_ids"] if isinstance(item, str))
            for component_id in component_ids:
                if component_id in removed_components:
                    found.append(
                        {
                            "reference_kind": kind,
                            "owner": owner,
                            "component_id": component_id,
                            "group_address_id": None,
                            "reason": "COMPONENT_REMOVED",
                        }
                    )
            ga_id = entry.get("group_address_id")
            if isinstance(ga_id, str) and ga_id in removed_gas:
                found.append(
                    {
                        "reference_kind": kind,
                        "owner": owner,
                        "component_id": None,
                        "group_address_id": ga_id,
                        "reason": "GROUP_ADDRESS_REMOVED",
                    }
                )

    scan("scenario_state", scenario_state, by_name=False)
    scan("mutation_delta", mutations, by_name=True)
    return found
