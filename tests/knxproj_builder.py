"""Synthetic ETS 6 .knxproj archives for tests (story 04, T4).

Builds small VALID archives in a temporary folder from a Python/YAML description (``default_spec()`` plus a
``patch``), then applies named mutations that produce every error and warning case. Only ``zipfile`` is used;
nothing is extracted. Imported by tests like conftest helpers: ``from knxproj_builder import build_project``.

Description (all keys optional in a patch; lists replace, mappings merge)::

    project_id, project_name, address_style, tool_version, namespace
    areas: [{address, name, lines: [{address, name, medium, components: [component...]}]}]
    component: {address, name, product, hardware2program, objects: [{ref, links, channel, description, text}],
                parameters: [{ref, value}], ip_config, id, omit_id}
    group_ranges: [{id, start, end, name, ranges: [...], addresses: [{id, address, name, dpt, description}]}]
    spaces: [{type, id, name, usage, devices: [short or full component id], children: [...]}]
    scenes: [{name, number, members: [ref]}]
    catalog: {hardware_xml, master, manufacturers: [{id, hardware: [...], applications: [...]}]}
    master_datapoints: [ids]
    Short ids ('GA-1', 'DI-2') are prefixed with '<project id>-0_' in the XML.

Mutations (``apply_mutations``): remove, doctype, entity, utf16, encoding_declaration, malform, replace,
append_entry, encrypt, duplicate, many_entries, big_entry, ratio_entry, second_installation,
second_project_folder, rename_project_folder, empty_entry. Entry arguments accept aliases: project_xml, zero_xml,
hardware_xml[:M-id], application_xml[:app id], master_xml, or a literal entry name.
"""

from __future__ import annotations

import copy
import random
import struct
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import quoteattr

NAMESPACE = "http://knx.org/xml/project/22"
TOOL_VERSION = "6.1.5686.0"
XML_DECLARATION = '<?xml version="1.0" encoding="utf-8"?>\r\n'
FLAG_NAMES = {
    "read": "ReadFlag",
    "write": "WriteFlag",
    "communication": "CommunicationFlag",
    "transmit": "TransmitFlag",
    "update": "UpdateFlag",
    "read_on_init": "ReadOnInitFlag",
}


# -- description --------------------------------------------------------------------------------
def _flags(kind: str) -> dict[str, str]:
    base = {"read": "Disabled", "write": "Disabled", "communication": "Enabled", "transmit": "Disabled",
            "update": "Disabled", "read_on_init": "Disabled"}  # fmt: skip
    if kind in ("tx", "both"):
        base["transmit"] = "Enabled"
    if kind in ("rx", "both"):
        base["write"] = "Enabled"
    return base


def _obj(number: int, text: str, kind: str, dpt: str) -> dict:
    return {"n": number, "text": text, "function_text": text, "size": "1 Bit", "dpt": dpt, "flags": _flags(kind)}


def default_spec() -> dict:
    """A small valid ETS 6 project: 3 components, 6 communication objects, 3 group addresses, 2 programs used."""
    app1, app2, app3 = "M-0001_A-0001-01-AAAA", "M-0001_A-0002-01-BBBB", "M-0001_A-0003-01-CCCC"
    return {
        "project_id": "P-0001",
        "project_name": "Synthetic house",
        "address_style": "ThreeLevel",
        "tool_version": TOOL_VERSION,
        "namespace": NAMESPACE,
        "areas": [
            {
                "address": 1,
                "name": "Area one",
                "lines": [
                    {
                        "address": 1,
                        "name": "Line one",
                        "medium": "MT-0",
                        "components": [
                            {
                                "address": 1,
                                "name": "Sensor",
                                "product": "M-0001_H-1_P-S1",
                                "hardware2program": "M-0001_H-1_HP-0001-01-AAAA",
                                "objects": [
                                    {"ref": "O-0_R-1", "links": ["GA-1"]},
                                    {"ref": "O-1_R-2", "links": ["GA-2"]},
                                ],
                                "parameters": [],
                            },
                            {
                                "address": 2,
                                "name": "Controller",
                                "product": "M-0001_H-1_P-S1",
                                "hardware2program": "M-0001_H-1_HP-0001-01-AAAA",
                                "objects": [
                                    {"ref": "O-2_R-3", "links": ["GA-1", "GA-3"]},
                                    {"ref": "O-3_R-4", "links": []},
                                ],
                                "parameters": [
                                    {"ref": f"{app1}_P-1_R-1", "value": "5"},
                                    {"ref": f"{app1}_P-2_R-2", "value": "7"},
                                ],
                            },
                            {
                                "address": 3,
                                "name": "Actuator",
                                "product": "M-0001_H-2_P-S2",
                                "hardware2program": "M-0001_H-2_HP-0002-01-BBBB",
                                "objects": [{"ref": "O-0_R-1", "links": []}, {"ref": "O-1_R-2", "links": []}],
                                "parameters": [],
                            },
                        ],
                    }
                ],
            }
        ],
        "group_ranges": [
            {
                "id": "GR-1",
                "start": 0,
                "end": 2047,
                "name": "Main group",
                "ranges": [
                    {
                        "id": "GR-2",
                        "start": 0,
                        "end": 255,
                        "name": "Middle group",
                        "addresses": [
                            {"id": "GA-1", "address": 1, "name": "Light", "dpt": "DPST-1-1"},
                            {"id": "GA-2", "address": 2, "name": "Brightness", "dpt": "DPST-5-1"},
                            {"id": "GA-3", "address": 3, "name": "Status"},
                        ],
                    }
                ],
            }
        ],
        "spaces": [
            {
                "type": "Building",
                "id": "BP-1",
                "name": "House",
                "children": [
                    {
                        "type": "Floor",
                        "id": "BP-2",
                        "name": "Ground floor",
                        "children": [
                            {"type": "Room", "id": "BP-3", "name": "Hall", "usage": "SU-1", "devices": ["DI-1", "DI-2"]}
                        ],
                    }
                ],
            }
        ],
        "scenes": [],
        "master_datapoints": ["DPT-1", "DPST-1-1", "DPST-1-2", "DPT-5", "DPST-5-1"],
        "catalog": {
            "hardware_xml": True,
            "master": True,
            "manufacturers": [
                {
                    "id": "M-0001",
                    "hardware": [
                        {
                            "id": "M-0001_H-1",
                            "product": {"id": "M-0001_H-1_P-S1", "text": "Sensor product", "order": "SW-1"},
                            "programs": [{"id": "M-0001_H-1_HP-0001-01-AAAA", "app": app1}],
                        },
                        {
                            "id": "M-0001_H-2",
                            "product": {"id": "M-0001_H-2_P-S2", "text": "Actuator product", "order": "AC-2"},
                            "programs": [{"id": "M-0001_H-2_HP-0002-01-BBBB", "app": app2}],
                        },
                        {
                            "id": "M-0001_H-3",
                            "product": {"id": "M-0001_H-3_P-S3", "text": "Unused product", "order": "UN-3"},
                            "programs": [{"id": "M-0001_H-3_HP-0003-01-CCCC", "app": app3}],
                        },
                    ],
                    "applications": [
                        {
                            "id": app1,
                            "number": 1,
                            "version": 1,
                            "mask": "MV-0705",
                            "name": "Sensor application",
                            "objects": [
                                _obj(0, "Switch input", "tx", "DPST-1-1"),
                                _obj(1, "Value input", "tx", "DPST-5-1"),
                                _obj(2, "Switch output", "rx", "DPST-1-1"),
                                _obj(3, "Status", "tx", "DPST-1-1"),
                            ],
                            "parameters": [
                                {"p": 1, "name": "Delay", "type": "PT-Time", "text": "Delay time"},
                                {"p": 2, "name": "Mode", "type": "PT-Mode", "text": "Operating mode"},
                            ],
                            "filler": 0,
                        },
                        {
                            "id": app2,
                            "number": 2,
                            "version": 1,
                            "mask": "MV-0705",
                            "name": "Actuator application",
                            "objects": [_obj(0, "Switch", "rx", "DPST-1-1"), _obj(1, "Value", "rx", "DPST-5-1")],
                            "parameters": [],
                            "filler": 0,
                        },
                        {
                            "id": app3,
                            "number": 3,
                            "version": 1,
                            "mask": "MV-0705",
                            "name": "Unreferenced application",
                            "objects": [_obj(0, "Unused", "tx", "DPST-1-1")],
                            "parameters": [],
                            "filler": 0,
                        },
                    ],
                }
            ],
        },
    }


def merge_spec(base: dict, patch: dict | None) -> dict:
    """Deep copy of ``base`` with ``patch`` merged in (mappings merge, everything else is replaced)."""
    result = copy.deepcopy(base)

    def merge(target: dict, source: dict) -> None:
        for key, value in source.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                merge(target[key], value)
            else:
                target[key] = copy.deepcopy(value)

    merge(result, patch or {})
    return result


# -- XML ----------------------------------------------------------------------------------------
def _attrs(values: dict) -> str:
    return "".join(f" {key}={quoteattr(str(value))}" for key, value in values.items() if value is not None)


def _element(tag: str, attributes: dict, children: str = "") -> str:
    if children:
        return f"<{tag}{_attrs(attributes)}>{children}</{tag}>"
    return f"<{tag}{_attrs(attributes)}/>"


def _document(spec: dict, body: str) -> bytes:
    root_attrs = {"CreatedBy": "ETS6", "ToolVersion": spec.get("tool_version", TOOL_VERSION)}
    if spec.get("tool_version", TOOL_VERSION) is None:
        root_attrs.pop("ToolVersion")
    namespace = spec.get("namespace", NAMESPACE)
    xmlns = f" xmlns={quoteattr(namespace)}" if namespace else ""
    root_tag = spec.get("root_tag", "KNX")
    text = f"{XML_DECLARATION}<{root_tag}{xmlns}{_attrs(root_attrs)}>{body}</{root_tag}>"
    return b"\xef\xbb\xbf" + text.encode("utf-8")


def _full_id(spec: dict, short: str) -> str:
    return short if "_" in short else f"{spec['project_id']}-0_{short}"


def _project_xml(spec: dict) -> bytes:
    info = _element(
        "ProjectInformation",
        {
            "Name": spec["project_name"],
            "GroupAddressStyle": spec["address_style"],
            "LastModified": "2026-01-01T00:00:00Z",
            "CompletionStatus": "Editing",
        },
    )
    project = _element("Project", {"Id": spec["project_id"]} if not spec.get("no_project_id") else {}, info)
    if spec.get("no_project_element"):
        project = ""
    return _document(spec, project)


class _Ids:
    def __init__(self, spec: dict) -> None:
        self.prefix = f"{spec['project_id']}-0"
        self.counters: dict[str, int] = {}

    def next(self, kind: str) -> str:
        self.counters[kind] = self.counters.get(kind, 0) + 1
        return f"{self.prefix}_{kind}-{self.counters[kind]}"


def _component_xml(spec: dict, component: dict, ids: _Ids) -> str:
    automatic = ids.next("DI")  # the counter always advances so explicit ids do not shift later components
    identifier = _full_id(spec, component["id"]) if component.get("id") else automatic
    attributes = {
        "Id": None if component.get("omit_id") else identifier,
        "Address": component.get("address"),
        "Name": component.get("name"),
        "ProductRefId": component.get("product"),
        "Hardware2ProgramRefId": component.get("hardware2program"),
        "Comment": "",
        "Description": component.get("description", ""),
        "ApplicationProgramLoaded": "true",
        "CommunicationPartLoaded": "true",
        "IndividualAddressLoaded": "true",
        "MediumConfigLoaded": "true",
        "ParametersLoaded": "true",
        "LastModified": "2026-01-01T00:00:00Z",
        **component.get("attrs", {}),
    }
    for dropped in component.get("drop_attrs", []):
        attributes.pop(dropped, None)
    children = ""
    if component.get("parameters"):
        children += _element(
            "ParameterInstanceRefs",
            {},
            "".join(_element("ParameterInstanceRef", {"RefId": p["ref"], "Value": p.get("value", "0")}) for p in component["parameters"]),
        )
    if component.get("objects"):
        refs = ""
        for obj in component["objects"]:
            links = " ".join(obj.get("links", []))
            refs += _element(
                "ComObjectInstanceRef",
                {
                    "RefId": obj["ref"],
                    "Links": links or None,
                    "ChannelId": obj.get("channel"),
                    "Description": obj.get("description"),
                    "Text": obj.get("text"),
                },
            )
        children += _element("ComObjectInstanceRefs", {}, refs)
    if component.get("ip_config"):
        children += _element("IPConfig", {"Assign": "Fixed", "IPAddress": "192.0.2.10"})
    return _element("DeviceInstance", attributes, children)


def _group_range_xml(spec: dict, group_range: dict) -> str:
    inner = ""
    for sub in group_range.get("ranges", []):
        inner += _group_range_xml(spec, sub)
    for address in group_range.get("addresses", []):
        inner += _element(
            "GroupAddress",
            {
                "Id": None if address.get("omit_id") else _full_id(spec, address["id"]),
                "Address": address.get("address"),
                "Name": address.get("name"),
                "Description": address.get("description"),
                "DatapointType": address.get("dpt"),
            },
        )
    return _element(
        "GroupRange",
        {
            "Id": _full_id(spec, group_range["id"]),
            "RangeStart": group_range.get("start"),
            "RangeEnd": group_range.get("end"),
            "Name": group_range.get("name"),
        },
        inner,
    )


def _space_xml(spec: dict, space: dict) -> str:
    inner = "".join(
        _element("DeviceInstanceRef", {"RefId": _full_id(spec, device)}) for device in space.get("devices", [])
    )
    inner += "".join(_space_xml(spec, child) for child in space.get("children", []))
    return _element(
        "Space",
        {
            "Type": space.get("type"),
            "Id": None if space.get("omit_id") else _full_id(spec, space["id"]),
            "Name": space.get("name"),
            "Usage": space.get("usage"),
        },
        inner,
    )


def _zero_xml(spec: dict) -> bytes:
    ids = _Ids(spec)
    topology = ""
    for area in spec["areas"]:
        lines = ""
        for line in area["lines"]:
            components = "".join(_component_xml(spec, c, ids) for c in line.get("components", []))
            segment = _element(
                "Segment",
                {"Id": ids.next("S"), "Name": "Segment", "Number": 0, "MediumTypeRefId": line.get("medium", "MT-0")},
                components,
            )
            lines += _element(
                "Line",
                {
                    "Id": None if line.get("omit_id") else ids.next("L"),
                    "Address": line.get("address"),
                    "Name": line.get("name"),
                    "Description": line.get("description"),
                },
                segment,
            )
        topology += _element(
            "Area",
            {
                "Id": None if area.get("omit_id") else ids.next("A"),
                "Address": area.get("address"),
                "Name": area.get("name"),
            },
            lines,
        )
    locations = "".join(_space_xml(spec, space) for space in spec.get("spaces", []))
    ranges = "".join(_group_range_xml(spec, r) for r in spec.get("group_ranges", []))
    scenes = ""
    for scene in spec.get("scenes", []):
        members = "".join(_element("SceneMember", {"RefId": ref}) for ref in scene.get("members", []))
        scenes += _element("Scene", {"Name": scene.get("name"), "Number": scene.get("number")}, members)
    installation = _element(
        "Installation",
        {"Name": "", "DefaultLine": f"{ids.prefix}_L-1"},
        _element("Topology", {}, topology)
        + _element("Locations", {}, locations)
        + _element("GroupAddresses", {}, _element("GroupRanges", {}, ranges))
        + scenes,
    )
    project = _element("Project", {"Id": spec["project_id"]}, _element("Installations", {}, installation))
    return _document(spec, project)


def _hardware_xml(spec: dict, manufacturer: dict) -> bytes:
    hardware = ""
    for item in manufacturer["hardware"]:
        product = item["product"]
        products = _element(
            "Products", {}, _element("Product", {"Id": product["id"], "Text": product.get("text"), "OrderNumber": product.get("order")})
        )
        programs = "".join(
            _element("Hardware2Program", {"Id": p["id"], "MediumTypes": "MT-0"}, _element("ApplicationProgramRef", {"RefId": p["app"]}))
            for p in item["programs"]
        )
        hardware += _element(
            "Hardware", {"Id": item["id"], "Name": item["id"]}, products + _element("Hardware2Programs", {}, programs)
        )
    body = _element(
        "ManufacturerData", {}, _element("Manufacturer", {"RefId": manufacturer["id"]}, _element("Hardware", {}, hardware))
    )
    return _document(spec, body)


def _application_xml(spec: dict, manufacturer: dict, app: dict) -> bytes:
    app_id = app["id"]
    comobjects, comobject_refs = "", ""
    for obj in app["objects"]:
        number = obj["n"]
        attributes = {
            "Id": f"{app_id}_O-{number}",
            "Name": f"Object{number}",
            "Text": obj.get("text"),
            "Number": number,
            "FunctionText": obj.get("function_text"),
            "ObjectSize": obj.get("size"),
            **{FLAG_NAMES[key]: value for key, value in obj.get("flags", {}).items()},
            "DatapointType": obj.get("dpt"),
        }
        comobjects += _element("ComObject", attributes)
        reference = obj.get("r", number + 1)
        ref_attributes = {"Id": f"{app_id}_O-{number}_R-{reference}", "RefId": f"{app_id}_O-{number}"}
        ref_attributes.update(obj.get("ref_overrides", {}))
        comobject_refs += _element("ComObjectRef", ref_attributes)
    parameters, parameter_refs = "", ""
    for parameter in app["parameters"]:
        number = parameter["p"]
        parameters += _element(
            "Parameter",
            {
                "Id": f"{app_id}_P-{number}",
                "Name": parameter.get("name"),
                "ParameterType": f"{app_id}_{parameter.get('type', 'PT-X')}",
                "Text": parameter.get("text"),
                "Value": "0",
            },
        )
        parameter_refs += _element("ParameterRef", {"Id": f"{app_id}_P-{number}_R-{parameter.get('r', number)}", "RefId": f"{app_id}_P-{number}"})
    static = _element(
        "Static",
        {},
        _element("ParameterTypes", {})
        + _element("Parameters", {}, parameters)
        + _element("ParameterRefs", {}, parameter_refs)
        + _element("ComObjectTable", {}, comobjects)
        + _element("ComObjectRefs", {}, comobject_refs),
    )
    translations = "".join(
        _element("TranslationElement", {"RefId": app_id}, _element("Translation", {"AttributeName": "Text", "Text": f"t{i}"}))
        for i in range(app.get("filler", 0))
    )
    languages = _element("Languages", {}, _element("Language", {"Identifier": "de-DE"}, _element("TranslationUnit", {"RefId": app_id}, translations)))
    program = _element(
        "ApplicationProgram",
        {
            "Id": app_id,
            "ApplicationNumber": app.get("number"),
            "ApplicationVersion": app.get("version"),
            "MaskVersion": app.get("mask"),
            "Name": app.get("name"),
        },
        static + _element("Dynamic", {}),
    )
    body = _element(
        "ManufacturerData",
        {},
        _element("Manufacturer", {"RefId": manufacturer["id"]}, _element("ApplicationPrograms", {}, program) + languages),
    )
    return _document(spec, body)


def _master_xml(spec: dict) -> bytes:
    main: dict[str, list[str]] = {}
    for identifier in spec["master_datapoints"]:
        if identifier.startswith("DPST-"):
            main.setdefault("DPT-" + identifier.split("-")[1], []).append(identifier)
        else:
            main.setdefault(identifier, [])
    types = "".join(
        _element("DatapointType", {"Id": key}, _element("DatapointSubtypes", {}, "".join(_element("DatapointSubtype", {"Id": s}) for s in subtypes)))
        for key, subtypes in main.items()
    )
    return _document(spec, _element("MasterData", {"Id": "MD-1"}, _element("DatapointTypes", {}, types)))


# -- archive ------------------------------------------------------------------------------------
@dataclass
class Entry:
    name: str
    data: bytes
    compress: int = zipfile.ZIP_DEFLATED


@dataclass
class Archive:
    """Ordered entries (duplicates allowed) plus names whose 'encrypted' flag bit is set after writing."""

    spec: dict
    entries: list[Entry] = field(default_factory=list)
    encrypted: set[str] = field(default_factory=set)

    @property
    def folder(self) -> str:
        return self.spec["project_id"]

    def find(self, name: str) -> Entry:
        for entry in self.entries:
            if entry.name == name:
                return entry
        raise KeyError(name)

    def resolve(self, alias: str) -> str:
        """Entry name for an alias (see module docstring) or a literal name."""
        catalog = self.spec["catalog"]
        first = catalog["manufacturers"][0]["id"] if catalog["manufacturers"] else "M-0001"
        if alias == "project_xml":
            return f"{self.folder}/project.xml"
        if alias == "zero_xml":
            return f"{self.folder}/0.xml"
        if alias == "master_xml":
            return "knx_master.xml"
        if alias == "hardware_xml" or alias.startswith("hardware_xml:"):
            manufacturer = alias.partition(":")[2] or first
            return f"{manufacturer}/Hardware.xml"
        if alias == "application_xml" or alias.startswith("application_xml:"):
            wanted = alias.partition(":")[2]
            for manufacturer in catalog["manufacturers"]:
                for app in manufacturer["applications"]:
                    if not wanted or app["id"] == wanted:
                        return f"{manufacturer['id']}/{app['id']}.xml"
            raise KeyError(alias)
        return alias


def build_parts(spec: dict) -> Archive:
    """All entries of a valid archive for ``spec``."""
    archive = Archive(spec)
    folder = spec["project_id"]
    archive.entries.append(Entry(f"{folder}/project.xml", _project_xml(spec)))
    archive.entries.append(Entry(f"{folder}/0.xml", _zero_xml(spec)))
    catalog = spec["catalog"]
    for manufacturer in catalog["manufacturers"]:
        if catalog.get("hardware_xml", True):
            archive.entries.append(Entry(f"{manufacturer['id']}/Hardware.xml", _hardware_xml(spec, manufacturer)))
        for app in manufacturer["applications"]:
            archive.entries.append(
                Entry(f"{manufacturer['id']}/{app['id']}.xml", _application_xml(spec, manufacturer, app))
            )
    if catalog.get("master", True):
        archive.entries.append(Entry("knx_master.xml", _master_xml(spec)))
    return archive


def _insert_after_declaration(data: bytes, inserted: str) -> bytes:
    marker = b"?>\r\n"
    index = data.index(marker) + len(marker)
    return data[:index] + inserted.encode("utf-8") + data[index:]


BILLION_LAUGHS = (
    '<!DOCTYPE KNX [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">'
    '<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;"><!ENTITY d "&c;&c;&c;&c;&c;&c;&c;&c;&c;&c;">]>\r\n'
)


def apply_mutations(archive: Archive, mutations: list[dict] | None) -> Archive:
    """Apply named mutations in order (see module docstring)."""
    for mutation in mutations or []:
        operation = mutation["op"]
        if operation in ("remove", "doctype", "entity", "utf16", "encoding_declaration", "malform", "replace",
                         "encrypt", "duplicate", "empty_entry"):  # fmt: skip
            name = archive.resolve(mutation["entry"])
            if operation == "remove":
                archive.entries = [e for e in archive.entries if e.name != name]
            elif operation == "encrypt":
                archive.encrypted.add(name)
            elif operation == "duplicate":
                archive.entries.append(Entry(name, archive.find(name).data))
            else:
                entry = archive.find(name)
                if operation == "doctype":
                    entry.data = _insert_after_declaration(entry.data, '<!DOCTYPE KNX [<!ELEMENT KNX ANY>]>\r\n')
                elif operation == "entity":
                    entry.data = _insert_after_declaration(entry.data, BILLION_LAUGHS)
                elif operation == "utf16":
                    entry.data = entry.data[3:].decode("utf-8").replace('encoding="utf-8"', 'encoding="utf-16"').encode("utf-16")
                elif operation == "encoding_declaration":
                    text = entry.data[3:].decode("utf-8").replace('encoding="utf-8"', f'encoding="{mutation["value"]}"')
                    entry.data = text.encode("latin-1")
                elif operation == "malform":
                    entry.data = entry.data[: max(len(entry.data) // 2, 1)] + b"<unclosed"
                elif operation == "replace":
                    old, new = mutation["old"].encode(), mutation["new"].encode()
                    if old not in entry.data:
                        raise ValueError(f"replace: {mutation['old']!r} not found in {name}")
                    entry.data = entry.data.replace(old, new) if mutation.get("all") else entry.data.replace(old, new, 1)
                elif operation == "empty_entry":
                    entry.data = b""
        elif operation == "append_entry":
            data = mutation.get("data", "<KNX/>")
            archive.entries.append(Entry(mutation["name"], data.encode() if isinstance(data, str) else data))
        elif operation == "many_entries":
            archive.entries.extend(Entry(f"filler/{i}.txt", b"x") for i in range(mutation["count"]))
        elif operation == "big_entry":
            payload = random.Random(1).randbytes(mutation["size"])
            archive.entries.append(Entry(mutation["name"], payload, zipfile.ZIP_STORED))
        elif operation == "ratio_entry":
            archive.entries.append(Entry(mutation["name"], b"\x00" * mutation["size"]))
        elif operation == "second_installation":
            archive.entries.append(Entry(f"{archive.folder}/1.xml", archive.find(f"{archive.folder}/0.xml").data))
        elif operation == "second_project_folder":
            archive.entries.append(Entry("P-0002/project.xml", archive.find(f"{archive.folder}/project.xml").data))
        elif operation == "rename_project_folder":
            for entry in archive.entries:
                if entry.name.startswith(f"{archive.folder}/"):
                    entry.name = mutation["to"] + entry.name[len(archive.folder):]
        else:
            raise ValueError(f"unknown mutation {operation!r}")
    return archive


def _set_encrypted_flags(path: Path, names: set[str]) -> None:
    """Set general-purpose flag bit 0 in local and central headers of the named entries (post-processing)."""
    raw = bytearray(path.read_bytes())
    with zipfile.ZipFile(path) as archive:
        start = archive.start_dir
        offsets = {info.filename: info.header_offset for info in archive.infolist()}
    position = start
    while raw[position : position + 4] == b"PK\x01\x02":
        name_length, extra_length, comment_length = struct.unpack_from("<HHH", raw, position + 28)
        name = bytes(raw[position + 46 : position + 46 + name_length]).decode("utf-8")
        if name in names:
            flags = struct.unpack_from("<H", raw, position + 8)[0] | 0x1
            struct.pack_into("<H", raw, position + 8, flags)
            local = offsets[name]
            local_flags = struct.unpack_from("<H", raw, local + 6)[0] | 0x1
            struct.pack_into("<H", raw, local + 6, local_flags)
        position += 46 + name_length + extra_length + comment_length
    path.write_bytes(bytes(raw))


def write_archive(path: Path, archive: Archive) -> Path:
    """Write the entries to ``path`` (a duplicate name is written twice on purpose)."""
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # zipfile warns about duplicate names
        with zipfile.ZipFile(path, "w") as target:
            for entry in archive.entries:
                info = zipfile.ZipInfo(entry.name, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = entry.compress
                target.writestr(info, entry.data)
    if archive.encrypted:
        _set_encrypted_flags(path, archive.encrypted)
    return path


def apply_edits(spec: dict, edits: list[dict] | None) -> dict:
    """Edit a description in place by dotted path (list indexes are integers).

    ``{path: "areas.0.lines.0.components.1.address", value: 0}`` sets, ``{path: ..., delete: true}`` removes
    (key or list item), ``{path: "...objects", append: {...}}`` appends to a list.
    """
    for edit in edits or []:
        parts = [int(p) if p.lstrip("-").isdigit() else p for p in edit["path"].split(".")]
        target = spec
        for part in parts[:-1]:
            target = target[part]
        last = parts[-1]
        if edit.get("delete"):
            del target[last]
        elif "append" in edit:
            target[last].append(copy.deepcopy(edit["append"]))
        else:
            target[last] = copy.deepcopy(edit["value"])
    return spec


def build_project(
    path: Path,
    patch: dict | None = None,
    mutations: list[dict] | None = None,
    *,
    edits: list[dict] | None = None,
    kind: str = "zip",
) -> Path:
    """Build a synthetic .knxproj at ``path``.

    ``patch`` is merged into the default description, ``edits`` modify it by dotted path, ``mutations`` change
    the built entries. ``kind``: 'zip' (default), 'not_zip' (text file) or 'empty' (0 bytes).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if kind == "not_zip":
        path.write_text("this is not a zip archive", encoding="utf-8")
        return path
    if kind == "empty":
        path.write_bytes(b"")
        return path
    spec = apply_edits(merge_spec(default_spec(), patch), edits)
    archive = apply_mutations(build_parts(spec), mutations)
    return write_archive(path, archive)
