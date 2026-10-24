"""Call the same capability on SDK, CLI and MCP and normalise the outcome (story 05 parity tests).

Outcome: ``("ok", <response JSON as dict>)`` or ``("error", <ErrorInfo JSON as dict>)``.
"""

from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path

from typer.testing import CliRunner

from knx_agent.adapters import mcp as mcp_package
from knx_agent.adapters.mcp import server
from knx_agent.application.graph_store import write_graph
from knx_agent.cli import app
from knx_agent.contracts import KnxAgentError
from knx_agent.domain import ProjectGraph
from knx_agent.sdk import KnxSessionClient

smod = importlib.import_module("knx_agent.adapters.mcp.server")

CLI_COMMANDS = {
    "list_components": "list-components",
    "describe_component": "describe-component",
    "summarize_topology": "summarize-topology",
    "trace_group_flow": "trace-group-flow",
}
CLI_OPTIONS = {
    "component_selector": {"list_components": "--query", "describe_component": "--component"},
    "selector_kind": "--selector-kind",
    "detail_level": "--detail-level",
    "mutation_name": "--mutation",
    "group_address_selector": "--group-address",
    "communication_object_ref": "--object-ref",
}


def install_graph(session_root: Path, label: str, graph: ProjectGraph) -> None:
    """Replace the stored graph of a session (the project file is unchanged, so no re-import follows)."""
    write_graph(session_root / label, graph)


def sdk_call(session_root: Path, capability: str, session: str, args: dict):
    client = KnxSessionClient(session_root=session_root)
    try:
        return "ok", json.loads(getattr(client, capability)(session_label=session, **args).model_dump_json())
    except KnxAgentError as exc:
        return "error", json.loads(exc.error.model_dump_json())


def cli_arguments(capability: str, session: str, args: dict, session_root: Path) -> list[str]:
    arguments = ["setup", CLI_COMMANDS[capability], "--session", session, "--session-root", str(session_root)]
    for name, value in args.items():
        if value is None:
            continue
        option = CLI_OPTIONS[name]
        if isinstance(option, dict):
            option = option[capability]
        arguments += [option, str(value)]
    return arguments


def cli_call(session_root: Path, capability: str, session: str, args: dict):
    result = CliRunner().invoke(app, cli_arguments(capability, session, args, session_root))
    if result.exit_code == 0:
        return "ok", json.loads(result.stdout)
    assert result.exit_code == 1, result.output
    return "error", json.loads(result.stderr.strip().splitlines()[-1])


def mcp_call(session_root: Path, capability: str, session: str, args: dict):
    """Success through the real MCP tool call (structured content); errors through the tool function."""
    smod._startup["session_root"] = str(session_root)
    smod._startup["log_level"] = "INFO"
    function = getattr(mcp_package, capability)
    try:
        function(session_label=session, **args)
    except ValueError as exc:
        text = str(exc)
        assert text.startswith(json.loads(text.splitlines()[-1])["code"] + ": ")
        return "error", json.loads(text.splitlines()[-1])
    result = asyncio.run(server.call_tool(capability, {"session_label": session, **args}))
    assert not result.is_error
    return "ok", result.structured_content


SURFACES = {"sdk": sdk_call, "cli": cli_call, "mcp": mcp_call}
