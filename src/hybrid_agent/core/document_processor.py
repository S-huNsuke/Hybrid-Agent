import os
import logging
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
    
    def process_file(self, file_path: str, filename: str) -> list[Document]:
        docs = self.load_document(file_path)
        
        for doc in docs:
            doc.metadata["filename"] = filename
        
        parent_docs = self.split_documents(docs, mode="parent")
        
        for doc in parent_docs:
            doc.metadata["filename"] = filename
        
        return parent_docs
    
    def process_content(self, content: str, metadata: dict | None = None) -> list[Document]:
        if metadata is None:
            metadata = {}
        
        doc = Document(page_content=content, metadata=metadata)
        return self.split_documents([doc], mode="parent")


document_processor = DocumentProcessor()
