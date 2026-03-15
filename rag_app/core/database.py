from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, make_transient
from datetime import datetime
from typing import Optional, List
import os
import logging

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
        db_path = os.path.join(os.path.dirname(__file__), "..", "..", "documents.db")
        connection_string = f"sqlite:///{db_path}"
        
        try:
            # SQLite 使用 NullPool 或静态池，不支持传统连接池参数
            # check_same_thread=False 允许多线程访问
            self.engine = create_engine(
                connection_string,
                echo=False,
                connect_args={"check_same_thread": False}
            )
            Base.metadata.create_all(self.engine)
            self.SessionLocal = sessionmaker(bind=self.engine)
            logger.info("数据库连接成功 (SQLite)")
        except Exception as e:
            logger.error(f"数据库连接失败：{e}")
            raise
    
    def add_document(self, doc: DocumentModel) -> DocumentModel:
        session = self.SessionLocal()
        try:
            session.add(doc)
            session.commit()
            session.refresh(doc)
            make_transient(doc)
            return doc
        finally:
            session.close()
    
    def get_document(self, doc_id: str) -> Optional[DocumentModel]:
        session = self.SessionLocal()
        try:
            doc = session.query(DocumentModel).filter(DocumentModel.id == doc_id).first()
            if doc:
                session.refresh(doc)
                make_transient(doc)
            return doc
        finally:
            session.close()
    
    def get_all_documents(self) -> List[DocumentModel]:
        session = self.SessionLocal()
        try:
            docs = session.query(DocumentModel).all()
            for doc in docs:
                make_transient(doc)
            return docs
        finally:
            session.close()
    
    def delete_document(self, doc_id: str) -> bool:
        session = self.SessionLocal()
        try:
            doc = session.query(DocumentModel).filter(DocumentModel.id == doc_id).first()
            if doc:
                session.delete(doc)
                session.commit()
                return True
            return False
        finally:
            session.close()
    
    def update_document_status(self, doc_id: str, status: str) -> bool:
        session = self.SessionLocal()
        try:
            doc = session.query(DocumentModel).filter(DocumentModel.id == doc_id).first()
            if doc:
                doc.status = status
                session.commit()
                return True
            return False
        finally:
            session.close()


db_manager: DatabaseManager = DatabaseManager()
