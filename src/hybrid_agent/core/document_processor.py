from __future__ import annotations

import logging
import os
from typing import Any, Callable

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
    UnstructuredPowerPointLoader,
    UnstructuredExcelLoader,
)
from langchain_core.documents import Document

from hybrid_agent.core.config import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHILD_CHUNK_SIZE,
    DEFAULT_CHILD_CHUNK_OVERLAP
)
from hybrid_agent.core.database import db_manager

ProgressCallback = Callable[[str, dict[str, Any] | None], None]

logger = logging.getLogger(__name__)


class DocumentProcessor:
    def __init__(self) -> None:
        self.parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=DEFAULT_CHUNK_SIZE,
            chunk_overlap=DEFAULT_CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", "。", "？", "！", "?", "!", ""],
        )

        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=DEFAULT_CHILD_CHUNK_SIZE,
            chunk_overlap=DEFAULT_CHILD_CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", "。", "？", "！", "?", "!", ""],
        )

    def load_document(self, file_path: str) -> list[Document]:
        file_ext = os.path.splitext(file_path)[1].lower()
        loader: Any
        
        if file_ext == '.pdf':
            loader = PyPDFLoader(file_path)
        elif file_ext == '.docx':
            loader = Docx2txtLoader(file_path)
        elif file_ext == '.txt':
            loader = TextLoader(file_path, encoding='utf-8')
        elif file_ext == '.md':
            return self._create_text_document(file_path)
        elif file_ext == '.pptx':
            try:
                loader = UnstructuredPowerPointLoader(file_path)
            except Exception:
                return self._create_text_document(file_path)
        elif file_ext == '.xlsx':
            try:
                loader = UnstructuredExcelLoader(file_path)
            except Exception:
                return self._create_text_document(file_path)
        else:
            return self._create_text_document(file_path)
        
        try:
            return loader.load()
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return self._create_text_document(file_path)
    
    def _create_text_document(self, file_path: str) -> list[Document]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            content = f"File: {os.path.basename(file_path)}"
        
        return [Document(
            page_content=content,
            metadata={"source": file_path, "type": "text"}
        )]
    
    def split_documents(self, documents: list[Document], mode: str = "parent") -> list[Document]:
        if mode == "parent":
            splitter = self.parent_splitter
        else:
            splitter = self.child_splitter
        
        return splitter.split_documents(documents)
    
    def process_file(
        self,
        file_path: str,
        filename: str,
        doc_id: str | None = None,
        group_id: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> list[Document]:
        """加载并分割文档，可选同时构建 BM25 索引

        Args:
            file_path: 文件路径
            filename: 文件名（写入 metadata）
            doc_id: 若提供，则在处理后触发 BM25 索引写入

        Returns:
            父级文本块列表
        """
        docs = self.load_document(file_path)

        for doc in docs:
            doc.metadata["filename"] = filename

        parent_docs = self.split_documents(docs, mode="parent")

        for doc in parent_docs:
            doc.metadata["filename"] = filename
            if group_id:
                doc.metadata["group_id"] = group_id

        self._emit_progress(
            progress_callback,
            "parsed",
            {"doc_id": doc_id, "chunks": len(parent_docs), "group_id": group_id},
        )

        # 触发 BM25 索引（延迟导入避免循环依赖）
        if doc_id:
            try:
                from hybrid_agent.core.hybrid_retriever import get_bm25_retriever
                bm25 = get_bm25_retriever()
                chunk_ids = [f"{doc_id}_{i}" for i in range(len(parent_docs))]
                contents = [d.page_content for d in parent_docs]
                bm25.index_chunks(doc_id, contents, chunk_ids)
                self._emit_progress(
                    progress_callback,
                    "bm25_indexed",
                    {"doc_id": doc_id, "chunks": len(parent_docs)},
                )
                self._assign_group_to_chunks(doc_id, group_id)
            except Exception as e:
                logger.warning(f"BM25 索引写入失败（不影响向量索引）: {e}")

        return parent_docs
    
    def process_content(self, content: str, metadata: dict | None = None) -> list[Document]:
        if metadata is None:
            metadata = {}
        
        doc = Document(page_content=content, metadata=metadata)
        return self.split_documents([doc], mode="parent")

    def _assign_group_to_chunks(self, doc_id: str, group_id: str | None) -> None:
        """为 BM25 文本块补充 group_id，以便后续检索过滤"""
        if not group_id:
            return

        chunks = db_manager.get_bm25_chunks(doc_id)
        if not chunks:
            return

        for chunk in chunks:
            chunk.group_id = group_id
        db_manager.add_bm25_chunks(chunks)

    def _emit_progress(
        self,
        progress_callback: ProgressCallback | None,
        stage: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        if not progress_callback:
            return

        try:
            progress_callback(stage, {"stage": stage, **(data or {})})
        except Exception as exc:
            logger.warning("Progress callback failed during %s: %s", stage, exc)


document_processor = DocumentProcessor()
