from __future__ import annotations

import os
import logging
from typing import TYPE_CHECKING

from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.documents import Document

from hybrid_agent.core.config import get_project_root

if TYPE_CHECKING:
    from hybrid_agent.core.vector import RAGConfig

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, config: RAGConfig) -> None:
        self.config = config
        self.embeddings = DashScopeEmbeddings(
            dashscope_api_key=config.tongyi_embedding_api_key,
            model="text-embedding-v3"
        )
        
        persist_directory = getattr(config, 'chroma_db_path', './chroma_db')
        collection_name = getattr(config, 'collection_name', 'documents')
        
        os.makedirs(persist_directory, exist_ok=True)
        
        self.vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=persist_directory,
        )
    
    def add_documents(self, documents: list[Document], ids: list[str] | None = None, doc_id: str | None = None) -> list[str]:
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
    
    def search(self, query: str, k: int = 4) -> list[Document]:
        return self.vector_store.similarity_search(query=query, k=k)
    
    def search_with_score(self, query: str, k: int = 4) -> list[tuple]:
        return self.vector_store.similarity_search_with_score(query=query, k=k)
    
    def delete(self, ids: list[str]) -> None:
        try:
            self.vector_store.delete(ids=ids)
        except Exception:
            pass

    def delete_by_doc_id_prefix(self, doc_id: str) -> int:
        try:
            collection = self.vector_store._collection
            
            # 优先使用 metadata 过滤删除（更高效）
            try:
                result = collection.get(where={"doc_id": doc_id})
                if result and result.get("ids"):
                    ids_to_delete = result["ids"]
                    collection.delete(ids=ids_to_delete)
                    return len(ids_to_delete)
            except Exception:
                pass
            
            # 降级到 ID 前缀匹配（兼容旧数据）
            all_ids = collection.get().get('ids', [])
            ids_to_delete = [id for id in all_ids if id.startswith(f"{doc_id}_")]

            if ids_to_delete:
                collection.delete(ids=ids_to_delete)
                return len(ids_to_delete)
            return 0
        except Exception as e:
            logger.error(f"删除向量失败: {e}")
            return 0
    
    def delete_all(self) -> None:
        self.vector_store.reset_collection()
    
    def get_collection_count(self) -> int:
        return self.vector_store._collection.count()


class RAGConfig:
    def __init__(self):
        from hybrid_agent.core.config import settings
        self.tongyi_embedding_api_key = settings.tongyi_embedding_api_key
        self.tongyi_embedding_base_url = settings.tongyi_embedding_base_url
        
        self.chroma_db_path = str(get_project_root() / "chroma_db")
        self.collection_name = "documents"


def get_vector_store() -> VectorStore:
    config = RAGConfig()
    return VectorStore(config)
