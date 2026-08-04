#!/usr/bin/env bash
# abacus_to_deepmd.sh — 示例流程：ABACUS 计算结果 -> DeePMD 训练数据检查
#
# 流程：
#   1. 批量审计 ABACUS 任务
#   2. 使用 dpdata 转成 DeepMD NPY
#   3. 核对数据集规模与能量/力范围
#
# 用法: bash abacus_to_deepmd.sh TASK_ROOT OUTPUT_DIR

set -euo pipefail

TASK_ROOT="${1:-.}"
DATA_DIR="${2:-./deepmd_data}"

echo "== 步骤 1: 审计 ABACUS 任务 =="
tck abacus audit "$TASK_ROOT" --strict

echo
echo "== 步骤 2: 转换为 DeepMD NPY =="
tck abacus to-deepmd "$TASK_ROOT" "$DATA_DIR"

echo
echo "== 步骤 3: 检查数据集 =="
tck deepmd stat "$DATA_DIR/deepmd_npy"
