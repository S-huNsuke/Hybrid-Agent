from contextlib import contextmanager
from sqlalchemy import create_engine, Column, Integer, String, DateTime
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


db_manager: DatabaseManager = DatabaseManager()
