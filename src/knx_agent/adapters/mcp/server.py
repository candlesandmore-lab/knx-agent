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
    DescribeSessionResponse,
    KnxAgentError,
    ReimportSystemDefinitionResponse,
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
        # Map to the MCP error mechanism unchanged: code and message in the error text.
        raise ValueError(f"{exc.error.code}: {exc.error.message}") from exc


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
