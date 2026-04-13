from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator, Sequence, Tuple

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.orm import declarative_base, make_transient, scoped_session, sessionmaker

from hybrid_agent.core.config import DATABASE_URL, get_project_root

logger = logging.getLogger(__name__)

Base: Any = declarative_base()


def _resolve_database_url() -> Tuple[str, bool]:
    """Return the DATABASE_URL plus whether this is the on-disk sqlite fallback."""
    if DATABASE_URL:
        return DATABASE_URL, DATABASE_URL.startswith("sqlite:///")

    project_root = get_project_root()
    sqlite_path = project_root / "documents.db"
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{sqlite_path}", True


class DocumentModel(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512))
    file_size = Column(Integer)
    file_type = Column(String(50))
    group_id = Column(String(36), ForeignKey("groups.id"), nullable=True, index=True)
    status = Column(String(20), default="ready")
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def to_dict(self):
        return {
            "id": self.id,
            "filename": self.filename,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "group_id": self.group_id,
            "status": self.status,
            "chunk_count": self.chunk_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class UploadTaskModel(Base):
    __tablename__ = "upload_tasks"

    task_id = Column(String(36), primary_key=True)
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=True, index=True)
    filename = Column(String(255), nullable=False)
    group_id = Column(String(36), ForeignKey("groups.id"), nullable=True, index=True)
    status = Column(String(20), default="queued", nullable=False)
    progress = Column(Integer, default=0, nullable=False)
    message = Column(Text)
    error = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "document_id": self.document_id,
            "filename": self.filename,
            "group_id": self.group_id,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class BM25ChunkModel(Base):
    """BM25 稀疏检索的文本块存储"""
    __tablename__ = "bm25_chunks"

    id = Column(String(36), primary_key=True)    # chunk_id，格式：{doc_id}_{i}
    doc_id = Column(String(36), nullable=False, index=True)
    group_id = Column(String(36), ForeignKey("groups.id"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    tokens = Column(Text)                         # JSON 编码的 bigram token 列表


class ConversationSummaryModel(Base):
    """会话摘要，用于长对话压缩"""
    __tablename__ = "conversation_summaries"

    thread_id = Column(String(255), primary_key=True)
    summary = Column(Text, nullable=False)
    message_count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ChatSessionModel(Base):
    """聊天会话元数据"""
    __tablename__ = "chat_sessions"

    id = Column(String(36), primary_key=True)
    title = Column(String(255), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    group_id = Column(String(36), ForeignKey("groups.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    last_message_at = Column(DateTime, default=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "user_id": self.user_id,
            "group_id": self.group_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
        }


class UserModel(Base):
    """系统用户与认证凭据（预留）"""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    username = Column(String(150), nullable=False, unique=True, index=True)
    email = Column(String(255), unique=True)
    hashed_password = Column(String(512))
    role = Column(String(50), default="member", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class GroupModel(Base):
    """租户/分组表"""
    __tablename__ = "groups"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class UserGroupModel(Base):
    """用户-组多对多关系"""
    __tablename__ = "user_groups"

    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True)
    group_id = Column(String(36), ForeignKey("groups.id"), primary_key=True)
    role = Column(String(50), default="member")
    assigned_at = Column(DateTime, default=datetime.now)


class LLMUsageLogModel(Base):
    """LLM 调用成本/审计记录"""
    __tablename__ = "llm_usage_logs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), index=True)
    group_id = Column(String(36), ForeignKey("groups.id"), nullable=True, index=True)
    model_name = Column(String(255), nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)


class ProviderModel(Base):
    """LLM Provider 配置（密钥需加密存储）"""
    __tablename__ = "providers"

    id = Column(String(36), primary_key=True)
    group_id = Column(String(36), ForeignKey("groups.id"), nullable=True, index=True)
    provider_type = Column(String(50), nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    base_url = Column(String(512))
    api_key_ciphertext = Column(Text, nullable=False)
    api_key_hint = Column(String(32))
    models = Column(Text)
    default_model = Column(String(255))
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    updated_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "group_id": self.group_id,
            "provider_type": self.provider_type,
            "display_name": self.display_name,
            "base_url": self.base_url,
            "api_key_hint": self.api_key_hint,
            "models": self.models,
            "default_model": self.default_model,
            "is_active": self.is_active,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class DatabaseManager:
    def __init__(self) -> None:
        self.engine: Any = None
        self.SessionLocal: Any = None
        self._init_database()
    
    def _init_database(self) -> None:
        connection_string, is_sqlite = _resolve_database_url()
        try:
            kwargs: dict[str, Any] = {"echo": False}
            if is_sqlite:
                kwargs["connect_args"] = {"check_same_thread": False}
            self.engine = create_engine(connection_string, **kwargs)
            Base.metadata.create_all(self.engine)
            if is_sqlite:
                self._apply_sqlite_compat_migrations()
            session_factory = sessionmaker(bind=self.engine)
            self.SessionLocal = scoped_session(session_factory)
            if is_sqlite:
                logger.info("数据库连接成功 (SQLite documents.db fallback)")
            else:
                logger.info("数据库连接成功 (DATABASE_URL)")
        except Exception as e:
            logger.error(f"数据库连接失败：{e}")
            raise

    def _apply_sqlite_compat_migrations(self) -> None:
        """为历史 SQLite 数据库补齐新增列，避免旧库启动失败。"""
        compatibility_columns = {
            "users": [
                ("role", "ALTER TABLE users ADD COLUMN role VARCHAR(50) DEFAULT 'member' NOT NULL"),
                ("is_active", "ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1 NOT NULL"),
            ],
            "documents": [
                ("group_id", "ALTER TABLE documents ADD COLUMN group_id VARCHAR(36)"),
            ],
            "bm25_chunks": [
                ("group_id", "ALTER TABLE bm25_chunks ADD COLUMN group_id VARCHAR(36)"),
            ],
            "llm_usage_logs": [
                ("group_id", "ALTER TABLE llm_usage_logs ADD COLUMN group_id VARCHAR(36)"),
            ],
        }

        with self.engine.begin() as connection:
            for table_name, columns in compatibility_columns.items():
                existing = {
                    row[1]
                    for row in connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
                }
                for column_name, ddl in columns:
                    if column_name not in existing:
                        connection.execute(text(ddl))
    
    @contextmanager
    def _get_session(self) -> Generator[Any, None, None]:
        """获取 session 的上下文管理器"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            # 使用 remove() 清理 scoped_session 的线程局部状态
            self.SessionLocal.remove()
    
    def add_document(self, doc: DocumentModel) -> DocumentModel:
        with self._get_session() as session:
            session.add(doc)
            session.flush()  # 获取生成的 ID
            session.refresh(doc)
            make_transient(doc)
            return doc

    def get_document(self, doc_id: str) -> DocumentModel | None:
        with self._get_session() as session:
            doc = session.query(DocumentModel).filter(DocumentModel.id == doc_id).first()
            if doc:
                make_transient(doc)
            return doc
    
    def get_all_documents(self) -> list[DocumentModel]:
        with self._get_session() as session:
            docs = session.query(DocumentModel).all()
            for doc in docs:
                make_transient(doc)
            return docs

    def list_documents_by_group(self, group_id: str) -> list[DocumentModel]:
        """按 group_id 列出文档"""
        with self._get_session() as session:
            docs = (
                session.query(DocumentModel)
                .filter(DocumentModel.group_id == group_id)
                .all()
            )
            for doc in docs:
                make_transient(doc)
            return docs

    def list_documents_without_group(self) -> list[DocumentModel]:
        """列出未绑定 group 的共享文档"""
        with self._get_session() as session:
            docs = (
                session.query(DocumentModel)
                .filter(DocumentModel.group_id.is_(None))
                .all()
            )
            for doc in docs:
                make_transient(doc)
            return docs

    def list_documents_by_group_ids(self, group_ids: Sequence[str]) -> list[DocumentModel]:
        """按多个 group_id 查询文档"""
        if not group_ids:
            return []
        with self._get_session() as session:
            docs = (
                session.query(DocumentModel)
                .filter(DocumentModel.group_id.in_(group_ids))
                .all()
            )
            for doc in docs:
                make_transient(doc)
            return docs

    def delete_document(self, doc_id: str) -> bool:
        with self._get_session() as session:
            doc = session.query(DocumentModel).filter(DocumentModel.id == doc_id).first()
            if doc:
                session.delete(doc)
                return True
            return False
    
    def update_document_status(self, doc_id: str, status: str) -> bool:
        with self._get_session() as session:
            doc = session.query(DocumentModel).filter(DocumentModel.id == doc_id).first()
            if doc:
                doc.status = status
                return True
            return False

    # ── BM25 chunk 相关方法 ──────────────────────────────────────────────

    def add_bm25_chunks(self, chunks: list[BM25ChunkModel]) -> None:
        """批量写入 BM25 文本块（已存在则覆盖更新）"""
        if not chunks:
            return
        with self._get_session() as session:
            for chunk in chunks:
                session.merge(chunk)

    def get_bm25_chunks(self, doc_id: str | None = None) -> list[BM25ChunkModel]:
        """获取 BM25 文本块，可按 doc_id 过滤"""
        with self._get_session() as session:
            q = session.query(BM25ChunkModel)
            if doc_id:
                q = q.filter(BM25ChunkModel.doc_id == doc_id)
            chunks = q.all()
            for c in chunks:
                make_transient(c)
            return chunks

    def get_all_bm25_chunks(self) -> list[BM25ChunkModel]:
        """获取全部 BM25 文本块（供 BM25 索引构建使用）"""
        return self.get_bm25_chunks()

    def delete_bm25_chunks(self, doc_id: str) -> int:
        """删除指定文档的全部 BM25 文本块，返回删除数量"""
        with self._get_session() as session:
            count = (
                session.query(BM25ChunkModel)
                .filter(BM25ChunkModel.doc_id == doc_id)
                .delete()
            )
            return count

    def list_bm25_chunks_for_group(self, group_id: str) -> list[BM25ChunkModel]:
        """按 group_id 获取 BM25 块"""
        with self._get_session() as session:
            chunks = (
                session.query(BM25ChunkModel)
                .filter(BM25ChunkModel.group_id == group_id)
                .all()
            )
            for chunk in chunks:
                make_transient(chunk)
            return chunks

    def list_bm25_chunks_for_groups(self, group_ids: Sequence[str]) -> list[BM25ChunkModel]:
        """按多个 group_id 获取 BM25 块"""
        if not group_ids:
            return []
        with self._get_session() as session:
            chunks = (
                session.query(BM25ChunkModel)
                .filter(BM25ChunkModel.group_id.in_(group_ids))
                .all()
            )
            for chunk in chunks:
                make_transient(chunk)
            return chunks

    # ── 会话摘要相关方法 ─────────────────────────────────────────────────

    def upsert_conversation_summary(self, thread_id: str, summary: str, message_count: int) -> None:
        """更新或插入会话摘要"""
        with self._get_session() as session:
            existing = session.query(ConversationSummaryModel).filter(
                ConversationSummaryModel.thread_id == thread_id
            ).first()
            if existing:
                existing.summary = summary
                existing.message_count = message_count
                existing.updated_at = datetime.now()
            else:
                session.add(ConversationSummaryModel(
                    thread_id=thread_id,
                    summary=summary,
                    message_count=message_count,
                ))

    def get_conversation_summary(self, thread_id: str) -> ConversationSummaryModel | None:
        """获取会话摘要"""
        with self._get_session() as session:
            s = session.query(ConversationSummaryModel).filter(
                ConversationSummaryModel.thread_id == thread_id
            ).first()
            if s:
                make_transient(s)
            return s

    def delete_conversation_summary(self, thread_id: str) -> None:
        """删除会话摘要"""
        with self._get_session() as session:
            session.query(ConversationSummaryModel).filter(
                ConversationSummaryModel.thread_id == thread_id
            ).delete()

    # ── 聊天会话相关方法 ────────────────────────────────────────────────

    def create_chat_session(self, session_model: ChatSessionModel) -> ChatSessionModel:
        """创建会话元数据"""
        with self._get_session() as session:
            session.add(session_model)
            session.flush()
            session.refresh(session_model)
            make_transient(session_model)
            return session_model

    def get_chat_session(self, session_id: str) -> ChatSessionModel | None:
        """获取单个会话"""
        with self._get_session() as session:
            session_obj = (
                session.query(ChatSessionModel)
                .filter(ChatSessionModel.id == session_id)
                .first()
            )
            if session_obj:
                make_transient(session_obj)
            return session_obj

    def list_chat_sessions(
        self,
        *,
        user_id: str | None,
        group_id: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ChatSessionModel]:
        """列出会话列表，按最近消息时间倒序"""
        if not user_id:
            return []
        with self._get_session() as session:
            query = session.query(ChatSessionModel).filter(ChatSessionModel.user_id == user_id)
            if group_id is not None:
                query = query.filter(ChatSessionModel.group_id == group_id)
            query = query.order_by(ChatSessionModel.last_message_at.desc())
            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)
            sessions = query.all()
            for session_obj in sessions:
                make_transient(session_obj)
            return sessions

    def update_chat_session_title(self, session_id: str, title: str) -> ChatSessionModel | None:
        """重命名会话"""
        with self._get_session() as session:
            session_obj = (
                session.query(ChatSessionModel)
                .filter(ChatSessionModel.id == session_id)
                .first()
            )
            if not session_obj:
                return None
            session_obj.title = title
            session_obj.updated_at = datetime.now()
            session.flush()
            session.refresh(session_obj)
            make_transient(session_obj)
            return session_obj

    def touch_chat_session(
        self,
        session_id: str,
        *,
        title: str,
        user_id: str | None,
        group_id: str | None,
    ) -> ChatSessionModel:
        """创建或更新会话时间戳与元信息"""
        with self._get_session() as session:
            session_obj = (
                session.query(ChatSessionModel)
                .filter(ChatSessionModel.id == session_id)
                .first()
            )
            now = datetime.now()
            if session_obj:
                if title and session_obj.title in {"", "New Chat"}:
                    session_obj.title = title
                session_obj.last_message_at = now
                session_obj.updated_at = now
                if user_id and not session_obj.user_id:
                    session_obj.user_id = user_id
                if group_id and not session_obj.group_id:
                    session_obj.group_id = group_id
                session.flush()
                session.refresh(session_obj)
                make_transient(session_obj)
                return session_obj
            session_obj = ChatSessionModel(
                id=session_id,
                title=title or "New Chat",
                user_id=user_id,
                group_id=group_id,
                created_at=now,
                updated_at=now,
                last_message_at=now,
            )
            session.add(session_obj)
            session.flush()
            session.refresh(session_obj)
            make_transient(session_obj)
            return session_obj

    def delete_chat_session(self, session_id: str) -> bool:
        """删除会话"""
        with self._get_session() as session:
            session_obj = (
                session.query(ChatSessionModel)
                .filter(ChatSessionModel.id == session_id)
                .first()
            )
            if not session_obj:
                return False
            session.delete(session_obj)
            return True

    # ── 用户/组/成员关系辅助方法 ───────────────────────────────────────────

    def get_user(self, user_id: str) -> UserModel | None:
        """根据主键获取用户"""
        with self._get_session() as session:
            user = session.query(UserModel).filter(UserModel.id == user_id).first()
            if user:
                make_transient(user)
            return user

    def get_user_by_username(self, username: str) -> UserModel | None:
        """通过账号名查单个用户"""
        with self._get_session() as session:
            user = session.query(UserModel).filter(UserModel.username == username).first()
            if user:
                make_transient(user)
            return user

    def list_users(self, limit: int | None = None) -> list[UserModel]:
        """按创建顺序列出用户"""
        with self._get_session() as session:
            q = session.query(UserModel).order_by(UserModel.created_at.desc())
            if limit:
                q = q.limit(limit)
            users = q.all()
            for user in users:
                make_transient(user)
            return users

    def get_group(self, group_id: str) -> GroupModel | None:
        """单个组信息"""
        with self._get_session() as session:
            group = session.query(GroupModel).filter(GroupModel.id == group_id).first()
            if group:
                make_transient(group)
            return group

    def list_groups(self, limit: int | None = None) -> list[GroupModel]:
        """列出全部组"""
        with self._get_session() as session:
            q = session.query(GroupModel).order_by(GroupModel.created_at.desc())
            if limit:
                q = q.limit(limit)
            groups = q.all()
            for group in groups:
                make_transient(group)
            return groups

    def get_user_groups(self, user_id: str) -> list[UserGroupModel]:
        """获取某用户的组关系"""
        with self._get_session() as session:
            entries = (
                session.query(UserGroupModel)
                .filter(UserGroupModel.user_id == user_id)
                .all()
            )
            for entry in entries:
                make_transient(entry)
            return entries

    def get_group_members(self, group_id: str) -> list[UserGroupModel]:
        """获取某组的成员关系"""
        with self._get_session() as session:
            entries = (
                session.query(UserGroupModel)
                .filter(UserGroupModel.group_id == group_id)
                .all()
            )
            for entry in entries:
                make_transient(entry)
            return entries

    def get_user_group_entry(self, user_id: str, group_id: str) -> UserGroupModel | None:
        """查询用户在某组中的角色条目"""
        with self._get_session() as session:
            entry = (
                session.query(UserGroupModel)
                .filter(
                    UserGroupModel.user_id == user_id,
                    UserGroupModel.group_id == group_id,
                )
                .first()
            )
            if entry:
                make_transient(entry)
            return entry

    def create_upload_task(self, task: UploadTaskModel) -> UploadTaskModel:
        """Insert a new upload task record."""
        with self._get_session() as session:
            session.add(task)
            session.flush()
            session.refresh(task)
            make_transient(task)
            return task

    def get_upload_task(self, task_id: str) -> UploadTaskModel | None:
        """Return a task by its ID."""
        with self._get_session() as session:
            task = (
                session.query(UploadTaskModel)
                .filter(UploadTaskModel.task_id == task_id)
                .first()
            )
            if task:
                make_transient(task)
            return task

    def update_upload_task_status(
        self,
        task_id: str,
        *,
        status: str | None = None,
        progress: int | None = None,
        message: str | None = None,
        error: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        document_id: str | None = None,
    ) -> bool:
        """Update fields on an existing upload task."""
        with self._get_session() as session:
            task = (
                session.query(UploadTaskModel)
                .filter(UploadTaskModel.task_id == task_id)
                .first()
            )
            if not task:
                return False
            if status is not None:
                task.status = status
            if progress is not None:
                task.progress = max(0, min(100, progress))
            if message is not None:
                task.message = message
            if error is not None:
                task.error = error
            if started_at is not None:
                task.started_at = started_at
            if completed_at is not None:
                task.completed_at = completed_at
            if document_id is not None:
                task.document_id = document_id
            return True

    # ── LLM 使用日志相关方法 ───────────────────────────────────────────────

    def log_llm_usage(
        self,
        *,
        log_id: str,
        user_id: str,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int | None = None,
        group_id: str | None = None,
        created_at: datetime | None = None,
    ) -> LLMUsageLogModel:
        """Insert a usage log row, computing totals if needed."""
        total = total_tokens if total_tokens is not None else prompt_tokens + completion_tokens
        entry = LLMUsageLogModel(
            id=log_id,
            user_id=user_id,
            group_id=group_id,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            created_at=created_at or datetime.now(),
        )
        with self._get_session() as session:
            session.add(entry)
            session.flush()
            session.refresh(entry)
            make_transient(entry)
            return entry

    def get_llm_usage(self, log_id: str) -> LLMUsageLogModel | None:
        """Fetch a usage log by its identifier."""
        with self._get_session() as session:
            log = (
                session.query(LLMUsageLogModel)
                .filter(LLMUsageLogModel.id == log_id)
                .first()
            )
            if log:
                make_transient(log)
            return log

    def list_llm_usage(
        self,
        *,
        user_id: str | None = None,
        group_id: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[LLMUsageLogModel]:
        """List usage logs, optionally filtered by user/group/time.
        Results are returned in desc order by created_at.
        """
        with self._get_session() as session:
            query = session.query(LLMUsageLogModel)
            if user_id:
                query = query.filter(LLMUsageLogModel.user_id == user_id)
            if group_id:
                query = query.filter(LLMUsageLogModel.group_id == group_id)
            if since:
                query = query.filter(LLMUsageLogModel.created_at >= since)
            query = query.order_by(LLMUsageLogModel.created_at.desc())
            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)
            logs = query.all()
            for log in logs:
                make_transient(log)
            return logs

    # ── Provider 配置相关方法 ──────────────────────────────────────────────

    def list_providers(
        self,
        *,
        group_id: str | None = None,
        provider_type: str | None = None,
        include_inactive: bool = False,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[ProviderModel]:
        """列出 Provider 配置"""
        with self._get_session() as session:
            query = session.query(ProviderModel)
            if group_id is not None:
                query = query.filter(ProviderModel.group_id == group_id)
            if provider_type:
                query = query.filter(ProviderModel.provider_type == provider_type)
            if not include_inactive:
                query = query.filter(ProviderModel.is_active.is_(True))
            query = query.order_by(ProviderModel.created_at.desc())
            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)
            providers = query.all()
            for provider in providers:
                make_transient(provider)
            return providers

    def get_provider(self, provider_id: str) -> ProviderModel | None:
        """获取单个 Provider 配置"""
        with self._get_session() as session:
            provider = (
                session.query(ProviderModel)
                .filter(ProviderModel.id == provider_id)
                .first()
            )
            if provider:
                make_transient(provider)
            return provider

    def create_provider(self, provider: ProviderModel) -> ProviderModel:
        """创建 Provider 配置"""
        with self._get_session() as session:
            session.add(provider)
            session.flush()
            session.refresh(provider)
            make_transient(provider)
            return provider

    def update_provider(
        self,
        provider_id: str,
        *,
        group_id: str | None = None,
        provider_type: str | None = None,
        display_name: str | None = None,
        base_url: str | None = None,
        api_key_ciphertext: str | None = None,
        api_key_hint: str | None = None,
        models: str | None = None,
        default_model: str | None = None,
        is_active: bool | None = None,
        updated_by: str | None = None,
    ) -> ProviderModel | None:
        """更新 Provider 配置"""
        with self._get_session() as session:
            provider = (
                session.query(ProviderModel)
                .filter(ProviderModel.id == provider_id)
                .first()
            )
            if not provider:
                return None
            if group_id is not None:
                provider.group_id = group_id
            if provider_type is not None:
                provider.provider_type = provider_type
            if display_name is not None:
                provider.display_name = display_name
            if base_url is not None:
                provider.base_url = base_url
            if api_key_ciphertext is not None:
                provider.api_key_ciphertext = api_key_ciphertext
            if api_key_hint is not None:
                provider.api_key_hint = api_key_hint
            if models is not None:
                provider.models = models
            if default_model is not None:
                provider.default_model = default_model
            if is_active is not None:
                provider.is_active = is_active
            if updated_by is not None:
                provider.updated_by = updated_by
            provider.updated_at = datetime.now()
            session.flush()
            session.refresh(provider)
            make_transient(provider)
            return provider

    def delete_provider(self, provider_id: str) -> bool:
        """删除 Provider 配置"""
        with self._get_session() as session:
            provider = (
                session.query(ProviderModel)
                .filter(ProviderModel.id == provider_id)
                .first()
            )
            if not provider:
                return False
            session.delete(provider)
            return True


if os.getenv("HYBRID_AGENT_SKIP_DB_INIT") == "1":
    db_manager: Any = None
else:
    db_manager = DatabaseManager()
