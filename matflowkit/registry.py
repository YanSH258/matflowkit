"""Single command registry shared by the Typer CLI and interactive menu."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple

from matflowkit.abacus.audit import audit
from matflowkit.abacus.check_relax import check_relax
from matflowkit.abacus.plot_convergence import plot_convergence
from matflowkit.abacus.to_deepmd import to_deepmd
from matflowkit.cp2k.audit import audit as cp2k_audit
from matflowkit.cp2k.collect import collect as cp2k_collect
from matflowkit.deepmd.merge import merge
from matflowkit.deepmd.report import report as deepmd_report
from matflowkit.deepmd.stat import stat
from matflowkit.doctor import doctor
from matflowkit.dpdata.convert import convert
from matflowkit.dpdata.overlap import overlap
from matflowkit.dpdata.xyz_to_deepmd import xyz_to_deepmd
from matflowkit.dpa4.batch_relax import batch_relax
from matflowkit.dpa4.evaluate import evaluate as dpa4_evaluate
from matflowkit.dpa4.neb import neb as dpa4_neb
from matflowkit.dpa4.relax import relax as dpa4_relax
from matflowkit.gpumd.from_deepmd import from_deepmd
from matflowkit.gpumd.merge_loss import merge_loss
from matflowkit.gpumd.plot_nep_training import plot_nep_training
from matflowkit.gpumd.thermo import thermo
from matflowkit.structure.convert import convert as structure_convert
from matflowkit.vasp.to_deepmd import to_deepmd as vasp_to_deepmd


MenuParameter = Tuple[str, str, str, bool]


@dataclass(frozen=True)
class CommandSpec:
    name: str
    callback: Callable[..., Any]
    menu_description: str
    menu_parameters: Tuple[MenuParameter, ...] = ()


@dataclass(frozen=True)
class GroupSpec:
    menu_key: str
    display_name: str
    cli_name: Optional[str]
    cli_help: str
    commands: Tuple[CommandSpec, ...]


GROUPS = (
    GroupSpec("1", "ABACUS", "abacus", "ABACUS", (
        CommandSpec("check-relax", check_relax, "检查 relax", (("dir", "计算目录", ".", False),)),
        CommandSpec("audit", audit, "批量检查任务", (("root", "任务根目录", ".", False),)),
        CommandSpec("plot-convergence", plot_convergence, "画收敛曲线", (("dir", "计算目录", ".", False),)),
        CommandSpec("to-deepmd", to_deepmd, "ABACUS 转 DeepMD", (
            ("root", "任务根目录", ".", False),
            ("output", "输出目录", "deepmd_from_abacus", False),
        )),
    )),
    GroupSpec("2", "DeePMD", "deepmd", "DeePMD", (
        CommandSpec("stat", stat, "数据集统计", (("dir", "数据目录", ".", False),)),
        CommandSpec("merge", merge, "合并 NPY 数据集", (
            ("@args", "输入目录（空格分隔）", "data_a data_b", False),
            ("--output", "输出目录", "deepmd_merged", False),
        )),
        CommandSpec("report", deepmd_report, "生成数据集审计报告", (
            ("dataset-path", "数据集目录", ".", False),
            ("--output", "报告目录", "deepmd_report", False),
        )),
    )),
    GroupSpec("3", "GPUMD", "gpumd", "GPUMD", (
        CommandSpec("from-deepmd", from_deepmd, "多 system NPY 转单个 XYZ", (
            ("dataset", "DeepMD NPY 数据集根目录", ".", False),
            ("output", "GPUMD Extended XYZ", "train.xyz", False),
        )),
        CommandSpec("thermo", thermo, "统计并绘制 thermo.out", (
            ("file", "thermo 文件", "thermo.out", False),
            ("plot", "是否生成热力学图 (y/n)", "n", True),
        )),
        CommandSpec("merge-loss", merge_loss, "合并首次训练与续训的 loss.out", (
            ("first", "首次训练 loss 文件", "loss.out", False),
            ("restart", "续训 loss 文件", "restart/loss.out", False),
            ("--output", "输出文件", "loss_merged.out", False),
        )),
        CommandSpec("plot-nep-training", plot_nep_training, "画 NEP 训练结果", (
            ("directory", "训练或预测目录", ".", False),
            ("--output", "输出图片", "nep_training.png", False),
            ("--metrics", "误差指标 JSON", "nep_training_metrics.json", False),
        )),
    )),
    GroupSpec("4", "dpdata", "dpdata", "数据转换与检查", (
        CommandSpec("convert", convert, "转换数据格式", (
            ("input", "输入文件或目录", ".", False),
            ("output", "输出文件或目录", "converted_data", False),
            ("--from", "输入格式", "deepmd/npy", False),
            ("--to", "输出格式", "extxyz", False),
        )),
        CommandSpec("xyz-to-deepmd", xyz_to_deepmd, "XYZ 转 DeepMD", (
            ("input", "输入 xyz 文件", "train.xyz", False),
            ("output", "输出目录", "deepmd", False),
        )),
        CommandSpec("overlap", overlap, "查重复帧", (
            ("reference", "参考结构数据集", "train.extxyz", False),
            ("candidate", "待检查结构数据集", "test.extxyz", False),
            ("--output", "JSON 汇总", "frame_overlap.json", False),
        )),
    )),
    GroupSpec("5", "DPA4", "dpa4", "DPA4", (
        CommandSpec("relax", dpa4_relax, "使用 DPA4 优化结构", (
            ("input", "输入结构", "structure.xyz", False),
            ("--output", "输出结构", "structure_dpa4_relaxed.extxyz", False),
            ("--model", "DPA4 model.pt", "~/dpa4/Neo-MPtrj/model.pt", False),
        )),
        CommandSpec("batch-relax", batch_relax, "批量优化结构", (
            ("manifest", "任务 manifest", "structures.csv", False),
            ("--output-dir", "输出目录", "dpa4_batch_relax", False),
            ("--model", "DPA4 model.pt", "~/dpa4/Neo-MPtrj/model.pt", False),
        )),
        CommandSpec("evaluate", dpa4_evaluate, "计算能量和力", (
            ("input", "单帧或多帧结构", "structures.extxyz", False),
            ("--output", "带标注的 extxyz", "structures_dpa4_evaluated.extxyz", False),
            ("--model", "DPA4 model.pt", "~/dpa4/Neo-MPtrj/model.pt", False),
        )),
        CommandSpec("neb", dpa4_neb, "计算 NEB/CI-NEB", (
            ("initial", "已优化初态", "initial.extxyz", False),
            ("final", "已优化末态", "final.extxyz", False),
            ("--output-dir", "输出目录", "dpa4_neb", False),
            ("--model", "DPA4 model.pt", "~/dpa4/Neo-MPtrj/model.pt", False),
        )),
    )),
    GroupSpec("6", "CP2K", "cp2k", "CP2K", (
        CommandSpec("audit", cp2k_audit, "检查 CP2K 输出", (
            ("root", "任务根目录或输出文件", ".", False),
            ("--output", "审计 CSV", "cp2k_audit.csv", False),
        )),
        CommandSpec("collect", cp2k_collect, "CP2K 转 DeepMD", (
            ("root", "CP2K 单点任务根目录", ".", False),
            ("output", "新的数据集目录", "cp2k_dataset", False),
        )),
    )),
    GroupSpec("7", "VASP", "vasp", "VASP", (
        CommandSpec("to-deepmd", vasp_to_deepmd, "OUTCAR 转 DeepMD", (
            ("root", "任务根目录或 OUTCAR", ".", False),
            ("output", "输出目录", "vasp_dataset", False),
        )),
    )),
    GroupSpec("8", "Structure", "structure", "周期结构格式转换", (
        CommandSpec("convert", structure_convert, "周期结构格式转换", (
            ("input", "输入 CIF / POSCAR / Extended XYZ", "structure.cif", False),
            ("--to", "目标格式 (cif/xyz/poscar/stru)", "xyz", False),
            ("--basis", "STRU 基组 (pw/lcao)", "pw", False),
        )),
    )),
    GroupSpec("9", "System", None, "环境检查", (
        CommandSpec("doctor", doctor, "检查安装和计算资源"),
    )),
)
