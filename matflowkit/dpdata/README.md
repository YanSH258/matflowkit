# dpdata

基于 dpdata / ASE 的通用结构与标注数据格式转换、数据集重叠检查。
每个命令的详细参数见 `mfk dpdata <命令> -h`。

## `mfk dpdata convert INPUT OUTPUT --from FMT --to FMT`
- 对 dpdata 支持的标注数据格式执行单一格式转换（如
  `deepmd/npy`、`extxyz`、`cp2kdata/md`、`abacus/scf` 等）。
- `dpdata` 是可选依赖，缺失时给出安装命令。
- 输出已存在时拒绝覆盖。

## `mfk dpdata xyz-to-deepmd [INPUT] [OUTPUT]`
- 输入：带 `Lattice`、`energy`、`force`（可选 `virial`）标注的 GPUMD/extxyz；
  默认 `train.xyz`。
- 解析：使用 `dpdata.MultiSystems`，允许输入中存在多种化学组成。
- 输出：默认写入 `deepmd/`，按精确组成分 system，同时生成 DeepMD raw 与 NPY；
  `--set-size` 控制 NPY 分片大小。
- 输出目录已存在且非空时拒绝覆盖；dpdata 缺失或解析失败时写 stderr 并非零退出。

## `mfk dpdata overlap REFERENCE CANDIDATE`
- 输入：ASE 可读取的两个单帧或多帧结构数据集。
- 比较：元素、PBC、晶胞和坐标按指定小数位规范化后计算哈希；可选忽略原子顺序和 wrap。
- 输出：JSON 汇总与匹配帧 CSV；只判断规范化重复，不代表近似结构相似度。

## 依赖

`convert` / `xyz-to-deepmd` 需要 dpdata；`overlap` 需要 ASE。均为延迟导入。
