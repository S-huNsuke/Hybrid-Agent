"""聊天路由"""

import json
import logging
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessageChunk, ToolMessage
from langchain_core.exceptions import LangChainException

from hybrid_agent.api.schemas import ChatRequest, ChatResponse
from hybrid_agent.core.rag_system import get_rag_system
from hybrid_agent.llm.model_selector import resolve_model_type
from hybrid_agent.agent.builder import get_agent_instance

logger = logging.getLogger(__name__)


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


async def chat_stream(request: ChatRequest):
    """流式聊天响应"""
    rag_system = get_rag_system()
    
    model_type = resolve_model_type(request.model or "auto")
    
    try:
        retrieved_docs = rag_system.vector_store.search(request.message, k=4)
        sources = []
        for doc in retrieved_docs:
            sources.append({
                "content": doc.page_content[:200],
                "filename": doc.metadata.get("filename", "unknown")
            })
        
        for chunk in rag_system.query_with_stream(
            query=request.message,
            use_rag=True,
            model=model_type,
            k=4
        ):
            yield f"data: {json.dumps({'content': chunk})}\n\n"
        
        yield f"data: {json.dumps({'sources': sources, 'done': True})}\n\n"
        
    except (KeyError, ValueError) as e:
        logger.error(f"流式聊天参数错误: {str(e)}")
        yield f"data: {json.dumps({'error': f'参数错误: {str(e)}'})}\n\n"
    except Exception as e:
        logger.error(f"流式聊天错误: {str(e)}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


async def chat_stream_with_agent(request: ChatRequest, session_id: str):
    """使用 Agent 的流式聊天响应（支持工具调用）"""
    agent = get_agent_instance()
    config = {
        "configurable": {
            "thread_id": session_id,
            "model": request.model or "auto"
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
        
        yield f"data: {json.dumps({'done': True})}\n\n"
        
    except LangChainException as e:
        logger.error(f"Agent 执行失败: {str(e)}")
        yield f"data: {json.dumps({'error': f'Agent 执行失败: {str(e)}'})}\n\n"
    except (KeyError, ValueError) as e:
        logger.error(f"Agent 流式响应参数错误: {str(e)}")
        yield f"data: {json.dumps({'error': f'参数错误: {str(e)}'})}\n\n"
    except Exception as e:
        logger.error(f"Agent 流式响应错误: {str(e)}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


async def chat(request: ChatRequest) -> ChatResponse | StreamingResponse:
    """处理聊天请求"""
    try:
        session_id = request.session_id or "default"
        
        if request.use_rag:
            model_type = resolve_model_type(request.model or "auto")
            
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
                rag_system = get_rag_system()
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
            # 使用 Agent 模式
            if request.stream:
                return StreamingResponse(
                    chat_stream_with_agent(request, session_id),
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
                        "model": request.model
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
                
                model_display_names = {
                    "auto": "Qwen3/DeepSeek (自动选择)",
                    "qwen3-omni": "Qwen3",
                    "deepseek-v3": "DeepSeek"
                }
                model_used = model_display_names.get(request.model, request.model or "Auto")
                
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
            error=f"参数错误: {str(e)}"
        )
    except Exception as e:
        logger.error(f"聊天处理错误: {str(e)}")
        return ChatResponse(
            success=False,
            message="",
            error=str(e)
        )
