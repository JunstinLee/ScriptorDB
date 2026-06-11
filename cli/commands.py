from __future__ import annotations

import asyncio
import getpass
from typing import Annotated

import typer

from agents.db_agent import get_agent
from cli import app
from config.models import fuzzy_match_model, list_available_models
from config.secrets import SUPPORTED_PROVIDERS, delete_api_key, save_api_key
from config.settings import settings


@app.command()
def setup():
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

    save_api_key(provider, api_key)
    settings.llm_provider = provider
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
        settings.llm_model = models[model_choice - 1]
        typer.echo(f"Default model set to: {settings.llm_model}")
    else:
        typer.echo("Skipped. You can pass --model at query time.")


@app.command()
def forget():
    provider = settings.llm_provider
    try:
        delete_api_key(provider)
        typer.echo(f"Removed API key for {provider} from keychain.")
    except Exception:
        typer.echo(f"No key found for {provider}.", err=True)


@app.command()
def models(
    provider: Annotated[str | None, typer.Option("--provider", "-p")] = None,
):
    """List available models for the given (or current) provider."""
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
):
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
):
    import readline
    from rich.console import Console
    from rich.markdown import Markdown

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


@app.command()
def serve(
    host: Annotated[str, typer.Option("--host", "-h")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", "-p")] = 8000,
    reload: Annotated[bool, typer.Option("--reload/--no-reload")] = True,
):
    import uvicorn

    typer.echo(f"Starting ScriptorDB API server at http://{host}:{port}")
    uvicorn.run("server.app:app", host=host, port=port, reload=reload)
