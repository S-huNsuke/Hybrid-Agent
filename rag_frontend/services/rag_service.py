from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from rag_app.core.rag_system import get_rag_system


class RAGRequest(BaseModel):
    query: str
    document_ids: Optional[List[str]] = None
    top_k: int = 4
    use_rag: bool = True
    model: str = "advanced"


class RAGResponse(BaseModel):
    success: bool
    answer: str
    sources: List[Dict[str, Any]] = []
    error: Optional[str] = None
    context_chunks: Optional[int] = None


class DocumentAddRequest(BaseModel):
    filename: str
    content: bytes


class DocumentAddResponse(BaseModel):
    success: bool
    doc_id: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    chunks: Optional[int] = None


async def process_rag_query(request: RAGRequest) -> RAGResponse:
    try:
        rag_system = get_rag_system()
        
        result = rag_system.query(
            query=request.query,
            use_rag=request.use_rag,
            model=request.model,
            k=request.top_k
        )
        
        return RAGResponse(
            success=result.get("success", False),
            answer=result.get("answer", ""),
            sources=result.get("sources", []),
            error=result.get("error"),
            context_chunks=result.get("context_chunks")
        )
    except Exception as e:
        return RAGResponse(
            success=False,
            answer="",
            error=str(e)
        )


async def add_document_to_knowledge_base(
    filename: str,
    content: bytes
) -> DocumentAddResponse:
    try:
        rag_system = get_rag_system()
        
        result = rag_system.add_document(content, filename)
        
        if result.get("success"):
            return DocumentAddResponse(
                success=True,
                doc_id=result.get("doc_id"),
                message=result.get("message"),
                chunks=result.get("chunks")
            )
        else:
            return DocumentAddResponse(
                success=False,
                error=result.get("error", "Unknown error")
            )
    except Exception as e:
        return DocumentAddResponse(
            success=False,
            error=str(e)
        )


async def delete_document_from_knowledge_base(doc_id: str) -> Dict[str, Any]:
    try:
        rag_system = get_rag_system()
        result = rag_system.delete_document(doc_id)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


async def list_knowledge_base_documents() -> Dict[str, Any]:
    try:
        rag_system = get_rag_system()
        docs = rag_system.list_documents()
        return {
            "success": True,
            "documents": docs,
            "count": len(docs)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "documents": []
        }


async def search_in_knowledge_base(
    query: str,
    top_k: int = 4
) -> Dict[str, Any]:
    try:
        rag_system = get_rag_system()
        results = rag_system.search_documents(query, k=top_k)
        return {
            "success": True,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "results": []
        }


def get_rag_stats() -> Dict[str, Any]:
    try:
        rag_system = get_rag_system()
        return rag_system.get_stats()
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
