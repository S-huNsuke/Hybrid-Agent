from langchain_openai import ChatOpenAI
from langchain_deepseek import ChatDeepSeek

from rag_app.core.config import (
    settings,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_ADVANCED_MAX_TOKENS,
    DEFAULT_TIMEOUT
)

base_model = ChatOpenAI(
    api_key=settings.qwen_omni_api_key,
    base_url=settings.qwen_omni_base_url,
    model_name="qwen3-omni-flash-2025-12-01",
    temperature=DEFAULT_TEMPERATURE,
    max_tokens=DEFAULT_MAX_TOKENS,
    request_timeout=DEFAULT_TIMEOUT,
)

advanced_model = ChatDeepSeek(
    api_key=settings.deepseek_api_key,
    api_base=settings.deepseek_base_url,
    model="deepseek-chat",
    temperature=DEFAULT_TEMPERATURE,
    max_tokens=DEFAULT_ADVANCED_MAX_TOKENS,
    request_timeout=DEFAULT_TIMEOUT,
    extra_body={"enable_thinking": True},
)

__all__ = ["base_model", "advanced_model"]