from __future__ import annotations

import asyncio
import getpass
from typing import Annotated

import typer

from agents.db_agent import get_agent
from config.secrets import SUPPORTED_PROVIDERS, delete_api_key, save_api_key
from config.settings import settings

app = typer.Typer()


@app.command()
def setup():
    providers = list(SUPPORTED_PROVIDERS.keys())
    typer.echo("Available LLM providers:\n")
    for i, p in enumerate(providers, 1):
        typer.echo(f"  {i}. {p} ({SUPPORTED_PROVIDERS[p]})")

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


@app.command()
def forget():
    provider = settings.llm_provider
    try:
        delete_api_key(provider)
        typer.echo(f"Removed API key for {provider} from keychain.")
    except Exception:
        typer.echo(f"No key found for {provider}.", err=True)


@app.command()
def ask(
    prompt: Annotated[str, typer.Argument(help="自然语言数据库操作请求")],
    model: Annotated[str | None, typer.Option("--model", "-m")] = None,
    provider: Annotated[str | None, typer.Option("--provider", "-p")] = None,
):
    if provider:
        settings.llm_provider = provider

    a = get_agent(model) if model else get_agent()
    result = a.run_sync(prompt, deps=settings)
    typer.echo(result.output)


@app.command()
def interactive(
    provider: Annotated[str | None, typer.Option("--provider", "-p")] = None,
):
    import readline
    from rich.console import Console
    from rich.markdown import Markdown

    if provider:
        settings.llm_provider = provider

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
def serve():
    asyncio.run(_serve())


async def _serve():
    from pydantic_ai.mcp import MCPServerStdio

    a = get_agent()
    async with MCPServerStdio(
        name="ScriptorDB",
        version="0.1.0",
        agent=a,
    ) as server:
        await server.run()


if __name__ == "__main__":
    app()
