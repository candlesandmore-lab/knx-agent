"""Adapter tests: delegation to the SDK (mocked) and end-to-end through the real SDK."""

import asyncio
import importlib
import json
import logging

import pytest
from conftest import apply_change, read_log_book
from typer.testing import CliRunner

from knx_agent.adapters import mcp as mcp_package
from knx_agent.adapters.mcp import server
from knx_agent.cli import app
from knx_agent.contracts import (
    DescribeSessionResponse,
    ErrorInfo,
    KnxAgentError,
    ProjectRefreshInfo,
    ResponseEnvelope,
)
from knx_agent.sdk import KnxSessionClient

# The package re-exports the MCPServer instance as `server`; the module is needed for startup state.
smod = importlib.import_module("knx_agent.adapters.mcp.server")

SENTINEL = DescribeSessionResponse(
    session_label="lbl",
    work_directory="/w/lbl",
    source_project_absolute_path="/p.knxproj",
    project_refresh=ProjectRefreshInfo(last_status="UNCHANGED"),
    active_setup="sentinel-setup",
    envelope=ResponseEnvelope(setup="sentinel-setup", limitation_notes=["sentinel"]),
)


@pytest.fixture
def calls(monkeypatch):
    recorded = []

    def fake(self, session_label, log_level=None):
        recorded.append((self._service._root_arg, session_label, log_level))
        return SENTINEL

    monkeypatch.setattr(KnxSessionClient, "describe_session", fake)
    return recorded


@pytest.fixture
def mcp_startup(monkeypatch):
    monkeypatch.setitem(smod._startup, "session_root", None)
    monkeypatch.setitem(smod._startup, "log_level", "INFO")
    return smod._startup


# --- CLI delegation (mocked SDK) ------------------------------------------------------------------
def test_cli_delegates_unchanged(calls, valid_case, tmp_path):
    label = valid_case["session_label"]
    result = CliRunner().invoke(
        app, ["session", "describe", "--session", label, "--session-root", str(tmp_path), "--log-level", "DEBUG"]
    )
    assert result.exit_code == 0
    assert calls == [(tmp_path, label, "DEBUG")]
    assert json.loads(result.stdout) == SENTINEL.model_dump(mode="json")


def test_cli_maps_sdk_exception(monkeypatch, invalid_case):
    def boom(self, session_label, log_level=None):
        raise KnxAgentError(ErrorInfo(code=invalid_case["expected_error_code"], message="bad"))

    monkeypatch.setattr(KnxSessionClient, "describe_session", boom)
    result = CliRunner().invoke(app, ["session", "describe", "--session", invalid_case["session_label"]])
    assert result.exit_code == 1
    last = result.stderr.strip().splitlines()[-1]
    assert json.loads(last) == {"code": invalid_case["expected_error_code"], "message": "bad", "details": None}
    assert result.stdout == ""


# --- CLI end to end -------------------------------------------------------------------------------
def test_cli_create_describe_reimport_end_to_end(project, session_root):
    runner = CliRunner()
    root = ["--session-root", str(session_root)]
    created = runner.invoke(
        app, ["session", "create", "--project", str(project), "--session-label", "s1", *root]
    )
    assert created.exit_code == 0, created.stderr
    assert json.loads(created.stdout)["work_directory"] == str(session_root.resolve() / "s1")

    described = runner.invoke(app, ["session", "describe", "--session", "s1", *root])
    assert described.exit_code == 0
    assert json.loads(described.stdout)["project_refresh"]["last_status"] == "UNCHANGED"

    apply_change(project, "both")
    described = runner.invoke(app, ["session", "describe", "--session", "s1", *root])
    assert json.loads(described.stdout)["project_refresh"]["last_status"] == "CHANGED"

    reimported = runner.invoke(app, ["session", "reimport", "--session", "s1", "--log-level", "FULL", *root])
    assert reimported.exit_code == 0
    assert json.loads(reimported.stdout)["project_refresh_status"] == "UNCHANGED"
    assert [e["level"] for e in read_log_book(session_root, "s1")] == ["INFO", "INFO", "INFO"]


def test_cli_error_json_on_stderr_and_exit_code_1(make_project, session_root):
    result = CliRunner().invoke(
        app,
        ["session", "create", "--project", str(make_project("not_zip")), "--session-label", "s1",
         "--session-root", str(session_root)],
    )  # fmt: skip
    assert result.exit_code == 1
    assert result.stdout == ""
    error = json.loads(result.stderr.strip().splitlines()[-1])
    assert error["code"] == "PROJECT_PARSE_ERROR"
    assert any("ERROR knx_agent" in line for line in result.stderr.splitlines())  # Python logging handler


def test_cli_invalid_log_level(project, session_root):
    result = CliRunner().invoke(
        app,
        ["session", "create", "--project", str(project), "--session-label", "s1",
         "--session-root", str(session_root), "--log-level", "LOUD"],
    )  # fmt: skip
    assert result.exit_code == 1
    assert json.loads(result.stderr.strip().splitlines()[-1])["code"] == "INVALID_LOG_LEVEL"


def test_cli_session_root_option_on_every_subcommand():
    for command in ("create", "describe", "reimport"):
        result = CliRunner().invoke(app, ["session", command, "--help"])
        assert "--session-root" in result.stdout


# --- MCP ---------------------------------------------------------------------------------------------
def test_mcp_tools_registered_under_capability_names():
    tools = asyncio.run(server.list_tools())
    assert sorted(t.name for t in tools) == ["create_session", "describe_session", "reimport_system_definition"]


def test_mcp_delegates_unchanged(calls, mcp_startup, valid_case, tmp_path):
    mcp_startup["session_root"] = str(tmp_path)
    mcp_startup["log_level"] = "DEBUG"
    assert mcp_package.describe_session(valid_case["session_label"]) == SENTINEL
    assert calls == [(str(tmp_path), valid_case["session_label"], None)]


def test_mcp_maps_sdk_exception(monkeypatch, mcp_startup, invalid_case):
    code = invalid_case["expected_error_code"]

    def boom(self, session_label, log_level=None):
        raise KnxAgentError(ErrorInfo(code=code, message="bad"))

    monkeypatch.setattr(KnxSessionClient, "describe_session", boom)
    with pytest.raises(ValueError, match=f"{code}: bad"):
        mcp_package.describe_session(invalid_case["session_label"])


def test_mcp_tools_end_to_end_with_startup_arguments(mcp_startup, project, session_root):
    mcp_startup["session_root"] = str(session_root)
    mcp_startup["log_level"] = "DEBUG"
    created = mcp_package.create_session(project_path=str(project), session_label="s1")
    assert created.work_directory == str(session_root.resolve() / "s1")
    mcp_package.describe_session("s1")
    assert mcp_package.reimport_system_definition("s1").project_refresh_status == "UNCHANGED"
    assert [e["level"] for e in read_log_book(session_root, "s1")] == ["INFO", "DEBUG", "INFO"]
    with pytest.raises(ValueError, match="SESSION_NOT_FOUND"):
        mcp_package.describe_session("ghost")


def test_mcp_startup_arguments_parsed():
    args = smod.parse_startup_arguments(["--session-root", "/x", "--log-level", "debug"])
    assert (args.session_root, args.log_level) == ("/x", "DEBUG")
    defaults = smod.parse_startup_arguments([])
    assert (defaults.session_root, defaults.log_level) == (None, "INFO")
    with pytest.raises(SystemExit):
        smod.parse_startup_arguments(["--log-level", "LOUD"])


def test_mcp_entry_point_configures_stderr_logging_and_runs(monkeypatch, mcp_startup, capsys):
    ran = []
    monkeypatch.setattr(server, "run", lambda *a, **k: ran.append(True))
    smod.mcp(["--session-root", "/some/root", "--log-level", "FULL"])
    assert ran == [True]
    assert mcp_startup == {"session_root": "/some/root", "log_level": "FULL"}
    logging.getLogger("knx_agent.test").error("boom")
    captured = capsys.readouterr()
    assert captured.out == ""  # MCP stdio owns stdout
    assert "ERROR knx_agent.test: boom" in captured.err


def test_console_scripts_registered():
    from importlib.metadata import entry_points

    scripts = {e.name: e.value for e in entry_points(group="console_scripts")}
    if "knx-agent-mcp" not in scripts:
        pytest.skip("package metadata not refreshed; run uv sync")
    assert scripts["knx-agent-mcp"] == "knx_agent.adapters.mcp:mcp"
