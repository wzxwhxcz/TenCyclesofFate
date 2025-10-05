# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

《浮生十梦》是一款基于 Web 的沉浸式文字冒险游戏，采用 FastAPI + WebSocket 后端和原生 JavaScript 前端架构。游戏核心是 AI 驱动的动态故事生成系统，玩家每天有10次机会进入不同的"梦境"体验独特人生。

## 核心架构

### 后端架构 (FastAPI)
- **main.py**: FastAPI 应用主入口，包含路由定义、OAuth2 回调处理和 WebSocket 端点
- **game_logic.py**: 游戏核心逻辑，包括会话管理、AI 互动流程和奖励计算
- **ai_service.py**: 统一 AI 服务接口，支持 OpenAI 和 Anthropic，自动故障转移
- **websocket_manager.py**: WebSocket 连接管理，处理实时通信和消息压缩
- **state_manager.py**: 游戏状态持久化，定期自动保存到 game_data.json
- **auth.py**: OAuth2 认证逻辑，集成 Linux.do 登录
- **admin.py**: 管理员功能路由，包括会话管理和兑换码生成

### 前端架构
- **index.js**: 主游戏界面逻辑，WebSocket 通信和 Markdown 渲染
- **admin.js**: 管理后台界面逻辑
- **live.js**: 实时游戏观战系统

### AI 提供商架构
- 支持 OpenAI 和 Anthropic Claude 双引擎
- 自动故障转移机制：当一个提供商失败时自动切换
- 流式响应支持，提供实时打字效果

## 常用开发命令

### 启动服务器
```bash
# Windows
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# Linux/Mac (使用 run.sh)
chmod +x run.sh
./run.sh

# Windows (使用批处理)
run_windows.bat
```

### 依赖管理
```bash
# 安装依赖
cd backend
pip install -r requirements.txt

# 使用 uv (推荐)
uv pip install -r backend/requirements.txt
```

### 测试命令
```bash
# 测试 AI 服务
python backend/test_ai_service.py

# 测试流式输出
python backend/test_streaming.py

# 测试认证和 WebSocket
python backend/test_auth_websocket.py
```

## 环境配置要点

必须在 `backend/.env` 配置的关键变量：
- `SECRET_KEY`: JWT 签名密钥（必须修改默认值）
- `LINUXDO_CLIENT_ID/SECRET`: OAuth2 认证凭证
- `AI_PROVIDER`: 选择 "openai"、"anthropic" 或 "auto"
- `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`: 至少配置一个

## WebSocket 通信协议

### 客户端发送消息类型
- `start_game`: 开始新游戏
- `start_trial`: 开始新的试炼
- `player_input`: 玩家输入 `{content: string}`
- `end_journey`: 结束当前旅程 `{accept: boolean}`
- `live_subscribe/unsubscribe`: 观战系统订阅

### 服务器响应消息类型
- `session_info`: 会话状态信息
- `narrative`: AI 生成的故事内容（支持流式）
- `journey_end`: 旅程结束信息
- `error`: 错误消息
- `keep_alive`: 心跳包

## 关键业务流程

### 游戏流程
1. 用户通过 Linux.do OAuth2 登录，获取 JWT token
2. WebSocket 连接时验证 token
3. 每日会话包含10次机会，每次试炼独立计算奖励
4. AI 根据玩家输入动态生成故事，支持天命判定（D100骰子）
5. 包含反作弊机制，检测 prompt 注入

### 状态管理
- 游戏状态存储在内存中，定期持久化到 `game_data.json`
- 支持多种数据库后端（SQLite、MySQL、PostgreSQL）
- WebSocket 断线重连机制

## 项目特色功能

### AI 双引擎支持
- 自动检测可用的 AI 服务
- 故障时自动切换提供商
- 支持流式和非流式响应

### 反作弊系统
- 使用独立 AI 模型检测 prompt 注入
- 惩罚机制：检测到作弊时返回失败结果

### 管理后台
- 访问路径：`/admin.html`
- 功能：查看会话、生成兑换码、清空数据
- 权限控制：trust_level >= 3 或在白名单中

### 实时观战系统
- 允许其他用户观看正在进行的游戏
- WebSocket 广播机制
- 隐私保护：可选择是否公开

## 注意事项

1. **路径处理**：Windows 环境使用反斜杠，需注意跨平台兼容性
2. **WebSocket 压缩**：使用 pako.js 进行 gzip 压缩，减少传输数据量
3. **Markdown 渲染**：前端使用 marked.js 渲染 AI 生成的 Markdown 内容
4. **异步初始化**：AI 服务采用延迟初始化，首次调用时验证客户端
5. **错误处理**：AI 调用失败时有完整的降级和重试机制