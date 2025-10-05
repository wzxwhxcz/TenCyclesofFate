# 数据库配置指南

## 概述

《浮生十梦》现已支持完整的数据库存储功能，将用户会话数据持久化到数据库中，支持 SQLite、MySQL 和 PostgreSQL。

## 功能特性

### 已实现的功能

#### 1. 基础版（state_manager.py）
- ✅ SQLite 数据库存储
- ✅ 自动保存机制（每60秒）
- ✅ 内存缓存 + 数据库持久化
- ✅ JSON 数据自动迁移

#### 2. 外部数据库支持（state_manager_external_db.py）
- ✅ MySQL 支持
- ✅ PostgreSQL 支持
- ✅ 连接池管理
- ✅ 统一数据库接口

#### 3. 增强版（database_models.py + state_manager_enhanced.py）
- ✅ 详细的会话记录
- ✅ 试炼历史追踪
- ✅ 玩家输入记录
- ✅ 奖励日志
- ✅ 玩家统计数据

## 数据库表结构

### 主要数据表

1. **game_sessions** - 玩家会话表
   - player_id: 玩家ID（主键）
   - username: 用户名
   - trust_level: 信任等级
   - session_data: 会话数据（JSON）
   - total_sessions: 总会话数
   - total_rewards: 总奖励
   - last_modified: 最后修改时间
   - created_at: 创建时间
   - last_login: 最后登录时间
   - is_active: 是否活跃

2. **trial_records** - 试炼记录表
   - id: 记录ID（主键）
   - player_id: 玩家ID
   - trial_number: 试炼编号
   - start_time: 开始时间
   - end_time: 结束时间
   - rewards: 获得奖励
   - journey_accepted: 是否接受旅程
   - narrative_summary: 故事摘要

3. **player_inputs** - 玩家输入历史
   - id: 记录ID（主键）
   - player_id: 玩家ID
   - trial_id: 试炼ID
   - input_text: 输入文本
   - ai_response: AI响应
   - timestamp: 时间戳

4. **reward_logs** - 奖励日志
   - id: 记录ID（主键）
   - player_id: 玩家ID
   - trial_id: 试炼ID
   - reward_type: 奖励类型
   - amount: 奖励数量
   - reason: 奖励原因
   - timestamp: 时间戳

## 配置方法

### 1. SQLite（默认）

在 `backend/.env` 文件中：

```env
DATABASE_URL=sqlite:///./veloera.db
```

无需额外安装，Python 自带 SQLite 支持。

### 2. MySQL

安装依赖：
```bash
pip install mysql-connector-python
```

在 `backend/.env` 文件中配置：
```env
DATABASE_URL=mysql://username:password@localhost:3306/database_name
```

### 3. PostgreSQL

安装依赖：
```bash
pip install psycopg2-binary
```

在 `backend/.env` 文件中配置：
```env
DATABASE_URL=postgresql://username:password@localhost:5432/database_name
```

## 使用方法

### 1. 使用默认配置（推荐）

项目默认使用 `state_manager.py`，自动使用 SQLite 数据库：

```python
# 无需修改，直接启动服务器
python -m uvicorn backend.app.main:app --reload
```

### 2. 启用外部数据库

如需使用 MySQL 或 PostgreSQL，修改 `backend/app/main.py`：

```python
# 将这行：
from .app import state_manager

# 改为：
from .app import state_manager_external_db as state_manager
```

### 3. 启用增强版功能

如需使用增强版功能（详细记录），修改 `backend/app/main.py`：

```python
# 将这行：
from .app import state_manager

# 改为：
from .app import state_manager_enhanced as state_manager
```

## 数据迁移

### 从 JSON 迁移到数据库

运行迁移脚本：
```bash
cd backend
python migrate_database.py
```

脚本会自动：
1. 检测 `game_data.json` 文件
2. 检测旧的 SQLite 数据库
3. 将数据迁移到新数据库
4. 创建备份文件

### 手动迁移

如需手动迁移特定数据：

```python
from backend.app.database_models import get_database_manager

db = get_database_manager()

# 保存会话
db.save_session(
    player_id="user123",
    session_data={"key": "value"},
    username="玩家名",
    trust_level=2
)

# 记录试炼
trial_id = db.save_trial_record(
    player_id="user123",
    trial_number=1,
    start_time=time.time(),
    rewards=100
)
```

## 测试

运行测试脚本验证数据库功能：

```bash
cd backend
python test_database.py
```

测试内容包括：
- 基本的 CRUD 操作
- 多用户场景
- 数据库连接
- 性能测试

## 性能优化

### 1. 连接池配置

MySQL 连接池（默认5个连接）：
```python
'pool_size': 5,
'pool_reset_session': True
```

PostgreSQL 连接池（1-5个连接）：
```python
SimpleConnectionPool(1, 5, ...)
```

### 2. 索引优化

已创建的索引：
- `idx_sessions_modified`: 按修改时间排序
- `idx_trials_player`: 按玩家和试炼编号
- `idx_inputs_player`: 按玩家和时间
- `idx_rewards_player`: 按玩家和时间

### 3. 缓存策略

- 内存缓存热数据
- 定期批量写入数据库
- 重要数据立即持久化

## 监控和维护

### 查看数据库状态

SQLite：
```bash
sqlite3 veloera.db
.tables
SELECT COUNT(*) FROM game_sessions;
```

MySQL：
```sql
SHOW TABLES;
SELECT COUNT(*) FROM game_sessions;
```

PostgreSQL：
```sql
\dt
SELECT COUNT(*) FROM game_sessions;
```

### 数据备份

定期备份数据库：

```bash
# SQLite
cp veloera.db veloera.db.backup

# MySQL
mysqldump -u username -p database_name > backup.sql

# PostgreSQL
pg_dump -U username database_name > backup.sql
```

## 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查 DATABASE_URL 配置
   - 确认数据库服务运行中
   - 验证用户权限

2. **表不存在错误**
   - 运行初始化：`python -c "from backend.app.database_models import init_enhanced_database; init_enhanced_database()"`

3. **性能问题**
   - 增加连接池大小
   - 添加适当的索引
   - 考虑分表或分区

## 未来计划

- [ ] 支持 MongoDB
- [ ] 数据分析仪表板
- [ ] 自动备份功能
- [ ] 数据导出/导入工具
- [ ] 性能监控集成