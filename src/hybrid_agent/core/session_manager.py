"""会话管理模块：TTLCache 会话存储 + 超长对话摘要压缩

功能：
    - 基于 TTLCache 管理会话状态（2小时 TTL，最多 1000 个会话）
    - 对话轮次超过 MAX_ROUNDS 时触发摘要压缩，避免上下文窗口溢出
    - 摘要持久化至 SQLite conversation_summaries 表
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from cachetools import TTLCache

from hybrid_agent.core.config import (
    MAX_ROUNDS_BEFORE_SUMMARY,
    SESSION_TTL,
    SESSION_MAX_SIZE,
    SUMMARY_MAX_TOKENS,
    QUERY_UNDERSTANDING_TIMEOUT,
)

logger = logging.getLogger(__name__)

_SUMMARY_PROMPT = """以下是一段对话记录，请用 200 字以内总结对话的核心内容、用户的主要需求和已解决的问题。

对话记录：
{messages}

摘要（直接输出，不要加前缀）："""


class SessionManager:
    """会话状态管理器

    线程安全，基于 TTLCache 存储会话元数据。
    超过 MAX_ROUNDS_BEFORE_SUMMARY 轮时触发异步摘要压缩。

    Attributes:
        _cache: TTLCache[thread_id, dict]，存储会话元数据
        _lock: 线程锁
    """

    def __init__(
        self,
        max_size: int = SESSION_MAX_SIZE,
        ttl: int = SESSION_TTL,
    ) -> None:
        self._cache: TTLCache = TTLCache(maxsize=max_size, ttl=ttl)
        self._lock = threading.Lock()

    def get_or_create(self, thread_id: str) -> dict[str, Any]:
        """获取或创建会话状态

        Args:
            thread_id: 会话线程 ID

        Returns:
            会话状态字典（含 message_count, summary, retrieval_paths_used 等）
        """
        # 先在锁内快速检查缓存命中
        with self._lock:
            if thread_id in self._cache:
                return self._cache[thread_id]

        # 缓存未命中：在锁外执行 DB I/O（避免长时间持锁阻塞其他线程）
        summary = self._load_summary(thread_id)

        # 二次检查：防止并发时重复初始化
        with self._lock:
            if thread_id not in self._cache:
                self._cache[thread_id] = {
                    "thread_id": thread_id,
                    "message_count": 0,
                    "summary": summary,
                    "retrieval_paths_used": [],
                    "last_intent": None,
                }
            return self._cache[thread_id]

    def increment_message_count(self, thread_id: str) -> int:
        """增加消息计数，超阈值时触发摘要压缩

        Args:
            thread_id: 会话 ID

        Returns:
            更新后的消息计数
        """
        session = self.get_or_create(thread_id)
        with self._lock:
            session["message_count"] += 1
            count = session["message_count"]

        if count > 0 and count % MAX_ROUNDS_BEFORE_SUMMARY == 0:
            logger.info(f"会话 {thread_id[:8]} 达到 {count} 轮，触发摘要压缩")
            # 注：摘要压缩需要外部调用 compress_session，由 AgenticRAGGraph 驱动

        return count

    def update_summary(self, thread_id: str, summary: str, message_count: int) -> None:
        """更新会话摘要（内存 + 持久化）

        Args:
            thread_id: 会话 ID
            summary: 摘要文本
            message_count: 当前消息数
        """
        session = self.get_or_create(thread_id)
        with self._lock:
            session["summary"] = summary
            session["message_count"] = message_count

        # 持久化到 SQLite
        try:
            from hybrid_agent.core.database import db_manager
            db_manager.upsert_conversation_summary(thread_id, summary, message_count)
        except Exception as e:
            logger.warning(f"摘要持久化失败: {e}")

    def get_summary(self, thread_id: str) -> str:
        """获取会话摘要

        Args:
            thread_id: 会话 ID

        Returns:
            摘要文本，无摘要返回空字符串
        """
        session = self.get_or_create(thread_id)
        return session.get("summary") or ""

    def should_compress(self, thread_id: str) -> bool:
        """判断是否需要摘要压缩

        Args:
            thread_id: 会话 ID

        Returns:
            True 表示需要压缩
        """
        session = self.get_or_create(thread_id)
        count = session.get("message_count", 0)
        return count > 0 and count % MAX_ROUNDS_BEFORE_SUMMARY == 0

    def compress_session(
        self,
        thread_id: str,
        messages: list[dict],
    ) -> str:
        """执行会话摘要压缩

        Args:
            thread_id: 会话 ID
            messages: 消息列表（每项含 role/content 字段）

        Returns:
            生成的摘要文本
        """
        if not messages:
            return ""

        # 格式化对话记录
        formatted_messages = "\n".join(
            f"{m.get('role', 'user')}: {str(m.get('content', ''))[:200]}"
            for m in messages[-40:]  # 最近 40 条
        )

        # 如果有旧摘要，一并纳入
        existing_summary = self.get_summary(thread_id)
        if existing_summary:
            formatted_messages = f"[之前对话摘要]: {existing_summary}\n\n{formatted_messages}"

        summary = self._generate_summary(formatted_messages)
        if summary:
            count = len(messages)
            self.update_summary(thread_id, summary, count)
            logger.info(f"会话 {thread_id[:8]} 摘要压缩完成（{count} 条消息）")
        return summary or ""

    def _generate_summary(self, formatted_messages: str) -> str | None:
        """调用 qwen-turbo 生成摘要

        Args:
            formatted_messages: 格式化后的对话记录

        Returns:
            摘要文本，失败返回 None
        """
        try:
            from hybrid_agent.core.config import settings
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage

            api_key = settings.qwen_api_key or settings.tongyi_embedding_api_key
            base_url = settings.qwen_base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"

            if not api_key:
                return None

            llm = ChatOpenAI(
                api_key=api_key,
                base_url=base_url,
                model_name="qwen-turbo",
                temperature=0.1,
                max_tokens=SUMMARY_MAX_TOKENS,
                request_timeout=QUERY_UNDERSTANDING_TIMEOUT,
            )

            prompt = _SUMMARY_PROMPT.format(messages=formatted_messages)
            resp = llm.invoke([HumanMessage(content=prompt)])
            return resp.content.strip() if resp and resp.content else None
        except Exception as e:
            logger.warning(f"摘要生成失败: {e}")
            return None

    def _load_summary(self, thread_id: str) -> str:
        """从 SQLite 加载持久化摘要

        Args:
            thread_id: 会话 ID

        Returns:
            摘要文本，无记录返回空字符串
        """
        try:
            from hybrid_agent.core.database import db_manager
            record = db_manager.get_conversation_summary(thread_id)
            return record.summary if record else ""
        except Exception:
            return ""

    def delete_session(self, thread_id: str) -> None:
        """删除会话状态（内存 + 持久化）

        Args:
            thread_id: 会话 ID
        """
        with self._lock:
            self._cache.pop(thread_id, None)
        try:
            from hybrid_agent.core.database import db_manager
            db_manager.delete_conversation_summary(thread_id)
        except Exception:
            pass


# ── 全局单例 ──────────────────────────────────────────────────────────────

_session_manager: SessionManager | None = None
_session_manager_lock = threading.Lock()


def get_session_manager() -> SessionManager:
    """获取 SessionManager 单例（线程安全）

    Returns:
        SessionManager 实例
    """
    global _session_manager
    if _session_manager is None:
        with _session_manager_lock:
            if _session_manager is None:
                _session_manager = SessionManager()
    return _session_manager
