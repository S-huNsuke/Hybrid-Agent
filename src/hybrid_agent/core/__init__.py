"""核心模块 - 配置、数据库、向量存储、RAG系统、混合检索"""

from hybrid_agent.core.config import (
    settings,
    get_project_root,
    DEFAULT_SEARCH_K,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHILD_CHUNK_SIZE,
    DEFAULT_CHILD_CHUNK_OVERLAP,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_ADVANCED_MAX_TOKENS,
    DEFAULT_TIMEOUT,
    DEFAULT_COMPLEXITY_THRESHOLD,
    ReviewerSettings,
    default_reviewer_settings,
    # Agentic RAG 配置
    AGENTIC_MAX_ITERATIONS,
    AGENTIC_REFLECTION_THRESHOLD,
    AGENTIC_FINAL_TOP_K,
    # 混合检索配置
    RRF_K,
    RETRIEVE_K_PER_PATH,
    DEFAULT_RERANK_TOP_K,
    MAX_DOCS_PER_RERANK,
    # 查询理解配置
    COMPLEX_QUERY_THRESHOLD,
    MAX_SUB_QUERIES,
    QUERY_UNDERSTANDING_TIMEOUT,
    QUERY_UNDERSTANDING_MAX_TOKENS,
    # 会话管理配置
    MAX_ROUNDS_BEFORE_SUMMARY,
    SESSION_TTL,
    SESSION_MAX_SIZE,
    SUMMARY_MAX_TOKENS,
)
from hybrid_agent.core.database import db_manager, DocumentModel
from hybrid_agent.core.vector import get_vector_store, VectorStore
from hybrid_agent.core.document_processor import document_processor, DocumentProcessor
from hybrid_agent.core.rag_system import get_rag_system, RAGSystem
from hybrid_agent.core.protocols import (
    RetrieverProtocol,
    AsyncRetrieverProtocol,
    IndexableRetrieverProtocol,
)

__all__ = [
    # 配置
    "settings",
    "get_project_root",
    "DEFAULT_SEARCH_K",
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_CHUNK_OVERLAP",
    "DEFAULT_CHILD_CHUNK_SIZE",
    "DEFAULT_CHILD_CHUNK_OVERLAP",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_ADVANCED_MAX_TOKENS",
    "DEFAULT_TIMEOUT",
    "DEFAULT_COMPLEXITY_THRESHOLD",
    "ReviewerSettings",
    "default_reviewer_settings",
    # Agentic RAG 配置
    "AGENTIC_MAX_ITERATIONS",
    "AGENTIC_REFLECTION_THRESHOLD",
    "AGENTIC_FINAL_TOP_K",
    # 混合检索配置
    "RRF_K",
    "RETRIEVE_K_PER_PATH",
    "DEFAULT_RERANK_TOP_K",
    "MAX_DOCS_PER_RERANK",
    # 查询理解配置
    "COMPLEX_QUERY_THRESHOLD",
    "MAX_SUB_QUERIES",
    "QUERY_UNDERSTANDING_TIMEOUT",
    "QUERY_UNDERSTANDING_MAX_TOKENS",
    # 会话管理配置
    "MAX_ROUNDS_BEFORE_SUMMARY",
    "SESSION_TTL",
    "SESSION_MAX_SIZE",
    "SUMMARY_MAX_TOKENS",
    # 数据库
    "db_manager",
    "DocumentModel",
    # 向量存储
    "get_vector_store",
    "VectorStore",
    # 文档处理
    "document_processor",
    "DocumentProcessor",
    # RAG 系统
    "get_rag_system",
    "RAGSystem",
    # 协议
    "RetrieverProtocol",
    "AsyncRetrieverProtocol",
    "IndexableRetrieverProtocol",
]
