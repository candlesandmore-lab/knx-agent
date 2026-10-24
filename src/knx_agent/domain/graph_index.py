"""In-memory indexes over a ProjectGraph for the query capabilities (story 05). Pure; the graph is never mutated.

Built on every call (nothing is cached between calls). Provides the deterministic component order, instance paths
(location tree), objects and parameters by component, group address memberships and warnings by object.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .project_graph import (
    ApplicationProgramNode,
    AreaNode,
    CommunicationObjectNode,
    ComponentNode,
    ComponentTyping,
    GroupAddressNode,
    GroupRangeNode,
    ImportWarning,
    LineNode,
    MembershipRelation,
    ParameterNode,
    ProjectGraph,
    SpaceNode,
)

LINK_WARNING_CODES: tuple[str, ...] = ("GROUP_ADDRESS_LINK_UNRESOLVED", "COMOBJECT_DEFINITION_UNRESOLVED")
_LAST = 1 << 30


def parse_individual_address(text: str | None) -> tuple[int, int, int] | None:
    """(area, line, device) from 'a.l.d' text, None when missing or unparsable."""
    if not text:
        return None
    parts = text.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    return int(parts[0]), int(parts[1]), int(parts[2])


def component_sort_key(component: ComponentNode) -> tuple[int, int, int, int, str]:
    """Component order: area, line, device numerically from the individual address; unparsable last; then id."""
    parsed = parse_individual_address(component.individual_address)
    if parsed is None:
        return (1, _LAST, _LAST, _LAST, component.id)
    return (0, parsed[0], parsed[1], parsed[2], component.id)


def space_segment(space: SpaceNode) -> str:
    """Path segment of a space: its name, else its ETS id."""
    return space.name if space.name else space.id


def component_segment(component: ComponentNode) -> str:
    """Path segment of a component: its name, else its individual address, else its ETS id."""
    if component.name:
        return component.name
    if component.individual_address:
        return component.individual_address
    return component.id


def _number_key(value: int | None) -> int:
    return _LAST if value is None else value


@dataclass
class GraphIndex:
    """Indexes of one project graph. Use ``GraphIndex.build``."""

    graph: ProjectGraph
    group_address_style: str | None = None
    components: list[ComponentNode] = field(default_factory=list)  # in component order
    component_by_id: dict[str, ComponentNode] = field(default_factory=dict)
    component_position: dict[str, int] = field(default_factory=dict)
    areas: list[AreaNode] = field(default_factory=list)  # by address
    area_by_id: dict[str, AreaNode] = field(default_factory=dict)
    lines: list[LineNode] = field(default_factory=list)  # by area address, line address
    line_by_id: dict[str, LineNode] = field(default_factory=dict)
    spaces: list[SpaceNode] = field(default_factory=list)  # by id
    space_by_id: dict[str, SpaceNode] = field(default_factory=dict)
    placements: dict[str, list[str]] = field(default_factory=dict)  # component id -> valid space ids sorted
    location_chains: dict[str, list[SpaceNode]] = field(default_factory=dict)  # space id -> root..leaf
    path_segments: dict[str, list[list[str]]] = field(default_factory=dict)  # component id -> segment lists
    objects_by_component: dict[str, list[CommunicationObjectNode]] = field(default_factory=dict)
    object_by_id: dict[str, CommunicationObjectNode] = field(default_factory=dict)
    parameters_by_component: dict[str, list[ParameterNode]] = field(default_factory=dict)
    group_addresses: list[GroupAddressNode] = field(default_factory=list)  # by address_raw, id
    group_address_by_id: dict[str, GroupAddressNode] = field(default_factory=dict)
    group_addresses_by_raw: dict[int, list[GroupAddressNode]] = field(default_factory=dict)
    memberships_by_group_address: dict[str, list[MembershipRelation]] = field(default_factory=dict)
    memberships_by_object: dict[str, list[MembershipRelation]] = field(default_factory=dict)
    range_by_id: dict[str, GroupRangeNode] = field(default_factory=dict)
    program_by_id: dict[str, ApplicationProgramNode] = field(default_factory=dict)
    warnings_by_object: dict[str, list[ImportWarning]] = field(default_factory=dict)
    typing: dict[str, ComponentTyping] = field(default_factory=dict)

    # -- construction ----------------------------------------------------------------------------
    @classmethod
    def build(cls, graph: ProjectGraph) -> GraphIndex:
        index = cls(graph=graph)
        index.typing = dict(graph.derived_facts.component_typing)
        components: list[ComponentNode] = []
        for node in graph.source_facts.nodes:
            if isinstance(node, ComponentNode):
                components.append(node)
            elif isinstance(node, AreaNode):
                index.areas.append(node)
            elif isinstance(node, LineNode):
                index.lines.append(node)
            elif isinstance(node, SpaceNode):
                index.spaces.append(node)
            elif isinstance(node, CommunicationObjectNode):
                index.object_by_id[node.id] = node
            elif isinstance(node, GroupAddressNode):
                index.group_addresses.append(node)
            elif isinstance(node, GroupRangeNode):
                index.range_by_id[node.id] = node
            elif isinstance(node, ParameterNode):
                if node.component_id is not None:
                    index.parameters_by_component.setdefault(node.component_id, []).append(node)
            elif isinstance(node, ApplicationProgramNode):
                index.program_by_id[node.id] = node
            elif node.kind == "installation":
                index.group_address_style = getattr(node, "group_address_style", None)

        index.components = sorted(components, key=component_sort_key)
        index.component_by_id = {c.id: c for c in index.components}
        index.component_position = {c.id: i for i, c in enumerate(index.components)}
        index.areas.sort(key=lambda a: (_number_key(a.address), a.id))
        index.area_by_id = {a.id: a for a in index.areas}
        index.lines.sort(
            key=lambda ln: (
                _number_key(index.area_by_id[ln.area_id].address) if ln.area_id in index.area_by_id else _LAST,
                _number_key(ln.address),
                ln.id,
            )
        )
        index.line_by_id = {ln.id: ln for ln in index.lines}
        index.spaces.sort(key=lambda s: s.id)
        index.space_by_id = {s.id: s for s in index.spaces}

        for obj in index.object_by_id.values():
            if obj.component_id is not None:
                index.objects_by_component.setdefault(obj.component_id, []).append(obj)
        for objects in index.objects_by_component.values():
            objects.sort(key=lambda o: (_number_key(o.object_number), o.id))
        for parameters in index.parameters_by_component.values():
            parameters.sort(key=lambda p: ((p.name or p.text or p.ref_id or "").casefold(), p.ref_id or "", p.id))

        index.group_addresses.sort(key=lambda g: (_number_key(g.address_raw), g.id))
        index.group_address_by_id = {g.id: g for g in index.group_addresses}
        for ga in index.group_addresses:
            if ga.address_raw is not None:
                index.group_addresses_by_raw.setdefault(ga.address_raw, []).append(ga)
        for relation in graph.source_facts.relations.membership:
            index.memberships_by_group_address.setdefault(relation.group_address_id, []).append(relation)
            index.memberships_by_object.setdefault(relation.communication_object_id, []).append(relation)
        for relations in index.memberships_by_object.values():
            relations.sort(key=lambda r: (r.order, r.group_address_id))
        for relations in index.memberships_by_group_address.values():
            relations.sort(key=lambda r: (r.communication_object_id, r.order))
        for warning in graph.warnings:
            if warning.code in LINK_WARNING_CODES and "#" in warning.location:
                index.warnings_by_object.setdefault(warning.location.partition("#")[2], []).append(warning)

        index._build_locations()
        return index

    def _build_locations(self) -> None:
        for space in self.spaces:
            chain: list[SpaceNode] = []
            seen: set[str] = set()
            current: SpaceNode | None = space
            while current is not None and current.id not in seen:  # a parent cycle stops at the first repeat
                chain.append(current)
                seen.add(current.id)
                current = self.space_by_id.get(current.parent_id) if current.parent_id else None
            chain.reverse()
            self.location_chains[space.id] = chain
        placed: dict[str, set[str]] = {}
        for relation in self.graph.source_facts.relations.placed_in:
            if relation.space_id in self.space_by_id and relation.component_id in self.component_by_id:
                placed.setdefault(relation.component_id, set()).add(relation.space_id)
        for component_id, space_ids in placed.items():
            self.placements[component_id] = sorted(space_ids)
        for component in self.components:
            segments = []
            for space_id in self.placements.get(component.id, []):
                segments.append([space_segment(s) for s in self.location_chains[space_id]] + [component_segment(component)])
            if segments:
                self.path_segments[component.id] = segments

    # -- lookups -----------------------------------------------------------------------------------
    def instance_paths(self, component_id: str) -> list[str]:
        """All instance path strings of a component (first = ``instance_path``); empty when unplaced."""
        return ["/".join(segments) for segments in self.path_segments.get(component_id, [])]

    def location_path(self, component_id: str) -> list[SpaceNode]:
        """Spaces root to leaf of the first placement; empty when unplaced."""
        spaces = self.placements.get(component_id)
        return list(self.location_chains[spaces[0]]) if spaces else []

    def is_placed(self, component_id: str) -> bool:
        return component_id in self.placements

    def component_line(self, component: ComponentNode) -> LineNode | None:
        return self.line_by_id.get(component.line_id) if component.line_id else None

    def component_area(self, component: ComponentNode) -> AreaNode | None:
        line = self.component_line(component)
        return self.area_by_id.get(line.area_id) if line is not None and line.area_id else None

    def range_chain(self, range_id: str | None) -> list[GroupRangeNode]:
        """Group ranges root to leaf; a cycle stops at the first repeated range."""
        chain: list[GroupRangeNode] = []
        seen: set[str] = set()
        current = self.range_by_id.get(range_id) if range_id else None
        while current is not None and current.id not in seen:
            chain.append(current)
            seen.add(current.id)
            current = self.range_by_id.get(current.parent_id) if current.parent_id else None
        chain.reverse()
        return chain

    @property
    def has_locations(self) -> bool:
        return bool(self.spaces)
