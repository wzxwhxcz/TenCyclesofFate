"""
增强版数据库模型 - 提供更详细的会话数据存储
支持 SQLite、MySQL、PostgreSQL
"""
import json
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from urllib.parse import urlparse
import sqlite3

# 可选导入
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

from .config import settings

logger = logging.getLogger(__name__)

class EnhancedDatabaseManager:
    """增强版数据库管理器，支持更详细的会话数据"""

    def __init__(self):
        self.db_type = None
        self.db_pool = None
        self._init_database_pool()
        self._init_tables()

    def _init_database_pool(self):
        """初始化数据库连接池"""
        db_url = settings.DATABASE_URL
        parsed = urlparse(db_url)

        if parsed.scheme == "sqlite":
            self.db_type = "sqlite"
            self.db_pool = None  # SQLite 不需要连接池
            logger.info("Using SQLite database")

        elif parsed.scheme in ["mysql", "mysql+pymysql"]:
            if not HAS_MYSQL:
                raise ImportError(
                    "MySQL support requires mysql-connector-python. "
                    "Install it with: pip install mysql-connector-python"
                )
            self.db_type = "mysql"
            config = {
                'user': parsed.username or 'root',
                'password': parsed.password or '',
                'host': parsed.hostname or 'localhost',
                'port': parsed.port or 3306,
                'database': parsed.path.lstrip('/'),
                'pool_name': 'game_pool',
                'pool_size': 10,
                'pool_reset_session': True
            }
            self.db_pool = pooling.MySQLConnectionPool(**config)
            logger.info(f"MySQL connection pool created for {parsed.hostname}")

        elif parsed.scheme in ["postgresql", "postgres"]:
            if not HAS_POSTGRESQL:
                raise ImportError(
                    "PostgreSQL support requires psycopg2. "
                    "Install it with: pip install psycopg2-binary"
                )
            self.db_type = "postgresql"
            self.db_pool = psycopg2_pool.SimpleConnectionPool(
                1, 10,  # min and max connections
                user=parsed.username,
                password=parsed.password,
                host=parsed.hostname or 'localhost',
                port=parsed.port or 5432,
                database=parsed.path.lstrip('/')
            )
            logger.info(f"PostgreSQL connection pool created for {parsed.hostname}")
        else:
            raise ValueError(f"Unsupported database type: {parsed.scheme}")

    def _get_connection(self):
        """获取数据库连接"""
        if self.db_type == "sqlite":
            db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            return sqlite3.connect(db_path)
        elif self.db_type == "mysql":
            return self.db_pool.get_connection()
        elif self.db_type == "postgresql":
            return self.db_pool.getconn()

    def _release_connection(self, conn):
        """释放数据库连接"""
        if self.db_type == "sqlite":
            conn.close()
        elif self.db_type == "mysql":
            conn.close()  # 自动返回池
        elif self.db_type == "postgresql":
            self.db_pool.putconn(conn)

    def _init_tables(self):
        """初始化数据库表结构"""
        conn = self._get_connection()

        try:
            cursor = conn.cursor()

            if self.db_type == "sqlite":
                # 主会话表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS game_sessions (
                        player_id TEXT PRIMARY KEY,
                        username TEXT,
                        trust_level INTEGER DEFAULT 0,
                        session_data TEXT NOT NULL,
                        total_sessions INTEGER DEFAULT 0,
                        total_rewards INTEGER DEFAULT 0,
                        last_modified REAL NOT NULL,
                        created_at REAL DEFAULT (strftime('%s', 'now')),
                        last_login REAL,
                        is_active BOOLEAN DEFAULT 1
                    )
                ''')

                # 试炼记录表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS trial_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        player_id TEXT NOT NULL,
                        trial_number INTEGER NOT NULL,
                        start_time REAL NOT NULL,
                        end_time REAL,
                        rewards INTEGER DEFAULT 0,
                        journey_accepted BOOLEAN DEFAULT 0,
                        narrative_summary TEXT,
                        created_at REAL DEFAULT (strftime('%s', 'now')),
                        FOREIGN KEY (player_id) REFERENCES game_sessions(player_id)
                    )
                ''')

                # 玩家输入历史表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS player_inputs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        player_id TEXT NOT NULL,
                        trial_id INTEGER,
                        input_text TEXT NOT NULL,
                        ai_response TEXT,
                        timestamp REAL DEFAULT (strftime('%s', 'now')),
                        FOREIGN KEY (player_id) REFERENCES game_sessions(player_id),
                        FOREIGN KEY (trial_id) REFERENCES trial_records(id)
                    )
                ''')

                # 奖励记录表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS reward_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        player_id TEXT NOT NULL,
                        trial_id INTEGER,
                        reward_type TEXT,
                        amount INTEGER,
                        reason TEXT,
                        timestamp REAL DEFAULT (strftime('%s', 'now')),
                        FOREIGN KEY (player_id) REFERENCES game_sessions(player_id),
                        FOREIGN KEY (trial_id) REFERENCES trial_records(id)
                    )
                ''')

                # 创建索引
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_modified ON game_sessions(last_modified DESC)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_trials_player ON trial_records(player_id, trial_number)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_inputs_player ON player_inputs(player_id, timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_rewards_player ON reward_logs(player_id, timestamp)')

            elif self.db_type == "mysql":
                # MySQL 表结构
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS game_sessions (
                        player_id VARCHAR(255) PRIMARY KEY,
                        username VARCHAR(255),
                        trust_level INT DEFAULT 0,
                        session_data LONGTEXT NOT NULL,
                        total_sessions INT DEFAULT 0,
                        total_rewards INT DEFAULT 0,
                        last_modified DOUBLE NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP NULL,
                        is_active BOOLEAN DEFAULT TRUE
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS trial_records (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        player_id VARCHAR(255) NOT NULL,
                        trial_number INT NOT NULL,
                        start_time TIMESTAMP NOT NULL,
                        end_time TIMESTAMP NULL,
                        rewards INT DEFAULT 0,
                        journey_accepted BOOLEAN DEFAULT FALSE,
                        narrative_summary TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (player_id) REFERENCES game_sessions(player_id),
                        INDEX idx_player_trial (player_id, trial_number)
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS player_inputs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        player_id VARCHAR(255) NOT NULL,
                        trial_id INT,
                        input_text TEXT NOT NULL,
                        ai_response LONGTEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (player_id) REFERENCES game_sessions(player_id),
                        FOREIGN KEY (trial_id) REFERENCES trial_records(id),
                        INDEX idx_player_time (player_id, timestamp)
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS reward_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        player_id VARCHAR(255) NOT NULL,
                        trial_id INT,
                        reward_type VARCHAR(100),
                        amount INT,
                        reason TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (player_id) REFERENCES game_sessions(player_id),
                        FOREIGN KEY (trial_id) REFERENCES trial_records(id),
                        INDEX idx_player_rewards (player_id, timestamp)
                    )
                ''')

            elif self.db_type == "postgresql":
                # PostgreSQL 表结构
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS game_sessions (
                        player_id VARCHAR(255) PRIMARY KEY,
                        username VARCHAR(255),
                        trust_level INT DEFAULT 0,
                        session_data TEXT NOT NULL,
                        total_sessions INT DEFAULT 0,
                        total_rewards INT DEFAULT 0,
                        last_modified DOUBLE PRECISION NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP,
                        is_active BOOLEAN DEFAULT TRUE
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS trial_records (
                        id SERIAL PRIMARY KEY,
                        player_id VARCHAR(255) NOT NULL,
                        trial_number INT NOT NULL,
                        start_time TIMESTAMP NOT NULL,
                        end_time TIMESTAMP,
                        rewards INT DEFAULT 0,
                        journey_accepted BOOLEAN DEFAULT FALSE,
                        narrative_summary TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (player_id) REFERENCES game_sessions(player_id)
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS player_inputs (
                        id SERIAL PRIMARY KEY,
                        player_id VARCHAR(255) NOT NULL,
                        trial_id INT,
                        input_text TEXT NOT NULL,
                        ai_response TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (player_id) REFERENCES game_sessions(player_id),
                        FOREIGN KEY (trial_id) REFERENCES trial_records(id)
                    )
                ''')

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS reward_logs (
                        id SERIAL PRIMARY KEY,
                        player_id VARCHAR(255) NOT NULL,
                        trial_id INT,
                        reward_type VARCHAR(100),
                        amount INT,
                        reason TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (player_id) REFERENCES game_sessions(player_id),
                        FOREIGN KEY (trial_id) REFERENCES trial_records(id)
                    )
                ''')

                # PostgreSQL 索引
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_modified ON game_sessions(last_modified DESC)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_trials_player ON trial_records(player_id, trial_number)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_inputs_player ON player_inputs(player_id, timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_rewards_player ON reward_logs(player_id, timestamp)')

            conn.commit()
            logger.info(f"Database tables initialized for {self.db_type}")

        except Exception as e:
            logger.error(f"Failed to initialize tables: {e}")
            conn.rollback()
        finally:
            cursor.close()
            self._release_connection(conn)

    def save_session(self, player_id: str, session_data: Dict, username: str = None, trust_level: int = 0):
        """保存完整的会话数据"""
        conn = self._get_connection()

        try:
            cursor = conn.cursor()
            session_json = json.dumps(session_data, ensure_ascii=False)
            last_modified = time.time()

            if self.db_type == "sqlite":
                cursor.execute('''
                    INSERT OR REPLACE INTO game_sessions
                    (player_id, username, trust_level, session_data, last_modified, last_login)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (player_id, username, trust_level, session_json, last_modified, last_modified))

            elif self.db_type == "mysql":
                cursor.execute('''
                    INSERT INTO game_sessions
                    (player_id, username, trust_level, session_data, last_modified, last_login)
                    VALUES (%s, %s, %s, %s, %s, FROM_UNIXTIME(%s))
                    ON DUPLICATE KEY UPDATE
                    username = VALUES(username),
                    trust_level = VALUES(trust_level),
                    session_data = VALUES(session_data),
                    last_modified = VALUES(last_modified),
                    last_login = VALUES(last_login)
                ''', (player_id, username, trust_level, session_json, last_modified, last_modified))

            elif self.db_type == "postgresql":
                cursor.execute('''
                    INSERT INTO game_sessions
                    (player_id, username, trust_level, session_data, last_modified, last_login)
                    VALUES (%s, %s, %s, %s, %s, to_timestamp(%s))
                    ON CONFLICT (player_id)
                    DO UPDATE SET
                    username = EXCLUDED.username,
                    trust_level = EXCLUDED.trust_level,
                    session_data = EXCLUDED.session_data,
                    last_modified = EXCLUDED.last_modified,
                    last_login = EXCLUDED.last_login
                ''', (player_id, username, trust_level, session_json, last_modified, last_modified))

            conn.commit()

        except Exception as e:
            logger.error(f"Failed to save session for {player_id}: {e}")
            conn.rollback()
        finally:
            cursor.close()
            self._release_connection(conn)

    def save_trial_record(
        self,
        player_id: str,
        trial_number: int,
        start_time: float,
        end_time: float = None,
        rewards: int = 0,
        journey_accepted: bool = False,
        narrative_summary: str = None
    ) -> Optional[int]:
        """保存试炼记录，返回记录ID"""
        conn = self._get_connection()

        try:
            cursor = conn.cursor()

            if self.db_type == "sqlite":
                cursor.execute('''
                    INSERT INTO trial_records
                    (player_id, trial_number, start_time, end_time, rewards, journey_accepted, narrative_summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (player_id, trial_number, start_time, end_time, rewards, journey_accepted, narrative_summary))
                trial_id = cursor.lastrowid

            elif self.db_type == "mysql":
                cursor.execute('''
                    INSERT INTO trial_records
                    (player_id, trial_number, start_time, end_time, rewards, journey_accepted, narrative_summary)
                    VALUES (%s, %s, FROM_UNIXTIME(%s), FROM_UNIXTIME(%s), %s, %s, %s)
                ''', (player_id, trial_number, start_time, end_time, rewards, journey_accepted, narrative_summary))
                trial_id = cursor.lastrowid

            elif self.db_type == "postgresql":
                cursor.execute('''
                    INSERT INTO trial_records
                    (player_id, trial_number, start_time, end_time, rewards, journey_accepted, narrative_summary)
                    VALUES (%s, %s, to_timestamp(%s), to_timestamp(%s), %s, %s, %s)
                    RETURNING id
                ''', (player_id, trial_number, start_time, end_time, rewards, journey_accepted, narrative_summary))
                trial_id = cursor.fetchone()[0]

            conn.commit()
            return trial_id

        except Exception as e:
            logger.error(f"Failed to save trial record: {e}")
            conn.rollback()
            return None
        finally:
            cursor.close()
            self._release_connection(conn)

    def save_player_input(
        self,
        player_id: str,
        input_text: str,
        ai_response: str = None,
        trial_id: int = None
    ):
        """保存玩家输入和AI响应"""
        conn = self._get_connection()

        try:
            cursor = conn.cursor()

            if self.db_type == "sqlite":
                cursor.execute('''
                    INSERT INTO player_inputs
                    (player_id, trial_id, input_text, ai_response)
                    VALUES (?, ?, ?, ?)
                ''', (player_id, trial_id, input_text, ai_response))

            elif self.db_type in ["mysql", "postgresql"]:
                cursor.execute('''
                    INSERT INTO player_inputs
                    (player_id, trial_id, input_text, ai_response)
                    VALUES (%s, %s, %s, %s)
                ''', (player_id, trial_id, input_text, ai_response))

            conn.commit()

        except Exception as e:
            logger.error(f"Failed to save player input: {e}")
            conn.rollback()
        finally:
            cursor.close()
            self._release_connection(conn)

    def save_reward_log(
        self,
        player_id: str,
        amount: int,
        reward_type: str = None,
        reason: str = None,
        trial_id: int = None
    ):
        """记录奖励日志"""
        conn = self._get_connection()

        try:
            cursor = conn.cursor()

            if self.db_type == "sqlite":
                cursor.execute('''
                    INSERT INTO reward_logs
                    (player_id, trial_id, reward_type, amount, reason)
                    VALUES (?, ?, ?, ?, ?)
                ''', (player_id, trial_id, reward_type, amount, reason))

            elif self.db_type in ["mysql", "postgresql"]:
                cursor.execute('''
                    INSERT INTO reward_logs
                    (player_id, trial_id, reward_type, amount, reason)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (player_id, trial_id, reward_type, amount, reason))

            conn.commit()

        except Exception as e:
            logger.error(f"Failed to save reward log: {e}")
            conn.rollback()
        finally:
            cursor.close()
            self._release_connection(conn)

    def get_player_statistics(self, player_id: str) -> Dict:
        """获取玩家统计数据"""
        conn = self._get_connection()

        try:
            cursor = conn.cursor()

            # 获取基础信息
            if self.db_type == "sqlite":
                cursor.execute('''
                    SELECT username, trust_level, total_sessions, total_rewards, created_at, last_login
                    FROM game_sessions
                    WHERE player_id = ?
                ''', (player_id,))
            else:
                cursor.execute('''
                    SELECT username, trust_level, total_sessions, total_rewards, created_at, last_login
                    FROM game_sessions
                    WHERE player_id = %s
                ''', (player_id,))

            row = cursor.fetchone()
            if not row:
                return {}

            stats = {
                'username': row[0],
                'trust_level': row[1],
                'total_sessions': row[2],
                'total_rewards': row[3],
                'created_at': row[4],
                'last_login': row[5]
            }

            # 获取试炼统计
            if self.db_type == "sqlite":
                cursor.execute('''
                    SELECT COUNT(*), SUM(rewards), AVG(rewards)
                    FROM trial_records
                    WHERE player_id = ?
                ''', (player_id,))
            else:
                cursor.execute('''
                    SELECT COUNT(*), SUM(rewards), AVG(rewards)
                    FROM trial_records
                    WHERE player_id = %s
                ''', (player_id,))

            trial_stats = cursor.fetchone()
            stats['total_trials'] = trial_stats[0] or 0
            stats['total_trial_rewards'] = trial_stats[1] or 0
            stats['avg_trial_rewards'] = trial_stats[2] or 0

            return stats

        except Exception as e:
            logger.error(f"Failed to get player statistics: {e}")
            return {}
        finally:
            cursor.close()
            self._release_connection(conn)

    def get_recent_sessions(self, limit: int = 10) -> List[Dict]:
        """获取最近的会话"""
        conn = self._get_connection()
        results = []

        try:
            cursor = conn.cursor()

            if self.db_type == "sqlite":
                cursor.execute('''
                    SELECT player_id, username, last_modified, total_rewards
                    FROM game_sessions
                    WHERE is_active = 1
                    ORDER BY last_modified DESC
                    LIMIT ?
                ''', (limit,))
            else:
                cursor.execute('''
                    SELECT player_id, username, last_modified, total_rewards
                    FROM game_sessions
                    WHERE is_active = TRUE
                    ORDER BY last_modified DESC
                    LIMIT %s
                ''', (limit,))

            for row in cursor.fetchall():
                results.append({
                    'player_id': row[0],
                    'username': row[1],
                    'last_modified': row[2],
                    'total_rewards': row[3]
                })

            return results

        except Exception as e:
            logger.error(f"Failed to get recent sessions: {e}")
            return []
        finally:
            cursor.close()
            self._release_connection(conn)

# 创建全局实例
database_manager = None

def init_enhanced_database():
    """初始化增强版数据库"""
    global database_manager
    database_manager = EnhancedDatabaseManager()
    logger.info("Enhanced database manager initialized")
    return database_manager

def get_database_manager() -> EnhancedDatabaseManager:
    """获取数据库管理器实例"""
    global database_manager
    if database_manager is None:
        database_manager = init_enhanced_database()
    return database_manager