import logging
from openai import AsyncOpenAI, APIError

from .config import settings
import asyncio
import random
import json

# --- Logging ---
logger = logging.getLogger(__name__)

# --- Client Initialization ---
client: AsyncOpenAI | None = None
if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "your_openai_api_key_here":
    try:
        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
        logger.info("OpenAI 客户端初始化成功。")
    except Exception as e:
        logger.error(f"初始化 OpenAI 客户端失败: {e}")
        client = None
else:
    logger.warning("OPENAI_API_KEY 未设置或为占位符，OpenAI 客户端未初始化。")


def _extract_json_from_response(response_str: str) -> str | None:
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


# --- Core Function ---
async def get_ai_response(
    prompt: str,
    history: list[dict] | None = None,
    model=settings.OPENAI_MODEL,
    force_json=True,
) -> str:
    """
    从 OpenAI API 获取响应。

    Args:
        prompt: 用户的提示。
        history: 对话的先前消息列表。

    Returns:
        AI 的响应消息，或错误字符串。
    """
    if not client:
        return "错误：OpenAI客户端未初始化。请在 backend/.env 文件中正确设置您的 OPENAI_API_KEY。"

    messages = []
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    total_tokens = sum(len(m["content"]) for m in messages)
    logger.debug(f"发送到OpenAI的消息总令牌数: {total_tokens}")

    _max_loop = 10000
    while total_tokens > 100000 and _max_loop > 0:
        random_id = random.randint(1, (len(history) - 1) // 2)
        # if history[random_id]["role"] != "system":  # 不删除系统消息
        total_tokens -= len(history[random_id]["content"])
        #     logger.warning("对话历史过长，随机删除一条消息以节省令牌。")
        history.pop(random_id)
        _max_loop -= 1

    if _max_loop == 0:
        raise ValueError("对话历史过长，无法通过删除消息节省足够的令牌。")

    max_retries = 7
    base_delay = 1  # 基础延迟时间（秒）

    for attempt in range(max_retries):
        _model = model
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
            response = await client.chat.completions.create(
                model=_model, messages=messages
            )
            ai_message = response.choices[0].message.content
            if not ai_message:
                raise ValueError("AI 响应为空")
            ret = ai_message.strip()
            if "<think>" in ret and "</think>" in ret:
                ret = ret[ret.rfind("</think>") + 8 :].strip()

            if force_json:
                try:
                    json_part = json.loads(_extract_json_from_response(ret))
                    if json_part:
                        return ret
                    else:
                        raise ValueError("未找到有效的JSON部分")
                except Exception as e:
                    raise ValueError(f"解析AI响应时出错: {e}")
            else:
                return ret

        except APIError as e:
            logger.error(f"OpenAI API 错误 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return f"错误：AI服务出现问题。详情: {e}"

            # 指数退避延迟
            delay = base_delay * (2**attempt) + random.uniform(0, 1)
            await asyncio.sleep(delay)

        except Exception as e:
            logger.error(
                f"联系OpenAI时发生意外错误 (尝试 {attempt + 1}/{max_retries}): {e}"
            )
            logger.error("错误详情：", exc_info=True)
            if attempt == max_retries - 1:
                return f"错误：发生意外错误。详情: {e}"

            # 指数退避延迟
            delay = base_delay * (2**attempt) + random.uniform(0, 1)
            await asyncio.sleep(delay)
