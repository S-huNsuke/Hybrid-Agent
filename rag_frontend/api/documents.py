from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from rag_app.core.rag_system import get_rag_system


class Document(BaseModel):
    id: str
    filename: str
    upload_time: str
    size: int
    status: str = "ready"


class UploadResponse(BaseModel):
    success: bool
    document: Optional[Document] = None
    error: Optional[str] = None


class DocumentListResponse(BaseModel):
    success: bool
    documents: List[Document] = []
    error: Optional[str] = None


async def upload_document(file_content: bytes, filename: str) -> UploadResponse:
    try:
        rag_system = get_rag_system()
        result = rag_system.add_document(file_content, filename)
        
        if result.get("success"):
            return UploadResponse(
                success=True,
                document=Document(
                    id=result.get("doc_id"),
                    filename=filename,
                    upload_time=datetime.now().isoformat(),
                    size=len(file_content),
                    status="ready"
                )
            )
        else:
            return UploadResponse(
                success=False,
                error=result.get("error", "Unknown error")
            )
        
    except Exception as e:
        return UploadResponse(
            success=False,
            error=str(e)
        )


async def list_documents() -> DocumentListResponse:
    try:
        rag_system = get_rag_system()
        docs = rag_system.list_documents()
        
        documents = [
            Document(
                id=doc.get("id"),
                filename=doc.get("filename"),
                upload_time=doc.get("created_at", ""),
                size=doc.get("file_size", 0),
                status=doc.get("status", "ready")
            )
            for doc in docs
        ]
        
        return DocumentListResponse(
            success=True,
            documents=documents
        )
    except Exception as e:
        return DocumentListResponse(
            success=False,
            error=str(e),
            documents=[]
        )


async def delete_document(doc_id: str) -> dict:
    try:
        rag_system = get_rag_system()
        result = rag_system.delete_document(doc_id)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_document(doc_id: str) -> Optional[Document]:
    try:
        rag_system = get_rag_system()
        docs = rag_system.list_documents()
        for doc in docs:
            if doc.get("id") == doc_id:
                return Document(
                    id=doc.get("id"),
                    filename=doc.get("filename"),
                    upload_time=doc.get("created_at", ""),
                    size=doc.get("file_size", 0),
                    status=doc.get("status", "ready")
                )
        return None
    except Exception:
        return None
