from __future__ import annotations

import getpass

import typer

from config.models import list_available_models
from config.secrets import SUPPORTED_PROVIDERS, delete_api_key, save_api_key
from config.settings import set_default_model, settings


def configure_setup(config=None) -> None:
    if config is None:
        config = settings
    providers = list(SUPPORTED_PROVIDERS.keys())
    typer.echo("Available LLM providers:\n")
    for i, p in enumerate(providers, 1):
        typer.echo(f"  {i}. {p}")

    choice = typer.prompt("\nChoose provider", type=int, default=1, show_default=False)
    if not (1 <= choice <= len(providers)):
        typer.echo("Invalid choice.", err=True)
        raise typer.Exit(1)

    provider = providers[choice - 1]
    api_key = getpass.getpass(f"Enter API key for {provider}: ").strip()
    if not api_key:
        typer.echo("API key cannot be empty.", err=True)
        raise typer.Exit(1)

    save_api_key(provider, api_key, config.workspace_id)
    config.llm_provider = provider
    if config.workspace_path and config.workspace_id:
        from config.workspace import WorkspaceSettings
        ws_settings = WorkspaceSettings(
            workspace_id=config.workspace_id,
            name=config.workspace_name or "",
            path=config.workspace_path,
            db_url=config.db_url,
            llm_provider=config.llm_provider,
            llm_model=config.llm_model,
            default_models=dict(config.default_models),
            auto_restore_sessions=config.auto_restore_sessions,
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
        set_default_model(config, provider, models[model_choice - 1])
        typer.echo(f"Default model set to: {models[model_choice - 1]}")
    else:
        typer.echo("Skipped. You can pass --model at query time.")


def forget_key(config=None) -> None:
    if config is None:
        config = settings
    provider = config.llm_provider
    try:
        delete_api_key(provider, config.workspace_id)
        typer.echo(f"Removed API key for {provider} from keychain.")
    except Exception:
        typer.echo(f"No key found for {provider}.", err=True)
