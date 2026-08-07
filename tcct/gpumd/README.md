# GPUMD / NEP

GPUMD `train.xyz` 准备、输出分析与 NEP 训练过程分析。每个命令的详细参数见
`tcct gpumd <命令> -h`。

## `tcct gpumd npy-to-xyz DATASET [OUTPUT]`

- 输入：一个 DeepMD NPY system，或包含多个 system 的数据集根目录；递归查找
  `type.raw + set.*/`。
- 输出：默认 `train.xyz`，内容是 GPUMD 要求的 Extended XYZ，不是普通 XYZ。
- 标签：所有帧必须包含有限的 energy 和 force；virial 默认可选，`--virial` 强制要求。
- 多组成：统一元素映射后由 `dpdata.MultiSystems` 写入同一个文件。
- 验证：写出后以 `gpumd/xyz` 回读，核对 system 数、总帧数和标签完整性。
- 已有输出不会覆盖。

```bash
tcct gpumd npy-to-xyz ./deepmd_npy train.xyz
tcct gpumd npy-to-xyz ./deepmd_npy train.xyz --virial
```

## `tcct gpumd thermo [FILE]`（默认 `thermo.out`）
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

## `tcct gpumd merge-loss [FIRST] [RESTART]`
- 输入：首次训练和续训产生的两个 `loss.out`；默认分别为 `loss.out` 和
  `restart/loss.out`。
- 处理：默认将续训步数加上首次训练最后一个步数；`--offset` 可显式指定偏移。
- 输出：默认 `loss_merged.out`；输出已存在时拒绝覆盖。

## `tcct gpumd plot-nep-evaluation [DIR]`

- 输入：自动扫描 `loss.out`，以及 `energy/force/stress/virial` 对应的 `_train.out`
  和 `_test.out`；每个文件独立绘图，不要求 loss、energy、force 或 train、test
  成对出现。
- 目录中只有训练文件时也会生成图，但 JSON 和终端会明确标记为“只有训练集误差”；
  发现任何测试文件时，测试集才会标记为主要验证证据。
- 统计：记录各 loss 列的首末值和范围；对完整预测数组分别计算 RMSE、MAE 和 R2；
  不同属性及 train/test 不混合统计。
- 绘图：小数据画散点，大于 `--density-threshold` 的面板画二维密度；散点抽样只影响
  显示，不影响指标。
- 输出：默认 `nep_evaluation.png` 和 `nep_evaluation_metrics.json`，已存在时拒绝覆盖。

```bash
tcct gpumd plot-nep-evaluation ./nep_results
tcct gpumd plot-nep-evaluation ./nep_results \
  --output test_parity.png --metrics test_metrics.json
```

## 依赖

`thermo` 统计和 `merge-loss` 仅依赖 numpy；`plot-nep-evaluation` 需要 matplotlib。

## 参考

- [GPUMD thermo.out](https://gpumd.org/gpumd/output_files/thermo_out.html)
- [GPUMD dump_thermo](https://gpumd.org/gpumd/input_parameters/dump_thermo.html)
- [GPUMD train.xyz and test.xyz](https://gpumd.org/nep/input_files/train_test_xyz.html)
- [GPUMDkit plotting scripts](https://zhyan0603.github.io/GPUMDkit/htmls/plot_scripts.html)
