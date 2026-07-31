# MatFlowKit

我平时处理 ABACUS、CP2K、DeepMD、GPUMD 和 DPA4 数据时用的一组命令行工具。
入口统一为 `mfk`，各计算软件仍按原来的方式安装和运行。

## 主要流程

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

目前收录的是我已经实际用过的操作：检查任务、转换数据、查重和画训练曲线。

## 功能

### 数据准备（DFT → ML 势数据集）
- 从 ABACUS / CP2K 输出提取能量、力、virial，生成 DeepMD NPY 数据集
- extxyz / DeepMD / CP2K / ABACUS 等格式互转（基于 dpdata）
- 按化学组成合并数据集、检查训练/测试集重复帧

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

MatFlowKit 只安装自己的 Python 依赖。ABACUS、DeepMD-kit 和 GPUMD 等软件需要另外安装。

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

不用 uv 时也可以在 Python 3.9+ 环境运行 `pip install -e .`。可选依赖见
`pyproject.toml`。DPA4 需要单独的 deepmd-kit + dftd3 环境，见
`matflowkit/dpa4/README.md`。

## Quick Start

```bash
mfk --help                          # 查看全部命令
mfk                                 # 进入交互式菜单

mfk abacus audit ./tasks --strict   # 批量审计 ABACUS 任务
mfk deepmd stat ./dataset           # DeePMD 数据集统计
mfk gpumd thermo --plot             # thermo.out 统计 + 温度曲线
mfk dpdata overlap train.xyz test.xyz  # 检查训练/测试集重复帧
```

所有命令都支持 `-h`。路径没有指定时通常使用当前目录。

## Typical Workflow

下面是一套常用的数据处理顺序：

```bash
mfk abacus audit ./tasks --strict                    # 1. 确认 DFT 任务全部完成
mfk abacus to-deepmd ./tasks ./deepmd_data           # 2. 提取为 DeepMD NPY
mfk deepmd stat ./deepmd_data/deepmd_npy             # 3. 检查数据集规模与范围
mfk dpdata overlap train.extxyz test.extxyz          # 4. 训练/测试集查重
# ... 用 GPUMD/DeepMD-kit 训练（外部环境）...
mfk gpumd plot-nep-training ./train                  # 5. 分析训练误差
```

其他例子见 [examples/common_data_workflows.md](examples/common_data_workflows.md)。

## Project Structure

```
matflowkit/
├── matflowkit/        # Python 包
│   ├── cli.py         #   typer 入口与子命令注册
│   ├── menu.py        #   交互式菜单（复用 cli.py，无独立逻辑）
│   ├── abacus/ cp2k/ deepmd/ dpdata/ dpa4/ gpumd/
│   └── common/        #   共用代码和画图样式
├── tests/             # pytest（uv run pytest tests/）
├── examples/          # 命令使用案例与常用工作流
├── workflow/          # 串联多条 mfk 命令的流程脚本
├── knowledge/         # 使用记录和约定
├── AGENTS.md          # 命令路由和开发约定
└── CONTRIBUTING.md    # 添加新命令的规范
```

## Documentation

- 各软件命令的输入/输出约定：`matflowkit/<software>/README.md`
- 命令路由和开发约定：`AGENTS.md`
- 贡献指南：`CONTRIBUTING.md`
- 使用案例：`examples/`

## 贡献

只添加确实会重复使用的命令。具体做法见 [CONTRIBUTING.md](CONTRIBUTING.md)。
