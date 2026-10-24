"""QueryService: the four read-only component inspection capabilities (story 05, capabilities 6-9).

Order of operations (003 'Component inspection (story 05)'): log level, session label / SESSION_NOT_FOUND, project
refresh check (may re-import), request validation (detail level, mutation_name, selector rules), graph load and
index, query, envelope. The capabilities write NO log book entry of their own; only the refresh check does, with the
calling capability name. Every failure is an ERROR (Python logger plus log book) and is re-raised.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from knx_agent.contracts import (
    MUTATION_NOT_FOUND,
    PROJECT_PARSE_ERROR,
    REASON_GRAPH_FILE_INVALID,
    DescribeComponentResponse,
    DetailLevel,
    EvidenceKind,
    EvidenceSource,
    ListComponentsResponse,
    LogLevel,
    ResponseEnvelope,
    SelectorKind,
    SummarizeTopologyResponse,
    TraceGroupFlowResponse,
    error,
    parse_detail_level,
    parse_selector_kind,
)
from knx_agent.domain import DEFAULT_SETUP, ProjectGraph, SessionState
from knx_agent.domain.component_view import (
    describe_components,
    list_components,
    validate_describe_request,
    validate_list_request,
)
from knx_agent.domain.graph_index import GraphIndex
from knx_agent.domain.group_flow import trace, validate_flow_request
from knx_agent.domain.topology_summary import summarize

from .error_reporting import report_error
from .graph_store import graph_path, read_graph
from .log_book import SessionLogBook
from .session_access import SessionAccess

T = TypeVar("T")

LIST_COMPONENTS = "list_components"
DESCRIBE_COMPONENT = "describe_component"
SUMMARIZE_TOPOLOGY = "summarize_topology"
TRACE_GROUP_FLOW = "trace_group_flow"


def check_mutation_name(mutation_name: object) -> None:
    """None, empty or 'default' target the default setup; every other value is MUTATION_NOT_FOUND (todo 08)."""
    if mutation_name is None or mutation_name in ("", DEFAULT_SETUP):
        return
    raise error(
        MUTATION_NOT_FOUND,
        f"Mutation {mutation_name!r} does not exist; mutations arrive with todo 08, only 'default' is available.",
        mutation_name=mutation_name if isinstance(mutation_name, str) else str(mutation_name),
    )


def load_graph(work_directory: Path) -> ProjectGraph:
    """The stored project graph; an unreadable or invalid file is PROJECT_PARSE_ERROR (GRAPH_FILE_INVALID)."""
    result = read_graph(work_directory)
    if result.graph is None:
        raise error(
            PROJECT_PARSE_ERROR,
            "The stored project graph is missing, unreadable or invalid; run reimport_system_definition to rebuild it.",
            reason=REASON_GRAPH_FILE_INVALID,
            path=str(graph_path(work_directory)),
            problem=result.problem,
        )
    return result.graph


def _optional_kind(selector_kind: object) -> SelectorKind | None:
    """None = not given (matters for list_components without selector); otherwise the parsed kind."""
    return None if selector_kind is None else parse_selector_kind(selector_kind)


class QueryService:
    """Read-only queries over the persisted project graph of one session."""

    def __init__(
        self,
        session_root: str | os.PathLike[str] | None = None,
        log_level: LogLevel | str = LogLevel.INFO,
    ) -> None:
        self._access = SessionAccess(session_root, log_level)
        self.guard = self._access.guard

    # -- common pipeline ---------------------------------------------------------------------------
    def _run(
        self,
        capability: str,
        session_label: str,
        log_level: LogLevel | str | None,
        detail_level: object,
        mutation_name: object,
        validate: Callable[[DetailLevel], object],
        query: Callable[[GraphIndex, DetailLevel, object], tuple[T, list[str]]],
        build: Callable[[T, ResponseEnvelope], object],
    ):
        work_directory: Path | None = None
        level = LogLevel.INFO
        try:
            level = self._access.level(log_level)
            work_directory, state = self._access.open(session_label)
            state, entry_id = self._access.guard.check(
                state, work_directory, SessionLogBook(work_directory, level), capability
            )
            detail = parse_detail_level(detail_level)
            check_mutation_name(mutation_name)
            checked = validate(detail)
            index = GraphIndex.build(load_graph(work_directory))
            result, notes = query(index, detail, checked)
            return build(result, self._envelope(state, entry_id, detail, notes))
        except Exception as exc:
            report_error(exc, capability, work_directory, level)
            raise

    @staticmethod
    def _envelope(state: SessionState, entry_id: int | None, detail: DetailLevel, notes: list[str]) -> ResponseEnvelope:
        return ResponseEnvelope(
            setup=state.active_setup,
            evidence_sources=[EvidenceSource(kind=EvidenceKind.KNXPROJ, reference=state.source_project_absolute_path)],
            limitation_notes=notes,
            log_book_entry_id=entry_id,
            detail_level=detail,
        )

    # -- capabilities --------------------------------------------------------------------------------
    def list_components(
        self,
        session_label: str,
        component_selector: str | None = None,
        selector_kind: SelectorKind | str | None = None,
        detail_level: DetailLevel | str | None = None,
        mutation_name: str | None = None,
        log_level: LogLevel | str | None = None,
    ) -> ListComponentsResponse:
        """list_components: components by (partial) selector, or all; no match is an empty set."""

        def validate(_detail: DetailLevel) -> SelectorKind | None:
            kind = _optional_kind(selector_kind)
            validate_list_request(component_selector, kind)
            return kind

        def query(index: GraphIndex, detail: DetailLevel, kind: object):
            result = list_components(index, component_selector, kind, detail)  # type: ignore[arg-type]
            return result, result.limitation_notes

        return self._run(
            LIST_COMPONENTS, session_label, log_level, detail_level, mutation_name, validate, query,
            lambda result, envelope: ListComponentsResponse(
                matches=result.views, match_count=result.match_count, ambiguous=result.ambiguous, envelope=envelope
            ),
        )

    def describe_component(
        self,
        session_label: str,
        component_selector: str | None = None,
        selector_kind: SelectorKind | str | None = None,
        detail_level: DetailLevel | str | None = None,
        mutation_name: str | None = None,
        log_level: LogLevel | str | None = None,
    ) -> DescribeComponentResponse:
        """describe_component: the set of matching components; nothing matching is SELECTOR_UNRESOLVED."""

        def validate(_detail: DetailLevel) -> SelectorKind | None:
            kind = _optional_kind(selector_kind)
            validate_describe_request(component_selector, kind)
            return kind

        def query(index: GraphIndex, detail: DetailLevel, kind: object):
            result = describe_components(index, component_selector, kind, detail)  # type: ignore[arg-type]
            return result, result.limitation_notes

        return self._run(
            DESCRIBE_COMPONENT, session_label, log_level, detail_level, mutation_name, validate, query,
            lambda result, envelope: DescribeComponentResponse(
                components=result.views, match_count=result.match_count, ambiguous=result.ambiguous, envelope=envelope
            ),
        )

    def summarize_topology(
        self,
        session_label: str,
        detail_level: DetailLevel | str | None = None,
        mutation_name: str | None = None,
        log_level: LogLevel | str | None = None,
    ) -> SummarizeTopologyResponse:
        """summarize_topology: areas, lines, locations and component distribution."""

        def query(index: GraphIndex, detail: DetailLevel, _checked: object):
            result = summarize(index, detail)
            return result, result.limitation_notes

        return self._run(
            SUMMARIZE_TOPOLOGY, session_label, log_level, detail_level, mutation_name, lambda _d: None, query,
            lambda result, envelope: SummarizeTopologyResponse(
                topology_summary=result.topology_summary, component_counts=result.component_counts, envelope=envelope
            ),
        )

    def trace_group_flow(
        self,
        session_label: str,
        group_address_selector: str | None = None,
        communication_object_ref: str | None = None,
        detail_level: DetailLevel | str | None = None,
        mutation_name: str | None = None,
        log_level: LogLevel | str | None = None,
    ) -> TraceGroupFlowResponse:
        """trace_group_flow: direct participants and flag-based direction of a group address or object."""

        def validate(_detail: DetailLevel) -> None:
            validate_flow_request(group_address_selector, communication_object_ref)

        def query(index: GraphIndex, detail: DetailLevel, _checked: object):
            result = trace(index, group_address_selector, communication_object_ref, detail)
            return result, result.limitation_notes

        return self._run(
            TRACE_GROUP_FLOW, session_label, log_level, detail_level, mutation_name, validate, query,
            lambda result, envelope: TraceGroupFlowResponse(
                group_addresses=result.entries, match_count=result.match_count, ambiguous=result.ambiguous,
                envelope=envelope,
            ),
        )
