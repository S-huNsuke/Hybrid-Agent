from __future__ import annotations

import base64
import json
import logging
from typing import Any, cast

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr
from langchain_openai import ChatOpenAI
from langchain_deepseek import ChatDeepSeek

from hybrid_agent.core.config import (
    settings,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_ADVANCED_MAX_TOKENS,
    DEFAULT_TIMEOUT,
    DEFAULT_BASE_MODEL,
    DEFAULT_ADVANCED_MODEL,
    get_provider_secret_key,
)
from hybrid_agent.core.database import ProviderModel, db_manager

logger = logging.getLogger(__name__)

# 延迟初始化模型，避免启动时就因为缺少 API Key 而崩溃
_base_model = None
_advanced_model = None
_provider_model_cache: dict[tuple[str, str, str], Any] = {}
_MODEL_NAME_ATTRS: tuple[str, ...] = (
    "model_name",
    "model",
    "model_id",
    "deployment_name",
)


def _to_secret(api_key: str | None) -> SecretStr | None:
    """将字符串 API Key 转为模型构造器接受的 SecretStr。"""
    if api_key is None:
        return None
    return SecretStr(api_key)


def _cache_key(
    model_type: str,
    group_id: str | None,
    requested_model: str | None = None,
) -> tuple[str, str, str]:
    """构建 provider 运行时模型缓存 key。"""
    return (
        model_type,
        group_id or "",
        requested_model or "",
    )


def _parse_provider_models(raw_models: str | None) -> list[str]:
    """解析 provider 记录中的 models 字段。"""
    if not raw_models:
        return []
    try:
        parsed = json.loads(raw_models)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass
    return [item.strip() for item in raw_models.split(",") if item.strip()]


def _get_provider_cipher() -> Fernet | None:
    secret = get_provider_secret_key()
    if not secret:
        return None

    key_bytes = secret.encode("utf-8")
    if len(key_bytes) != 44:
        key_bytes = base64.urlsafe_b64encode(key_bytes.ljust(32, b"0")[:32])
    return Fernet(key_bytes)


def _decrypt_provider_api_key(ciphertext: str | None) -> str | None:
    if not ciphertext:
        return None

    cipher = _get_provider_cipher()
    if cipher is None:
        logger.warning("PROVIDER_SECRET_KEY 未配置，无法解密 provider API key")
        return None

    try:
        return cipher.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.warning("provider API key 解密失败，回退到默认环境变量模型")
        return None


def _iter_provider_candidates(group_id: str | None) -> list[ProviderModel]:
    if not db_manager:
        return []

    group_records = (
        db_manager.list_providers(group_id=group_id, include_inactive=False)
        if group_id
        else []
    )
    global_records = [
        record
        for record in db_manager.list_providers(include_inactive=False)
        if not record.group_id
    ]
    return group_records + global_records


def _select_provider(group_id: str | None, provider_types: set[str]) -> ProviderModel | None:
    for record in _iter_provider_candidates(group_id):
        if str(record.provider_type).lower() in provider_types:
            return record
    return None


def _select_provider_for_requested_model(
    requested_model: str,
    group_id: str | None,
) -> ProviderModel | None:
    normalized = requested_model.strip()
    if not normalized:
        return None

    for record in _iter_provider_candidates(group_id):
        models = _parse_provider_models(str(record.models) if record.models else None)
        default_model = str(record.default_model).strip() if record.default_model else ""
        if normalized == default_model or normalized in models:
            return record
    return None


def _create_openai_compatible_model(
    provider: ProviderModel,
    *,
    fallback_model: str,
    requested_model: str | None = None,
) -> ChatOpenAI | None:
    api_key = _decrypt_provider_api_key(
        str(provider.api_key_ciphertext) if provider.api_key_ciphertext else None
    )
    if not api_key:
        return None

    return ChatOpenAI(
        api_key=_to_secret(api_key),
        base_url=str(provider.base_url) if provider.base_url else None,
        model=requested_model or (str(provider.default_model) if provider.default_model else fallback_model),
        temperature=DEFAULT_TEMPERATURE,
        max_completion_tokens=DEFAULT_MAX_TOKENS,
        timeout=DEFAULT_TIMEOUT,
    )


def _create_deepseek_provider_model(
    provider: ProviderModel,
    *,
    requested_model: str | None = None,
) -> ChatDeepSeek | None:
    api_key = _decrypt_provider_api_key(
        str(provider.api_key_ciphertext) if provider.api_key_ciphertext else None
    )
    if not api_key:
        return None

    return ChatDeepSeek(
        api_key=_to_secret(api_key),
        base_url=str(provider.base_url) if provider.base_url else settings.deepseek_base_url,
        model=requested_model or (
            str(provider.default_model) if provider.default_model else DEFAULT_ADVANCED_MODEL
        ),
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=DEFAULT_ADVANCED_MAX_TOKENS,
        timeout=DEFAULT_TIMEOUT,
        extra_body={"enable_thinking": True},
    )


def _create_provider_backed_model(
    provider: ProviderModel,
    *,
    fallback_model: str,
    requested_model: str | None = None,
) -> Any:
    """根据 provider 类型创建运行时模型。"""
    provider_type = str(provider.provider_type).lower()
    if provider_type == "deepseek":
        return _create_deepseek_provider_model(
            provider,
            requested_model=requested_model,
        )
    return _create_openai_compatible_model(
        provider,
        fallback_model=fallback_model,
        requested_model=requested_model,
    )


def _fallback_model_type_for_requested_model(requested_model: str) -> str:
    """当未命中 provider 配置时，根据模型名推断基础/高级类型。"""
    normalized = requested_model.strip().lower()
    if normalized in {
        "qwen3-omni",
        "base",
        DEFAULT_BASE_MODEL.lower(),
    } or "qwen" in normalized:
        return "base"
    if normalized in {
        "deepseek-v3",
        "advanced",
        DEFAULT_ADVANCED_MODEL.lower(),
    } or "deepseek" in normalized:
        return "advanced"
    return "base"


def _create_base_model() -> ChatOpenAI:
    """创建基础模型实例"""
    if settings.qwen_omni_api_key is None:
        error_msg = "QWEN_OMNI_API_KEY 未配置，请在 .env 文件中设置该环境变量"
        logger.error(error_msg)
        raise ValueError(error_msg)

    return ChatOpenAI(
        api_key=_to_secret(settings.qwen_omni_api_key),
        base_url=settings.qwen_omni_base_url,
        model=DEFAULT_BASE_MODEL,
        temperature=DEFAULT_TEMPERATURE,
        max_completion_tokens=DEFAULT_MAX_TOKENS,
        timeout=DEFAULT_TIMEOUT,
    )


def _create_advanced_model() -> ChatDeepSeek:
    """创建高级模型实例"""
    if settings.deepseek_api_key is None:
        error_msg = "DEEPSEEK_API_KEY 未配置，请在 .env 文件中设置该环境变量"
        logger.error(error_msg)
        raise ValueError(error_msg)

    return ChatDeepSeek(
        api_key=_to_secret(settings.deepseek_api_key),
        base_url=settings.deepseek_base_url,
        model=DEFAULT_ADVANCED_MODEL,
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=DEFAULT_ADVANCED_MAX_TOKENS,
        timeout=DEFAULT_TIMEOUT,
        extra_body={"enable_thinking": True},
    )


def get_base_model(group_id: str | None = None) -> Any:
    """获取基础模型实例（延迟加载）"""
    if group_id:
        cache_key = _cache_key("base", group_id)
        if cache_key not in _provider_model_cache:
            provider = _select_provider(
                group_id,
                {"qwen", "openai", "openai_compatible", "custom", "azure_openai"},
            )
            model = (
                _create_openai_compatible_model(provider, fallback_model=DEFAULT_BASE_MODEL)
                if provider
                else None
            )
            if model is not None:
                _provider_model_cache[cache_key] = model
        if cache_key in _provider_model_cache:
            return _provider_model_cache[cache_key]

    global _base_model
    if _base_model is None:
        _base_model = _create_base_model()
    return cast(ChatOpenAI, _base_model)


def get_advanced_model(group_id: str | None = None) -> Any:
    """获取高级模型实例（延迟加载）"""
    if group_id:
        cache_key = _cache_key("advanced", group_id)
        if cache_key not in _provider_model_cache:
            provider = _select_provider(
                group_id,
                {"deepseek", "openai", "openai_compatible", "custom", "azure_openai"},
            )
            model: Any = None
            if provider:
                provider_type = str(provider.provider_type).lower()
                if provider_type == "deepseek":
                    model = _create_deepseek_provider_model(provider)
                else:
                    model = _create_openai_compatible_model(
                        provider,
                        fallback_model=DEFAULT_ADVANCED_MODEL,
                    )
            if model is not None:
                _provider_model_cache[cache_key] = model
        if cache_key in _provider_model_cache:
            return _provider_model_cache[cache_key]

    global _advanced_model
    if _advanced_model is None:
        _advanced_model = _create_advanced_model()
    return cast(ChatDeepSeek, _advanced_model)


def resolve_model_used(model: Any, fallback: str) -> str:
    """提取实际运行模型名，失败时回退到默认模型名。"""
    for attr in _MODEL_NAME_ATTRS:
        value = getattr(model, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback


def resolve_runtime_model(
    model_type: str,
    *,
    group_id: str | None = None,
    requested_model: str | None = None,
) -> tuple[Any, str]:
    """按模型类型和 group 解析运行时模型，并返回实际模型名。"""
    if model_type == "selected" and requested_model:
        cache_key = _cache_key("selected", group_id, requested_model)
        if cache_key not in _provider_model_cache:
            provider = _select_provider_for_requested_model(requested_model, group_id)
            resolved_model = None
            if provider is not None:
                fallback_model = (
                    DEFAULT_ADVANCED_MODEL
                    if str(provider.provider_type).lower() == "deepseek"
                    else DEFAULT_BASE_MODEL
                )
                resolved_model = _create_provider_backed_model(
                    provider,
                    fallback_model=fallback_model,
                    requested_model=requested_model,
                )
            if resolved_model is None:
                inferred_type = _fallback_model_type_for_requested_model(requested_model)
                resolved_model = (
                    get_advanced_model(group_id=group_id)
                    if inferred_type == "advanced"
                    else get_base_model(group_id=group_id)
                )
            _provider_model_cache[cache_key] = resolved_model
        model = _provider_model_cache[cache_key]
        return model, resolve_model_used(model, requested_model)

    if model_type == "advanced":
        model = get_advanced_model(group_id=group_id)
        return model, resolve_model_used(model, DEFAULT_ADVANCED_MODEL)

    model = get_base_model(group_id=group_id)
    return model, resolve_model_used(model, DEFAULT_BASE_MODEL)


def list_runtime_models(group_id: str | None = None) -> list[dict[str, Any]]:
    """列出当前用户/组可见的运行时模型目录。"""
    catalog: list[dict[str, Any]] = [
        {
            "id": "auto",
            "name": "自动选择",
            "description": "根据问题复杂度和 provider 配置自动选择",
            "is_available": True,
            "provider": "system",
            "provider_type": "system",
            "group_id": group_id,
        },
        {
            "id": DEFAULT_BASE_MODEL,
            "name": "默认基础模型",
            "description": "环境变量基础模型回退",
            "is_available": True,
            "provider": "env",
            "provider_type": "fallback",
            "group_id": None,
        },
        {
            "id": DEFAULT_ADVANCED_MODEL,
            "name": "默认增强模型",
            "description": "环境变量增强模型回退",
            "is_available": True,
            "provider": "env",
            "provider_type": "fallback",
            "group_id": None,
        },
    ]
    seen = {item["id"] for item in catalog}

    for record in _iter_provider_candidates(group_id):
        if not record.api_key_ciphertext:
            continue

        model_ids = _parse_provider_models(str(record.models) if record.models else None)
        default_model = str(record.default_model).strip() if record.default_model else ""
        if default_model and default_model not in model_ids:
            model_ids.insert(0, default_model)
        if not model_ids:
            model_ids = [
                default_model
                or (
                    DEFAULT_ADVANCED_MODEL
                    if str(record.provider_type).lower() == "deepseek"
                    else DEFAULT_BASE_MODEL
                )
            ]

        for model_id in model_ids:
            if model_id in seen:
                continue
            seen.add(model_id)
            catalog.append(
                {
                    "id": model_id,
                    "name": model_id,
                    "description": f"{record.display_name} ({record.provider_type})",
                    "is_available": True,
                    "provider": str(record.display_name),
                    "provider_type": str(record.provider_type),
                    "group_id": str(record.group_id) if record.group_id else None,
                }
            )

    return catalog


def clear_provider_model_cache() -> None:
    """Invalidate provider-backed runtime model instances after config changes."""
    _provider_model_cache.clear()


# 为了向后兼容，创建模块级别的访问器
# 注意：这些不是真正的变量，而是通过 __getattr__ 动态获取
def __getattr__(name):
    if name == "base_model":
        return get_base_model()
    elif name == "advanced_model":
        return get_advanced_model()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "clear_provider_model_cache",
    "get_base_model",
    "get_advanced_model",
    "list_runtime_models",
    "resolve_model_used",
    "resolve_runtime_model",
]
