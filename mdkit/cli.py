"""MatFlowKit 命令行入口：typer app + 子命令注册。

不带参数运行 `mfk` 时进入交互式菜单（见 mdkit/menu.py）。
"""

import typer

from mdkit import __version__
from mdkit.abacus.audit import audit
from mdkit.abacus.check_relax import check_relax
from mdkit.abacus.plot_convergence import plot_convergence
from mdkit.abacus.to_deepmd import to_deepmd
from mdkit.deepmd.merge import merge
from mdkit.deepmd.stat import stat
from mdkit.dpdata.convert import convert
from mdkit.dpdata.xyz_to_deepmd import xyz_to_deepmd
from mdkit.gpumd.merge_loss import merge_loss
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
dpdata_app = typer.Typer(help="dpdata 格式转换", no_args_is_help=True,
                         context_settings=_CONTEXT_SETTINGS)

abacus_app.command("check-relax")(check_relax)
abacus_app.command("audit")(audit)
abacus_app.command("plot-convergence")(plot_convergence)
abacus_app.command("to-deepmd")(to_deepmd)
deepmd_app.command("stat")(stat)
deepmd_app.command("merge")(merge)
gpumd_app.command("thermo")(thermo)
gpumd_app.command("merge-loss")(merge_loss)
dpdata_app.command("convert")(convert)
dpdata_app.command("xyz-to-deepmd")(xyz_to_deepmd)

app.add_typer(abacus_app, name="abacus")
app.add_typer(deepmd_app, name="deepmd")
app.add_typer(gpumd_app, name="gpumd")
app.add_typer(dpdata_app, name="dpdata")


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
