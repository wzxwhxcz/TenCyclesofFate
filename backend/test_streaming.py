"""
测试流式输出功能
"""
import asyncio
import logging
from app.ai_service import get_ai_response_stream
from app.config import settings

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_streaming():
    """测试流式输出"""
    print("=" * 50)
    print("测试流式输出功能")
    print(f"当前配置: ENABLE_STREAMING = {settings.ENABLE_STREAMING}")
    print(f"AI提供商: {settings.AI_PROVIDER}")
    print("=" * 50)
    
    # 测试提示
    test_prompt = "请用JSON格式返回一个简单的游戏状态，包含narrative和state_update字段"
    
    # 测试历史
    test_history = [
        {"role": "system", "content": "你是一个游戏主持人"},
        {"role": "user", "content": "开始游戏"}
    ]
    
    print("\n开始流式输出测试...")
    print("-" * 30)
    
    full_response = ""
    chunk_count = 0
    
    try:
        async for chunk in get_ai_response_stream(
            prompt=test_prompt,
            history=test_history,
            force_json=True
        ):
            chunk_count += 1
            full_response += chunk
            # 打印每个数据块（为了演示效果）
            print(f"[Chunk {chunk_count}]: {chunk}", end="", flush=True)
        
        print("\n" + "-" * 30)
        print(f"\n流式输出完成!")
        print(f"总共接收到 {chunk_count} 个数据块")
        print(f"完整响应长度: {len(full_response)} 字符")
        
        # 验证JSON格式
        import json
        try:
            # 提取JSON部分
            if "```json" in full_response:
                start = full_response.find("```json") + 7
                end = full_response.find("```", start)
                json_str = full_response[start:end].strip()
            else:
                start = full_response.find("{")
                end = full_response.rfind("}") + 1
                json_str = full_response[start:end]
            
            parsed = json.loads(json_str)
            print("\n✅ JSON格式验证成功!")
            print(f"解析的JSON包含字段: {list(parsed.keys())}")
        except json.JSONDecodeError as e:
            print(f"\n❌ JSON格式验证失败: {e}")
            print(f"原始响应: {full_response[:200]}...")
            
    except Exception as e:
        print(f"\n❌ 流式输出测试失败: {e}")
        logger.error(f"错误详情: {e}", exc_info=True)

async def test_normal_response():
    """测试普通（非流式）响应作为对比"""
    print("\n" + "=" * 50)
    print("测试普通响应（非流式）")
    print("=" * 50)
    
    from app.ai_service import get_ai_response
    
    test_prompt = "请用JSON格式返回一个简单的游戏状态，包含narrative和state_update字段"
    test_history = [
        {"role": "system", "content": "你是一个游戏主持人"},
        {"role": "user", "content": "开始游戏"}
    ]
    
    try:
        print("\n开始普通响应测试...")
        response = await get_ai_response(
            prompt=test_prompt,
            history=test_history,
            force_json=True
        )
        
        print(f"响应长度: {len(response)} 字符")
        print(f"响应预览: {response[:200]}...")
        print("\n✅ 普通响应测试成功!")
        
    except Exception as e:
        print(f"\n❌ 普通响应测试失败: {e}")
        logger.error(f"错误详情: {e}", exc_info=True)

async def main():
    """主测试函数"""
    print("\n🚀 开始AI服务流式输出测试\n")
    
    # 测试流式输出
    await test_streaming()
    
    # 等待一下
    await asyncio.sleep(2)
    
    # 测试普通响应作为对比
    await test_normal_response()
    
    print("\n" + "=" * 50)
    print("✨ 所有测试完成!")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())