# DPA4

使用 DPA4 机器学习势（DeepMD 格式模型 + PBE-D3(BJ) 色散修正）做结构优化、
单点预测和 NEB 路径计算。每个命令的详细参数见 `tcct dpa4 <命令> -h`。

> 这些命令需要单独安装 deepmd-kit、PyTorch、ASE 和 dftd3。计算结果是 DPA4
> 预测值，不是 DFT 结果。

## `tcct dpa4 relax INPUT`
- 输入：ASE 可读取的结构文件；DPA4 模型由 `--model`、`DPA4_MODEL` 或
  `~/dpa4/Neo-MPtrj/model.pt` 提供。
- 默认：固定晶胞、BFGS、`fmax=0.05 eV/Å`、DPA4 + PBE-D3(BJ)。
- 可选：`--relax-cell` 变胞；`--fix-indices-file` 固定从 1 开始编号的原子。
- 输出：优化结构、日志、extxyz 轨迹和 JSON 状态；不覆盖已有结果。

## `tcct dpa4 batch-relax [CSV]`
- 输入：至少包含 `input` 列的 CSV，可选 `id` 列；相对路径以 CSV 所在目录为准。
- 输出：每个任务一个目录，持续更新 `batch_status.csv` 和 `batch_summary.json`。
- 恢复：默认跳过已通过任务；`--retry-failed` 仅清理并重跑本命令生成的失败任务文件。

## `tcct dpa4 evaluate INPUT`
- 输入：ASE 可读取的单帧或多帧结构；`--index` 使用 ASE 帧选择语法。
- 输出：带 DPA4 单点标签的 extxyz、逐帧能量/力指标 CSV 和汇总 JSON。
- 默认只计算能量和原子力；`--stress` 显式请求应力；不执行结构优化。

## `tcct dpa4 neb INITIAL FINAL`
- 输入：已优化且原子顺序、晶胞和周期性完全匹配的初态与末态。
- 流程：IDPP 插值、普通 ASE NEB；普通 NEB 收敛且最高点位于路径内部时默认继续 CI-NEB。
- 可选：`--images`、两阶段 `fmax/steps`、`--fix-indices-file`、`--no-climb`、`--no-d3`。
- 输出：插值及优化路径、能量 CSV、最高能图像和状态 JSON。报告中注明这是 DPA4
  路径，不写成 DFT NEB。

## 依赖

deepmd-kit + ASE + dftd3（均为延迟导入，未安装时给出环境提示）。
