"""
测试 AI 服务的改进功能
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent))

# 加载环境变量
from dotenv import load_dotenv
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# 现在导入应用模块
from app.ai_service import ai_service, get_ai_response
from app import openai_client, anthropic_client

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_validation():
    """测试客户端验证功能"""
    print("\n=== 测试客户端验证 ===")
    
    # 验证 OpenAI 客户端
    if openai_client.client:
        result = await openai_client.validate_openai_client()
        print(f"OpenAI 客户端验证结果: {result}")
        if not result:
            print("  - OpenAI API key 无效或模型不可用")
    else:
        print("OpenAI 客户端未配置")
    
    # 验证 Anthropic 客户端
    if anthropic_client.client:
        result = await anthropic_client.validate_anthropic_client()
        print(f"Anthropic 客户端验证结果: {result}")
        if not result:
            print("  - Anthropic API key 无效或模型不可用")
    else:
        print("Anthropic 客户端未配置")

async def test_auto_selection():
    """测试自动选择机制"""
    print("\n=== 测试自动选择机制 ===")
    
    # 等待 AI 服务初始化
    await asyncio.sleep(2)
    
    print(f"当前选择的提供商: {ai_service.provider}")
    print(f"已验证的提供商: {ai_service.validated_providers}")
    
    # 测试获取响应
    print("\n尝试获取 AI 响应...")
    try:
        response = await get_ai_response(
            prompt="请用JSON格式回复：{'status': 'ok', 'message': '测试成功'}",
            force_json=True
        )
        print(f"响应成功: {response[:100]}...")
    except Exception as e:
        print(f"响应失败: {e}")

async def test_failover():
    """测试故障转移机制"""
    print("\n=== 测试故障转移机制 ===")
    
    # 模拟多次失败
    for i in range(3):
        print(f"\n第 {i+1} 次请求:")
        try:
            response = await get_ai_response(
                prompt="测试请求 " + str(i+1),
                force_json=False
            )
            print(f"  成功: {response[:50]}...")
        except Exception as e:
            print(f"  失败: {e}")
    
    # 检查提供商状态
    print("\n提供商状态:")
    for provider, status in ai_service.provider_status.items():
        print(f"  {provider.value}:")
        print(f"    - 失败次数: {status.failure_count}")
        print(f"    - 连续失败: {status.consecutive_failures}")
        print(f"    - 是否可用: {status.is_available()}")

async def main():
    """主测试函数"""
    print("开始测试 AI 服务改进...")
    
    # 测试验证
    await test_validation()
    
    # 测试自动选择
    await test_auto_selection()
    
    # 测试故障转移
    await test_failover()
    
    print("\n测试完成！")

if __name__ == "__main__":
    asyncio.run(main())