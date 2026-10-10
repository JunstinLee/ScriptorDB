from __future__ import annotations

import sys
from typing import Annotated

import typer

from cli import app
from config.settings import load_default_workspace, settings


def _run_server_on_os_port(host: str) -> None:
    """用 OS 分配的空闲端口启动 uvicorn，并报告绑定后的真实端口。

    `uvicorn.run` 拿不到绑定后的端口，因此显式构造 `uvicorn.Server` 并在 startup
    之后读 socket；也正因为要自己读 socket，该模式下不支持 `--reload`
    （reload 时端口在 reloader 子进程里才绑定）。

    端口要写到启动命令时的 `sys.stdout`：`api.app` 导入时 `core.log_to_file`
    会把 `sys.stdout` 换成日志文件。
    """
    import uvicorn

    console = sys.stdout

    class _PortReportingServer(uvicorn.Server):
        async def startup(self, sockets=None) -> None:
            await super().startup(sockets)
            bound = self.servers[0].sockets[0].getsockname()[1]
            console.write(f"ScriptorDB API listening on http://{host}:{bound}\n")
            console.flush()

    _PortReportingServer(uvicorn.Config("api.app:app", host=host, port=0)).run()


@app.command()
def serve(
    host: Annotated[str, typer.Option("--host", "-h")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", "-p")] = 8000,
    reload: Annotated[bool, typer.Option("--reload/--no-reload")] = True,
):
    import uvicorn

    load_default_workspace()
    config = settings
    typer.echo(f"Starting ScriptorDB API server at http://{host}:{port}")
    if config.workspace_id:
        typer.echo(
            f"Active workspace: {config.workspace_name} ({config.workspace_id}) @ {config.workspace_path}"
        )
    else:
        typer.echo("No active workspace — endpoints requiring one will return 409.")
    if port:
        uvicorn.run("api.app:app", host=host, port=port, reload=reload)
    else:
        _run_server_on_os_port(host)
