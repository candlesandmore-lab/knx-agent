"""Shared test configuration: loader for YAML fixture files under tests/fixtures/."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

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


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize tests that request `valid_case` / `invalid_case` from the YAML fixture."""
    for argname, key in _DESCRIBE_SESSION_PARAMS.items():
        if argname in metafunc.fixturenames:
            cases = load_fixture("describe_session_cases.yaml")[key]
            metafunc.parametrize(argname, cases, ids=[case["id"] for case in cases])
