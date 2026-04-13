"""文档路由"""

from datetime import datetime
from threading import Lock
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from hybrid_agent.api.schemas import (
    Document,
    DocumentListResponse,
    UploadResponse,
    UploadTaskResponse,
    TaskStatus,
)
from hybrid_agent.api.auth.permissions import resolve_requested_group_id
from hybrid_agent.core.rag_system import get_rag_system
from hybrid_agent.core.database import DocumentModel, db_manager
from hybrid_agent.api.auth.service import TokenData, auth_service

documents_router = APIRouter(tags=["documents"])

_bearer_scheme = HTTPBearer(auto_error=False)
_task_store: dict[str, dict[str, Any]] = {}
_task_lock = Lock()


def _get_optional_token_data(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme)
) -> TokenData | None:
    if not credentials or credentials.scheme.lower() != "bearer":
        return None
    try:
        return auth_service.decode_access_token(credentials.credentials)
    except HTTPException as exc:
        if exc.status_code == 401:
            return None
        raise


def _resolve_group_id(
    token_data: TokenData | None,
    requested_group_id: str | None = None,
    *,
    require_explicit_if_multiple: bool = False,
) -> str | None:
    return resolve_requested_group_id(
        token_data,
        requested_group_id,
        require_explicit_if_multiple=require_explicit_if_multiple,
    )


def _require_token_data(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> TokenData:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Not authenticated")
    return auth_service.decode_access_token(credentials.credentials)


async def upload_document(
    file_content: bytes, filename: str, group_id: str | None = None
) -> UploadResponse:
    """上传文档"""
    try:
        rag_system = get_rag_system()
        result = rag_system.add_document(file_content, filename, group_id=group_id)
        doc_id = result.get("doc_id")
        if result.get("success") and isinstance(doc_id, str):
            return UploadResponse(
                success=True,
                document=Document(
                    id=doc_id,
                    filename=filename,
                    upload_time=datetime.utcnow().isoformat(),
                    size=len(file_content),
                    status="ready",
                ),
            )
        return UploadResponse(success=False, error=result.get("error", "Unknown error"))
    except (KeyError, ValueError) as exc:
        return UploadResponse(success=False, error=f"参数错误: {exc}")
    except Exception as exc:
        return UploadResponse(success=False, error=str(exc))


async def list_documents(group_id: str | None = None) -> DocumentListResponse:
    """列出所有文档"""
    try:
        rag_system = get_rag_system()
        docs = rag_system.list_documents(group_id=group_id)
        documents = [
            Document(
                id=str(doc.get("id", "")),
                filename=str(doc.get("filename", "")),
                upload_time=str(doc.get("created_at", "")),
                size=int(doc.get("file_size", 0) or 0),
                status=str(doc.get("status", "ready")),
            )
            for doc in docs
        ]
        return DocumentListResponse(success=True, documents=documents)
    except (KeyError, ValueError) as exc:
        return DocumentListResponse(success=False, error=f"参数错误: {exc}", documents=[])
    except Exception as exc:
        return DocumentListResponse(success=False, error=str(exc), documents=[])


async def delete_document(doc_id: str, group_id: str | None = None) -> dict:
    """删除文档"""
    try:
        rag_system = get_rag_system()
        result = rag_system.delete_document(doc_id, group_id=group_id)
        return result
    except (KeyError, ValueError) as exc:
        return {"success": False, "error": f"参数错误: {exc}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def get_document(doc_id: str, group_id: str | None = None) -> Document | None:
    """获取单个文档"""
    try:
        rag_system = get_rag_system()
        docs = rag_system.list_documents(group_id=group_id)
        for doc in docs:
            if doc.get("id") == doc_id:
                return Document(
                    id=str(doc.get("id", "")),
                    filename=str(doc.get("filename", "")),
                    upload_time=str(doc.get("created_at", "")),
                    size=int(doc.get("file_size", 0) or 0),
                    status=str(doc.get("status", "ready")),
                )
        return None
    except (KeyError, ValueError):
        return None
    except Exception:
        return None


def _document_to_response(doc: DocumentModel) -> Document:
    return Document(
        id=str(doc.id),
        filename=str(doc.filename),
        upload_time=doc.created_at.isoformat() if doc.created_at else "",
        size=int(doc.file_size or 0),
        status=str(doc.status or "ready"),
    )


def _can_access_document(doc: DocumentModel, token_data: TokenData) -> bool:
    if token_data.role.lower() == "admin":
        return True
    if doc.group_id is None:
        return True
    return str(doc.group_id) in token_data.group_roles


def _list_accessible_document_models(
    token_data: TokenData,
    requested_group_id: str | None,
) -> list[DocumentModel]:
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database unavailable")

    resolved_group_id = _resolve_group_id(token_data, requested_group_id)
    if token_data.role.lower() == "admin":
        if resolved_group_id is None:
            return db_manager.get_all_documents()
        return db_manager.list_documents_by_group(resolved_group_id)

    if resolved_group_id is not None:
        docs = db_manager.list_documents_by_group(resolved_group_id)
        return docs + db_manager.list_documents_without_group()

    group_ids = [str(group_id) for group_id in token_data.group_ids if group_id]
    docs = db_manager.list_documents_without_group()
    if group_ids:
        docs.extend(db_manager.list_documents_by_group_ids(group_ids))
    seen: dict[str, DocumentModel] = {str(doc.id): doc for doc in docs}
    return list(seen.values())


def _get_accessible_document_model(
    doc_id: str,
    token_data: TokenData,
    requested_group_id: str | None = None,
) -> DocumentModel:
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database unavailable")
    resolved_group_id = _resolve_group_id(token_data, requested_group_id)
    doc = db_manager.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if resolved_group_id is not None and doc.group_id is not None and str(doc.group_id) != resolved_group_id:
        raise HTTPException(status_code=404, detail="Document not found")
    if not _can_access_document(doc, token_data):
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _create_task_record(
    task_id: str,
    filename: str,
    status: str,
    progress: int,
    group_id: str | None,
    user_id: str | None,
) -> None:
    with _task_lock:
        _task_store[task_id] = {
            "task_id": task_id,
            "filename": filename,
            "status": status,
            "progress": progress,
            "group_id": group_id,
            "user_id": user_id,
            "document_id": None,
            "message": None,
            "error": None,
        }


def _update_task(task_id: str, **fields: Any) -> None:
    with _task_lock:
        if task_id not in _task_store:
            return
        _task_store[task_id].update(fields)


def _get_task(task_id: str) -> dict[str, Any] | None:
    with _task_lock:
        return _task_store.get(task_id)


def _assert_task_access(task: dict[str, Any], token_data: TokenData) -> None:
    if token_data.role.lower() == "admin":
        return
    task_user_id = task.get("user_id")
    task_group_id = task.get("group_id")
    if task_user_id and task_user_id == token_data.user_id:
        return
    if task_group_id and str(task_group_id) in token_data.group_roles:
        return
    raise HTTPException(status_code=403, detail="Forbidden")


async def _run_upload_task(task_id: str, content: bytes, filename: str, group_id: str | None) -> None:
    rag_system = get_rag_system()
    try:
        _update_task(task_id, status="processing", progress=30)
        result = rag_system.add_document(content, filename, group_id=group_id)
        if result.get("success"):
            _update_task(task_id, status="done", progress=100, document_id=result.get("doc_id"))
        else:
            _update_task(task_id, status="failed", progress=100, error=result.get("error"))
    except Exception as exc:
        _update_task(task_id, status="failed", progress=100, error=str(exc))


@documents_router.post("/documents/upload", response_model=UploadTaskResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    group_id: str | None = None,
    token_data: TokenData = Depends(_require_token_data),
) -> UploadTaskResponse:
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    group_id = _resolve_group_id(
        token_data,
        group_id,
        require_explicit_if_multiple=True,
    )
    user_id = token_data.user_id
    task_id = str(uuid.uuid4())
    content = await file.read()
    _create_task_record(
        task_id,
        filename,
        status="queued",
        progress=10,
        group_id=group_id,
        user_id=user_id,
    )
    background_tasks.add_task(_run_upload_task, task_id, content, filename, group_id)
    return UploadTaskResponse(
        success=True,
        task_id=task_id,
        status="queued",
        progress=10,
        message="Upload task submitted",
    )


@documents_router.get("/documents/tasks/{task_id}", response_model=TaskStatus)
async def get_upload_task(
    task_id: str,
    token_data: TokenData = Depends(_require_token_data),
) -> TaskStatus:
    task = _get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    _assert_task_access(task, token_data)
    return TaskStatus(**task)


@documents_router.get("/documents")
async def get_documents(
    group_id: str | None = None,
    token_data: TokenData = Depends(_require_token_data),
) -> DocumentListResponse:
    try:
        docs = _list_accessible_document_models(token_data, group_id)
        documents = [_document_to_response(doc) for doc in docs]
        return DocumentListResponse(success=True, documents=documents)
    except (KeyError, ValueError) as exc:
        return DocumentListResponse(success=False, error=f"参数错误: {exc}", documents=[])
    except HTTPException:
        raise
    except Exception as exc:
        return DocumentListResponse(success=False, error=str(exc), documents=[])


@documents_router.delete("/documents/{doc_id}")
async def remove_document(
    doc_id: str,
    group_id: str | None = None,
    token_data: TokenData = Depends(_require_token_data),
) -> dict:
    try:
        doc = _get_accessible_document_model(doc_id, token_data, group_id)
        rag_system = get_rag_system()
        result = rag_system.delete_document(doc_id, group_id=str(doc.group_id) if doc.group_id else None)
        return result
    except (KeyError, ValueError) as exc:
        return {"success": False, "error": f"参数错误: {exc}"}
    except HTTPException:
        raise
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@documents_router.get("/documents/{doc_id}")
async def get_document_route(
    doc_id: str,
    group_id: str | None = None,
    token_data: TokenData = Depends(_require_token_data),
) -> Document:
    try:
        doc = _get_accessible_document_model(doc_id, token_data, group_id)
        return _document_to_response(doc)
    except (KeyError, ValueError):
        raise HTTPException(status_code=404, detail="Document not found")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
