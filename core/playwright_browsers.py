from __future__ import annotations

"""Point Playwright at the browser build bundled with the release.

Release bundles ship the Chromium build in `<repo root>/browsers`, while
Playwright looks in its per-user cache directory by default. Importing this
module sets `PLAYWRIGHT_BROWSERS_PATH` to the bundled copy, so the CLI and the
API both resolve it. When the directory is absent — a plain source checkout
that never ran the bundled install — Playwright keeps its default location.
"""

import os
from pathlib import Path

BUNDLED_BROWSERS_PATH = Path(__file__).resolve().parent.parent / "browsers"

if BUNDLED_BROWSERS_PATH.is_dir():
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(BUNDLED_BROWSERS_PATH))
