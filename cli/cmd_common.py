from __future__ import annotations

import typer

from config.app_config import AppConfig
from config.settings import load_default_workspace


def _push_ctx(config: AppConfig) -> None:
    import click
    ctx = click.Context(click.Command("main"), obj=config)
    ctx.__enter__()


def _get_config_ctx() -> AppConfig:
    import click
    ctx = click.get_current_context()
    return ctx.obj


def ensure_workspace() -> bool:
    config = _get_config_ctx()
    if config.workspace_id:
        return True
    if load_default_workspace():
        return True
    typer.echo(
        "No active workspace. Run 'python main.py workspace list' to create or select one.",
        err=True,
    )
    return False
