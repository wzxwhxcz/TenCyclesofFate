# AI 服务提供商配置指南

本项目现已支持多个 AI 服务提供商，包括 OpenAI 和 Anthropic Claude。您可以根据需要选择使用不同的 AI 服务。

## 支持的 AI 服务

### 1. OpenAI（包括兼容接口）
- **原生 OpenAI API**
- **Azure OpenAI**
- **本地模型**（Ollama、LocalAI、Text Generation WebUI 等）
- **第三方代理**（OpenRouter、One API 等）
- **国内服务**（通义千问、文心一言等，需提供 OpenAI 兼容接口）

### 2. Anthropic Claude
- **Claude 3 系列模型**（Opus、Sonnet、Haiku）
- **支持自定义端点**（用于代理或私有部署）

## 配置方法

### 步骤 1：安装依赖

确保已安装所需的 Python 包：

```bash
cd backend
pip install -r requirements.txt
```

### 步骤 2：配置环境变量

在 `backend/.env` 文件中配置相应的环境变量：

#### 使用 OpenAI：

```env
# 选择 AI 提供商
AI_PROVIDER="openai"

# OpenAI 配置
OPENAI_API_KEY="your_openai_api_key_here"
OPENAI_BASE_URL="https://api.openai.com/v1"
OPENAI_MODEL="gpt-3.5-turbo"
```

#### 使用 Anthropic Claude：

```env
# 选择 AI 提供商
AI_PROVIDER="anthropic"

# Anthropic 配置
ANTHROPIC_API_KEY="your_anthropic_api_key_here"
ANTHROPIC_MODEL="claude-3-opus-20240229"
# 可选：自定义端点（用于代理或私有部署）
# ANTHROPIC_BASE_URL="https://your-proxy.com/v1"
```

#### 使用 Anthropic 代理服务：

```env
# 选择 AI 提供商
AI_PROVIDER="anthropic"

# 使用自定义代理端点
ANTHROPIC_API_KEY="your_api_key_here"
ANTHROPIC_BASE_URL="https://claude-proxy.example.com"
ANTHROPIC_MODEL="claude-3-opus-20240229"
```

#### 自动选择（推荐）：

```env
# 自动选择可用的提供商
AI_PROVIDER="auto"

# 配置多个提供商，系统会自动选择可用的
OPENAI_API_KEY="your_openai_api_key_here"
ANTHROPIC_API_KEY="your_anthropic_api_key_here"
```

## 高级配置

### 1. 使用多个模型（故障转移）

您可以配置多个模型，系统会在主模型失败时自动切换：

```env
# OpenAI 多模型配置
OPENAI_MODEL="gpt-3.5-turbo,gpt-4,gpt-4-turbo"

# Anthropic 多模型配置
ANTHROPIC_MODEL="claude-3-opus-20240229,claude-3-sonnet-20240229"
```

### 2. 使用本地模型（通过 Ollama）

```env
AI_PROVIDER="openai"
OPENAI_BASE_URL="http://localhost:11434/v1"
OPENAI_API_KEY="ollama"  # Ollama 不需要真实的 API key
OPENAI_MODEL="llama2,mistral,qwen"
```

### 3. 使用第三方代理

#### OpenRouter 示例：
```env
AI_PROVIDER="openai"
OPENAI_BASE_URL="https://openrouter.ai/api/v1"
OPENAI_API_KEY="your_openrouter_api_key"
OPENAI_MODEL="anthropic/claude-3-opus,openai/gpt-4"
```

#### 国内代理示例：

##### OpenAI 代理：
```env
AI_PROVIDER="openai"
OPENAI_BASE_URL="https://api.your-proxy.com/v1"
OPENAI_API_KEY="your_proxy_api_key"
OPENAI_MODEL="gpt-3.5-turbo"
```

##### Anthropic 代理：
```env
AI_PROVIDER="anthropic"
ANTHROPIC_BASE_URL="https://claude-api.your-proxy.com"
ANTHROPIC_API_KEY="your_proxy_api_key"
ANTHROPIC_MODEL="claude-3-opus-20240229"
```

### 4. 混合使用多个服务

配置多个服务，让系统自动选择：

```env
# 自动选择可用的服务
AI_PROVIDER="auto"

# OpenAI 配置（通过代理）
OPENAI_API_KEY="your_openai_key"
OPENAI_BASE_URL="https://openai-proxy.example.com/v1"
OPENAI_MODEL="gpt-4-turbo"

# Anthropic 配置（通过代理）
ANTHROPIC_API_KEY="your_anthropic_key"
ANTHROPIC_BASE_URL="https://claude-proxy.example.com"
ANTHROPIC_MODEL="claude-3-opus-20240229"
```

## 功能特性

### 1. 自动故障转移
当配置了 `AI_PROVIDER="auto"` 时，系统会：
- 优先尝试 OpenAI
- 如果 OpenAI 不可用，自动切换到 Anthropic
- 在 API 调用失败时，自动尝试备用提供商

### 2. 统一接口
无论使用哪个提供商，代码调用方式保持一致：

```python
from backend.app.ai_service import get_ai_response

# 自动使用配置的提供商
response = await get_ai_response(
    prompt="你的提示词",
    history=[{"role": "user", "content": "历史消息"}]
)

# 指定使用特定提供商
response = await get_ai_response(
    prompt="你的提示词",
    provider="anthropic"  # 或 "openai"
)
```

### 3. 向后兼容
原有的 OpenAI 调用代码无需修改，系统会自动路由到新的统一接口。

## 注意事项

1. **API Key 安全**：请勿将 API Key 提交到版本控制系统
2. **费用控制**：不同的模型有不同的费用，请根据需求选择
3. **速率限制**：系统内置了重试机制和指数退避策略
4. **模型差异**：不同模型的响应风格可能有所不同，可能需要调整提示词

## 故障排查

### 问题：客户端未初始化
**解决方案**：检查环境变量配置是否正确，API Key 是否有效

### 问题：API 调用失败
**解决方案**：
1. 检查网络连接
2. 验证 API Key 是否有效
3. 确认 BASE_URL 是否正确
4. 查看日志文件获取详细错误信息

### 问题：响应格式错误
**解决方案**：不同的模型可能需要不同的提示词格式，尝试调整提示词

## 更新日志

- **2024-10-04**：添加 Anthropic Claude 支持
- **2024-10-04**：实现统一的 AI 服务接口
- **2024-10-04**：支持自动故障转移和多模型配置