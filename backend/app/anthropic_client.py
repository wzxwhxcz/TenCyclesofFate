import logging
import asyncio
import random
import json
from typing import Optional, List, Dict, Any
from anthropic import AsyncAnthropic, APIError

from .config import settings

# --- Logging ---
logger = logging.getLogger(__name__)

# --- Client Initialization ---
client: Optional[AsyncAnthropic] = None
client_validated = False  # 标记客户端是否已验证

async def validate_anthropic_client():
    """验证 Anthropic 客户端和 API key 的有效性"""
    global client, client_validated
    
    if not client:
        return False
    
    try:
        # 使用用户配置的模型进行验证
        model = settings.ANTHROPIC_MODEL if hasattr(settings, 'ANTHROPIC_MODEL') else "claude-3-opus-20240229"
        
        # 如果配置了多个模型（逗号分隔），使用第一个
        if "," in model:
            model = model.split(",")[0].strip()
        
        # 尝试一个简单的 API 调用来验证 key
        response = await client.messages.create(
            model=model,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1
        )
        client_validated = True
        logger.info(f"Anthropic API key 验证成功，使用模型: {model}")
        return True
    except APIError as e:
        if e.status_code == 401:
            logger.error(f"Anthropic API key 无效: {e}")
            client = None  # 清除无效的客户端
            client_validated = False
            return False
        else:
            # 其他错误可能是临时的，保留客户端
            logger.warning(f"Anthropic API 验证时出现错误: {e}")
            client_validated = False
            return False
    except Exception as e:
        logger.error(f"验证 Anthropic 客户端时出现意外错误: {e}")
        client_validated = False
        return False

# 初始化客户端
if settings.ANTHROPIC_API_KEY and settings.ANTHROPIC_API_KEY != "your_anthropic_api_key_here":
    try:
        # 构建客户端参数
        client_kwargs = {
            "api_key": settings.ANTHROPIC_API_KEY,
        }
        
        # 如果设置了自定义基础 URL，则使用它
        if settings.ANTHROPIC_BASE_URL:
            client_kwargs["base_url"] = settings.ANTHROPIC_BASE_URL
            logger.info(f"使用自定义 Anthropic 基础 URL: {settings.ANTHROPIC_BASE_URL}")
        
        client = AsyncAnthropic(**client_kwargs)
        logger.info("Anthropic 客户端对象创建成功，等待验证。")
    except Exception as e:
        logger.error(f"创建 Anthropic 客户端失败: {e}")
        client = None
else:
    logger.warning("ANTHROPIC_API_KEY 未设置或为占位符，Anthropic 客户端未初始化。")


def _extract_json_from_response(response_str: str) -> Optional[str]:
    """从响应中提取 JSON 内容"""
    if "```json" in response_str:
        start_pos = response_str.find("```json") + 7
        end_pos = response_str.find("```", start_pos)
        if end_pos != -1:
            return response_str[start_pos:end_pos].strip()
    start_pos = response_str.find("{")
    end_pos = response_str.rfind("}")
    if start_pos != -1 and end_pos != -1 and end_pos > start_pos:
        return response_str[start_pos : end_pos + 1].strip()
    return None


def _convert_messages_format(messages: List[Dict[str, str]]) -> tuple[str, List[Dict[str, str]]]:
    """
    将 OpenAI 格式的消息转换为 Anthropic 格式
    Anthropic 需要系统提示单独传递，且不支持 system role 在消息列表中
    """
    system_prompt = ""
    converted_messages = []
    
    for msg in messages:
        if msg["role"] == "system":
            # Anthropic 的系统提示需要单独处理
            if system_prompt:
                system_prompt += "\n\n" + msg["content"]
            else:
                system_prompt = msg["content"]
        elif msg["role"] == "user":
            converted_messages.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant":
            converted_messages.append({"role": "assistant", "content": msg["content"]})
    
    # 确保消息列表以 user 消息开始
    if converted_messages and converted_messages[0]["role"] != "user":
        converted_messages.insert(0, {"role": "user", "content": "继续"})
    
    return system_prompt, converted_messages


async def get_ai_response(
    prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
    model: str = None,
    force_json: bool = True,
) -> str:
    """
    从 Anthropic API 获取响应。

    Args:
        prompt: 用户的提示。
        history: 对话的先前消息列表。
        model: 使用的模型，默认使用配置中的模型。
        force_json: 是否强制返回 JSON 格式。

    Returns:
        AI 的响应消息，或错误字符串。
    """
    if not client:
        return "错误：Anthropic客户端未初始化。请在 backend/.env 文件中正确设置您的 ANTHROPIC_API_KEY。"

    if model is None:
        model = settings.ANTHROPIC_MODEL

    messages = []
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    # 转换消息格式
    system_prompt, anthropic_messages = _convert_messages_format(messages)

    # 计算令牌数（粗略估计）
    total_tokens = len(system_prompt) + sum(len(m["content"]) for m in anthropic_messages)
    logger.debug(f"发送到Anthropic的消息总令牌数（估计）: {total_tokens}")

    # 如果历史记录过长，随机删除一些消息
    _max_loop = 10000
    while total_tokens > 100000 and history and _max_loop > 0:
        if len(history) > 2:  # 保留至少一些上下文
            random_id = random.randint(1, len(history) - 1)
            if history[random_id].get("role") != "system":  # 不删除系统消息
                total_tokens -= len(history[random_id]["content"])
                history.pop(random_id)
                # 重新转换消息
                messages = []
                if history:
                    messages.extend(history)
                messages.append({"role": "user", "content": prompt})
                system_prompt, anthropic_messages = _convert_messages_format(messages)
        _max_loop -= 1

    if _max_loop == 0:
        raise ValueError("对话历史过长，无法通过删除消息节省足够的令牌。")

    max_retries = 7
    base_delay = 1  # 基础延迟时间（秒）

    for attempt in range(max_retries):
        _model = model
        # 支持多模型配置
        if "," in model:
            model_options = [m.strip() for m in model.split(",") if m.strip()]
            if model_options:
                if attempt == 0:
                    _model = model_options[0]
                    logger.debug(f"首次尝试使用模型: {_model}")
                else:
                    _model = random.choice(model_options)
                    logger.debug(f"从列表中选择模型: {_model}")
        
        try:
            # 调用 Anthropic API
            kwargs = {
                "model": _model,
                "messages": anthropic_messages,
                "max_tokens": 4096,
            }
            
            if system_prompt:
                kwargs["system"] = system_prompt
            
            response = await client.messages.create(**kwargs)
            
            # 提取响应内容
            ai_message = response.content[0].text if response.content else ""
            
            if not ai_message:
                raise ValueError("AI 响应为空")
            
            ret = ai_message.strip()
            
            # 处理思考标签（如果存在）
            if "<think>" in ret and "</think>" in ret:
                ret = ret[ret.rfind("</think>") + 8:].strip()

            if force_json:
                try:
                    json_str = _extract_json_from_response(ret)
                    if json_str:
                        json_part = json.loads(json_str)
                        return ret
                    else:
                        raise ValueError("未找到有效的JSON部分")
                except Exception as e:
                    raise ValueError(f"解析AI响应时出错: {e}")
            else:
                return ret

        except APIError as e:
            logger.error(f"Anthropic API 错误 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return f"错误：AI服务出现问题。详情: {e}"

            # 指数退避延迟
            delay = base_delay * (2**attempt) + random.uniform(0, 1)
            await asyncio.sleep(delay)

        except Exception as e:
            logger.error(
                f"联系Anthropic时发生意外错误 (尝试 {attempt + 1}/{max_retries}): {e}"
            )
            logger.error("错误详情：", exc_info=True)
            if attempt == max_retries - 1:
                return f"错误：发生意外错误。详情: {e}"

            # 指数退避延迟
            delay = base_delay * (2**attempt) + random.uniform(0, 1)
            await asyncio.sleep(delay)

    return "错误：达到最大重试次数，无法获取AI响应。"


async def get_ai_response_stream(
    prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
    model: str = None,
    force_json: bool = True,
):
    """
    从 Anthropic API 获取流式响应。
    
    Args:
        prompt: 用户的提示。
        history: 对话的先前消息列表。
        model: 使用的模型。
        force_json: 是否强制返回 JSON 格式。
    
    Yields:
        流式响应的文本片段。
    """
    if not client:
        yield "错误：Anthropic客户端未初始化。请在 backend/.env 文件中正确设置您的 ANTHROPIC_API_KEY。"
        return

    if model is None:
        model = settings.ANTHROPIC_MODEL

    messages = []
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    # 转换消息格式
    system_prompt, anthropic_messages = _convert_messages_format(messages)

    # 计算令牌数（粗略估计）
    total_tokens = len(system_prompt) + sum(len(m["content"]) for m in anthropic_messages)
    logger.debug(f"发送到Anthropic的消息总令牌数（估计）: {total_tokens}")

    # 如果历史记录过长，随机删除一些消息
    _max_loop = 10000
    while total_tokens > 100000 and history and _max_loop > 0:
        if len(history) > 2:  # 保留至少一些上下文
            random_id = random.randint(1, len(history) - 1)
            if history[random_id].get("role") != "system":  # 不删除系统消息
                total_tokens -= len(history[random_id]["content"])
                history.pop(random_id)
                # 重新转换消息
                messages = []
                if history:
                    messages.extend(history)
                messages.append({"role": "user", "content": prompt})
                system_prompt, anthropic_messages = _convert_messages_format(messages)
        _max_loop -= 1

    if _max_loop == 0:
        yield "错误：对话历史过长，无法通过删除消息节省足够的令牌。"
        return

    max_retries = 7
    base_delay = 1

    for attempt in range(max_retries):
        _model = model
        # 支持多模型配置
        if "," in model:
            model_options = [m.strip() for m in model.split(",") if m.strip()]
            if model_options:
                if attempt == 0:
                    _model = model_options[0]
                    logger.debug(f"首次尝试使用模型: {_model}")
                else:
                    _model = random.choice(model_options)
                    logger.debug(f"从列表中选择模型: {_model}")
        
        try:
            # 调用 Anthropic API 的流式接口
            kwargs = {
                "model": _model,
                "messages": anthropic_messages,
                "max_tokens": 4096,
                "stream": True,  # 启用流式响应
            }
            
            if system_prompt:
                kwargs["system"] = system_prompt
            
            stream = await client.messages.create(**kwargs)
            
            full_response = ""
            async for event in stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, 'text'):
                        content = event.delta.text
                        full_response += content
                        yield content
            
            # 处理完整响应
            if not full_response:
                raise ValueError("AI 响应为空")
            
            # 如果需要验证JSON格式
            if force_json:
                # 处理思考标签（如果存在）
                if "<think>" in full_response and "</think>" in full_response:
                    full_response = full_response[full_response.rfind("</think>") + 8:].strip()
                
                # 验证JSON格式
                json_str = _extract_json_from_response(full_response)
                if json_str:
                    try:
                        json.loads(json_str)
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON解析失败: {e}")
                        yield f"\n错误：AI响应不是有效的JSON格式"
            
            return  # 成功完成
            
        except APIError as e:
            logger.error(f"Anthropic API 错误 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                yield f"\n错误：AI服务出现问题。详情: {e}"
                return
            
            delay = base_delay * (2**attempt) + random.uniform(0, 1)
            await asyncio.sleep(delay)
            
        except Exception as e:
            logger.error(f"联系Anthropic时发生意外错误 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                yield f"\n错误：发生意外错误。详情: {e}"
                return
            
            delay = base_delay * (2**attempt) + random.uniform(0, 1)
            await asyncio.sleep(delay)