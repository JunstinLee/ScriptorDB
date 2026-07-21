from __future__ import annotations

from typing import Annotated, Optional

import typer

from cli import app
from cli.cmd_common import _get_config_ctx, ensure_workspace
from config.settings import load_for_workspace
from config.workspace import WorkspaceNotFoundError
from services.setup_service import configure_setup, forget_key


@app.command()
def setup(
    workspace: Annotated[Optional[str], typer.Option("--workspace", help="临时工作区 ID")] = None,
):
    config = _get_config_ctx()
    if workspace:
        try:
            load_for_workspace(config, workspace)
        except WorkspaceNotFoundError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(1)
    elif not ensure_workspace():
        raise typer.Exit(1)
    configure_setup(config)


@app.command()
def forget(
    workspace: Annotated[Optional[str], typer.Option("--workspace", help="临时工作区 ID")] = None,
):
    config = _get_config_ctx()
    if workspace:
        try:
            load_for_workspace(config, workspace)
        except WorkspaceNotFoundError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(1)
    elif not ensure_workspace():
        raise typer.Exit(1)
    forget_key(config)
