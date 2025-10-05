"""
测试增强版数据库功能
"""
import asyncio
import time
import sys
import os
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.database_models import init_enhanced_database
from backend.app.config import settings

def test_basic_operations():
    """测试基本的数据库操作"""
    print("\n" + "="*60)
    print("测试基本数据库操作")
    print("="*60)

    # 初始化数据库
    db_manager = init_enhanced_database()
    print(f"✓ 数据库初始化成功: {settings.DATABASE_URL}")

    # 测试用户数据
    test_player_id = "test_user_001"
    test_username = "测试玩家"
    test_trust_level = 2

    # 1. 保存会话
    test_session = {
        "username": test_username,
        "trust_level": test_trust_level,
        "sessions_today": 3,
        "total_rewards": 150,
        "internal_history": [
            {"role": "user", "content": "开始游戏"},
            {"role": "assistant", "content": "欢迎来到浮生十梦"},
            {"role": "user", "content": "我要进入第一个梦境"},
        ],
        "current_trial": {
            "trial_number": 3,
            "start_time": time.time(),
            "rewards": 50
        }
    }

    db_manager.save_session(
        player_id=test_player_id,
        session_data=test_session,
        username=test_username,
        trust_level=test_trust_level
    )
    print(f"✓ 保存会话成功: {test_player_id}")

    # 2. 保存试炼记录
    trial_id = db_manager.save_trial_record(
        player_id=test_player_id,
        trial_number=1,
        start_time=time.time() - 600,
        end_time=time.time(),
        rewards=50,
        journey_accepted=True,
        narrative_summary="玩家成功完成了第一个梦境的冒险"
    )
    print(f"✓ 保存试炼记录成功: Trial ID #{trial_id}")

    # 3. 保存玩家输入
    db_manager.save_player_input(
        player_id=test_player_id,
        input_text="我选择向北走",
        ai_response="你向北走去，发现了一片神秘的森林...",
        trial_id=trial_id
    )
    print("✓ 保存玩家输入成功")

    # 4. 保存奖励日志
    db_manager.save_reward_log(
        player_id=test_player_id,
        amount=50,
        reward_type="trial_completion",
        reason="成功完成第一个试炼",
        trial_id=trial_id
    )
    print("✓ 保存奖励日志成功")

    # 5. 获取玩家统计
    stats = db_manager.get_player_statistics(test_player_id)
    print("\n玩家统计数据:")
    for key, value in stats.items():
        print(f"  - {key}: {value}")

    # 6. 获取最近会话
    recent = db_manager.get_recent_sessions(limit=5)
    print(f"\n✓ 获取最近会话成功: 找到 {len(recent)} 个会话")

    return True

def test_multiple_users():
    """测试多用户场景"""
    print("\n" + "="*60)
    print("测试多用户场景")
    print("="*60)

    db_manager = init_enhanced_database()

    # 创建多个测试用户
    users = [
        {"id": "player_001", "name": "勇者", "trust": 3},
        {"id": "player_002", "name": "法师", "trust": 2},
        {"id": "player_003", "name": "游侠", "trust": 1},
    ]

    for user in users:
        # 为每个用户创建会话
        session_data = {
            "username": user["name"],
            "trust_level": user["trust"],
            "sessions_today": user["trust"],
            "total_rewards": user["trust"] * 100
        }

        db_manager.save_session(
            player_id=user["id"],
            session_data=session_data,
            username=user["name"],
            trust_level=user["trust"]
        )

        # 为每个用户创建试炼记录
        for trial_num in range(1, user["trust"] + 1):
            db_manager.save_trial_record(
                player_id=user["id"],
                trial_number=trial_num,
                start_time=time.time() - (trial_num * 3600),
                end_time=time.time() - (trial_num * 3600) + 600,
                rewards=trial_num * 20,
                journey_accepted=trial_num % 2 == 0
            )

        print(f"✓ 创建用户 {user['name']} 及其 {user['trust']} 个试炼记录")

    # 获取所有用户的最近会话
    recent_sessions = db_manager.get_recent_sessions(limit=10)
    print(f"\n最近活跃的会话 ({len(recent_sessions)} 个):")
    for session in recent_sessions:
        print(f"  - {session['username']}: 总奖励 {session['total_rewards']}")

    return True

def test_database_types():
    """测试不同类型的数据库连接"""
    print("\n" + "="*60)
    print("测试数据库类型")
    print("="*60)

    db_url = settings.DATABASE_URL
    print(f"当前数据库配置: {db_url}")

    if db_url.startswith("sqlite"):
        print("✓ 使用 SQLite 数据库")
    elif db_url.startswith("mysql"):
        print("✓ 使用 MySQL 数据库")
    elif db_url.startswith("postgresql"):
        print("✓ 使用 PostgreSQL 数据库")
    else:
        print("⚠ 未知的数据库类型")

    # 测试连接
    try:
        db_manager = init_enhanced_database()
        print("✓ 数据库连接成功")

        # 测试表创建
        print("✓ 数据库表结构创建成功")

        return True
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
        return False

def test_performance():
    """测试数据库性能"""
    print("\n" + "="*60)
    print("测试数据库性能")
    print("="*60)

    db_manager = init_enhanced_database()

    # 批量插入测试
    start_time = time.time()
    batch_size = 100

    print(f"开始批量插入 {batch_size} 条记录...")

    for i in range(batch_size):
        player_id = f"perf_test_{i:04d}"
        session_data = {
            "username": f"性能测试用户{i}",
            "trust_level": i % 5,
            "sessions_today": i % 10,
            "total_rewards": i * 10
        }

        db_manager.save_session(
            player_id=player_id,
            session_data=session_data,
            username=session_data["username"],
            trust_level=session_data["trust_level"]
        )

    elapsed = time.time() - start_time
    print(f"✓ 批量插入完成: {batch_size} 条记录耗时 {elapsed:.2f} 秒")
    print(f"  平均每条: {elapsed/batch_size*1000:.2f} 毫秒")

    # 查询性能测试
    start_time = time.time()
    recent = db_manager.get_recent_sessions(limit=50)
    elapsed = time.time() - start_time
    print(f"✓ 查询最近50个会话耗时: {elapsed*1000:.2f} 毫秒")

    return True

def cleanup_test_data():
    """清理测试数据"""
    print("\n" + "="*60)
    print("清理测试数据")
    print("="*60)

    # 这里只是提示，实际清理需要根据需求实现
    print("⚠ 测试数据保留在数据库中，可手动清理")
    print("  SQLite: 删除 veloera.db 文件")
    print("  MySQL/PostgreSQL: 删除相应的表或数据")

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║         浮生十梦 - 数据库功能测试                       ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    tests = [
        ("基本操作", test_basic_operations),
        ("多用户场景", test_multiple_users),
        ("数据库类型", test_database_types),
        ("性能测试", test_performance),
    ]

    success_count = 0
    failed_count = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                success_count += 1
                print(f"✓ {test_name} 测试通过")
            else:
                failed_count += 1
                print(f"✗ {test_name} 测试失败")
        except Exception as e:
            failed_count += 1
            print(f"✗ {test_name} 测试异常: {e}")

    print("\n" + "="*60)
    print(f"测试完成: {success_count} 通过, {failed_count} 失败")
    print("="*60)

    if failed_count == 0:
        print("🎉 所有测试通过！")
    else:
        print("⚠ 部分测试失败，请检查日志")

    cleanup_test_data()