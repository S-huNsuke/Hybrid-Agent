"""API 数据模型定义"""

from typing import Any
from pydantic import BaseModel


# ==================== 聊天相关 ====================

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    model: str | None = "auto"
    use_rag: bool | None = True
    stream: bool = True


class ChatResponse(BaseModel):
    success: bool
    message: str
    session_id: str | None = None
    model_used: str | None = None
    sources: list | None = None
    error: str | None = None


# ==================== 文档相关 ====================

class Document(BaseModel):
    id: str
    filename: str
    upload_time: str
    size: int
    status: str = "ready"


class UploadResponse(BaseModel):
    success: bool
    document: Document | None = None
    error: str | None = None


class DocumentListResponse(BaseModel):
    success: bool
    documents: list[Document] = []
    error: str | None = None


# ==================== RAG 服务相关 ====================

class RAGRequest(BaseModel):
    query: str
    document_ids: list[str] | None = None
    top_k: int = 4
    use_rag: bool = True
    model: str = "advanced"


class RAGResponse(BaseModel):
    success: bool
    answer: str
    sources: list[dict[str, Any]] = []
    error: str | None = None
    context_chunks: int | None = None


class DocumentAddRequest(BaseModel):
    filename: str
    content: bytes


class DocumentAddResponse(BaseModel):
    success: bool
    doc_id: str | None = None
    message: str | None = None
    error: str | None = None
    chunks: int | None = None


# ==================== 模型相关 ====================

class ModelInfo(BaseModel):
    id: str
    name: str
    description: str
    is_available: bool = True


__all__ = [
    "ChatRequest",
    "ChatResponse",
    "Document",
    "UploadResponse",
    "DocumentListResponse",
    "RAGRequest",
    "RAGResponse",
    "DocumentAddRequest",
    "DocumentAddResponse",
    "ModelInfo",
]
