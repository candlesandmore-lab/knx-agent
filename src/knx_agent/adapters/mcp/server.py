"""MCP server exposing the session tools (mcp 2.x `MCPServer`, formerly FastMCP).

Started via the console script `knx-agent-mcp [--session-root DIR] [--log-level INFO|DEBUG|FULL]`.
The stdio transport owns stdout, so logging is configured on stderr only.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from mcp.server.mcpserver import MCPServer

from knx_agent.contracts import (
    CreateSessionResponse,
    DescribeComponentResponse,
    DescribeSessionResponse,
    KnxAgentError,
    ListComponentsResponse,
    ReimportSystemDefinitionResponse,
    SummarizeTopologyResponse,
    TraceGroupFlowResponse,
)
from knx_agent.sdk import KnxSessionClient, configure_stderr_logging

server = MCPServer("knx-agent")

# Startup arguments; set by mcp() before the server runs.
_startup: dict[str, str | None] = {"session_root": None, "log_level": "INFO"}


def _client() -> KnxSessionClient:
    return KnxSessionClient(session_root=_startup["session_root"], log_level=_startup["log_level"] or "INFO")


def _call(fn, **kwargs):  # noqa: ANN001, ANN003
    try:
        return fn(**kwargs)
    except KnxAgentError as exc:
        # Map to the MCP error mechanism unchanged: "CODE: message" on the first line, the ErrorInfo JSON (with
        # details such as details.reason) on the second line, identical to the CLI error JSON.
        raise ValueError(f"{exc.error.code}: {exc.error.message}\n{exc.error.model_dump_json()}") from exc


@server.tool(name="create_session")
def create_session(project_path: str, session_label: str) -> CreateSessionResponse:
    """Create an investigation session bound to a .knxproj file, identified by session_label."""
    return _call(_client().create_session, project_path=project_path, session_label=session_label)


@server.tool(name="describe_session")
def describe_session(session_label: str) -> DescribeSessionResponse:
    """Describe an investigation session identified by session_label."""
    return _call(_client().describe_session, session_label=session_label)


@server.tool(name="reimport_system_definition")
def reimport_system_definition(session_label: str) -> ReimportSystemDefinitionResponse:
    """Re-read the bound .knxproj of the session identified by session_label."""
    return _call(_client().reimport_system_definition, session_label=session_label)


# The query tools take plain strings (not enums) so that invalid values reach the core and return the catalogue
# error code. log_level is the server startup argument (C6), not a tool argument.
@server.tool(name="list_components")
def list_components(
    session_label: str,
    component_selector: str | None = None,
    selector_kind: str | None = None,
    detail_level: str | None = None,
    mutation_name: str | None = None,
) -> ListComponentsResponse:
    """List components by selector (name, instance path, individual address, ETS id), or all; empty set if none."""
    return _call(
        _client().list_components,
        session_label=session_label,
        component_selector=component_selector,
        selector_kind=selector_kind,
        detail_level=detail_level,
        mutation_name=mutation_name,
    )


@server.tool(name="describe_component")
def describe_component(
    session_label: str,
    component_selector: str,
    selector_kind: str | None = None,
    detail_level: str | None = None,
    mutation_name: str | None = None,
) -> DescribeComponentResponse:
    """Describe the components matching a selector; SELECTOR_UNRESOLVED when nothing matches."""
    return _call(
        _client().describe_component,
        session_label=session_label,
        component_selector=component_selector,
        selector_kind=selector_kind,
        detail_level=detail_level,
        mutation_name=mutation_name,
    )


@server.tool(name="summarize_topology")
def summarize_topology(
    session_label: str, detail_level: str | None = None, mutation_name: str | None = None
) -> SummarizeTopologyResponse:
    """Summarize areas, lines, locations and the component distribution."""
    return _call(
        _client().summarize_topology,
        session_label=session_label,
        detail_level=detail_level,
        mutation_name=mutation_name,
    )


@server.tool(name="trace_group_flow")
def trace_group_flow(
    session_label: str,
    group_address_selector: str | None = None,
    communication_object_ref: str | None = None,
    detail_level: str | None = None,
    mutation_name: str | None = None,
) -> TraceGroupFlowResponse:
    """Trace the direct participants of a group address or communication object (exactly one selector)."""
    return _call(
        _client().trace_group_flow,
        session_label=session_label,
        group_address_selector=group_address_selector,
        communication_object_ref=communication_object_ref,
        detail_level=detail_level,
        mutation_name=mutation_name,
    )


def parse_startup_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse --session-root and --log-level."""
    parser = argparse.ArgumentParser(prog="knx-agent-mcp", description="knx-agent MCP server (stdio).")
    parser.add_argument("--session-root", default=None, help="Folder holding all work-directories.")
    parser.add_argument(
        "--log-level", default="INFO", type=str.upper, choices=["INFO", "DEBUG", "FULL"], help="Log level."
    )
    return parser.parse_args(argv)


def mcp(argv: Sequence[str] | None = None) -> None:
    """Console script entry point: parse startup arguments, configure stderr logging, run over stdio."""
    args = parse_startup_arguments(argv)
    _startup["session_root"] = args.session_root
    _startup["log_level"] = args.log_level
    configure_stderr_logging(args.log_level)
    server.run()
