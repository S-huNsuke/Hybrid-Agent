from typing import Optional
from pydantic import BaseModel
from rag_app.core.rag_system import get_rag_system
import json
from fastapi.responses import StreamingResponse


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    model: Optional[str] = "auto"
    use_rag: Optional[bool] = True
    stream: bool = True


class ChatResponse(BaseModel):
    success: bool
    message: str
    session_id: Optional[str] = None
    model_used: Optional[str] = None
    sources: Optional[list] = None
    error: Optional[str] = None


def resolve_model_type(model: str) -> str:
    if model == "auto":
        return "advanced"
    elif model == "deepseek-v3":
        return "advanced"
    else:
        return "base"


async def chat_stream(request: ChatRequest):
    rag_system = get_rag_system()
    session_id = request.session_id or "default"
    
    model_type = resolve_model_type(request.model)
    
    try:
        retrieved_docs = rag_system.vector_store.search(request.message, k=4)
        sources = []
        for doc in retrieved_docs:
            sources.append({
                "content": doc.page_content[:200],
                "filename": doc.metadata.get("filename", "unknown")
            })
        
        full_answer = ""
        
        for chunk in rag_system.query_with_stream(
            query=request.message,
            use_rag=True,
            model=model_type,
            k=4
        ):
            full_answer += chunk
            yield f"data: {json.dumps({'content': chunk})}\n\n"
        
        yield f"data: {json.dumps({'sources': sources, 'done': True})}\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


async def chat(request: ChatRequest) -> ChatResponse | StreamingResponse:
    try:
        rag_system = get_rag_system()
        
        session_id = request.session_id or "default"
        
        if request.use_rag:
            model_type = resolve_model_type(request.model)
            
            if request.stream:
                return StreamingResponse(
                    chat_stream(request),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    }
                )
            else:
                result = rag_system.query(
                    query=request.message,
                    use_rag=True,
                    model=model_type,
                    k=4
                )
                
                if result.get("success"):
                    return ChatResponse(
                        success=True,
                        message=result.get("answer", ""),
                        session_id=session_id,
                        model_used="DeepSeek + RAG",
                        sources=result.get("sources", [])
                    )
                else:
                    return ChatResponse(
                        success=False,
                        message="",
                        session_id=session_id,
                        error=result.get("error", "Unknown error")
                    )
        else:
            from rag_app.agent.builder import get_agent_instance
            
            agent = get_agent_instance()
            config = {
                "configurable": {
                    "thread_id": session_id,
                    "model": request.model
                }
            }
            
            full_response = ""
            
            for chunk, _ in agent.stream(
                {"messages": [("user", request.message)]},
                config,
                stream_mode="messages"
            ):
                if hasattr(chunk, 'content') and chunk.content:
                    if isinstance(chunk.content, str):
                        full_response += chunk.content
                    elif isinstance(chunk.content, list):
                        for item in chunk.content:
                            if isinstance(item, dict) and item.get('text'):
                                full_response += item['text']
            
            model_used = request.model if request.model != "auto" else "Qwen3"
            if request.model == "auto":
                model_used = "Qwen3/DeepSeek (Auto)"
            
            return ChatResponse(
                success=True,
                message=full_response,
                session_id=session_id,
                model_used=model_used,
                sources=[]
            )
        
    except Exception as e:
        return ChatResponse(
            success=False,
            message="",
            error=str(e)
        )
