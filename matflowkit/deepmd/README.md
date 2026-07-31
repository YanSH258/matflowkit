# DeePMD

DeePMD raw/npy 数据集的统计与合并。每个命令的详细参数见 `mfk deepmd <命令> -h`。

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

`stat` 仅依赖 numpy；`merge` 需要 dpdata（延迟导入）。
