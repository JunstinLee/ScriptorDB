from __future__ import annotations

from typing import Annotated

import typer

from cli.cmd_common import _get_config_ctx, ensure_workspace
from tools.undo_repository import UndoRepository

undo_app = typer.Typer(help="Undo 操作")


@undo_app.command("list")
def undo_list():
    """列出所有可回退的轮次。"""
    if not ensure_workspace():
        raise typer.Exit(1)

    config = _get_config_ctx()
    repo = UndoRepository(config.db_url, config.workspace_id or "")
    groups = repo.list_all_groups()
    if not groups:
        typer.echo("没有可回退的操作记录。")
        return
    for g in groups:
        status_icon = {"pending": "~", "completed": "+", "reverted": "-"}.get(
            g["status"], "?"
        )
        typer.echo(
            f"  [{status_icon}] #{g['id']} seq={g['sequence']} status={g['status']} "
            f"prompt={g['prompt_preview'][:40]}"
        )


@undo_app.command("revert")
def undo_revert(group_id: Annotated[int, typer.Argument(help="回退到的 group ID")]):
    """回退到指定轮次之后的状态。"""
    if not ensure_workspace():
        raise typer.Exit(1)

    config = _get_config_ctx()
    repo = UndoRepository(config.db_url, config.workspace_id or "")
    try:
        reverted = repo.revert_to_group(group_id)
    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    typer.echo(f"已回退 {len(reverted)} 个操作。被回退的 group: {reverted}")
