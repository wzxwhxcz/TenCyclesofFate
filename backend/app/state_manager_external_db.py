"""
支持外部数据库（MySQL, PostgreSQL）的状态管理器
"""
import asyncio
import json
import logging
import time
from typing import Optional, Dict, List
from urllib.parse import urlparse
import sqlite3

# 可选导入，只在需要时导入
try:
    import mysql.connector
    from mysql.connector import pooling
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False
    
try:
    import psycopg2
    from psycopg2 import pool as psycopg2_pool
    HAS_POSTGRESQL = True
except ImportError:
    HAS_POSTGRESQL = False
    psycopg2 = None
    psycopg2_pool = None

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

# --- Database Connection Pool ---
_db_pool = None
_db_type = None

def init_database_pool():
    """初始化数据库连接池"""
    global _db_pool, _db_type
    
    db_url = settings.DATABASE_URL
    parsed = urlparse(db_url)
    
    if parsed.scheme == "sqlite":
        _db_type = "sqlite"
        # SQLite 不需要连接池
        _db_pool = None
        
    elif parsed.scheme in ["mysql", "mysql+pymysql"]:
        if not HAS_MYSQL:
            raise ImportError(
                "MySQL support requires mysql-connector-python. "
                "Install it with: pip install mysql-connector-python"
            )
        _db_type = "mysql"
        # 创建 MySQL 连接池
        config = {
            'user': parsed.username or 'root',
            'password': parsed.password or '',
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 3306,
            'database': parsed.path.lstrip('/'),
            'pool_name': 'game_pool',
            'pool_size': 5,
            'pool_reset_session': True
        }
        _db_pool = pooling.MySQLConnectionPool(**config)
        logger.info(f"MySQL connection pool created for {parsed.hostname}")
        
    elif parsed.scheme in ["postgresql", "postgres"]:
        if not HAS_POSTGRESQL:
            raise ImportError(
                "PostgreSQL support requires psycopg2. "
                "Install it with: pip install psycopg2-binary"
            )
        _db_type = "postgresql"
        # 创建 PostgreSQL 连接池
        _db_pool = psycopg2_pool.SimpleConnectionPool(
            1, 5,  # min and max connections
            user=parsed.username,
            password=parsed.password,
            host=parsed.hostname or 'localhost',
            port=parsed.port or 5432,
            database=parsed.path.lstrip('/')
        )
        logger.info(f"PostgreSQL connection pool created for {parsed.hostname}")
    
    else:
        raise ValueError(f"Unsupported database type: {parsed.scheme}")

def get_db_connection():
    """从连接池获取数据库连接"""
    if _db_type == "sqlite":
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        return sqlite3.connect(db_path)
    elif _db_type == "mysql":
        return _db_pool.get_connection()
    elif _db_type == "postgresql":
        return _db_pool.getconn()
    else:
        raise ValueError(f"Unknown database type: {_db_type}")

def release_db_connection(conn):
    """释放数据库连接回连接池"""
    if _db_type == "sqlite":
        conn.close()
    elif _db_type == "mysql":
        conn.close()  # MySQL connector 自动返回到池
    elif _db_type == "postgresql":
        _db_pool.putconn(conn)

def init_database():
    """初始化数据库表（支持多种数据库）"""
    init_database_pool()
    
    conn = get_db_connection()
    
    try:
        if _db_type == "sqlite":
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS game_sessions (
                    player_id TEXT PRIMARY KEY,
                    session_data TEXT NOT NULL,
                    last_modified REAL NOT NULL,
                    created_at REAL DEFAULT (strftime('%s', 'now'))
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_last_modified 
                ON game_sessions(last_modified DESC)
            ''')
            
        elif _db_type == "mysql":
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS game_sessions (
                    player_id VARCHAR(255) PRIMARY KEY,
                    session_data LONGTEXT NOT NULL,
                    last_modified DOUBLE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_last_modified 
                ON game_sessions(last_modified DESC)
            ''')
            
        elif _db_type == "postgresql":
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS game_sessions (
                    player_id VARCHAR(255) PRIMARY KEY,
                    session_data TEXT NOT NULL,
                    last_modified DOUBLE PRECISION NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_last_modified 
                ON game_sessions(last_modified DESC)
            ''')
        
        conn.commit()
        logger.info(f"Database tables initialized for {_db_type}")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        conn.rollback()
    finally:
        cursor.close()
        release_db_connection(conn)

def load_from_database():
    """从数据库加载所有会话数据到内存"""
    global SESSIONS
    
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT player_id, session_data, last_modified 
            FROM game_sessions
        ''')
        
        rows = cursor.fetchall()
        SESSIONS = {}
        
        for row in rows:
            player_id = row[0]
            session_data_json = row[1]
            last_modified = row[2]
            
            try:
                session_data = json.loads(session_data_json)
                session_data["last_modified"] = last_modified
                SESSIONS[player_id] = session_data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse session data for {player_id}: {e}")
        
        logger.info(f"Loaded {len(SESSIONS)} sessions from {_db_type} database")
        
    except Exception as e:
        logger.error(f"Database load error: {e}")
        SESSIONS = {}
    finally:
        cursor.close()
        release_db_connection(conn)

def save_session_to_database(player_id: str, session_data: Dict):
    """保存单个会话到数据库"""
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        session_json = json.dumps(session_data, ensure_ascii=False)
        last_modified = session_data.get("last_modified", time.time())
        
        if _db_type == "sqlite":
            cursor.execute('''
                REPLACE INTO game_sessions (player_id, session_data, last_modified)
                VALUES (?, ?, ?)
            ''', (player_id, session_json, last_modified))
            
        elif _db_type == "mysql":
            cursor.execute('''
                REPLACE INTO game_sessions (player_id, session_data, last_modified)
                VALUES (%s, %s, %s)
            ''', (player_id, session_json, last_modified))
            
        elif _db_type == "postgresql":
            cursor.execute('''
                INSERT INTO game_sessions (player_id, session_data, last_modified)
                VALUES (%s, %s, %s)
                ON CONFLICT (player_id) 
                DO UPDATE SET session_data = EXCLUDED.session_data, 
                              last_modified = EXCLUDED.last_modified
            ''', (player_id, session_json, last_modified))
        
        conn.commit()
        
    except Exception as e:
        logger.error(f"Failed to save session for {player_id}: {e}")
        conn.rollback()
    finally:
        cursor.close()
        release_db_connection(conn)

def save_all_to_database():
    """批量保存所有会话到数据库"""
    global _sessions_modified
    
    if not _sessions_modified:
        return
    
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        for player_id, session_data in SESSIONS.items():
            session_json = json.dumps(session_data, ensure_ascii=False)
            last_modified = session_data.get("last_modified", time.time())
            
            if _db_type == "sqlite":
                cursor.execute('''
                    REPLACE INTO game_sessions (player_id, session_data, last_modified)
                    VALUES (?, ?, ?)
                ''', (player_id, session_json, last_modified))
                
            elif _db_type == "mysql":
                cursor.execute('''
                    REPLACE INTO game_sessions (player_id, session_data, last_modified)
                    VALUES (%s, %s, %s)
                ''', (player_id, session_json, last_modified))
                
            elif _db_type == "postgresql":
                cursor.execute('''
                    INSERT INTO game_sessions (player_id, session_data, last_modified)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (player_id) 
                    DO UPDATE SET session_data = EXCLUDED.session_data, 
                                  last_modified = EXCLUDED.last_modified
                ''', (player_id, session_json, last_modified))
        
        conn.commit()
        _sessions_modified = False
        logger.info(f"Saved {len(SESSIONS)} sessions to {_db_type} database")
        
    except Exception as e:
        logger.error(f"Failed to save sessions: {e}")
        conn.rollback()
    finally:
        cursor.close()
        release_db_connection(conn)

# --- 兼容原有接口 ---
def load_from_json():
    """兼容接口：从数据库加载"""
    init_database()
    load_from_database()
    
    # 迁移旧JSON数据
    from pathlib import Path
    json_path = Path("game_data.json")
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                old_sessions = json.load(f)
            
            for player_id, session_data in old_sessions.items():
                if player_id not in SESSIONS:
                    SESSIONS[player_id] = session_data
                    save_session_to_database(player_id, session_data)
            
            json_path.rename(f"game_data.json.backup.{int(time.time())}")
            logger.info(f"Migrated {len(old_sessions)} sessions from JSON to database")
            
        except Exception as e:
            logger.error(f"Failed to migrate JSON data: {e}")

def save_to_json():
    """兼容接口：保存到数据库"""
    save_all_to_database()

async def _auto_save_task():
    """定期保存数据"""
    while True:
        await asyncio.sleep(_auto_save_interval)
        if _sessions_modified:
            logger.info(f"Auto-saving to {_db_type} database...")
            save_all_to_database()

def start_auto_save_task():
    """启动自动保存任务"""
    logger.info(f"Starting auto-save task. Interval: {_auto_save_interval} seconds.")
    asyncio.create_task(_auto_save_task())

async def save_session(player_id: str, session_data: Dict):
    """保存会话"""
    global _sessions_modified
    
    session_data["last_modified"] = time.time()
    SESSIONS[player_id] = session_data
    _sessions_modified = True
    
    save_session_to_database(player_id, session_data)
    
    tasks = [
        websocket_manager.send_json_to_player(
            player_id, {"type": "full_state", "data": session_data}
        ),
        live_manager.broadcast_state_update(player_id, session_data)
    ]
    await asyncio.gather(*tasks)

async def get_session(player_id: str) -> Optional[Dict]:
    """获取会话"""
    if player_id in SESSIONS:
        return SESSIONS[player_id]
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        if _db_type == "sqlite":
            cursor.execute('''
                SELECT session_data, last_modified 
                FROM game_sessions 
                WHERE player_id = ?
            ''', (player_id,))
        else:  # MySQL and PostgreSQL
            cursor.execute('''
                SELECT session_data, last_modified 
                FROM game_sessions 
                WHERE player_id = %s
            ''', (player_id,))
        
        row = cursor.fetchone()
        
        if row:
            session_data = json.loads(row[0])
            session_data["last_modified"] = row[1]
            SESSIONS[player_id] = session_data
            return session_data
            
    except Exception as e:
        logger.error(f"Failed to load session for {player_id}: {e}")
    finally:
        cursor.close()
        release_db_connection(conn)
    
    return None

async def get_last_n_inputs(player_id: str, n: int) -> List[str]:
    """获取最近N个输入"""
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
    """获取最近的会话"""
    conn = get_db_connection()
    results = []
    
    try:
        cursor = conn.cursor()
        
        if _db_type == "sqlite":
            cursor.execute('''
                SELECT player_id, last_modified 
                FROM game_sessions 
                ORDER BY last_modified DESC 
                LIMIT ?
            ''', (limit,))
        else:  # MySQL and PostgreSQL
            cursor.execute('''
                SELECT player_id, last_modified 
                FROM game_sessions 
                ORDER BY last_modified DESC 
                LIMIT %s
            ''', (limit,))
        
        rows = cursor.fetchall()
        
        for row in rows:
            player_id = row[0]
            last_modified = row[1]
            
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
            
    except Exception as e:
        logger.error(f"Failed to get recent sessions: {e}")
    finally:
        cursor.close()
        release_db_connection(conn)
    
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
    save_session_to_database(player_id, session)
    
    logger.info(f"Player {player_id} flagged for {level} punishment. Reason: {reason}")
    
    await websocket_manager.send_json_to_player(
        player_id, {"type": "full_state", "data": session}
    )