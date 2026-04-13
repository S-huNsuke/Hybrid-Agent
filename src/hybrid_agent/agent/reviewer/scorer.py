"""评分算法模块"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ReviewScore:
    """审查评分结果"""
    total_score: int
    relevance: int
    completeness: int
    timeliness: int
    credibility: int
    reasoning: str
    should_use: bool
    key_info: list[str]
    
    @property
    def weight(self) -> float:
        """根据总分计算权重"""
        if self.total_score >= 8:
            return 1.0
        elif self.total_score >= 6:
            return 0.85
        elif self.total_score >= 4:
            return 0.7
        else:
            return 0.5


@dataclass
class BatchReviewResult:
    """批量审查结果"""
    reviews: list[ReviewScore]
    best_index: int | None
    overall_assessment: str
    filtered_contents: list[dict]  # 过滤后的内容
    
    @property
    def average_score(self) -> float:
        """计算平均分"""
        if not self.reviews:
            return 0.0
        return sum(r.total_score for r in self.reviews) / len(self.reviews)
    
    @property
    def high_quality_count(self) -> int:
        """高质量内容数量 (score >= 7)"""
        return sum(1 for r in self.reviews if r.total_score >= 7)


def parse_review_response(response: str) -> ReviewScore | None:
    """解析单条审查响应
    
    Args:
        response: LLM 返回的 JSON 字符串
    
    Returns:
        ReviewScore 对象，解析失败返回 None
    """
    import json
    import re
    
    try:
        # 尝试提取 JSON
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = json.loads(response)
        
        return ReviewScore(
            total_score=int(data.get("total_score", 0)),
            relevance=int(data.get("breakdown", {}).get("relevance", 0)),
            completeness=int(data.get("breakdown", {}).get("completeness", 0)),
            timeliness=int(data.get("breakdown", {}).get("timeliness", 0)),
            credibility=int(data.get("breakdown", {}).get("credibility", 0)),
            reasoning=data.get("reasoning", ""),
            should_use=data.get("should_use", True),
            key_info=data.get("key_info", []),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def parse_batch_review_response(response: str) -> dict[str, Any] | None:
    """解析批量审查响应
    
    Args:
        response: LLM 返回的 JSON 字符串
    
    Returns:
        解析后的字典，失败返回 None
    """
    import json
    import re
    
    try:
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(response)
    except (json.JSONDecodeError, TypeError):
        return None


def calculate_relevance_threshold(
    base_threshold: float,
    query_complexity: float,
    content_count: int
) -> float:
    """动态计算相关性阈值
    
    Args:
        base_threshold: 基础阈值
        query_complexity: 问题复杂度 (0-1)
        content_count: 内容数量
    
    Returns:
        调整后的阈值
    """
    # 复杂问题降低阈值，允许更多上下文
    complexity_adjustment = (1 - query_complexity) * 0.5
    
    # 内容多时提高阈值，更严格筛选
    count_adjustment = min(content_count * 0.1, 1.0)
    
    adjusted = base_threshold - complexity_adjustment + count_adjustment
    return max(3.0, min(adjusted, 8.0))  # 限制在 3-8 之间


def should_include_content(
    score: ReviewScore,
    threshold: float,
    min_contents: int = 2,
    current_count: int = 0
) -> bool:
    """判断是否应该包含该内容
    
    Args:
        score: 审查评分
        threshold: 相关性阈值
        min_contents: 最少保留内容数
        current_count: 当前已保留数量
    
    Returns:
        是否应该包含
    """
    # 如果评分高于阈值，直接包含
    if score.total_score >= threshold:
        return True
    
    # 如果内容质量很高（相关性和完整性都不错），包含
    if score.relevance >= 3 and score.completeness >= 2:
        return True
    
    # 如果当前保留数量不足最小值，且评分不算太低，包含
    if current_count < min_contents and score.total_score >= 3:
        return True
    
    return False


def rank_contents_by_relevance(
    contents: list[dict],
    scores: list[ReviewScore]
) -> list[tuple[dict, ReviewScore]]:
    """按相关度排序内容
    
    Args:
        contents: 原始内容列表
        scores: 对应的评分列表
    
    Returns:
        排序后的 (内容, 评分) 元组列表
    """
    if len(contents) != len(scores):
        raise ValueError("内容数量和评分数量不匹配")
    
    paired = list(zip(contents, scores))
    # 按总分降序排序
    paired.sort(key=lambda x: x[1].total_score, reverse=True)
    
    return paired


def merge_key_infos(scores: list[ReviewScore], max_infos: int = 10) -> list[str]:
    """合并关键信息点
    
    Args:
        scores: 评分列表
        max_infos: 最大信息点数量
    
    Returns:
        去重后的关键信息列表
    """
    all_infos = []
    seen = set()
    
    for score in scores:
        for info in score.key_info:
            # 简单去重
            normalized = info.strip().lower()
            if normalized not in seen and len(normalized) > 5:
                all_infos.append(info.strip())
                seen.add(normalized)
                
                if len(all_infos) >= max_infos:
                    return all_infos
    
    return all_infos


__all__ = [
    "ReviewScore",
    "BatchReviewResult",
    "parse_review_response",
    "parse_batch_review_response",
    "calculate_relevance_threshold",
    "should_include_content",
    "rank_contents_by_relevance",
    "merge_key_infos",
]
