# Changelog

## 0.4.0 — 2026-08-01

### 新增

- `mfk gpumd plot-nep-evaluation`：分别统计和绘制 NEP 训练集、独立测试集的
  energy/force/stress 或 virial 预测误差，并对大数据自动使用密度图。
- `mfk deepmd split`：使用固定 seed 的 random 或 uniform 方法划分 DeepMD NPY，
  输出逐帧 manifest、校验值并进行 NPY 回读验证。
- DeepMD 数据集报告可选全帧 PBC 最小原子距离、逐元素对最小距离和阈值计数；
  大型数据集默认不运行该耗时检查。
- `mfk cp2k aimd-to-deepmd`：使用 dpdata + CP2KData 将原生 CP2K AIMD
  位置、力、能量、晶胞和可用位力转换为经过回读验证的 DeepMD NPY。
- `mfk doctor`：检查 MatFlowKit 版本、可选依赖和 ABACUS 赝势/轨道目录。
- `mfk abacus report`：输出 ABACUS 批量任务的 HTML、JSON、CSV 和 PNG 报告。
- Structure 转换支持 CIF、POSCAR、Extended XYZ 输入，并可输出 CIF、POSCAR、
  Extended XYZ 或带资源绝对路径的 ABACUS STRU。
- GitHub Actions 自动测试 Python 3.9/3.12、CLI 入口、源码包和 wheel。
- ABACUS、CP2K、VASP、DeepMD 的仓库外真实样例回归测试入口。

### 调整

- `mfk gpumd plot-nep-evaluation` 改为自动扫描已有的 train/test energy、force、
  stress 和 virial 文件，每个文件可独立绘图。
- CLI 与交互菜单改为共用一个命令注册表。
- ABACUS 审计会列出缺少的完成证据，不再只写笼统的“完成证据不完整”。
- 主菜单按 Structure、ABACUS、CP2K、VASP、dpdata、DeepMD、GPUMD、DPA4、System
  排列，并直接显示每个模块的用途。
- `mfk cp2k collect` 改为 `mfk cp2k singlepoint-to-deepmd`，只输出 DeepMD NPY。
- `mfk vasp to-deepmd` 改为 `mfk vasp outcar-to-deepmd`。
- `mfk gpumd from-deepmd` 改为 `mfk gpumd npy-to-xyz`。
- 交互式 `dpdata convert` 可通过编号选择常用格式。
- CP2KData 改为默认依赖，普通 `uv sync` 即可使用 CP2K AIMD 转换。

### 验证

- 快速测试：74 项通过。
- 真实样例：ABACUS 报告、4 个 CP2K 单点审计、CP2K AIMD 转 DeepMD、VASP OUTCAR
  转 DeepMD、DeepMD 数据集报告全部通过。
