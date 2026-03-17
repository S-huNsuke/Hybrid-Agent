import logging

from langchain_openai import ChatOpenAI
from langchain_deepseek import ChatDeepSeek

from hybrid_agent.core.config import (
    settings,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_ADVANCED_MAX_TOKENS,
    DEFAULT_TIMEOUT
)

logger = logging.getLogger(__name__)


def _create_base_model() -> ChatOpenAI:
    """创建基础模型实例"""
    if settings.qwen_omni_api_key is None:
        logger.warning("QWEN_OMNI_API_KEY 未配置，base_model 可能无法正常工作")
    
    return ChatOpenAI(
        api_key=settings.qwen_omni_api_key,
        base_url=settings.qwen_omni_base_url,
        model_name="qwen3-omni-flash-2025-12-01",
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=DEFAULT_MAX_TOKENS,
        request_timeout=DEFAULT_TIMEOUT,
    )


def _create_advanced_model() -> ChatDeepSeek:
    """创建高级模型实例"""
    if settings.deepseek_api_key is None:
        logger.warning("DEEPSEEK_API_KEY 未配置，advanced_model 可能无法正常工作")
    
    return ChatDeepSeek(
        api_key=settings.deepseek_api_key,
        api_base=settings.deepseek_base_url,
        model="deepseek-V3.2",
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=DEFAULT_ADVANCED_MAX_TOKENS,
        request_timeout=DEFAULT_TIMEOUT,
        extra_body={"enable_thinking": True},
    )


base_model = _create_base_model()
advanced_model = _create_advanced_model()

__all__ = ["base_model", "advanced_model"]
