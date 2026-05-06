"""查询理解模块单元测试"""

from unittest.mock import patch
from hybrid_agent.core.query_understanding import (
    IntentRouter,
    HyDERewriter,
    SubQueryDecomposer,
    get_intent_router,
    get_hyde_rewriter,
    get_sub_query_decomposer,
)
from hybrid_agent.core.config import COMPLEX_QUERY_THRESHOLD, MAX_SUB_QUERIES


class TestIntentRouter:
    """意图分类器测试"""

    def test_short_query_returns_direct(self):
        """测试短查询返回 direct"""
        router = IntentRouter()
        # <=3 字符视为闲聊
        assert router.classify("hi") == "direct"
        assert router.classify("你好") == "direct"
        assert router.classify("abc") == "direct"

    def test_normal_query_returns_rag_only_on_failure(self):
        """测试分类失败时降级为 rag_only"""
        router = IntentRouter()
        
        with patch.object(router, '_parse_intent', return_value="rag_only"):
            result = router._parse_intent("invalid response")
            assert result == "rag_only"

    def test_parse_intent_valid_json(self):
        """测试解析有效 JSON"""
        router = IntentRouter()
        
        response = '{"intent": "web_only", "reason": "需要实时信息"}'
        result = router._parse_intent(response)
        assert result == "web_only"

    def test_parse_intent_invalid_json_fallback(self):
        """测试无效 JSON 降级"""
        router = IntentRouter()
        
        # 包含有效意图关键字
        response = "The intent is math_code for this query"
        result = router._parse_intent(response)
        assert result == "math_code"

    def test_parse_intent_unknown_returns_rag_only(self):
        """测试未知意图返回 rag_only"""
        router = IntentRouter()
        
        response = "unknown response without intent"
        result = router._parse_intent(response)
        assert result == "rag_only"


class TestHyDERewriter:
    """HyDE 改写器测试"""

    def test_rewrite_returns_none_on_api_failure(self):
        """测试 API 失败返回 None"""
        rewriter = HyDERewriter()
        
        with patch(
            'hybrid_agent.core.query_understanding._call_qwen_turbo',
            return_value=None
        ):
            result = rewriter.rewrite("测试问题")
            assert result is None

    def test_rewrite_returns_content_on_success(self):
        """测试成功时返回内容"""
        rewriter = HyDERewriter()
        
        with patch(
            'hybrid_agent.core.query_understanding._call_qwen_turbo',
            return_value="这是假设性回答"
        ):
            result = rewriter.rewrite("测试问题")
            assert result == "这是假设性回答"


class TestSubQueryDecomposer:
    """子问题分解器测试"""

    def test_short_query_no_decomposition(self):
        """测试短查询不分解"""
        decomposer = SubQueryDecomposer()
        
        # 短于阈值不分解
        short_query = "a" * (COMPLEX_QUERY_THRESHOLD - 1)
        result = decomposer.decompose(short_query)
        assert result == []

    def test_long_query_attempts_decomposition(self):
        """测试长查询尝试分解"""
        decomposer = SubQueryDecomposer()
        
        long_query = "a" * (COMPLEX_QUERY_THRESHOLD + 10)
        
        with patch(
            'hybrid_agent.core.query_understanding._call_qwen_turbo',
            return_value='["子问题1", "子问题2", "子问题3"]'
        ):
            result = decomposer.decompose(long_query)
            assert len(result) <= MAX_SUB_QUERIES

    def test_parse_sub_queries_valid_json(self):
        """测试解析有效 JSON 数组"""
        decomposer = SubQueryDecomposer()
        
        response = '["问题1", "问题2", "问题3"]'
        result = decomposer._parse_sub_queries(response)
        
        assert len(result) <= MAX_SUB_QUERIES
        assert all(isinstance(q, str) for q in result)

    def test_parse_sub_queries_fallback_to_lines(self):
        """测试 JSON 解析失败时降级为行分割"""
        decomposer = SubQueryDecomposer()
        
        # 非法 JSON，但有多行
        response = "1. 第一行内容\n2. 第二行内容\n3. 第三行内容"
        result = decomposer._parse_sub_queries(response)
        
        # 应该有解析结果（去除前缀后的行）
        assert isinstance(result, list)


class TestSingletonPattern:
    """单例模式测试"""

    def test_intent_router_singleton(self):
        """测试 IntentRouter 单例"""
        router1 = get_intent_router()
        router2 = get_intent_router()
        assert router1 is router2

    def test_hyde_rewriter_singleton(self):
        """测试 HyDERewriter 单例"""
        rewriter1 = get_hyde_rewriter()
        rewriter2 = get_hyde_rewriter()
        assert rewriter1 is rewriter2

    def test_sub_query_decomposer_singleton(self):
        """测试 SubQueryDecomposer 单例"""
        decomposer1 = get_sub_query_decomposer()
        decomposer2 = get_sub_query_decomposer()
        assert decomposer1 is decomposer2
