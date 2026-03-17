import re

from hybrid_agent.llm.models import get_advanced_model, get_base_model

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
        模型类型: "advanced" (DeepSeek) 或 "base" (Qwen)
    """
    if model == "deepseek-v3":
        return "advanced"
    else:
        # auto 和 qwen3-omni 都使用 base 模型
        # auto 模式会在 select_model 中根据复杂度动态选择
        return "base"


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

    # 安全地获取配置
    configurable = getattr(config, "configurable", None)
    if configurable is None and isinstance(config, dict):
        configurable = config.get("configurable", {})
    if configurable is None:
        configurable = {}

    selected = configurable.get("model", "auto") if isinstance(configurable, dict) else "auto"

    if selected == "qwen3-omni":
        return get_base_model()
    if selected == "deepseek-v3":
        return get_advanced_model()

    score = _calculate_complexity_score(user_input)

    return get_advanced_model() if score >= 0.4 else get_base_model()


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
