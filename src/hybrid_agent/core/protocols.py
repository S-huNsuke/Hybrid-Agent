"""检索器接口定义

定义检索器的统一接口协议，便于扩展不同类型的检索器实现。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class RetrieverProtocol(Protocol):
    """检索器协议基类
    
    所有检索器（BM25、Vector、Hybrid 等）都应实现此协议。
    使用 @runtime_checkable 装饰器支持 isinstance() 检查。
    """

    def search(self, query: str, k: int = 10) -> list[dict]:
        """执行检索

        Args:
            query: 查询文本
            k: 返回数量

        Returns:
            检索结果列表，每项包含：
            - content: 文本内容
            - doc_id: 文档 ID
            - chunk_id: 文本块 ID
            - score: 相关性分数
            - retrieval_method: 检索方法标识
            - metadata: 元数据（可选）
        """
        ...


class AsyncRetrieverProtocol(Protocol):
    """异步检索器协议基类"""

    async def search(self, query: str, k: int = 10) -> list[dict]:
        """异步执行检索

        Args:
            query: 查询文本
            k: 返回数量

        Returns:
            检索结果列表
        """
        ...


class IndexableRetrieverProtocol(Protocol):
    """可索引检索器协议
    
    支持索引管理的检索器（如 BM25）。
    """

    def index_chunks(
        self,
        doc_id: str,
        chunks: list[str],
        chunk_ids: list[str] | None = None,
    ) -> None:
        """索引文档块

        Args:
            doc_id: 文档 ID
            chunks: 文本块列表
            chunk_ids: 文本块 ID 列表（可选）
        """
        ...

    def delete_chunks(self, doc_id: str) -> int:
        """删除文档索引

        Args:
            doc_id: 文档 ID

        Returns:
            删除的块数量
        """
        ...
