"""
测试认证和WebSocket连接的脚本
使用方法：python backend/test_auth_websocket.py
"""
import asyncio
import aiohttp
import json
from aiohttp import ClientSession

# 测试配置
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/api/ws"

async def test_auth_and_websocket():
    """测试认证流程和WebSocket连接"""
    
    print("=" * 50)
    print("开始测试认证和WebSocket连接")
    print("=" * 50)
    
    async with ClientSession() as session:
        # 1. 测试主页访问
        print("\n1. 测试主页访问...")
        async with session.get(f"{BASE_URL}/") as resp:
            print(f"   状态码: {resp.status}")
            if resp.status == 200:
                print("   ✓ 主页访问成功")
            else:
                print("   ✗ 主页访问失败")
        
        # 2. 测试登录重定向
        print("\n2. 测试OAuth登录重定向...")
        async with session.get(f"{BASE_URL}/api/login/linuxdo", allow_redirects=False) as resp:
            print(f"   状态码: {resp.status}")
            if resp.status == 302:
                location = resp.headers.get('Location')
                print(f"   重定向到: {location[:50]}...")
                print("   ✓ OAuth重定向正常")
            else:
                print("   ✗ OAuth重定向失败")
        
        # 3. 检查cookie设置（需要实际登录）
        print("\n3. Cookie检查")
        print("   注意: 完整的认证测试需要通过浏览器进行实际的OAuth登录")
        print("   请在浏览器中：")
        print("   1) 访问 http://localhost:8000")
        print("   2) 点击登录按钮")
        print("   3) 完成LinuxDo OAuth认证")
        print("   4) 检查浏览器控制台是否有WebSocket连接错误")
        
        # 4. 测试未认证的WebSocket连接（应该失败）
        print("\n4. 测试未认证的WebSocket连接（预期失败）...")
        try:
            async with session.ws_connect(WS_URL) as ws:
                print("   ✗ 未认证连接不应该成功")
        except Exception as e:
            print(f"   ✓ 未认证连接被正确拒绝: {str(e)[:50]}...")

async def test_with_manual_token():
    """使用手动提供的token测试WebSocket连接"""
    print("\n" + "=" * 50)
    print("手动Token测试")
    print("=" * 50)
    print("\n如果你已经登录并获得了token，可以在这里测试：")
    print("1. 在浏览器开发者工具中查看Cookie")
    print("2. 找到名为'token'的cookie值")
    print("3. 将值复制到下面的TOKEN变量中")
    
    TOKEN = ""  # 在这里粘贴你的token
    
    if TOKEN:
        headers = {"Cookie": f"token={TOKEN}"}
        async with ClientSession() as session:
            try:
                async with session.ws_connect(WS_URL, headers=headers) as ws:
                    print("✓ WebSocket连接成功！")
                    
                    # 发送测试消息
                    await ws.send_json({"action": "test"})
                    
                    # 等待响应
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            print(f"收到消息: {data}")
                            break
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            print(f"WebSocket错误: {ws.exception()}")
                            break
            except Exception as e:
                print(f"✗ WebSocket连接失败: {e}")
    else:
        print("跳过手动token测试（未提供token）")

async def main():
    """主测试函数"""
    try:
        await test_auth_and_websocket()
        await test_with_manual_token()
        
        print("\n" + "=" * 50)
        print("测试总结")
        print("=" * 50)
        print("\n修复内容：")
        print("1. ✓ Cookie SameSite属性调整（HTTP环境不设置SameSite）")
        print("2. ✓ WebSocket认证错误处理改进")
        print("3. ✓ 添加详细的日志记录")
        print("\n请通过浏览器进行完整的登录测试以验证修复效果。")
        print("查看后端日志以获取更多调试信息。")
        
    except Exception as e:
        print(f"\n测试过程中出错: {e}")

if __name__ == "__main__":
    print("WebSocket认证测试工具")
    print("确保后端服务正在运行在 http://localhost:8000")
    asyncio.run(main())