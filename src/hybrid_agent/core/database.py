from __future__ import annotations

from contextlib import contextmanager
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float
from sqlalchemy.orm import sessionmaker, declarative_base, make_transient, scoped_session
from datetime import datetime
from typing import Generator
import logging

from hybrid_agent.core.config import get_project_root

logger = logging.getLogger(__name__)

Base = declarative_base()


class DocumentModel(Base):
    __tablename__ = "documents"
    
    id = Column(String(36), primary_key=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512))
    file_size = Column(Integer)
    file_type = Column(String(50))
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
            "status": self.status,
            "chunk_count": self.chunk_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class BM25ChunkModel(Base):
    """BM25 稀疏检索的文本块存储"""
    __tablename__ = "bm25_chunks"

    id = Column(String(36), primary_key=True)    # chunk_id，格式：{doc_id}_{i}
    doc_id = Column(String(36), nullable=False, index=True)
    content = Column(Text, nullable=False)
    tokens = Column(Text)                         # JSON 编码的 bigram token 列表


class ConversationSummaryModel(Base):
    """会话摘要，用于长对话压缩"""
    __tablename__ = "conversation_summaries"

    thread_id = Column(String(255), primary_key=True)
    summary = Column(Text, nullable=False)
    message_count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class DatabaseManager:
    def __init__(self) -> None:
        self.engine = None
        self.SessionLocal = None
        self._init_database()
    
    def _init_database(self):
        db_path = get_project_root() / "documents.db"
        connection_string = f"sqlite:///{db_path}"
        
        try:
            # SQLite 使用 check_same_thread=False 允许多线程访问
            # 使用 scoped_session 确保线程安全的 session 管理
            self.engine = create_engine(
                connection_string,
                echo=False,
                connect_args={"check_same_thread": False}
            )
            Base.metadata.create_all(self.engine)
            # 使用 scoped_session 实现线程局部 session
            session_factory = sessionmaker(bind=self.engine)
            self.SessionLocal = scoped_session(session_factory)
            logger.info("数据库连接成功 (SQLite)")
        except Exception as e:
            logger.error(f"数据库连接失败：{e}")
            raise
    
    @contextmanager
    def _get_session(self) -> Generator:
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


db_manager: DatabaseManager = DatabaseManager()
