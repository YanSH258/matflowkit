"""交互式菜单（GPUMDkit 风格）。

菜单本身不实现任何命令逻辑：收集参数后，通过 typer.testing.CliRunner
调用同一个 typer app 执行，保证与命令行模式行为完全一致。
"""

import typer
from typer.testing import CliRunner

from tcct import __version__
from tcct.registry import GROUPS

try:
    import readline  # noqa: F401  # Enable editing/history for input().
except ImportError:  # pragma: no cover - Windows may not provide readline.
    readline = None

BANNER = r"""
  _____   ____   ____  _____
 |_   _| / ___| / ___||_   _|
   | |  | |    | |      | |
   | |  | |___ | |___   | |
   |_|   \____| \____|  |_|
"""

# 菜单与 CLI 使用同一份注册表，避免新增命令时只更新其中一处。
MENU = {
    group.menu_key: (
        group.display_name,
        [
            (
                command.name,
                command.menu_description,
                list(command.menu_parameters),
            )
            for command in group.commands
        ],
    )
    for group in GROUPS
}
_GROUP_NAME = {group.menu_key: group.cli_name or "" for group in GROUPS}
_GROUP_HELP = {group.menu_key: group.cli_help for group in GROUPS}

DPDATA_INPUT_FORMATS = (
    "deepmd/npy",
    "deepmd/raw",
    "extxyz",
    "gpumd/xyz",
    "vasp/outcar",
    "abacus/lcao/scf",
    "abacus/pw/scf",
    "cp2kdata/md",
)
DPDATA_OUTPUT_FORMATS = (
    "deepmd/npy",
    "deepmd/raw",
    "extxyz",
    "gpumd/xyz",
)


def _prompt(text: str, default: str) -> str:
    """提示输入，回车取默认值；输入 q/0 返回 None 表示取消。"""
    try:
        value = input(f"  {text} [{default}]: ").strip()
    except EOFError:
        return None
    if value.lower() in ("q", "0"):
        return None
    return value if value else default


def _prompt_dpdata_format(text: str, default: str, formats: tuple[str, ...]):
    """Select a common dpdata format by number, or accept an exact format name."""
    print(f"  {text}（输入编号或 dpdata 格式名）:")
    for index, name in enumerate(formats, 1):
        print(f"    {index}) {name}")
    try:
        value = input(f"  选择 [{default}]: ").strip()
    except EOFError:
        return None
    if value.lower() in ("q", "0"):
        return None
    if not value:
        return default
    if value.isdigit():
        index = int(value)
        if 1 <= index <= len(formats):
            return formats[index - 1]
        print("  无效编号，请重新输入。")
        return _prompt_dpdata_format(text, default, formats)
    return value


def _run_command(app, group: str, cmd: str, params: list) -> None:
    """逐个收集参数，打印等价命令行，再复用 typer app 执行。"""
    args = [group, cmd] if group else [cmd]
    display = ["tcct", group, cmd] if group else ["tcct", cmd]
    for name, text, default, is_flag in params:
        if group == "dpdata" and cmd == "convert" and name in {"--from", "--to"}:
            formats = DPDATA_INPUT_FORMATS if name == "--from" else DPDATA_OUTPUT_FORMATS
            value = _prompt_dpdata_format(text, default, formats)
        else:
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
    if result.stderr and result.stderr not in result.output:
        print(result.stderr, end="")
    print(f"{'-' * 50}\n(退出码: {result.exit_code})")


def run_menu(app) -> None:
    """主循环：选软件 -> 选命令 -> 输入参数 -> 执行。"""
    print(BANNER)
    print(f"  TCCT v{__version__}")
    print("  (输入编号选择；q 或 0 返回/退出)\n")

    while True:
        print("请选择软件:")
        for key, (name, _) in MENU.items():
            print(f"  {key}) {name}    {_GROUP_HELP[key]}")
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
            print(f"  {i}) {cmd:24s} {desc}")
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
