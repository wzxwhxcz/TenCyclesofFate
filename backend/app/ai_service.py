"""
统一的 AI 服务接口
支持 OpenAI 和 Anthropic API
"""
import logging
from typing import Optional, List, Dict, Any
from enum import Enum

from .config import settings
from . import openai_client
from . import anthropic_client

# --- Logging ---
logger = logging.getLogger(__name__)


class AIProvider(Enum):
    """AI 服务提供商枚举"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AUTO = "auto"  # 自动选择可用的提供商


class AIService:
    """统一的 AI 服务接口"""
    
    def __init__(self):
        self.provider = self._determine_provider()
        logger.info(f"AI 服务初始化，使用提供商: {self.provider}")
    
    def _determine_provider(self) -> Optional[AIProvider]:
        """根据配置确定使用哪个 AI 提供商"""
        provider_str = settings.AI_PROVIDER.lower() if hasattr(settings, 'AI_PROVIDER') else "auto"
        
        if provider_str == "openai":
            if openai_client.client:
                return AIProvider.OPENAI
            else:
                logger.warning("指定了 OpenAI 但客户端未初始化")
                return None
        
        elif provider_str == "anthropic":
            if anthropic_client.client:
                return AIProvider.ANTHROPIC
            else:
                logger.warning("指定了 Anthropic 但客户端未初始化")
                return None
        
        else:  # auto 或未指定
            # 优先尝试 OpenAI
            if openai_client.client:
                return AIProvider.OPENAI
            # 然后尝试 Anthropic
            elif anthropic_client.client:
                return AIProvider.ANTHROPIC
            else:
                logger.error("没有可用的 AI 提供商")
                return None
    
    async def get_response(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        model: Optional[str] = None,
        force_json: bool = True,
        provider: Optional[AIProvider] = None,
    ) -> str:
        """
        获取 AI 响应的统一接口
        
        Args:
            prompt: 用户提示
            history: 对话历史
            model: 指定模型（可选）
            force_json: 是否强制返回 JSON 格式
            provider: 指定使用的提供商（可选）
        
        Returns:
            AI 响应字符串
        """
        # 确定使用的提供商
        use_provider = provider or self.provider
        
        if not use_provider:
            return "错误：没有可用的 AI 服务提供商。请检查配置。"
        
        # 根据提供商调用相应的客户端
        if use_provider == AIProvider.OPENAI:
            if not openai_client.client:
                # 如果 OpenAI 不可用，尝试 Anthropic
                if anthropic_client.client:
                    logger.info("OpenAI 不可用，切换到 Anthropic")
                    use_provider = AIProvider.ANTHROPIC
                else:
                    return "错误：OpenAI 客户端未初始化。"
        
        if use_provider == AIProvider.ANTHROPIC:
            if not anthropic_client.client:
                # 如果 Anthropic 不可用，尝试 OpenAI
                if openai_client.client:
                    logger.info("Anthropic 不可用，切换到 OpenAI")
                    use_provider = AIProvider.OPENAI
                else:
                    return "错误：Anthropic 客户端未初始化。"
        
        # 调用相应的 API
        try:
            if use_provider == AIProvider.OPENAI:
                return await openai_client.get_ai_response(
                    prompt=prompt,
                    history=history,
                    model=model or settings.OPENAI_MODEL,
                    force_json=force_json
                )
            elif use_provider == AIProvider.ANTHROPIC:
                return await anthropic_client.get_ai_response(
                    prompt=prompt,
                    history=history,
                    model=model or settings.ANTHROPIC_MODEL if hasattr(settings, 'ANTHROPIC_MODEL') else None,
                    force_json=force_json
                )
            else:
                return "错误：未知的 AI 提供商。"
        
        except Exception as e:
            logger.error(f"调用 AI 服务时出错: {e}", exc_info=True)
            # 尝试切换到另一个提供商
            if use_provider == AIProvider.OPENAI and anthropic_client.client:
                logger.info("OpenAI 调用失败，尝试 Anthropic")
                try:
                    return await anthropic_client.get_ai_response(
                        prompt=prompt,
                        history=history,
                        model=model or settings.ANTHROPIC_MODEL if hasattr(settings, 'ANTHROPIC_MODEL') else None,
                        force_json=force_json
                    )
                except Exception as e2:
                    logger.error(f"Anthropic 也失败了: {e2}")
                    return f"错误：所有 AI 服务都失败了。最后的错误: {e2}"
            
            elif use_provider == AIProvider.ANTHROPIC and openai_client.client:
                logger.info("Anthropic 调用失败，尝试 OpenAI")
                try:
                    return await openai_client.get_ai_response(
                        prompt=prompt,
                        history=history,
                        model=model or settings.OPENAI_MODEL,
                        force_json=force_json
                    )
                except Exception as e2:
                    logger.error(f"OpenAI 也失败了: {e2}")
                    return f"错误：所有 AI 服务都失败了。最后的错误: {e2}"
            
            return f"错误：AI 服务调用失败: {e}"


# 创建全局 AI 服务实例
ai_service = AIService()


async def get_ai_response(
    prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
    model: Optional[str] = None,
    force_json: bool = True,
    provider: Optional[str] = None,
) -> str:
    """
    便捷函数，直接调用全局 AI 服务
    
    Args:
        prompt: 用户提示
        history: 对话历史
        model: 指定模型（可选）
        force_json: 是否强制返回 JSON 格式
        provider: 指定使用的提供商（"openai" 或 "anthropic"，可选）
    
    Returns:
        AI 响应字符串
    """
    provider_enum = None
    if provider:
        provider_lower = provider.lower()
        if provider_lower == "openai":
            provider_enum = AIProvider.OPENAI
        elif provider_lower == "anthropic":
            provider_enum = AIProvider.ANTHROPIC
    
    return await ai_service.get_response(
        prompt=prompt,
        history=history,
        model=model,
        force_json=force_json,
        provider=provider_enum
    )


# 保持向后兼容性
async def get_openai_response(
    prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
    model: Optional[str] = None,
    force_json: bool = True,
) -> str:
    """向后兼容的 OpenAI 响应函数"""
    return await get_ai_response(
        prompt=prompt,
        history=history,
        model=model,
        force_json=force_json,
        provider="openai"
    )


async def get_anthropic_response(
    prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
    model: Optional[str] = None,
    force_json: bool = True,
) -> str:
    """Anthropic 响应函数"""
    return await get_ai_response(
        prompt=prompt,
        history=history,
        model=model,
        force_json=force_json,
        provider="anthropic"
    )