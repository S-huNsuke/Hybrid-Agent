import logging

from langchain_community.tools import StructuredTool
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper

logger = logging.getLogger(__name__)

search = DuckDuckGoSearchAPIWrapper()


def web_search_func(query: str) -> str:
    try:
        logger.info(f"执行网页搜索: {query}")
        results = search.run(query)
        logger.info(f"搜索完成，结果长度: {len(results)}")
        return results
    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        return f"搜索失败: {str(e)}"


web_search = StructuredTool.from_function(
    func=web_search_func,
    name="web_search",
    description="当用户问题需要实时信息或当前知识时，使用此工具进行网页搜索。输入搜索关键词或问题，输出搜索结果摘要。",
)

__all__ = ["web_search"]
