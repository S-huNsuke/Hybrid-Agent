"""查询理解模块：意图分类、HyDE 改写、子问题分解

组件：
    IntentRouter        — 使用 qwen-turbo 将查询分为 5 类意图
    HyDERewriter        — 生成假设文档（Hypothetical Document Embedding）
    SubQueryDecomposer  — 复杂查询拆解为子问题（>100 字符时激活）

意图分类（5类）：
    direct      — 闲聊/常识，不检索
    rag_only    — 文档库可解答
    web_only    — 需实时信息
    hybrid      — 文档 + 网络
    math_code   — 计算/代码，直接推理
"""

from __future__ import annotations

import json
import logging
import re
import threading
from typing import Literal

from hybrid_agent.core.config import (
    COMPLEX_QUERY_THRESHOLD,
    MAX_SUB_QUERIES,
    QUERY_UNDERSTANDING_TIMEOUT,
    QUERY_UNDERSTANDING_MAX_TOKENS,
)

logger = logging.getLogger(__name__)

Intent = Literal["direct", "rag_only", "web_only", "hybrid", "math_code"]

# ── 提示词模板 ────────────────────────────────────────────────────────────

_INTENT_PROMPT = """你是一个查询意图分类器。根据用户的查询，判断最合适的处理方式。

意图类别：
- direct: 日常闲聊、问候、简单常识（无需检索）
- rag_only: 问题可通过本地知识库文档回答
- web_only: 需要实时/最新信息（新闻、价格、天气等）
- hybrid: 需要结合文档知识和实时网络信息
- math_code: 数学计算、代码生成/调试（直接推理即可）

用户查询：{query}

请只输出一个 JSON，格式：{{"intent": "<类别>", "reason": "<简短理由>"}}
不要输出任何其他内容。"""

_HYDE_PROMPT = """请根据以下问题，写一段简短的假设性回答（100字以内）。
这段回答将用于语义检索，无需完全准确，但应包含可能相关的关键词和概念。

问题：{query}

假设性回答（直接输出内容，不要加前缀）："""

_SUBQUERY_PROMPT = """将以下复杂问题分解为 2-3 个简单子问题，每个子问题可以独立检索回答。

原始问题：{query}

请输出 JSON 数组，格式：["子问题1", "子问题2", "子问题3"]
只输出 JSON，不要任何其他内容。"""


def _call_qwen_turbo(prompt: str, max_tokens: int | None = None) -> str | None:
    """调用 qwen-turbo（通过 OpenAI 兼容接口）

    Args:
        prompt: 提示词
        max_tokens: 最大 token 数，None 时使用配置默认值

    Returns:
        模型输出文本，失败返回 None
    """
    if max_tokens is None:
        max_tokens = QUERY_UNDERSTANDING_MAX_TOKENS

    try:
        from hybrid_agent.core.config import settings
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage

        api_key = settings.qwen_api_key or settings.tongyi_embedding_api_key
        base_url = settings.qwen_base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"

        if not api_key:
            logger.warning("QWEN_API_KEY 未配置，跳过 qwen-turbo 调用")
            return None

        llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model_name="qwen-turbo",
            temperature=0.1,
            max_tokens=max_tokens,
            request_timeout=QUERY_UNDERSTANDING_TIMEOUT,
        )
        resp = llm.invoke([HumanMessage(content=prompt)])
        return resp.content.strip() if resp and resp.content else None
    except Exception as e:
        logger.warning(f"qwen-turbo 调用失败: {e}")
        return None


class IntentRouter:
    """查询意图分类器

    使用 qwen-turbo 将查询分为 5 类意图，决定是否需要检索及检索策略。
    分类失败时降级为 rag_only（保守策略）。
    """

    def classify(self, query: str) -> Intent:
        """对查询进行意图分类

        Args:
            query: 用户查询文本

        Returns:
            意图类别
        """
        # 快速规则：极短查询（≤3字符）视为闲聊，避免误分类"什么是AI"等4+字符查询
        if len(query.strip()) <= 3:
            return "direct"

        prompt = _INTENT_PROMPT.format(query=query)
        response = _call_qwen_turbo(prompt, max_tokens=128)

        if not response:
            return "rag_only"  # 降级保守策略

        intent = self._parse_intent(response)
        logger.debug(f"意图分类: '{query[:30]}...' → {intent}")
        return intent

    def _parse_intent(self, response: str) -> Intent:
        """解析意图分类响应

        Args:
            response: 模型输出文本

        Returns:
            意图类别
        """
        valid_intents = {"direct", "rag_only", "web_only", "hybrid", "math_code"}

        # 尝试解析 JSON
        try:
            # 提取 JSON 部分
            json_match = re.search(r'\{[^{}]+\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                intent = data.get("intent", "").strip()
                if intent in valid_intents:
                    return intent  # type: ignore[return-value]
        except (json.JSONDecodeError, AttributeError):
            pass

        # 降级：在文本中查找意图关键字
        response_lower = response.lower()
        for intent in valid_intents:
            if intent in response_lower:
                return intent  # type: ignore[return-value]

        return "rag_only"


class HyDERewriter:
    """HyDE（Hypothetical Document Embedding）查询改写器

    生成一段假设性回答文本，用该文本的嵌入向量代替原始问题进行检索，
    可显著提升稀疏问题的召回质量。
    """

    def rewrite(self, query: str) -> str | None:
        """生成 HyDE 假设文档

        Args:
            query: 原始查询文本

        Returns:
            假设文档文本，失败返回 None
        """
        prompt = _HYDE_PROMPT.format(query=query)
        hyde_doc = _call_qwen_turbo(prompt, max_tokens=200)

        if hyde_doc:
            logger.debug(f"HyDE 改写成功: '{query[:30]}' → '{hyde_doc[:50]}...'")

        return hyde_doc


class SubQueryDecomposer:
    """子问题分解器

    将复杂查询（>100 字符）拆解为 2-3 个可独立检索的子问题，
    各子问题并行检索后通过 RRF 合并（Path D）。
    """

    def decompose(self, query: str) -> list[str]:
        """拆解复杂查询为子问题

        Args:
            query: 原始查询文本

        Returns:
            子问题列表（最多 MAX_SUB_QUERIES 个），简单查询返回空列表
        """
        # 短查询不拆分
        if len(query.strip()) <= COMPLEX_QUERY_THRESHOLD:
            return []

        prompt = _SUBQUERY_PROMPT.format(query=query)
        response = _call_qwen_turbo(prompt, max_tokens=256)

        if not response:
            return []

        sub_queries = self._parse_sub_queries(response)
        logger.debug(f"子问题分解: '{query[:30]}...' → {len(sub_queries)} 个子问题")
        return sub_queries

    def _parse_sub_queries(self, response: str) -> list[str]:
        """解析子问题列表

        Args:
            response: 模型输出文本

        Returns:
            子问题列表
        """
        # 尝试解析 JSON 数组
        try:
            json_match = re.search(r'\[[^\[\]]+\]', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                if isinstance(data, list):
                    sub_queries = [str(q).strip() for q in data if str(q).strip()]
                    return sub_queries[:MAX_SUB_QUERIES]
        except (json.JSONDecodeError, AttributeError):
            pass

        # 降级：按行拆分
        lines = [
            re.sub(r'^[\d\.\-\*\s]+', '', line).strip()
            for line in response.split('\n')
            if line.strip() and len(line.strip()) > 5
        ]
        return lines[:MAX_SUB_QUERIES]


# ── 全局单例 ──────────────────────────────────────────────────────────────

_intent_router: IntentRouter | None = None
_hyde_rewriter: HyDERewriter | None = None
_sub_query_decomposer: SubQueryDecomposer | None = None
_router_lock = threading.Lock()
_rewriter_lock = threading.Lock()
_decomposer_lock = threading.Lock()


def get_intent_router() -> IntentRouter:
    """获取 IntentRouter 单例（线程安全）

    Returns:
        IntentRouter 实例
    """
    global _intent_router
    if _intent_router is None:
        with _router_lock:
            if _intent_router is None:
                _intent_router = IntentRouter()
    return _intent_router


def get_hyde_rewriter() -> HyDERewriter:
    """获取 HyDERewriter 单例（线程安全）

    Returns:
        HyDERewriter 实例
    """
    global _hyde_rewriter
    if _hyde_rewriter is None:
        with _rewriter_lock:
            if _hyde_rewriter is None:
                _hyde_rewriter = HyDERewriter()
    return _hyde_rewriter


def get_sub_query_decomposer() -> SubQueryDecomposer:
    """获取 SubQueryDecomposer 单例（线程安全）

    Returns:
        SubQueryDecomposer 实例
    """
    global _sub_query_decomposer
    if _sub_query_decomposer is None:
        with _decomposer_lock:
            if _sub_query_decomposer is None:
                _sub_query_decomposer = SubQueryDecomposer()
    return _sub_query_decomposer
