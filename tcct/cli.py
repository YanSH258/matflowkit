"""TCCT 命令行入口：typer app + 子命令注册。

不带参数运行 `tcct` 时进入交互式菜单（见 tcct/menu.py）。
"""

import typer

from tcct import __version__
from tcct.registry import GROUPS

# 所有命令统一支持 -h / --help
_CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

app = typer.Typer(
    name="tcct",
    help="材料计算命令行工具。不带参数时打开菜单。",
    invoke_without_command=True,
    no_args_is_help=False,
    add_completion=False,
    context_settings=_CONTEXT_SETTINGS,
)

for group in GROUPS:
    if group.cli_name is None:
        for command in group.commands:
            app.command(command.name)(command.callback)
        continue
    group_app = typer.Typer(
        help=group.cli_help,
        no_args_is_help=True,
        context_settings=_CONTEXT_SETTINGS,
    )
    for command in group.commands:
        group_app.command(command.name)(command.callback)
    app.add_typer(group_app, name=group.cli_name)


@app.callback()
def _callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-V", help="显示版本号并退出"),
):
    """不带参数运行时进入交互菜单。"""
    if version:
        typer.echo(f"tcct (TCCT) {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        from tcct.menu import run_menu

        run_menu(app)


def main():
    app()


if __name__ == "__main__":
    main()
