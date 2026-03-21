"""内容审查器核心模块"""

from __future__ import annotations

import hashlib
import logging
import threading
from collections import OrderedDict
from typing import Any

from hybrid_agent.core.config import ReviewerSettings, default_reviewer_settings
from hybrid_agent.llm.reviewer import create_reviewer_model
from hybrid_agent.agent.reviewer.prompts import (
    format_single_review_prompt,
    format_batch_review_prompt,
    format_context_optimization_prompt,
)
from hybrid_agent.agent.reviewer.scorer import (
    ReviewScore,
    BatchReviewResult,
    parse_review_response,
    parse_batch_review_response,
    calculate_relevance_threshold,
    should_include_content,
)

logger = logging.getLogger(__name__)

# 缓存最大条目数
MAX_CACHE_SIZE = 1000


class ContentReviewer:
    """内容审查器
    
    用于审查检索到的内容（网络搜索结果或知识库文档），
    评估其与用户问题的相关性，并过滤低质量内容。
    """
    
    def __init__(self, settings: ReviewerSettings | None = None, max_cache_size: int = MAX_CACHE_SIZE):
        self.settings = settings or default_reviewer_settings
        self.model = create_reviewer_model(
            model_name=self.settings.model_name,
            temperature=self.settings.temperature,
            max_tokens=self.settings.max_tokens,
        )
        self._cache: OrderedDict[str, ReviewScore] = OrderedDict()
        self._max_cache_size = max_cache_size
    
    def _get_from_cache(self, key: str) -> ReviewScore | None:
        """从缓存获取数据，命中时移到末尾（LRU）"""
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None
    
    def _add_to_cache(self, key: str, value: ReviewScore) -> None:
        """添加到缓存，超过限制时淘汰最旧的条目"""
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key] = value
        else:
            if len(self._cache) >= self._max_cache_size:
                self._cache.popitem(last=False)  # 淘汰最旧的条目
            self._cache[key] = value
    
    def review_single(
        self,
        query: str,
        content: str,
        source_type: str = "knowledge_base"
    ) -> ReviewScore:
        """审查单条内容
        
        Args:
            query: 用户问题
            content: 待审查内容
            source_type: 内容来源类型
        
        Returns:
            ReviewScore 审查评分对象
        """
        # 检查缓存 - 使用 SHA256 生成更可靠的缓存键
        content_preview = content[:200] if len(content) > 200 else content
        cache_key = hashlib.sha256(f"{query}_{content_preview}".encode('utf-8')).hexdigest()
        
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        try:
            prompt = format_single_review_prompt(query, content, source_type)
            response = self.model.invoke(prompt)
            
            score = parse_review_response(response.content)
            if score is None:
                # 解析失败，返回默认评分
                logger.warning(f"审查响应解析失败: {response.content[:100]}")
                score = ReviewScore(
                    total_score=5,
                    relevance=2,
                    completeness=2,
                    timeliness=1,
                    credibility=0,
                    reasoning="解析失败，使用默认评分",
                    should_use=True,
                    key_info=[]
                )
            
            # 缓存结果
            self._add_to_cache(cache_key, score)
            return score
            
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"审查内容失败: 参数错误 - {str(e)}")
            return ReviewScore(
                total_score=5,
                relevance=2,
                completeness=2,
                timeliness=1,
                credibility=0,
                reasoning=f"审查异常: 参数错误",
                should_use=True,
                key_info=[]
            )
        except Exception as e:
            logger.error(f"审查内容失败: {e}")
            return ReviewScore(
                total_score=5,
                relevance=2,
                completeness=2,
                timeliness=1,
                credibility=0,
                reasoning=f"审查异常: {str(e)}",
                should_use=True,
                key_info=[]
            )
    
    def review_batch(
        self,
        query: str,
        contents: list[dict],
        query_complexity: float = 0.5
    ) -> BatchReviewResult:
        """批量审查内容
        
        Args:
            query: 用户问题
            contents: 内容列表，每项包含 content 和 source_type
            query_complexity: 问题复杂度 (0-1)
        
        Returns:
            BatchReviewResult 批量审查结果
        """
        if not contents:
            return BatchReviewResult(
                reviews=[],
                best_index=None,
                overall_assessment="无内容需要审查",
                filtered_contents=[]
            )
        
        # 如果内容较少，逐条审查
        if len(contents) <= 3:
            reviews = []
            for item in contents:
                score = self.review_single(
                    query=query,
                    content=item.get("content", ""),
                    source_type=item.get("source_type", "unknown")
                )
                reviews.append(score)
        else:
            # 批量审查
            reviews = self._review_batch_optimized(query, contents)
        
        # 计算动态阈值
        threshold = calculate_relevance_threshold(
            base_threshold=self.settings.relevance_threshold,
            query_complexity=query_complexity,
            content_count=len(contents)
        )
        
        # 过滤内容
        filtered_contents = []
        current_count = 0
        
        for i, (item, score) in enumerate(zip(contents, reviews)):
            if should_include_content(
                score=score,
                threshold=threshold,
                min_contents=2,
                current_count=current_count
            ):
                filtered_contents.append({
                    **item,
                    "review_score": score.total_score,
                    "key_info": score.key_info,
                    "weight": score.weight,
                })
                current_count += 1
            
            if current_count >= self.settings.max_contents:
                break
        
        # 找出最佳内容
        best_index = None
        if reviews:
            best_index = max(range(len(reviews)), key=lambda i: reviews[i].total_score)
        
        # 整体评估
        if reviews:
            avg_score = sum(r.total_score for r in reviews) / len(reviews)
            high_quality = sum(1 for r in reviews if r.total_score >= 7)
            overall = f"平均分 {avg_score:.1f}，{high_quality} 条高质量内容"
        else:
            overall = "无有效内容"
        
        return BatchReviewResult(
            reviews=reviews,
            best_index=best_index,
            overall_assessment=overall,
            filtered_contents=filtered_contents,
        )
    
    def _review_batch_optimized(
        self,
        query: str,
        contents: list[dict]
    ) -> list[ReviewScore]:
        """优化的批量审查（使用批量提示词）"""
        try:
            prompt = format_batch_review_prompt(query, contents)
            response = self.model.invoke(prompt)
            
            parsed = parse_batch_review_response(response.content)
            if parsed and "reviews" in parsed:
                reviews = []
                for item in parsed["reviews"]:
                    score = ReviewScore(
                        total_score=int(item.get("total_score", 0)),
                        relevance=int(item.get("breakdown", {}).get("relevance", 0)),
                        completeness=int(item.get("breakdown", {}).get("completeness", 0)),
                        timeliness=int(item.get("breakdown", {}).get("timeliness", 0)),
                        credibility=int(item.get("breakdown", {}).get("credibility", 0)),
                        reasoning=item.get("reasoning", ""),
                        should_use=item.get("should_use", True),
                        key_info=item.get("key_info", []),
                    )
                    reviews.append(score)
                return reviews
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"批量审查失败: 参数错误 - {str(e)}")
        
        # 降级为逐条审查
        return [
            self.review_single(
                query=query,
                content=item.get("content", ""),
                source_type=item.get("source_type", "unknown")
            )
            for item in contents
        ]
    
    def optimize_context(
        self,
        query: str,
        reviewed_contents: list[dict]
    ) -> str:
        """优化上下文内容
        
        Args:
            query: 用户问题
            reviewed_contents: 已审查的内容列表
        
        Returns:
            优化后的上下文字符串
        """
        if not reviewed_contents:
            return ""
        
        try:
            prompt = format_context_optimization_prompt(query, reviewed_contents)
            response = self.model.invoke(prompt)
            return response.content
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"上下文优化失败: 参数错误 - {str(e)}")
            # 降级：直接拼接内容
            return "\n\n---\n\n".join(
                c.get("content", "")[:500]
                for c in reviewed_contents[:3]
            )
        except Exception as e:
            logger.error(f"上下文优化失败: {e}")
            # 降级：直接拼接内容
            return "\n\n---\n\n".join(
                c.get("content", "")[:500]
                for c in reviewed_contents[:3]
            )
    
    def clear_cache(self) -> None:
        """清除缓存"""
        self._cache.clear()


# 全局审查器实例
_reviewer_instance: ContentReviewer | None = None
_reviewer_lock = threading.Lock()


def get_reviewer() -> ContentReviewer:
    """获取全局审查器实例（线程安全）"""
    global _reviewer_instance
    if _reviewer_instance is None:
        with _reviewer_lock:
            # 双重检查锁定
            if _reviewer_instance is None:
                _reviewer_instance = ContentReviewer()
    return _reviewer_instance


def review_contents(
    query: str,
    contents: list[dict],
    query_complexity: float = 0.5
) -> BatchReviewResult:
    """审查内容的便捷函数"""
    reviewer = get_reviewer()
    return reviewer.review_batch(query, contents, query_complexity)


__all__ = [
    "ContentReviewer",
    "get_reviewer",
    "review_contents",
    "ReviewScore",
    "BatchReviewResult",
]
