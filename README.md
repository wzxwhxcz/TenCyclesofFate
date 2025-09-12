# 《浮生十梦》

**《浮生十梦》** 是一款基于 Web 的沉浸式文字冒险游戏。玩家在游戏中扮演一个与命运博弈的角色，每天有十次机会进入不同的“梦境”（即生命轮回），体验由 AI 动态生成的、独一无二的人生故事。游戏的核心在于“知足”与“贪欲”之间的抉择：是见好就收，还是追求更高的回报但可能失去一切？

## ✨ 功能特性

- **动态 AI 生成内容**:每一次游戏体验都由大型语言模型（如 GPT）实时生成，确保了故事的独特性和不可预测性。
- **实时交互**: 通过 WebSocket 实现前端与后端的实时通信，提供流畅的游戏体验。
- **OAuth2 认证**: 集成 Linux.do OAuth2 服务，实现安全便捷的用户登录。
- **精美的前端界面**: 采用具有“江南园林”风格的 UI 设计，提供沉浸式的视觉体验。
- **互动式判定系统**: 游戏中的关键行动可能触发“天命判定”。AI 会根据情境请求一次 D100 投骰，其“成功”、“失败”、“大成功”或“大失败”的结果将实时影响叙事走向，增加了游戏的随机性和戏剧性。
- **智能反作弊机制**: 内置一套基于 AI 的反作弊系统。它会分析玩家的输入行为，以识别并惩罚那些试图使用“奇巧咒语”（如 Prompt 注入）来破坏游戏平衡或牟取不当利益的玩家，确保了游戏的公平性。
- **数据持久化**: 游戏状态会定期保存，并在应用重启时加载，保证玩家进度不丢失。

## 🛠️ 技术栈

- **后端**:
  - **框架**: FastAPI
  - **Web 服务器**: Uvicorn
  - **实时通信**: WebSockets
  - **认证**: Python-JOSE (JWT), Authlib (OAuth)
  - **数据库**: SQLite (用于存储兑换码)
  - **AI 集成**: OpenAI API
  - **依赖管理**: uv / pip

- **前端**:
  - **语言**: HTML, CSS, JavaScript (ESM)
  - **库**:
    - `marked.js`: 用于在前端渲染 Markdown 格式的叙事文本。
    - `pako.js`: 用于解压缩从 WebSocket 服务器接收的 Gzip 数据，提高传输效率。

## 🚀 部署指南

请遵循以下步骤在您的本地环境或服务器上部署《浮生十梦》。

### 1. 环境准备

确保您的系统已安装以下软件：

- **Python 3.8+**
- **Git**
- **uv** (推荐, 用于快速安装依赖):
  ```bash
  pip install uv
  ```

### 2. 获取项目代码

使用 `git` 克隆本仓库到您的本地机器：

```bash
git clone https://github.com/CassiopeiaCode/TenCyclesofFate.git
cd TenCyclesofFate
```

### 3. 安装后端依赖

项目使用 `uv`（或 `pip`）来管理 Python 依赖。在项目根目录下运行：

```bash
# 使用 uv (推荐)
uv pip install -r backend/requirements.txt

# 或者使用 pip
pip install -r backend/requirements.txt
```

### 4. 配置环境变量

项目的所有配置都通过环境变量进行管理。

1.  **创建 `.env` 文件**:
    在 `backend/` 目录下，复制示例文件 `.env.example` 并重命名为 `.env`。

    ```bash
    cp backend/.env.example backend/.env
    ```

2.  **编辑 `.env` 文件**:
    使用文本编辑器打开 `backend/.env` 文件，并填入以下必要信息：

    ```dotenv
    # OpenAI API Settings
    # 必填。你的 OpenAI API 密钥。
    OPENAI_API_KEY="your_openai_api_key_here"
    # 如果你使用代理或第三方服务，请修改此 URL。
    OPENAI_BASE_URL="https://api.openai.com/v1"
    # 指定用于生成游戏内容的模型。
    OPENAI_MODEL="gpt-4o"
    # 指定用于作弊检查的模型。
    OPENAI_MODEL_CHEAT_CHECK="gpt-3.5-turbo"

    # JWT Settings for OAuth2
    # 必填。一个长而随机的字符串，用于签名 JWT。
    # 你可以使用 `openssl rand -hex 32` 生成。
    SECRET_KEY="a_very_secret_key_that_should_be_changed"
    ALGORITHM="HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES=600

    # Linux.do OAuth Settings
    # 必填。在 Linux.do 注册应用后获取的 Client ID。
    LINUXDO_CLIENT_ID="your_linuxdo_client_id"
    # 必填。在 Linux.do 注册应用后获取的 Client Secret。
    LINUXDO_CLIENT_SECRET="your_linuxdo_client_secret"
    LINUXDO_SCOPE="read"

    # Database
    # 数据库文件路径。默认指向项目根目录下的 veloera.db 文件。
    DATABASE_URL="sqlite:///veloera.db"

    # Server Settings
    # 服务器监听的主机和端口。
    HOST="0.0.0.0"
    PORT=8000
    # 是否开启热重载。在生产环境中建议设为 false。
    UVICORN_RELOAD=true
    ```

    **重要**:
    - **`SECRET_KEY`**: 必须更改为一个强随机字符串，否则会存在安全风险。
    - **`LINUXDO_CLIENT_ID` / `SECRET`**: 你需要在 [Linux.do](https://linux.do/) 的用户设置中注册一个新的 OAuth2 应用来获取这些凭证。**回调 URL (Redirect URI)** 必须设置为 `http://<你的域名或IP>:<端口>/callback`。例如：`http://localhost:8000/callback`。

### 5. 运行应用

提供了一个 `run.sh` 脚本来方便地启动应用。

首先，给脚本添加执行权限：
```bash
chmod +x run.sh
```

然后，运行脚本：
```bash
./run.sh
```

脚本会自动加载 `backend/.env` 文件中的环境变量，并使用 `uvicorn` 启动 FastAPI 服务器。

服务器成功启动后，您应该会看到类似以下的输出：
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

现在，在您的浏览器中打开 `http://localhost:8000` 即可开始游戏。

## 📁 项目结构

```
.
├── backend/
│   ├── .env.example        # 环境变量示例文件
│   ├── requirements.txt    # Python 依赖
│   └── app/
│       ├── __init__.py
│       ├── main.py         # FastAPI 应用主入口
│       ├── config.py       # Pydantic 配置模型
│       ├── auth.py         # 认证和 OAuth 逻辑
│       ├── game_logic.py   # 核心游戏逻辑
│       ├── websocket_manager.py # WebSocket 连接管理
│       ├── state_manager.py  # 游戏状态的保存与加载
│       ├── db.py           # 数据库连接
│       ├── openai_client.py # OpenAI API 客户端
│       ├── cheat_check.py  # 作弊检查逻辑
│       ├── redemption.py   # 兑换码生成逻辑
│       └── prompts/        # 存放 AI 系统提示的目录
│
├── frontend/
│   ├── index.html          # 主 HTML 文件
│   ├── style.css           # CSS 样式文件
│   └── app.js              # 前端 JavaScript 逻辑
│
├── scripts/
│   └── generate_token.py   # 用于生成测试 token 的脚本
│
├── .gitignore
├── README.md               # 本文档
└── run.sh                  # 应用启动脚本
```
