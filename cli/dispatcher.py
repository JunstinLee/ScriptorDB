from __future__ import annotations

import shlex

import typer

from cli.commands import ask, forget, interactive, models, serve, setup

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
}


def show_help():
    typer.echo("命令列表:")
    typer.echo("  1. setup       — 配置 LLM provider 和 API key")
    typer.echo("  2. forget      — 删除 API key")
    typer.echo("  3. models      — 列出可用模型")
    typer.echo("  4. ask         — 执行单次查询")
    typer.echo("  5. interactive — 进入交互式查询")
    typer.echo("  6. serve       — 启动 MCP server")
    typer.echo("  help           — 显示帮助")
    typer.echo("  exit / quit    — 退出")


def run_dispatcher():
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


def _handle_ask(args: list[str]) -> None:
    model = None
    provider = None
    prompt = None

    if args:
        i = 0
        while i < len(args):
            if args[i] in ("--model", "-m") and i + 1 < len(args):
                model = args[i + 1]
                i += 2
            elif args[i] in ("--provider", "-p") and i + 1 < len(args):
                provider = args[i + 1]
                i += 2
            else:
                if prompt is None:
                    prompt = args[i]
                i += 1

    if prompt is None:
        prompt = input("请输入查询: ").strip()

    if prompt:
        ask(prompt, model=model, provider=provider)
    else:
        typer.echo("查询内容不能为空", err=True)


def _handle_models(args: list[str]) -> None:
    provider = None
    if args:
        provider = args[0]
    models(provider=provider)


def _handle_interactive(args: list[str]) -> None:
    provider = None
    model = None

    if args:
        i = 0
        while i < len(args):
            if args[i] in ("--provider", "-p") and i + 1 < len(args):
                provider = args[i + 1]
                i += 2
            elif args[i] in ("--model", "-m") and i + 1 < len(args):
                model = args[i + 1]
                i += 2
            else:
                i += 1

    interactive(provider=provider, model=model)
