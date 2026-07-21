from __future__ import annotations

from typing import Annotated, Optional

import typer

from agents.db_agent import get_agent
from cli import app
from cli.cmd_common import _get_config_ctx, ensure_workspace
from config.settings import load_for_workspace
from config.workspace import WorkspaceNotFoundError
from services.model_service import resolve_user_model


@app.command()
def ask(
    prompt: Annotated[str, typer.Argument(help="自然语言数据库操作请求")],
    model: Annotated[str | None, typer.Option("--model", "-m")] = None,
    provider: Annotated[str | None, typer.Option("--provider", "-p")] = None,
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

    if provider:
        config.llm_provider = provider

    if model:
        matched = resolve_user_model(config.llm_provider, model)
        if matched and matched != model:
            typer.echo(f"Using model: {matched}")
        model = matched

    a = get_agent(config, model=model)
    result = a.run_sync(prompt, deps=config)
    typer.echo(result.output)
