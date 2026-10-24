"""Handler configuration for the 'knx_agent' logger; used by the CLI and MCP entry points only."""

from __future__ import annotations

import logging
import sys

_MARKER = "_knx_agent_entry_point_handler"


def configure_stderr_logging(log_level: str = "INFO") -> logging.Handler:
    """Attach a stderr handler to logger 'knx_agent' (stdout stays free for JSON / MCP stdio)."""
    logger = logging.getLogger("knx_agent")
    for old in [h for h in logger.handlers if getattr(h, _MARKER, False)]:
        logger.removeHandler(old)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    setattr(handler, _MARKER, True)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if str(log_level).upper() in ("DEBUG", "FULL") else logging.INFO)
    return handler


def remove_configured_logging() -> None:
    """Remove handlers installed by configure_stderr_logging (used by tests)."""
    logger = logging.getLogger("knx_agent")
    for old in [h for h in logger.handlers if getattr(h, _MARKER, False)]:
        logger.removeHandler(old)
