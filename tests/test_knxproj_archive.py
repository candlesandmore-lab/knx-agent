"""Hostile-archive guard and safe XML reading (story 04, T5)."""

from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

import pytest
from conftest import build_case, fixture_cases

from knx_agent.application import knxproj_archive as archive_module
from knx_agent.application.knxproj_archive import (
    DEFAULT_MAX_COMPRESSION_RATIO,
    DEFAULT_MAX_ENTRIES,
    DEFAULT_MAX_ENTRY_BYTES,
    DEFAULT_MAX_TOTAL_BYTES,
    ArchiveLimits,
    KnxprojArchive,
    OptionalPartRejected,
    RejectedPart,
    XmlGuardScanner,
    scan_xml_stream,
)
from knx_agent.contracts import KnxAgentError, PROJECT_PARSE_ERROR


def _error(exc_info) -> dict:
    return exc_info.value.error.details


# -- constants ----------------------------------------------------------------------------------
def test_default_limits_are_the_specified_constants():
    limits = ArchiveLimits()
    assert (limits.max_entries, limits.max_entry_bytes, limits.max_total_bytes, limits.max_compression_ratio) == (
        5000, 268435456, 1073741824, 200,
    )  # fmt: skip
    assert DEFAULT_MAX_ENTRIES == 5000
    assert DEFAULT_MAX_ENTRY_BYTES == 256 * 1024 * 1024 == 268435456
    assert DEFAULT_MAX_TOTAL_BYTES == 1024**3 == 1073741824
    assert DEFAULT_MAX_COMPRESSION_RATIO == 200


# -- archive limits (data driven, lowered limits) -----------------------------------------------
@pytest.mark.parametrize("case", fixture_cases("zip_limit_cases.yaml", "cases"))
def test_archive_limit_cases(build, case):
    path = build_case(build, case)
    limits = ArchiveLimits(**case["limits"]) if "limits" in case else None
    if case.get("expected_ok"):
        with KnxprojArchive(path, limits) as archive:
            assert archive.project_folder == "P-0001"
        return
    with pytest.raises(KnxAgentError) as exc_info:
        KnxprojArchive(path, limits).open()
    error = exc_info.value.error
    assert error.code == PROJECT_PARSE_ERROR
    assert error.details["reason"] == case["expected_reason"]
    assert error.details["path"] == str(path)
    if "expected_entry" in case:
        assert error.details["entry"] == case["expected_entry"]


def test_default_valid_archive_has_the_entry_count_the_limit_cases_rely_on(build):
    with KnxprojArchive(build()) as archive:
        assert archive.entry_count == 7


def test_limit_details_name_limit_and_actual_value(build):
    path = build(mutations=[{"op": "big_entry", "name": "P-0001/blob.bin", "size": 100001}])
    with pytest.raises(KnxAgentError) as exc_info:
        KnxprojArchive(path, ArchiveLimits(max_entry_bytes=100000)).open()
    assert _error(exc_info)["limit"] == 100000
    assert _error(exc_info)["actual"] == 100001


def test_total_size_boundary_is_strictly_greater(build):
    path = build()
    with zipfile.ZipFile(path) as archive:
        total = sum(info.file_size for info in archive.infolist())
    with KnxprojArchive(path, ArchiveLimits(max_total_bytes=total)):
        pass  # equal to the limit passes
    with pytest.raises(KnxAgentError) as exc_info:
        KnxprojArchive(path, ArchiveLimits(max_total_bytes=total - 1)).open()
    assert _error(exc_info)["reason"] == "ARCHIVE_TOTAL_TOO_LARGE"
    assert _error(exc_info)["actual"] == total


def test_ratio_boundary_is_strictly_greater(build):
    path = build(mutations=[{"op": "ratio_entry", "name": "P-0001/zeros.bin", "size": 100000}])
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo("P-0001/zeros.bin")
        ratio = info.file_size / info.compress_size
        others = max(i.file_size / i.compress_size for i in archive.infolist() if i.filename != info.filename)
    assert others < ratio
    with KnxprojArchive(path, ArchiveLimits(max_compression_ratio=ratio)):
        pass  # exactly the limit passes
    with pytest.raises(KnxAgentError) as exc_info:
        KnxprojArchive(path, ArchiveLimits(max_compression_ratio=ratio - 0.5)).open()
    assert _error(exc_info)["reason"] == "ARCHIVE_COMPRESSION_RATIO"


def test_stored_entry_with_zero_compressed_size_breaches_the_ratio(build, monkeypatch):
    path = build()
    real = zipfile.ZipFile.infolist

    def patched(self):
        infos = real(self)
        infos[0].compress_size = 0  # a declared non-empty entry that claims zero compressed bytes
        return infos

    monkeypatch.setattr(zipfile.ZipFile, "infolist", patched)
    with pytest.raises(KnxAgentError) as exc_info:
        KnxprojArchive(path).open()
    assert _error(exc_info)["reason"] == "ARCHIVE_COMPRESSION_RATIO"
    assert _error(exc_info)["actual"] is None


def test_empty_entries_and_directories_do_not_breach_the_ratio(build):
    path = build(mutations=[{"op": "empty_entry", "entry": "master_xml"}, {"op": "append_entry", "name": "dir/", "data": ""}])
    with KnxprojArchive(path) as archive:
        assert archive.has("dir/")


# -- project folder and required parts ----------------------------------------------------------
def test_project_folder_discovery_and_entry_helpers(build):
    with KnxprojArchive(build(mutations=[{"op": "second_installation"}])) as archive:
        assert archive.project_folder == "P-0001"
        assert archive.project_entry("0.xml") == "P-0001/0.xml"
        assert archive.installation_entries() == ["P-0001/0.xml", "P-0001/1.xml"]
        assert archive.require("P-0001/0.xml") == "P-0001/0.xml"
        with pytest.raises(KnxAgentError) as exc_info:
            archive.require("P-0001/missing.xml")
        assert _error(exc_info)["reason"] == "REQUIRED_PART_MISSING"


def test_open_reports_a_missing_file_as_unreadable(tmp_path):
    with pytest.raises(KnxAgentError) as exc_info:
        KnxprojArchive(tmp_path / "missing.knxproj").open()
    assert exc_info.value.error.code == "PROJECT_FILE_UNREADABLE"


# -- XML guard: scanner -------------------------------------------------------------------------
BOM = b"\xef\xbb\xbf"


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (BOM + b'<?xml version="1.0" encoding="utf-8"?><KNX/>', None),
        (b'<?xml version="1.0"?><KNX/>', None),
        (b"<KNX/>", None),
        (b'<?xml version="1.0" encoding="UTF-8"?><KNX/>', None),
        (b'<?xml version="1.0" encoding=\'utf8\'?><KNX/>', None),
        (b'<?xml version="1.0"?><!DOCTYPE KNX><KNX/>', "XML_DTD_FORBIDDEN"),
        (b'<?xml version="1.0"?><!DOCTYPE KNX [<!ENTITY a "b">]><KNX>&a;</KNX>', "XML_ENTITY_FORBIDDEN"),
        (b'<KNX><!ENTITY a "b"></KNX>', "XML_ENTITY_FORBIDDEN"),
        ("<?xml version=\"1.0\"?><KNX/>".encode("utf-16"), "XML_ENCODING_UNSUPPORTED"),
        ("<?xml version=\"1.0\"?><KNX/>".encode("utf-16-le"), "XML_ENCODING_UNSUPPORTED"),
        ("<?xml version=\"1.0\"?><KNX/>".encode("utf-16-be"), "XML_ENCODING_UNSUPPORTED"),
        ("<KNX/>".encode("utf-32"), "XML_ENCODING_UNSUPPORTED"),
        (b'<?xml version="1.0" encoding="windows-1252"?><KNX/>', "XML_ENCODING_UNSUPPORTED"),
        (BOM + b'<?xml version="1.0" encoding="iso-8859-1"?><KNX/>', "XML_ENCODING_UNSUPPORTED"),
    ],
)
def test_scanner_decides_before_any_parser_sees_the_document(data, reason):
    assert scan_xml_stream(io.BytesIO(data)) == reason


@pytest.mark.parametrize("chunk_size", [1, 2, 3, 5, 7, 8, 9, 10, 16])
@pytest.mark.parametrize(
    ("needle", "reason"), [(b"<!DOCTYPE", "XML_DTD_FORBIDDEN"), (b"<!ENTITY", "XML_ENTITY_FORBIDDEN")]
)
def test_marker_split_across_chunk_boundaries_is_found(chunk_size, needle, reason):
    data = b"<KNX>" + b"x" * 11 + needle + b" y>" + b"z" * 20 + b"</KNX>"
    assert scan_xml_stream(io.BytesIO(data), chunk_size) == reason


def test_scanner_finds_a_marker_at_every_offset_for_awkward_chunk_size():
    for offset in range(0, 40):
        data = b"a" * offset + b"<!DOCTYPE KNX>" + b"b" * 40
        assert scan_xml_stream(io.BytesIO(data), 7) == "XML_DTD_FORBIDDEN", offset


def test_scanner_precedence_is_encoding_then_entity_then_dtd():
    scanner = XmlGuardScanner()
    scanner.feed(b'<!DOCTYPE KNX [<!ENTITY a "b">]><KNX/>')
    assert scanner.reason == "XML_ENTITY_FORBIDDEN"
    assert XmlGuardScanner().reason is None


# -- XML guard on archive parts -----------------------------------------------------------------
GUARD_MUTATIONS = {
    "XML_DTD_FORBIDDEN": "doctype",
    "XML_ENTITY_FORBIDDEN": "entity",
    "XML_ENCODING_UNSUPPORTED": "utf16",
}


@pytest.mark.parametrize("reason", sorted(GUARD_MUTATIONS))
@pytest.mark.parametrize("alias", ["zero_xml", "project_xml"])
def test_required_part_rejection_raises_parse_error_with_reason(build, reason, alias):
    path = build(mutations=[{"op": GUARD_MUTATIONS[reason], "entry": alias}])
    entry = {"zero_xml": "P-0001/0.xml", "project_xml": "P-0001/project.xml"}[alias]
    with KnxprojArchive(path) as archive:
        with pytest.raises(KnxAgentError) as exc_info:
            archive.inspect_xml_part(entry, required=True)
        assert exc_info.value.error.code == PROJECT_PARSE_ERROR
        assert _error(exc_info)["reason"] == reason
        assert _error(exc_info)["entry"] == entry
        with pytest.raises(KnxAgentError):  # the event stream refuses as well, before any event is produced
            next(archive.iter_events(entry, required=True))


@pytest.mark.parametrize("reason", sorted(GUARD_MUTATIONS))
@pytest.mark.parametrize("alias", ["hardware_xml", "application_xml", "master_xml"])
def test_optional_part_rejection_returns_a_rejected_part_result(build, reason, alias):
    path = build(mutations=[{"op": GUARD_MUTATIONS[reason], "entry": alias}])
    entry = {
        "hardware_xml": "M-0001/Hardware.xml",
        "application_xml": "M-0001/M-0001_A-0001-01-AAAA.xml",
        "master_xml": "knx_master.xml",
    }[alias]
    with KnxprojArchive(path) as archive:
        assert archive.inspect_xml_part(entry, required=False) == RejectedPart(entry, reason)
        with pytest.raises(OptionalPartRejected) as exc_info:
            list(archive.iter_events(entry, required=False))
        assert (exc_info.value.entry, exc_info.value.reason) == (entry, reason)


def test_rejected_optional_part_is_never_handed_to_a_parser(build, monkeypatch):
    path = build(mutations=[{"op": "entity", "entry": "master_xml"}])
    seen = []
    real = archive_module.ET.iterparse
    monkeypatch.setattr(archive_module.ET, "iterparse", lambda *a, **k: seen.append(a) or real(*a, **k))
    with KnxprojArchive(path) as archive:
        with pytest.raises(OptionalPartRejected):
            list(archive.iter_events("knx_master.xml", required=False))
    assert seen == []


def test_acceptable_part_passes_the_scan_and_streams_events(build):
    with KnxprojArchive(build()) as archive:
        assert archive.inspect_xml_part("P-0001/0.xml", required=True) is None
        tags = {el.tag.rsplit("}", 1)[-1] for ev, el in archive.iter_events("P-0001/0.xml", required=True, events=("end",))}
        assert {"KNX", "Installation", "DeviceInstance", "GroupAddress"} <= tags
        root = archive.read_tree("P-0001/project.xml", required=True)
        assert root.tag.endswith("KNX")


def test_malformed_required_part_raises_required_part_malformed(build):
    path = build(mutations=[{"op": "malform", "entry": "zero_xml"}])
    with KnxprojArchive(path) as archive:
        with pytest.raises(KnxAgentError) as exc_info:
            archive.read_tree("P-0001/0.xml", required=True)
    assert _error(exc_info)["reason"] == "REQUIRED_PART_MALFORMED"


def test_malformed_optional_part_is_reported_as_xml_malformed(build):
    path = build(mutations=[{"op": "malform", "entry": "master_xml"}])
    with KnxprojArchive(path) as archive:
        with pytest.raises(OptionalPartRejected) as exc_info:
            list(archive.iter_events("knx_master.xml", required=False))
    assert exc_info.value.reason == "XML_MALFORMED"


def test_unreadable_entry_data_is_an_entry_read_error_for_optional_parts(build, tmp_path):
    path = build()
    raw = bytearray(path.read_bytes())
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo("knx_master.xml")
    raw[info.header_offset + 30 + len(info.filename) + 5] ^= 0xFF  # corrupt the compressed data
    path.write_bytes(bytes(raw))
    with KnxprojArchive(path) as archive:
        assert archive.inspect_xml_part("knx_master.xml", required=False) == RejectedPart("knx_master.xml", "ENTRY_READ_ERROR")


# -- nothing is extracted, names are never paths -----------------------------------------------
def test_hostile_archives_are_never_extracted(build, tmp_path, monkeypatch):
    names = ["../evil.txt", "/abs/evil.txt", "a/../../evil.txt", "C:\\evil.txt"]
    path = build(mutations=[{"op": "append_entry", "name": name, "data": "x"} for name in names])
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    with KnxprojArchive(path) as archive:
        assert all(archive.has(name) for name in names)  # looked up by exact string only
    for param in fixture_cases("zip_limit_cases.yaml", "cases"):
        case = param.values[0]
        hostile = build_case(build, case)
        try:
            with KnxprojArchive(hostile, ArchiveLimits(**case.get("limits", {}))):
                pass
        except KnxAgentError:
            pass
    assert os.listdir(workdir) == []
    assert not (tmp_path / "evil.txt").exists()
    assert not Path("/abs/evil.txt").exists()


def test_working_directory_listing_is_unchanged_after_hostile_imports(build, tmp_path, monkeypatch):
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    path = build(mutations=[{"op": "entity", "entry": "zero_xml"}])
    with pytest.raises(KnxAgentError):
        with KnxprojArchive(path) as archive:
            archive.read_tree("P-0001/0.xml", required=True)
    assert os.listdir(workdir) == []
