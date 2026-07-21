from __future__ import annotations

import sys

import typer

from cli import app
from cli import commands  # noqa: F401
from cli.dispatcher import run_dispatcher
from config.settings import load_default_workspace, settings


@app.callback()
def main_callback(ctx: typer.Context):
    load_default_workspace()
    ctx.obj = settings


if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        load_default_workspace()
        from cli.cmd_common import _push_ctx
        _push_ctx(settings)
        run_dispatcher()
