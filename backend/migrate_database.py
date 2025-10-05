"""
数据库迁移脚本
将现有的数据从简单存储迁移到增强版数据库
"""
import json
import sqlite3
import time
import logging
from pathlib import Path
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.config import settings
from backend.app.database_models import init_enhanced_database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_from_json():
    """从JSON文件迁移数据"""
    json_path = Path("game_data.json")

    if not json_path.exists():
        logger.info("No JSON file found to migrate")
        return False

    logger.info(f"Found JSON file: {json_path}")

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            sessions = json.load(f)

        logger.info(f"Loaded {len(sessions)} sessions from JSON")
        return sessions

    except Exception as e:
        logger.error(f"Failed to load JSON file: {e}")
        return None

def migrate_from_old_database():
    """从旧的SQLite数据库迁移数据"""
    old_db_path = "./veloera.db"

    if not Path(old_db_path).exists():
        logger.info("No old database found to migrate")
        return None

    logger.info(f"Found old database: {old_db_path}")

    try:
        conn = sqlite3.connect(old_db_path)
        cursor = conn.cursor()

        # 检查是否有game_sessions表
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='game_sessions'
        """)

        if not cursor.fetchone():
            logger.info("No game_sessions table in old database")
            conn.close()
            return None

        # 读取所有会话数据
        cursor.execute("""
            SELECT player_id, session_data, last_modified, created_at
            FROM game_sessions
        """)

        rows = cursor.fetchall()
        sessions = {}

        for player_id, session_data_json, last_modified, created_at in rows:
            try:
                session_data = json.loads(session_data_json)
                session_data["last_modified"] = last_modified
                session_data["created_at"] = created_at
                sessions[player_id] = session_data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse session for {player_id}: {e}")

        conn.close()
        logger.info(f"Loaded {len(sessions)} sessions from old database")
        return sessions

    except Exception as e:
        logger.error(f"Failed to load old database: {e}")
        return None

def perform_migration():
    """执行数据迁移"""
    logger.info("=" * 60)
    logger.info("Starting database migration")
    logger.info("=" * 60)

    # 初始化增强版数据库
    logger.info("Initializing enhanced database...")
    db_manager = init_enhanced_database()

    # 收集所有需要迁移的数据
    all_sessions = {}

    # 1. 尝试从JSON迁移
    json_sessions = migrate_from_json()
    if json_sessions:
        all_sessions.update(json_sessions)
        logger.info(f"Added {len(json_sessions)} sessions from JSON")

    # 2. 尝试从旧数据库迁移
    db_sessions = migrate_from_old_database()
    if db_sessions:
        # 合并数据，旧数据库的数据优先级更高
        for player_id, session_data in db_sessions.items():
            if player_id in all_sessions:
                # 比较时间戳，保留更新的
                old_time = all_sessions[player_id].get("last_modified", 0)
                new_time = session_data.get("last_modified", 0)
                if new_time > old_time:
                    all_sessions[player_id] = session_data
            else:
                all_sessions[player_id] = session_data
        logger.info(f"Added/updated {len(db_sessions)} sessions from old database")

    if not all_sessions:
        logger.info("No data to migrate")
        return

    # 3. 迁移到增强版数据库
    logger.info(f"Migrating {len(all_sessions)} total sessions to enhanced database...")

    success_count = 0
    error_count = 0

    for player_id, session_data in all_sessions.items():
        try:
            # 提取信息
            username = session_data.get("username", player_id)
            trust_level = session_data.get("trust_level", 0)

            # 保存到新数据库
            db_manager.save_session(
                player_id=player_id,
                session_data=session_data,
                username=username,
                trust_level=trust_level
            )

            # 如果有试炼数据，也迁移
            if "sessions_today" in session_data:
                sessions_today = session_data["sessions_today"]
                for i in range(sessions_today):
                    # 创建试炼记录（使用估算的时间）
                    db_manager.save_trial_record(
                        player_id=player_id,
                        trial_number=i + 1,
                        start_time=time.time() - (10 - i) * 3600,  # 估算时间
                        end_time=time.time() - (10 - i) * 3600 + 600,
                        rewards=0  # 无法恢复具体奖励
                    )

            success_count += 1

            if success_count % 10 == 0:
                logger.info(f"Progress: {success_count}/{len(all_sessions)}")

        except Exception as e:
            logger.error(f"Failed to migrate session for {player_id}: {e}")
            error_count += 1

    logger.info("=" * 60)
    logger.info(f"Migration completed!")
    logger.info(f"Success: {success_count} sessions")
    logger.info(f"Errors: {error_count} sessions")
    logger.info("=" * 60)

    # 备份旧文件
    if json_sessions:
        json_path = Path("game_data.json")
        backup_name = f"game_data.json.backup.{int(time.time())}"
        json_path.rename(backup_name)
        logger.info(f"JSON file backed up as: {backup_name}")

    if db_sessions:
        old_db_path = Path("./veloera.db")
        backup_name = f"veloera.db.backup.{int(time.time())}"
        old_db_path.rename(backup_name)
        logger.info(f"Old database backed up as: {backup_name}")

def verify_migration():
    """验证迁移结果"""
    logger.info("\nVerifying migration...")

    db_manager = init_enhanced_database()
    recent_sessions = db_manager.get_recent_sessions(limit=5)

    if recent_sessions:
        logger.info(f"Successfully found {len(recent_sessions)} recent sessions:")
        for session in recent_sessions:
            logger.info(f"  - Player: {session['username']}, Rewards: {session['total_rewards']}")
    else:
        logger.warning("No sessions found in enhanced database")

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║         浮生十梦 - 数据库迁移工具                       ║
    ║                                                          ║
    ║  此脚本将把现有数据迁移到增强版数据库                   ║
    ║  支持从以下来源迁移：                                    ║
    ║  1. game_data.json 文件                                 ║
    ║  2. veloera.db SQLite 数据库                           ║
    ║                                                          ║
    ║  迁移后将创建备份文件                                   ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    response = input("是否开始迁移？(y/n): ")

    if response.lower() == 'y':
        perform_migration()
        verify_migration()
    else:
        print("迁移已取消")