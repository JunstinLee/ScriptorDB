from __future__ import annotations

import asyncio
import getpass
from pathlib import Path
from typing import Annotated, Optional

import typer

from agents.db_agent import get_agent
from cli import app
from cli import workspace_cli  # noqa: F401
from config.models import fuzzy_match_model, list_available_models
from config.secrets import SUPPORTED_PROVIDERS, delete_api_key, save_api_key
from config.settings import load_default_workspace, load_for_workspace, set_default_model, settings
from config.workspace import (
    WorkspaceAlreadyExistsError,
    WorkspaceNotFoundError,
    WorkspaceNotSelectedError,
    WorkspaceRegistry,
)


def _ensure_workspace() -> bool:
    if settings.workspace_id:
        return True
    if load_default_workspace():
        return True
    typer.echo(
        "No active workspace. Run 'python main.py workspace list' to create or select one.",
        err=True,
    )
    return False


@app.command()
def setup(
    workspace: Annotated[Optional[str], typer.Option("--workspace", help="临时工作区 ID")] = None,
):
    if workspace:
        try:
            load_for_workspace(settings, workspace)
        except WorkspaceNotFoundError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(1)
    elif not _ensure_workspace():
        raise typer.Exit(1)

    providers = list(SUPPORTED_PROVIDERS.keys())
    typer.echo("Available LLM providers:\n")
    for i, p in enumerate(providers, 1):
        typer.echo(f"  {i}. {p}")

    choice = typer.prompt(
        "\nChoose provider",
        type=int,
        default=1,
        show_default=False,
    )
    if not (1 <= choice <= len(providers)):
        typer.echo("Invalid choice.", err=True)
        raise typer.Exit(1)

    provider = providers[choice - 1]
    api_key = getpass.getpass(f"Enter API key for {provider}: ").strip()
    if not api_key:
        typer.echo("API key cannot be empty.", err=True)
        raise typer.Exit(1)

    save_api_key(provider, api_key, settings.workspace_id)
    settings.llm_provider = provider
    from config.workspace import WorkspaceSettings
    if settings.workspace_path and settings.workspace_id:
        ws_settings = WorkspaceSettings(
            workspace_id=settings.workspace_id,
            name=settings.workspace_name or "",
            path=settings.workspace_path,
            db_url=settings.db_url,
            llm_provider=settings.llm_provider,
            llm_model=settings.llm_model,
            default_models=dict(settings.default_models),
            auto_restore_sessions=settings.auto_restore_sessions,
        )
        ws_settings.save()
    typer.echo(f"\nAPI key for {provider} saved to system keychain.")

    try:
        models = list_available_models(provider, use_cache=False)
    except Exception as e:
        typer.echo(f"\nCould not fetch model list: {e}", err=True)
        typer.echo("You can still pass --model when running queries.")
        return

    if not models:
        typer.echo("\nNo models returned by provider. Use --model to specify one at runtime.")
        return

    typer.echo(f"\nAvailable models for {provider}:\n")
    for i, m in enumerate(models, 1):
        typer.echo(f"  {i}. {m}")

    model_choice = typer.prompt(
        "\nChoose default model (or press Enter to skip)",
        type=int,
        default=0,
        show_default=False,
    )
    if model_choice and 1 <= model_choice <= len(models):
        set_default_model(settings, provider, models[model_choice - 1])
        typer.echo(f"Default model set to: {models[model_choice - 1]}")
    else:
        typer.echo("Skipped. You can pass --model at query time.")


@app.command()
def forget(
    workspace: Annotated[Optional[str], typer.Option("--workspace", help="临时工作区 ID")] = None,
):
    if workspace:
        try:
            load_for_workspace(settings, workspace)
        except WorkspaceNotFoundError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(1)
    elif not _ensure_workspace():
        raise typer.Exit(1)
    provider = settings.llm_provider
    try:
        delete_api_key(provider, settings.workspace_id)
        typer.echo(f"Removed API key for {provider} from keychain.")
    except Exception:
        typer.echo(f"No key found for {provider}.", err=True)


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
    elif not _ensure_workspace():
        raise typer.Exit(1)
    p = provider or settings.llm_provider
    try:
        ms = list_available_models(p)
    except Exception as e:
        typer.echo(f"Failed to fetch models: {e}", err=True)
        raise typer.Exit(1)
    for m in ms:
        typer.echo(m)


@app.command()
def ask(
    prompt: Annotated[str, typer.Argument(help="自然语言数据库操作请求")],
    model: Annotated[str | None, typer.Option("--model", "-m")] = None,
    provider: Annotated[str | None, typer.Option("--provider", "-p")] = None,
    workspace: Annotated[Optional[str], typer.Option("--workspace", help="临时工作区 ID")] = None,
):
    if workspace:
        try:
            load_for_workspace(settings, workspace)
        except WorkspaceNotFoundError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(1)
    elif not _ensure_workspace():
        raise typer.Exit(1)

    if provider:
        settings.llm_provider = provider

    if model:
        matched = fuzzy_match_model(settings.llm_provider, model)
        if matched and matched != model and not model.startswith(f"{settings.llm_provider}:"):
            typer.echo(f"Using model: {matched}")
            model = matched

    a = get_agent(model) if model else get_agent()
    result = a.run_sync(prompt, deps=settings)
    typer.echo(result.output)


@app.command()
def interactive(
    provider: Annotated[str | None, typer.Option("--provider", "-p")] = None,
    model: Annotated[str | None, typer.Option("--model", "-m")] = None,
    workspace: Annotated[Optional[str], typer.Option("--workspace", help="临时工作区 ID")] = None,
):
    import readline
    from rich.console import Console
    from rich.markdown import Markdown

    if workspace:
        try:
            load_for_workspace(settings, workspace)
        except WorkspaceNotFoundError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(1)
    elif not _ensure_workspace():
        raise typer.Exit(1)

    if provider:
        settings.llm_provider = provider
    if model:
        matched = fuzzy_match_model(settings.llm_provider, model)
        if matched:
            settings.llm_model = matched

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

        a = get_agent()
        result = a.run_sync(prompt, deps=settings)
        console.print(Markdown(result.output))


undo_app = typer.Typer(help="Undo 操作")
app.add_typer(undo_app, name="undo")


@undo_app.command("list")
def undo_list():
    """列出所有可回退的轮次。"""
    if not _ensure_workspace():
        raise typer.Exit(1)
    from tools.db_connection import get_engine
    from tools.undo_log import list_all_groups

    engine = get_engine(settings.db_url)
    groups = list_all_groups(engine)
    if not groups:
        typer.echo("没有可回退的操作记录。")
        return
    for g in groups:
        status_icon = {"pending": "~", "completed": "+", "reverted": "-"}.get(
            g["status"], "?"
        )
        typer.echo(
            f"  [{status_icon}] #{g['id']} seq={g['sequence']} status={g['status']} "
            f"prompt={g['prompt_preview'][:40]}"
        )


@undo_app.command("revert")
def undo_revert(group_id: Annotated[int, typer.Argument(help="回退到的 group ID")]):
    """回退到指定轮次之后的状态。"""
    if not _ensure_workspace():
        raise typer.Exit(1)
    from tools.db_connection import get_engine
    from tools.undo_log import revert_to_group

    engine = get_engine(settings.db_url)
    try:
        reverted = revert_to_group(engine, group_id)
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    typer.echo(f"已回退 {len(reverted)} 个操作。被回退的 group: {reverted}")


@app.command()
def serve(
    host: Annotated[str, typer.Option("--host", "-h")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", "-p")] = 8000,
    reload: Annotated[bool, typer.Option("--reload/--no-reload")] = True,
):
    import uvicorn

    load_default_workspace()
    typer.echo(f"Starting ScriptorDB API server at http://{host}:{port}")
    if settings.workspace_id:
        typer.echo(
            f"Active workspace: {settings.workspace_name} ({settings.workspace_id}) @ {settings.workspace_path}"
        )
    else:
        typer.echo("No active workspace — endpoints requiring one will return 409.")
    uvicorn.run("server.app:app", host=host, port=port, reload=reload)
