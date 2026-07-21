from __future__ import annotations

from typing import Annotated

import typer

from cli import app
from config.settings import load_default_workspace, settings


@app.command()
def serve(
    host: Annotated[str, typer.Option("--host", "-h")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", "-p")] = 8000,
    reload: Annotated[bool, typer.Option("--reload/--no-reload")] = True,
):
    import uvicorn

    load_default_workspace()
    config = settings
    typer.echo(f"Starting ScriptorDB API server at http://{host}:{port}")
    if config.workspace_id:
        typer.echo(
            f"Active workspace: {config.workspace_name} ({config.workspace_id}) @ {config.workspace_path}"
        )
    else:
        typer.echo("No active workspace — endpoints requiring one will return 409.")
    uvicorn.run("server.app:app", host=host, port=port, reload=reload)
