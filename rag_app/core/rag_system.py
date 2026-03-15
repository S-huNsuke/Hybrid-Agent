import logging
import os
import re
import uuid
from typing import Any, Dict, Generator, List, Optional

from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate

from rag_app.core.database import DocumentModel, db_manager
from rag_app.core.document_processor import document_processor
from rag_app.core.vector import get_vector_store
from rag_app.llm.models import advanced_model, base_model

logger = logging.getLogger(__name__)


def _sanitize_filename(filename: str) -> str:
    filename = os.path.basename(filename)
    filename = re.sub(r'[^\w\s\-\.]', '', filename)
    filename = filename[:255]
    return filename if filename else "unnamed"


class RAGSystem:
    def __init__(self):
        self.vector_store = get_vector_store()
        self._uploads_dir = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
        os.makedirs(self._uploads_dir, exist_ok=True)
    
    def _get_uploads_dir(self) -> str:
        return self._uploads_dir
    
    def add_document(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        doc_id = str(uuid.uuid4())
        logger.info(f"开始添加文档: {filename}, doc_id: {doc_id}")
        
        safe_filename = _sanitize_filename(filename)
        file_path = os.path.join(self._get_uploads_dir(), f"{doc_id}_{safe_filename}")
        
        try:
            with open(file_path, "wb") as f:
                f.write(file_content)
        except IOError as e:
            logger.error(f"保存文件失败: {filename}, 错误: {str(e)}")
            return {"success": False, "error": f"保存文件失败: {str(e)}"}
        
        try:
            documents = document_processor.process_file(file_path, filename)
            logger.info(f"文档处理完成，生成 {len(documents)} 个文本块")
            
            ids = [f"{doc_id}_{i}" for i in range(len(documents))]
            self.vector_store.add_documents(documents, ids)
            logger.info(f"向量存储完成，共 {len(ids)} 个向量")
            
            doc_model = DocumentModel(
                id=doc_id,
                filename=filename,
                file_path=file_path,
                file_size=len(file_content),
                file_type=os.path.splitext(filename)[1],
                status="ready",
                chunk_count=len(documents)
            )
            db_manager.add_document(doc_model)
            
            logger.info(f"文档添加成功: {filename}")
            return {
                "success": True,
                "doc_id": doc_id,
                "filename": filename,
                "chunks": len(documents),
                "message": f"成功添加文档 '{filename}'，共 {len(documents)} 个文本块"
            }
        except ValueError as e:
            logger.error(f"文档处理失败: {filename}, 错误: {str(e)}")
            if os.path.exists(file_path):
                os.remove(file_path)
            return {"success": False, "error": f"文档处理失败: {str(e)}"}
        except IOError as e:
            logger.error(f"向量存储失败: {filename}, 错误: {str(e)}")
            return {"success": False, "error": f"向量存储失败: {str(e)}"}
        except Exception as e:
            logger.error(f"添加文档失败: {filename}, 错误: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def delete_document(self, doc_id: str) -> Dict[str, Any]:
        try:
            logger.info(f"开始删除文档: {doc_id}")
            doc_model = db_manager.get_document(doc_id)
            if not doc_model:
                logger.warning(f"文档不存在: {doc_id}")
                return {"success": False, "error": "文档不存在"}

            if doc_model.file_path and os.path.exists(doc_model.file_path):
                os.remove(doc_model.file_path)
                logger.info(f"已删除物理文件: {doc_model.file_path}")

            deleted_count = self.vector_store.delete_by_doc_id_prefix(doc_id)
            logger.info(f"已删除 {deleted_count} 个向量")

            db_manager.delete_document(doc_id)
            logger.info(f"文档删除成功: {doc_model.filename}")

            return {
                "success": True,
                "message": f"成功删除文档 '{doc_model.filename}'，清理了 {deleted_count} 个向量"
            }
        except FileNotFoundError as e:
            logger.error(f"文件不存在: {doc_id}, 错误: {str(e)}")
            return {"success": False, "error": f"文件不存在: {str(e)}"}
        except PermissionError as e:
            logger.error(f"权限不足，无法删除: {doc_id}, 错误: {str(e)}")
            return {"success": False, "error": f"权限不足: {str(e)}"}
        except Exception as e:
            logger.error(f"删除文档失败: {doc_id}, 错误: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def list_documents(self) -> List[Dict[str, Any]]:
        docs = db_manager.get_all_documents()
        return [doc.to_dict() for doc in docs]
    
    def search_documents(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        results = self.vector_store.search_with_score(query, k=k)
        
        sources = []
        for doc, score in results:
            sources.append({
                "content": doc.page_content[:500],
                "metadata": doc.metadata,
                "score": float(score)
            })
        return sources
    
    def query(
        self,
        query: str,
        use_rag: bool = True,
        model: str = "advanced",
        k: int = 4
    ) -> Dict[str, Any]:
        if not use_rag:
            return self._direct_query(query, model)
        
        try:
            retrieved_docs = self.vector_store.search(query, k=k)
            
            if not retrieved_docs:
                return {
                    "success": True,
                    "answer": "知识库为空，请先上传文档。",
                    "sources": []
                }
            
            context = "\n\n".join([doc.page_content for doc in retrieved_docs])
            
            prompt_template = """基于以下参考文档回答用户的问题。如果文档中没有相关信息，请基于你的知识回答。

参考文档：
{context}

用户问题：{question}

回答："""

            prompt = PromptTemplate(
                template=prompt_template,
                input_variables=["context", "question"]
            )
            
            llm = advanced_model if model == "advanced" else base_model
            
            from langchain_core.messages import HumanMessage
            formatted_prompt = prompt.format(context=context, question=query)
            messages = [HumanMessage(content=formatted_prompt)]
            
            full_answer = ""
            thinking_content = ""
            
            for chunk in llm.stream(messages):
                if hasattr(chunk, 'content'):
                    full_answer += chunk.content
                
                if hasattr(chunk, 'additional_kwargs'):
                    kwargs = chunk.additional_kwargs
                    if isinstance(kwargs, dict):
                        reasoning = kwargs.get('reasoning_content', '')
                        if reasoning:
                            thinking_content += reasoning
            
            sources = []
            for doc in retrieved_docs:
                sources.append({
                    "content": doc.page_content[:200],
                    "filename": doc.metadata.get("filename", "unknown"),
                    "source": doc.metadata.get("source", "")
                })
            
            return {
                "success": True,
                "answer": full_answer,
                "sources": sources,
                "context_chunks": len(retrieved_docs),
                "thinking_process": thinking_content
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "answer": f"处理查询时出错: {str(e)}",
                "sources": []
            }
    
    def _direct_query(self, query: str, model: str = "advanced") -> Dict[str, Any]:
        try:
            llm = advanced_model if model == "advanced" else base_model
            
            from langchain_core.messages import HumanMessage
            messages = [HumanMessage(content=query)]
            
            full_answer = ""
            thinking_content = ""
            
            for chunk in llm.stream(messages):
                if hasattr(chunk, 'content'):
                    full_answer += chunk.content
                
                if hasattr(chunk, 'additional_kwargs'):
                    kwargs = chunk.additional_kwargs
                    if isinstance(kwargs, dict):
                        reasoning = kwargs.get('reasoning_content', '')
                        if reasoning:
                            thinking_content += reasoning
            
            return {
                "success": True,
                "answer": full_answer,
                "sources": [],
                "mode": "direct",
                "thinking_process": thinking_content
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "answer": f"处理查询时出错: {str(e)}",
                "sources": []
            }
    
    def query_with_stream(
        self,
        query: str,
        use_rag: bool = True,
        model: str = "advanced",
        k: int = 4
    ) -> Generator[str, None, None]:
        if not use_rag:
            llm = advanced_model if model == "advanced" else base_model
            from langchain_core.messages import HumanMessage
            messages = [HumanMessage(content=query)]
            
            for chunk in llm.stream(messages):
                if hasattr(chunk, 'content'):
                    yield chunk.content
            return
        
        try:
            retrieved_docs = self.vector_store.search(query, k=k)
            
            if not retrieved_docs:
                yield "知识库为空，请先上传文档。"
                return
            
            context = "\n\n".join([doc.page_content for doc in retrieved_docs])
            
            prompt_template = """基于以下参考文档回答用户的问题。如果文档中没有相关信息，请基于你的知识回答。

参考文档：
{context}

用户问题：{question}

回答："""

            prompt = PromptTemplate(
                template=prompt_template,
                input_variables=["context", "question"]
            )
            
            llm = advanced_model if model == "advanced" else base_model
            
            from langchain_core.messages import HumanMessage
            formatted_prompt = prompt.format(context=context, question=query)
            messages = [HumanMessage(content=formatted_prompt)]
            
            for chunk in llm.stream(messages):
                if hasattr(chunk, 'content'):
                    yield chunk.content
        except Exception as e:
            yield f"处理查询时出错: {str(e)}"
    
    def get_stats(self) -> Dict[str, Any]:
        count = self.vector_store.get_collection_count()
        docs = db_manager.get_all_documents()
        
        return {
            "total_documents": len(docs),
            "total_chunks": count,
            "documents": [doc.to_dict() for doc in docs]
        }


_rag_system: Optional[RAGSystem] = None


def get_rag_system() -> RAGSystem:
    global _rag_system
    if _rag_system is None:
        _rag_system = RAGSystem()
    return _rag_system
