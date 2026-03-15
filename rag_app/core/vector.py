import logging
import os
from typing import List, Optional

from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, config) -> None:
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
    
    def add_documents(self, documents: List[Document], ids: Optional[List[str]] = None) -> List[str]:
        if ids is None:
            ids = [f"doc_{i}" for i in range(len(documents))]
        
        self.vector_store.add_documents(documents=documents, ids=ids)
        return ids
    
    def search(self, query: str, k: int = 4) -> List[Document]:
        return self.vector_store.similarity_search(query=query, k=k)
    
    def search_with_score(self, query: str, k: int = 4) -> List[tuple]:
        return self.vector_store.similarity_search_with_score(query=query, k=k)
    
    def delete(self, ids: List[str]) -> None:
        try:
            self.vector_store.delete(ids=ids)
        except Exception:
            pass

    def delete_by_doc_id_prefix(self, doc_id: str) -> int:
        try:
            collection = self.vector_store._collection
            all_ids = collection.get()['ids']
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
        from rag_app.core.config import settings
        self.tongyi_embedding_api_key = settings.tongyi_embedding_api_key
        self.tongyi_embedding_base_url = settings.tongyi_embedding_base_url
        
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.chroma_db_path = os.path.join(project_root, "chroma_db")
        self.collection_name = "documents"


def get_vector_store() -> VectorStore:
    config = RAGConfig()
    return VectorStore(config)
