# ABACUS

`to-deepmd` 根据 `INPUT` 中的 `basis_type` 和 `calculation` 选择 dpdata 官方的
`abacus/{lcao,pw}/{scf,relax,md}` 格式，不使用一个模糊的通用解析模式。

ABACUS 任务的检查、批量审计、收敛分析与数据提取。每个命令的详细参数见
`mfk abacus <命令> -h`。

## `mfk abacus check-relax [DIR]`（默认当前目录）
- 输入：DIR 下的 `OUT.*/running_relax.log` 或 `running_relax.log`（ABACUS relax 日志）。
- 输出（stdout）：日志路径；是否发现收敛标记（列出匹配行）；最后一步离子步序号；
  总能（匹配 `final etot` / `!FINAL` 行，找不到会明说"未找到总能行"）；最大力。
- 日志不存在：stderr 报错，退出码 1。

## `mfk abacus audit [ROOT]`
- 输入：ROOT 下由 `INPUT` 标识的 ABACUS 任务目录。
- 判断：正常结束、SCF/结构收敛、最终能量、力和应力证据。
- 输出：`abacus_audit.csv` 和 `abacus_audit.json`。
- `--strict`：存在未完成任务时返回退出码 2。

## `mfk abacus plot-convergence [DIR]`
- 绘制 ABACUS relax / cell-relax 的结构优化收敛曲线（能量、力随离子步）。
- 依赖 matplotlib（延迟导入，未安装时清晰提示）。

## `mfk abacus report [ROOT]`
- 复用 `audit` 的任务发现、完成证据和状态判断，以及 `plot-convergence` 的能量、
  最大力和最大应力解析，不另写 ABACUS 日志解析器。
- 输出目录默认为 `abacus_report/`，包含 `report.html`、`report.json`、`jobs.csv`、
  `failed_jobs.csv` 和 `figures/` 下的任务状态与 relax 指标 PNG。
- `--expected`：记录并检查预期任务数；`--strict`：报告生成后，存在未完成任务或
  任务数不符时返回退出码 2。
- 提示只陈述缺少日志、完成证据不完整、任务数不符等事实，不判断计算质量。

## `mfk abacus to-deepmd ROOT OUTPUT`
- 输入：一批已完成的 ABACUS SCF、relax、cell-relax 或 MD 任务。
- 解析：dpdata；自动读取 `INPUT` 中的 `calculation` 与 `basis_type`，生成
  `abacus/{lcao,pw}/{scf,relax,md}` 格式。
- 输出：`deepmd_npy/<exact_formula>/`、逐任务审计、逐帧 manifest、汇总和 SHA256。
- 默认要求 virial；不接受缺失标签，不覆盖非空输出目录。

## 依赖

- 硬依赖：仅 typer + numpy。
- `plot-convergence`：matplotlib（延迟导入）。
- `report`：matplotlib（延迟导入）。
- `to-deepmd`：dpdata（延迟导入）。
