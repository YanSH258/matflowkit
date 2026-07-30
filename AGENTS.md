# AGENTS.md — MatFlowKit 路由文档

## 这是什么

MatFlowKit 是一个个人科研工具箱（分子动力学 / 第一性原理计算方向），Python 包名
`mdkit`，命令行入口 `mfk`，基于 typer。覆盖 ABACUS / DeePMD / GPUMD 的前处理、
过程分析与后处理。设计模式：单一入口 + 子命令分发 + 双模式（命令行直跑 / 交互式菜单）。

## 安装

```bash
cd MatFlowKit
pip install -e .    # 装进当前 python 环境
mfk --help          # 验证
```

## 双模式用法

- 命令行模式：`mfk <软件> <命令> [参数]`，如 `mfk gpumd thermo --plot`。
- 交互模式：直接运行 `mfk` 进入菜单，逐级选择软件 → 命令 → 输入参数。
  菜单没有独立实现，最终复用同一个 typer app 执行，并会打印等价命令行。

## 场景 → 命令路由表

| 场景 | 命令 |
| --- | --- |
| 看 ABACUS relax 算完没有、收敛没有、最后能量和最大力 | `mfk abacus check-relax [DIR]` |
| 拿到一批 DeePMD 训练数据，先看规模、元素组成、能量/力范围 | `mfk deepmd stat [DIR]` |
| 需要程序化读取 DeePMD 数据集统计（接脚本/管道） | `mfk deepmd stat [DIR] --json` |
| GPUMD 跑完后看 thermo.out 各列统计（温度、能量、压力走势） | `mfk gpumd thermo [FILE]` |
| 想快速看一眼温度随步数的演化曲线 | `mfk gpumd thermo [FILE] --plot` |

## 命令的输入/输出约定

### `mfk abacus check-relax [DIR]`（默认当前目录）
- 输入：DIR 下的 `OUT.*/running_relax.log` 或 `running_relax.log`（ABACUS relax 日志）。
- 输出（stdout）：日志路径；是否发现收敛标记（列出匹配行）；最后一步离子步序号；
  总能（匹配 `final etot` / `!FINAL` 行，找不到会明说"未找到总能行"）；最大力。
- 日志不存在：stderr 报错，退出码 1。

### `mfk deepmd stat [DIR]`（默认当前目录）
- 输入：DeePMD raw/npy 数据集。DIR 下每个子目录是一个 system（含 `type.raw` +
  `set.*/{coord,energy,force,box}.npy`，可选 `type_map.raw`）；DIR 本身是单个 system 也兼容。
- 输出（stdout）：system 数量、每个 system 的 frame 数与原子数、各元素原子计数
  （有 type_map.raw 时显示元素符号）、能量范围、力分量绝对值范围；`--json` 输出机器可读 JSON。
- 找不到数据：stderr 报错，退出码 1。仅依赖 numpy，不依赖 dpdata。

### `mfk gpumd thermo [FILE]`（默认 `thermo.out`）
- 输入：空格分隔数值列的 thermo.out，列数不固定（典型 12 列）。
- 输出（stdout）：行数、列数、每列 mean/min/max/末值，标注第 1 列通常为温度。
- `--plot`：画第 1 列随步数曲线，保存当前目录 `thermo_col1.png`；
  未安装 matplotlib 时改为保存 `thermo_col1.csv` 并提示，不崩溃。
- 文件不存在：stderr 报错，退出码 1。

## 添加新命令的规范

1. 实现放在对应软件子包：`mdkit/<software>/<command_name>.py`，
   新软件则新建 `mdkit/<software>/` 子包。跨命令共享代码放 `mdkit/common/`。
2. 在 `mdkit/cli.py` 中 import 并用 `<software>_app.command("<cmd-name>")(func)` 注册；
   新软件需新建 typer 子组并 `app.add_typer(...)`。
3. 在 `mdkit/menu.py` 的 `MENU` 中追加对应条目（编号、一句话说明、参数提示列表），
   菜单通过 CliRunner 复用命令，禁止在菜单里另写实现。
4. 硬性要求：
   - 必须支持 `-h`（用 typer 声明参数即可获得）；
   - 路径输入默认当前目录（或当前目录下的约定文件名）；
   - 产出文件（图、csv 等）写到当前目录，命名固定、见名知意；
   - 报错走 stderr 且退出码非零；不许编造解析不到的数据（找不到就明说）。
5. 装依赖前先确认 `pyproject.toml` 已声明；画图类功能对 matplotlib 必须延迟导入。
