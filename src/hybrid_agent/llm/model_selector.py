import re
from typing import Any

from hybrid_agent.core.config import DEFAULT_ADVANCED_MODEL, DEFAULT_BASE_MODEL
from hybrid_agent.core.database import db_manager
from hybrid_agent.llm.models import resolve_runtime_model

COMPLEXITY_PATTERNS = [
    r"为什么|如何|怎么",
    r"分析|比较|解释",
    r"代码|编程|算法",
    r"数学|推理|证明"
]


def resolve_model_type(model: str) -> str:
    """将模型选择转换为 RAG 系统使用的模型类型标识
    
    Args:
        model: 模型选择，可选值: "auto", "qwen3-omni", "deepseek-v3"
    
    Returns:
        模型类型: "advanced"、"base"、"auto" 或 "selected"
    """
    normalized = str(model or "").strip()
    if normalized in {"deepseek-v3", "advanced", DEFAULT_ADVANCED_MODEL}:
        return "advanced"
    if normalized in {"qwen3-omni", "base", DEFAULT_BASE_MODEL}:
        return "base"
    if normalized in {"", "auto"}:
        return "auto"
    return "selected"


def resolve_model_type_for_input(model: str, user_input: str) -> str:
    """结合用户输入，在 auto 模式下动态选择模型类型。"""
    resolved = resolve_model_type(model)
    if resolved != "auto":
        return resolved
    score = _calculate_complexity_score(user_input)
    return "advanced" if score >= 0.4 else "base"


def _extract_configurable(config: Any) -> dict[str, Any]:
    configurable = getattr(config, "configurable", None)
    if isinstance(configurable, dict):
        return configurable
    if isinstance(config, dict):
        nested = config.get("configurable")
        if isinstance(nested, dict):
            return nested
    return {}


def _resolve_group_id(configurable: dict[str, Any]) -> str | None:
    raw_group_id = configurable.get("group_id")
    if raw_group_id:
        return str(raw_group_id)

    thread_id = configurable.get("thread_id")
    if not thread_id or not db_manager:
        return None

    try:
        session_obj = db_manager.get_chat_session(str(thread_id))
    except Exception:
        return None
    if not session_obj or not session_obj.group_id:
        return None
    return str(session_obj.group_id)


def resolve_runtime_selection(
    model: str,
    user_input: str,
    *,
    group_id: str | None = None,
) -> tuple[Any, str, str]:
    """为一次请求解析实际运行模型实例、模型名与模型类型。"""
    model_type = resolve_model_type_for_input(model, user_input)
    runtime_model, model_used = resolve_runtime_model(
        model_type,
        group_id=group_id,
        requested_model=model,
    )
    return runtime_model, model_used, model_type


def select_model(state, config):
    """动态模型选择函数，供 create_react_agent 的 model 参数使用。

    Args:
        state: LangGraph 状态对象，包含消息历史
        config: LangGraph 配置对象，包含 configurable 字典
    """
    messages = state.get("messages", [])
    user_input = ""
    for msg in reversed(messages):
        content = getattr(msg, "content", "") if hasattr(msg, "content") else ""
        if isinstance(content, list):
            content = "".join(
                b.get("text", "") for b in content if isinstance(b, dict)
            )
        if getattr(msg, "type", None) == "human" and content:
            user_input = content
            break

    configurable = _extract_configurable(config)
    selected = str(configurable.get("model") or "auto")
    group_id = _resolve_group_id(configurable)

    model, model_used, model_type = resolve_runtime_selection(
        selected,
        user_input,
        group_id=group_id,
    )

    # 供调用方/观测层读取本次实际选择结果
    if isinstance(configurable, dict):
        configurable["resolved_model_type"] = model_type
        configurable["resolved_model_used"] = model_used
        if group_id:
            configurable["group_id"] = group_id

    return model


def _calculate_complexity_score(user_input: str) -> float:
    """计算用户输入的复杂度得分。"""
    score = 0.0
    if len(user_input) > 300:
        score += 0.3
    if len(user_input) > 1000:
        score += 0.3
    for pattern in COMPLEXITY_PATTERNS:
        if re.search(pattern, user_input):
            score += 0.2
    if "`" in user_input or "//" in user_input:
        score += 0.2
    return min(score, 1.0)
