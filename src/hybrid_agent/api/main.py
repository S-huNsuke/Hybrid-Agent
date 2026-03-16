"""FastAPI 应用入口"""

import os

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from hybrid_agent.api.schemas import ChatRequest, ChatResponse, ModelInfo
from hybrid_agent.api.routes.chat import chat
from hybrid_agent.api.routes.documents import upload_document, list_documents, delete_document, get_document

app = FastAPI(title="Hybrid-Agent API", version="1.0.0")

# CORS 配置
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8501").split(",")
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


# ==================== 健康检查 ====================

@app.get("/")
async def root():
    return {"message": "Hybrid-Agent API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ==================== 聊天接口 ====================

@app.post("/api/chat", response_model=None)
async def chat_endpoint(request: ChatRequest, api_key: str | None = Depends(verify_api_key)) -> ChatResponse | StreamingResponse:
    return await chat(request)


# ==================== 文档接口 ====================

@app.post("/api/documents/upload")
async def upload_file(file: UploadFile = File(...), api_key: str | None = Depends(verify_api_key)):
    content = await file.read()
    return await upload_document(content, file.filename)


@app.get("/api/documents")
async def get_documents(api_key: str | None = Depends(verify_api_key)):
    return await list_documents()


@app.delete("/api/documents/{doc_id}")
async def remove_document(doc_id: str, api_key: str | None = Depends(verify_api_key)):
    return await delete_document(doc_id)


@app.get("/api/documents/{doc_id}")
async def get_document_endpoint(doc_id: str, api_key: str | None = Depends(verify_api_key)):
    doc = await get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


# ==================== 模型接口 ====================

AVAILABLE_MODELS = [
    ModelInfo(
        id="auto",
        name="自动选择",
        description="根据问题复杂度自动选择合适的模型"
    ),
    ModelInfo(
        id="qwen3-omni",
        name="Qwen3 Omni",
        description="基础模型，适合简单问题，响应速度快"
    ),
    ModelInfo(
        id="deepseek-v3",
        name="DeepSeek V3",
        description="增强模型，适合复杂问题，深度思考"
    ),
]


@app.get("/api/models")
async def list_models():
    return AVAILABLE_MODELS
