# structure

单个周期结构的轻量级格式转换。pymatgen 负责可靠展开 CIF 空间群，ASE/dpdata
负责输出 Extended XYZ、VASP POSCAR 或 ABACUS STRU。

## `mfk structure convert CIF --to FORMAT`

- 输入：一个包含完整三维晶胞、单个结构且原子完全占位的 CIF。
- `--to xyz`：输出 `<文件名>.xyz`，实际内容为包含 `Lattice` 和 `pbc` 的
  Extended XYZ，不写普通 XYZ。
- `--to poscar`：输出 `<文件名>.vasp`，采用 VASP 5 POSCAR 格式和分数坐标。
- `--to stru`：输出 `<文件名>.STRU`。默认从 `ABACUS_PP_PATH` 按
  `element.json` 查找赝势；没有映射文件时只接受每个元素唯一匹配的 `.upf`。
- `--basis lcao`：除赝势外，从 `ABACUS_ORB_PATH` 查找配套 `.orb`；默认 `pw`
  不写 `NUMERICAL_ORBITAL`。
- `--pp-dir` / `--orb-dir`：临时切换资源库，不修改全局配置。
- 转为 STRU 时同时生成单点 SCF 使用的 `INPUT`；默认在 INPUT 中直接引用资源库，
  不创建软链接。`--copy-files` 会复制赝势和轨道，并把目录改为当前目录。
- `INPUT` 的 `ecutwfc` 默认取赝势库 `ecutwfc.json` 和轨道文件头中的最大推荐值；
  无推荐值时必须使用 `--ecutwfc` 指定。
- LCAO 单点模板使用 Gamma 点，PW 模板使用 `kspacing 0.2`；正式计算前仍需按体系
  检查 k 点、磁性和收敛参数。
- `--output/-o`：覆盖默认输出文件名。已有文件不会覆盖。
- 默认只打印输出路径和校验摘要；`--json` 输出完整校验、赝势和轨道文件记录。

每次转换完成后都会重新读取输出，核对元素、原子数、PBC、晶格度量、体积和分数坐标。
多结构 CIF、部分占位、缺失/歧义赝势以及回读不一致都会以非零退出码停止。

```bash
mfk structure convert Al.cif --to xyz
mfk structure convert Al.cif --to poscar --output POSCAR
mfk structure convert Al.cif --to stru --output STRU
mfk structure convert Al.cif --to stru --basis lcao --copy-files
```

格式转换不会判断某套赝势是否适合具体研究。续接已有计算或机器学习数据时，应使用原项目
完全相同的赝势文件；使用 `--json` 可记录文件名和 SHA-256。
