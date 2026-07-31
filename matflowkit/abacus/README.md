# matflowkit/abacus — ABACUS 相关命令

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

## `mfk abacus to-deepmd ROOT OUTPUT`
- 输入：一批已完成的 ABACUS SCF、relax、cell-relax 或 MD 任务。
- 解析：dpdata；自动读取 `INPUT` 中的 `calculation` 与 `basis_type`，生成
  `abacus/{lcao,pw}/{scf,relax,md}` 格式。
- 输出：`deepmd_npy/<exact_formula>/`、逐任务审计、逐帧 manifest、汇总和 SHA256。
- 默认要求 virial；不接受缺失标签，不覆盖非空输出目录。

## 依赖

- 硬依赖：仅 typer + numpy。
- `plot-convergence`：matplotlib（延迟导入）。
- `to-deepmd`：dpdata（延迟导入）。

## 维护说明

本子包独立维护：新增/修改 ABACUS 命令时，必须同一次提交更新本 README、
`matflowkit/menu.py` 菜单条目和根 `AGENTS.md` 路由表。规范见根 `CONTRIBUTING.md`。
