"""The synthetic .knxproj builder produces archives that zipfile and ElementTree can read (story 04, T4)."""

from __future__ import annotations

import zipfile
from xml.etree import ElementTree as ET

import pytest
from conftest import fixture_cases
from knxproj_builder import NAMESPACE, build_project, default_spec, merge_spec

NS = f"{{{NAMESPACE}}}"


def _read(path, name):
    with zipfile.ZipFile(path) as archive:
        return archive.read(name)


def test_default_archive_is_a_valid_zip_with_seven_entries(build):
    path = build()
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert sorted(archive.namelist()) == sorted(
            [
                "P-0001/project.xml",
                "P-0001/0.xml",
                "M-0001/Hardware.xml",
                "M-0001/M-0001_A-0001-01-AAAA.xml",
                "M-0001/M-0001_A-0002-01-BBBB.xml",
                "M-0001/M-0001_A-0003-01-CCCC.xml",
                "knx_master.xml",
            ]
        )


def test_every_default_part_is_well_formed_ets6_xml(build):
    path = build()
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            root = ET.fromstring(archive.read(name))
            assert root.tag == f"{NS}KNX"
            assert root.get("ToolVersion") == "6.1.5686.0"
            assert root.get("CreatedBy") == "ETS6"
            assert archive.read(name).startswith(b"\xef\xbb\xbf<?xml")  # ETS writes UTF-8 with BOM


def test_zero_xml_has_topology_locations_and_group_addresses(build):
    root = ET.fromstring(_read(build(), "P-0001/0.xml"))
    assert len(root.findall(f".//{NS}Area")) == 1
    assert len(root.findall(f".//{NS}DeviceInstance")) == 3
    assert len(root.findall(f".//{NS}ComObjectInstanceRef")) == 6
    assert len(root.findall(f".//{NS}ParameterInstanceRef")) == 2
    assert len(root.findall(f".//{NS}GroupAddress")) == 3
    assert len(root.findall(f".//{NS}GroupRange")) == 2
    assert len(root.findall(f".//{NS}Space")) == 3
    assert len(root.findall(f".//{NS}DeviceInstanceRef")) == 2
    device = root.find(f".//{NS}DeviceInstance")
    assert device.get("Id") == "P-0001-0_DI-1"
    assert device.get("Hardware2ProgramRefId") == "M-0001_H-1_HP-0001-01-AAAA"


def test_catalog_parts_describe_products_programs_and_objects(build):
    path = build()
    hardware = ET.fromstring(_read(path, "M-0001/Hardware.xml"))
    assert len(hardware.findall(f".//{NS}Hardware2Program")) == 3
    assert hardware.find(f".//{NS}ApplicationProgramRef").get("RefId") == "M-0001_A-0001-01-AAAA"
    application = ET.fromstring(_read(path, "M-0001/M-0001_A-0001-01-AAAA.xml"))
    assert len(application.findall(f".//{NS}ComObject")) == 4
    assert len(application.findall(f".//{NS}ComObjectRef")) == 4
    assert len(application.findall(f".//{NS}Parameter")) == 2
    master = ET.fromstring(_read(path, "knx_master.xml"))
    assert {e.get("Id") for e in master.iter(f"{NS}DatapointSubtype")} == {"DPST-1-1", "DPST-1-2", "DPST-5-1"}


def test_merge_spec_merges_mappings_and_replaces_lists():
    base = default_spec()
    merged = merge_spec(base, {"catalog": {"master": False}, "spaces": []})
    assert merged["catalog"]["master"] is False
    assert merged["catalog"]["manufacturers"] == base["catalog"]["manufacturers"]
    assert merged["spaces"] == []
    assert base["spaces"] != []  # the base is not modified


def test_patch_and_edits_change_the_description(build):
    path = build({"project_name": "Other"}, edits=[{"path": "areas.0.lines.0.components.0.name", "value": "Renamed"}])
    root = ET.fromstring(_read(path, "P-0001/0.xml"))
    assert root.find(f".//{NS}DeviceInstance").get("Name") == "Renamed"
    info = ET.fromstring(_read(path, "P-0001/project.xml")).find(f".//{NS}ProjectInformation")
    assert info.get("Name") == "Other"


def test_edits_can_delete_and_append(build):
    path = build(edits=[
        {"path": "areas.0.lines.0.components", "append": {"address": 4, "name": "Extra", "objects": [], "parameters": []}},
        {"path": "catalog.master", "value": False},
    ])  # fmt: skip
    with zipfile.ZipFile(path) as archive:
        assert "knx_master.xml" not in archive.namelist()
        assert len(ET.fromstring(archive.read("P-0001/0.xml")).findall(f".//{NS}DeviceInstance")) == 4


def test_filler_translations_make_large_application_programs(build):
    path = build(edits=[{"path": "catalog.manufacturers.0.applications.0.filler", "value": 500}])
    application = ET.fromstring(_read(path, "M-0001/M-0001_A-0001-01-AAAA.xml"))
    assert len(application.findall(f".//{NS}Translation")) == 500


@pytest.mark.parametrize(
    ("mutation", "check"),
    [
        ({"op": "doctype", "entry": "zero_xml"}, lambda data: b"<!DOCTYPE" in data and b"<!ENTITY" not in data),
        ({"op": "entity", "entry": "zero_xml"}, lambda data: b"<!DOCTYPE" in data and b"<!ENTITY" in data),
        ({"op": "utf16", "entry": "zero_xml"}, lambda data: data[:2] in (b"\xff\xfe", b"\xfe\xff")),
        ({"op": "malform", "entry": "zero_xml"}, lambda data: data.endswith(b"<unclosed")),
        ({"op": "empty_entry", "entry": "zero_xml"}, lambda data: data == b""),
        ({"op": "encoding_declaration", "entry": "zero_xml", "value": "iso-8859-1"}, lambda data: b'encoding="iso-8859-1"' in data),
    ],
)
def test_mutations_change_the_entry_as_named(build, mutation, check):
    assert check(_read(build(mutations=[mutation]), "P-0001/0.xml"))


def test_mutation_replace_requires_the_text_to_exist(build):
    with pytest.raises(ValueError):
        build(mutations=[{"op": "replace", "entry": "zero_xml", "old": "does-not-occur", "new": "x"}])


def test_unknown_mutation_is_rejected(build):
    with pytest.raises(ValueError):
        build(mutations=[{"op": "explode"}])


def test_remove_and_append_entry(build):
    path = build(mutations=[{"op": "remove", "entry": "master_xml"}, {"op": "append_entry", "name": "x/y.txt", "data": "hi"}])
    with zipfile.ZipFile(path) as archive:
        assert "knx_master.xml" not in archive.namelist()
        assert archive.read("x/y.txt") == b"hi"


def test_encrypted_flag_is_set_in_local_and_central_header(build):
    path = build(mutations=[{"op": "encrypt", "entry": "hardware_xml"}])
    with zipfile.ZipFile(path) as archive:
        flagged = {info.filename for info in archive.infolist() if info.flag_bits & 0x1}
        assert flagged == {"M-0001/Hardware.xml"}
        info = archive.getinfo("M-0001/Hardware.xml")
    raw = path.read_bytes()
    assert raw[info.header_offset + 6] & 0x1  # local header flags


def test_duplicate_entry_names_are_written_twice(build):
    path = build(mutations=[{"op": "duplicate", "entry": "zero_xml"}])
    with zipfile.ZipFile(path) as archive:
        assert archive.namelist().count("P-0001/0.xml") == 2


def test_many_big_and_ratio_entries(build):
    path = build(mutations=[
        {"op": "many_entries", "count": 30},
        {"op": "big_entry", "name": "big.bin", "size": 5000},
        {"op": "ratio_entry", "name": "zeros.bin", "size": 100000},
    ])  # fmt: skip
    with zipfile.ZipFile(path) as archive:
        assert len(archive.namelist()) == 7 + 30 + 2
        assert archive.getinfo("big.bin").compress_type == zipfile.ZIP_STORED
        zeros = archive.getinfo("zeros.bin")
        assert zeros.file_size / zeros.compress_size > 200


def test_second_installation_and_second_project_folder(build):
    path = build(mutations=[{"op": "second_installation"}, {"op": "second_project_folder"}, {"op": "rename_project_folder", "to": "P-00AB"}])
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    assert "P-00AB/1.xml" in names and "P-00AB/0.xml" in names and "P-0002/project.xml" in names


def test_non_zip_and_empty_kinds(build):
    assert not zipfile.is_zipfile(build(kind="not_zip"))
    assert build(kind="empty").stat().st_size == 0


def test_archive_description_fixtures_load_and_build(build, tmp_path):
    # every case of the three fixture files that describes a ZIP must at least be buildable
    for name in ("import_error_cases.yaml", "import_warning_cases.yaml", "zip_limit_cases.yaml"):
        for param in fixture_cases(name, "cases"):
            case = param.values[0]
            path = build(case.get("patch"), case.get("mutations"), case.get("edits"), kind=case.get("kind", "zip"))
            assert path.exists(), (name, case["id"])


def test_builder_writes_only_below_tmp_path(build, tmp_path):
    path = build()
    assert tmp_path in path.parents
