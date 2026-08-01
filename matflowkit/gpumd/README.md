# GPUMD / NEP

GPUMD 输出分析与 NEP 训练过程分析。每个命令的详细参数见 `mfk gpumd <命令> -h`。

## `mfk gpumd from-deepmd DATASET [OUTPUT]`

- 输入：一个 DeepMD NPY system，或包含多个 system 的数据集根目录；递归查找
  `type.raw + set.*/`。
- 输出：默认 `train.xyz`，内容是 GPUMD 要求的 Extended XYZ，不是普通 XYZ。
- 标签：所有帧必须包含有限的 energy 和 force；virial 默认可选，`--virial` 强制要求。
- 多组成：统一元素映射后由 `dpdata.MultiSystems` 写入同一个文件。
- 验证：写出后以 `gpumd/xyz` 回读，核对 system 数、总帧数和标签完整性。
- 已有输出不会覆盖。

```bash
mfk gpumd from-deepmd ./deepmd_npy train.xyz
mfk gpumd from-deepmd ./deepmd_npy train.xyz --virial
```

## `mfk gpumd thermo [FILE]`（默认 `thermo.out`）
- 输入：GPUMD `thermo.out`；统计模式可读取任意数值列。
- 输出（stdout）：每列的 mean、min、max 和末值。
- `--plot`：支持旧版 12 列正交晶胞和当前 18 列 triclinic 格式，默认读取同目录
  `run.in` 中的 `time_step` 与 `dump_thermo`。
- 图片：默认在 `thermo.out` 所在目录生成 `thermo.png`，包括温度、压力、
  动能/势能、晶格长度、体积和晶格角；
  12 列格式没有晶格角时改画总能量。
- 平均值：默认在同一目录生成 `thermo_averages.txt`，统计后 50%；用
  `--start-fraction` 修改。`--output` 和 `--averages` 可分别指定其他位置。
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
- [GPUMD train.xyz and test.xyz](https://gpumd.org/nep/input_files/train_test_xyz.html)
- [GPUMDkit plotting scripts](https://zhyan0603.github.io/GPUMDkit/htmls/plot_scripts.html)
