"""MCP server exposing the describe_session tool (mcp 2.x `MCPServer`, formerly FastMCP)."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from knx_agent.contracts import DescribeSessionResponse, KnxAgentError
from knx_agent.sdk import KnxSessionClient

server = MCPServer("knx-agent")


@server.tool(name="describe_session")
def describe_session(session_label: str) -> DescribeSessionResponse:
    """Describe an investigation session identified by session_label."""
    try:
        return KnxSessionClient().describe_session(session_label=session_label)
    except KnxAgentError as exc:
        # Map to the MCP error mechanism unchanged: code and message in the error text.
        raise ValueError(f"{exc.error.code}: {exc.error.message}") from exc


def mcp() -> None:
    """Run the MCP server over stdio."""
    server.run()
