"""Typer app: `knx-agent session describe --session <session_label>`."""

from __future__ import annotations

import typer

from knx_agent.contracts import KnxAgentError
from knx_agent.sdk import KnxSessionClient

app = typer.Typer(help="knx-agent command line interface.", no_args_is_help=True)
session_app = typer.Typer(help="Investigation session commands.", no_args_is_help=True)
app.add_typer(session_app, name="session")


@session_app.command("describe")
def describe(session: str = typer.Option(..., "--session", help="The session_label.")) -> None:
    """Describe an investigation session and print the response as JSON."""
    try:
        response = KnxSessionClient().describe_session(session_label=session)
    except KnxAgentError as exc:
        typer.echo(exc.error.model_dump_json(), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(response.model_dump_json())


def main() -> None:
    """Console script entry point."""
    app()
