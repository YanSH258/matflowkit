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
    ]),
    "2": ("DeePMD", [
        ("stat", "统计 DeePMD 数据集（frame/原子数/能量与力范围）",
         [("dir", "数据目录", ".", False)]),
    ]),
    "3": ("GPUMD", [
        ("thermo", "分析 thermo.out 各列统计，可选画图",
         [("file", "thermo 文件", "thermo.out", False),
          ("plot", "是否画第 1 列曲线 (y/n)", "n", True)]),
    ]),
}
_GROUP_NAME = {"1": "abacus", "2": "deepmd", "3": "gpumd"}


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
