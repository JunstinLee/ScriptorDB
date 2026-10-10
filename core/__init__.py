from __future__ import annotations

"""Core infrastructure: process-wide logging.

- `logging_setup.py` — `get_logger`/`configure_logging`/`unconfigure` (root "scriptordb" logger)
- `log_to_file.py` — import-time side effect: redirect stdout/stderr to `logs/run_<timestamp>.log`
- `playwright_browsers.py` — import-time side effect: point Playwright at the bundled browser build
"""
