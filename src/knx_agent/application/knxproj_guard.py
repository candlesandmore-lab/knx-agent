"""The .knxproj guard: file readable and a valid zip archive. No content parsing."""

from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass
from pathlib import Path

from knx_agent.contracts import PROJECT_FILE_UNREADABLE, PROJECT_PARSE_ERROR, error
from knx_agent.domain import ProjectImportSummary


@dataclass(frozen=True)
class ProjectFileInfo:
    """File metadata plus archive summary of a validated .knxproj."""

    path: Path
    mtime_ns: int
    size: int
    summary: ProjectImportSummary


def stat_project(path: Path) -> tuple[int, int]:
    """(mtime_ns, size) of a readable regular file, else PROJECT_FILE_UNREADABLE."""
    try:
        stat = path.stat()
    except OSError as exc:
        raise error(PROJECT_FILE_UNREADABLE, f"Project file {path} is missing or unreadable.", path=str(path)) from exc
    if not path.is_file() or not os.access(path, os.R_OK):
        raise error(PROJECT_FILE_UNREADABLE, f"Project file {path} is not a readable file.", path=str(path))
    return stat.st_mtime_ns, stat.st_size


def inspect_project(path: Path) -> ProjectFileInfo:
    """Validate the file (readable, valid zip archive) and return metadata and summary."""
    mtime_ns, size = stat_project(path)
    try:
        with zipfile.ZipFile(path) as archive:
            entry_count = len(archive.namelist())
    except zipfile.BadZipFile as exc:
        raise error(PROJECT_PARSE_ERROR, f"Project file {path} is not a valid .knxproj zip archive.", path=str(path)) from exc
    except OSError as exc:
        raise error(PROJECT_FILE_UNREADABLE, f"Project file {path} cannot be read.", path=str(path)) from exc
    return ProjectFileInfo(
        path=path,
        mtime_ns=mtime_ns,
        size=size,
        summary=ProjectImportSummary(file_name=path.name, archive_entry_count=entry_count),
    )
