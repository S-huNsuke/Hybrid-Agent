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

# 延迟初始化模型，避免启动时就因为缺少 API Key 而崩溃
_base_model = None
_advanced_model = None


def _create_base_model() -> ChatOpenAI:
    """创建基础模型实例"""
    if settings.qwen_omni_api_key is None:
        error_msg = "QWEN_OMNI_API_KEY 未配置，请在 .env 文件中设置该环境变量"
        logger.error(error_msg)
        raise ValueError(error_msg)

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
        error_msg = "DEEPSEEK_API_KEY 未配置，请在 .env 文件中设置该环境变量"
        logger.error(error_msg)
        raise ValueError(error_msg)

    return ChatDeepSeek(
        api_key=settings.deepseek_api_key,
        api_base=settings.deepseek_base_url,
        model="deepseek-V3.2",
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=DEFAULT_ADVANCED_MAX_TOKENS,
        request_timeout=DEFAULT_TIMEOUT,
        extra_body={"enable_thinking": True},
    )


def get_base_model() -> ChatOpenAI:
    """获取基础模型实例（延迟加载）"""
    global _base_model
    if _base_model is None:
        _base_model = _create_base_model()
    return _base_model


def get_advanced_model() -> ChatDeepSeek:
    """获取高级模型实例（延迟加载）"""
    global _advanced_model
    if _advanced_model is None:
        _advanced_model = _create_advanced_model()
    return _advanced_model


# 为了向后兼容，创建模块级别的访问器
# 注意：这些不是真正的变量，而是通过 __getattr__ 动态获取
def __getattr__(name):
    if name == "base_model":
        return get_base_model()
    elif name == "advanced_model":
        return get_advanced_model()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = ["base_model", "advanced_model", "get_base_model", "get_advanced_model"]

