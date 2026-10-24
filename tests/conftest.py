"""Shared test configuration: YAML fixture loader, synthetic .knxproj factory, session helpers."""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import pytest
import yaml

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


def write_zip(path: Path, entries: tuple[str, ...] = ("0.xml", "P-1/0.xml")) -> Path:
    """Write a small synthetic .knxproj zip archive."""
    with zipfile.ZipFile(path, "w") as archive:
        for entry in entries:
            archive.writestr(entry, "<KNX/>")
    return path


@pytest.fixture
def make_project(tmp_path):
    """Factory for synthetic project files: kind zip | not_zip | empty | directory | missing."""

    def _make(kind: str = "zip", name: str = "house.knxproj") -> Path:
        path = tmp_path / "projects" / name
        path.parent.mkdir(exist_ok=True)
        if kind == "zip":
            write_zip(path)
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


def apply_change(path: Path, change: str) -> None:
    """Apply a named change kind to a project file (see refresh_change_cases.yaml)."""
    stat = path.stat()
    if change == "none":
        return
    if change == "mtime":
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10_000_000_000))
    elif change == "size":
        write_zip(path, ("0.xml", "P-1/0.xml", "extra.xml"))
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))  # keep mtime: only size differs
    elif change == "both":
        write_zip(path, ("0.xml", "P-1/0.xml", "extra.xml"))
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10_000_000_000))
    elif change == "missing":
        path.unlink()
    elif change == "not_zip":
        path.write_text("no longer a zip archive, different size", encoding="utf-8")
    else:
        raise ValueError(change)
