# Repository Guidelines

## 项目结构与模块组织
- 后端：`backend/app/`（FastAPI，核心模块含 `main.py`、`auth.py`、`game_logic.py`、`state_manager*.py`、`websocket_manager.py`、`database_models.py`、`config.py`、`ai_service.py`、`security.py`、`prompts/`）。
- 前端：`frontend/`（`index.html`、`admin.html`、`live.html` 及对应 `*.js/*.css`）。
- 测试/工具：`backend/test_*.py`、`scripts/generate_token.py`、迁移脚本 `backend/migrate_database.py`。
- 启动脚本：`run_windows.bat`、`run.sh`；配置示例：`backend/.env.example`。

## 构建、运行与开发
- 安装依赖：`uv pip install -r backend/requirements.txt` 或 `pip install -r backend/requirements.txt`。
- 本地运行（跨平台）：`python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload`（或 `python backend/app/main.py`）。
- Windows 快速启动：`./run_windows.bat`；Linux/macOS 可参考 `./run.sh`（注意根据环境调整脚本中的路径）。
- 配置：复制 `backend/.env.example` 为 `backend/.env` 并设置 `SECRET_KEY`、`OPENAI_API_KEY`、`DATABASE_URL`、Linux.do OAuth 等，详见 `README.md`、`AI_PROVIDER_GUIDE.md`、`DATABASE_SETUP.md`。

## 代码风格与命名
- Python 3.10+，四空格缩进，`snake_case`，尽量使用类型标注；模块职责单一（SOLID/S）。
- 前端 JS 使用清晰函数名与模块化文件；避免全局污染。
- 统一字符串风格与日志级别，避免重复逻辑（DRY/KISS）。

## 测试指南
- 脚本化测试：直接运行 `python backend/test_database.py`、`python backend/test_auth_websocket.py`、`python backend/test_streaming.py`、`python backend/test_ai_service.py`。
- WebSocket/认证相关测试需先启动后端（默认 `http://127.0.0.1:8000`）。
- 测试文件命名：`test_*.py`，输出应包含可读日志；当前无强制覆盖率要求。

## 提交与 PR 规范
- 历史提交偏短中文说明；建议采用简洁祈使句，必要时加前缀：`feat:`、`fix:`、`chore:`、`docs:`。
- PR 要求：问题背景与动机、变更说明、测试方法与结果、相关截图（如 `frontend/index.html`/`admin.html`）、关联 Issue、风险与回滚策略。

## 安全与配置
- 绝不提交密钥与私密配置；仅使用 `backend/.env`。生产环境关闭 `UVICORN_RELOAD`，务必设置强 `SECRET_KEY`。数据库变更/迁移前先备份，`backend/migrate_database.py` 为交互式工具。

