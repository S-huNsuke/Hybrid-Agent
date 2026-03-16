"""网络搜索工具 - 集成内容审查"""

import logging
from requests import RequestException

from langchain_core.tools import StructuredTool
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper

from hybrid_agent.core.config import default_reviewer_settings
from hybrid_agent.agent.reviewer import get_reviewer, BatchReviewResult

logger = logging.getLogger(__name__)

search = DuckDuckGoSearchAPIWrapper()


def web_search_func(query: str, enable_review: bool = True) -> str:
    """执行网络搜索并审查结果
    
    Args:
        query: 搜索关键词
        enable_review: 是否启用内容审查
    
    Returns:
        搜索结果摘要
    """
    try:
        logger.info(f"执行网页搜索: {query}")
        
        # 获取原始搜索结果
        raw_results = search.results(query, max_results=5)
        
        if not raw_results:
            return "未找到相关搜索结果"
        
        # 格式化搜索结果
        formatted_results = []
        for item in raw_results:
            formatted_results.append({
                "content": f"{item.get('title', '')}\n{item.get('snippet', '')}\n{item.get('link', '')}",
                "source_type": "web_search",
                "title": item.get("title", ""),
                "link": item.get("link", ""),
            })
        
        # 审查内容
        if enable_review and default_reviewer_settings.enabled:
            reviewer = get_reviewer()
            review_result: BatchReviewResult = reviewer.review_batch(
                query=query,
                contents=formatted_results,
                query_complexity=0.5  # 默认中等复杂度
            )
            
            logger.info(f"搜索结果审查完成: {review_result.overall_assessment}")
            
            # 使用审查后的高质量内容
            filtered = review_result.filtered_contents
            
            if not filtered:
                # 如果审查后无内容，使用原始结果的前2条
                filtered = formatted_results[:2]
            
            # 格式化输出
            output_parts = []
            for i, item in enumerate(filtered[:3], 1):
                score = item.get("review_score", "N/A")
                title = item.get("title", "")
                link = item.get("link", "")
                content = item.get("content", "")
                key_info = item.get("key_info", [])
                
                output_parts.append(
                    f"【结果 {i}】(相关度: {score}/10)\n"
                    f"标题: {title}\n"
                    f"链接: {link}\n"
                    f"摘要: {content[:300]}...\n"
                    f"关键信息: {', '.join(key_info[:3]) if key_info else '无'}"
                )
            
            output = "\n\n---\n\n".join(output_parts)
            output += f"\n\n[审查摘要: {review_result.overall_assessment}]"
            
            return output
        else:
            # 不审查，直接返回原始结果
            output_parts = []
            for i, item in enumerate(formatted_results[:3], 1):
                output_parts.append(
                    f"【结果 {i}】\n"
                    f"标题: {item.get('title', '')}\n"
                    f"链接: {item.get('link', '')}\n"
                    f"摘要: {item.get('content', '')[:300]}..."
                )
            return "\n\n---\n\n".join(output_parts)
            
    except RequestException as e:
        logger.error(f"网络搜索请求失败: {str(e)}")
        return f"搜索失败: 网络连接问题"
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"搜索结果解析失败: {str(e)}")
        return f"搜索失败: 数据解析错误"
    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        return f"搜索失败: {str(e)}"


web_search = StructuredTool.from_function(
    func=web_search_func,
    name="web_search",
    description="当用户问题需要实时信息或当前知识时，使用此工具进行网页搜索。输入搜索关键词或问题，输出经过相关性审查的搜索结果摘要。",
)

__all__ = ["web_search", "web_search_func"]