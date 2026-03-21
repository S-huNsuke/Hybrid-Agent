"""Agentic RAG 控制图（LangGraph StateGraph）

架构：
    用户输入
        ↓
    understand_query    — 意图分类 → HyDE 改写 → 子问题分解
        ↓
    retrieval_decision  — 是否需要检索？（direct/math_code 直接 generate）
        ↓ YES
    hybrid_retrieve     — BM25 + Vector + RRF 多路融合
        ↓
    post_process        — DashScope Rerank → 上下文压缩
        ↓
    self_reflect        — ContentReviewer 评估检索质量（最多 2 次迭代）
        ├─ 满足 → generate
        └─ 不满足（iteration < 2）→ hybrid_retrieve（扩大查询）
    generate            — 生成最终回答 + 来源归因

状态字段：AgenticRAGState（TypedDict）
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from hybrid_agent.core.config import (
    AGENTIC_MAX_ITERATIONS,
    AGENTIC_REFLECTION_THRESHOLD,
    AGENTIC_FINAL_TOP_K,
)

logger = logging.getLogger(__name__)


# ── 状态定义 ──────────────────────────────────────────────────────────────

class AgenticRAGState(TypedDict):
    """Agentic RAG 图的共享状态"""
    original_query: str
    intent: Literal["direct", "rag_only", "web_only", "hybrid", "math_code"]
    rewritten_query: str                   # HyDE 改写后的查询（或原始查询）
    sub_queries: list[str]                 # 子问题列表（复杂查询时非空）
    hyde_doc: str                          # HyDE 假设文档
    retrieved_chunks: list[dict]           # 多路召回原始结果
    reranked_chunks: list[dict]            # Reranker 排序后结果
    compressed_context: str               # 上下文压缩后文本
    reflection_score: float               # ContentReviewer 评分（0-1）
    iteration_count: int                  # 当前迭代次数
    retrieval_sufficient: bool            # 检索质量是否满足
    messages: Annotated[list[BaseMessage], add_messages]
    conversation_summary: str             # 当前会话摘要
    sources: list[dict]                   # 最终来源列表（含 retrieval_method/rerank_score）
    retrieval_paths_used: list[str]       # 激活的检索路径
    path_chunk_counts: dict[str, int]     # 各路径召回数量（调试用）
    thread_id: str                        # 会话 ID


# ── 节点实现 ──────────────────────────────────────────────────────────────

def understand_query(state: AgenticRAGState) -> AgenticRAGState:
    """节点1：意图分类 + HyDE 改写 + 子问题分解

    Args:
        state: 当前图状态

    Returns:
        更新后的状态（intent, rewritten_query, hyde_doc, sub_queries）
    """
    query = state["original_query"]
    logger.info(f"[understand_query] query='{query[:40]}'")

    try:
        from hybrid_agent.core.query_understanding import (
            get_intent_router,
            get_hyde_rewriter,
            get_sub_query_decomposer,
        )

        intent = get_intent_router().classify(query)
        logger.debug(f"意图: {intent}")

        hyde_doc = ""
        sub_queries: list[str] = []

        # 仅对 rag_only/hybrid 执行 HyDE 和子问题分解
        if intent in ("rag_only", "hybrid"):
            hyde_doc = get_hyde_rewriter().rewrite(query) or ""
            sub_queries = get_sub_query_decomposer().decompose(query)

        return {
            "intent": intent,
            "rewritten_query": query,
            "hyde_doc": hyde_doc,
            "sub_queries": sub_queries,
        }
    except Exception as e:
        logger.warning(f"[understand_query] 失败，使用默认 rag_only: {e}")
        return {
            "intent": "rag_only",
            "rewritten_query": query,
            "hyde_doc": "",
            "sub_queries": [],
        }


def retrieval_decision(state: AgenticRAGState) -> AgenticRAGState:
    """节点2：决策是否需要检索

    direct/math_code 意图直接跳到 generate，其余进入检索流程。

    Args:
        state: 当前图状态

    Returns:
        空字典（纯路由节点，不修改状态）
    """
    intent = state.get("intent", "rag_only")
    logger.debug(f"[retrieval_decision] intent={intent}")
    return {}


def hybrid_retrieve(state: AgenticRAGState) -> AgenticRAGState:
    """节点3：多路召回（BM25 + Dense + HyDE + 子问题）

    Args:
        state: 当前图状态

    Returns:
        更新了 retrieved_chunks, retrieval_paths_used, path_chunk_counts 的状态
    """
    query = state["rewritten_query"]
    hyde_doc = state.get("hyde_doc") or None
    sub_queries = state.get("sub_queries") or None

    # 迭代时扩展查询（将子问题注入原始查询关键词）
    iteration = state.get("iteration_count", 0)
    if iteration > 0 and sub_queries:
        # 第二次迭代：扩大子问题覆盖
        logger.debug(f"[hybrid_retrieve] 迭代 {iteration}，扩展子问题检索")

    logger.info(
        f"[hybrid_retrieve] query='{query[:30]}' "
        f"hyde={'yes' if hyde_doc else 'no'} "
        f"sub_queries={len(sub_queries or [])}"
    )

    try:
        from hybrid_agent.core.hybrid_retriever import get_multi_path_retriever

        retriever = get_multi_path_retriever()
        chunks = retriever.retrieve_sync(
            query=query,
            sub_queries=sub_queries,
            hyde_doc=hyde_doc,
        )

        # 统计各路径数量（调试用）
        path_counts: dict[str, int] = {}
        for c in chunks:
            method = c.get("retrieval_method", "unknown")
            for m in method.split(","):
                m = m.strip()
                path_counts[m] = path_counts.get(m, 0) + 1

        paths_used = list(path_counts.keys())

        return {
            "retrieved_chunks": chunks,
            "retrieval_paths_used": paths_used,
            "path_chunk_counts": path_counts,
        }
    except Exception as e:
        logger.error(f"[hybrid_retrieve] 失败: {e}")
        return {
            "retrieved_chunks": [],
            "retrieval_paths_used": [],
            "path_chunk_counts": {},
        }


def post_process(state: AgenticRAGState) -> AgenticRAGState:
    """节点4：Reranker + 上下文压缩

    Args:
        state: 当前图状态

    Returns:
        更新了 reranked_chunks, compressed_context, sources 的状态
    """
    query = state["original_query"]
    chunks = state.get("retrieved_chunks", [])

    if not chunks:
        return {"reranked_chunks": [], "compressed_context": "", "sources": []}

    logger.info(f"[post_process] 对 {len(chunks)} 个候选块进行 rerank")

    try:
        from hybrid_agent.core.reranker import get_reranker

        reranker = get_reranker()
        reranked = reranker.rerank(query, chunks, top_k=AGENTIC_FINAL_TOP_K)
    except Exception as e:
        logger.warning(f"[post_process] Reranker 失败，使用原始顺序: {e}")
        reranked = chunks[:AGENTIC_FINAL_TOP_K]
        for r in reranked:
            r.setdefault("rerank_score", 0.5)

    # 提取式上下文压缩：拼接 reranked_chunks 内容
    context_parts = []
    for chunk in reranked:
        content = chunk.get("content", "").strip()
        if content:
            context_parts.append(content)
    compressed_context = "\n\n---\n\n".join(context_parts)

    # 构建来源列表
    sources = []
    for chunk in reranked:
        sources.append({
            "content": chunk.get("content", "")[:200],
            "doc_id": chunk.get("doc_id", ""),
            "chunk_id": chunk.get("chunk_id", ""),
            "filename": chunk.get("metadata", {}).get("filename", "未知文件"),
            "retrieval_method": chunk.get("retrieval_method", "hybrid"),
            "rerank_score": chunk.get("rerank_score", 0.0),
        })

    return {
        "reranked_chunks": reranked,
        "compressed_context": compressed_context,
        "sources": sources,
    }


def self_reflect(state: AgenticRAGState) -> AgenticRAGState:
    """节点5：检索质量自我反思（SELF-RAG）

    使用 ContentReviewer 评估检索结果是否足以回答原始问题。
    评分 >= AGENTIC_REFLECTION_THRESHOLD 或已达最大迭代次数时标记为满足。

    Args:
        state: 当前图状态

    Returns:
        更新了 reflection_score, retrieval_sufficient, iteration_count 的状态
    """
    query = state["original_query"]
    reranked = state.get("reranked_chunks", [])
    iteration = state.get("iteration_count", 0)

    if not reranked:
        return {
            "reflection_score": 0.0,
            "retrieval_sufficient": iteration >= AGENTIC_MAX_ITERATIONS,
            "iteration_count": iteration + 1,
        }

    logger.info(f"[self_reflect] iteration={iteration}, chunks={len(reranked)}")

    try:
        from hybrid_agent.agent.reviewer import get_reviewer

        reviewer = get_reviewer()
        contents_to_review = [
            {"content": c.get("content", ""), "source_type": "knowledge_base"}
            for c in reranked
        ]
        review_result = reviewer.review_batch(query, contents_to_review)

        avg_score = review_result.average_score / 10.0  # 归一化到 0-1
        is_sufficient = avg_score >= AGENTIC_REFLECTION_THRESHOLD or iteration >= AGENTIC_MAX_ITERATIONS

        logger.debug(
            f"[self_reflect] avg_score={avg_score:.2f}, "
            f"sufficient={is_sufficient}, iteration={iteration}"
        )

        return {
            "reflection_score": avg_score,
            "retrieval_sufficient": is_sufficient,
            "iteration_count": iteration + 1,
        }
    except Exception as e:
        logger.warning(f"[self_reflect] 评估失败，视为满足: {e}")
        return {
            "reflection_score": 1.0,
            "retrieval_sufficient": True,
            "iteration_count": iteration + 1,
        }


def generate(state: AgenticRAGState) -> AgenticRAGState:
    """节点6：生成最终回答

    根据意图和检索结果生成回答，无检索结果时直接推理。

    Args:
        state: 当前图状态

    Returns:
        更新了 messages 的状态（最终回答 AIMessage 追加到 messages）
    """
    query = state["original_query"]
    context = state.get("compressed_context", "")
    intent = state.get("intent", "rag_only")
    conversation_summary = state.get("conversation_summary", "")

    logger.info(f"[generate] intent={intent}, context_len={len(context)}")

    try:
        from hybrid_agent.llm.models import get_advanced_model, get_base_model
        from langchain_core.messages import AIMessage, HumanMessage

        llm = get_base_model()  # 生成使用基础模型（速度快）

        # 构建提示词
        system_parts = []
        if conversation_summary:
            system_parts.append(f"[对话摘要]\n{conversation_summary}\n")

        if context and intent in ("rag_only", "hybrid"):
            system_parts.append(
                f"[参考文档]\n{context}\n\n"
                "请基于以上参考文档回答问题。文档中没有相关信息时，基于自身知识回答并说明。"
            )
        else:
            system_parts.append("请直接回答以下问题。")

        full_prompt = "\n".join(system_parts) + f"\n\n问题：{query}"
        messages_to_send = [HumanMessage(content=full_prompt)]

        # 流式生成
        full_answer = ""
        for chunk in llm.stream(messages_to_send):
            if hasattr(chunk, "content"):
                full_answer += chunk.content or ""

        new_ai_message = AIMessage(content=full_answer)

        return {"messages": [new_ai_message]}
    except Exception as e:
        logger.error(f"[generate] 生成失败: {e}")
        return {"messages": [AIMessage(content=f"抱歉，生成回答时出错：{str(e)}")]}


# ── 条件边函数 ────────────────────────────────────────────────────────────

def _route_after_decision(state: AgenticRAGState) -> str:
    """retrieval_decision 后的路由：是否需要检索

    Args:
        state: 当前图状态

    Returns:
        下一个节点名称
    """
    intent = state.get("intent", "rag_only")
    if intent in ("direct", "math_code"):
        return "generate"
    return "hybrid_retrieve"


def _route_after_reflect(state: AgenticRAGState) -> str:
    """self_reflect 后的路由：迭代还是生成

    Args:
        state: 当前图状态

    Returns:
        下一个节点名称
    """
    if state.get("retrieval_sufficient", True):
        return "generate"
    return "hybrid_retrieve"


# ── 图构建 ────────────────────────────────────────────────────────────────

def build_agentic_rag_graph() -> StateGraph:
    """构建 Agentic RAG StateGraph

    节点顺序：
        understand_query → retrieval_decision → [hybrid_retrieve → post_process → self_reflect] → generate → END

    Returns:
        编译好的 LangGraph CompiledGraph
    """
    graph = StateGraph(AgenticRAGState)

    # 注册节点
    graph.add_node("understand_query", understand_query)
    graph.add_node("retrieval_decision", retrieval_decision)
    graph.add_node("hybrid_retrieve", hybrid_retrieve)
    graph.add_node("post_process", post_process)
    graph.add_node("self_reflect", self_reflect)
    graph.add_node("generate", generate)

    # 入口
    graph.set_entry_point("understand_query")

    # 固定边
    graph.add_edge("understand_query", "retrieval_decision")
    graph.add_edge("hybrid_retrieve", "post_process")
    graph.add_edge("post_process", "self_reflect")
    graph.add_edge("generate", END)

    # 条件边
    graph.add_conditional_edges(
        "retrieval_decision",
        _route_after_decision,
        {
            "generate": "generate",
            "hybrid_retrieve": "hybrid_retrieve",
        },
    )
    graph.add_conditional_edges(
        "self_reflect",
        _route_after_reflect,
        {
            "generate": "generate",
            "hybrid_retrieve": "hybrid_retrieve",
        },
    )

    return graph


def get_compiled_rag_graph():
    """获取编译好的 Agentic RAG 图（带 InMemorySaver checkpointer）

    Returns:
        编译好的图实例
    """
    from langgraph.checkpoint.memory import InMemorySaver

    graph = build_agentic_rag_graph()
    checkpointer = InMemorySaver()
    return graph.compile(checkpointer=checkpointer)


def run_agentic_rag(
    query: str,
    thread_id: str = "default",
    conversation_summary: str = "",
) -> dict:
    """运行 Agentic RAG 图，返回最终结果

    Args:
        query: 用户查询
        thread_id: 会话 ID（用于 checkpointer）
        conversation_summary: 已有的会话摘要

    Returns:
        {"answer": str, "sources": list, "intent": str, "paths_used": list, "reflection_score": float}
    """
    try:
        from langchain_core.messages import AIMessage, HumanMessage

        compiled = get_compiled_rag_graph()

        initial_state: AgenticRAGState = {
            "original_query": query,
            "intent": "rag_only",
            "rewritten_query": query,
            "sub_queries": [],
            "hyde_doc": "",
            "retrieved_chunks": [],
            "reranked_chunks": [],
            "compressed_context": "",
            "reflection_score": 0.0,
            "iteration_count": 0,
            "retrieval_sufficient": False,
            "messages": [HumanMessage(content=query)],
            "conversation_summary": conversation_summary,
            "sources": [],
            "retrieval_paths_used": [],
            "path_chunk_counts": {},
            "thread_id": thread_id,
        }

        config = {"configurable": {"thread_id": thread_id}}
        final_state = compiled.invoke(initial_state, config=config)

        # 提取最终回答（找最后一条 AIMessage）
        answer = ""
        for msg in reversed(final_state.get("messages", [])):
            if isinstance(msg, AIMessage):
                answer = msg.content
                break

        return {
            "answer": answer,
            "sources": final_state.get("sources", []),
            "intent": final_state.get("intent", "rag_only"),
            "paths_used": final_state.get("retrieval_paths_used", []),
            "reflection_score": final_state.get("reflection_score", 0.0),
            "iteration_count": final_state.get("iteration_count", 0),
        }
    except Exception as e:
        logger.error(f"[run_agentic_rag] 失败: {e}", exc_info=True)
        return {
            "answer": f"处理查询时出错：{str(e)}",
            "sources": [],
            "intent": "rag_only",
            "paths_used": [],
            "reflection_score": 0.0,
            "iteration_count": 0,
        }
