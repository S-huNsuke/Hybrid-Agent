"""FastAPI 应用入口"""

import os

from fastapi import APIRouter, FastAPI, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from hybrid_agent.api.schemas import ChatRequest, ChatResponse, ModelInfo
from hybrid_agent.api.auth.permissions import resolve_requested_group_id
from hybrid_agent.api.admin.router import admin_router
from hybrid_agent.api.routes.chat import (
    chat,
    chat_router,
    _get_optional_token_data as get_optional_chat_token_data,
)
from hybrid_agent.api.routes.documents import documents_router, list_documents, delete_document, get_document
from hybrid_agent.api.routes.documents import (
    _document_to_response as build_document_payload,
    _get_accessible_document_model as get_accessible_document_model,
    _list_accessible_document_models as list_accessible_document_models,
)
from hybrid_agent.api.auth.router import auth_router
from hybrid_agent.api.providers.router import providers_router
from hybrid_agent.llm.models import list_runtime_models

app = FastAPI(title="Hybrid-Agent API", version="1.0.0")

# CORS 配置
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
).split(",")
if "*" in allowed_origins:
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


def verify_api_key(x_api_key: str | None = Header(None)) -> str | None:
    """API Key 验证"""
    configured_key = os.getenv("API_KEY")
    
    # 如果未配置 API_KEY，跳过认证（开发模式）
    if not configured_key:
        return None
    
    # 已配置 API_KEY 时进行认证
    if x_api_key is None or x_api_key != configured_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


def _require_api_key_or_token(
    api_key: str | None,
    token_data,
) -> None:
    if api_key is None and token_data is None:
        raise HTTPException(status_code=401, detail="Not authenticated")


def _resolve_optional_group_id(
    token_data,
    requested_group_id: str | None,
    *,
    require_explicit_if_multiple: bool = False,
) -> str | None:
    return resolve_requested_group_id(
        token_data,
        requested_group_id,
        require_explicit_if_multiple=require_explicit_if_multiple,
    )


api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(providers_router)
api_v1_router.include_router(chat_router)
api_v1_router.include_router(documents_router)


def _health_payload():
    return {"status": "healthy"}


@app.get("/")
async def root():
    return {"message": "Hybrid-Agent API", "version": "1.0.0"}


@app.get("/health")
async def health_redirect():
    return RedirectResponse(url="/api/v1/health", status_code=307)


@api_v1_router.get("/health")
async def health():
    return _health_payload()


# ==================== 聊天接口 ====================

@app.post("/api/chat", response_model=None)
async def chat_endpoint(
    request: ChatRequest,
    api_key: str | None = Depends(verify_api_key),
    token_data=Depends(get_optional_chat_token_data),
) -> ChatResponse | StreamingResponse:
    group_id = (
        request.group_id
        if token_data is None
        else _resolve_optional_group_id(
            token_data,
            request.group_id,
            require_explicit_if_multiple=True,
        )
    )
    return await chat(request, group_id=group_id, token_data=token_data)


@app.get("/api/documents")
async def get_documents(
    group_id: str | None = None,
    api_key: str | None = Depends(verify_api_key),
    token_data=Depends(get_optional_chat_token_data),
):
    _require_api_key_or_token(api_key, token_data)
    if token_data is None:
        return await list_documents(group_id=group_id)
    documents = [build_document_payload(doc) for doc in list_accessible_document_models(token_data, group_id)]
    return {"success": True, "documents": [doc.model_dump() for doc in documents]}


@app.delete("/api/documents/{doc_id}")
async def remove_document(
    doc_id: str,
    group_id: str | None = None,
    api_key: str | None = Depends(verify_api_key),
    token_data=Depends(get_optional_chat_token_data),
):
    _require_api_key_or_token(api_key, token_data)
    if token_data is None:
        return await delete_document(doc_id, group_id=group_id)
    doc = get_accessible_document_model(doc_id, token_data, group_id)
    return await delete_document(doc_id, group_id=str(doc.group_id) if doc.group_id else None)


@app.get("/api/documents/{doc_id}")
async def get_document_endpoint(
    doc_id: str,
    group_id: str | None = None,
    api_key: str | None = Depends(verify_api_key),
    token_data=Depends(get_optional_chat_token_data),
):
    _require_api_key_or_token(api_key, token_data)
    if token_data is None:
        doc = await get_document(doc_id, group_id=group_id)
    else:
        doc = build_document_payload(get_accessible_document_model(doc_id, token_data, group_id))
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


# ==================== 模型接口 ====================

def _build_runtime_models_payload(
    token_data,
    requested_group_id: str | None = None,
) -> list[ModelInfo]:
    if token_data and not requested_group_id and len(token_data.group_ids) > 1:
        merged: dict[str, ModelInfo] = {}
        for group_id in [str(group_id) for group_id in token_data.group_ids if group_id]:
            for item in list_runtime_models(group_id=group_id):
                model = ModelInfo(**item)
                merged.setdefault(model.id, model)
        for item in list_runtime_models(group_id=None):
            model = ModelInfo(**item)
            merged.setdefault(model.id, model)
        return list(merged.values())

    resolved_group_id: str | None = _resolve_optional_group_id(token_data, requested_group_id)
    return [ModelInfo(**item) for item in list_runtime_models(group_id=resolved_group_id)]


@api_v1_router.get("/models", response_model=list[ModelInfo])
async def list_models_v1(
    group_id: str | None = None,
    token_data=Depends(get_optional_chat_token_data),
):
    return _build_runtime_models_payload(token_data, group_id)


@app.get("/api/models", response_model=list[ModelInfo])
async def list_models(
    group_id: str | None = None,
    token_data=Depends(get_optional_chat_token_data),
):
    return _build_runtime_models_payload(token_data, group_id)


app.include_router(api_v1_router)
