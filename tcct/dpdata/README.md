# dpdata

基于 dpdata / ASE 的通用结构与标注数据格式转换、数据集重叠检查。
每个命令的详细参数见 `tcct dpdata <命令> -h`。

这里处理的是带能量、力或位力的单帧/多帧数据。CIF、POSCAR、STRU 等不含训练标签的
单个周期结构使用 `tcct structure convert`。需要判断 ABACUS、CP2K 或 VASP 计算是否
完成、是否收敛时，使用对应软件模块的数据提取命令，而不是通用 `convert`。

## `tcct dpdata convert INPUT OUTPUT --from FMT --to FMT`
- 对 dpdata 支持的标注数据格式执行单一格式转换（如
  `deepmd/npy`、`extxyz`、`cp2kdata/md`、`abacus/scf` 等）。
- 交互菜单列出常用输入和输出格式，可直接输入编号；命令行仍使用 dpdata 的准确格式名。
- cp2kdata 随 TCCT 默认安装；其他格式支持范围以当前 dpdata 版本为准。
- 输出已存在时拒绝覆盖。

## `tcct dpdata xyz-to-deepmd [INPUT] [OUTPUT]`
- 输入：带 `Lattice`、`energy`、`force`（可选 `virial`）标注的 GPUMD/extxyz；
  默认 `train.xyz`。
- 解析：使用 `dpdata.MultiSystems`，允许输入中存在多种化学组成。
- virial：同一组成的帧全部有则写 `virial.npy`，全部没有则不写；部分帧缺失时在
  调用 dpdata 前报错，并列出该组成的总帧数、有/无 virial 数量和缺失帧编号。
- 输出：默认写入 `deepmd/`，按精确组成分 system，只生成 DeepMD NPY；
  `--set-size` 控制 NPY 分片大小。显式使用 `--raw` 时额外生成 DeepMD raw。
  NPY system 自身仍会包含必需的 `type.raw` 和 `type_map.raw`；默认省略的是
  `coord.raw`、`energy.raw`、`force.raw`、`box.raw`、`virial.raw` 等文本数组。
- 输出目录已存在且非空时拒绝覆盖；dpdata 缺失或解析失败时写 stderr 并非零退出。

## `tcct dpdata overlap REFERENCE CANDIDATE`
- 输入：ASE 可读取的两个单帧或多帧结构数据集。
- 比较：元素、PBC、晶胞和坐标按指定小数位规范化后计算哈希；可选忽略原子顺序和 wrap。
- 输出：JSON 汇总与匹配帧 CSV；只判断规范化重复，不代表近似结构相似度。

## 依赖

`convert` / `xyz-to-deepmd` 需要 dpdata；`overlap` 需要 ASE。均为延迟导入。
