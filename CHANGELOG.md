# Changelog

## 0.4.0 — 2026-08-01

### 新增

- `mfk cp2k aimd-to-deepmd`：使用 dpdata + CP2KData 将原生 CP2K AIMD
  位置、力、能量、晶胞和可用位力转换为经过回读验证的 DeepMD NPY 和
  GPUMD/NEP `train.xyz`。
- `mfk doctor`：检查 MatFlowKit 版本、可选依赖和 ABACUS 赝势/轨道目录。
- `mfk abacus report`：输出 ABACUS 批量任务的 HTML、JSON、CSV 和 PNG 报告。
- Structure 转换支持 CIF、POSCAR、Extended XYZ 输入，并可输出 CIF、POSCAR、
  Extended XYZ 或带资源绝对路径的 ABACUS STRU。
- GitHub Actions 自动测试 Python 3.9/3.12、CLI 入口、源码包和 wheel。
- ABACUS、CP2K、VASP、DeepMD 的仓库外真实样例回归测试入口。

### 调整

- CLI 与交互菜单改为共用一个命令注册表。
- ABACUS 审计会列出缺少的完成证据，不再只写笼统的“完成证据不完整”。

### 验证

- 快速测试：66 项通过。
- 真实样例：ABACUS 报告、4 个 CP2K 单点审计、VASP OUTCAR 转 DeepMD、
  DeepMD 数据集报告全部通过。
