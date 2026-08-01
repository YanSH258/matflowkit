"""MatFlowKit 命令行入口：typer app + 子命令注册。

不带参数运行 `mfk` 时进入交互式菜单（见 matflowkit/menu.py）。
"""

import typer

from matflowkit import __version__
from matflowkit.abacus.audit import audit
from matflowkit.abacus.check_relax import check_relax
from matflowkit.abacus.plot_convergence import plot_convergence
from matflowkit.abacus.to_deepmd import to_deepmd
from matflowkit.cp2k.audit import audit as cp2k_audit
from matflowkit.cp2k.collect import collect as cp2k_collect
from matflowkit.deepmd.merge import merge
from matflowkit.deepmd.report import report as deepmd_report
from matflowkit.deepmd.stat import stat
from matflowkit.dpdata.convert import convert
from matflowkit.dpdata.overlap import overlap
from matflowkit.dpdata.xyz_to_deepmd import xyz_to_deepmd
from matflowkit.dpa4.batch_relax import batch_relax
from matflowkit.dpa4.evaluate import evaluate as dpa4_evaluate
from matflowkit.dpa4.neb import neb as dpa4_neb
from matflowkit.dpa4.relax import relax as dpa4_relax
from matflowkit.gpumd.merge_loss import merge_loss
from matflowkit.gpumd.from_deepmd import from_deepmd
from matflowkit.gpumd.plot_nep_training import plot_nep_training
from matflowkit.gpumd.thermo import thermo
from matflowkit.structure.convert import convert as structure_convert
from matflowkit.vasp.to_deepmd import to_deepmd as vasp_to_deepmd

# 所有命令统一支持 -h / --help
_CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

app = typer.Typer(
    name="mfk",
    help="材料计算命令行工具。不带参数时打开菜单。",
    invoke_without_command=True,
    no_args_is_help=False,
    add_completion=False,
    context_settings=_CONTEXT_SETTINGS,
)

abacus_app = typer.Typer(help="ABACUS", no_args_is_help=True,
                         context_settings=_CONTEXT_SETTINGS)
deepmd_app = typer.Typer(help="DeePMD", no_args_is_help=True,
                         context_settings=_CONTEXT_SETTINGS)
gpumd_app = typer.Typer(help="GPUMD", no_args_is_help=True,
                        context_settings=_CONTEXT_SETTINGS)
dpdata_app = typer.Typer(help="数据转换与检查", no_args_is_help=True,
                         context_settings=_CONTEXT_SETTINGS)
dpa4_app = typer.Typer(help="DPA4", no_args_is_help=True,
                       context_settings=_CONTEXT_SETTINGS)
cp2k_app = typer.Typer(help="CP2K", no_args_is_help=True,
                       context_settings=_CONTEXT_SETTINGS)
vasp_app = typer.Typer(help="VASP", no_args_is_help=True,
                       context_settings=_CONTEXT_SETTINGS)
structure_app = typer.Typer(help="周期结构格式转换", no_args_is_help=True,
                            context_settings=_CONTEXT_SETTINGS)

abacus_app.command("check-relax")(check_relax)
abacus_app.command("audit")(audit)
abacus_app.command("plot-convergence")(plot_convergence)
abacus_app.command("to-deepmd")(to_deepmd)
deepmd_app.command("stat")(stat)
deepmd_app.command("merge")(merge)
deepmd_app.command("report")(deepmd_report)
gpumd_app.command("thermo")(thermo)
gpumd_app.command("from-deepmd")(from_deepmd)
gpumd_app.command("merge-loss")(merge_loss)
gpumd_app.command("plot-nep-training")(plot_nep_training)
dpdata_app.command("convert")(convert)
dpdata_app.command("overlap")(overlap)
dpdata_app.command("xyz-to-deepmd")(xyz_to_deepmd)
dpa4_app.command("relax")(dpa4_relax)
dpa4_app.command("batch-relax")(batch_relax)
dpa4_app.command("evaluate")(dpa4_evaluate)
dpa4_app.command("neb")(dpa4_neb)
cp2k_app.command("audit")(cp2k_audit)
cp2k_app.command("collect")(cp2k_collect)
vasp_app.command("to-deepmd")(vasp_to_deepmd)
structure_app.command("convert")(structure_convert)

app.add_typer(abacus_app, name="abacus")
app.add_typer(deepmd_app, name="deepmd")
app.add_typer(gpumd_app, name="gpumd")
app.add_typer(dpdata_app, name="dpdata")
app.add_typer(dpa4_app, name="dpa4")
app.add_typer(cp2k_app, name="cp2k")
app.add_typer(vasp_app, name="vasp")
app.add_typer(structure_app, name="structure")


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
        from matflowkit.menu import run_menu

        run_menu(app)


def main():
    app()


if __name__ == "__main__":
    main()
