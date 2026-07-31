# MatFlowKit

A lightweight workflow and analysis toolkit for computational materials simulations.

MatFlowKit provides unified command-line utilities for managing, processing and
analyzing data generated from electronic structure calculations and machine-learning
potential simulations. It is designed to work with your **existing** computational
environments — ABACUS, CP2K, DeepMD-kit, GPUMD, DPA4 — not to replace or manage them.

> 中文说明：MatFlowKit 是一个轻量级科研流程工具箱，用统一 CLI（`mfk`）管理
> 计算材料研究中的重复性操作。它只提供工具层，不管理软件环境。
> 注意：PyPI 上的 `mdkit` 是别人的包，与本项目无关，本项目只通过源码安装。

## Why MatFlowKit?

计算材料研究的日常流程涉及一串彼此独立的工具：

```
DFT 计算 (ABACUS / CP2K)
      ↓ 数据提取与格式转换
ML 势数据集 (DeepMD / NEP)
      ↓ 训练
验证与误差分析
      ↓
MD 模拟 (GPUMD)
      ↓
后处理分析
```

每一步都有大量重复的手动操作：检查任务收敛没有、把输出转成训练数据、
统计数据集规模、画训练曲线…… 这些操作通常散落在每个人自己的脚本里。

MatFlowKit 把这些**被反复验证过的操作**收进一个统一命令行入口，
让课题组共用同一套工具，而不是各写各的脚本。

## Features

### 数据准备（DFT → ML 势数据集）
- 从 ABACUS / CP2K 输出提取能量、力、virial，生成 DeepMD NPY 数据集
- extxyz / DeepMD / CP2K / ABACUS 等格式互转（基于 dpdata）
- 按精确化学组成合并数据集、检查训练/测试集重复帧

### 过程检查与审计
- 批量审计 ABACUS / CP2K 任务：算完没有、收敛没有、标签齐不齐
- ABACUS 结构优化收敛曲线绘制

### 训练与模拟分析
- GPUMD `thermo.out` 统计与快速绘图
- NEP 训练 loss 合并、能量/力/应力预测误差分析
- DPA4 结构优化、单点预测、NEB（独立环境，见子包 README）

### 支持的软件

| 软件 | 功能 |
| --- | --- |
| ABACUS | 收敛检查、批量审计、收敛曲线、转 DeepMD 数据 |
| CP2K | 输出审计、单点数据收集 |
| DeepMD | 数据集统计、按组成合并 |
| dpdata | 通用格式转换、数据集重叠检查 |
| GPUMD | thermo 分析、NEP 训练分析 |
| DPA4 | 结构优化、批量优化、单点预测、NEB |

## Installation

MatFlowKit 只管理自己的 Python 依赖；ABACUS / DeepMD-kit / GPUMD 等外部
计算软件请按各自文档单独安装。

需要 [uv](https://docs.astral.sh/uv/)（`curl -LsSf https://astral.sh/uv/install.sh | sh`）：

```bash
git clone git@github.com:YanSH258/matflowkit.git
cd matflowkit
uv sync --extra plot --extra dpdata --extra structure
uv run mfk --help    # 验证
```

想在任意目录直接使用 `mfk`：

```bash
uv tool install --editable '.[plot,dpdata,structure]'
```

其他方式：不用 uv 时可在任何 Python 3.9+ 环境 `pip install -e .`（extras 见
`pyproject.toml`）；依赖锁定在 `uv.lock`，组内环境可复现。DPA4 命令需要独立的
deepmd-kit + dftd3 环境，见 `matflowkit/dpa4/README.md`。

## Quick Start

```bash
mfk --help                          # 查看全部命令
mfk                                 # 进入交互式菜单

mfk abacus audit ./tasks --strict   # 批量审计 ABACUS 任务
mfk deepmd stat ./dataset           # DeePMD 数据集统计
mfk gpumd thermo --plot             # thermo.out 统计 + 温度曲线
mfk dpdata overlap train.xyz test.xyz  # 检查训练/测试集重复帧
```

所有命令支持 `-h`；路径参数默认当前目录；产出文件写到当前目录；
报错走 stderr 且退出码非零。

## Typical Workflow

以"DFT 数据 → ML 势训练 → 分析"为例，每一步对应一条 `mfk` 命令：

```bash
mfk abacus audit ./tasks --strict                    # 1. 确认 DFT 任务全部完成
mfk abacus to-deepmd ./tasks ./deepmd_data           # 2. 提取为 DeepMD NPY
mfk deepmd stat ./deepmd_data/deepmd_npy             # 3. 检查数据集规模与范围
mfk dpdata overlap train.extxyz test.extxyz          # 4. 训练/测试集查重
# ... 用 GPUMD/DeepMD-kit 训练（外部环境）...
mfk gpumd plot-nep-training ./train                  # 5. 分析训练误差
```

更多组合流程见 [examples/common_data_workflows.md](examples/common_data_workflows.md)，
多步串联脚本见 `workflow/`。

## Project Structure

```
matflowkit/
├── matflowkit/        # Python 包（每个软件子包有自己的 README，独立维护）
│   ├── cli.py         #   typer 入口与子命令注册
│   ├── menu.py        #   交互式菜单（复用 cli.py，无独立逻辑）
│   ├── abacus/ cp2k/ deepmd/ dpdata/ dpa4/ gpumd/
│   └── common/        #   跨命令共享代码
├── tests/             # pytest（uv run pytest tests/）
├── examples/          # 命令使用案例与常用工作流
├── workflow/          # 串联多条 mfk 命令的流程脚本
├── knowledge/         # 给 AI / 人看的经验文档
├── AGENTS.md          # AI agent 路由文档（场景 → 命令）
└── CONTRIBUTING.md    # 添加新命令的规范
```

## Documentation

- 各软件命令的输入/输出约定：`matflowkit/<software>/README.md`
- AI agent / 场景路由：`AGENTS.md`
- 贡献指南：`CONTRIBUTING.md`
- 使用案例：`examples/`

## Roadmap

- [x] 统一 CLI（`mfk`）+ 交互式菜单
- [x] ABACUS / CP2K / DeepMD / dpdata / GPUMD 工具集
- [x] DPA4 结构优化与 NEB
- [x] uv 锁定环境、命令测试
- [ ] workflow 自动化（多命令串联的模板化）
- [ ] 分析报告自动生成
- [ ] AI 辅助知识库（`knowledge/` 持续积累）

## 贡献

欢迎课题组成员把反复手动做的操作搬进来。原则与步骤见
[CONTRIBUTING.md](CONTRIBUTING.md)，核心一条：**第三次手动做同一件事时才变成命令**。
