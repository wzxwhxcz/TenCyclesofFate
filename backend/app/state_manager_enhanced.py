"""
增强版状态管理器 - 集成详细数据库存储
"""
import asyncio
import json
import logging
import time
from typing import Optional, Dict, List
from pathlib import Path

from .websocket_manager import manager as websocket_manager
from .live_system import live_manager
from . import security
from .config import settings
from .database_models import get_database_manager, init_enhanced_database

# --- Module-level State (内存缓存) ---
SESSIONS: Dict[str, Dict] = {}
_sessions_modified: bool = False
_auto_save_interval: int = 60  # 1分钟自动保存一次

# --- Logging ---
logger = logging.getLogger(__name__)

# --- Database Manager ---
db_manager = None

def init_database():
    """初始化数据库"""
    global db_manager
    db_manager = init_enhanced_database()
    logger.info("Enhanced database initialized")

def load_from_database():
    """从数据库加载所有会话数据到内存"""
    global SESSIONS

    if not db_manager:
        init_database()

    try:
        # 获取最近的会话
        recent_sessions = db_manager.get_recent_sessions(limit=100)
        SESSIONS = {}

        logger.info(f"Loaded {len(recent_sessions)} recent sessions from database")

    except Exception as e:
        logger.error(f"Database load error: {e}")
        SESSIONS = {}

def save_session_to_database(player_id: str, session_data: Dict):
    """保存单个会话到数据库（增强版）"""
    if not db_manager:
        init_database()

    try:
        # 提取用户信息
        username = session_data.get("username", player_id)
        trust_level = session_data.get("trust_level", 0)

        # 保存主会话数据
        db_manager.save_session(
            player_id=player_id,
            session_data=session_data,
            username=username,
            trust_level=trust_level
        )

        # 如果有当前试炼，保存试炼记录
        current_trial = session_data.get("current_trial")
        if current_trial:
            trial_number = current_trial.get("trial_number", 0)
            start_time = current_trial.get("start_time", time.time())
            rewards = current_trial.get("rewards", 0)

            trial_id = db_manager.save_trial_record(
                player_id=player_id,
                trial_number=trial_number,
                start_time=start_time,
                rewards=rewards
            )

            # 保存最新的输入历史
            internal_history = session_data.get("internal_history", [])
            if internal_history:
                # 保存最近的交互
                for item in internal_history[-5:]:  # 只保存最近5条
                    if item.get("role") == "user":
                        db_manager.save_player_input(
                            player_id=player_id,
                            input_text=item.get("content", ""),
                            trial_id=trial_id
                        )

    except Exception as e:
        logger.error(f"Failed to save enhanced session for {player_id}: {e}")

def save_all_to_database():
    """保存所有内存中的会话到数据库"""
    global _sessions_modified

    if not _sessions_modified:
        return

    if not db_manager:
        init_database()

    try:
        saved_count = 0
        for player_id, session_data in SESSIONS.items():
            save_session_to_database(player_id, session_data)
            saved_count += 1

        _sessions_modified = False
        logger.info(f"Saved {saved_count} sessions to enhanced database")

    except Exception as e:
        logger.error(f"Failed to save sessions to database: {e}")

# --- 兼容原有的JSON文件接口 ---
def load_from_json():
    """兼容接口：从数据库加载（而不是JSON文件）"""
    init_database()
    load_from_database()

    # 尝试迁移旧的JSON数据（如果存在）
    json_path = Path("game_data.json")
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                old_sessions = json.load(f)

            # 合并旧数据到数据库
            migrated_count = 0
            for player_id, session_data in old_sessions.items():
                if player_id not in SESSIONS:  # 只迁移不存在的数据
                    SESSIONS[player_id] = session_data
                    save_session_to_database(player_id, session_data)
                    migrated_count += 1

            # 重命名旧文件作为备份
            backup_name = f"game_data.json.backup.{int(time.time())}"
            json_path.rename(backup_name)
            logger.info(f"Migrated {migrated_count} sessions from JSON to enhanced database")
            logger.info(f"Old JSON file backed up as: {backup_name}")

        except Exception as e:
            logger.error(f"Failed to migrate JSON data: {e}")

def save_to_json():
    """兼容接口：保存到数据库（而不是JSON文件）"""
    save_all_to_database()

async def _auto_save_task():
    """定期保存数据到数据库"""
    while True:
        await asyncio.sleep(_auto_save_interval)
        if _sessions_modified:
            logger.info("Auto-saving to enhanced database...")
            save_all_to_database()

def start_auto_save_task():
    """启动自动保存任务"""
    logger.info(f"Starting auto-save task. Interval: {_auto_save_interval} seconds.")
    asyncio.create_task(_auto_save_task())

async def save_session(player_id: str, session_data: Dict):
    """保存会话并推送到WebSocket"""
    global _sessions_modified

    session_data["last_modified"] = time.time()
    SESSIONS[player_id] = session_data
    _sessions_modified = True

    # 立即保存到数据库（重要数据）
    save_session_to_database(player_id, session_data)

    # 推送更新
    tasks = [
        websocket_manager.send_json_to_player(
            player_id, {"type": "full_state", "data": session_data}
        ),
        live_manager.broadcast_state_update(player_id, session_data)
    ]
    await asyncio.gather(*tasks)

async def get_session(player_id: str) -> Optional[Dict]:
    """获取会话数据"""
    # 先从内存获取
    if player_id in SESSIONS:
        return SESSIONS[player_id]

    # 如果内存中没有，尝试从数据库加载
    # 这里简化处理，实际应该从数据库查询
    return None

async def get_last_n_inputs(player_id: str, n: int) -> List[str]:
    """获取最近N个玩家输入"""
    session = await get_session(player_id)
    if not session:
        return []

    internal_history = session.get("internal_history", [])

    player_inputs = [
        item["content"]
        for item in internal_history
        if isinstance(item, dict) and item.get("role") == "user"
    ]

    return player_inputs[-n:]

def get_most_recent_sessions(limit: int = 10) -> List[Dict]:
    """获取最近活跃的会话"""
    if not db_manager:
        init_database()

    results = []

    try:
        # 从数据库获取最新数据
        recent_sessions = db_manager.get_recent_sessions(limit)

        for session in recent_sessions:
            encrypted_id = security.encrypt_player_id(session['player_id'])
            display_name = session.get('username', session['player_id'])

            results.append({
                "player_id": encrypted_id,
                "display_name": display_name,
                "last_modified": session.get('last_modified', 0),
                "total_rewards": session.get('total_rewards', 0)
            })

    except Exception as e:
        logger.error(f"Failed to get recent sessions: {e}")

    return results

async def create_or_get_session(player_id: str) -> Dict:
    """创建或获取会话"""
    global _sessions_modified

    session = await get_session(player_id)
    if session is None:
        session = {}
        SESSIONS[player_id] = session
        _sessions_modified = True
        save_session_to_database(player_id, session)

    return session

async def clear_session(player_id: str):
    """清除会话"""
    global _sessions_modified

    if player_id in SESSIONS:
        SESSIONS[player_id] = {}
        _sessions_modified = True
        save_session_to_database(player_id, {})
        logger.info(f"Session for player {player_id} has been cleared.")

async def flag_player_for_punishment(player_id: str, level: str, reason: str):
    """标记玩家惩罚"""
    global _sessions_modified

    session = await get_session(player_id)
    if not session:
        logger.warning(f"Attempted to flag non-existent session for player {player_id}")
        return

    session["pending_punishment"] = {
        "level": level,
        "reason": reason
    }
    _sessions_modified = True

    # 立即保存到数据库
    save_session_to_database(player_id, session)

    logger.info(f"Player {player_id} flagged for {level} punishment. Reason: {reason}")

    await websocket_manager.send_json_to_player(
        player_id, {"type": "full_state", "data": session}
    )

def record_trial_completion(
    player_id: str,
    trial_number: int,
    rewards: int,
    journey_accepted: bool,
    narrative_summary: str = None
):
    """记录试炼完成"""
    if not db_manager:
        init_database()

    try:
        # 保存试炼记录
        trial_id = db_manager.save_trial_record(
            player_id=player_id,
            trial_number=trial_number,
            start_time=time.time() - 600,  # 假设试炼持续10分钟
            end_time=time.time(),
            rewards=rewards,
            journey_accepted=journey_accepted,
            narrative_summary=narrative_summary
        )

        # 记录奖励日志
        if rewards > 0:
            db_manager.save_reward_log(
                player_id=player_id,
                amount=rewards,
                reward_type="trial_completion",
                reason=f"Completed trial #{trial_number}",
                trial_id=trial_id
            )

        logger.info(f"Recorded trial completion for {player_id}: Trial #{trial_number}, Rewards: {rewards}")

    except Exception as e:
        logger.error(f"Failed to record trial completion: {e}")

def get_player_statistics(player_id: str) -> Dict:
    """获取玩家统计数据"""
    if not db_manager:
        init_database()

    try:
        stats = db_manager.get_player_statistics(player_id)
        return stats
    except Exception as e:
        logger.error(f"Failed to get player statistics: {e}")
        return {}

# 导出兼容的接口，让其他模块无需修改即可使用
__all__ = [
    'SESSIONS',
    'init_database',
    'load_from_json',
    'save_to_json',
    'start_auto_save_task',
    'save_session',
    'get_session',
    'get_last_n_inputs',
    'get_most_recent_sessions',
    'create_or_get_session',
    'clear_session',
    'flag_player_for_punishment',
    'record_trial_completion',
    'get_player_statistics'
]