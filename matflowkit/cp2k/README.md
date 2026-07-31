# CP2K

dpdata 官方同时提供 `cp2k/output` 和 `cp2k/aimd_output`。当前 `collect` 的范围仍是
MatFlowKit 已验证的单点 `output.log + structure.xyz`，不把 AIMD 目录混入同一入口。

CP2K 输出的批量审计与单点数据收集。每个命令的详细参数见 `mfk cp2k <命令> -h`。

## `mfk cp2k audit [ROOT]`
- 输入：单个 CP2K 输出或根目录；默认递归查找 `**/output.log`。
- 判断：正常结束、所有 SCF 收敛、最终能量、原子力块和晶胞是否齐全。
- 输出：逐任务 CSV 和 JSON 汇总；`PROGRAM ENDED AT` 本身不是通过的充分条件。

## `mfk cp2k collect [ROOT] [OUTPUT]`
- 输入：每个输出目录中的 CP2K 单点 `output.log` 与对应单帧 `structure.xyz`。
- 输出：按精确组成拆分的 DeepMD NPY、extxyz、任务审计、frame manifest 和校验报告。
- 边界：不从 GEO_OPT 日志重建末态，不推断缺失标签，也不自动验证 DFT 方法一致性。

## 依赖

硬依赖仅 typer + numpy；`cp2k/parser.py` 为自实现解析器，不依赖 cp2k 官方工具。
