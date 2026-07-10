from __future__ import annotations

from typing import Annotated, Optional

import typer

from cli import app
from cli.cmd_common import ensure_workspace
from config.models import list_available_models
from config.settings import load_for_workspace, settings
from config.workspace import WorkspaceNotFoundError


@app.command()
def models(
    provider: Annotated[str | None, typer.Option("--provider", "-p")] = None,
    workspace: Annotated[Optional[str], typer.Option("--workspace", help="临时工作区 ID")] = None,
):
    """List available models for the given (or current) provider."""
    if workspace:
        try:
            load_for_workspace(settings, workspace)
        except WorkspaceNotFoundError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(1)
    elif not ensure_workspace():
        raise typer.Exit(1)
    p = provider or settings.llm_provider
    try:
        ms = list_available_models(p)
    except Exception as e:
        typer.echo(f"Failed to fetch models: {e}", err=True)
        raise typer.Exit(1)
    for m in ms:
        typer.echo(m)
