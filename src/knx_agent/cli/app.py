"""Typer app: `knx-agent session create|describe|reimport`."""

from __future__ import annotations

from pathlib import Path

import typer

from knx_agent.contracts import KnxAgentError
from knx_agent.sdk import KnxSessionClient, configure_stderr_logging

app = typer.Typer(help="knx-agent command line interface.", no_args_is_help=True)
session_app = typer.Typer(help="Investigation session commands.", no_args_is_help=True)
app.add_typer(session_app, name="session")

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


def main() -> None:
    """Console script entry point."""
    app()
