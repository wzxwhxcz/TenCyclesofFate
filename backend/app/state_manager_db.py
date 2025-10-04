"""
使用数据库持久化的状态管理器
替代原本的JSON文件存储方式
"""
import asyncio
import json
import logging
import time
import sqlite3
from pathlib import Path
from typing import Optional, Dict, List
from .websocket_manager import manager as websocket_manager
from .live_system import live_manager
from . import security
from .config import settings

# --- Module-level State (内存缓存) ---
SESSIONS: Dict[str, Dict] = {}
_sessions_modified: bool = False
_auto_save_interval: int = 60  # 1分钟自动保存一次

# --- Logging ---
logger = logging.getLogger(__name__)

# --- Database Setup ---
def get_db_path() -> str:
    """获取数据库路径"""
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        return db_url.replace("sqlite:///", "")
    return "./game_sessions.db"  # 默认数据库文件

def init_database():
    """初始化数据库表"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建会话表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_sessions (
            player_id TEXT PRIMARY KEY,
            session_data TEXT NOT NULL,
            last_modified REAL NOT NULL,
            created_at REAL DEFAULT (strftime('%s', 'now'))
        )
    ''')
    
    # 创建索引以加快查询
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_last_modified 
        ON game_sessions(last_modified DESC)
    ''')
    
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at: {db_path}")

def load_from_database():
    """从数据库加载所有会话数据到内存"""
    global SESSIONS
    db_path = get_db_path()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT player_id, session_data, last_modified 
            FROM game_sessions
        ''')
        
        rows = cursor.fetchall()
        SESSIONS = {}
        
        for player_id, session_data_json, last_modified in rows:
            try:
                session_data = json.loads(session_data_json)
                session_data["last_modified"] = last_modified
                SESSIONS[player_id] = session_data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse session data for {player_id}: {e}")
        
        conn.close()
        logger.info(f"Loaded {len(SESSIONS)} sessions from database")
        
    except sqlite3.Error as e:
        logger.error(f"Database load error: {e}")
        SESSIONS = {}

def save_session_to_database(player_id: str, session_data: Dict):
    """保存单个会话到数据库"""
    db_path = get_db_path()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 序列化会话数据
        session_json = json.dumps(session_data, ensure_ascii=False)
        last_modified = session_data.get("last_modified", time.time())
        
        # 使用 REPLACE 来插入或更新
        cursor.execute('''
            REPLACE INTO game_sessions (player_id, session_data, last_modified)
            VALUES (?, ?, ?)
        ''', (player_id, session_json, last_modified))
        
        conn.commit()
        conn.close()
        
    except sqlite3.Error as e:
        logger.error(f"Failed to save session for {player_id}: {e}")

def save_all_to_database():
    """保存所有内存中的会话到数据库"""
    global _sessions_modified
    
    if not _sessions_modified:
        return
    
    db_path = get_db_path()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 批量更新所有会话
        for player_id, session_data in SESSIONS.items():
            session_json = json.dumps(session_data, ensure_ascii=False)
            last_modified = session_data.get("last_modified", time.time())
            
            cursor.execute('''
                REPLACE INTO game_sessions (player_id, session_data, last_modified)
                VALUES (?, ?, ?)
            ''', (player_id, session_json, last_modified))
        
        conn.commit()
        conn.close()
        
        _sessions_modified = False
        logger.info(f"Saved {len(SESSIONS)} sessions to database")
        
    except sqlite3.Error as e:
        logger.error(f"Failed to save sessions to database: {e}")

# --- 兼容原有的JSON文件接口 ---
def load_from_json():
    """兼容接口：从数据库加载（而不是JSON文件）"""
    init_database()  # 确保数据库已初始化
    load_from_database()
    
    # 尝试迁移旧的JSON数据（如果存在）
    json_path = Path("game_data.json")
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                old_sessions = json.load(f)
            
            # 合并旧数据到数据库
            for player_id, session_data in old_sessions.items():
                if player_id not in SESSIONS:  # 只迁移不存在的数据
                    SESSIONS[player_id] = session_data
                    save_session_to_database(player_id, session_data)
            
            # 重命名旧文件作为备份
            json_path.rename(f"game_data.json.backup.{int(time.time())}")
            logger.info(f"Migrated {len(old_sessions)} sessions from JSON to database")
            
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
            logger.info("Auto-saving to database...")
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
    db_path = get_db_path()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT session_data, last_modified 
            FROM game_sessions 
            WHERE player_id = ?
        ''', (player_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            session_data = json.loads(row[0])
            session_data["last_modified"] = row[1]
            # 缓存到内存
            SESSIONS[player_id] = session_data
            return session_data
            
    except sqlite3.Error as e:
        logger.error(f"Failed to load session for {player_id}: {e}")
    
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
    # 从数据库获取最新数据
    db_path = get_db_path()
    results = []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT player_id, last_modified 
            FROM game_sessions 
            ORDER BY last_modified DESC 
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        for player_id, last_modified in rows:
            encrypted_id = security.encrypt_player_id(player_id)
            display_name = (
                f"{player_id[0]}...{player_id[-1]}"
                if len(player_id) > 2
                else player_id
            )
            
            results.append({
                "player_id": encrypted_id,
                "display_name": display_name,
                "last_modified": last_modified
            })
            
    except sqlite3.Error as e:
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