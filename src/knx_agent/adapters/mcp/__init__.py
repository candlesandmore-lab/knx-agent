"""MCP tool adapter (mcp `MCPServer`); delegates to the SDK only."""

from .server import describe_session, mcp, server

__all__ = ["describe_session", "mcp", "server"]
