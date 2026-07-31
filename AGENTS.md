# AGENTS.md — MatFlowKit 路由文档

## 这是什么

MatFlowKit 是一个科研工具箱（分子动力学 / 第一性原理计算方向），Python 包名
`matflowkit`，命令行入口 `mfk`，基于 typer。覆盖 ABACUS / CP2K / dpdata / DeePMD /
GPUMD / DPA4 的前处理、过程分析与后处理。设计模式：单一入口 + 子命令分发 +
双模式（命令行直跑 / 交互式菜单）。

## 安装与验证

```bash
uv sync --extra dev --extra plot --extra dpdata --extra structure
uv run mfk --help          # 验证 CLI
uv run pytest tests/       # 验证测试
```

不用 uv 时也可在任何 Python 3.9+ 环境 `pip install -e .`。
DPA4 命令需要独立的 deepmd-kit + dftd3 环境（暂不随主环境安装，
见 `matflowkit/dpa4/README.md`）。

## 双模式用法

- 命令行模式：`mfk <软件> <命令> [参数]`，如 `mfk gpumd thermo --plot`。
- 交互模式：直接运行 `mfk` 进入菜单，逐级选择软件 → 命令 → 输入参数。
  菜单没有独立实现，最终复用同一个 typer app 执行，并会打印等价命令行。

## 场景 → 命令路由表

| 场景 | 命令 |
| --- | --- |
| 看 ABACUS relax 算完没有、收敛没有、最后能量和最大力 | `mfk abacus check-relax [DIR]` |
| 批量检查 ABACUS SCF/relax/cell-relax 任务 | `mfk abacus audit [ROOT]` |
| 绘制 ABACUS 结构优化收敛曲线 | `mfk abacus plot-convergence [DIR]` |
| 将完成的 ABACUS 任务转换为 DeepMD NPY | `mfk abacus to-deepmd ROOT OUTPUT` |
| 拿到一批 DeePMD 训练数据，先看规模、元素组成、能量/力范围 | `mfk deepmd stat [DIR]` |
| 按精确组成合并多个 DeepMD NPY 数据集 | `mfk deepmd merge INPUT... --output DIR` |
| 需要程序化读取 DeePMD 数据集统计（接脚本/管道） | `mfk deepmd stat [DIR] --json` |
| 在 ABACUS/CP2K/DeepMD/extxyz/GPUMD 格式间转换 | `mfk dpdata convert INPUT OUTPUT --from FMT --to FMT` |
| 将带标注的 GPUMD/extxyz 转为 DeepMD raw + NPY | `mfk dpdata xyz-to-deepmd [INPUT] [OUTPUT]` |
| 检查训练集、验证集或测试集之间的重复结构 | `mfk dpdata overlap REFERENCE CANDIDATE` |
| GPUMD 跑完后看 thermo.out 各列统计（温度、能量、压力走势） | `mfk gpumd thermo [FILE]` |
| 想快速看一眼温度随步数的演化曲线 | `mfk gpumd thermo [FILE] --plot` |
| 合并 NEP 首次训练与续训的 loss.out | `mfk gpumd merge-loss [FIRST] [RESTART]` |
| 绘制 NEP loss 与能量/力/应力预测误差 | `mfk gpumd plot-nep-training [DIR]` |
| 使用 DPA4 优化结构 | `mfk dpa4 relax INPUT` |
| 按 manifest 批量运行并恢复 DPA4 优化 | `mfk dpa4 batch-relax [CSV]` |
| 使用 DPA4 为单帧或多帧结构计算能量和力 | `mfk dpa4 evaluate INPUT` |
| 使用 DPA4 计算 NEB/CI-NEB 路径 | `mfk dpa4 neb INITIAL FINAL` |
| 批量审计 CP2K 单点输出的完成与标注证据 | `mfk cp2k audit [ROOT]` |
| 收集 CP2K 单点能量和力为 DeepMD NPY/extxyz | `mfk cp2k collect [ROOT] [OUTPUT]` |

## 命令的输入/输出约定

每个命令的输入约定、参数、输出与边界条件，见对应软件子包的 README
（`matflowkit/<software>/README.md`），由各软件独立维护。本文件不再重复细节，
只保留路由表。不确定时以 `mfk <软件> <命令> -h` 为准。

## 补充脚本的原则（加命令前先读）

1. **用出来的才搬**：只收录真实用过且重复用过的操作（经验法则：第三次手动做同一件事时
   才变成命令）。不为凑模块写没人用的命令——空命令会误导 AI 的路由判断。
2. **搬运 ≠ 重写**：旧脚本先包一层 typer 外壳，内部逻辑原样保留，验证跑通后再考虑重构。
   一次只改一件事。
3. **约定大于配置**：输入默认当前目录与标准文件名；输出文件名固定、见名知意；
   结构数据一律以 extxyz 为中间格式（转换用 dpdata/ASE，不自己造格式）。
4. **一个命令干一件事**：`deepmd merge` 只做合并，不顺手筛选。串联是 workflow 层的事，
   可组合性优先于"一条命令全自动"。
5. **依赖克制**：硬依赖只有 typer + numpy；ASE/dpdata/matplotlib 等在对应命令内延迟导入，
   未安装时清晰提示而非 ImportError。加新依赖前先确认无法用现有依赖解决，并声明进
   `pyproject.toml`。
6. **文档与命令同生同死**：每加一个命令，同一次提交必须包含：写清"输入约定/参数/输出/
   示例"的 docstring、菜单注册、对应子包 README（`matflowkit/<software>/README.md`）、
   本文件路由表更新。做不到这条，AI 可用性就断档。
7. **可验证**：新命令配最小测试数据（放 /tmp，不进仓库）实际跑一遍验收；
   有真实案例后按 `examples/` 格式（命令 + 输入 + 输出 + 解释）收录。
8. **提交纪律**：一个命令一个 commit，message 写清命令名与用途；积累 5~10 个命令打一次 tag。

## 添加新命令的规范

见 [CONTRIBUTING.md](CONTRIBUTING.md)（实现位置、cli.py 注册、菜单注册、
子包 README、硬性要求）。AI agent 加命令时同样必须遵守，并同时更新本文件路由表。
