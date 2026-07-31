# GPUMD / NEP

GPUMD 输出分析与 NEP 训练过程分析。每个命令的详细参数见 `mfk gpumd <命令> -h`。

## `mfk gpumd thermo [FILE]`（默认 `thermo.out`）
- 输入：GPUMD `thermo.out`；统计模式可读取任意数值列。
- 输出（stdout）：每列的 mean、min、max 和末值。
- `--plot`：支持旧版 12 列正交晶胞和当前 18 列 triclinic 格式，默认读取同目录
  `run.in` 中的 `time_step` 与 `dump_thermo`。
- 图片：`thermo.png`，包括温度、压力、动能/势能、晶格长度、体积和晶格角；
  12 列格式没有晶格角时改画总能量。
- 平均值：`thermo_averages.txt`，默认统计后 50%；用 `--start-fraction` 修改。
- 实现参考 GPUMDkit 的 `gpumdkit.sh -plt thermo` 使用方式，但代码在本项目中重新编写。
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

`thermo` 统计和 `merge-loss` 仅依赖 numpy；画图和 `plot-nep-training` 需要 matplotlib。

## 参考

- [GPUMD thermo.out](https://gpumd.org/gpumd/output_files/thermo_out.html)
- [GPUMD dump_thermo](https://gpumd.org/gpumd/input_parameters/dump_thermo.html)
- [GPUMDkit plotting scripts](https://zhyan0603.github.io/GPUMDkit/htmls/plot_scripts.html)
