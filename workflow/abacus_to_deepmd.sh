#!/usr/bin/env bash
# abacus_to_deepmd.sh — 示例流程：ABACUS 计算结果 -> DeePMD 训练数据检查
#
# 流程：
#   1. 对每个 ABACUS relax 目录检查收敛（mfk abacus check-relax）
#   2. 数据转成 DeePMD 格式后（转换本身由 dpdata 等外部工具完成，不在本脚本内），
#      用 mfk deepmd stat 核对数据集规模与能量/力范围
#
# 用法: bash abacus_to_deepmd.sh [relax_dir1 relax_dir2 ...] [deepmd_data_dir]

set -euo pipefail

RELAX_DIRS=("$@")
DATA_DIR="${DATA_DIR:-./deepmd_data}"

echo "== 步骤 1: 检查各 ABACUS relax 目录收敛情况 =="
for d in "${RELAX_DIRS[@]}"; do
    echo "--- $d"
    mfk abacus check-relax "$d" || echo "警告: $d 未通过检查，请人工确认后再纳入训练集"
done

echo
echo "== 步骤 2: 检查 DeePMD 数据集统计 =="
echo "（假设数据已转换到 $DATA_DIR）"
mfk deepmd stat "$DATA_DIR"

echo
echo "完成。如需程序化读取统计结果: mfk deepmd stat $DATA_DIR --json"
