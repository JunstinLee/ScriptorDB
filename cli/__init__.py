from __future__ import annotations

import typer

app = typer.Typer()

from cli.cmd_undo import undo_app  # noqa: E402
app.add_typer(undo_app, name="undo")
