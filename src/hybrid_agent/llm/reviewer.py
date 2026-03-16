"""审查器模型配置"""

import logging

from langchain_openai import ChatOpenAI

from hybrid_agent.core.config import (
    settings,
    ReviewerSettings,
)

logger = logging.getLogger(__name__)

_settings = ReviewerSettings()


def create_reviewer_model(
    model_name: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> ChatOpenAI:
    if settings.qwen_omni_api_key is None:
        logger.warning("QWEN_OMNI_API_KEY 未配置，reviewer_model 可能无法正常工作")
    
    return ChatOpenAI(
        api_key=settings.qwen_omni_api_key,
        base_url=settings.qwen_omni_base_url,
        model_name=model_name or _settings.model_name,
        temperature=temperature or _settings.temperature,
        max_tokens=max_tokens or _settings.max_tokens,
        request_timeout=_settings.timeout,
    )


# 默认审查器模型实例
reviewer_model = create_reviewer_model()

__all__ = ["reviewer_model", "create_reviewer_model"]
