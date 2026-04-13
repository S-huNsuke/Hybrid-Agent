from __future__ import annotations

import os
import logging
from hashlib import sha256
from math import sqrt

from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document
from langchain_huggingface.embeddings import HuggingFaceEmbeddings

from hybrid_agent.core.config import get_project_root, DEFAULT_SEARCH_K

logger = logging.getLogger(__name__)


class LocalHashEmbeddings(Embeddings):
    """无外部依赖的本地 deterministic embedding fallback。"""

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in text.split():
            digest = sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class RAGConfig:
    """RAG 系统配置类"""
    def __init__(self):
        from hybrid_agent.core.config import settings
        self.tongyi_embedding_api_key = settings.tongyi_embedding_api_key
        self.tongyi_embedding_base_url = settings.tongyi_embedding_base_url
        self.embedding_backend = settings.embedding_backend or "sentence_transformers"
        self.embedding_model_name = (
            settings.embedding_model_name or "sentence-transformers/all-MiniLM-L6-v2"
        )
        self.embedding_cache_dir = settings.embedding_cache_dir
        self.chroma_db_path = settings.chroma_db_dir or str(get_project_root() / "chroma_db")
        self.collection_name = "documents"


class VectorStore:
    """向量存储检索器

    实现 RetrieverProtocol 协议。
    基于 Chroma 和可配置 embedding backend 实现稠密向量检索。
    """

    def __init__(self, config: RAGConfig) -> None:
        self.config = config
        self.embeddings = self._build_embeddings()
        
        persist_directory = getattr(config, 'chroma_db_path', './chroma_db')
        collection_name = getattr(config, 'collection_name', 'documents')
        
        os.makedirs(persist_directory, exist_ok=True)
        
        self.vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=persist_directory,
        )

    def _build_embeddings(self):
        """根据配置构建 embedding backend。"""
        backend = (self.config.embedding_backend or "sentence_transformers").lower()

        if backend == "dashscope":
            logger.info("使用 DashScope embedding backend")
            return DashScopeEmbeddings(
                dashscope_api_key=self.config.tongyi_embedding_api_key,
                model="text-embedding-v4",
            )

        cache_dir = self.config.embedding_cache_dir
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

        logger.info("使用开源 embedding backend: %s", self.config.embedding_model_name)
        try:
            return HuggingFaceEmbeddings(
                model_name=self.config.embedding_model_name,
                cache_folder=cache_dir,
            )
        except Exception as exc:
            if self.config.tongyi_embedding_api_key:
                logger.warning(
                    "开源 embedding 初始化失败，回退到 DashScopeEmbeddings: %s",
                    exc,
                )
                return DashScopeEmbeddings(
                    dashscope_api_key=self.config.tongyi_embedding_api_key,
                    model="text-embedding-v4",
                )

            logger.warning(
                "开源 embedding 初始化失败，回退到 LocalHashEmbeddings: %s",
                exc,
            )
            return LocalHashEmbeddings()
    
    def add_documents(
        self, 
        documents: list[Document], 
        ids: list[str] | None = None, 
        doc_id: str | None = None
    ) -> list[str]:
        """添加文档到向量存储
        
        Args:
            documents: 文档列表
            ids: 可选的文档 ID 列表
            doc_id: 可选的文档 ID，用于批量删除
            
        Returns:
            文档 ID 列表
            
        Raises:
            ValueError: 参数无效
            OSError: 存储错误
        """
        if not documents:
            return []
        
        if ids is None:
            ids = [f"doc_{i}" for i in range(len(documents))]
        
        # 为每个文档添加 doc_id 到 metadata，便于后续删除
        if doc_id:
            for doc in documents:
                if doc.metadata is None:
                    doc.metadata = {}
                doc.metadata["doc_id"] = doc_id
        
        self.vector_store.add_documents(documents=documents, ids=ids)
        return ids
    
    def search(self, query: str, k: int = DEFAULT_SEARCH_K, group_id: str | None = None) -> list[Document]:
        metadata_filter = self._build_filter(group_id)
        kwargs: dict[str, dict[str, str]] = {}
        if metadata_filter:
            kwargs["filter"] = metadata_filter
        return self.vector_store.similarity_search(query=query, k=k, **kwargs)

    def search_with_score(self, query: str, k: int = DEFAULT_SEARCH_K, group_id: str | None = None) -> list[tuple]:
        metadata_filter = self._build_filter(group_id)
        kwargs: dict[str, dict[str, str]] = {}
        if metadata_filter:
            kwargs["filter"] = metadata_filter
        return self.vector_store.similarity_search_with_score(query=query, k=k, **kwargs)

    def search_with_metadata(self, query: str, k: int = DEFAULT_SEARCH_K, group_id: str | None = None) -> list[dict]:
        """相似度搜索，返回包含完整 metadata（doc_id, chunk_id）的字典列表

        Args:
            query: 查询文本
            k: 返回数量

        Returns:
            list of {"content", "doc_id", "chunk_id", "metadata", "score", "retrieval_method"}
        """
        metadata_filter = self._build_filter(group_id)
        kwargs: dict[str, dict[str, str]] = {}
        if metadata_filter:
            kwargs["filter"] = metadata_filter
        results = self.vector_store.similarity_search_with_score(query=query, k=k, **kwargs)
        output = []
        for doc, score in results:
            meta = doc.metadata or {}
            output.append({
                "content": doc.page_content,
                "doc_id": meta.get("doc_id", ""),
                "chunk_id": meta.get("chunk_id", ""),
                "metadata": meta,
                "score": float(score),
                "retrieval_method": "dense",
            })
        return output

    def _build_filter(self, group_id: str | None) -> dict[str, str] | None:
        if not group_id:
            return None
        return {"group_id": group_id}
    
    def delete(self, ids: list[str]) -> None:
        """删除指定 ID 的向量"""
        if not ids:
            return
        try:
            self.vector_store.delete(ids=ids)
        except (ValueError, KeyError) as e:
            logger.error(f"删除向量失败: 无效的 ID 参数 - {e}")
            raise
        except OSError as e:
            logger.error(f"删除向量失败: 存储错误 - {e}")
            raise
        except Exception as e:
            logger.error(f"删除向量失败: {e}")
            raise

    def delete_by_doc_id_prefix(self, doc_id: str) -> int:
        """根据文档 ID 前缀删除向量"""
        try:
            collection = self.vector_store._collection
            
            # 优先使用 metadata 过滤删除（更高效）
            try:
                result = collection.get(where={"doc_id": doc_id})
                if result and result.get("ids"):
                    ids_to_delete = result["ids"]
                    collection.delete(ids=ids_to_delete)
                    return len(ids_to_delete)
            except (ValueError, KeyError, TypeError):
                # metadata 查询不支持或参数错误，降级到前缀匹配
                pass
            
            # 降级到 ID 前缀匹配（兼容旧数据）
            try:
                all_ids = collection.get().get('ids', [])
            except (ValueError, KeyError):
                all_ids = []
            
            ids_to_delete = [id for id in all_ids if id.startswith(f"{doc_id}_")]

            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
                return len(ids_to_delete)
            return 0
        except (ValueError, KeyError) as e:
            logger.error(f"删除向量失败: 参数错误 - {e}")
            return 0
        except OSError as e:
            logger.error(f"删除向量失败: 存储错误 - {e}")
            return 0
        except Exception as e:
            logger.error(f"删除向量失败: {e}")
            return 0
    
    def delete_all(self) -> None:
        self.vector_store.reset_collection()
    
    def get_collection_count(self) -> int:
        return self.vector_store._collection.count()


def get_vector_store() -> VectorStore:
    config = RAGConfig()
    return VectorStore(config)
