from __future__ import annotations

"""Desktop entry point: the bundled FastAPI app + React SPA inside a native window.

`main.py` stays the CLI entry; release bundles launch this module instead. It boots the
same `api.app:app` in a background thread and points a pywebview (WKWebView) window at
it, so backend and frontend ship as a single double-clickable app.

`api/app.py` mounts `frontend/dist` at `/`, so the window only needs the local URL.
Layout assumed by the bundle: `browsers/` (Chromium for Playwright), `frontend/dist/`,
and the app packages all sit next to this file — hence the `chdir` below, which also
gives relative paths a predictable base when macOS launches the app from Finder.
"""

import os
import socket
import sys
import threading
import time
from pathlib import Path

import core.playwright_browsers  # noqa: F401  must precede any playwright import

BASE_DIR = Path(__file__).resolve().parent
HOST = "127.0.0.1"
STARTUP_TIMEOUT = 60.0


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind((HOST, 0))
        return int(sock.getsockname()[1])


def _wait_until_listening(port: int) -> bool:
    deadline = time.monotonic() + STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.5)
            if sock.connect_ex((HOST, port)) == 0:
                return True
        time.sleep(0.15)
    return False


def _serve(port: int) -> None:
    import uvicorn

    from config.settings import load_default_workspace

    load_default_workspace()
    uvicorn.Server(
        uvicorn.Config("api.app:app", host=HOST, port=port, log_level="warning")
    ).run()


def main() -> int:
    os.chdir(BASE_DIR)
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

    import webview

    port = _free_port()
    threading.Thread(target=_serve, args=(port,), daemon=True).start()
    if not _wait_until_listening(port):
        sys.stderr.write(
            f"ScriptorDB: API did not start within {STARTUP_TIMEOUT:.0f}s\n"
        )
        return 1

    webview.create_window(
        "ScriptorDB",
        f"http://{HOST}:{port}/",
        width=1440,
        height=920,
        min_size=(1024, 700),
    )
    webview.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
