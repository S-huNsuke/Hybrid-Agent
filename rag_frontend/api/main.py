from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
import os
from typing import Optional

from rag_frontend.api.chat import ChatRequest, chat
from rag_frontend.api.documents import upload_document, list_documents, delete_document

app = FastAPI(title="Hybrid-Agent API", version="1.0.0")

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


def verify_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    configured_key = os.getenv("API_KEY")
    if not configured_key:
        raise HTTPException(status_code=500, detail="Server API key not configured")
    if x_api_key is None or x_api_key != configured_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


@app.get("/")
async def root():
    return {"message": "Hybrid-Agent API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest, api_key: str = Depends(verify_api_key)):
    return await chat(request)


@app.post("/api/documents/upload")
async def upload_file(file: UploadFile = File(...), api_key: str = Depends(verify_api_key)):
    content = await file.read()
    return await upload_document(content, file.filename)


@app.get("/api/documents")
async def get_documents(api_key: str = Depends(verify_api_key)):
    return await list_documents()


@app.delete("/api/documents/{doc_id}")
async def remove_document(doc_id: str, api_key: str = Depends(verify_api_key)):
    return await delete_document(doc_id)


@app.get("/api/documents/{doc_id}")
async def get_document(doc_id: str, api_key: str = Depends(verify_api_key)):
    from rag_frontend.api.documents import get_document as get_doc
    doc = await get_doc(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc
