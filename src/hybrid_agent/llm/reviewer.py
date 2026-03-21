"""审查器模型配置"""

import logging

from langchain_openai import ChatOpenAI

from hybrid_agent.core.config import (
    settings,
    default_reviewer_settings,
)

logger = logging.getLogger(__name__)


def create_reviewer_model(
    model_name: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> ChatOpenAI:
    api_key = settings.qwen_api_key or settings.qwen_omni_api_key
    base_url = settings.qwen_base_url or settings.qwen_omni_base_url

    if api_key is None:
        logger.warning("QWEN_API_KEY 和 QWEN_OMNI_API_KEY 都未配置，reviewer_model 可能无法正常工作")

    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model_name=model_name or default_reviewer_settings.model_name,
        temperature=temperature or default_reviewer_settings.temperature,
        max_tokens=max_tokens or default_reviewer_settings.max_tokens,
        request_timeout=default_reviewer_settings.timeout,
    )


reviewer_model = create_reviewer_model()

__all__ = ["reviewer_model", "create_reviewer_model"]
