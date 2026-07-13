from __future__ import annotations

import typer

from cli import app
from config.settings import load_default_workspace, settings


def ensure_workspace() -> bool:
    if settings.workspace_id:
        return True
    if load_default_workspace():
        return True
    typer.echo(
        "No active workspace. Run 'python main.py workspace list' to create or select one.",
        err=True,
    )
    return False
