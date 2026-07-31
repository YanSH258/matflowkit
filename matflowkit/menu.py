"""交互式菜单（GPUMDkit 风格）。

菜单本身不实现任何命令逻辑：收集参数后，通过 typer.testing.CliRunner
调用同一个 typer app 执行，保证与命令行模式行为完全一致。
"""

import typer
from typer.testing import CliRunner

from matflowkit import __version__

BANNER = r"""
  __  __       _   _____ _              _  ___ _
 |  \/  | __ _| |_|  ___| | _____      _| |/ (_) |_
 | |\/| |/ _` | __| |_  | |/ _ \ \ /\ / /| ' /| | __|
 | |  | | (_| | |_|  _| | | (_) \ V  V / | . \| | |_
 |_|  |_|\__,_|_| |_|   |_|\___/ \_/\_/  |_|\_\_|\__|
"""

# 菜单结构：编号 -> (软件名, [(子命令, 一句话说明, [(参数名, 提示, 默认值, 是否为flag)])])
MENU = {
    "1": ("ABACUS", [
        ("check-relax", "检查 relax",
         [("dir", "计算目录", ".", False)]),
        ("audit", "批量检查任务",
         [("root", "任务根目录", ".", False)]),
        ("plot-convergence", "画收敛曲线",
         [("dir", "计算目录", ".", False)]),
        ("to-deepmd", "ABACUS 转 DeepMD",
         [("root", "任务根目录", ".", False),
          ("output", "输出目录", "deepmd_from_abacus", False)]),
    ]),
    "2": ("DeePMD", [
        ("stat", "数据集统计",
         [("dir", "数据目录", ".", False)]),
        ("merge", "合并 NPY 数据集",
         [("@args", "输入目录（空格分隔）", "data_a data_b", False),
          ("--output", "输出目录", "deepmd_merged", False)]),
        ("report", "生成数据集审计报告",
         [("dataset-path", "数据集目录", ".", False),
          ("--output", "报告目录", "deepmd_report", False)]),
    ]),
    "3": ("GPUMD", [
        ("thermo", "统计并绘制 thermo.out",
         [("file", "thermo 文件", "thermo.out", False),
          ("plot", "是否生成热力学图 (y/n)", "n", True)]),
        ("merge-loss", "合并首次训练与续训的 loss.out",
         [("first", "首次训练 loss 文件", "loss.out", False),
          ("restart", "续训 loss 文件", "restart/loss.out", False),
          ("--output", "输出文件", "loss_merged.out", False)]),
        ("plot-nep-training", "画 NEP 训练结果",
         [("directory", "训练或预测目录", ".", False),
          ("--output", "输出图片", "nep_training.png", False),
          ("--metrics", "误差指标 JSON", "nep_training_metrics.json", False)]),
    ]),
    "4": ("dpdata", [
        ("convert", "转换数据格式",
         [("input", "输入文件或目录", ".", False),
          ("output", "输出文件或目录", "converted_data", False),
          ("--from", "输入格式", "deepmd/npy", False),
          ("--to", "输出格式", "extxyz", False)]),
        ("xyz-to-deepmd", "XYZ 转 DeepMD",
         [("input", "输入 xyz 文件", "train.xyz", False),
          ("output", "输出目录", "deepmd", False)]),
        ("overlap", "查重复帧",
         [("reference", "参考结构数据集", "train.extxyz", False),
          ("candidate", "待检查结构数据集", "test.extxyz", False),
          ("--output", "JSON 汇总", "frame_overlap.json", False)]),
    ]),
    "5": ("DPA4", [
        ("relax", "使用 DPA4 优化结构",
         [("input", "输入结构", "structure.xyz", False),
          ("--output", "输出结构", "structure_dpa4_relaxed.extxyz", False),
          ("--model", "DPA4 model.pt", "~/dpa4/Neo-MPtrj/model.pt", False)]),
        ("batch-relax", "批量优化结构",
         [("manifest", "任务 manifest", "structures.csv", False),
          ("--output-dir", "输出目录", "dpa4_batch_relax", False),
          ("--model", "DPA4 model.pt", "~/dpa4/Neo-MPtrj/model.pt", False)]),
        ("evaluate", "计算能量和力",
         [("input", "单帧或多帧结构", "structures.extxyz", False),
          ("--output", "带标注的 extxyz", "structures_dpa4_evaluated.extxyz", False),
          ("--model", "DPA4 model.pt", "~/dpa4/Neo-MPtrj/model.pt", False)]),
        ("neb", "计算 NEB/CI-NEB",
         [("initial", "已优化初态", "initial.extxyz", False),
          ("final", "已优化末态", "final.extxyz", False),
          ("--output-dir", "输出目录", "dpa4_neb", False),
          ("--model", "DPA4 model.pt", "~/dpa4/Neo-MPtrj/model.pt", False)]),
    ]),
    "6": ("CP2K", [
        ("audit", "检查 CP2K 输出",
         [("root", "任务根目录或输出文件", ".", False),
          ("--output", "审计 CSV", "cp2k_audit.csv", False)]),
        ("collect", "CP2K 转 DeepMD",
         [("root", "CP2K 单点任务根目录", ".", False),
          ("output", "新的数据集目录", "cp2k_dataset", False)]),
    ]),
    "7": ("VASP", [
        ("to-deepmd", "OUTCAR 转 DeepMD",
         [("root", "任务根目录或 OUTCAR", ".", False),
          ("output", "输出目录", "vasp_dataset", False)]),
    ]),
}
_GROUP_NAME = {
    "1": "abacus",
    "2": "deepmd",
    "3": "gpumd",
    "4": "dpdata",
    "5": "dpa4",
    "6": "cp2k",
    "7": "vasp",
}


def _prompt(text: str, default: str) -> str:
    """提示输入，回车取默认值；输入 q/0 返回 None 表示取消。"""
    try:
        value = input(f"  {text} [{default}]: ").strip()
    except EOFError:
        return None
    if value.lower() in ("q", "0"):
        return None
    return value if value else default


def _run_command(app, group: str, cmd: str, params: list) -> None:
    """逐个收集参数，打印等价命令行，再复用 typer app 执行。"""
    args = [group, cmd]
    display = ["mfk", group, cmd]
    for name, text, default, is_flag in params:
        value = _prompt(text, default)
        if is_flag:
            # y/n 类开关：输入 q/0 视为 "否" 并继续执行，而非取消命令
            if value is not None and value.lower() in ("y", "yes"):
                args.append(f"--{name}")
                display.append(f"--{name}")
        else:
            if value is None:
                print("  已取消，返回上级菜单。")
                return
            if name == "@args":
                import shlex
                values = shlex.split(value)
                args.extend(values)
                display.extend(values)
            elif name.startswith("--"):
                args.extend([name, value])
                display.extend([name, value])
            else:
                args.append(value)
                display.append(value)

    print(f"\n等价命令: {' '.join(display)}\n{'-' * 50}")
    try:
        runner = CliRunner(mix_stderr=False)  # click < 8.2
    except TypeError:
        runner = CliRunner()  # click >= 8.2 默认分离 stderr
    result = runner.invoke(app, args)
    if result.output:
        print(result.output, end="")
    if result.stderr:
        print(result.stderr, end="")
    print(f"{'-' * 50}\n(退出码: {result.exit_code})")


def run_menu(app) -> None:
    """主循环：选软件 -> 选命令 -> 输入参数 -> 执行。"""
    print(BANNER)
    print(f"  MatFlowKit v{__version__}")
    print("  (输入编号选择；q 或 0 返回/退出)\n")

    while True:
        print("请选择软件:")
        for key, (name, _) in MENU.items():
            print(f"  {key}) {name}")
        print("  0) Exit")
        try:
            choice = input("> ").strip().lower()
        except EOFError:
            print("\n再见！")
            return
        if choice in ("0", "q", ""):
            print("再见！")
            return
        if choice not in MENU:
            print("无效选择，请重新输入。\n")
            continue

        name, commands = MENU[choice]
        print(f"\n[{name}] 可用命令:")
        for i, (cmd, desc, _) in enumerate(commands, 1):
            print(f"  {i}) {cmd:14s} {desc}")
        print("  0) 返回")
        try:
            cidx = input("> ").strip().lower()
        except EOFError:
            print("\n再见！")
            return
        if cidx in ("0", "q", ""):
            print()
            continue
        if not cidx.isdigit() or not (1 <= int(cidx) <= len(commands)):
            print("无效选择。\n")
            continue

        cmd, _, params = commands[int(cidx) - 1]
        print(f"\n[{name} -> {cmd}] 请依次输入参数（回车使用默认值，q 取消）:")
        _run_command(app, _GROUP_NAME[choice], cmd, params)
        print()
