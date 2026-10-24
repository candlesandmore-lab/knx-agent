"""The .knxproj file guard: the file exists, is a regular file and is readable.

Content validation is the importer's job (``project_importer.import_project``).
"""

from __future__ import annotations

import os
from pathlib import Path

from knx_agent.contracts import PROJECT_FILE_UNREADABLE, error


def stat_project(path: Path) -> tuple[int, int]:
    """(mtime_ns, size) of a readable regular file, else PROJECT_FILE_UNREADABLE."""
    try:
        stat = path.stat()
    except OSError as exc:
        raise error(PROJECT_FILE_UNREADABLE, f"Project file {path} is missing or unreadable.", path=str(path)) from exc
    if not path.is_file() or not os.access(path, os.R_OK):
        raise error(PROJECT_FILE_UNREADABLE, f"Project file {path} is not a readable file.", path=str(path))
    return stat.st_mtime_ns, stat.st_size
