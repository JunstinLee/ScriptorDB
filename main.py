from __future__ import annotations

import sys

from cli import app
from cli import commands  # noqa: F401
from cli.dispatcher import run_dispatcher

if __name__ == "__main__":
    if len(sys.argv) > 1:
        app()
    else:
        run_dispatcher()
