# MatFlowKit

个人科研工具箱（分子动力学 / 第一性原理计算方向），覆盖 **ABACUS / CP2K / dpdata / DeePMD / GPUMD / DPA4**
三条工作线的前处理 → 过程分析 → 后处理。设计借鉴 GPUMDkit：单一入口 `mfk` +
子命令分发，支持**命令行直跑**和**交互式菜单**两种模式。

## 安装

```bash
cd MatFlowKit
pip install -e .
```

基础依赖为 `typer`、`numpy`。需要绘图和数据转换时使用完整安装：

```bash
pip install -e ".[all]"
```

## 命令行模式

```bash
mfk --help                       # 总览
mfk abacus check-relax ./run     # 检查 ABACUS relax 是否收敛、离子步数、总能、最大力
mfk abacus audit ./tasks         # 批量审计 SCF/relax/cell-relax 任务
mfk abacus plot-convergence run  # 绘制结构优化收敛曲线
mfk abacus to-deepmd tasks data  # 将完成任务提取为 DeepMD NPY
mfk deepmd stat ./data           # 统计 DeePMD 数据集（system/frame/元素/能量/力范围）
mfk deepmd stat ./data --json    # 机器可读 JSON 输出
mfk deepmd merge a b -o merged   # 按精确组成合并 NPY 数据集
mfk dpdata convert in out --from deepmd/npy --to extxyz
mfk dpdata xyz-to-deepmd train.xyz deepmd  # GPUMD/extxyz 转 DeepMD raw + NPY
mfk dpdata overlap train.extxyz test.extxyz # 检查重复帧与测试集泄漏
mfk gpumd thermo thermo.out      # 统计 thermo.out 各列
mfk gpumd thermo --plot          # 同时画第 1 列（温度）演化，保存 thermo_col1.png
mfk gpumd merge-loss             # 合并首次训练与续训的 loss.out
mfk gpumd plot-nep-training .    # 绘制 loss 与能量/力/应力预测误差
mfk dpa4 relax structure.xyz     # DPA4 固定晶胞结构优化
mfk dpa4 batch-relax structures.csv  # 按 manifest 批量优化并断点续跑
mfk dpa4 evaluate structures.extxyz  # 批量预测能量、力和可选应力
mfk dpa4 neb IS.xyz FS.xyz       # DPA4 NEB 与 CI-NEB
mfk cp2k audit ./tasks           # 审计 CP2K 结束、SCF、能量、力和晶胞
mfk cp2k collect ./tasks cp2k_dataset # 单点能量和力转 DeepMD NPY
```

所有命令的路径参数都默认为当前目录（或当前目录下的默认文件），支持 `-h` 查看帮助。

## 交互模式

直接运行 `mfk`（不带任何参数）进入交互菜单：

```
$ mfk
  ... banner ...
请选择软件:
  1) ABACUS
  2) DeePMD
  3) GPUMD
  0) Exit
> 3
[GPUMD] 可用命令:
  1) thermo         分析 thermo.out 各列统计，可选画图
  0) 返回
> 1
[GPUMD -> thermo] 请依次输入参数（回车使用默认值，q 取消）:
  thermo 文件 [thermo.out]:
  是否画第 1 列曲线 (y/n) [n]: y
等价命令: mfk gpumd thermo thermo.out --plot
```

菜单不实现任何独立逻辑：收集参数后打印等价命令，然后调用同一个 typer app 执行。
任何时候输入 `q` 或 `0` 返回上级 / 退出。

## 目录结构

```
MatFlowKit/
├── mdkit/              # Python 包（命令实现）
│   ├── cli.py          #   typer 入口与子命令注册
│   ├── menu.py         #   交互式菜单
│   ├── abacus/         #   ABACUS 相关命令
│   ├── deepmd/         #   DeePMD 相关命令
│   ├── dpdata/         #   dpdata 通用格式转换
│   ├── gpumd/          #   GPUMD 相关命令
│   └── common/         #   跨命令共享代码
├── workflow/           # 串联多条 mfk 命令的流程脚本
├── knowledge/          # 给 AI / 人看的经验文档
└── examples/           # 命令使用案例
```

## 如何添加新命令

以给 GPUMD 加一个 `plot-thermo` 命令为例：

1. 在对应软件子包（如 `mdkit/gpumd/`）新建 `plot_thermo.py`，实现一个普通函数，
   用 `typer.Argument` / `typer.Option` 声明参数；路径参数默认值给当前目录 / 默认文件名。
2. 在 `mdkit/cli.py` 中 import 并注册：`gpumd_app.command("plot-thermo")(plot_thermo)`。
3. 在 `mdkit/menu.py` 的 `MENU` 对应软件条目里追加一行（命令名、一句话说明、参数列表）。
4. 运行 `mfk gpumd plot-thermo -h` 确认帮助正常。

规范：命令必须支持 `-h`；输入默认当前目录；产生的输出文件（图片、csv 等）写到当前目录；
报错信息写 stderr 并以非零退出码退出。详见 `AGENTS.md`。

补充脚本的原则（精简版，完整版见 `AGENTS.md`）：

- 用出来的才搬：第三次手动做同一件事时才变成命令，不凑数
- 搬运 ≠ 重写：旧脚本先包 typer 外壳、逻辑原样，跑通再重构
- 约定大于配置：默认当前目录与标准文件名；结构数据以 extxyz 为中间格式
- 一个命令干一件事：串联交给 workflow 层
- 依赖克制：硬依赖仅 typer + numpy，其余延迟导入
- 文档与命令同生同死：docstring + 菜单注册 + `AGENTS.md` 路由表同一次提交完成
- 一个命令一个 commit，配最小测试数据跑一遍再提交

## 常用数据流程

### ABACUS 批量结果转 DeepMD NPY

```bash
mfk abacus audit ./tasks --strict
mfk abacus to-deepmd ./tasks ./deepmd_data \
  --type-map "Ca Mg Zn Sr P O H" \
  --frames all
mfk deepmd stat ./deepmd_data/deepmd_npy
```

`to-deepmd` 自动从 `INPUT` 判断 `abacus/{lcao,pw}/{scf,relax,md}`，要求完整的
能量、力和 virial，不使用零值填充缺失标注。

### 合并多个 DeepMD 数据集

```bash
mfk deepmd merge dataset_a dataset_b dataset_c \
  --output merged_dataset
```

数据按精确化学组成合并。默认使用晶胞、坐标和原子类型哈希检查重复帧。

### 通用格式转换

```bash
mfk dpdata convert cp2k_work cp2k_npy \
  --from cp2kdata/md --to deepmd/npy

mfk dpdata convert deepmd_system train.xyz \
  --from deepmd/npy --to extxyz
```

### 结构数据集重叠检查

```bash
mfk dpdata overlap train.extxyz test.extxyz --strict
```

元素、周期性、晶胞和坐标按指定精度规范化后进行哈希比较。输出
`frame_overlap.json` 和匹配帧 CSV，同时报告文件内部重复和跨数据集重叠。
这是重复构型检测，不是近似结构相似度分析。

### GPUMD/extxyz 转 DeepMD raw + NPY

```bash
mfk dpdata xyz-to-deepmd train.xyz deepmd
```

输入需包含晶胞、能量和原子力标注；多种化学组成会自动拆成多个 system。输出目录
同时包含 DeepMD raw 文件与 `set.*/*.npy`，默认拒绝覆盖非空目录。

### 合并 NEP 续训 loss

```bash
mfk gpumd merge-loss loss.out restart/loss.out -o loss_merged.out
```

默认将续训文件第一列加上首次训练的最后一个步数。续训文件已使用全局步数时，
使用 `--offset 0`。

### 绘制 NEP 训练与预测误差

```bash
mfk gpumd plot-nep-training ./train
```

读取 `loss.out`、`energy_train.out` 和 `force_train.out`；存在
`stress_train.out` 时自动加入应力面板。生成 `nep_training.png` 和
`nep_training_metrics.json`。误差使用完整数据计算，散点图对超大数据自动抽样。

### DPA4 结构优化

先在包含兼容 DeepMD-kit、PyTorch、ASE 和 dftd3 的环境中安装命令：

```bash
conda activate dpa4
pip install -e /home/yan/matflowkit
```

```bash
mfk dpa4 relax structure.xyz \
  --model ~/dpa4/Neo-MPtrj/model.pt \
  --fmax 0.05 --fixed-cell
```

默认执行固定晶胞优化，并叠加 PBE-D3(BJ)。使用 `--relax-cell` 显式启用变胞优化，
使用 `--fix-indices-file fixed.txt` 固定从 1 开始编号的原子。输出包括优化结构、
日志、逐步 extxyz 轨迹和 JSON 状态文件。

### DPA4 NEB

```bash
mfk dpa4 neb initial.extxyz final.extxyz \
  --model ~/dpa4/Neo-MPtrj/model.pt \
  --images 5 --neb-fmax 0.10 --ci-fmax 0.05
```

端点必须具有相同原子数、元素顺序、晶胞和周期性。命令使用 IDPP 插值，先执行
普通 NEB，收敛且最高能图像位于路径内部时继续执行 CI-NEB。输出包括各阶段路径、
`energy_profile.csv`、最高能图像和 `status.json`。所得势垒属于 DPA4 预测，
不是第一性原理 NEB 势垒。

### CP2K 输出审计

```bash
mfk cp2k audit ./tasks --strict
```

默认递归查找 `output.log`，检查正常结束、SCF 收敛、最终能量、完整原子力块和
晶胞证据，生成 `cp2k_audit.csv` 与 JSON 汇总。`PROGRAM ENDED AT` 不会被
单独视为通过证据。

### CP2K 单点数据收集

```bash
mfk cp2k collect ./tasks ./cp2k_dataset \
  --structure-name structure.xyz
```

每个任务目录必须包含相互对应的 `output.log` 和单帧 `structure.xyz`。命令只收集
通过审计的最终能量和原子力，按精确组成输出 DeepMD NPY、extxyz、逐帧 manifest
和校验报告。它不会从 `GEO_OPT` 日志重建末态，也不会验证不同任务的 DFT 设置一致性。

### DPA4 批量结构优化

准备至少包含 `input` 列的 CSV，可选 `id` 列；相对路径以 CSV 所在目录为准：

```csv
id,input
hap_001,structures/hap_001.cif
hap_010,structures/hap_010.cif
```

```bash
mfk dpa4 batch-relax structures.csv \
  --output-dir dpa4_batch_relax \
  --model ~/dpa4/Neo-MPtrj/model.pt
```

每个任务写入独立目录，`batch_status.csv` 和 `batch_summary.json` 持续记录状态。
重复运行会跳过已经通过的任务；使用 `--retry-failed` 重新运行失败或未收敛任务。

### DPA4 单点批量预测

```bash
mfk dpa4 evaluate structures.extxyz \
  --model ~/dpa4/Neo-MPtrj/model.pt
```

默认读取全部帧并计算能量和原子力，生成带标签 extxyz、逐帧指标 CSV 和汇总 JSON。
使用 `--index` 选择帧，使用 `--stress` 额外计算应力。该命令不会优化结构。
