"""Reranker 模块：基于 DashScope gte-rerank 的重排序

调用 DashScope TextReRank API 对候选块重排序，返回 top-K 最相关块。
DashScope API 不可用时降级至 ContentReviewer 评分排序。
"""

from __future__ import annotations

import logging
import threading

from hybrid_agent.core.config import DEFAULT_RERANK_TOP_K, MAX_DOCS_PER_RERANK

logger = logging.getLogger(__name__)


def _dashscope_rerank(
    query: str,
    documents: list[str],
    top_n: int,
    api_key: str | None = None,
) -> list[dict] | None:
    """调用 DashScope TextReRank API

    Args:
        query: 查询文本
        documents: 候选文本列表
        top_n: 返回数量
        api_key: DashScope API Key

    Returns:
        重排结果列表 [{"index": int, "relevance_score": float}]，失败返回 None
    """
    try:
        from dashscope import TextReRank

        resp = TextReRank.call(
            model="gte-rerank",
            query=query,
            documents=documents,
            top_n=top_n,
            return_documents=False,
            api_key=api_key,
        )
        if resp and resp.status_code == 200 and resp.output:
            return [
                {"index": r.index, "relevance_score": r.relevance_score}
                for r in resp.output.results
            ]
        logger.warning(f"DashScope rerank 返回异常: status={getattr(resp, 'status_code', None)}")
        return None
    except ImportError:
        logger.warning("dashscope 未安装，跳过 DashScope rerank")
        return None
    except Exception as e:
        logger.warning(f"DashScope rerank 调用失败: {e}")
        return None


def _reviewer_rerank(
    query: str,
    chunks: list[dict],
    top_n: int,
) -> list[dict]:
    """降级方案：使用 ContentReviewer 评分重排

    Args:
        query: 查询文本
        chunks: 候选块列表（包含 content 字段）
        top_n: 返回数量

    Returns:
        重排后的 top-n 块（添加了 rerank_score 字段）
    """
    try:
        from hybrid_agent.agent.reviewer import get_reviewer
        reviewer = get_reviewer()

        contents_to_review = [
            {"content": c.get("content", ""), "source_type": "knowledge_base"}
            for c in chunks
        ]
        review_result = reviewer.review_batch(query, contents_to_review)

        # 将评分合并回原始块
        scored_chunks = []
        for i, review in enumerate(review_result.reviews):
            if i < len(chunks):
                chunk = dict(chunks[i])
                chunk["rerank_score"] = review.total_score / 10.0  # 归一化到 0-1
                chunk["review_reasoning"] = review.reasoning
                scored_chunks.append(chunk)

        # 按评分降序，取 top-n
        scored_chunks.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
        return scored_chunks[:top_n]

    except Exception as e:
        logger.warning(f"ContentReviewer 降级 rerank 失败，返回原始顺序: {e}")
        result = [dict(c) for c in chunks[:top_n]]
        for r in result:
            r.setdefault("rerank_score", 0.5)
        return result


class Reranker:
    """文档重排序器

    优先使用 DashScope gte-rerank，失败时降级至 ContentReviewer 评分。

    Args:
        api_key: DashScope API Key，None 时从环境变量读取
        top_k: 默认返回数量
    """

    def __init__(self, api_key: str | None = None, top_k: int = DEFAULT_RERANK_TOP_K) -> None:
        self.top_k = top_k
        self._api_key = api_key
        self._load_api_key()

    def _load_api_key(self) -> None:
        """从配置读取 API Key"""
        if self._api_key:
            return
        try:
            from hybrid_agent.core.config import settings
            self._api_key = (
                settings.qwen_api_key
                or settings.tongyi_embedding_api_key
            )
        except Exception as e:
            logger.warning(f"无法加载 Reranker API Key: {e}")

    def rerank(
        self,
        query: str,
        chunks: list[dict],
        top_k: int | None = None,
    ) -> list[dict]:
        """对候选块重排序，返回 top-K 最相关块

        Args:
            query: 查询文本
            chunks: 候选块列表（每项须含 content 字段）
            top_k: 返回数量，None 时使用实例默认值

        Returns:
            重排后的块列表，每项新增 rerank_score 字段
        """
        if not chunks:
            return []

        k = top_k or self.top_k
        k = min(k, len(chunks))

        # 截断候选数
        candidates = chunks[:MAX_DOCS_PER_RERANK]
        documents = [c.get("content", "") for c in candidates]

        # 尝试 DashScope rerank
        rerank_results = _dashscope_rerank(query, documents, top_n=k, api_key=self._api_key)

        if rerank_results is not None:
            # 按重排结果重组块
            reranked = []
            for r in rerank_results:
                idx = r["index"]
                if idx < len(candidates):
                    chunk = dict(candidates[idx])
                    chunk["rerank_score"] = float(r["relevance_score"])
                    reranked.append(chunk)
            logger.debug(f"DashScope rerank 完成，返回 {len(reranked)} 块")
            return reranked

        # 降级到 ContentReviewer
        logger.info("DashScope rerank 不可用，降级至 ContentReviewer")
        return _reviewer_rerank(query, candidates, top_n=k)


# ── 全局单例 ──────────────────────────────────────────────────────────────

_reranker: Reranker | None = None
_reranker_lock = threading.Lock()


def get_reranker() -> Reranker:
    """获取 Reranker 单例（线程安全）

    Returns:
        Reranker 实例
    """
    global _reranker
    if _reranker is None:
        with _reranker_lock:
            if _reranker is None:
                _reranker = Reranker()
    return _reranker
