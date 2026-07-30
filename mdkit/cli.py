"""MatFlowKit 命令行入口：typer app + 子命令注册。

不带参数运行 `mfk` 时进入交互式菜单（见 mdkit/menu.py）。
"""

import typer

from mdkit import __version__
from mdkit.abacus.check_relax import check_relax
from mdkit.deepmd.stat import stat
from mdkit.gpumd.thermo import thermo

# 所有命令统一支持 -h / --help
_CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

app = typer.Typer(
    name="mfk",
    help="MatFlowKit: 个人科研工具箱（ABACUS / DeePMD / GPUMD）。不带参数运行进入交互菜单。",
    invoke_without_command=True,
    no_args_is_help=False,
    add_completion=False,
    context_settings=_CONTEXT_SETTINGS,
)

abacus_app = typer.Typer(help="ABACUS 相关命令", no_args_is_help=True,
                         context_settings=_CONTEXT_SETTINGS)
deepmd_app = typer.Typer(help="DeePMD 相关命令", no_args_is_help=True,
                         context_settings=_CONTEXT_SETTINGS)
gpumd_app = typer.Typer(help="GPUMD 相关命令", no_args_is_help=True,
                        context_settings=_CONTEXT_SETTINGS)

abacus_app.command("check-relax")(check_relax)
deepmd_app.command("stat")(stat)
gpumd_app.command("thermo")(thermo)

app.add_typer(abacus_app, name="abacus")
app.add_typer(deepmd_app, name="deepmd")
app.add_typer(gpumd_app, name="gpumd")


@app.callback()
def _callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-V", help="显示版本号并退出"),
):
    """不带参数运行时进入交互菜单。"""
    if version:
        typer.echo(f"mfk (MatFlowKit) {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        from mdkit.menu import run_menu

        run_menu(app)


def main():
    app()


if __name__ == "__main__":
    main()
