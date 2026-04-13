"""聊天路由"""

import json
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langchain_core.messages import ToolMessage
from langchain_core.exceptions import LangChainException

from hybrid_agent.api.schemas import (
    ChatRequest,
    ChatResponse,
    ChatSessionDeleteResponse,
    ChatSessionItem,
    ChatSessionListResponse,
    ChatSessionRenameRequest,
)
from hybrid_agent.api.auth.permissions import resolve_requested_group_id
from hybrid_agent.api.auth.service import TokenData, auth_service
from hybrid_agent.core.rag_system import get_rag_system
from hybrid_agent.core.config import DEFAULT_SEARCH_K
from hybrid_agent.core.database import ChatSessionModel, db_manager
from hybrid_agent.llm.model_selector import resolve_runtime_selection
from hybrid_agent.agent.builder import get_agent_instance

logger = logging.getLogger(__name__)


chat_router = APIRouter(tags=["chat"])

_bearer_scheme = HTTPBearer(auto_error=False)


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


def _derive_session_title(message: str) -> str:
    cleaned = message.strip()
    if not cleaned:
        return "New Chat"
    if len(cleaned) <= 80:
        return cleaned
    return cleaned[:77] + "..."


def _touch_chat_session(
    *,
    session_id: str,
    title: str,
    user_id: str | None,
    group_id: str | None,
) -> None:
    if not db_manager:
        return
    try:
        db_manager.touch_chat_session(
            session_id,
            title=title,
            user_id=user_id,
            group_id=group_id,
        )
    except Exception as exc:
        logger.debug("Chat session update failed", exc_info=exc)


def _assert_session_access(
    session_obj: ChatSessionModel,
    token_data: TokenData,
) -> None:
    if session_obj.user_id and session_obj.user_id != token_data.user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if (
        session_obj.group_id
        and token_data.role.lower() != "admin"
        and str(session_obj.group_id) not in token_data.group_roles
    ):
        raise HTTPException(status_code=403, detail="Forbidden")


def _log_llm_usage(
    *,
    session_id: str,
    model_name: str,
    user_id: str | None,
    group_id: str | None,
) -> None:
    if not db_manager:
        return
    entry_id = f"{session_id}-{uuid.uuid4()}"
    user_identifier = user_id or "anonymous"
    try:
        db_manager.log_llm_usage(
            log_id=entry_id,
            user_id=user_identifier,
            model_name=model_name,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            group_id=group_id,
        )
    except Exception as exc:
        logger.debug("LLM usage logging failed", exc_info=exc)


def _extract_tool_info(chunk) -> dict | None:
    """从响应块中提取工具调用信息"""
    if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
        tool_call = chunk.tool_calls[0]
        return {
            "type": "tool_call",
            "name": tool_call.get("name", "unknown"),
            "args": tool_call.get("args", {})
        }
    return None


def _is_tool_message(chunk) -> bool:
    """检查是否是工具消息"""
    return isinstance(chunk, ToolMessage) or (
        hasattr(chunk, 'type') and chunk.type == 'tool'
    )


async def chat_stream(request: ChatRequest, group_id: str | None = None):
    """流式聊天响应"""
    rag_system = get_rag_system()
    _, model_used, _ = resolve_runtime_selection(
        request.model or "auto",
        request.message,
        group_id=group_id,
    )
    
    try:
        retrieved_docs = rag_system.vector_store.search(
            request.message, k=DEFAULT_SEARCH_K, group_id=group_id
        )
        sources = []
        for doc in retrieved_docs:
            sources.append({
                "content": doc.page_content[:200],
                "filename": doc.metadata.get("filename", "unknown")
            })
        
        for chunk in rag_system.query_with_stream(
            query=request.message,
            use_rag=True,
            model=request.model or "auto",
            k=DEFAULT_SEARCH_K,
            group_id=group_id,
        ):
            yield f"data: {json.dumps({'content': chunk})}\n\n"
        
        yield f"data: {json.dumps({'sources': sources, 'model_used': model_used, 'done': True})}\n\n"
        
    except (KeyError, ValueError) as e:
        logger.error(f"流式聊天参数错误: {str(e)}")
        yield f"data: {json.dumps({'error': '参数错误，请检查输入', 'done': True})}\n\n"
    except Exception as e:
        logger.error(f"流式聊天错误: {str(e)}", exc_info=True)
        yield f"data: {json.dumps({'error': '服务器内部错误，请稍后重试', 'done': True})}\n\n"


async def chat_stream_with_agent(
    request: ChatRequest,
    session_id: str,
    group_id: str | None = None,
):
    """使用 Agent 的流式聊天响应（支持工具调用）"""
    agent = get_agent_instance()
    config = {
        "configurable": {
            "thread_id": session_id,
            "model": request.model or "auto",
            "group_id": group_id,
        }
    }
    
    current_tool = None
    
    try:
        for chunk, metadata in agent.stream(
            {"messages": [("user", request.message)]},
            config,
            stream_mode="messages"
        ):
            # 检查工具调用开始
            tool_info = _extract_tool_info(chunk)
            if tool_info:
                current_tool = tool_info["name"]
                yield f"data: {json.dumps({'tool_call': tool_info})}\n\n"
                continue
            
            # 检查工具消息（工具执行结果）
            if _is_tool_message(chunk):
                if current_tool:
                    yield f"data: {json.dumps({'tool_result': {'name': current_tool, 'status': 'completed'}})}\n\n"
                    current_tool = None
                continue
            
            # 处理普通内容
            if hasattr(chunk, 'content') and chunk.content:
                content = ""
                if isinstance(chunk.content, str):
                    content = chunk.content
                elif isinstance(chunk.content, list):
                    for item in chunk.content:
                        if isinstance(item, dict) and item.get('text'):
                            content += item['text']
                
                if content:
                    yield f"data: {json.dumps({'content': content})}\n\n"
        
        model_used = (
            config["configurable"].get("resolved_model_used")
            or request.model
            or "auto"
        )
        yield f"data: {json.dumps({'model_used': model_used, 'done': True})}\n\n"
        
    except LangChainException as e:
        logger.error(f"Agent 执行失败: {str(e)}", exc_info=True)
        yield f"data: {json.dumps({'error': 'Agent 执行失败，请稍后重试', 'done': True})}\n\n"
    except (KeyError, ValueError) as e:
        logger.error(f"Agent 流式响应参数错误: {str(e)}")
        yield f"data: {json.dumps({'error': '参数错误，请检查输入', 'done': True})}\n\n"
    except Exception as e:
        logger.error(f"Agent 流式响应错误: {str(e)}", exc_info=True)
        yield f"data: {json.dumps({'error': '服务器内部错误，请稍后重试', 'done': True})}\n\n"


async def chat(
    request: ChatRequest,
    group_id: str | None = None,
    token_data: TokenData | None = None,
) -> ChatResponse | StreamingResponse:
    """处理聊天请求"""
    try:
        # 为每个请求生成唯一的 session_id，避免不同用户对话混淆
        session_id = request.session_id or str(uuid.uuid4())
        user_id = token_data.user_id if token_data else None
        _touch_chat_session(
            session_id=session_id,
            title=_derive_session_title(request.message),
            user_id=user_id,
            group_id=group_id,
        )

        if request.use_rag:
            _, model_used, _ = resolve_runtime_selection(
                request.model or "auto",
                request.message,
                group_id=group_id,
            )

            if request.stream:
                _log_llm_usage(
                    session_id=session_id,
                    model_name=model_used,
                    user_id=user_id,
                    group_id=group_id,
                )
                return StreamingResponse(
                    chat_stream(request, group_id=group_id),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    }
                )
            else:
                rag_system = get_rag_system()
                result = rag_system.query(
                    query=request.message,
                    use_rag=True,
                    model=request.model or "auto",
                    k=DEFAULT_SEARCH_K,
                    group_id=group_id,
                )

                if result.get("success"):
                    model_used = result.get("model_used") or model_used
                    _log_llm_usage(
                        session_id=session_id,
                        model_name=model_used,
                        user_id=user_id,
                        group_id=group_id,
                    )
                    return ChatResponse(
                        success=True,
                        message=result.get("answer", ""),
                        session_id=session_id,
                        model_used=model_used,
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
            # 使用 Agent 模式
            if request.stream:
                _log_llm_usage(
                    session_id=session_id,
                    model_name=request.model or "auto",
                    user_id=user_id,
                    group_id=group_id,
                )
                return StreamingResponse(
                    chat_stream_with_agent(request, session_id, group_id=group_id),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    }
                )
            else:
                agent = get_agent_instance()
                config = {
                    "configurable": {
                        "thread_id": session_id,
                        "model": request.model or "auto",
                        "group_id": group_id,
                    }
                }
                
                full_response = ""
                
                for chunk, _ in agent.stream(
                    {"messages": [("user", request.message)]},
                    config,
                    stream_mode="messages"
                ):
                    # 跳过工具消息
                    if _is_tool_message(chunk):
                        continue
                    
                    # 跳过工具调用（不包含内容）
                    if _extract_tool_info(chunk):
                        continue
                    
                    if hasattr(chunk, 'content') and chunk.content:
                        if isinstance(chunk.content, str):
                            full_response += chunk.content
                        elif isinstance(chunk.content, list):
                            for item in chunk.content:
                                if isinstance(item, dict) and item.get('text'):
                                    full_response += item['text']
                
                model_used = (
                    config["configurable"].get("resolved_model_used")
                    or request.model
                    or "auto"
                )
                _log_llm_usage(
                    session_id=session_id,
                    model_name=model_used,
                    user_id=user_id,
                    group_id=group_id,
                )
                
                return ChatResponse(
                    success=True,
                    message=full_response,
                    session_id=session_id,
                    model_used=model_used,
                    sources=[]
                )
        
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"聊天参数错误: {str(e)}")
        return ChatResponse(
            success=False,
            message="",
            error="参数错误，请检查输入"
        )
    except Exception as e:
        logger.error(f"聊天处理错误: {str(e)}", exc_info=True)
        return ChatResponse(
            success=False,
            message="",
            error="服务器内部错误，请稍后重试"
        )


@chat_router.post("/chat", response_model=None)
async def chat_route(
    request: ChatRequest,
    token_data: TokenData | None = Depends(_get_optional_token_data),
):
    """FastAPI router wrapper that retains the existing chat implementation."""
    group_id = _resolve_group_id(
        token_data,
        request.group_id,
        require_explicit_if_multiple=True,
    )
    return await chat(
        request,
        group_id=group_id,
        token_data=token_data,
    )


@chat_router.get("/chat/sessions", response_model=ChatSessionListResponse)
def list_chat_sessions(
    group_id: str | None = None,
    token_data: TokenData = Depends(_require_token_data),
) -> ChatSessionListResponse:
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database unavailable")
    resolved_group_id = _resolve_group_id(token_data, group_id)
    sessions = db_manager.list_chat_sessions(
        user_id=token_data.user_id,
        group_id=resolved_group_id,
    )
    items = [ChatSessionItem(**session.to_dict()) for session in sessions]
    return ChatSessionListResponse(success=True, sessions=items)


@chat_router.patch("/chat/sessions/{session_id}", response_model=ChatSessionItem)
def rename_chat_session(
    session_id: str,
    payload: ChatSessionRenameRequest,
    token_data: TokenData = Depends(_require_token_data),
) -> ChatSessionItem:
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database unavailable")
    session_obj = db_manager.get_chat_session(session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    _assert_session_access(session_obj, token_data)
    updated = db_manager.update_chat_session_title(
        session_id,
        payload.title.strip() or "New Chat",
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Session not found")
    return ChatSessionItem(**updated.to_dict())


@chat_router.delete("/chat/sessions/{session_id}", response_model=ChatSessionDeleteResponse)
def delete_chat_session(
    session_id: str,
    token_data: TokenData = Depends(_require_token_data),
) -> ChatSessionDeleteResponse:
    if not db_manager:
        raise HTTPException(status_code=500, detail="Database unavailable")
    session_obj = db_manager.get_chat_session(session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    _assert_session_access(session_obj, token_data)
    if not db_manager.delete_chat_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return ChatSessionDeleteResponse(success=True, session_id=session_id)
