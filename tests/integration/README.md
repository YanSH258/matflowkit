# Real-sample regression tests

这些测试读取仓库外保留的真实计算输出，不复制或修改原始文件，结果写入 pytest 临时目录。
普通 `pytest` 在没有指定样例目录时会跳过它们。

当前样例根目录为 `/home/yan/脚本整理`，运行：

```bash
MFK_REAL_SAMPLE_ROOT=/home/yan/脚本整理 uv run pytest tests/integration -q
```

覆盖范围：

- ABACUS：真实 SCF 任务生成报告；
- CP2K：4 个 352 原子单点输出审计；
- VASP：真实 Cu OUTCAR 转换为 DeepMD NPY；
- DeepMD：对上述真实转换数据生成数据集报告。

更换样例后应同步更新测试中的预期任务数、帧数和元素，不根据文件名猜测结果。
