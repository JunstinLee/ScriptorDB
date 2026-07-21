from __future__ import annotations

import shlex
from pathlib import Path

import typer

from agents.db_agent import reset_agent_cache
from cli import workspace_cli  # noqa: F401
from cli.commands import ask, forget, interactive, models, serve, setup
from cli.cmd_common import _get_config_ctx
from config.settings import load_default_workspace, load_for_workspace
from config.workspace import WorkspaceRegistry, migrate_legacy

COMMAND_MAP = {
    "1": setup,
    "setup": setup,
    "2": forget,
    "forget": forget,
    "3": models,
    "models": models,
    "4": ask,
    "ask": ask,
    "5": interactive,
    "interactive": interactive,
    "6": serve,
    "serve": serve,
    "7": "workspace",
    "workspace": "workspace",
    "8": "undo",
    "undo": "undo",
}


def show_help():
    typer.echo("命令列表:")
    typer.echo("  1. setup       — 配置 LLM provider 和 API key")
    typer.echo("  2. forget      — 删除 API key")
    typer.echo("  3. models      — 列出可用模型")
    typer.echo("  4. ask         — 执行单次查询")
    typer.echo("  5. interactive — 进入交互式查询")
    typer.echo("  6. serve       — 启动 API server")
    typer.echo("  7. workspace   — 切换/新建工作区")
    typer.echo("  8. undo        — 撤销操作（list / revert <id>）")
    typer.echo("  help           — 显示帮助")
    typer.echo("  exit / quit    — 退出")


def _print_workspace_banner() -> None:
    config = _get_config_ctx()
    if config.workspace_id:
        typer.echo(
            f"📁 当前工作区: {config.workspace_name} ({config.workspace_id}) @ {config.workspace_path}\n"
        )
    else:
        typer.echo("📁 当前无激活工作区 — 部分命令会要求先选择/创建。\n")


def _workspace_selection_menu() -> None:
    """首次进入：列出已有工作区供选择，或新建。"""
    config = _get_config_ctx()
    registry = WorkspaceRegistry()
    recs = registry.list()

    if not recs:
        typer.echo("还没有任何工作区。\n")
        _interactive_create_workspace(registry)
        return

    typer.echo("可用工作区：\n")
    for i, rec in enumerate(recs, 1):
        marker = " *" if rec.id == config.workspace_id else "  "
        typer.echo(f"{marker} {i}. {rec.name}  [{rec.id}]")
        typer.echo(f"      path: {rec.path}")

    if config.workspace_id:
        typer.echo(f"\n* = 当前激活 ({config.workspace_id})")

    typer.echo("\n选项：")
    typer.echo("  1-{} — 切换到对应工作区".format(len(recs)))
    typer.echo("  n    — 新建工作区")
    typer.echo("  o    — 用当前目录创建/打开")
    typer.echo("  q    — 跳过（继续主菜单）")

    choice = typer.prompt("选择", default="q").strip().lower()
    if choice == "q":
        return
    if choice == "n":
        _interactive_create_workspace(registry)
        return
    if choice == "o":
        rec = _create_or_open_for(Path.cwd(), registry)
        if rec is not None:
            _activate(rec.id, registry)
        return
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(recs):
            _activate(recs[idx].id, registry)
            return
    typer.echo("无效选择。", err=True)


def _create_or_open_for(path: Path, registry: WorkspaceRegistry):
    target = path.expanduser().resolve(strict=False)
    if not target.exists() or not target.is_dir():
        typer.echo(f"目录不存在: {target}", err=True)
        return None
    existing = registry.exists_for_path(target)
    if existing is not None:
        typer.echo(f"已存在工作区: {existing.name} ({existing.id})")
        return existing
    rec = registry.create(target, name=target.name or "workspace")
    typer.echo(f"已创建工作区: {rec.name} ({rec.id})")
    return rec


def _interactive_create_workspace(registry: WorkspaceRegistry) -> None:
    default = str(Path.cwd())
    raw = typer.prompt("请输入工作区目录路径", default=default).strip()
    rec = _create_or_open_for(Path(raw), registry)
    if rec is not None:
        _activate(rec.id, registry)


def _activate(workspace_id: str, registry: WorkspaceRegistry) -> None:
    config = _get_config_ctx()
    load_for_workspace(config, workspace_id)
    registry.set_last_active(workspace_id)
    reset_agent_cache()
    typer.echo(f"✅ 已激活: {config.workspace_name} ({config.workspace_id})\n")


def run_dispatcher():
    migrate_legacy()
    if not load_default_workspace():
        _workspace_selection_menu()
    _print_workspace_banner()

    typer.echo("🚀 ScriptorDB — 输入命令编号或名称，输入 'exit' 退出\n")
    show_help()
    typer.echo()

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            typer.echo("\nBye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "q"):
            typer.echo("Bye!")
            break

        if user_input.lower() == "help":
            show_help()
            continue

        parts = shlex.split(user_input)
        cmd_name = parts[0]
        args = parts[1:]

        if COMMAND_MAP.get(cmd_name) == "workspace":
            _dispatch_workspace(args)
            _print_workspace_banner()
            continue

        if COMMAND_MAP.get(cmd_name) == "undo":
            _dispatch_undo(args)
            continue

        command = COMMAND_MAP.get(cmd_name)
        if not command:
            typer.echo(f"未知命令: {cmd_name}，输入 help 查看列表", err=True)
            continue

        try:
            if command is ask:
                _handle_ask(args)
            elif command is models:
                _handle_models(args)
            elif command is interactive:
                _handle_interactive(args)
            else:
                command()
        except Exception as e:
            typer.echo(f"执行出错: {e}", err=True)


def _dispatch_workspace(args: list[str]) -> None:
    if not args:
        _workspace_selection_menu()
        return
    sub = args[0]
    if sub == "list":
        workspace_cli.workspace_list()
    elif sub == "create":
        rest = args[1:]
        if not rest:
            _interactive_create_workspace(WorkspaceRegistry())
            return
        path = rest[0]
        name = None
        if "--name" in rest:
            i = rest.index("--name")
            if i + 1 < len(rest):
                name = rest[i + 1]
        workspace_cli.workspace_create(path=path, name=name)
    elif sub == "switch":
        if len(args) < 2:
            typer.echo("用法: workspace switch <id-or-name>", err=True)
            return
        workspace_cli.workspace_switch(workspace_id=args[1])
    elif sub == "current":
        workspace_cli.workspace_current()
    elif sub == "rename":
        if len(args) < 3:
            typer.echo("用法: workspace rename <id-or-name> <new-name>", err=True)
            return
        workspace_cli.workspace_rename(workspace_id=args[1], new_name=args[2])
    elif sub == "remove":
        if len(args) < 2:
            typer.echo("用法: workspace remove <id-or-name> [--delete-files]", err=True)
            return
        delete_files = "--delete-files" in args
        workspace_cli.workspace_remove(workspace_id=args[1], delete_files=delete_files)
    elif sub == "migrate":
        workspace_cli.workspace_migrate()
    else:
        typer.echo(f"未知子命令: {sub}", err=True)


def _dispatch_undo(args: list[str]) -> None:
    from cli.commands import undo_list, undo_revert

    if not args:
        typer.echo("用法: undo list | undo revert <group_id>", err=True)
        return
    sub = args[0]
    if sub == "list":
        undo_list()
    elif sub == "revert":
        if len(args) < 2:
            typer.echo("用法: undo revert <group_id>", err=True)
            return
        try:
            gid = int(args[1])
        except ValueError:
            typer.echo("group_id 必须是整数", err=True)
            return
        undo_revert(gid)
    else:
        typer.echo(f"未知子命令: {sub}，可用: list, revert <id>", err=True)


def _handle_ask(args: list[str]) -> None:
    model = None
    provider = None
    workspace = None
    prompt = None

    i = 0
    while i < len(args):
        if args[i] in ("--model", "-m") and i + 1 < len(args):
            model = args[i + 1]
            i += 2
        elif args[i] in ("--provider", "-p") and i + 1 < len(args):
            provider = args[i + 1]
            i += 2
        elif args[i] == "--workspace" and i + 1 < len(args):
            workspace = args[i + 1]
            i += 2
        else:
            if prompt is None:
                prompt = args[i]
            i += 1

    if prompt is None:
        prompt = input("请输入查询: ").strip()

    if prompt:
        ask(prompt, model=model, provider=provider, workspace=workspace)
    else:
        typer.echo("查询内容不能为空", err=True)


def _handle_models(args: list[str]) -> None:
    provider = None
    workspace = None
    i = 0
    while i < len(args):
        if args[i] in ("--provider", "-p") and i + 1 < len(args):
            provider = args[i + 1]
            i += 2
        elif args[i] == "--workspace" and i + 1 < len(args):
            workspace = args[i + 1]
            i += 2
        else:
            i += 1
    models(provider=provider, workspace=workspace)


def _handle_interactive(args: list[str]) -> None:
    provider = None
    model = None
    workspace = None

    i = 0
    while i < len(args):
        if args[i] in ("--provider", "-p") and i + 1 < len(args):
            provider = args[i + 1]
            i += 2
        elif args[i] in ("--model", "-m") and i + 1 < len(args):
            model = args[i + 1]
            i += 2
        elif args[i] == "--workspace" and i + 1 < len(args):
            workspace = args[i + 1]
            i += 2
        else:
            i += 1

    interactive(provider=provider, model=model, workspace=workspace)
