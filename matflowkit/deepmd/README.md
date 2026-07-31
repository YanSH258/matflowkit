# DeePMD

DeePMD raw/npy 数据集的统计与合并。每个命令的详细参数见 `mfk deepmd <命令> -h`。

## `mfk deepmd report DATASET_PATH`

- 输入：DeepMD NPY 数据集。每个 system 需要 `type.raw`、一个或多个 `set.*`，
  set 中需要 `coord.npy` 和 `box.npy`；`energy.npy`、`force.npy`、`virial.npy`
  可以缺失并会如实记录。`type_map.raw` 可选。
- 输出：默认写入新的 `deepmd_report/` 目录，包括 `report.html`、`report.json`、
  `systems.csv`、`duplicates.csv` 和三张 PNG 图。
- 统计：总能、每原子能量、同组成相对能量、力分量、原子力模长、逐帧最大原子力、
  组成分布和 exact normalized duplicate。
- `--force-threshold VALUE` 只统计超过阈值的原子数，不据此评价数据质量。
- 重复帧按元素、PBC、晶胞和坐标在 6 位小数归一化后判断；不做近似结构或 RMSD 聚类。
- 输出目录非空、必需结构数组缺失或数组形状不一致时退出码非零。

示例：

```bash
mfk deepmd report ./dataset
mfk deepmd report ./dataset --output audit_2026_07 --force-threshold 10
```

## `mfk deepmd stat [DIR]`（默认当前目录）
- 输入：DeePMD raw/npy 数据集。DIR 下每个子目录是一个 system（含 `type.raw` +
  `set.*/{coord,energy,force,box}.npy`，可选 `type_map.raw`）；DIR 本身是单个 system 也兼容。
- 输出（stdout）：system 数量、每个 system 的 frame 数与原子数、各元素原子计数
  （有 type_map.raw 时显示元素符号）、能量范围、力分量绝对值范围；`--json` 输出 JSON。
- 找不到数据：stderr 报错，退出码 1。仅依赖 numpy，不依赖 dpdata。

## `mfk deepmd merge INPUT... --output DIR`
- 输入：两个或多个 DeepMD NPY 数据集。
- 按精确化学组成合并，并统一 type map。
- 默认拒绝重复的 cell+coord+atom-type 帧。

## 依赖

`stat` 仅依赖 numpy；`report` 画图需要 matplotlib（延迟导入）；`merge` 需要
dpdata（延迟导入）。
