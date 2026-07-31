# AGENTS.md — MatFlowKit 路由文档

## 这是什么

MatFlowKit 是一个个人科研工具箱（分子动力学 / 第一性原理计算方向），Python 包名
`mdkit`，命令行入口 `mfk`，基于 typer。覆盖 ABACUS / dpdata / DeePMD / GPUMD / DPA4 的前处理、
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
| 批量检查 ABACUS SCF/relax/cell-relax 任务 | `mfk abacus audit [ROOT]` |
| 绘制 ABACUS 结构优化收敛曲线 | `mfk abacus plot-convergence [DIR]` |
| 将完成的 ABACUS 任务转换为 DeepMD NPY | `mfk abacus to-deepmd ROOT OUTPUT` |
| 拿到一批 DeePMD 训练数据，先看规模、元素组成、能量/力范围 | `mfk deepmd stat [DIR]` |
| 按精确组成合并多个 DeepMD NPY 数据集 | `mfk deepmd merge INPUT... --output DIR` |
| 需要程序化读取 DeePMD 数据集统计（接脚本/管道） | `mfk deepmd stat [DIR] --json` |
| 在 ABACUS/CP2K/DeepMD/extxyz/GPUMD 格式间转换 | `mfk dpdata convert INPUT OUTPUT --from FMT --to FMT` |
| 将带标注的 GPUMD/extxyz 转为 DeepMD raw + NPY | `mfk dpdata xyz-to-deepmd [INPUT] [OUTPUT]` |
| GPUMD 跑完后看 thermo.out 各列统计（温度、能量、压力走势） | `mfk gpumd thermo [FILE]` |
| 想快速看一眼温度随步数的演化曲线 | `mfk gpumd thermo [FILE] --plot` |
| 合并 NEP 首次训练与续训的 loss.out | `mfk gpumd merge-loss [FIRST] [RESTART]` |
| 绘制 NEP loss 与能量/力/应力预测误差 | `mfk gpumd plot-nep-training [DIR]` |
| 使用 DPA4 优化结构 | `mfk dpa4 relax INPUT` |
| 使用 DPA4 计算 NEB/CI-NEB 路径 | `mfk dpa4 neb INITIAL FINAL` |

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

### `mfk abacus audit [ROOT]`
- 输入：ROOT 下由 `INPUT` 标识的 ABACUS 任务目录。
- 判断：正常结束、SCF/结构收敛、最终能量、力和应力证据。
- 输出：`abacus_audit.csv` 和 `abacus_audit.json`。
- `--strict`：存在未完成任务时返回退出码 2。

### `mfk abacus to-deepmd ROOT OUTPUT`
- 输入：一批已完成的 ABACUS SCF、relax、cell-relax 或 MD 任务。
- 解析：dpdata；自动读取 `INPUT` 中的 `calculation` 与 `basis_type`，生成 `abacus/{lcao,pw}/{scf,relax,md}` 格式。
- 输出：`deepmd_npy/<exact_formula>/`、逐任务审计、逐帧 manifest、汇总和 SHA256。
- 默认要求 virial；不接受缺失标签，不覆盖非空输出目录。

### `mfk deepmd merge INPUT... --output DIR`
- 输入：两个或多个 DeepMD NPY 数据集。
- 按精确化学组成合并，并统一 type map。
- 默认拒绝重复的 cell+coord+atom-type 帧。

### `mfk dpdata convert INPUT OUTPUT --from FMT --to FMT`
- 对 dpdata 支持的标注数据格式执行单一格式转换。
- `dpdata` 是可选依赖，缺失时给出安装命令。
- 输出已存在时拒绝覆盖。

### `mfk dpdata xyz-to-deepmd [INPUT] [OUTPUT]`
- 输入：带 `Lattice`、`energy`、`force`（可选 `virial`）标注的 GPUMD/extxyz；
  默认 `train.xyz`。
- 解析：使用 `dpdata.MultiSystems`，允许输入中存在多种化学组成。
- 输出：默认写入 `deepmd/`，按精确组成分 system，同时生成 DeepMD raw 与 NPY；
  `--set-size` 控制 NPY 分片大小。
- 输出目录已存在且非空时拒绝覆盖；`dpdata` 缺失或解析失败时写 stderr 并非零退出。

### `mfk gpumd thermo [FILE]`（默认 `thermo.out`）
- 输入：空格分隔数值列的 thermo.out，列数不固定（典型 12 列）。
- 输出（stdout）：行数、列数、每列 mean/min/max/末值，标注第 1 列通常为温度。
- `--plot`：画第 1 列随步数曲线，保存当前目录 `thermo_col1.png`；
  未安装 matplotlib 时改为保存 `thermo_col1.csv` 并提示，不崩溃。
- 文件不存在：stderr 报错，退出码 1。

### `mfk gpumd merge-loss [FIRST] [RESTART]`
- 输入：首次训练和续训产生的两个 `loss.out`；默认分别为 `loss.out` 和
  `restart/loss.out`。
- 处理：默认将续训步数加上首次训练最后一个步数；`--offset` 可显式指定偏移。
- 输出：默认 `loss_merged.out`；输出已存在时拒绝覆盖。

### `mfk gpumd plot-nep-training [DIR]`
- 输入：`loss.out`、`energy_train.out`、`force_train.out`；可选
  `stress_train.out`。
- 统计：完整数据上的 RMSE、MAE 和 R2；大数据只在散点绘制阶段抽样。
- 输出：默认 `nep_training.png` 和 `nep_training_metrics.json`，已存在时拒绝覆盖。

### `mfk dpa4 relax INPUT`
- 输入：ASE 可读取的结构文件；DPA4 模型由 `--model`、`DPA4_MODEL` 或
  `~/dpa4/Neo-MPtrj/model.pt` 提供。
- 默认：固定晶胞、BFGS、`fmax=0.05 eV/Å`、DPA4 + PBE-D3(BJ)。
- 可选：`--relax-cell` 变胞；`--fix-indices-file` 固定从 1 开始编号的原子。
- 输出：优化结构、日志、extxyz 轨迹和 JSON 状态；不覆盖已有结果。

### `mfk dpa4 neb INITIAL FINAL`
- 输入：已优化且原子顺序、晶胞和周期性完全匹配的初态与末态。
- 流程：IDPP 插值、普通 ASE NEB；普通 NEB 收敛且最高点位于路径内部时默认继续
  CI-NEB。
- 可选：`--images`、两阶段 `fmax/steps`、`--fix-indices-file`、`--no-climb`、
  `--no-d3`。
- 输出：插值及优化路径、能量 CSV、最高能图像和状态 JSON；结果明确标为 DPA4
  最低能量路径，不冒充 DFT NEB。

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
   示例"的 docstring、菜单注册、本文件路由表更新。做不到这条，AI 可用性就断档。
7. **可验证**：新命令配最小测试数据（放 /tmp，不进仓库）实际跑一遍验收；
   有真实案例后按 `examples/` 格式（命令 + 输入 + 输出 + 解释）收录。
8. **提交纪律**：一个命令一个 commit，message 写清命令名与用途；积累 5~10 个命令打一次 tag。

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
