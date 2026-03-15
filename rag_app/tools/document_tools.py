import os
import logging
from typing import Optional
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from rag_app.core.rag_system import get_rag_system

logger = logging.getLogger(__name__)


class DocumentEditInput(BaseModel):
    """文档编辑工具的输入参数"""
    document_id: str = Field(description="要编辑的文档ID")
    new_content: str = Field(description="新的文档内容")


class SearchDocumentsInput(BaseModel):
    """搜索文档工具的输入参数"""
    query: str = Field(description="搜索关键词或问题")
    top_k: int = Field(default=3, description="返回结果数量，默认3")

def document_edit_func(document_id: str, new_content: str) -> str:
    try:
        logger.info(f"开始编辑文档: {document_id}")
        rag_system = get_rag_system()
        
        docs = rag_system.list_documents()
        file_path = None
        filename = None
        for doc in docs:
            if doc.get("id") == document_id:
                file_path = doc.get("file_path")
                filename = doc.get("filename")
                break
        
        if not file_path or not filename:
            logger.warning(f"文档不存在: {document_id}")
            return f"❌ 文档 {document_id} 不存在"
        
        if not os.path.exists(file_path):
            logger.warning(f"文档文件不存在: {file_path}")
            return f"❌ 文档文件不存在: {file_path}"
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        try:
            rag_system.delete_document(document_id)
            with open(file_path, "rb") as f:
                rag_system.add_document(f.read(), filename)
            reindex_msg = "并重新索引"
            logger.info(f"文档编辑成功: {filename}")
        except (OSError, IOError, Exception) as e:
            reindex_msg = f"（重新索引失败: {str(e)}，请手动重新上传）"
            logger.error(f"重新索引失败: {str(e)}")
        
        return f"✅ 文档已更新 {reindex_msg}: {filename}"
    except Exception as e:
        logger.error(f"编辑失败: {str(e)}")
        return f"❌ 编辑失败: {str(e)}"

def document_delete_func(document_id: str) -> str:
    try:
        logger.info(f"开始删除文档: {document_id}")
        rag_system = get_rag_system()
        result = rag_system.delete_document(document_id)
        if result.get("success"):
            logger.info(f"文档删除成功: {document_id}")
            return f"✅ {result.get('message', '文档已删除')}"
        else:
            logger.warning(f"文档删除失败: {document_id}, 原因: {result.get('error', '未知错误')}")
            return f"❌ 删除失败: {result.get('error', '未知错误')}"
    except Exception as e:
        logger.error(f"删除失败: {str(e)}")
        return f"❌ 删除失败: {str(e)}"

def list_documents_func(query: Optional[str] = None) -> str:
    try:
        logger.info("获取文档列表")
        rag_system = get_rag_system()
        docs = rag_system.list_documents()
        
        if not docs:
            return "📚 知识库为空，还没有任何文档。"
        
        result = "📚 知识库文档列表:\n\n"
        for i, doc in enumerate(docs, 1):
            filename = doc.get("filename", "未命名")
            doc_id = doc.get("id", "")
            result += f"{i}. {filename} (ID: {doc_id[:8]}...)\n"
        
        logger.info(f"返回文档列表，共 {len(docs)} 个文档")
        return result
    except Exception as e:
        logger.error(f"获取文档列表失败: {str(e)}")
        return f"获取文档列表失败: {str(e)}"

def search_documents_func(query: str, top_k: int = 3) -> str:
    try:
        logger.info(f"搜索文档: query={query}, top_k={top_k}")
        rag_system = get_rag_system()
        results = rag_system.search_documents(query, k=top_k)
        
        if not results:
            logger.info(f"未找到相关文档: {query}")
            return f"未找到与 '{query}' 相关的文档内容。"
        
        result = f"🔍 搜索结果 (查询: {query}):\n\n"
        for i, r in enumerate(results, 1):
            content = r.get("content", "")[:200]
            filename = r.get("metadata", {}).get("filename", "未知文件")
            result += f"--- 结果 {i} (来自: {filename}) ---\n{content}...\n\n"
        
        logger.info(f"搜索完成，返回 {len(results)} 个结果")
        return result
    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        return f"搜索失败: {str(e)}"

document_edit = StructuredTool.from_function(
    func=document_edit_func,
    name="document_edit",
    description="编辑知识库中的文档内容。需要提供文档ID和新的文档内容。",
    args_schema=DocumentEditInput,
)

document_delete = StructuredTool.from_function(
    func=document_delete_func,
    name="document_delete",
    description="删除知识库中的文档。需要提供要删除的文档ID。",
)

list_documents = StructuredTool.from_function(
    func=list_documents_func,
    name="list_documents",
    description="列出知识库中的所有文档。无需输入参数。",
)

search_documents = StructuredTool.from_function(
    func=search_documents_func,
    name="search_documents",
    description="在知识库中搜索与问题相关的文档内容。需要提供搜索关键词，可选返回结果数量。",
    args_schema=SearchDocumentsInput,
)

__all__ = [
    "document_edit",
    "document_delete", 
    "list_documents",
    "search_documents",
]
