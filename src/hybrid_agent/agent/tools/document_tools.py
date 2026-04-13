import os
import logging

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from hybrid_agent.core.rag_system import get_rag_system
from hybrid_agent.core.config import default_reviewer_settings
from hybrid_agent.agent.reviewer import get_reviewer

logger = logging.getLogger(__name__)


class DocumentEditInput(BaseModel):
    """文档编辑工具的输入参数"""
    document_id: str = Field(description="要编辑的文档ID")
    new_content: str = Field(description="新的文档内容")


class SearchDocumentsInput(BaseModel):
    """搜索文档工具的输入参数"""
    query: str = Field(description="搜索关键词或问题")
    top_k: int = Field(default=3, description="返回结果数量，默认3")


class DocumentDeleteInput(BaseModel):
    """文档删除工具的输入参数"""
    document_id: str = Field(description="要删除的文档ID")


def document_edit_func(document_id: str, new_content: str) -> str:
    import tempfile
    import shutil
    
    temp_file_path = None
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
        
        # 使用临时文件确保原子性写入
        file_dir = os.path.dirname(file_path)
        temp_fd, temp_file_path = tempfile.mkstemp(dir=file_dir, suffix='.tmp')
        try:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            # 先删除旧向量数据（保留数据库记录和文件）
            deleted_count = rag_system.vector_store.delete_by_doc_id_prefix(document_id)
            logger.info(f"已删除 {deleted_count} 个旧向量")
            
            # 用同一 doc_id 重新添加文档
            with open(temp_file_path, "rb") as f:
                add_result = rag_system.add_document(f.read(), filename, doc_id=document_id)
            
            if not add_result.get("success"):
                # 添加失败，清理临时文件
                os.remove(temp_file_path)
                temp_file_path = None
                return f"❌ 重新索引失败: {add_result.get('error', '未知错误')}"
            
            # 替换原文件
            shutil.move(temp_file_path, file_path)
            temp_file_path = None
            
            logger.info(f"文档编辑成功: {filename}")
            return f"✅ 文档已更新并重新索引: {filename}"
        finally:
            # 清理临时文件（如果还存在）
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                
    except (FileNotFoundError, PermissionError, IOError) as e:
        logger.error(f"编辑失败: 文件操作错误 - {str(e)}")
        return "❌ 编辑失败: 文件访问错误"
    except ValueError as e:
        logger.error(f"编辑失败: 数据验证错误 - {str(e)}")
        return "❌ 编辑失败: 数据验证错误"
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
    except (FileNotFoundError, PermissionError, IOError) as e:
        logger.error(f"删除失败: 文件操作错误 - {str(e)}")
        return "❌ 删除失败: 文件访问错误"
    except Exception as e:
        logger.error(f"删除失败: {str(e)}")
        return f"❌ 删除失败: {str(e)}"


def list_documents_func(query: str | None = None) -> str:
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
    except (FileNotFoundError, PermissionError, IOError) as e:
        logger.error(f"获取文档列表失败: 文件操作错误 - {str(e)}")
        return "获取文档列表失败: 文件访问错误"
    except Exception as e:
        logger.error(f"获取文档列表失败: {str(e)}")
        return f"获取文档列表失败: {str(e)}"


def search_documents_func(query: str, top_k: int = 3, enable_review: bool = True) -> str:
    """搜索文档并审查结果
    
    Args:
        query: 搜索关键词
        top_k: 返回结果数量
        enable_review: 是否启用内容审查
    
    Returns:
        搜索结果摘要
    """
    try:
        logger.info(f"搜索文档: query={query}, top_k={top_k}")
        rag_system = get_rag_system()
        results = rag_system.search_documents(query, k=top_k)
        
        if not results:
            logger.info(f"未找到相关文档: {query}")
            return f"未找到与 '{query}' 相关的文档内容。"
        
        # 准备内容审查
        if enable_review and default_reviewer_settings.enabled:
            reviewer = get_reviewer()
            
            # 准备审查内容
            contents_to_review = []
            for r in results:
                contents_to_review.append({
                    "content": r.get("content", ""),
                    "source_type": "knowledge_base",
                    "metadata": r.get("metadata", {})
                })
            
            # 执行审查
            review_result = reviewer.review_batch(query, contents_to_review)
            
            # 使用审查后的内容构建输出
            output = f"🔍 搜索结果 (查询: {query}):\n\n"
            output += f"[审查摘要: {review_result.overall_assessment}]\n\n"
            
            filtered_results = review_result.filtered_contents
            if not filtered_results:
                output += "未找到高相关度的内容，以下是原始结果:\n\n"
                filtered_results = results
            
            for i, r in enumerate(filtered_results[:top_k], 1):
                content = r.get("content", "")[:200]
                metadata = r.get("metadata", {})
                filename = metadata.get("filename", "未知文件")
                score = r.get("review_score", None)
                key_info = r.get("key_info", [])

                score_str = f" [评分: {score}/10]" if score else ""
                key_info_str = f"\n关键信息: {', '.join(key_info)}" if key_info else ""

                output += f"--- 结果 {i} (来自: {filename}){score_str} ---\n{content}...{key_info_str}\n\n"
            
            logger.info(f"搜索完成，返回 {len(filtered_results)} 个结果 (审查后)")
            return output
        else:
            # 不审查，直接返回原始结果
            output = f"🔍 搜索结果 (查询: {query}):\n\n"
            for i, r in enumerate(results, 1):
                content = r.get("content", "")[:200]
                filename = r.get("metadata", {}).get("filename", "未知文件")
                output += f"--- 结果 {i} (来自: {filename}) ---\n{content}...\n\n"
            
            logger.info(f"搜索完成，返回 {len(results)} 个结果")
            return output
            
    except (FileNotFoundError, PermissionError, IOError) as e:
        logger.error(f"搜索失败: 文件操作错误 - {str(e)}")
        return "搜索失败: 文件访问错误"
    except ValueError as e:
        logger.error(f"搜索失败: 数据验证错误 - {str(e)}")
        return "搜索失败: 数据验证错误"
    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        return f"搜索失败: {str(e)}"


document_edit = StructuredTool.from_function(
    func=document_edit_func,
    name="document_edit",
    description="编辑知识库中的文档内容。需要提供文档ID和新的文档内容。如果启用了内容审查，会对新内容进行审查。",
    args_schema=DocumentEditInput,
)

document_delete = StructuredTool.from_function(
    func=document_delete_func,
    name="document_delete",
    description="删除知识库中的文档。需要提供要删除的文档ID。如果文档存在，将被永久删除。",
    args_schema=DocumentDeleteInput,
)

list_documents = StructuredTool.from_function(
    func=list_documents_func,
    name="list_documents",
    description="列出知识库中的所有文档。无需输入参数。",
)

search_documents = StructuredTool.from_function(
    func=search_documents_func,
    name="search_documents",
    description="在知识库中搜索与问题相关的文档内容，并自动审查内容相关性。需要提供搜索关键词，可选返回结果数量。返回的结果已经过相关性评分和过滤。",
    args_schema=SearchDocumentsInput,
)

__all__ = [
    "document_edit",
    "document_delete",
    "list_documents",
    "search_documents",
]
