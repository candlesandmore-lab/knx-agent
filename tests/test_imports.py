"""One import test per sub-package."""

import importlib

import pytest

SUBPACKAGES = [
    "knx_agent",
    "knx_agent.domain",
    "knx_agent.application",
    "knx_agent.adapters",
    "knx_agent.adapters.mcp",
    "knx_agent.sdk",
    "knx_agent.cli",
    "knx_agent.agent_layer",
    "knx_agent.contracts",
]


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_imports(name):
    assert importlib.import_module(name) is not None
