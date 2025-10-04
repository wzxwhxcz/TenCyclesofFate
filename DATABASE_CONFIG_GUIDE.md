# 外部数据库配置指南

## 概述

项目支持多种数据库类型，可以根据部署环境选择合适的数据库：
- **SQLite**（默认）- 适合开发和小型部署
- **MySQL** - 适合中大型部署
- **PostgreSQL** - 适合需要高级功能的部署

## 数据库配置

在 `backend/.env` 文件中设置 `DATABASE_URL` 环境变量：

### 1. SQLite（默认）
```env
DATABASE_URL=sqlite:///./veloera.db
```
- 数据存储在本地文件
- 无需额外安装数据库服务器
- 适合开发环境

### 2. MySQL
```env
# 格式：mysql://用户名:密码@主机:端口/数据库名
DATABASE_URL=mysql://root:password@localhost:3306/game_db

# 示例（使用云数据库）
DATABASE_URL=mysql://user123:pass456@db.example.com:3306/tencycles
```

#### MySQL 设置步骤：
1. 创建数据库：
```sql
CREATE DATABASE game_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. 创建用户（可选）：
```sql
CREATE USER 'gameuser'@'%' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON game_db.* TO 'gameuser'@'%';
FLUSH PRIVILEGES;
```

### 3. PostgreSQL
```env
# 格式：postgresql://用户名:密码@主机:端口/数据库名
DATABASE_URL=postgresql://postgres:password@localhost:5432/game_db

# 示例（使用 Render 的 PostgreSQL）
DATABASE_URL=postgresql://user:pass@dpg-xxx.render.com:5432/dbname
```

#### PostgreSQL 设置步骤：
1. 创建数据库：
```sql
CREATE DATABASE game_db;
```

2. 创建用户（可选）：
```sql
CREATE USER gameuser WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE game_db TO gameuser;
```

## Render 部署配置

### 使用 Render 的 PostgreSQL

1. 在 Render Dashboard 创建一个 PostgreSQL 数据库
2. 复制 Internal Database URL 或 External Database URL
3. 在你的 Web Service 中添加环境变量：
   - Key: `DATABASE_URL`
   - Value: 复制的数据库 URL

### 使用外部 MySQL（如 PlanetScale）

1. 在 PlanetScale 创建数据库
2. 获取连接字符串
3. 在 Render 环境变量中设置：
   ```
   DATABASE_URL=mysql://xxx:pscale_pw_xxx@aws.connect.psdb.cloud/your-db?ssl={"rejectUnauthorized":true}
   ```

## 数据迁移

### 从 JSON 文件迁移到数据库

如果你之前使用的是 JSON 文件存储（`game_data.json`），系统会自动迁移数据：

1. 启动时检测到 `game_data.json` 文件
2. 自动导入所有会话数据到新数据库
3. 将原文件重命名为备份（`game_data.json.backup.时间戳`）

### 从 SQLite 迁移到 MySQL/PostgreSQL

1. 备份当前 SQLite 数据：
```bash
sqlite3 veloera.db .dump > backup.sql
```

2. 修改 `DATABASE_URL` 为新数据库
3. 重启应用，表结构会自动创建
4. 如需导入旧数据，可以手动转换 SQL 格式

## 性能优化建议

### MySQL 优化
```sql
-- 增加连接数
SET GLOBAL max_connections = 200;

-- 优化缓冲池
SET GLOBAL innodb_buffer_pool_size = 256M;
```

### PostgreSQL 优化
```sql
-- 增加连接数
ALTER SYSTEM SET max_connections = 200;

-- 优化共享缓冲区
ALTER SYSTEM SET shared_buffers = '256MB';

-- 重载配置
SELECT pg_reload_conf();
```

## 连接池配置

项目已内置连接池管理：
- MySQL: 默认池大小 5
- PostgreSQL: 默认池大小 1-5

可以在代码中调整：
```python
# backend/app/state_manager.py
'pool_size': 10,  # 增加连接池大小
```

## 故障排查

### 连接失败
1. 检查 `DATABASE_URL` 格式是否正确
2. 确认数据库服务器正在运行
3. 验证用户名和密码
4. 检查防火墙设置

### 权限问题
```sql
-- MySQL
SHOW GRANTS FOR 'username'@'host';

-- PostgreSQL
\du  -- 列出用户
\l   -- 列出数据库
```

### 查看日志
```bash
# 查看应用日志
tail -f backend/app.log

# MySQL 日志
tail -f /var/log/mysql/error.log

# PostgreSQL 日志
tail -f /var/log/postgresql/postgresql-*.log
```

## 备份策略

### 自动备份脚本
```bash
#!/bin/bash
# backup.sh

# MySQL
mysqldump -u user -p database > backup_$(date +%Y%m%d).sql

# PostgreSQL
pg_dump -U user database > backup_$(date +%Y%m%d).sql

# SQLite
cp veloera.db backup_$(date +%Y%m%d).db
```

### 定时备份（cron）
```bash
# 每天凌晨3点备份
0 3 * * * /path/to/backup.sh
```

## 监控建议

1. **连接数监控**
   - MySQL: `SHOW STATUS LIKE 'Threads_connected';`
   - PostgreSQL: `SELECT count(*) FROM pg_stat_activity;`

2. **查询性能**
   - 启用慢查询日志
   - 定期分析查询性能

3. **存储空间**
   - 监控数据库大小增长
   - 定期清理旧数据

## 安全建议

1. **使用环境变量**
   - 不要在代码中硬编码数据库密码
   - 使用 `.env` 文件且不提交到版本控制

2. **限制访问**
   - 使用防火墙限制数据库访问
   - 只允许应用服务器IP访问

3. **加密连接**
   - MySQL: 添加 `?ssl=true`
   - PostgreSQL: 添加 `?sslmode=require`

4. **定期更新密码**
   - 每3-6个月更换数据库密码
   - 使用强密码

## 示例配置

### 开发环境
```env
DATABASE_URL=sqlite:///./dev.db
```

### 测试环境
```env
DATABASE_URL=mysql://test_user:test_pass@localhost:3306/test_db
```

### 生产环境（Render + PostgreSQL）
```env
DATABASE_URL=postgresql://user:pass@dpg-xxx.oregon-postgres.render.com:5432/dbname
```

## 联系支持

如遇到数据库配置问题：
1. 检查本文档的故障排查部分
2. 查看应用日志
3. 确认数据库服务状态
4. 联系技术支持