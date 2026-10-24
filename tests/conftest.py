"""Shared test configuration: YAML fixture loader, synthetic .knxproj factory, session helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import yaml

from knxproj_builder import build_project

from knx_agent.application.knxproj_archive import ArchiveLimits, KnxprojArchive
from knx_agent.application.knxproj_parser import parse_project
from knx_agent.sdk import KnxSessionClient
from knx_agent.sdk.logging_setup import remove_configured_logging

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Fixture argument name -> key inside describe_session_cases.yaml
_DESCRIBE_SESSION_PARAMS = {"valid_case": "valid", "invalid_case": "invalid"}


def load_fixture(name: str) -> dict:
    """Load a YAML fixture file from tests/fixtures/ and return its mapping."""
    with (FIXTURES_DIR / name).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Fixture {name} must contain a top-level mapping.")
    return data


def fixture_cases(name: str, key: str) -> list:
    """Parametrize helper: pytest.param per case of fixture file `name` under `key` (id from case)."""
    cases = load_fixture(name)[key]
    return [pytest.param(case, id=str(case.get("id", index))) for index, case in enumerate(cases)]


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize tests that request `valid_case` / `invalid_case` from the YAML fixture."""
    for argname, key in _DESCRIBE_SESSION_PARAMS.items():
        if argname in metafunc.fixturenames:
            cases = load_fixture("describe_session_cases.yaml")[key]
            metafunc.parametrize(argname, cases, ids=[case["id"] for case in cases])


MARKER_ENTRY = "marker.txt"  # stored in every session test project so that a same-size content change is possible


def marker_mutation(token: str = "AAAAAAAA") -> dict:
    """Builder mutation adding the marker entry (8 characters; same length, different bytes)."""
    return {"op": "append_entry", "name": MARKER_ENTRY, "data": token}


@pytest.fixture
def make_project(tmp_path):
    """Factory for project files: kind zip (valid ETS 6, built) | not_zip | empty | directory | missing."""

    def _make(kind: str = "zip", name: str = "house.knxproj") -> Path:
        path = tmp_path / "projects" / name
        path.parent.mkdir(exist_ok=True)
        if kind == "zip":
            build_project(path, mutations=[marker_mutation()])
        elif kind == "plain_zip":  # a zip archive that is not an ETS project
            build_project(path, mutations=[{"op": "rename_project_folder", "to": "X-1"}])
        elif kind == "encrypted":
            build_project(path, mutations=[{"op": "encrypt", "entry": "zero_xml"}])
        elif kind == "malformed_zero":
            build_project(path, mutations=[{"op": "malform", "entry": "zero_xml"}])
        elif kind == "not_zip":
            path.write_text("this is not a zip archive", encoding="utf-8")
        elif kind == "empty":
            path.write_bytes(b"")
        elif kind == "directory":
            path.mkdir()
        elif kind != "missing":
            raise ValueError(kind)
        return path

    return _make


@pytest.fixture
def build(tmp_path):
    """Factory for valid synthetic ETS 6 archives (see tests/knxproj_builder.py)."""
    counter = {"n": 0}

    def _build(patch=None, mutations=None, edits=None, *, kind: str = "zip", name: str | None = None) -> Path:
        counter["n"] += 1
        return build_project(
            tmp_path / "built" / (name or f"project{counter['n']}.knxproj"),
            patch,
            mutations,
            edits=edits,
            kind=kind,
        )

    return _build


def build_case(build_factory, case: dict) -> Path:
    """Build the archive described by a YAML case (keys: patch, edits, mutations, kind)."""
    return build_factory(case.get("patch"), case.get("mutations"), case.get("edits"), kind=case.get("kind", "zip"))


def parse_archive(path: Path, limits: ArchiveLimits | None = None):
    """Open + parse an archive; returns (ParsedProject, list of entries opened for reading)."""
    with KnxprojArchive(path, limits) as archive:
        parsed = parse_project(archive)
        return parsed, list(archive.opened_entries)


@pytest.fixture
def session_root(tmp_path) -> Path:
    return tmp_path / "sessions"


@pytest.fixture
def client(session_root) -> KnxSessionClient:
    return KnxSessionClient(session_root=session_root)


@pytest.fixture
def project(make_project) -> Path:
    return make_project("zip")


@pytest.fixture(autouse=True)
def _clean_logging():
    yield
    remove_configured_logging()


def read_log_book(session_root: Path, label: str) -> list[dict]:
    """Entries of a session's log book."""
    path = session_root / label / "session-log-book.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def state_bytes(session_root: Path, label: str) -> bytes:
    return (session_root / label / "session-state.yaml").read_bytes()


def rebuild_project(path: Path, patch=None, mutations=None, edits=None, *, keep_mtime: bool = False) -> None:
    """Rebuild a session test project in place (marker entry included), optionally keeping its mtime."""
    stat = path.stat()
    build_project(path, patch, [marker_mutation(), *(mutations or [])], edits=edits)
    if keep_mtime:
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))


def apply_change(path: Path, change: str) -> None:
    """Apply a named change kind to a project file (see refresh_change_cases.yaml)."""
    stat = path.stat()
    if change == "none":
        return
    if change == "mtime":
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10_000_000_000))
    elif change == "size":
        rebuild_project(path, mutations=[{"op": "append_entry", "name": "extra.xml", "data": "<KNX/>"}], keep_mtime=True)
    elif change == "both":
        rebuild_project(path, mutations=[{"op": "append_entry", "name": "extra.xml", "data": "<KNX/>"}])
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10_000_000_000))
    elif change == "content_same_mtime_and_size":
        # Same size, same mtime, different bytes (the story 03 limitation, closed by the fingerprint).
        build_project(path, mutations=[marker_mutation("BBBBBBBB")])
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        assert path.stat().st_size == stat.st_size, "marker change must keep the file size"
    elif change == "missing":
        path.unlink()
    elif change == "not_zip":
        path.write_text("no longer a zip archive, different size", encoding="utf-8")
    else:
        raise ValueError(change)
