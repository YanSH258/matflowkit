"""交互式菜单（GPUMDkit 风格）。

菜单本身不实现任何命令逻辑：收集参数后，通过 typer.testing.CliRunner
调用同一个 typer app 执行，保证与命令行模式行为完全一致。
"""

import typer
from typer.testing import CliRunner

from mdkit import __version__

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
        ("check-relax", "检查 relax 计算是否收敛",
         [("dir", "计算目录", ".", False)]),
        ("audit", "批量审计 ABACUS 任务完成状态",
         [("root", "任务根目录", ".", False)]),
        ("plot-convergence", "绘制 relax/cell-relax 收敛曲线",
         [("dir", "计算目录", ".", False)]),
        ("to-deepmd", "将完成的 ABACUS scf/relax/md 任务转为 DeepMD NPY（自动识别 basis_type）",
         [("root", "任务根目录", ".", False),
          ("output", "输出目录", "deepmd_from_abacus", False)]),
    ]),
    "2": ("DeePMD", [
        ("stat", "统计 DeePMD 数据集（frame/原子数/能量与力范围）",
         [("dir", "数据目录", ".", False)]),
        ("merge", "按精确组成合并多个 DeepMD NPY 数据集",
         [("@args", "输入目录（空格分隔）", "data_a data_b", False),
          ("--output", "输出目录", "deepmd_merged", False)]),
    ]),
    "3": ("GPUMD", [
        ("thermo", "分析 thermo.out 各列统计，可选画图",
         [("file", "thermo 文件", "thermo.out", False),
          ("plot", "是否画第 1 列曲线 (y/n)", "n", True)]),
        ("merge-loss", "合并首次训练与续训的 loss.out",
         [("first", "首次训练 loss 文件", "loss.out", False),
          ("restart", "续训 loss 文件", "restart/loss.out", False),
          ("--output", "输出文件", "loss_merged.out", False)]),
        ("plot-nep-training", "绘制 NEP loss 与能量/力/应力预测误差",
         [("directory", "训练或预测目录", ".", False),
          ("--output", "输出图片", "nep_training.png", False),
          ("--metrics", "误差指标 JSON", "nep_training_metrics.json", False)]),
    ]),
    "4": ("dpdata", [
        ("convert", "转换 dpdata 支持的结构/标注数据格式",
         [("input", "输入文件或目录", ".", False),
          ("output", "输出文件或目录", "converted_data", False),
          ("--from", "输入格式", "deepmd/npy", False),
          ("--to", "输出格式", "extxyz", False)]),
        ("xyz-to-deepmd", "将带标注的 GPUMD/extxyz 转为 DeepMD raw + NPY",
         [("input", "输入 xyz 文件", "train.xyz", False),
          ("output", "输出目录", "deepmd", False)]),
    ]),
    "5": ("DPA4", [
        ("relax", "使用 DPA4 优化结构",
         [("input", "输入结构", "structure.xyz", False),
          ("--output", "输出结构", "structure_dpa4_relaxed.extxyz", False),
          ("--model", "DPA4 model.pt", "~/dpa4/Neo-MPtrj/model.pt", False)]),
        ("batch-relax", "按 CSV manifest 批量运行可恢复的 DPA4 优化",
         [("manifest", "任务 manifest", "structures.csv", False),
          ("--output-dir", "输出目录", "dpa4_batch_relax", False),
          ("--model", "DPA4 model.pt", "~/dpa4/Neo-MPtrj/model.pt", False)]),
        ("evaluate", "使用 DPA4 计算多帧结构的能量和原子力",
         [("input", "单帧或多帧结构", "structures.extxyz", False),
          ("--output", "带标注的 extxyz", "structures_dpa4_evaluated.extxyz", False),
          ("--model", "DPA4 model.pt", "~/dpa4/Neo-MPtrj/model.pt", False)]),
        ("neb", "使用 DPA4 执行 NEB/CI-NEB",
         [("initial", "已优化初态", "initial.extxyz", False),
          ("final", "已优化末态", "final.extxyz", False),
          ("--output-dir", "输出目录", "dpa4_neb", False),
          ("--model", "DPA4 model.pt", "~/dpa4/Neo-MPtrj/model.pt", False)]),
    ]),
}
_GROUP_NAME = {
    "1": "abacus",
    "2": "deepmd",
    "3": "gpumd",
    "4": "dpdata",
    "5": "dpa4",
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
    print(f"  MatFlowKit v{__version__}  -  个人科研工具箱")
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
