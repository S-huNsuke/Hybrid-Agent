"""RRF 融合算法单元测试"""

from hybrid_agent.core.hybrid_retriever import _rrf_merge


class TestRRFMerge:
    """RRF 融合算法测试"""

    def test_empty_results(self):
        """测试空结果"""
        result = _rrf_merge([])
        assert result == []

    def test_single_path_single_result(self):
        """测试单路径单结果"""
        results = [[
            {"content": "test content", "chunk_id": "c1", "score": 1.0, "retrieval_method": "dense"}
        ]]
        merged = _rrf_merge(results)
        
        assert len(merged) == 1
        assert merged[0]["chunk_id"] == "c1"
        assert "rrf_score" in merged[0]
        # 单个结果 RRF 分数 = 1/(60+1) ≈ 0.0164
        assert abs(merged[0]["rrf_score"] - 1/61) < 0.0001

    def test_two_paths_same_content(self):
        """测试两路径返回相同内容（去重）"""
        results = [
            [{"content": "same content", "chunk_id": "c1", "score": 1.0, "retrieval_method": "dense"}],
            [{"content": "same content", "chunk_id": "c1", "score": 1.0, "retrieval_method": "bm25"}],
        ]
        merged = _rrf_merge(results)
        
        # 应该去重，只保留一个
        assert len(merged) == 1
        # RRF 分数应该是两路之和：1/(60+1) + 1/(60+1)
        expected_score = 2 / 61
        assert abs(merged[0]["rrf_score"] - expected_score) < 0.0001
        # retrieval_method 应该合并
        assert "dense" in merged[0]["retrieval_method"]
        assert "bm25" in merged[0]["retrieval_method"]

    def test_two_paths_different_content(self):
        """测试两路径返回不同内容"""
        results = [
            [{"content": "content A", "chunk_id": "c1", "score": 1.0, "retrieval_method": "dense"}],
            [{"content": "content B", "chunk_id": "c2", "score": 1.0, "retrieval_method": "bm25"}],
        ]
        merged = _rrf_merge(results)
        
        # 两个不同内容，应该都保留
        assert len(merged) == 2
        # 两条结果都在各自路径中 rank=1，因此 RRF 分数相同
        assert merged[0]["rrf_score"] == merged[1]["rrf_score"]
        assert {item["chunk_id"] for item in merged} == {"c1", "c2"}

    def test_ranking_order(self):
        """测试排序顺序（按 RRF 分数降序）"""
        results = [
            [
                {"content": "A", "chunk_id": "c1", "score": 1.0, "retrieval_method": "dense"},
                {"content": "B", "chunk_id": "c2", "score": 0.5, "retrieval_method": "dense"},
            ],
            [
                {"content": "B", "chunk_id": "c2", "score": 1.0, "retrieval_method": "bm25"},
                {"content": "C", "chunk_id": "c3", "score": 0.5, "retrieval_method": "bm25"},
            ],
        ]
        merged = _rrf_merge(results)
        
        # B 在两路都出现，RRF 分数应该最高
        assert merged[0]["chunk_id"] == "c2"
        
        # 验证所有结果都有 rrf_score
        for item in merged:
            assert "rrf_score" in item

    def test_multiple_paths(self):
        """测试多路径融合"""
        results = [
            [{"content": "A", "chunk_id": "c1", "score": 1.0, "retrieval_method": "dense"}],
            [{"content": "A", "chunk_id": "c1", "score": 1.0, "retrieval_method": "bm25"}],
            [{"content": "A", "chunk_id": "c1", "score": 1.0, "retrieval_method": "hyde"}],
        ]
        merged = _rrf_merge(results)
        
        assert len(merged) == 1
        # 三路融合：3/(60+1)
        expected_score = 3 / 61
        assert abs(merged[0]["rrf_score"] - expected_score) < 0.0001

    def test_missing_chunk_id_uses_content(self):
        """测试缺少 chunk_id 时使用 content 作为去重键"""
        results = [
            [{"content": "same content", "score": 1.0, "retrieval_method": "dense"}],
            [{"content": "same content", "score": 1.0, "retrieval_method": "bm25"}],
        ]
        merged = _rrf_merge(results)
        
        # 应该去重
        assert len(merged) == 1


class TestBigramTokenize:
    """Bigram 分词测试"""

    def test_empty_string(self):
        """测试空字符串"""
        from hybrid_agent.core.hybrid_retriever import _bigram_tokenize
        assert _bigram_tokenize("") == []
        assert _bigram_tokenize("   ") == []

    def test_single_char(self):
        """测试单字符"""
        from hybrid_agent.core.hybrid_retriever import _bigram_tokenize
        assert _bigram_tokenize("a") == ["a"]
        assert _bigram_tokenize("中") == ["中"]

    def test_two_chars(self):
        """测试双字符"""
        from hybrid_agent.core.hybrid_retriever import _bigram_tokenize
        assert _bigram_tokenize("ab") == ["ab"]
        assert _bigram_tokenize("中文") == ["中文"]

    def test_multiple_chars(self):
        """测试多字符"""
        from hybrid_agent.core.hybrid_retriever import _bigram_tokenize
        result = _bigram_tokenize("abcd")
        assert result == ["ab", "bc", "cd"]
        
        result = _bigram_tokenize("中文测试")
        assert result == ["中文", "文测", "测试"]

    def test_mixed_content(self):
        """测试混合内容"""
        from hybrid_agent.core.hybrid_retriever import _bigram_tokenize
        result = _bigram_tokenize("Hello World")
        # 保留空格处理
        assert len(result) > 0
