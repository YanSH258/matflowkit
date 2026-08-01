# MatFlowKit

**面向计算材料研究的轻量级 workflow + analysis toolkit，用统一 CLI 管理常见科研计算流程。**

MatFlowKit 把平时散落在不同目录里的检查、转换、统计和画图脚本收进一个命令行入口
`mfk`。它不负责安装或替代 ABACUS、CP2K、VASP、DeepMD-kit、GPUMD、DPA4，而是处理这些
软件前后的重复工作。

## 为什么做这个工具

一次完整的计算材料工作通常会经过多个程序：

```text
DFT 计算（ABACUS / CP2K / VASP）
        ↓ 检查与数据提取
训练数据（DeepMD / NEP）
        ↓ 统计、合并与查重
模型训练与验证
        ↓
MD 模拟（GPUMD）
        ↓
结果分析与画图
```

这些步骤本身不复杂，但很容易反复写临时脚本，也容易出现输入约定不同、输出文件名混乱、
漏查未收敛任务等问题。MatFlowKit 只收录实际会重复使用的操作，并为它们提供固定命令、
输入约定和输出格式。

## 主要功能

- 检查 ABACUS 和 CP2K 任务是否结束、是否收敛、标签是否完整；
- 从 ABACUS、CP2K 或 VASP 输出中收集标注，生成 DeepMD NPY；
- 转换 extxyz、DeepMD、CP2K、ABACUS、VASP 等常用格式；
- 在 CIF、Extended XYZ、POSCAR 之间转换，并生成 ABACUS STRU；
- 统计、合并和检查训练数据中的重复结构；
- 分析 GPUMD `thermo.out` 和 NEP 训练结果；
- 使用 DPA4 做结构优化、单点计算和 NEB；
- 用同一套字体、配色和版式生成 PNG 科研图。

## 安装

推荐使用 [uv](https://docs.astral.sh/uv/)：

```bash
git clone git@github.com:YanSH258/matflowkit.git
cd matflowkit
uv sync --extra plot --extra dpdata --extra structure
uv run mfk --help
```

需要在任意目录直接运行 `mfk` 时：

```bash
uv tool install --editable '.[plot,dpdata,structure]'
```

也可以安装到现有 Python 3.9+ 环境：

```bash
python -m pip install -e '.[plot,dpdata,structure]'
mfk --help
```

MatFlowKit 只安装 Python 依赖。ABACUS、CP2K、DeepMD-kit 和 GPUMD 需要另外安装。
DPA4 需要单独的 deepmd-kit + dftd3 环境，见
[DPA4 说明](matflowkit/dpa4/README.md)。

## 使用

### 命令行

```bash
mfk --help
mfk doctor
mfk abacus audit ./tasks --strict
mfk abacus report ./tasks
mfk abacus to-deepmd ./tasks ./deepmd_data
mfk vasp to-deepmd ./vasp_tasks ./vasp_data
mfk gpumd from-deepmd ./deepmd_data/deepmd_npy train.xyz
mfk deepmd stat ./deepmd_data/deepmd_npy
mfk dpdata overlap train.extxyz test.extxyz
mfk structure convert structure.cif --to stru
mfk gpumd plot-nep-training ./train
```

所有命令都支持 `-h`：

```bash
mfk abacus audit -h
```

安装后可运行 `mfk doctor`，检查可选依赖以及 `ABACUS_PP_PATH`、
`ABACUS_ORB_PATH` 的配置状态；使用 `mfk doctor --json` 可获得机器可读结果。

### 交互菜单

不带参数运行即可进入菜单。菜单最终调用的仍是同一条 CLI 命令。

```bash
mfk
```

### 一个常用流程

```bash
# 1. 检查 DFT 任务
mfk abacus audit ./tasks --strict

# 2. 收集 DeepMD NPY
mfk abacus to-deepmd ./tasks ./deepmd_data

# 3. 检查数据规模和数值范围
mfk deepmd stat ./deepmd_data/deepmd_npy

# 4. 检查训练集与测试集是否重复
mfk dpdata overlap train.extxyz test.extxyz

# 5. 训练结束后画误差图
mfk gpumd plot-nep-training ./train
```

更多例子见 [常用数据流程](examples/common_data_workflows.md)。

## 支持的模块


| 模块   | 目前包含的命令                          |
| -------- | ----------------------------------------- |
| ABACUS | relax 检查、批量审计、任务报告、收敛图、转 DeepMD |
| CP2K   | 输出审计、单点数据收集                  |
| VASP   | OUTCAR 转 DeepMD NPY                    |
| DeepMD | 数据集统计、按组成合并、数据集报告       |
| dpdata | 格式转换、XYZ 转 DeepMD、数据集查重     |
| GPUMD  | NPY 转训练 XYZ、thermo 图、loss 合并、NEP 训练图 |
| DPA4   | 结构优化、批量优化、单点计算、NEB       |
| Structure | CIF、Extended XYZ、POSCAR 转换与 ABACUS STRU 生成 |

## 项目目录

```text
matflowkit/
├── matflowkit/        # Python 包
│   ├── cli.py         # CLI 入口
│   ├── menu.py        # 交互菜单
│   ├── registry.py    # CLI 与菜单共用的命令注册表
│   ├── abacus/ cp2k/ vasp/ deepmd/ dpdata/ dpa4/ gpumd/ structure/
│   └── common/        # 共用代码和画图样式
├── tests/             # 测试
├── examples/          # 使用例子
├── workflow/          # 多命令流程脚本
├── knowledge/         # 使用记录和约定
├── AGENTS.md          # 命令路由和开发约定
└── CONTRIBUTING.md    # 添加命令的方法
```

## 文档

- 各模块的输入和输出：`matflowkit/<module>/README.md`
- 绘图规范：[knowledge/plotting_standard.md](knowledge/plotting_standard.md)
- 添加命令：[CONTRIBUTING.md](CONTRIBUTING.md)
- 版本变化：[CHANGELOG.md](CHANGELOG.md)
- 命令路由：[AGENTS.md](AGENTS.md)

## 参考文档

- [GPUMD documentation](https://gpumd.org/)
- [GPUMDkit](https://github.com/zhyan0603/GPUMDkit)
- [DeePMD-kit documentation](https://docs.deepmodeling.com/projects/deepmd/en/latest/)
- [dpdata documentation](https://docs.deepmodeling.com/projects/dpdata/en/master/)
- [ABACUS documentation](https://abacus.deepmodeling.com/en/latest/)
- [CP2K manual](https://manual.cp2k.org/)
- [VASP documentation](https://www.vasp.at/wiki/)

## 贡献

添加高频重复使用的命令。具体要求见 [CONTRIBUTING.md](CONTRIBUTING.md)。
