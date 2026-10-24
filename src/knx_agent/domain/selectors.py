"""Component and group address selectors (story 05): parsing, kind detection and matching. Pure, no I/O.

Rules: 003 'Selector grammar: component selector', 'ANY overlap rules (binding)' and the group address selector in
'trace_group_flow'. Name and instance path match as case-insensitive substrings (instance path per consecutive
path segments); individual address and ETS id match exactly. Under ANY the NAME kind is always evaluated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from knx_agent.contracts import (
    INVALID_REQUEST,
    REASON_SELECTOR_BLANK,
    REASON_SELECTOR_KIND_MISMATCH,
    SelectorKind,
    error,
)

from .graph_index import GraphIndex
from .project_graph import ComponentNode

_IA_PATTERN = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{1,3}$")
_ETS_ID_PATTERN = re.compile(r"^P-[0-9A-Fa-f]+-\d+_DI-\d+(~\d+)?$")
_GA_THREE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{1,3})$")
_GA_TWO = re.compile(r"^(\d{1,2})/(\d{1,4})$")
_GA_FREE = re.compile(r"^\d{1,5}$")
COMMUNICATION_OBJECT_MARKER = "/co/"

KIND_ORDER: tuple[str, ...] = ("ETS_ID", "INDIVIDUAL_ADDRESS", "INSTANCE_PATH", "NAME")  # sorted


# -- generic -------------------------------------------------------------------------------------------
def strip_selector(value: str) -> str:
    """Strip surrounding whitespace; a value that is empty afterwards is INVALID_REQUEST (SELECTOR_BLANK)."""
    stripped = value.strip()
    if not stripped:
        raise error(INVALID_REQUEST, "The selector must not be blank.", reason=REASON_SELECTOR_BLANK)
    return stripped


# -- syntax tests --------------------------------------------------------------------------------------
def individual_address_syntax(value: str) -> str | None:
    """The normalised 'a.l.d' text when the value is a valid individual address (area, line 0-15, device 0-255)."""
    if not _IA_PATTERN.match(value):
        return None
    area, line, device = (int(part) for part in value.split("."))
    if area > 15 or line > 15 or device > 255:
        return None
    return f"{area}.{line}.{device}"


def ets_id_syntax(value: str) -> bool:
    return _ETS_ID_PATTERN.match(value) is not None


@dataclass(frozen=True)
class PathQuery:
    """A parsed instance path query: casefolded segments, root anchor and location-only (trailing '/') flag."""

    segments: tuple[str, ...]
    anchored: bool
    location_only: bool


def parse_path_query(value: str) -> PathQuery | None:
    """Parse an instance path query; None when no non-empty segment remains."""
    segments = tuple(part.strip().casefold() for part in value.split("/") if part.strip())
    if not segments:
        return None
    return PathQuery(segments, value.startswith("/"), value.endswith("/"))


def syntax_fits(value: str, kind: str) -> bool:
    if kind == "INDIVIDUAL_ADDRESS":
        return individual_address_syntax(value) is not None
    if kind == "ETS_ID":
        return ets_id_syntax(value)
    if kind == "INSTANCE_PATH":
        return parse_path_query(value) is not None
    return True  # NAME accepts any non-blank value


# -- matching ------------------------------------------------------------------------------------------
def path_matches(segment_lists: list[list[str]], query: PathQuery) -> bool:
    """True when the query segments match consecutive path segments of any of the paths."""
    count = len(query.segments)
    for segments in segment_lists:
        region = [s.casefold() for s in (segments[:-1] if query.location_only else segments)]
        starts = [0] if query.anchored else range(0, len(region) - count + 1)
        for start in starts:
            if start + count > len(region):
                continue
            if all(query.segments[i] in region[start + i] for i in range(count)):
                return True
    return False


def evaluated_kinds(value: str, kind: SelectorKind) -> list[str]:
    """The kinds evaluated for a (stripped) value; sorted. Explicit kinds evaluate only themselves."""
    if kind is not SelectorKind.ANY:
        return [kind.value]
    kinds = ["NAME"]
    if individual_address_syntax(value) is not None:
        kinds.append("INDIVIDUAL_ADDRESS")
    if ets_id_syntax(value):
        kinds.append("ETS_ID")
    if "/" in value and parse_path_query(value) is not None:
        kinds.append("INSTANCE_PATH")
    return sorted(kinds)


def require_kind_fits(value: str, kind: SelectorKind) -> None:
    """An explicit kind that the value does not fit is INVALID_REQUEST (SELECTOR_KIND_MISMATCH)."""
    if kind is not SelectorKind.ANY and not syntax_fits(value, kind.value):
        raise error(
            INVALID_REQUEST,
            f"The value {value!r} is not a valid {kind.value} selector.",
            reason=REASON_SELECTOR_KIND_MISMATCH,
            selector_kind=kind.value,
            value=value,
        )


@dataclass(frozen=True)
class ComponentMatch:
    component: ComponentNode
    match_kinds: tuple[str, ...]  # sorted, no duplicates


def match_components(index: GraphIndex, value: str, kind: SelectorKind = SelectorKind.ANY) -> list[ComponentMatch]:
    """Components matching a stripped, non-blank value, de-duplicated, in component order.

    An explicit kind that the value does not fit raises INVALID_REQUEST (SELECTOR_KIND_MISMATCH).
    """
    require_kind_fits(value, kind)
    kinds = evaluated_kinds(value, kind)
    address = individual_address_syntax(value) if "INDIVIDUAL_ADDRESS" in kinds else None
    path_query = parse_path_query(value) if "INSTANCE_PATH" in kinds else None
    needle = value.casefold()
    result: list[ComponentMatch] = []
    for component in index.components:
        matched: set[str] = set()
        if "NAME" in kinds and component.name and needle in component.name.casefold():
            matched.add("NAME")
        if address is not None and component.individual_address == address:
            matched.add("INDIVIDUAL_ADDRESS")
        if "ETS_ID" in kinds and component.id == value:
            matched.add("ETS_ID")
        if path_query is not None and path_matches(index.path_segments.get(component.id, []), path_query):
            matched.add("INSTANCE_PATH")
        if matched:
            result.append(ComponentMatch(component, tuple(sorted(matched))))
    return result


# -- group address selector ----------------------------------------------------------------------------
def parse_group_address_form(value: str, style: str | None) -> int | None:
    """The raw 16-bit address when the value is a valid address form for the project style, else None.

    The 3-level form 'a/b/c' (a 0-31, b 0-7, c 0-255) is always valid; the project style adds TwoLevel 'a/b'
    (a 0-31, b 0-2047) or Free (a plain integer 0-65535). Out-of-range values are not address forms.
    """
    match = _GA_THREE.match(value)
    if match:
        main, middle, sub = (int(part) for part in match.groups())
        if main <= 31 and middle <= 7 and sub <= 255:
            return (main << 11) | (middle << 8) | sub
        return None
    if style == "TwoLevel":
        match = _GA_TWO.match(value)
        if match:
            main, sub = (int(part) for part in match.groups())
            if main <= 31 and sub <= 2047:
                return (main << 11) | sub
    elif style == "Free" and _GA_FREE.match(value):
        raw = int(value)
        if raw <= 65535:
            return raw
    return None


@dataclass(frozen=True)
class GroupAddressQuery:
    """Parsed group address selector: an exact raw address, or a partial name."""

    text: str
    address_raw: int | None  # not None = exact address
    name_needle: str | None  # casefolded; not None = partial name


def parse_group_address_selector(value: str, style: str | None) -> GroupAddressQuery:
    stripped = strip_selector(value)
    raw = parse_group_address_form(stripped, style)
    if raw is not None:
        return GroupAddressQuery(stripped, raw, None)
    return GroupAddressQuery(stripped, None, stripped.casefold())


def parse_communication_object_ref(value: str) -> str:
    """The stripped object ref; blank is SELECTOR_BLANK, a value without '/co/' is SELECTOR_KIND_MISMATCH."""
    stripped = strip_selector(value)
    if COMMUNICATION_OBJECT_MARKER not in stripped:
        raise error(
            INVALID_REQUEST,
            f"communication_object_ref must be a communication object id '<component id>/co/<ref id>', got {stripped!r}.",
            reason=REASON_SELECTOR_KIND_MISMATCH,
            selector_kind="COMMUNICATION_OBJECT_REF",
            value=stripped,
        )
    return stripped
