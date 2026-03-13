from langchain_community.embeddings import DashScopeEmbeddings
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI

from rag_app.core.config import settings

base_model = ChatOpenAI(
    api_key=settings.qwen_omni_api_key,
    base_url=settings.qwen_omni_base_url,
    model_name="qwen3-omni-flash-2025-12-01",
    temperature=0.5,
    max_tokens=1024,
    request_timeout=60,
    reasoning_effort="high",
)

advanced_model = ChatDeepSeek(
    api_key=settings.deepseek_api_key,
    api_base=settings.deepseek_base_url,
    model="deepseek-v3.2",
    temperature=0.5,
    max_tokens=2048,
    request_timeout=60,
    extra_body={"enable_thinking": True},
)

embedding_model = DashScopeEmbeddings(
    dashscope_api_key=settings.tongyi_embedding_api_key,
    model="tongyi-embedding-vision-flash",
)

__all__ = ["base_model", "advanced_model", "embedding_model"]