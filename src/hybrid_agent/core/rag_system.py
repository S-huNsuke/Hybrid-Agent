from __future__ import annotations

import logging
import os
import re
import threading
import uuid
from typing import Any, Dict, Generator

from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate

from hybrid_agent.core.config import get_project_root
from hybrid_agent.core.database import DocumentModel, db_manager
from hybrid_agent.core.document_processor import (
    document_processor,
    ProgressCallback as DocumentProgressCallback,
)
from hybrid_agent.core.vector import get_vector_store
from hybrid_agent.llm.model_selector import resolve_runtime_selection

logger = logging.getLogger(__name__)

ProgressCallback = DocumentProgressCallback

# 安全配置常量
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.docx', '.md', '.csv', '.xlsx', '.xls', '.json'}


def _extract_chunk_text(content: str | list[str | dict[Any, Any]] | None) -> str:
    """将模型 chunk.content 统一转为字符串。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content

    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict):
            text = item.get("text", "")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def _sanitize_filename(filename: str) -> str:
    """清理文件名，防止路径遍历攻击"""
    filename = os.path.basename(filename)
    filename = re.sub(r'[^\w\s\-\.]', '', filename)
    filename = filename[:255]
    return filename if filename else "unnamed"


def _validate_file(file_content: bytes, filename: str) -> tuple[bool, str]:
    """验证文件是否安全
    
    Returns:
        tuple[bool, str]: (是否有效, 错误消息)
    """
    if not file_content:
        return False, "文件内容为空"
    
    if len(file_content) > MAX_FILE_SIZE:
        return False, f"文件大小超过限制 (最大 {MAX_FILE_SIZE // (1024*1024)}MB)"
    
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"不支持的文件类型: {ext}。支持的类型: {', '.join(ALLOWED_EXTENSIONS)}"
    
    return True, ""


def _is_safe_path(base_dir: str, target_path: str) -> bool:
    """验证目标路径是否在基础目录内，防止路径遍历攻击"""
    try:
        real_base = os.path.realpath(base_dir)
        real_target = os.path.realpath(target_path)
        return real_target.startswith(real_base + os.sep) or real_target == real_base
    except Exception:
        return False


class RAGSystem:
    def __init__(self):
        self.vector_store = get_vector_store()
        self._uploads_dir = str(get_project_root() / "uploads")
        os.makedirs(self._uploads_dir, exist_ok=True)

    def _emit_progress(
        self,
        progress_callback: ProgressCallback | None,
        stage: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        if not progress_callback:
            return

        payload = {"stage": stage, **(data or {})}
        try:
            progress_callback(stage, payload)
        except Exception as exc:
            logger.warning("Progress callback failed during %s: %s", stage, exc)

    def _report_failure(
        self,
        progress_callback: ProgressCallback | None,
        doc_id: str,
        error: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self._emit_progress(
            progress_callback,
            "failed",
            {"doc_id": doc_id, "error": error, **(extra or {})},
        )

    def _matches_group(
        self,
        group_id: str | None,
        metadata: dict | None,
        doc_id: str | None,
    ) -> bool:
        if group_id is None:
            return True

        if metadata:
            meta_group = metadata.get("group_id")
            if meta_group == group_id:
                return True

        if doc_id:
            doc = db_manager.get_document(doc_id)
            if doc and doc.group_id == group_id:
                return True

        return False

    def _filter_documents_by_group(
        self,
        documents: list[Document],
        group_id: str | None,
    ) -> list[Document]:
        if group_id is None:
            return documents

        filtered: list[Document] = []
        for doc in documents:
            metadata = doc.metadata or {}
            doc_id = metadata.get("doc_id")
            if self._matches_group(group_id, metadata, doc_id):
                filtered.append(doc)
        return filtered

    def _filter_retriever_results(
        self,
        results: list[dict[str, Any]],
        group_id: str | None,
    ) -> list[dict[str, Any]]:
        if group_id is None:
            return results

        filtered = []
        for item in results:
            metadata = item.get("metadata", {})
            doc_id = metadata.get("doc_id") or item.get("doc_id")
            if self._matches_group(group_id, metadata, doc_id):
                filtered.append(item)
        return filtered

    def _resolve_runtime_llm(
        self,
        *,
        selected_model: str,
        query: str,
        group_id: str | None,
    ) -> tuple[Any, str, str]:
        """统一解析运行时模型，保持 RAG/Agent 选择逻辑一致。"""
        llm, model_used, model_type = resolve_runtime_selection(
            selected_model,
            query,
            group_id=group_id,
        )
        return llm, model_type, model_used

    def add_document(
        self,
        file_content: bytes,
        filename: str,
        doc_id: str | None = None,
        group_id: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> Dict[str, Any]:
        # 支持传入已有的 doc_id（用于编辑文档），否则生成新的
        new_doc_id = doc_id or str(uuid.uuid4())
        is_edit_mode = doc_id is not None
        logger.info(f"开始{'编辑' if is_edit_mode else '添加'}文档: doc_id: {new_doc_id}")

        # 输入验证
        if not filename or not filename.strip():
            self._report_failure(progress_callback, new_doc_id, "文件名无效")
            return {"success": False, "error": "文件名无效"}

        # 文件安全验证
        is_valid, error_msg = _validate_file(file_content, filename)
        if not is_valid:
            self._report_failure(progress_callback, new_doc_id, error_msg)
            return {"success": False, "error": error_msg}

        safe_filename = _sanitize_filename(filename)
        file_path = os.path.join(self._uploads_dir, f"{new_doc_id}_{safe_filename}")
        
        # 路径安全检查
        if not _is_safe_path(self._uploads_dir, file_path):
            logger.error(f"路径安全检查失败: {file_path}")
            self._report_failure(progress_callback, new_doc_id, "无效的文件路径")
            return {"success": False, "error": "无效的文件路径"}

        # 如果是编辑模式，先备份旧文档信息
        old_doc_model = None
        old_file_path = None
        if is_edit_mode and doc_id is not None:
            old_doc_model = db_manager.get_document(doc_id)
            if old_doc_model:
                old_file_path = old_doc_model.file_path

        try:
            with open(file_path, "wb") as f:
                f.write(file_content)
            self._emit_progress(
                progress_callback,
                "file_saved",
                {
                    "doc_id": new_doc_id,
                    "filename": filename,
                    "path": file_path,
                    "group_id": group_id,
                    "is_edit": is_edit_mode,
                },
            )
        except PermissionError as e:
            logger.error(f"权限不足，无法保存文件: {filename}, 错误: {str(e)}")
            self._report_failure(
                progress_callback,
                new_doc_id,
                f"权限不足，无法保存文件: {str(e)}",
            )
            return {"success": False, "error": f"权限不足，无法保存文件: {str(e)}"}
        except OSError as e:
            logger.error(f"保存文件失败: {filename}, 错误: {str(e)}")
            self._report_failure(
                progress_callback,
                new_doc_id,
                f"保存文件失败: {str(e)}",
            )
            return {"success": False, "error": f"保存文件失败: {str(e)}"}

        try:
            # 编辑模式：在写入新 BM25 块之前必须先删除旧块，否则 chunk_id 主键冲突
            if is_edit_mode:
                try:
                    from hybrid_agent.core.hybrid_retriever import get_bm25_retriever
                    bm25_deleted = get_bm25_retriever().delete_chunks(new_doc_id)
                    logger.info(f"编辑模式：预先删除旧 BM25 块 {bm25_deleted} 个")
                except Exception as e:
                    logger.warning(f"编辑模式 BM25 旧块删除失败（继续）: {e}")

            documents = document_processor.process_file(
                file_path,
                filename,
                doc_id=new_doc_id,
                group_id=group_id,
                progress_callback=progress_callback,
            )
            logger.info(f"文档处理完成，生成 {len(documents)} 个文本块")

            ids = [f"{new_doc_id}_{i}" for i in range(len(documents))]
            self.vector_store.add_documents(documents, ids, doc_id=new_doc_id)
            self._emit_progress(
                progress_callback,
                "vectorized",
                {"doc_id": new_doc_id, "chunks": len(ids), "group_id": group_id},
            )
            logger.info(f"向量存储完成，共 {len(ids)} 个向量")

            # 创建新的数据库记录
            doc_model = DocumentModel(
                id=new_doc_id,
                filename=filename,
                file_path=file_path,
                file_size=len(file_content),
                file_type=os.path.splitext(filename)[1],
                group_id=group_id,
                status="ready",
                chunk_count=len(documents)
            )
            db_manager.add_document(doc_model)
            self._emit_progress(
                progress_callback,
                "persisted",
                {
                    "doc_id": new_doc_id,
                    "group_id": group_id,
                    "status": doc_model.status,
                },
            )

            # 如果是编辑模式，成功后再删除旧数据
            if is_edit_mode and old_doc_model:
                try:
                    # 删除旧的向量数据
                    deleted_count = self.vector_store.delete_by_doc_id_prefix(new_doc_id)
                    logger.info(f"已删除旧文档的 {deleted_count} 个向量")

                    # 删除旧的数据库记录
                    db_manager.delete_document(new_doc_id)

                    # 删除旧的物理文件
                    if old_file_path and os.path.exists(old_file_path) and old_file_path != file_path:
                        try:
                            os.remove(old_file_path)
                            logger.info(f"已删除旧文件: {old_file_path}")
                        except (PermissionError, OSError) as e:
                            logger.warning(f"删除旧文件失败: {old_file_path}, 错误: {str(e)}")
                except Exception as e:
                    logger.warning(f"清理旧文档数据失败: {str(e)}")

            logger.info(f"文档{'编辑' if is_edit_mode else '添加'}成功: {filename}")
            return {
                "success": True,
                "doc_id": new_doc_id,
                "filename": filename,
                "chunks": len(documents),
                "message": f"成功{'更新' if is_edit_mode else '添加'}文档 '{filename}'，共 {len(documents)} 个文本块"
            }
        except (ValueError, KeyError) as e:
            logger.error(f"文档处理失败: {filename}, 错误: {str(e)}")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except (PermissionError, OSError):
                    pass
            try:
                from hybrid_agent.core.hybrid_retriever import get_bm25_retriever
                get_bm25_retriever().delete_chunks(new_doc_id)
            except Exception:
                pass
            self._report_failure(
                progress_callback,
                new_doc_id,
                f"文档处理失败: {str(e)}",
            )
            return {"success": False, "error": f"文档处理失败: {str(e)}"}
        except OSError as e:
            logger.error(f"向量存储失败（存储空间不足或IO错误）: {filename}, 错误: {str(e)}")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except (PermissionError, OSError):
                    pass
            try:
                from hybrid_agent.core.hybrid_retriever import get_bm25_retriever
                get_bm25_retriever().delete_chunks(new_doc_id)
            except Exception:
                pass
            self._report_failure(
                progress_callback,
                new_doc_id,
                "向量存储失败: 存储空间不足或IO错误",
            )
            return {"success": False, "error": "向量存储失败: 存储空间不足或IO错误"}
        except Exception as e:
            logger.error(f"添加文档失败（未知错误）: {filename}, 错误: {str(e)}")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except (PermissionError, OSError):
                    pass
            try:
                from hybrid_agent.core.hybrid_retriever import get_bm25_retriever
                get_bm25_retriever().delete_chunks(new_doc_id)
            except Exception:
                pass
            self._report_failure(
                progress_callback,
                new_doc_id,
                f"添加文档失败: {str(e)}",
            )
            return {"success": False, "error": f"添加文档失败: {str(e)}"}
    
    def delete_document(self, doc_id: str, group_id: str | None = None) -> Dict[str, Any]:
        try:
            logger.info(f"开始删除文档: {doc_id}")
            doc_model = db_manager.get_document(doc_id)
            if not doc_model:
                logger.warning(f"文档不存在: {doc_id}")
                return {"success": False, "error": "文档不存在"}

            if group_id is not None and doc_model.group_id != group_id:
                logger.warning(f"组 {group_id} 无权删除文档 {doc_id}")
                return {"success": False, "error": "文档不存在"}

            # 删除物理文件
            if doc_model.file_path and os.path.exists(doc_model.file_path):
                try:
                    os.remove(doc_model.file_path)
                    logger.info(f"已删除物理文件: {doc_model.file_path}")
                except (PermissionError, OSError) as e:
                    logger.warning(f"删除物理文件失败: {doc_model.file_path}, 错误: {str(e)}")
                    # 继续删除向量和数据库记录

            # 删除向量数据
            deleted_count = self.vector_store.delete_by_doc_id_prefix(doc_id)
            logger.info(f"已删除 {deleted_count} 个向量")

            # 删除 BM25 索引
            try:
                from hybrid_agent.core.hybrid_retriever import get_bm25_retriever
                bm25_deleted = get_bm25_retriever().delete_chunks(doc_id)
                logger.info(f"已删除 {bm25_deleted} 个 BM25 块")
            except Exception as e:
                logger.warning(f"BM25 块删除失败（不影响主流程）: {e}")

            # 删除数据库记录
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
        except (KeyError, ValueError) as e:
            logger.error(f"删除文档参数错误: {doc_id}, 错误: {str(e)}")
            return {"success": False, "error": f"参数错误: {str(e)}"}
        except Exception as e:
            logger.error(f"删除文档失败: {doc_id}, 错误: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def list_documents(self, group_id: str | None = None) -> list[Dict[str, Any]]:
        docs = db_manager.get_all_documents()
        if group_id is not None:
            docs = [doc for doc in docs if doc.group_id == group_id]
        return [doc.to_dict() for doc in docs]
    
    def search_documents(
        self,
        query: str,
        k: int = 4,
        group_id: str | None = None,
    ) -> list[Dict[str, Any]]:
        """混合检索文档（BM25 + 向量 + RRF 融合）

        Args:
            query: 查询文本
            k: 返回数量

        Returns:
            检索结果列表，每项包含 content/metadata/score/retrieval_method
        """
        try:
            from hybrid_agent.core.hybrid_retriever import get_multi_path_retriever
            retriever = get_multi_path_retriever()
            raw_results = retriever.retrieve_sync(query)
            raw_results = self._filter_retriever_results(raw_results, group_id)
            # 截取 top-k，截短 content 以控制长度
            sources = []
            for r in raw_results[:k]:
                sources.append({
                    "content": r["content"][:500],
                    "metadata": r.get("metadata", {}),
                    "score": r.get("rrf_score", r.get("score", 0.0)),
                    "retrieval_method": r.get("retrieval_method", "hybrid"),
                })
            return sources
        except Exception as e:
            logger.warning(f"混合检索失败，降级到纯向量检索: {e}")
            results = self.vector_store.search_with_score(query, k=k)
            if group_id is not None:
                filtered_results = []
                for doc, score in results:
                    metadata = doc.metadata or {}
                    doc_id = metadata.get("doc_id")
                    if self._matches_group(group_id, metadata, doc_id):
                        filtered_results.append((doc, score))
                results = filtered_results
            sources = []
            for doc, score in results:
                sources.append({
                    "content": doc.page_content[:500],
                    "metadata": doc.metadata,
                    "score": float(score),
                    "retrieval_method": "dense_fallback",
                })
            return sources
    
    def query(
        self,
        query: str,
        use_rag: bool = True,
        model: str = "advanced",
        k: int = 4,
        group_id: str | None = None,
    ) -> Dict[str, Any]:
        if not use_rag:
            return self._direct_query(query, model, group_id=group_id)
        
        try:
            retrieved_docs = self.vector_store.search(query, k=k, group_id=group_id)
            retrieved_docs = self._filter_documents_by_group(retrieved_docs, group_id)
            
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
            
            llm, model_type, model_used = self._resolve_runtime_llm(
                selected_model=model or "auto",
                query=query,
                group_id=group_id,
            )
            
            from langchain_core.messages import HumanMessage
            formatted_prompt = prompt.format(context=context, question=query)
            messages = [HumanMessage(content=formatted_prompt)]
            
            full_answer = ""
            thinking_content = ""
            
            for chunk in llm.stream(messages):
                if hasattr(chunk, 'content'):
                    full_answer += _extract_chunk_text(chunk.content)
                
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
                "thinking_process": thinking_content,
                "model_used": model_used,
                "model_type": model_type,
            }
        except (KeyError, ValueError) as e:
            logger.error(f"查询参数错误: {str(e)}")
            return {
                "success": False,
                "error": "查询参数错误",
                "answer": "参数错误，请检查输入",
                "sources": []
            }
        except Exception as e:
            logger.error(f"查询处理失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": "服务器内部错误",
                "answer": "处理查询时出错，请稍后重试",
                "sources": []
            }
    
    def _direct_query(
        self,
        query: str,
        model: str = "advanced",
        group_id: str | None = None,
    ) -> Dict[str, Any]:
        try:
            llm, model_type, model_used = self._resolve_runtime_llm(
                selected_model=model or "auto",
                query=query,
                group_id=group_id,
            )
            
            from langchain_core.messages import HumanMessage
            messages = [HumanMessage(content=query)]
            
            full_answer = ""
            thinking_content = ""
            
            for chunk in llm.stream(messages):
                if hasattr(chunk, 'content'):
                    full_answer += _extract_chunk_text(chunk.content)
                
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
                "thinking_process": thinking_content,
                "model_used": model_used,
                "model_type": model_type,
            }
        except Exception as e:
            logger.error(f"直接查询失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": "服务器内部错误",
                "answer": "处理查询时出错，请稍后重试",
                "sources": []
            }
    
    def query_with_stream(
        self,
        query: str,
        use_rag: bool = True,
        model: str = "advanced",
        k: int = 4,
        group_id: str | None = None,
    ) -> Generator[str, None, None]:
        if not use_rag:
            llm, _, _ = self._resolve_runtime_llm(
                selected_model=model or "auto",
                query=query,
                group_id=group_id,
            )
            from langchain_core.messages import HumanMessage
            messages = [HumanMessage(content=query)]
            
            for chunk in llm.stream(messages):
                if hasattr(chunk, 'content'):
                    yield _extract_chunk_text(chunk.content)
            return
        
        try:
            retrieved_docs = self.vector_store.search(query, k=k, group_id=group_id)
            retrieved_docs = self._filter_documents_by_group(retrieved_docs, group_id)
            
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
            
            llm, _, _ = self._resolve_runtime_llm(
                selected_model=model or "auto",
                query=query,
                group_id=group_id,
            )
            
            from langchain_core.messages import HumanMessage
            formatted_prompt = prompt.format(context=context, question=query)
            messages = [HumanMessage(content=formatted_prompt)]
            
            for chunk in llm.stream(messages):
                if hasattr(chunk, 'content'):
                    yield _extract_chunk_text(chunk.content)
        except (KeyError, ValueError) as e:
            logger.error(f"流式查询参数错误: {str(e)}")
            yield "处理查询时出错: 参数错误"
        except Exception as e:
            logger.error(f"流式查询失败: {str(e)}", exc_info=True)
            yield "处理查询时出错，请稍后重试"
    
    def get_stats(self) -> Dict[str, Any]:
        count = self.vector_store.get_collection_count()
        docs = db_manager.get_all_documents()
        
        return {
            "total_documents": len(docs),
            "total_chunks": count,
            "documents": [doc.to_dict() for doc in docs]
        }


_rag_system: RAGSystem | None = None
_rag_system_lock = threading.Lock()


def get_rag_system() -> RAGSystem:
    """获取 RAG 系统实例（线程安全）"""
    global _rag_system
    if _rag_system is None:
        with _rag_system_lock:
            # 双重检查锁定
            if _rag_system is None:
                _rag_system = RAGSystem()
    return _rag_system
