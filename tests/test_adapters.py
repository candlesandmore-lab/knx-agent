"""Adapter delegation tests: SDK method mocked; inputs and outputs pass through unchanged."""

import asyncio
import json

import pytest
from typer.testing import CliRunner

from knx_agent.adapters.mcp import describe_session as mcp_describe_session
from knx_agent.adapters.mcp import server
from knx_agent.cli import app
from knx_agent.contracts import (
    DescribeSessionResponse,
    ErrorInfo,
    KnxAgentError,
    ResponseEnvelope,
)
from knx_agent.sdk import KnxSessionClient

SENTINEL = DescribeSessionResponse(
    session_label="lbl",
    active_setup="sentinel-setup",
    envelope=ResponseEnvelope(setup="sentinel-setup", limitation_notes=["sentinel"]),
)


@pytest.fixture
def calls(monkeypatch):
    recorded = []

    def fake(self, session_label):
        recorded.append(session_label)
        return SENTINEL

    monkeypatch.setattr(KnxSessionClient, "describe_session", fake)
    return recorded


def test_cli_delegates_unchanged(calls, valid_case):
    label = valid_case["session_label"]
    result = CliRunner().invoke(app, ["session", "describe", "--session", label])
    assert result.exit_code == 0
    assert calls == [label]
    assert json.loads(result.output) == SENTINEL.model_dump(mode="json")


def test_cli_maps_sdk_exception(monkeypatch, invalid_case):
    def boom(self, session_label):
        raise KnxAgentError(ErrorInfo(code=invalid_case["expected_error_code"], message="bad"))

    monkeypatch.setattr(KnxSessionClient, "describe_session", boom)
    result = CliRunner().invoke(
        app, ["session", "describe", "--session", invalid_case["session_label"]]
    )
    assert result.exit_code == 1


def test_mcp_tool_registered_under_capability_name():
    tools = asyncio.run(server.list_tools())
    assert [t.name for t in tools] == ["describe_session"]


def test_mcp_delegates_unchanged(calls, valid_case):
    label = valid_case["session_label"]
    assert mcp_describe_session(label) == SENTINEL
    assert calls == [label]


def test_mcp_maps_sdk_exception(monkeypatch, invalid_case):
    code = invalid_case["expected_error_code"]

    def boom(self, session_label):
        raise KnxAgentError(ErrorInfo(code=code, message="bad"))

    monkeypatch.setattr(KnxSessionClient, "describe_session", boom)
    with pytest.raises(ValueError, match=f"{code}: bad"):
        mcp_describe_session(invalid_case["session_label"])
