# VASP

## `tck vasp outcar-to-deepmd [ROOT] [OUTPUT]`

- 输入：单个 `OUTCAR`，或 ROOT 下由 `--pattern` 找到的一批 `OUTCAR`。
- 解析：使用 dpdata 官方 `vasp/outcar` 格式；默认只保留 dpdata 判定为已收敛的帧。
- 标签：要求 energy、force，默认也要求 virial；可用 `--no-virial` 放宽。
- 输出：按精确组成拆分的 `deepmd_npy/`、解析审计、逐帧 manifest、系统汇总、
  环境摘要和 SHA256。
- 验证：写出后用 dpdata 以 `deepmd/npy` 回读，核对帧数、有限值和 type map。
- `--frames final`：每个 OUTCAR 只写最后一个有效帧。

```bash
tck vasp outcar-to-deepmd ./vasp_tasks ./vasp_dataset
tck vasp outcar-to-deepmd ./OUTCAR ./vasp_dataset --frames final
```

边界：本命令不检查不同任务的 INCAR、KPOINTS、POTCAR、泛函或截断能是否一致；
转换通过不代表这些标签可以安全合并训练。

格式依据：[dpdata Supported Formats](https://docs.deepmodeling.com/projects/dpdata/en/latest/formats.html)
和 [VASP parser API](https://docs.deepmodeling.com/projects/dpdata/en/latest/api/dpdata.formats.vasp.html)。
