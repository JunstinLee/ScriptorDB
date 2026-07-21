from __future__ import annotations

from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.markdown import Markdown

from agents.db_agent import get_agent
from cli import app
from cli.cmd_common import _get_config_ctx, ensure_workspace
from config.settings import load_for_workspace
from config.workspace import WorkspaceNotFoundError
from services.model_service import resolve_user_model


@app.command()
def interactive(
    provider: Annotated[str | None, typer.Option("--provider", "-p")] = None,
    model: Annotated[str | None, typer.Option("--model", "-m")] = None,
    workspace: Annotated[Optional[str], typer.Option("--workspace", help="临时工作区 ID")] = None,
):
    import readline

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
        if matched:
            config.llm_model = matched

    console = Console()
    console.print("[bold green]ScriptorDB — 输入 'exit' 退出[/bold green]\n")

    while True:
        try:
            prompt = input("> ")
        except (EOFError, KeyboardInterrupt):
            break

        if prompt.strip().lower() in ("exit", "quit"):
            break
        if not prompt.strip():
            continue

        a = get_agent(config=config)
        result = a.run_sync(prompt, deps=config)
        console.print(Markdown(str(result.output)))
