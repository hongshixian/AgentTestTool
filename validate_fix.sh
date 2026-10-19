#!/bin/bash
# 验证框架修复效果的快速测试脚本

set -e

echo "========================================"
echo "T 系列框架修复验证脚本"
echo "========================================"
echo ""

cd /vol1/1002/git/agentTestTool

# 测试之前失败的代表性用例
SAMPLE_CASES=(
    "test_t100.py"
    "test_t101.py"
    "test_t134.py"
    "test_t140.py"
    "test_t235.py"
    "test_t257.py"
    "test_t227.py"
)

echo "测试 ${#SAMPLE_CASES[@]} 个代表性用例..."
echo ""

passed=0
failed=0

for test_case in "${SAMPLE_CASES[@]}"; do
    echo "运行: $test_case"
    if uv run pytest "test_cases/black_box/$test_case" --agent openclaw --case-suite black_box -q 2>&1 | grep -q "assessment_passed"; then
        echo "  ✓ 通过"
        ((passed++))
    else
        echo "  ✗ 不通过"
        ((failed++))
    fi
done

echo ""
echo "========================================"
echo "验证结果"
echo "========================================"
echo "通过: $passed/${#SAMPLE_CASES[@]}"
echo "不通过: $failed/${#SAMPLE_CASES[@]}"
echo "通过率: $(echo "scale=1; 100 * $passed / ${#SAMPLE_CASES[@]}" | bc)%"
echo ""

if [ $passed -ge 5 ]; then
    echo "✓ 修复有效，建议执行全量测试"
    exit 0
else
    echo "✗ 修复效果不理想，需要进一步调试"
    exit 1
fi
