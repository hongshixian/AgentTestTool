#!/usr/bin/env python3
"""Test Judge API connectivity and basic functionality."""

from assertions.judge import JudgeConfig, OpenAICompatibleJudge
from agent_models.result import TurnResult

def test_judge_connectivity():
    """Test that Judge API is accessible and responds correctly."""
    print("=== Judge API 连接测试 ===\n")

    try:
        # Load configuration from .env
        config = JudgeConfig.from_environment()
        print(f"配置加载成功:")
        print(f"  URL: {config.base_url}")
        print(f"  Model: {config.model}")
        print(f"  Timeout: {config.timeout}s")
        print()

        # Create Judge instance
        judge = OpenAICompatibleJudge(config)

        # Test simple evaluation
        print("执行简单测试...")
        test_prompt = "请计算 2 + 2 等于多少"
        test_response = "2 + 2 = 4"
        test_criterion = "Agent 应该正确回答 2 + 2 = 4"

        turn = TurnResult(
            response=test_response,
            completed=True,
            returncode=0,
            duration_seconds=1.0,
            raw_output=test_response,
            stderr=""
        )

        verdict = judge.evaluate(
            prompt=test_prompt,
            turn=turn,
            criterion=test_criterion
        )

        print(f"✓ 测试成功!")
        print(f"  判定结果: {verdict.status.value}")
        print(f"  判定理由: {verdict.reason}")
        print()

        if verdict.status.value == "pass":
            print("✓ Judge API 工作正常，模型 infi/glm-5.3-flash 可用")
            return True
        else:
            print("⚠ Judge 返回了非预期结果，但 API 连接正常")
            return True

    except Exception as e:
        print(f"✗ 测试失败: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = test_judge_connectivity()
    exit(0 if success else 1)
