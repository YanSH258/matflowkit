# matflowkit/gpumd — GPUMD / NEP 相关命令

GPUMD 输出分析与 NEP 训练过程分析。每个命令的详细参数见 `mfk gpumd <命令> -h`。

## `mfk gpumd thermo [FILE]`（默认 `thermo.out`）
- 输入：空格分隔数值列的 thermo.out，列数不固定（典型 12 列）。
- 输出（stdout）：行数、列数、每列 mean/min/max/末值，标注第 1 列通常为温度。
- `--plot`：画第 1 列随步数曲线，保存当前目录 `thermo_col1.png`；
  未安装 matplotlib 时改为保存 `thermo_col1.csv` 并提示，不崩溃。
- 文件不存在：stderr 报错，退出码 1。

## `mfk gpumd merge-loss [FIRST] [RESTART]`
- 输入：首次训练和续训产生的两个 `loss.out`；默认分别为 `loss.out` 和
  `restart/loss.out`。
- 处理：默认将续训步数加上首次训练最后一个步数；`--offset` 可显式指定偏移。
- 输出：默认 `loss_merged.out`；输出已存在时拒绝覆盖。

## `mfk gpumd plot-nep-training [DIR]`
- 输入：`loss.out`、`energy_train.out`、`force_train.out`；可选 `stress_train.out`。
- 统计：完整数据上的 RMSE、MAE 和 R2；大数据只在散点绘制阶段抽样。
- 输出：默认 `nep_training.png` 和 `nep_training_metrics.json`，已存在时拒绝覆盖。

## 依赖

`thermo` / `merge-loss` 仅依赖 numpy；`plot-nep-training` 需要 matplotlib（延迟导入）。

## 维护说明

本子包独立维护：新增/修改 GPUMD 命令时，必须同一次提交更新本 README、
`matflowkit/menu.py` 菜单条目和根 `AGENTS.md` 路由表。规范见根 `CONTRIBUTING.md`。
