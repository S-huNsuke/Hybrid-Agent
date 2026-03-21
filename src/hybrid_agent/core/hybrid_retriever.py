"""混合检索模块：BM25 稀疏检索 + 向量稠密检索 + RRF 融合

多路召回架构：
    Path A: Dense 向量检索  (VectorStore.search_with_metadata)
    Path B: BM25 稀疏检索   (BM25Retriever)
    Path C: HyDE 向量检索   (HyDE假设文档嵌入后再检索，由 query_understanding 提供)
    Path D: 子问题并行检索  (SubQueryDecomposer 拆分后各路合并)
    ↓
    RRF 融合 (k=60, 去重)
    ↓
    DashScope Rerank → top-K
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from typing import TYPE_CHECKING

from rank_bm25 import BM25Okapi

from hybrid_agent.core.database import BM25ChunkModel, db_manager
from hybrid_agent.core.vector import VectorStore, RAGConfig
from hybrid_agent.core.config import RRF_K, RETRIEVE_K_PER_PATH

if TYPE_CHECKING:
    from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def _bigram_tokenize(text: str) -> list[str]:
    """字符级 bigram 分词，无需 jieba 词典依赖

    Args:
        text: 输入文本

    Returns:
        bigram token 列表
    """
    text = text.strip()
    if len(text) <= 1:
        return list(text)
    return [text[i:i + 2] for i in range(len(text) - 1)]


class BM25Retriever:
    """BM25 稀疏检索器，基于 SQLite bm25_chunks 表构建索引

    实现 RetrieverProtocol 和 IndexableRetrieverProtocol 协议。

    索引构建策略：懒加载，首次 search 时从数据库加载全量数据；
    文档新增/删除时调用 index_chunks/delete_chunks 触发重建标记。
    """

    def __init__(self) -> None:
        self._corpus: list[str] = []        # 原始文本
        self._chunk_ids: list[str] = []     # 对应 chunk_id
        self._doc_ids: list[str] = []       # 对应 doc_id
        self._bm25: BM25Okapi | None = None
        self._dirty = True  # 标记索引是否需要重建
        self._lock = threading.Lock()       # 保护索引重建与检索

    def _rebuild_index(self) -> None:
        """从数据库重建 BM25 索引"""
        chunks = db_manager.get_all_bm25_chunks()
        if not chunks:
            self._corpus = []
            self._chunk_ids = []
            self._doc_ids = []
            self._bm25 = None
            self._dirty = False
            return

        corpus_tokens = []
        self._corpus = []
        self._chunk_ids = []
        self._doc_ids = []

        for c in chunks:
            if c.tokens:
                try:
                    tokens = json.loads(c.tokens)
                except (json.JSONDecodeError, TypeError):
                    tokens = _bigram_tokenize(c.content)
            else:
                tokens = _bigram_tokenize(c.content)

            corpus_tokens.append(tokens)
            self._corpus.append(c.content)
            self._chunk_ids.append(c.id)
            self._doc_ids.append(c.doc_id)

        self._bm25 = BM25Okapi(corpus_tokens)
        self._dirty = False
        logger.debug(f"BM25 索引重建完成，共 {len(chunks)} 个文本块")

    def index_chunks(self, doc_id: str, chunks: list[str], chunk_ids: list[str] | None = None) -> None:
        """将文档的文本块写入 BM25 索引（SQLite 持久化）

        Args:
            doc_id: 文档 ID
            chunks: 文本块内容列表
            chunk_ids: 对应的 chunk_id 列表，默认自动生成
        """
        if not chunks:
            return

        if chunk_ids is None:
            chunk_ids = [f"{doc_id}_{i}" for i in range(len(chunks))]

        models = []
        for cid, content in zip(chunk_ids, chunks):
            tokens = _bigram_tokenize(content)
            models.append(BM25ChunkModel(
                id=cid,
                doc_id=doc_id,
                content=content,
                tokens=json.dumps(tokens, ensure_ascii=False),
            ))

        db_manager.add_bm25_chunks(models)
        with self._lock:
            self._dirty = True
        logger.debug(f"BM25 已索引文档 {doc_id}，共 {len(chunks)} 块")

    def delete_chunks(self, doc_id: str) -> int:
        """删除指定文档的 BM25 索引

        Args:
            doc_id: 文档 ID

        Returns:
            删除的块数量
        """
        count = db_manager.delete_bm25_chunks(doc_id)
        with self._lock:
            self._dirty = True
        logger.debug(f"BM25 已删除文档 {doc_id} 的 {count} 个块")
        return count

    def search(self, query: str, k: int = RETRIEVE_K_PER_PATH) -> list[dict]:
        """BM25 检索

        Args:
            query: 查询文本
            k: 返回数量

        Returns:
            list of {"content", "doc_id", "chunk_id", "score", "retrieval_method"}
        """
        with self._lock:
            if self._dirty:
                self._rebuild_index()

            if self._bm25 is None or not self._corpus:
                return []

            query_tokens = _bigram_tokenize(query)
            scores = self._bm25.get_scores(query_tokens)

            # 取 top-k
            top_k = min(k, len(scores))
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

            results = []
            for idx in top_indices:
                if scores[idx] <= 0:
                    continue
                results.append({
                    "content": self._corpus[idx],
                    "doc_id": self._doc_ids[idx],
                    "chunk_id": self._chunk_ids[idx],
                    "metadata": {"doc_id": self._doc_ids[idx]},
                    "score": float(scores[idx]),
                    "retrieval_method": "bm25",
                })
            return results


def _rrf_merge(all_results: list[list[dict]], k: int = RRF_K) -> list[dict]:
    """Reciprocal Rank Fusion（RRF）多路结果融合

    RRF 公式：score(d) = Σ 1/(k + rank_i(d))，k=60

    Args:
        all_results: 各路检索结果列表，每路结果按相关性排序
        k: RRF 平滑参数，默认 60

    Returns:
        融合后按 RRF 分数排序的去重结果列表
    """
    rrf_scores: dict[str, float] = {}
    chunk_data: dict[str, dict] = {}  # chunk_id → chunk dict（保留最佳来源数据）

    for results in all_results:
        for rank, chunk in enumerate(results, start=1):
            # 用 content 的前 200 字符作为去重键（避免不同路径返回同一内容但 chunk_id 不同）
            dedup_key = chunk.get("chunk_id") or chunk["content"][:200]
            rrf_scores[dedup_key] = rrf_scores.get(dedup_key, 0.0) + 1.0 / (k + rank)
            if dedup_key not in chunk_data:
                chunk_data[dedup_key] = dict(chunk)  # 存副本，避免原地修改影响调用方
            else:
                # 合并 retrieval_method 记录
                existing = chunk_data[dedup_key]
                existing_method = existing.get("retrieval_method", "")
                new_method = chunk.get("retrieval_method", "")
                if new_method and new_method not in existing_method:
                    existing["retrieval_method"] = f"{existing_method},{new_method}"

    # 按 RRF 分数排序
    merged = []
    for dedup_key, rrf_score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
        chunk = dict(chunk_data[dedup_key])
        chunk["rrf_score"] = rrf_score
        merged.append(chunk)

    return merged


# ── 全局单例 ──────────────────────────────────────────────────────────────

_bm25_retriever: BM25Retriever | None = None
_bm25_lock = threading.Lock()


def get_bm25_retriever() -> BM25Retriever:
    """获取 BM25 检索器单例（线程安全）"""
    global _bm25_retriever
    if _bm25_retriever is None:
        with _bm25_lock:
            if _bm25_retriever is None:
                _bm25_retriever = BM25Retriever()
    return _bm25_retriever


class MultiPathRetriever:
    """多路召回控制器，并发执行各路径后 RRF 合并

    支持的路径：
        Path A: Dense 向量检索（始终激活）
        Path B: BM25 稀疏检索（始终激活）
        Path C: HyDE 向量检索（hyde_doc 非空时激活）
        Path D: 子问题并行检索（sub_queries 非空时激活）

    Args:
        vector_store: VectorStore 实例
        bm25_retriever: BM25Retriever 实例
        k_per_path: 每路检索候选数
    """

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_retriever: BM25Retriever,
        k_per_path: int = RETRIEVE_K_PER_PATH,
    ) -> None:
        self.vector_store = vector_store
        self.bm25 = bm25_retriever
        self.k_per_path = k_per_path

    async def _dense_retrieve(self, query: str) -> list[dict]:
        """Path A/C: 稠密向量检索（同步包装为异步）

        Args:
            query: 查询文本或 HyDE 假设文档

        Returns:
            检索结果列表
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.vector_store.search_with_metadata(query, k=self.k_per_path)
        )

    async def _bm25_retrieve(self, query: str) -> list[dict]:
        """Path B: BM25 稀疏检索（同步包装为异步）

        Args:
            query: 查询文本

        Returns:
            检索结果列表
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.bm25.search(query, k=self.k_per_path)
        )

    async def _retrieve_subquery(self, sub_query: str) -> list[dict]:
        """Path D: 子问题检索（Dense + BM25 合并后返回）

        Args:
            sub_query: 子问题文本

        Returns:
            合并后的检索结果
        """
        dense_res, bm25_res = await asyncio.gather(
            self._dense_retrieve(sub_query),
            self._bm25_retrieve(sub_query),
        )
        # 标记来源
        for r in dense_res:
            r["retrieval_method"] = f"subquery_dense[{sub_query[:20]}]"
        for r in bm25_res:
            r["retrieval_method"] = f"subquery_bm25[{sub_query[:20]}]"
        return _rrf_merge([dense_res, bm25_res])

    async def retrieve(
        self,
        query: str,
        sub_queries: list[str] | None = None,
        hyde_doc: str | None = None,
    ) -> list[dict]:
        """多路并发检索 + RRF 融合

        Args:
            query: 原始查询
            sub_queries: 子问题列表（Path D，可选）
            hyde_doc: HyDE 假设文档（Path C，可选）

        Returns:
            RRF 融合后的结果列表（按 rrf_score 降序）
        """
        tasks = [
            self._dense_retrieve(query),   # Path A
            self._bm25_retrieve(query),    # Path B
        ]

        path_names = ["dense", "bm25"]

        if hyde_doc:
            tasks.append(self._dense_retrieve(hyde_doc))  # Path C
            path_names.append("hyde")

        if sub_queries:
            for sq in sub_queries:
                tasks.append(self._retrieve_subquery(sq))  # Path D
            path_names.extend([f"subquery_{i}" for i in range(len(sub_queries))])

        all_results = await asyncio.gather(*tasks)

        # 标记各路径的 retrieval_method（Path A/B 已由方法内部设置）
        if hyde_doc:
            hyde_idx = 2
            for r in all_results[hyde_idx]:
                r["retrieval_method"] = "hyde"

        merged = _rrf_merge(list(all_results))

        logger.debug(
            f"多路召回完成：激活路径 {path_names}，"
            f"融合后 {len(merged)} 个候选块"
        )
        return merged

    def retrieve_sync(
        self,
        query: str,
        sub_queries: list[str] | None = None,
        hyde_doc: str | None = None,
    ) -> list[dict]:
        """同步版本的多路检索（兼容同步调用场景）

        Args:
            query: 原始查询
            sub_queries: 子问题列表
            hyde_doc: HyDE 假设文档

        Returns:
            RRF 融合后的结果列表
        """
        coro = self.retrieve(query, sub_queries, hyde_doc)
        try:
            # 已在运行中的事件循环（如 FastAPI async handler）→ 新线程中执行
            asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        except RuntimeError:
            # 没有运行中的事件循环（同步上下文）→ 直接运行
            return asyncio.run(coro)


# ── 全局单例工厂 ──────────────────────────────────────────────────────────

_multi_path_retriever: MultiPathRetriever | None = None
_multi_path_lock = threading.Lock()


def get_multi_path_retriever() -> MultiPathRetriever:
    """获取 MultiPathRetriever 单例（线程安全延迟初始化）

    Returns:
        MultiPathRetriever 实例
    """
    global _multi_path_retriever
    if _multi_path_retriever is None:
        with _multi_path_lock:
            if _multi_path_retriever is None:
                from hybrid_agent.core.vector import get_vector_store
                _multi_path_retriever = MultiPathRetriever(
                    vector_store=get_vector_store(),
                    bm25_retriever=get_bm25_retriever(),
                )
    return _multi_path_retriever
