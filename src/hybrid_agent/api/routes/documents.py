"""文档路由"""

from datetime import datetime

from hybrid_agent.api.schemas import (
    Document,
    UploadResponse,
    DocumentListResponse,
)
from hybrid_agent.core.rag_system import get_rag_system


async def upload_document(file_content: bytes, filename: str) -> UploadResponse:
    """上传文档"""
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
        
    except (KeyError, ValueError) as e:
        return UploadResponse(
            success=False,
            error=f"参数错误: {str(e)}"
        )
    except Exception as e:
        return UploadResponse(
            success=False,
            error=str(e)
        )


async def list_documents() -> DocumentListResponse:
    """列出所有文档"""
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
    except (KeyError, ValueError) as e:
        return DocumentListResponse(
            success=False,
            error=f"参数错误: {str(e)}",
            documents=[]
        )
    except Exception as e:
        return DocumentListResponse(
            success=False,
            error=str(e),
            documents=[]
        )


async def delete_document(doc_id: str) -> dict:
    """删除文档"""
    try:
        rag_system = get_rag_system()
        result = rag_system.delete_document(doc_id)
        return result
    except (KeyError, ValueError) as e:
        return {"success": False, "error": f"参数错误: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_document(doc_id: str) -> Document | None:
    """获取单个文档"""
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
    except (KeyError, ValueError):
        return None
    except Exception:
        return None
