"""ETS 6 parser: project.xml, 0.xml, catalog resolution, streaming of application programs (story 04, T6).

Own parser on the standard library (``xml.etree.ElementTree`` iterparse); no xknxproject. It turns a guarded
``KnxprojArchive`` into the source facts of the project graph plus import warnings. Derived facts are computed
elsewhere (``domain.derivation``).

Referenced application program (003 'Referenced application program'): P1 = Hardware2ProgramRefId ->
``<M>/Hardware.xml`` Hardware2Program -> ApplicationProgramRef; P2 = textual fallback when P1 is unusable;
ProductRefId only supplies product text and order number. Only referenced programs are opened.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from knx_agent.contracts import PROJECT_PARSE_ERROR, error
from knx_agent.contracts.import_codes import (
    REASON_NOT_ETS_PROJECT,
    REASON_REQUIRED_PART_MALFORMED,
    REASON_UNSUPPORTED_NAMESPACE,
    REASON_UNSUPPORTED_TOOL_VERSION,
    WARNING_ADDITIONAL_INSTALLATION_IGNORED,
    WARNING_APPLICATION_PROGRAM_MISSING,
    WARNING_APPLICATION_PROGRAM_REFERENCE_MISMATCH,
    WARNING_COMOBJECT_DEFINITION_UNRESOLVED,
    WARNING_DATAPOINT_TYPE_UNKNOWN,
    WARNING_DEVICE_REFERENCE_UNRESOLVED,
    WARNING_DUPLICATE_ID,
    WARNING_GROUP_ADDRESS_LINK_UNRESOLVED,
    WARNING_INVALID_ATTRIBUTE_VALUE,
    WARNING_OPTIONAL_PART_MISSING,
    WARNING_OPTIONAL_PART_UNREADABLE,
    WARNING_PARAMETER_DEFINITION_UNRESOLVED,
    WARNING_PRODUCT_REFERENCE_UNRESOLVED,
    WARNING_STRUCTURAL_ID_FALLBACK,
    WARNING_UNSUPPORTED_ELEMENT,
)
from knx_agent.domain import ApplicationProgramCounts, ImportWarning
from knx_agent.domain.project_graph import (
    FACT_ORIGIN_CATALOG,
    FACT_ORIGIN_PROJECT,
    ApplicationProgramNode,
    AreaNode,
    CommunicationObjectNode,
    ComponentNode,
    GraphNode,
    GroupAddressNode,
    GroupRangeNode,
    IdAllocator,
    InstallationNode,
    LineNode,
    LoadState,
    MembershipRelation,
    ParameterNode,
    PlacedInRelation,
    Relations,
    SceneNode,
    SourceFacts,
    SpaceNode,
    StableId,
    application_program_node_id,
    communication_object_id,
    ets_id,
    format_group_address,
    individual_address_text,
    installation_id,
    membership_sort_key,
    parameter_node_id,
    placed_in_sort_key,
    sort_nodes,
    structural_fallback_id,
    structural_key,
)

from .knxproj_archive import KnxprojArchive, OptionalPartRejected

SUPPORTED_NAMESPACE = "http://knx.org/xml/project/22"
SUPPORTED_MAJOR_VERSION = 6
MASTER_ENTRY = "knx_master.xml"

_REF_PROGRAM_SPLIT = re.compile(r"_(?:P|UP|MD)-")
_HARDWARE2PROGRAM_SPLIT = "_HP-"
_FLAG_KEYS = {
    "read_flag": "ReadFlag",
    "write_flag": "WriteFlag",
    "communication_flag": "CommunicationFlag",
    "transmit_flag": "TransmitFlag",
    "update_flag": "UpdateFlag",
    "read_on_init_flag": "ReadOnInitFlag",
}
_PROGRAM_CLEAR_TAGS = frozenset({"Translation", "TranslationElement", "TranslationUnit", "Language", "Dynamic"})


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _namespace(tag: str) -> str:
    return tag[1 : tag.index("}")] if tag.startswith("{") else ""


def _int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def _bool(value: str | None) -> bool | None:
    if value is None:
        return None
    lowered = value.strip().lower()
    return True if lowered == "true" else False if lowered == "false" else None


def _manufacturer_of(*references: str | None) -> str | None:
    for reference in references:
        if reference and reference.startswith("M-"):
            return reference.split("_", 1)[0]
    return None


def reference_program_prefix(ref_id: str) -> str | None:
    """Application program id named by a ParameterInstanceRef RefId (the part before _P-, _UP- or _MD-)."""
    match = _REF_PROGRAM_SPLIT.search(ref_id)
    return ref_id[: match.start()] if match else None


def derive_program_id_from_hardware2program(hardware2program: str) -> str | None:
    """P2: '<M>_H-...-<x>_HP-<rest>' -> '<M>_A-<rest>' (textual derivation, no catalog access)."""
    head, separator, rest = hardware2program.partition(_HARDWARE2PROGRAM_SPLIT)
    if not separator or not rest or not head:
        return None
    return f"{head.split('_', 1)[0]}_A-{rest}"


# -- result -------------------------------------------------------------------------------------
@dataclass
class ParsedProject:
    """Source facts, warnings and application program counts of one import."""

    source_facts: SourceFacts
    warnings: list[ImportWarning]
    application_programs: ApplicationProgramCounts
    read_programs: list[str] = field(default_factory=list)


@dataclass
class _Frame:
    tag: str
    node_id: str | None
    locator: str
    extra: dict[str, object] = field(default_factory=dict)


@dataclass
class _RawObject:
    ref_id: str
    links: list[str]
    channel_id: str | None
    description: str | None
    text: str | None
    locator: str


@dataclass
class _RawParameter:
    ref_id: str
    value: str | None
    locator: str


@dataclass
class _Hardware:
    status: str  # 'ok', 'missing', 'unreadable'
    programs: dict[str, str] = field(default_factory=dict)  # Hardware2Program Id -> ApplicationProgramRef RefId
    products: dict[str, tuple[str | None, str | None]] = field(default_factory=dict)  # Id -> (text, order number)


@dataclass
class _ProgramDefs:
    attrs: dict[str, str] = field(default_factory=dict)
    comobjects: dict[str, dict[str, str]] = field(default_factory=dict)
    comobject_refs: dict[str, dict[str, str]] = field(default_factory=dict)
    parameters: dict[str, dict[str, str]] = field(default_factory=dict)
    parameter_refs: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass
class _Resolution:
    program_id: str | None = None
    entry: str | None = None
    status: str = "missing"  # 'read', 'unreadable', 'missing'
    mismatch_parameters: bool = False


class _Parser:
    def __init__(self, archive: KnxprojArchive) -> None:
        self.archive = archive
        self.warnings: list[ImportWarning] = []
        self.allocator = IdAllocator()
        self.folder = archive.project_folder or ""
        self.zero_entry = archive.project_entry("0.xml")
        self.project_entry = archive.project_entry("project.xml")
        # project.xml
        self.tool_version: str | None = None
        self.created_by: str | None = None
        self.project_id: str | None = None
        self.project_name: str | None = None
        self.address_style: str | None = None
        self.project_last_modified: str | None = None
        self.completion_status: str | None = None
        # 0.xml
        self.installation: InstallationNode | None = None
        self.nodes: list[GraphNode] = []
        self.components: dict[str, ComponentNode] = {}
        self.component_locators: dict[str, str] = {}
        self.raw_objects: dict[str, list[_RawObject]] = {}
        self.raw_parameters: dict[str, list[_RawParameter]] = {}
        self.group_addresses: dict[str, GroupAddressNode] = {}
        self.space_refs: list[tuple[str, str, str]] = []  # (space id, component id, locator)
        self.scene_like: dict[str, None] = {}
        self._positions: dict[tuple[str, str], int] = {}
        self._stack: list[_Frame] = []
        # catalog
        self.hardware: dict[str, _Hardware] = {}
        self.master_ids: set[str] | None = None
        self.resolutions: dict[str, _Resolution] = {}
        self.programs: dict[str, _ProgramDefs] = {}
        self.read_programs: list[str] = []
        self.unreadable_programs: set[str] = set()

    # -- warnings and ids -----------------------------------------------------------------------
    def warn(self, code: str, message: str, location: str) -> None:
        self.warnings.append(ImportWarning(code=code, message=message, location=location))

    def _node_location(self, node_id: str) -> str:
        return f"{self.zero_entry}#{node_id}"

    def _position(self, parent_id: str, kind: str) -> int:
        key = (parent_id, kind)
        position = self._positions.get(key, 0)
        self._positions[key] = position + 1
        return position

    def _stable_id(
        self,
        element: ET.Element,
        kind: str,
        parent_id: str,
        parent_locator: str,
        address: object | None,
        name: str | None,
    ) -> tuple[StableId, str]:
        """Stable ID (rules 1, 4, 5) and the source locator of an element that should carry an ETS Id."""
        tag = _local(element.tag)
        position = self._position(parent_id, kind)
        ets = element.get("Id")
        if ets:
            stable, locator = ets_id(ets), f"{tag}[@Id={ets}]"
        else:
            stable = structural_fallback_id(parent_id, kind, structural_key(address, name, position))
            locator = f"{parent_locator}/{tag}[{position}]"
            self.warn(
                WARNING_STRUCTURAL_ID_FALLBACK,
                f"{tag} has no Id; the structural fallback ID {stable.id} is used.",
                self._node_location(stable.id),
            )
        unique, collided = self.allocator.claim(stable)
        if collided:
            self.warn(
                WARNING_DUPLICATE_ID,
                f"The ID {stable.id} occurs more than once; the later element gets {unique.id}.",
                self._node_location(stable.id),
            )
        return unique, locator

    def _nearest(self, tag: str) -> _Frame | None:
        for frame in reversed(self._stack):
            if frame.tag == tag and frame.node_id is not None:
                return frame
        return None

    def _invalid(self, element: ET.Element, attribute: str, node_hint: str) -> None:
        self.warn(
            WARNING_INVALID_ATTRIBUTE_VALUE,
            f"{_local(element.tag)} has a missing or non-numeric {attribute} attribute and is skipped.",
            f"{self.zero_entry}#{element.get('Id') or node_hint}",
        )

    # -- root checks ----------------------------------------------------------------------------
    def _check_root(self, entry: str, root: ET.Element) -> None:
        if _local(root.tag) != "KNX":
            raise self._not_ets(entry, REASON_NOT_ETS_PROJECT, "Root element is not KNX; not an ETS project.")
        namespace = _namespace(root.tag)
        if namespace != SUPPORTED_NAMESPACE:
            raise self._not_ets(
                entry,
                REASON_UNSUPPORTED_NAMESPACE,
                f"Unsupported schema namespace {namespace!r}; only {SUPPORTED_NAMESPACE} (ETS 6) is supported.",
                namespace=namespace,
            )
        tool_version = root.get("ToolVersion")
        major = _int(tool_version.split(".", 1)[0]) if tool_version else None
        if major != SUPPORTED_MAJOR_VERSION:
            raise self._not_ets(
                entry,
                REASON_UNSUPPORTED_TOOL_VERSION,
                f"Unsupported ETS ToolVersion {tool_version!r}; only ETS 6 projects are supported.",
                tool_version=tool_version,
            )
        self.tool_version = tool_version
        self.created_by = root.get("CreatedBy")

    def _not_ets(self, entry: str, reason: str, message: str, **details: object) -> Exception:
        return error(PROJECT_PARSE_ERROR, message, reason=reason, path=str(self.archive.path), entry=entry, **details)

    def _read_project_xml(self) -> None:
        entry = self.archive.require(self.project_entry)
        root = self.archive.read_tree(entry, required=True)
        self._check_root(entry, root)
        project = next((child for child in root if _local(child.tag) == "Project"), None)
        if project is None or not project.get("Id"):
            raise self._not_ets(entry, REASON_NOT_ETS_PROJECT, "project.xml has no Project element with an Id.")
        self.project_id = project.get("Id")
        info = next((child for child in project if _local(child.tag) == "ProjectInformation"), None)
        if info is not None:
            self.project_name = info.get("Name")
            self.address_style = info.get("GroupAddressStyle")
            self.project_last_modified = info.get("LastModified")
            self.completion_status = info.get("CompletionStatus")

    def _note_additional_installations(self) -> None:
        for entry in self.archive.installation_entries():
            if entry != self.zero_entry:
                self.warn(
                    WARNING_ADDITIONAL_INSTALLATION_IGNORED,
                    "A further installation file exists and is ignored; only 0.xml is imported.",
                    entry,
                )

    # -- 0.xml ----------------------------------------------------------------------------------
    def _read_zero_xml(self) -> None:
        entry = self.archive.require(self.zero_entry)
        depth = 0
        skip_at: int | None = None
        scene_depth = 0
        for event, element in self.archive.iter_events(entry, required=True):
            tag = _local(element.tag)
            if event == "start":
                depth += 1
                if skip_at is not None:
                    continue
                if depth == 1:
                    self._check_root(entry, element)
                    continue
                if scene_depth:
                    scene_depth += 1
                    continue
                if tag == "Scene":
                    scene_depth = 1
                    continue
                if "scene" in tag.lower() and tag != "Scenes" and self.installation is not None:
                    self.scene_like.setdefault(tag, None)
                if not self._start(tag, element):
                    skip_at = depth
                continue
            # end event
            if skip_at is not None:
                if depth == skip_at:
                    skip_at = None
                depth -= 1
                continue
            if scene_depth:
                scene_depth -= 1
                if scene_depth == 0:
                    self._end_scene(element)
                depth -= 1
                continue
            self._end(tag, element)
            depth -= 1
        if self.installation is None:
            raise self._not_ets(entry, REASON_REQUIRED_PART_MALFORMED, "0.xml has no Installation element.")
        for tag in self.scene_like:
            self.warn(
                WARNING_UNSUPPORTED_ELEMENT,
                f"Scene-like element {tag} cannot be mapped and is ignored.",
                f"{entry}#{tag}",
            )

    def _start(self, tag: str, element: ET.Element) -> bool:
        """Handle a start event. Returns False when the element (and its subtree) must be skipped."""
        entry = self.zero_entry
        if tag == "Project":
            return True
        if tag == "Installation":
            if self.installation is not None:
                return False  # only the first installation of the file is imported
            stem = entry.rsplit("/", 1)[-1].removesuffix(".xml")
            stable = self._claim_composite(installation_id(self.folder, stem))
            self.installation = InstallationNode(
                id=stable.id,
                id_origin=stable.origin,
                source_part=entry,
                source_locator="Installation",
                fact_origin=FACT_ORIGIN_PROJECT,
                project_id=self.project_id,
                project_name=self.project_name,
                group_address_style=self.address_style,
                default_line_id=element.get("DefaultLine"),
                last_modified=self.project_last_modified,
                completion_status=self.completion_status,
                ets_tool_version=self.tool_version,
                created_by=self.created_by,
                schema_namespace=SUPPORTED_NAMESPACE,
            )
            self.nodes.append(self.installation)
            self._stack.append(_Frame("Installation", stable.id, "Installation"))
            return True
        if self.installation is None:
            return True
        parent = self._stack[-1] if self._stack else None
        if tag == "Area":
            address = _int(element.get("Address"))
            if address is None:
                self._invalid(element, "Address", f"Area[{self._position(self.installation.id, 'area')}]")
                return False
            stable, locator = self._stable_id(
                element, "area", self.installation.id, parent.locator if parent else "", address, element.get("Name")
            )
            self.nodes.append(
                AreaNode(
                    id=stable.id,
                    id_origin=stable.origin,
                    source_part=entry,
                    source_locator=locator,
                    fact_origin=FACT_ORIGIN_PROJECT,
                    installation_id=self.installation.id,
                    address=address,
                    name=element.get("Name"),
                )
            )
            self._stack.append(_Frame("Area", stable.id, locator, {"address": address}))
            return True
        if tag == "Line":
            area = self._nearest("Area")
            address = _int(element.get("Address"))
            parent_id = area.node_id if area and area.node_id else self.installation.id
            if address is None:
                self._invalid(element, "Address", f"Line[{self._position(parent_id, 'line')}]")
                return False
            stable, locator = self._stable_id(
                element, "line", parent_id, area.locator if area else "", address, element.get("Name")
            )
            self._stack.append(
                _Frame(
                    "Line",
                    stable.id,
                    locator,
                    {
                        "address": address,
                        "area_id": area.node_id if area else None,
                        "name": element.get("Name"),
                        "description": element.get("Description"),
                        "media": [],
                        "origin": stable.origin,
                    },
                )
            )
            return True
        if tag == "Segment":
            line = self._nearest("Line")
            medium = element.get("MediumTypeRefId")
            if line is not None and medium and medium not in line.extra["media"]:  # type: ignore[operator]
                line.extra["media"].append(medium)  # type: ignore[union-attr]
            self._stack.append(
                _Frame("Segment", element.get("Id") or None, f"Segment[@Id={element.get('Id')}]", {"medium": medium})
            )
            return True
        if tag == "Space":
            parent_space = self._nearest("Space")
            parent_id = parent_space.node_id if parent_space and parent_space.node_id else self.installation.id
            stable, locator = self._stable_id(
                element, "space", parent_id, parent_space.locator if parent_space else "", None, element.get("Name")
            )
            self.nodes.append(
                SpaceNode(
                    id=stable.id,
                    id_origin=stable.origin,
                    source_part=entry,
                    source_locator=locator,
                    fact_origin=FACT_ORIGIN_PROJECT,
                    parent_id=parent_space.node_id if parent_space else None,
                    space_type=element.get("Type"),
                    name=element.get("Name"),
                    usage_ref=element.get("Usage"),
                )
            )
            self._stack.append(_Frame("Space", stable.id, locator))
            return True
        if tag == "GroupRange":
            parent_range = self._nearest("GroupRange")
            parent_id = parent_range.node_id if parent_range and parent_range.node_id else self.installation.id
            start, end = _int(element.get("RangeStart")), _int(element.get("RangeEnd"))
            if start is None or end is None:
                self._invalid(
                    element, "RangeStart/RangeEnd", f"GroupRange[{self._position(parent_id, 'group_range')}]"
                )
                self._stack.append(_Frame("GroupRange", None, "GroupRange"))  # children attach to the grandparent
                return True
            stable, locator = self._stable_id(
                element,
                "group_range",
                parent_id,
                parent_range.locator if parent_range else "",
                start,
                element.get("Name"),
            )
            self.nodes.append(
                GroupRangeNode(
                    id=stable.id,
                    id_origin=stable.origin,
                    source_part=entry,
                    source_locator=locator,
                    fact_origin=FACT_ORIGIN_PROJECT,
                    parent_id=parent_range.node_id if parent_range else None,
                    range_start=start,
                    range_end=end,
                    name=element.get("Name"),
                    description=element.get("Description"),
                )
            )
            self._stack.append(_Frame("GroupRange", stable.id, locator))
            return True
        return True

    def _claim_composite(self, stable: StableId) -> StableId:
        unique, collided = self.allocator.claim(stable)
        if collided:
            self.warn(
                WARNING_DUPLICATE_ID,
                f"The ID {stable.id} occurs more than once; the later element gets {unique.id}.",
                f"{self.zero_entry}#{stable.id}",
            )
        return unique

    def _end(self, tag: str, element: ET.Element) -> None:
        if self.installation is None:
            return
        if tag in ("Installation", "Area", "Space", "GroupRange", "Segment") and self._stack:
            if self._stack[-1].tag == tag:
                self._stack.pop()
            return
        if tag == "Line":
            if self._stack and self._stack[-1].tag == "Line":
                frame = self._stack.pop()
                self.nodes.append(
                    LineNode(
                        id=frame.node_id or "",
                        id_origin=frame.extra["origin"],  # type: ignore[arg-type]
                        source_part=self.zero_entry,
                        source_locator=frame.locator,
                        fact_origin=FACT_ORIGIN_PROJECT,
                        area_id=frame.extra["area_id"],  # type: ignore[arg-type]
                        address=frame.extra["address"],  # type: ignore[arg-type]
                        name=frame.extra["name"],  # type: ignore[arg-type]
                        description=frame.extra["description"],  # type: ignore[arg-type]
                        medium_type_refs=list(frame.extra["media"]),  # type: ignore[call-overload]
                    )
                )
            return
        if tag == "DeviceInstance":
            self._end_device(element)
            element.clear()
        elif tag == "DeviceInstanceRef":
            space = self._nearest("Space")
            ref = element.get("RefId")
            if space is not None and space.node_id and ref:
                self.space_refs.append((space.node_id, ref, f"{self.zero_entry}#{space.node_id}"))
            element.clear()
        elif tag == "GroupAddress":
            self._end_group_address(element)
            element.clear()

    def _end_device(self, element: ET.Element) -> None:
        assert self.installation is not None
        line = self._nearest("Line")
        segment = next((f for f in reversed(self._stack) if f.tag == "Segment"), None)
        area = self._nearest("Area")
        address = _int(element.get("Address"))
        parent_id = line.node_id if line and line.node_id else self.installation.id
        if address is None:
            self._invalid(element, "Address", f"DeviceInstance[{self._position(parent_id, 'component')}]")
            return
        stable, locator = self._stable_id(
            element, "component", parent_id, line.locator if line else "", address, element.get("Name")
        )
        product = element.get("ProductRefId")
        hardware2program = element.get("Hardware2ProgramRefId")
        line_address = line.extra.get("address") if line else None
        area_address = area.extra.get("address") if area else None
        component = ComponentNode(
            id=stable.id,
            id_origin=stable.origin,
            source_part=self.zero_entry,
            source_locator=locator,
            fact_origin=FACT_ORIGIN_PROJECT,
            line_id=line.node_id if line else None,
            segment_id=segment.node_id if segment else None,
            medium_type_ref=segment.extra.get("medium") if segment else None,  # type: ignore[arg-type]
            address=address,
            individual_address=individual_address_text(area_address, line_address, address),  # type: ignore[arg-type]
            name=element.get("Name"),
            description=element.get("Description"),
            comment=element.get("Comment"),
            product_ref_id=product,
            hardware2program_ref_id=hardware2program,
            manufacturer_id=_manufacturer_of(product, hardware2program),
            has_ip_config=any(_local(child.tag) == "IPConfig" for child in element),
            serial_number=element.get("SerialNumber"),
            last_modified=element.get("LastModified"),
            last_download=element.get("LastDownload"),
            load_state=LoadState(
                application_program_loaded=_bool(element.get("ApplicationProgramLoaded")),
                communication_part_loaded=_bool(element.get("CommunicationPartLoaded")),
                individual_address_loaded=_bool(element.get("IndividualAddressLoaded")),
                medium_config_loaded=_bool(element.get("MediumConfigLoaded")),
                parameters_loaded=_bool(element.get("ParametersLoaded")),
            ),
        )
        self.nodes.append(component)
        self.components[component.id] = component
        self.component_locators[component.id] = locator
        objects: list[_RawObject] = []
        parameters: list[_RawParameter] = []
        for child in element:
            child_tag = _local(child.tag)
            if child_tag == "ComObjectInstanceRefs":
                for ref in child:
                    ref_id = ref.get("RefId")
                    if _local(ref.tag) == "ComObjectInstanceRef" and ref_id:
                        objects.append(
                            _RawObject(
                                ref_id=ref_id,
                                links=(ref.get("Links") or "").split(),
                                channel_id=ref.get("ChannelId"),
                                description=ref.get("Description"),
                                text=ref.get("Text"),
                                locator=f"ComObjectInstanceRef[@RefId={ref_id}]",
                            )
                        )
            elif child_tag == "ParameterInstanceRefs":
                for ref in child:
                    ref_id = ref.get("RefId")
                    if _local(ref.tag) == "ParameterInstanceRef" and ref_id:
                        parameters.append(
                            _RawParameter(ref_id, ref.get("Value"), f"ParameterInstanceRef[@RefId={ref_id}]")
                        )
        self.raw_objects[component.id] = objects
        self.raw_parameters[component.id] = parameters

    def _end_group_address(self, element: ET.Element) -> None:
        assert self.installation is not None
        group_range = self._nearest("GroupRange")
        parent_id = group_range.node_id if group_range and group_range.node_id else self.installation.id
        raw = _int(element.get("Address"))
        if raw is None or not 0 <= raw <= 0xFFFF:
            self._invalid(element, "Address", f"GroupAddress[{self._position(parent_id, 'group_address')}]")
            return
        stable, locator = self._stable_id(
            element,
            "group_address",
            parent_id,
            group_range.locator if group_range else "",
            raw,
            element.get("Name"),
        )
        node = GroupAddressNode(
            id=stable.id,
            id_origin=stable.origin,
            source_part=self.zero_entry,
            source_locator=locator,
            fact_origin=FACT_ORIGIN_PROJECT,
            address_raw=raw,
            address=format_group_address(raw, self.address_style),
            name=element.get("Name"),
            description=element.get("Description"),
            datapoint_type=element.get("DatapointType"),
            range_id=group_range.node_id if group_range else None,
        )
        self.nodes.append(node)
        self.group_addresses[node.id] = node

    def _end_scene(self, element: ET.Element) -> None:
        assert self.installation is not None
        number = _int(element.get("Number"))
        name = element.get("Name")
        stable, locator = self._stable_id(element, "scene", self.installation.id, "Installation", number, name)
        members = [child.get("RefId") for child in element.iter() if child is not element and child.get("RefId")]
        self.nodes.append(
            SceneNode(
                id=stable.id,
                id_origin=stable.origin,
                source_part=self.zero_entry,
                source_locator=locator,
                fact_origin=FACT_ORIGIN_PROJECT,
                name=name,
                scene_number=number,
                members=members,  # type: ignore[arg-type]
            )
        )
        element.clear()

    # -- optional parts -------------------------------------------------------------------------
    def _skip_optional(self, entry: str, reason: str) -> None:
        self.warn(
            WARNING_OPTIONAL_PART_UNREADABLE,
            f"Optional part skipped (reason: {reason})",
            entry,
        )

    def _read_master(self) -> None:
        if not self.archive.has(MASTER_ENTRY):
            self.warn(
                WARNING_OPTIONAL_PART_MISSING,
                "Optional part knx_master.xml is not in the archive; datapoint types are not verified.",
                MASTER_ENTRY,
            )
            return
        found: set[str] = set()
        try:
            for _event, element in self.archive.iter_events(MASTER_ENTRY, required=False, events=("end",)):
                if _local(element.tag) in ("DatapointType", "DatapointSubtype") and element.get("Id"):
                    found.add(element.get("Id"))  # type: ignore[arg-type]
        except OptionalPartRejected as rejected:
            self._skip_optional(MASTER_ENTRY, rejected.reason)
            return
        self.master_ids = found

    def _hardware_for(self, manufacturer: str) -> _Hardware:
        cached = self.hardware.get(manufacturer)
        if cached is not None:
            return cached
        entry = f"{manufacturer}/Hardware.xml"
        if not self.archive.has(entry):
            self.warn(
                WARNING_OPTIONAL_PART_MISSING,
                f"Optional part {entry} is not in the archive; the catalog references of {manufacturer} cannot be resolved.",
                entry,
            )
            result = _Hardware("missing")
        else:
            programs: dict[str, str] = {}
            products: dict[str, tuple[str | None, str | None]] = {}
            try:
                for _event, element in self.archive.iter_events(entry, required=False, events=("end",)):
                    tag = _local(element.tag)
                    if tag == "Hardware2Program" and element.get("Id"):
                        ref = next((c for c in element if _local(c.tag) == "ApplicationProgramRef"), None)
                        if ref is not None and ref.get("RefId"):
                            programs[element.get("Id")] = ref.get("RefId")  # type: ignore[index]
                    elif tag == "Product" and element.get("Id"):
                        products[element.get("Id")] = (element.get("Text"), element.get("OrderNumber"))  # type: ignore[index]
                result = _Hardware("ok", programs, products)
            except OptionalPartRejected as rejected:
                self._skip_optional(entry, rejected.reason)
                result = _Hardware("unreadable")
        self.hardware[manufacturer] = result
        return result

    # -- application program resolution ---------------------------------------------------------
    def _resolve_components(self) -> None:
        for component_id in sorted(self.components):
            component = self.components[component_id]
            location = self._node_location(component_id)
            resolution = _Resolution()
            self.resolutions[component_id] = resolution
            hardware2program = component.hardware2program_ref_id
            product = component.product_ref_id
            product_manufacturer = _manufacturer_of(product)
            program_manufacturer = _manufacturer_of(hardware2program, product)
            unresolved: list[str] = []

            # product text and order number (ProductRefId is never a path to the program)
            if product and product_manufacturer:
                catalog = self._hardware_for(product_manufacturer)
                if catalog.status == "ok":
                    found = catalog.products.get(product)
                    if found is None:
                        unresolved.append(f"product {product}")
                    else:
                        component.product_text, component.order_number = found
            elif product:
                unresolved.append(f"product {product}")

            p1: str | None = None
            if hardware2program and program_manufacturer:
                hardware = self._hardware_for(program_manufacturer)
                if hardware.status == "ok":
                    p1 = hardware.programs.get(hardware2program)
                    if p1 is None:
                        unresolved.append(f"hardware-to-program reference {hardware2program}")
            p2 = derive_program_id_from_hardware2program(hardware2program) if hardware2program else None
            manufacturer = program_manufacturer or ""

            if p1 is not None:
                resolution.program_id = p1
                if p2 is not None and p2 != p1:
                    self.warn(
                        WARNING_APPLICATION_PROGRAM_REFERENCE_MISMATCH,
                        f"Catalog gives application program {p1} but the reference text suggests {p2}; the catalog wins.",
                        location,
                    )
            elif p2 is not None and self.archive.has(f"{manufacturer}/{p2}.xml"):
                resolution.program_id = p2
            if unresolved:
                self.warn(
                    WARNING_PRODUCT_REFERENCE_UNRESOLVED,
                    "Not found in the catalog: " + "; ".join(unresolved) + ".",
                    location,
                )
            program_id = resolution.program_id
            if program_id is not None:
                resolution.entry = f"{manufacturer}/{program_id}.xml"
                component.application_program_id = program_id
                if self.archive.has(resolution.entry):
                    resolution.status = "read"  # tentative; becomes 'unreadable' if the program is rejected
                else:
                    resolution.status = "missing"
            if resolution.status == "missing":
                self.warn(
                    WARNING_APPLICATION_PROGRAM_MISSING,
                    "The application program of the component is not in the archive; its objects and parameters stay unresolved."
                    if program_id
                    else "No application program could be determined for the component; its objects and parameters stay unresolved.",
                    location,
                )
                continue
            prefixes = {
                reference_program_prefix(raw.ref_id)
                for raw in self.raw_parameters.get(component_id, [])
                if reference_program_prefix(raw.ref_id) is not None
            }
            if any(prefix != program_id for prefix in prefixes):
                resolution.mismatch_parameters = True
                self.warn(
                    WARNING_APPLICATION_PROGRAM_REFERENCE_MISMATCH,
                    f"Parameter references of the component name another application program than {program_id}; "
                    "those parameters stay unresolved.",
                    location,
                )

    def _read_programs(self) -> None:
        needs: dict[str, tuple[str, set[str], set[str], set[str], set[str]]] = {}
        for component_id in sorted(self.components):
            resolution = self.resolutions[component_id]
            if resolution.status != "read" or resolution.program_id is None or resolution.entry is None:
                continue
            program_id = resolution.program_id
            entry = needs.setdefault(program_id, (resolution.entry, set(), set(), set(), set()))
            for raw in self.raw_objects.get(component_id, []):
                full = f"{program_id}_{raw.ref_id}"
                entry[1].add(full)
                entry[2].add(full.rsplit("_R-", 1)[0])
            for raw_parameter in self.raw_parameters.get(component_id, []):
                prefix = reference_program_prefix(raw_parameter.ref_id)
                if prefix is not None and prefix != program_id:
                    continue
                entry[3].add(raw_parameter.ref_id)
                entry[4].add(raw_parameter.ref_id.rsplit("_R-", 1)[0])
        for program_id in sorted(needs):
            entry_name, ref_ids, object_ids, parameter_ref_ids, parameter_ids = needs[program_id]
            defs = self._stream_program(entry_name, ref_ids, object_ids, parameter_ref_ids, parameter_ids)
            if defs is None:
                self.unreadable_programs.add(program_id)
                for component_id, resolution in self.resolutions.items():
                    if resolution.program_id == program_id and resolution.status == "read":
                        resolution.status = "unreadable"
            else:
                self.programs[program_id] = defs
                self.read_programs.append(program_id)

    def _stream_program(
        self,
        entry: str,
        ref_ids: set[str],
        object_ids: set[str],
        parameter_ref_ids: set[str],
        parameter_ids: set[str],
    ) -> _ProgramDefs | None:
        defs = _ProgramDefs()
        try:
            for event, element in self.archive.iter_events(entry, required=False, events=("start", "end")):
                tag = _local(element.tag)
                if event == "start":
                    if tag == "ApplicationProgram":
                        defs.attrs = dict(element.attrib)
                    continue
                identifier = element.get("Id", "")
                if tag == "ComObject":
                    if identifier in object_ids:
                        defs.comobjects[identifier] = dict(element.attrib)
                elif tag == "ComObjectRef":
                    if identifier in ref_ids:
                        defs.comobject_refs[identifier] = dict(element.attrib)
                elif tag == "Parameter":
                    if identifier in parameter_ids:
                        defs.parameters[identifier] = dict(element.attrib)
                elif tag == "ParameterRef":
                    if identifier in parameter_ref_ids:
                        defs.parameter_refs[identifier] = dict(element.attrib)
                element.clear()
        except OptionalPartRejected as rejected:
            self._skip_optional(entry, rejected.reason)
            return None
        return defs

    # -- assembly -------------------------------------------------------------------------------
    def _assemble(self) -> SourceFacts:
        assert self.installation is not None
        ga_ids = set(self.group_addresses)
        membership: list[MembershipRelation] = []
        unknown_datapoint: dict[str, str] = {}

        def check_datapoint(token: str, node_id: str) -> None:
            if self.master_ids is not None and token not in self.master_ids and token not in unknown_datapoint:
                unknown_datapoint[token] = node_id

        for ga in self.group_addresses.values():
            for token in (ga.datapoint_type or "").split():
                check_datapoint(token, ga.id)

        for component_id in sorted(self.components):
            component = self.components[component_id]
            resolution = self.resolutions[component_id]
            defs = self.programs.get(resolution.program_id or "")
            warn_unresolved = resolution.status in ("read", "unreadable")
            for raw in self.raw_objects.get(component_id, []):
                stable = self._claim_composite_child(communication_object_id(component_id, raw.ref_id))
                merged: dict[str, str] = {}
                resolved = False
                if defs is not None:
                    reference = defs.comobject_refs.get(f"{resolution.program_id}_{raw.ref_id}")
                    definition = defs.comobjects.get(reference.get("RefId", "")) if reference else None
                    if definition is None and reference is not None:
                        definition = defs.comobjects.get(f"{resolution.program_id}_{raw.ref_id}".rsplit("_R-", 1)[0])
                    if reference is not None and definition is not None:
                        merged = {**definition, **{k: v for k, v in reference.items() if k not in ("Id", "RefId")}}
                        resolved = True
                datapoints = merged.get("DatapointType", "").split()
                node = CommunicationObjectNode(
                    id=stable.id,
                    id_origin=stable.origin,
                    source_part=self.zero_entry,
                    source_locator=f"{self.component_locators[component_id]}/{raw.locator}",
                    fact_origin=FACT_ORIGIN_PROJECT,
                    component_id=component_id,
                    ref_id=raw.ref_id,
                    object_number=_int(merged.get("Number")),
                    function_text=merged.get("FunctionText"),
                    text=merged.get("Text"),
                    object_size=merged.get("ObjectSize"),
                    datapoint_types=datapoints,
                    channel_id=raw.channel_id,
                    description=raw.description,
                    instance_text=raw.text,
                    definition_resolved=resolved,
                    **{field_name: merged.get(attribute) for field_name, attribute in _FLAG_KEYS.items()},
                )
                self.nodes.append(node)
                if not resolved and warn_unresolved:
                    self.warn(
                        WARNING_COMOBJECT_DEFINITION_UNRESOLVED,
                        f"Communication object {raw.ref_id} has no definition in application program {resolution.program_id}.",
                        self._node_location(node.id),
                    )
                for token in datapoints:
                    check_datapoint(token, node.id)
                for order, link in enumerate(raw.links):
                    ga_id = f"{self.installation.id}_{link}"
                    if ga_id in ga_ids:
                        membership.append(
                            MembershipRelation(communication_object_id=node.id, group_address_id=ga_id, order=order)
                        )
                    else:
                        self.warn(
                            WARNING_GROUP_ADDRESS_LINK_UNRESOLVED,
                            f"Link {link} names a group address that does not exist; no membership is created.",
                            self._node_location(node.id),
                        )
            for raw_parameter in self.raw_parameters.get(component_id, []):
                stable = self._claim_composite_child(parameter_node_id(component_id, raw_parameter.ref_id))
                reference = None
                definition = None
                prefix = reference_program_prefix(raw_parameter.ref_id)
                if defs is not None and (prefix is None or prefix == resolution.program_id):
                    reference = defs.parameter_refs.get(raw_parameter.ref_id)
                    if reference is not None:
                        definition = defs.parameters.get(
                            reference.get("RefId", ""), defs.parameters.get(raw_parameter.ref_id.rsplit("_R-", 1)[0])
                        )
                resolved_parameter = reference is not None and definition is not None
                name = text = type_id = parameter_id = None
                if resolved_parameter:
                    assert reference is not None and definition is not None
                    parameter_id = definition.get("Id")
                    name = reference.get("Name", definition.get("Name"))
                    text = reference.get("Text", definition.get("Text"))
                    type_id = definition.get("ParameterType")
                self.nodes.append(
                    ParameterNode(
                        id=stable.id,
                        id_origin=stable.origin,
                        source_part=self.zero_entry,
                        source_locator=f"{self.component_locators[component_id]}/{raw_parameter.locator}",
                        fact_origin=FACT_ORIGIN_PROJECT,
                        component_id=component_id,
                        ref_id=raw_parameter.ref_id,
                        parameter_id=parameter_id,
                        name=name,
                        text=text,
                        parameter_type_id=type_id,
                        value=raw_parameter.value,
                        definition_resolved=resolved_parameter,
                    )
                )
                if not resolved_parameter and warn_unresolved:
                    self.warn(
                        WARNING_PARAMETER_DEFINITION_UNRESOLVED,
                        f"Parameter {raw_parameter.ref_id} has no definition in application program {resolution.program_id}.",
                        self._node_location(stable.id),
                    )

        for token, node_id in unknown_datapoint.items():
            self.warn(
                WARNING_DATAPOINT_TYPE_UNKNOWN,
                f"Datapoint type {token} is not defined in knx_master.xml.",
                self._node_location(node_id),
            )

        placed: list[PlacedInRelation] = []
        seen_placements: set[tuple[str, str]] = set()
        for space_id, component_id, location in self.space_refs:
            if component_id not in self.components:
                self.warn(
                    WARNING_DEVICE_REFERENCE_UNRESOLVED,
                    f"Space {space_id} refers to component {component_id}, which does not exist.",
                    location,
                )
            elif (space_id, component_id) not in seen_placements:
                seen_placements.add((space_id, component_id))
                placed.append(PlacedInRelation(space_id=space_id, component_id=component_id))

        program_ids = sorted(
            {r.program_id for r in self.resolutions.values() if r.program_id is not None}
        )
        for program_id in program_ids:
            defs = self.programs.get(program_id)
            entry = next(r.entry for r in self.resolutions.values() if r.program_id == program_id)
            attrs = defs.attrs if defs else {}
            stable = application_program_node_id(program_id)
            stable = self._claim_composite_child(stable)
            self.nodes.append(
                ApplicationProgramNode(
                    id=stable.id,
                    id_origin=stable.origin,
                    source_part=entry or "",
                    source_locator=f"ApplicationProgram[@Id={program_id}]",
                    fact_origin=FACT_ORIGIN_CATALOG,
                    manufacturer_id=_manufacturer_of(program_id),
                    application_number=_int(attrs.get("ApplicationNumber")),
                    application_version=_int(attrs.get("ApplicationVersion")),
                    mask_version=attrs.get("MaskVersion"),
                    name=attrs.get("Name"),
                    source_loaded=defs is not None,
                )
            )

        return SourceFacts(
            nodes=sort_nodes(self.nodes),  # type: ignore[arg-type]
            relations=Relations(
                membership=sorted(membership, key=membership_sort_key),
                placed_in=sorted(placed, key=placed_in_sort_key),
            ),
        )

    def _claim_composite_child(self, stable: StableId) -> StableId:
        return self._claim_composite(stable)

    # -- driver ---------------------------------------------------------------------------------
    def run(self) -> ParsedProject:
        self._read_project_xml()
        self._note_additional_installations()
        self._read_zero_xml()
        self._read_master()
        self._resolve_components()
        self._read_programs()
        source_facts = self._assemble()
        referenced = sorted({r.program_id for r in self.resolutions.values() if r.program_id is not None})
        counts = ApplicationProgramCounts(
            referenced=len(referenced), read=len(self.read_programs), unreadable=len(self.unreadable_programs)
        )
        return ParsedProject(
            source_facts=source_facts,
            warnings=self.warnings,
            application_programs=counts,
            read_programs=list(self.read_programs),
        )


def parse_project(archive: KnxprojArchive) -> ParsedProject:
    """Parse a guarded archive into source facts and warnings (required parts fail with PROJECT_PARSE_ERROR)."""
    return _Parser(archive).run()
