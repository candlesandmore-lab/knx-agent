"""Topology summary (story 05, capability 8): areas, lines, locations and component distribution. Pure, no I/O.

SUMMARY: counts, locations by type. MEDIUM adds areas/lines with component counts, a depth-first location list and
the unplaced / unassigned counts. FULL adds the components under lines and locations (and the unplaced and
unassigned lists). Ordering: areas and lines by address, locations depth-first with siblings by casefolded name
then id, components in component order.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from knx_agent.contracts import (
    AreaEntry,
    AreaEntryFull,
    ComponentCounts,
    ComponentListItem,
    DetailLevel,
    LineEntry,
    LineEntryFull,
    LocationEntry,
    LocationEntryFull,
    TopologyCounts,
    TopologySummaryBasic,
    TopologySummaryFull,
    TopologySummaryMedium,
)

from .graph_index import GraphIndex, space_segment
from .project_graph import ComponentNode, SpaceNode

TopologyType = TopologySummaryBasic | TopologySummaryMedium | TopologySummaryFull

NO_LOCATIONS_TOPOLOGY_NOTE = "The project encodes no locations; the topology summary has no location entries."


def unplaced_topology_note(count: int) -> str:
    return f"{count} components are not placed in a location."


def unassigned_topology_note(count: int) -> str:
    return f"{count} components are not assigned to a line."


@dataclass(frozen=True)
class TopologyResult:
    topology_summary: TopologyType
    component_counts: ComponentCounts
    limitation_notes: list[str]


def _item(component: ComponentNode) -> ComponentListItem:
    return ComponentListItem(ets_id=component.id, name=component.name or None, individual_address=component.individual_address)


def _location_order(index: GraphIndex) -> list[tuple[SpaceNode, int, str, str | None]]:
    """Depth-first (space, depth, path, tree parent id); siblings by casefolded segment then id.

    Members of a parent cycle have no root; the lowest id of each cycle becomes a root."""
    children: dict[str | None, list[SpaceNode]] = {}
    for space in index.spaces:
        parent = space.parent_id if space.parent_id in index.space_by_id and space.parent_id != space.id else None
        children.setdefault(parent, []).append(space)
    for siblings in children.values():
        siblings.sort(key=lambda s: (space_segment(s).casefold(), s.id))
    ordered: list[tuple[SpaceNode, int, str, str | None]] = []
    visited: set[str] = set()

    def walk(space: SpaceNode, depth: int, path: str, parent: str | None) -> None:
        if space.id in visited:
            return
        visited.add(space.id)
        here = f"{path}/{space_segment(space)}" if path else space_segment(space)
        ordered.append((space, depth, here, parent))
        for child in children.get(space.id, []):
            walk(child, depth + 1, here, space.id)

    for root in children.get(None, []):
        walk(root, 1, "", None)
    for space in index.spaces:
        if space.id not in visited:
            walk(space, 1, "", None)
    return ordered


def summarize(index: GraphIndex, level: DetailLevel) -> TopologyResult:
    """The topology summary and component counts for ``level``."""
    components = index.components
    placed = [c for c in components if index.is_placed(c.id)]
    unplaced = [c for c in components if not index.is_placed(c.id)]
    type_counts = Counter(
        (index.typing[c.id].component_type if c.id in index.typing else "UNTYPED") for c in components
    )
    counts = ComponentCounts(
        total=len(components),
        placed=len(placed),
        unplaced=len(unplaced),
        by_component_type={key: type_counts[key] for key in sorted(type_counts)},
    )
    type_distribution = Counter(space.space_type or "UNKNOWN" for space in index.spaces)
    basic = TopologySummaryBasic(
        counts=TopologyCounts(areas=len(index.areas), lines=len(index.lines), locations=len(index.spaces)),
        locations_by_type={key: type_distribution[key] for key in sorted(type_distribution)},
    )
    unassigned = [c for c in components if c.line_id is None or c.line_id not in index.line_by_id]
    notes: list[str] = []
    if not index.has_locations:
        notes.append(NO_LOCATIONS_TOPOLOGY_NOTE)
    if unplaced:
        notes.append(unplaced_topology_note(len(unplaced)))
    if unassigned:
        notes.append(unassigned_topology_note(len(unassigned)))
    if level is DetailLevel.SUMMARY:
        return TopologyResult(basic, counts, notes)

    full = level is DetailLevel.FULL
    by_line: dict[str, list[ComponentNode]] = {}
    for component in components:
        if component.line_id in index.line_by_id:
            by_line.setdefault(component.line_id, []).append(component)  # type: ignore[arg-type]
    areas = []
    for area in index.areas:
        line_entries = []
        for line in (ln for ln in index.lines if ln.area_id == area.id):
            members = by_line.get(line.id, [])
            address_text = f"{area.address}.{line.address}" if area.address is not None and line.address is not None else None
            common = {
                "ets_id": line.id,
                "address": line.address,
                "address_text": address_text,
                "name": line.name,
                "component_count": len(members),
            }
            line_entries.append(
                LineEntryFull(**common, components=[_item(c) for c in members]) if full else LineEntry(**common)
            )
        total = sum(entry.component_count for entry in line_entries)
        area_common = {"ets_id": area.id, "address": area.address, "name": area.name, "component_count": total}
        areas.append(AreaEntryFull(**area_common, lines=line_entries) if full else AreaEntry(**area_common, lines=line_entries))

    members_by_space: dict[str, list[ComponentNode]] = {}
    for component in components:
        for space_id in index.placements.get(component.id, []):
            members_by_space.setdefault(space_id, []).append(component)
    order = _location_order(index)
    descendants: dict[str, set[str]] = {}
    for space, _depth, _path, _parent in order:
        descendants[space.id] = {c.id for c in members_by_space.get(space.id, [])}
    for space, _depth, _path, parent in reversed(order):  # children come after their parent in depth-first order
        if parent is not None:
            descendants[parent] |= descendants[space.id]
    locations = []
    for space, depth, path, _parent in order:
        direct = members_by_space.get(space.id, [])
        location_common = {
            "ets_id": space.id,
            "name": space.name,
            "space_type": space.space_type,
            "path": path,
            "depth": depth,
            "component_count": len(direct),
            "component_count_total": len(descendants[space.id]),
        }
        locations.append(
            LocationEntryFull(**location_common, components=[_item(c) for c in direct])
            if full
            else LocationEntry(**location_common)
        )
    medium_fields = {
        "counts": basic.counts,
        "locations_by_type": basic.locations_by_type,
        "areas": areas,
        "locations": locations,
        "unplaced_component_count": len(unplaced),
        "unassigned_to_line": len(unassigned),
    }
    if not full:
        return TopologyResult(TopologySummaryMedium(**medium_fields), counts, notes)
    return TopologyResult(
        TopologySummaryFull(
            **medium_fields,
            unplaced_components=[_item(c) for c in unplaced],
            unassigned_components=[_item(c) for c in unassigned],
        ),
        counts,
        notes,
    )
