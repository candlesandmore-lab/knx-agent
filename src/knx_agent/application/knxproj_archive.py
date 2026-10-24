"""Hostile-archive guard and safe XML reading for .knxproj files (story 04, T5).

Rules (003 'Archive and XML limits'): the central directory is checked first (entry count, sizes, ratio,
duplicate names, encrypted flag); entries are only ever opened with ``ZipFile.open`` and never extracted, entry
names are never used as file system paths; every XML part is scanned as a byte stream for ``<!DOCTYPE``,
``<!ENTITY`` and a non-UTF-8 encoding BEFORE a parser sees it. A rejection of a REQUIRED part raises
``PROJECT_PARSE_ERROR`` with ``details.reason``; a rejection of an OPTIONAL part raises ``OptionalPartRejected``
(carrying the reason) so the caller skips the part, adds the warning and never uses partial content.
"""

from __future__ import annotations

import re
import zipfile
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO
from xml.etree import ElementTree as ET

from knx_agent.contracts import KnxAgentError, error
from knx_agent.contracts import PROJECT_FILE_UNREADABLE, PROJECT_PARSE_ERROR
from knx_agent.contracts.import_codes import (
    REASON_ARCHIVE_COMPRESSION_RATIO,
    REASON_ARCHIVE_DUPLICATE_ENTRY,
    REASON_ARCHIVE_ENTRY_TOO_LARGE,
    REASON_ARCHIVE_TOO_MANY_ENTRIES,
    REASON_ARCHIVE_TOTAL_TOO_LARGE,
    REASON_ENCRYPTED,
    REASON_ENTRY_READ_ERROR,
    REASON_NOT_A_ZIP,
    REASON_PROJECT_FOLDER_NOT_FOUND,
    REASON_REQUIRED_PART_MALFORMED,
    REASON_REQUIRED_PART_MISSING,
    REASON_XML_DTD_FORBIDDEN,
    REASON_XML_ENCODING_UNSUPPORTED,
    REASON_XML_ENTITY_FORBIDDEN,
    REASON_XML_MALFORMED,
)

DEFAULT_MAX_ENTRIES = 5000
DEFAULT_MAX_ENTRY_BYTES = 256 * 1024 * 1024  # 268435456
DEFAULT_MAX_TOTAL_BYTES = 1024 * 1024 * 1024  # 1073741824
DEFAULT_MAX_COMPRESSION_RATIO = 200  # uncompressed / compressed, per entry; strictly greater breaches
SCAN_CHUNK_SIZE = 1024 * 1024

_PROJECT_FOLDER = re.compile(r"P-[0-9A-Fa-f]+")
_ENCODING_DECLARATION = re.compile(rb"""<\?xml[^>]*?encoding\s*=\s*["']([^"']+)["']""")
_DOCTYPE = b"<!DOCTYPE"
_ENTITY = b"<!ENTITY"
_OVERLAP = max(len(_DOCTYPE), len(_ENTITY)) - 1
_UTF8_NAMES = {"utf-8", "utf8"}
_NON_UTF8_BOMS = (b"\xff\xfe", b"\xfe\xff", b"\x00\x00\xfe\xff")


@dataclass(frozen=True)
class ArchiveLimits:
    """Limits of the hostile-archive guard. 'Exceeds' means strictly greater."""

    max_entries: int = DEFAULT_MAX_ENTRIES
    max_entry_bytes: int = DEFAULT_MAX_ENTRY_BYTES
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES
    max_compression_ratio: int = DEFAULT_MAX_COMPRESSION_RATIO


class OptionalPartRejected(Exception):
    """An optional XML part was rejected or is unreadable; the caller skips it and warns."""

    def __init__(self, entry: str, reason: str) -> None:
        super().__init__(f"{entry}: {reason}")
        self.entry = entry
        self.reason = reason


@dataclass(frozen=True)
class RejectedPart:
    """Result of inspecting an optional part that must not be used."""

    entry: str
    reason: str


# -- byte-stream guard --------------------------------------------------------------------------
class XmlGuardScanner:
    """Incremental scanner for DTD, entity declarations and non-UTF-8 documents (chunk-overlap safe)."""

    def __init__(self) -> None:
        self._first = True
        self._tail = b""
        self.saw_doctype = False
        self.saw_entity = False
        self.encoding_problem = False

    def feed(self, chunk: bytes) -> None:
        if self._first:
            self._first = False
            self._check_encoding(chunk)
        data = self._tail + chunk
        if not self.saw_doctype and _DOCTYPE in data:
            self.saw_doctype = True
        if not self.saw_entity and _ENTITY in data:
            self.saw_entity = True
        self._tail = data[-_OVERLAP:] if _OVERLAP else b""

    def _check_encoding(self, head: bytes) -> None:
        if head.startswith(_NON_UTF8_BOMS) or head.startswith(b"\xff\xfe\x00\x00"):
            self.encoding_problem = True
            return
        if head[:3] == b"\xef\xbb\xbf":
            head = head[3:]
        if b"\x00" in head[:4]:  # UTF-16/32 without a byte-order mark
            self.encoding_problem = True
            return
        match = _ENCODING_DECLARATION.match(head.lstrip()[:512])
        if match and match.group(1).decode("ascii", "replace").strip().lower() not in _UTF8_NAMES:
            self.encoding_problem = True

    @property
    def reason(self) -> str | None:
        """Rejection reason once the stream has been fed: encoding first, then entity, then DTD."""
        if self.encoding_problem:
            return REASON_XML_ENCODING_UNSUPPORTED
        if self.saw_entity:
            return REASON_XML_ENTITY_FORBIDDEN
        if self.saw_doctype:
            return REASON_XML_DTD_FORBIDDEN
        return None


def scan_xml_stream(stream: IO[bytes], chunk_size: int = SCAN_CHUNK_SIZE) -> str | None:
    """Scan a whole byte stream; return the rejection reason or None."""
    scanner = XmlGuardScanner()
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        scanner.feed(chunk)
        if scanner.encoding_problem:
            break
    return scanner.reason


# -- archive ------------------------------------------------------------------------------------
class KnxprojArchive:
    """A validated .knxproj zip archive. Use as a context manager; nothing is ever extracted."""

    def __init__(self, path: Path, limits: ArchiveLimits | None = None, *, scan_chunk_size: int = SCAN_CHUNK_SIZE) -> None:
        self.path = Path(path)
        self.limits = limits or ArchiveLimits()
        self.scan_chunk_size = scan_chunk_size
        self._zip: zipfile.ZipFile | None = None
        self.infos: dict[str, zipfile.ZipInfo] = {}
        self.project_folder: str | None = None
        self.opened_entries: list[str] = []  # every entry opened for reading, in order (tests assert on it)

    # -- lifecycle
    def __enter__(self) -> KnxprojArchive:
        self.open()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def open(self) -> None:
        """Open the archive and run the header checks, then find the project folder."""
        try:
            self._zip = zipfile.ZipFile(self.path)
        except zipfile.BadZipFile as exc:
            raise self._fail(REASON_NOT_A_ZIP, f"Project file {self.path} is not a valid .knxproj zip archive.") from exc
        except OSError as exc:
            raise error(
                PROJECT_FILE_UNREADABLE, f"Project file {self.path} cannot be read.", path=str(self.path)
            ) from exc
        try:
            self._check_headers()
            self.project_folder = self._find_project_folder()
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if self._zip is not None:
            self._zip.close()
            self._zip = None

    # -- errors
    def _fail(self, reason: str, message: str, **details: object) -> KnxAgentError:
        return error(PROJECT_PARSE_ERROR, message, reason=reason, path=str(self.path), **details)

    # -- header checks (central directory only)
    def _check_headers(self) -> None:
        assert self._zip is not None
        limits = self.limits
        infos = self._zip.infolist()
        if len(infos) > limits.max_entries:
            raise self._fail(
                REASON_ARCHIVE_TOO_MANY_ENTRIES,
                f"Archive has {len(infos)} entries; the limit is {limits.max_entries}.",
                limit=limits.max_entries,
                actual=len(infos),
            )
        seen: dict[str, zipfile.ZipInfo] = {}
        for info in infos:
            if info.filename in seen:
                raise self._fail(
                    REASON_ARCHIVE_DUPLICATE_ENTRY,
                    f"Archive contains the entry name {info.filename!r} more than once.",
                    entry=info.filename,
                )
            seen[info.filename] = info
        total = 0
        for info in infos:
            if info.flag_bits & 0x1:
                raise self._fail(
                    REASON_ENCRYPTED,
                    f"Archive entry {info.filename!r} is encrypted (password-protected project); nothing is read.",
                    entry=info.filename,
                )
            if info.file_size > limits.max_entry_bytes:
                raise self._fail(
                    REASON_ARCHIVE_ENTRY_TOO_LARGE,
                    f"Archive entry {info.filename!r} is {info.file_size} bytes; the limit is {limits.max_entry_bytes}.",
                    entry=info.filename,
                    limit=limits.max_entry_bytes,
                    actual=info.file_size,
                )
            if info.file_size > 0 and (
                info.compress_size == 0 or info.file_size / info.compress_size > limits.max_compression_ratio
            ):
                actual = None if info.compress_size == 0 else round(info.file_size / info.compress_size, 1)
                raise self._fail(
                    REASON_ARCHIVE_COMPRESSION_RATIO,
                    f"Archive entry {info.filename!r} has a compression ratio above {limits.max_compression_ratio}.",
                    entry=info.filename,
                    limit=limits.max_compression_ratio,
                    actual=actual,
                )
            total += info.file_size
        if total > limits.max_total_bytes:
            raise self._fail(
                REASON_ARCHIVE_TOTAL_TOO_LARGE,
                f"Archive expands to {total} bytes; the limit is {limits.max_total_bytes}.",
                limit=limits.max_total_bytes,
                actual=total,
            )
        self.infos = seen

    def _find_project_folder(self) -> str:
        folders = sorted(
            {
                name.split("/", 1)[0]
                for name in self.infos
                if "/" in name and _PROJECT_FOLDER.fullmatch(name.split("/", 1)[0])
                and name == f"{name.split('/', 1)[0]}/project.xml"
            }
        )
        if len(folders) != 1:
            raise self._fail(
                REASON_PROJECT_FOLDER_NOT_FOUND,
                "Archive must contain exactly one top-level project folder P-<hex> with project.xml "
                f"(found {len(folders)}).",
                found=folders,
            )
        return folders[0]

    # -- lookups
    @property
    def entry_count(self) -> int:
        return len(self.infos)

    @property
    def names(self) -> list[str]:
        return list(self.infos)

    def has(self, name: str) -> bool:
        return name in self.infos

    def project_entry(self, filename: str) -> str:
        """Entry name inside the project folder."""
        assert self.project_folder is not None
        return f"{self.project_folder}/{filename}"

    def installation_entries(self) -> list[str]:
        """Entries '<project folder>/<n>.xml' (installation files), sorted."""
        assert self.project_folder is not None
        pattern = re.compile(re.escape(self.project_folder) + r"/\d+\.xml")
        return sorted(name for name in self.infos if pattern.fullmatch(name))

    def require(self, name: str) -> str:
        """A required part must exist, else PROJECT_PARSE_ERROR REQUIRED_PART_MISSING."""
        if name not in self.infos:
            raise self._fail(REASON_REQUIRED_PART_MISSING, f"Required part {name!r} is missing.", entry=name)
        return name

    # -- reading
    def _open_entry(self, name: str) -> IO[bytes]:
        assert self._zip is not None
        self.opened_entries.append(name)
        return self._zip.open(self.infos[name])

    def inspect_xml_part(self, name: str, *, required: bool) -> RejectedPart | None:
        """Scan one XML part before any parser sees it.

        Required part: a rejection raises PROJECT_PARSE_ERROR with the reason (a missing part raises
        REQUIRED_PART_MISSING). Optional part: returns a RejectedPart (or None when the part is acceptable);
        a missing optional part is the caller's business (use ``has``).
        """
        if required:
            self.require(name)
        try:
            with self._open_entry(name) as stream:
                reason = scan_xml_stream(stream, self.scan_chunk_size)
        except (OSError, zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, RuntimeError) as exc:
            if required:
                raise self._fail(
                    REASON_REQUIRED_PART_MALFORMED, f"Required part {name!r} cannot be read.", entry=name
                ) from exc
            return RejectedPart(name, REASON_ENTRY_READ_ERROR)
        if reason is None:
            return None
        if required:
            raise self._fail(reason, f"Required part {name!r} is rejected: {_REASON_WORDS[reason]}.", entry=name)
        return RejectedPart(name, reason)

    def iter_events(
        self, name: str, *, required: bool, events: tuple[str, ...] = ("start", "end")
    ) -> Iterator[tuple[str, ET.Element]]:
        """Yield iterparse events of one zip entry after the guard scan.

        Required part: failures raise PROJECT_PARSE_ERROR (guard reasons, REQUIRED_PART_MALFORMED).
        Optional part: raises OptionalPartRejected (guard reasons, XML_MALFORMED, ENTRY_READ_ERROR) at the point of
        failure; the caller must drop anything it collected from this part so far.
        """
        rejected = self.inspect_xml_part(name, required=required)
        if rejected is not None:
            raise OptionalPartRejected(name, rejected.reason)
        try:
            with self._open_entry(name) as stream:
                yield from ET.iterparse(stream, events=events)
        except ET.ParseError as exc:
            if required:
                raise self._fail(REASON_REQUIRED_PART_MALFORMED, f"Required part {name!r} is not well-formed XML.", entry=name) from exc
            raise OptionalPartRejected(name, REASON_XML_MALFORMED) from exc
        except (OSError, zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, RuntimeError, UnicodeError) as exc:
            if required:
                raise self._fail(REASON_REQUIRED_PART_MALFORMED, f"Required part {name!r} cannot be read.", entry=name) from exc
            raise OptionalPartRejected(name, REASON_ENTRY_READ_ERROR) from exc

    def read_tree(self, name: str, *, required: bool) -> ET.Element:
        """Small tree of one part (for required parts such as project.xml). Same failure rules as iter_events."""
        root: ET.Element | None = None
        for _event, element in self.iter_events(name, required=required, events=("end",)):
            root = element  # the last 'end' event is the root element
        if root is None:  # pragma: no cover - ET.ParseError covers empty documents
            raise self._fail(REASON_REQUIRED_PART_MALFORMED, f"Part {name!r} is empty.", entry=name)
        return root


_REASON_WORDS = {
    REASON_XML_DTD_FORBIDDEN: "a DTD (<!DOCTYPE) is not allowed",
    REASON_XML_ENTITY_FORBIDDEN: "an entity declaration (<!ENTITY) is not allowed",
    REASON_XML_ENCODING_UNSUPPORTED: "only UTF-8 documents are supported",
}
