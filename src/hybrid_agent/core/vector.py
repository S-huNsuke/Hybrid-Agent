from __future__ import annotations

import os
import logging

from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.documents import Document

from hybrid_agent.core.config import get_project_root, DEFAULT_SEARCH_K

logger = logging.getLogger(__name__)


class RAGConfig:
    """RAG 系统配置类"""
    def __init__(self):
        from hybrid_agent.core.config import settings
        self.tongyi_embedding_api_key = settings.tongyi_embedding_api_key
        self.tongyi_embedding_base_url = settings.tongyi_embedding_base_url
        
        self.chroma_db_path = str(get_project_root() / "chroma_db")
        self.collection_name = "documents"


class VectorStore:
    def __init__(self, config: RAGConfig) -> None:
        self.config = config
        self.embeddings = DashScopeEmbeddings(
            dashscope_api_key=config.tongyi_embedding_api_key,
            model="text-embedding-v4"
        )
        
        persist_directory = getattr(config, 'chroma_db_path', './chroma_db')
        collection_name = getattr(config, 'collection_name', 'documents')
        
        os.makedirs(persist_directory, exist_ok=True)
        
        self.vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=persist_directory,
        )
    
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
    
    def search(self, query: str, k: int = DEFAULT_SEARCH_K) -> list[Document]:
        return self.vector_store.similarity_search(query=query, k=k)
    
    def search_with_score(self, query: str, k: int = DEFAULT_SEARCH_K) -> list[tuple]:
        return self.vector_store.similarity_search_with_score(query=query, k=k)
    
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
