import re

from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call

from rag_app.llm.models import advanced_model, base_model

try:
    from openai import AuthenticationError as OpenAIAuthenticationError
except Exception:  # pragma: no cover
    OpenAIAuthenticationError = tuple()


def _is_auth_error(exc: Exception) -> bool:
    if OpenAIAuthenticationError and isinstance(exc, OpenAIAuthenticationError):
        return True

    if getattr(exc, "status_code", None) == 401:
        return True

    text = str(exc).lower()
    auth_markers = ("authentication", "invalid api key", "api key", "401")
    return any(marker in text for marker in auth_markers)


def _content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    texts.append(text)
        return "".join(texts)
    return ""


@wrap_model_call
def dynamic_model_selection(request: ModelRequest, handler) -> ModelResponse:
    user_input = ""
    if request.messages:
        user_input = _content_to_text(request.messages[-1].content)

    advanced_patterns = [
        r"为什么|如何|怎么",
        r"分析|比较|解释",
        r"代码|编程|算法",
        r"数学|推理|证明",
        r"\?.*\?.*\?",
    ]

    score = 0.0
    if len(user_input) > 300:
        score += 0.3
    if len(user_input) > 1000:
        score += 0.3

    for pattern in advanced_patterns:
        if re.search(pattern, user_input):
            score += 0.2

    if "```" in user_input or "`" in user_input:
        score += 0.2
    elif "//" in user_input or "/*" in user_input:
        score += 0.2

    complexity = min(score, 1.0)
    threshold = 0.4
    use_advanced = complexity >= threshold

    if use_advanced:
        model = advanced_model
        print(f"[模型切换] 复杂请求，使用增强模型 (复杂度: {complexity:.2f})")
    else:
        model = base_model
        print(f"[模型切换] 简单请求，使用基础模型 (复杂度: {complexity:.2f})")

    try:
        return handler(request.override(model=model))
    except Exception as exc:
        if use_advanced and _is_auth_error(exc):
            print("[模型降级] 增强模型鉴权失败，自动回退到基础模型。请检查 DEEPSEEK_API_KEY。")
            return handler(request.override(model=base_model))
        raise