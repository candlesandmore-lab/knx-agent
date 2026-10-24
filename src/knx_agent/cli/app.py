"""Typer app: `knx-agent session create|describe|reimport` and
`knx-agent setup list-components|describe-component|summarize-topology|trace-group-flow`."""

from __future__ import annotations

from pathlib import Path

import typer

from knx_agent.contracts import KnxAgentError
from knx_agent.sdk import KnxSessionClient, configure_stderr_logging

app = typer.Typer(help="knx-agent command line interface.", no_args_is_help=True)
session_app = typer.Typer(help="Investigation session commands.", no_args_is_help=True)
app.add_typer(session_app, name="session")
setup_app = typer.Typer(help="Component inspection commands (read-only).", no_args_is_help=True)
app.add_typer(setup_app, name="setup")

_SESSION_ROOT = typer.Option(
    None, "--session-root", help="Folder holding all work-directories (default ./.knx-agent/sessions)."
)
_LOG_LEVEL = typer.Option("INFO", "--log-level", help="Log level: INFO, DEBUG or FULL.")


def _run(call, log_level: str):  # noqa: ANN001
    """Run an SDK call; print JSON on stdout, or ErrorInfo JSON on stderr with exit code 1."""
    configure_stderr_logging(log_level if log_level.upper() in ("INFO", "DEBUG", "FULL") else "INFO")
    try:
        response = call()
    except KnxAgentError as exc:
        typer.echo(exc.error.model_dump_json(), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(response.model_dump_json())


@session_app.command("create")
def create(
    project: Path = typer.Option(..., "--project", help="Path of the .knxproj file."),
    session_label: str = typer.Option(..., "--session-label", help="User-chosen session_label."),
    session_root: Path | None = _SESSION_ROOT,
    log_level: str = _LOG_LEVEL,
) -> None:
    """Create an investigation session and print the response as JSON."""
    client = KnxSessionClient(session_root=session_root)
    _run(lambda: client.create_session(project_path=project, session_label=session_label, log_level=log_level), log_level)


@session_app.command("describe")
def describe(
    session: str = typer.Option(..., "--session", help="The session_label."),
    session_root: Path | None = _SESSION_ROOT,
    log_level: str = _LOG_LEVEL,
) -> None:
    """Describe an investigation session and print the response as JSON."""
    client = KnxSessionClient(session_root=session_root)
    _run(lambda: client.describe_session(session_label=session, log_level=log_level), log_level)


@session_app.command("reimport")
def reimport(
    session: str = typer.Option(..., "--session", help="The session_label."),
    session_root: Path | None = _SESSION_ROOT,
    log_level: str = _LOG_LEVEL,
) -> None:
    """Re-read the bound .knxproj of a session and print the response as JSON."""
    client = KnxSessionClient(session_root=session_root)
    _run(lambda: client.reimport_system_definition(session_label=session, log_level=log_level), log_level)


_SESSION = typer.Option(..., "--session", help="The session_label.")
_DETAIL_LEVEL = typer.Option(None, "--detail-level", help="SUMMARY, MEDIUM (default) or FULL (any case).")
_MUTATION = typer.Option(
    None, "--mutation", help="mutation_name; 'default' or omitted targets the default setup (mutations: todo 08)."
)
_SELECTOR_KIND = typer.Option(
    None, "--selector-kind", help="ANY (default), NAME, INSTANCE_PATH, INDIVIDUAL_ADDRESS or ETS_ID (any case)."
)

# All values are plain strings: the core validates them, so a bad value yields the catalogue error code.


@setup_app.command("list-components")
def list_components(
    session: str = _SESSION,
    query: str | None = typer.Option(
        None, "--query", help="Component selector: name, instance path ('EG/Room/'), 1.1.5 or an ETS id; omit to list all."
    ),
    selector_kind: str | None = _SELECTOR_KIND,
    detail_level: str | None = _DETAIL_LEVEL,
    mutation: str | None = _MUTATION,
    session_root: Path | None = _SESSION_ROOT,
    log_level: str = _LOG_LEVEL,
) -> None:
    """List components (JSON): all, or those matching a selector; no match is an empty set."""
    client = KnxSessionClient(session_root=session_root)
    _run(
        lambda: client.list_components(
            session_label=session, component_selector=query, selector_kind=selector_kind,
            detail_level=detail_level, mutation_name=mutation, log_level=log_level,
        ),
        log_level,
    )


@setup_app.command("describe-component")
def describe_component(
    session: str = _SESSION,
    component: str = typer.Option(..., "--component", help="Component selector (see list-components --query)."),
    selector_kind: str | None = _SELECTOR_KIND,
    detail_level: str | None = _DETAIL_LEVEL,
    mutation: str | None = _MUTATION,
    session_root: Path | None = _SESSION_ROOT,
    log_level: str = _LOG_LEVEL,
) -> None:
    """Describe the components matching a selector (JSON); nothing matching is SELECTOR_UNRESOLVED."""
    client = KnxSessionClient(session_root=session_root)
    _run(
        lambda: client.describe_component(
            session_label=session, component_selector=component, selector_kind=selector_kind,
            detail_level=detail_level, mutation_name=mutation, log_level=log_level,
        ),
        log_level,
    )


@setup_app.command("summarize-topology")
def summarize_topology(
    session: str = _SESSION,
    detail_level: str | None = _DETAIL_LEVEL,
    mutation: str | None = _MUTATION,
    session_root: Path | None = _SESSION_ROOT,
    log_level: str = _LOG_LEVEL,
) -> None:
    """Summarize areas, lines, locations and the component distribution (JSON)."""
    client = KnxSessionClient(session_root=session_root)
    _run(
        lambda: client.summarize_topology(
            session_label=session, detail_level=detail_level, mutation_name=mutation, log_level=log_level
        ),
        log_level,
    )


@setup_app.command("trace-group-flow")
def trace_group_flow(
    session: str = _SESSION,
    group_address: str | None = typer.Option(
        None, "--group-address", help="Group address (for example 5/0/12) or a partial group address name."
    ),
    object_ref: str | None = typer.Option(
        None, "--object-ref", help="Communication object id '<component id>/co/<ref id>' (exactly one of the two)."
    ),
    detail_level: str | None = _DETAIL_LEVEL,
    mutation: str | None = _MUTATION,
    session_root: Path | None = _SESSION_ROOT,
    log_level: str = _LOG_LEVEL,
) -> None:
    """Trace the direct participants of a group address or communication object (JSON)."""
    client = KnxSessionClient(session_root=session_root)
    _run(
        lambda: client.trace_group_flow(
            session_label=session, group_address_selector=group_address, communication_object_ref=object_ref,
            detail_level=detail_level, mutation_name=mutation, log_level=log_level,
        ),
        log_level,
    )


def main() -> None:
    """Console script entry point."""
    app()
