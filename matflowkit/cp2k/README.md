# CP2K

`singlepoint-to-deepmd` 处理多个独立单点任务；`aimd-to-deepmd` 处理一个 CP2K
原生 AIMD 轨迹，两者不混用。

CP2K 输出的批量审计、单点数据收集与 AIMD 数据提取。每个命令的详细参数见
`mfk cp2k <命令> -h`。

## `mfk cp2k audit [ROOT]`
- 输入：单个 CP2K 输出或根目录；默认递归查找 `**/output.log`。
- 判断：正常结束、所有 SCF 收敛、最终能量、原子力块和晶胞是否齐全。
- 输出：默认在当前目录生成 `cp2k_audit.csv` 和 `cp2k_audit.json`，终端显示任务数、
  通过数和未完成数；`PROGRAM ENDED AT` 本身不是通过的充分条件。

## `mfk cp2k singlepoint-to-deepmd [ROOT] [OUTPUT]`
- 输入：每个输出目录中的 CP2K 单点 `output.log` 与对应单帧 `structure.xyz`。
- 输出：按精确组成拆分的 DeepMD NPY、任务审计、frame manifest 和校验报告；不再
  额外生成 extxyz。
- 边界：不从 GEO_OPT 日志重建末态，不推断缺失标签，也不自动验证 DFT 方法一致性。

```bash
mfk cp2k singlepoint-to-deepmd ./single_points ./cp2k_dataset
```

## `mfk cp2k aimd-to-deepmd [ROOT] [OUTPUT]`

- 输入：一个完整 CP2K AIMD 目录，默认读取 `output.log`，并要求存在对应的
  `*-pos-*.xyz`、`*-frc-*.xyz`、`*.cell` 和 `*.ener`。
- 解析：使用 dpdata 的 `cp2kdata/md` 插件；`--log-name` 可修改标准输出文件名，
  restart 续算使用 `--restart`。CP2K 中多个 KIND 属于同一元素时按真实元素符号合并。
- 审计：要求 CP2K 正常结束、没有未收敛 SCF，且收敛 SCF 数不少于输出帧数；
  拒绝 NaN/Inf 和零帧数据。
- 输出：`deepmd_npy/<composition>/`、逐帧统计、源文件哈希、JSON 汇总和输出文件
  哈希。位力存在时写入 `virial.npy`；不存在时不猜测。
- 验证：生成后重新读取 DeepMD NPY，检查帧数、原子数、元素映射、数值和标签。
- 终端默认只显示关键结果；`--json` 可打印完整机器可读汇总。
- 输出目录已存在时拒绝覆盖。

```bash
mfk cp2k aimd-to-deepmd ./aimd ./cp2k_aimd_dataset
```

## 依赖

cp2kdata 已随 MatFlowKit 默认安装；AIMD 转换无需再单独补装解析器：

```bash
uv sync
```

参考：[dpdata CP2K AIMD 格式](https://docs.deepmodeling.com/projects/dpdata/en/master/formats/CP2KAIMDOutputFormat.html)、
[CP2KData 的 dpdata 插件](https://robinzyb.github.io/cp2kdata/docs/dpdata_plugin.html)。
