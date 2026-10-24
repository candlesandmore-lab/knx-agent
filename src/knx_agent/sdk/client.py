"""KnxSessionClient: SDK entry point; delegates to the application layer."""

from __future__ import annotations

import os

from knx_agent.application import QueryService, SessionService
from knx_agent.contracts import (
    CreateSessionResponse,
    DescribeComponentResponse,
    DescribeSessionResponse,
    DetailLevel,
    ListComponentsResponse,
    LogLevel,
    ReimportSystemDefinitionResponse,
    SelectorKind,
    SummarizeTopologyResponse,
    TraceGroupFlowResponse,
)


class KnxSessionClient:
    """SDK client exposing catalogue capabilities as methods.

    session_root: folder holding all work-directories (default ./.knx-agent/sessions); the only
    way to set it besides the CLI option and MCP startup argument. No environment variable is read.
    log_level: default INFO/DEBUG/FULL of this client; every method also accepts a per-call log_level.
    """

    def __init__(
        self,
        session_root: str | os.PathLike[str] | None = None,
        log_level: LogLevel | str = LogLevel.INFO,
    ) -> None:
        self._service = SessionService(session_root=session_root, log_level=log_level)
        self._queries = QueryService(session_root=session_root, log_level=log_level)

    def create_session(
        self, project_path: str | os.PathLike[str], session_label: str, log_level: LogLevel | str | None = None
    ) -> CreateSessionResponse:
        """Create an investigation session bound to a .knxproj file."""
        return self._service.create_session(os.fspath(project_path), session_label, log_level)

    def describe_session(
        self, session_label: str, log_level: LogLevel | str | None = None
    ) -> DescribeSessionResponse:
        """Describe an investigation session (runs the project refresh check first)."""
        return self._service.describe_session(session_label, log_level)

    def reimport_system_definition(
        self, session_label: str, log_level: LogLevel | str | None = None
    ) -> ReimportSystemDefinitionResponse:
        """Explicitly re-read the bound .knxproj of a session."""
        return self._service.reimport_system_definition(session_label, log_level)

    def list_components(
        self,
        session_label: str,
        component_selector: str | None = None,
        selector_kind: SelectorKind | str | None = None,
        detail_level: DetailLevel | str | None = None,
        mutation_name: str | None = None,
        log_level: LogLevel | str | None = None,
    ) -> ListComponentsResponse:
        """List components by selector (name, instance path, individual address, ETS id) or all of them."""
        return self._queries.list_components(
            session_label, component_selector, selector_kind, detail_level, mutation_name, log_level
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
        """Describe the components matching a selector (SELECTOR_UNRESOLVED when nothing matches)."""
        return self._queries.describe_component(
            session_label, component_selector, selector_kind, detail_level, mutation_name, log_level
        )

    def summarize_topology(
        self,
        session_label: str,
        detail_level: DetailLevel | str | None = None,
        mutation_name: str | None = None,
        log_level: LogLevel | str | None = None,
    ) -> SummarizeTopologyResponse:
        """Summarize areas, lines, locations and the component distribution."""
        return self._queries.summarize_topology(session_label, detail_level, mutation_name, log_level)

    def trace_group_flow(
        self,
        session_label: str,
        group_address_selector: str | None = None,
        communication_object_ref: str | None = None,
        detail_level: DetailLevel | str | None = None,
        mutation_name: str | None = None,
        log_level: LogLevel | str | None = None,
    ) -> TraceGroupFlowResponse:
        """Trace the direct participants of a group address or communication object (exactly one selector)."""
        return self._queries.trace_group_flow(
            session_label, group_address_selector, communication_object_ref, detail_level, mutation_name, log_level
        )
