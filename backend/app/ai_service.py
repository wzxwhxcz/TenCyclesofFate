"""
统一的 AI 服务接口
支持 OpenAI 和 Anthropic API
"""
import logging
from typing import Optional, List, Dict, Any
from enum import Enum
import asyncio
from datetime import datetime, timedelta

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


class ProviderStatus:
    """提供商状态跟踪"""
    def __init__(self):
        self.failure_count = 0
        self.last_failure_time = None
        self.last_success_time = None
        self.is_validated = False
        self.consecutive_failures = 0
        
    def record_success(self):
        """记录成功调用"""
        self.failure_count = max(0, self.failure_count - 1)  # 成功后减少失败计数
        self.consecutive_failures = 0
        self.last_success_time = datetime.now()
        
    def record_failure(self):
        """记录失败调用"""
        self.failure_count += 1
        self.consecutive_failures += 1
        self.last_failure_time = datetime.now()
        
    def is_available(self) -> bool:
        """判断提供商是否可用"""
        # 如果连续失败超过3次，暂时禁用
        if self.consecutive_failures >= 3:
            # 检查是否已经过了冷却期（5分钟）
            if self.last_failure_time:
                cooldown_period = timedelta(minutes=5)
                if datetime.now() - self.last_failure_time > cooldown_period:
                    # 重置连续失败计数，给予重试机会
                    self.consecutive_failures = 0
                    return True
            return False
        return True


class AIService:
    """统一的 AI 服务接口"""
    
    def __init__(self):
        self.provider_status = {
            AIProvider.OPENAI: ProviderStatus(),
            AIProvider.ANTHROPIC: ProviderStatus()
        }
        self.provider = None
        self.validated_providers = set()
        self._initialized = False
        # 不在这里创建异步任务，而是在第一次使用时初始化
    
    async def _async_init(self):
        """异步初始化，验证客户端"""
        if self._initialized:
            return
        self._initialized = True
        await self._validate_clients()
        self.provider = await self._determine_provider()
        logger.info(f"AI 服务初始化完成，使用提供商: {self.provider}")
    
    async def _validate_clients(self):
        """验证所有配置的客户端"""
        # 验证 OpenAI
        if openai_client.client:
            if await openai_client.validate_openai_client():
                self.provider_status[AIProvider.OPENAI].is_validated = True
                self.validated_providers.add(AIProvider.OPENAI)
                logger.info("OpenAI 客户端验证通过")
            else:
                logger.warning("OpenAI 客户端验证失败")
                openai_client.client = None
        
        # 验证 Anthropic
        if anthropic_client.client:
            if await anthropic_client.validate_anthropic_client():
                self.provider_status[AIProvider.ANTHROPIC].is_validated = True
                self.validated_providers.add(AIProvider.ANTHROPIC)
                logger.info("Anthropic 客户端验证通过")
            else:
                logger.warning("Anthropic 客户端验证失败")
                anthropic_client.client = None
    
    async def _determine_provider(self) -> Optional[AIProvider]:
        """根据配置和验证状态确定使用哪个 AI 提供商"""
        provider_str = settings.AI_PROVIDER.lower() if hasattr(settings, 'AI_PROVIDER') else "auto"
        
        if provider_str == "openai":
            if AIProvider.OPENAI in self.validated_providers:
                return AIProvider.OPENAI
            else:
                logger.warning("指定了 OpenAI 但客户端未通过验证")
                # 尝试使用 Anthropic 作为后备
                if AIProvider.ANTHROPIC in self.validated_providers:
                    logger.info("切换到 Anthropic 作为后备提供商")
                    return AIProvider.ANTHROPIC
                return None
        
        elif provider_str == "anthropic":
            if AIProvider.ANTHROPIC in self.validated_providers:
                return AIProvider.ANTHROPIC
            else:
                logger.warning("指定了 Anthropic 但客户端未通过验证")
                # 尝试使用 OpenAI 作为后备
                if AIProvider.OPENAI in self.validated_providers:
                    logger.info("切换到 OpenAI 作为后备提供商")
                    return AIProvider.OPENAI
                return None
        
        else:  # auto 或未指定
            # 基于可用性和成功率选择最佳提供商
            available_providers = []
            
            for provider in [AIProvider.OPENAI, AIProvider.ANTHROPIC]:
                if provider in self.validated_providers:
                    status = self.provider_status[provider]
                    if status.is_available():
                        available_providers.append(provider)
            
            if not available_providers:
                logger.error("没有可用的 AI 提供商")
                return None
            
            # 选择失败次数最少的提供商
            best_provider = min(
                available_providers,
                key=lambda p: self.provider_status[p].failure_count
            )
            
            return best_provider
    
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
        # 如果还没有初始化完成，进行初始化
        if not self._initialized:
            await self._async_init()
        
        # 确定使用的提供商
        use_provider = provider or self.provider
        
        if not use_provider:
            # 尝试重新选择可用的提供商
            use_provider = await self._determine_provider()
            if not use_provider:
                return "错误：没有可用的 AI 服务提供商。请检查配置。"
        
        # 检查提供商状态
        if use_provider in self.provider_status:
            status = self.provider_status[use_provider]
            if not status.is_available():
                logger.warning(f"{use_provider.value} 暂时不可用，尝试切换提供商")
                # 尝试切换到另一个提供商
                for alt_provider in [AIProvider.OPENAI, AIProvider.ANTHROPIC]:
                    if alt_provider != use_provider and alt_provider in self.validated_providers:
                        alt_status = self.provider_status[alt_provider]
                        if alt_status.is_available():
                            logger.info(f"切换到 {alt_provider.value}")
                            use_provider = alt_provider
                            break
        
        # 获取可用的提供商列表（用于故障转移）
        fallback_providers = []
        for p in [AIProvider.OPENAI, AIProvider.ANTHROPIC]:
            if p != use_provider and p in self.validated_providers:
                if self.provider_status[p].is_available():
                    fallback_providers.append(p)
        
        # 尝试调用主提供商
        try:
            result = await self._call_provider(
                use_provider, prompt, history, model, force_json
            )
            # 记录成功
            self.provider_status[use_provider].record_success()
            return result
            
        except Exception as e:
            logger.error(f"{use_provider.value} 调用失败: {e}")
            # 记录失败
            self.provider_status[use_provider].record_failure()
            
            # 尝试故障转移到其他提供商
            for fallback in fallback_providers:
                logger.info(f"尝试故障转移到 {fallback.value}")
                try:
                    result = await self._call_provider(
                        fallback, prompt, history, model, force_json
                    )
                    # 记录成功
                    self.provider_status[fallback].record_success()
                    # 更新默认提供商为成功的提供商
                    self.provider = fallback
                    return result
                except Exception as e2:
                    logger.error(f"{fallback.value} 也失败了: {e2}")
                    self.provider_status[fallback].record_failure()
            
            return f"错误：所有 AI 服务都失败了。最后的错误: {e}"
    
    async def _call_provider(
        self,
        provider: AIProvider,
        prompt: str,
        history: Optional[List[Dict[str, str]]],
        model: Optional[str],
        force_json: bool
    ) -> str:
        """调用指定的 AI 提供商"""
        if provider == AIProvider.OPENAI:
            if not openai_client.client:
                raise ValueError("OpenAI 客户端未初始化")
            return await openai_client.get_ai_response(
                prompt=prompt,
                history=history,
                model=model or settings.OPENAI_MODEL,
                force_json=force_json
            )
        elif provider == AIProvider.ANTHROPIC:
            if not anthropic_client.client:
                raise ValueError("Anthropic 客户端未初始化")
            return await anthropic_client.get_ai_response(
                prompt=prompt,
                history=history,
                model=model or settings.ANTHROPIC_MODEL if hasattr(settings, 'ANTHROPIC_MODEL') else None,
                force_json=force_json
            )
        else:
            raise ValueError(f"未知的 AI 提供商: {provider}")


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


async def get_ai_response_stream(
    prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
    model: Optional[str] = None,
    force_json: bool = True,
    provider: Optional[str] = None,
):
    """
    获取 AI 流式响应的统一接口
    
    Args:
        prompt: 用户提示
        history: 对话历史
        model: 指定模型（可选）
        force_json: 是否强制返回 JSON 格式
        provider: 指定使用的提供商（"openai" 或 "anthropic"，可选）
    
    Yields:
        流式响应的文本片段
    """
    # 如果还没有初始化完成，进行初始化
    if not ai_service._initialized:
        await ai_service._async_init()
    
    # 确定使用的提供商
    provider_enum = None
    if provider:
        provider_lower = provider.lower()
        if provider_lower == "openai":
            provider_enum = AIProvider.OPENAI
        elif provider_lower == "anthropic":
            provider_enum = AIProvider.ANTHROPIC
    
    use_provider = provider_enum or ai_service.provider
    
    if not use_provider:
        # 尝试重新选择可用的提供商
        use_provider = await ai_service._determine_provider()
        if not use_provider:
            yield "错误：没有可用的 AI 服务提供商。请检查配置。"
            return
    
    # 检查提供商状态
    if use_provider in ai_service.provider_status:
        status = ai_service.provider_status[use_provider]
        if not status.is_available():
            logger.warning(f"{use_provider.value} 暂时不可用，尝试切换提供商")
            # 尝试切换到另一个提供商
            for alt_provider in [AIProvider.OPENAI, AIProvider.ANTHROPIC]:
                if alt_provider != use_provider and alt_provider in ai_service.validated_providers:
                    alt_status = ai_service.provider_status[alt_provider]
                    if alt_status.is_available():
                        logger.info(f"切换到 {alt_provider.value}")
                        use_provider = alt_provider
                        break
    
    # 获取可用的提供商列表（用于故障转移）
    fallback_providers = []
    for p in [AIProvider.OPENAI, AIProvider.ANTHROPIC]:
        if p != use_provider and p in ai_service.validated_providers:
            if ai_service.provider_status[p].is_available():
                fallback_providers.append(p)
    
    # 尝试调用主提供商
    try:
        if use_provider == AIProvider.OPENAI:
            if not openai_client.client:
                raise ValueError("OpenAI 客户端未初始化")
            async for chunk in openai_client.get_ai_response_stream(
                prompt=prompt,
                history=history,
                model=model or settings.OPENAI_MODEL,
                force_json=force_json
            ):
                yield chunk
            # 记录成功
            ai_service.provider_status[use_provider].record_success()
            
        elif use_provider == AIProvider.ANTHROPIC:
            if not anthropic_client.client:
                raise ValueError("Anthropic 客户端未初始化")
            async for chunk in anthropic_client.get_ai_response_stream(
                prompt=prompt,
                history=history,
                model=model or settings.ANTHROPIC_MODEL if hasattr(settings, 'ANTHROPIC_MODEL') else None,
                force_json=force_json
            ):
                yield chunk
            # 记录成功
            ai_service.provider_status[use_provider].record_success()
        else:
            raise ValueError(f"未知的 AI 提供商: {use_provider}")
            
    except Exception as e:
        logger.error(f"{use_provider.value} 流式调用失败: {e}")
        # 记录失败
        ai_service.provider_status[use_provider].record_failure()
        
        # 尝试故障转移到其他提供商
        for fallback in fallback_providers:
            logger.info(f"尝试故障转移到 {fallback.value}")
            try:
                if fallback == AIProvider.OPENAI:
                    async for chunk in openai_client.get_ai_response_stream(
                        prompt=prompt,
                        history=history,
                        model=model or settings.OPENAI_MODEL,
                        force_json=force_json
                    ):
                        yield chunk
                elif fallback == AIProvider.ANTHROPIC:
                    async for chunk in anthropic_client.get_ai_response_stream(
                        prompt=prompt,
                        history=history,
                        model=model or settings.ANTHROPIC_MODEL if hasattr(settings, 'ANTHROPIC_MODEL') else None,
                        force_json=force_json
                    ):
                        yield chunk
                
                # 记录成功
                ai_service.provider_status[fallback].record_success()
                # 更新默认提供商为成功的提供商
                ai_service.provider = fallback
                return
            except Exception as e2:
                logger.error(f"{fallback.value} 也失败了: {e2}")
                ai_service.provider_status[fallback].record_failure()
        
        yield f"\n错误：所有 AI 服务都失败了。最后的错误: {e}"