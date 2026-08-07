# 常用数据流程

## 检查并收集 ABACUS 任务

```bash
tcct abacus audit ./tasks --expected 120 --strict
tcct abacus to-deepmd ./tasks ./dataset_v1 \
  --expected 120 \
  --type-map "Ca Mg P O H"
```

输出目录里会有按组成拆分的 NPY、任务记录、帧记录和校验值。

## 合并数据集

```bash
tcct deepmd merge relaxation_data strain_data \
  --output combined_data
```

不同组成仍放在不同 system 中。发现完全重复的结构时命令会停止；确认需要保留时再加
`--allow-duplicates`。

## 转换格式

```bash
tcct dpdata convert work training_data \
  --from cp2kdata/md --to deepmd/npy

tcct dpdata convert training_data train.xyz \
  --from deepmd/npy --to extxyz
```
