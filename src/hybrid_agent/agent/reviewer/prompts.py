"""审查器提示词模板"""

# 单条内容审查提示词
SINGLE_CONTENT_REVIEW_PROMPT = """你是一个专业的内容审查专家。请评估以下检索到的内容与用户问题的相关程度。

## 用户问题
{query}

## 待审查内容
{content}

## 内容来源
{source_type}

## 评分标准 (总分 10 分)
1. 语义相关性 (0-4分): 内容是否直接回答或有助于回答用户问题
2. 信息完整性 (0-3分): 信息是否完整、具体、可操作
3. 时效性 (0-2分): 信息是否最新有效 (知识库内容默认 1 分，网络搜索根据内容判断)
4. 可信度 (0-1分): 来源是否可靠、信息是否准确

请严格按照 JSON 格式输出，不要添加任何其他文字:
{{
    "total_score": <0-10 的整数>,
    "breakdown": {{
        "relevance": <0-4 的整数>,
        "completeness": <0-3 的整数>,
        "timeliness": <0-2 的整数>,
        "credibility": <0-1 的整数>
    }},
    "reasoning": "<一句话说明评分理由>",
    "should_use": <true 或 false>,
    "key_info": ["提取的 1-3 个关键信息点"]
}}"""


# 批量内容审查提示词
BATCH_CONTENT_REVIEW_PROMPT = """你是一个专业的内容审查专家。请批量评估以下检索到的内容与用户问题的相关程度。

## 用户问题
{query}

## 待审查内容列表
{contents_formatted}

## 评分标准 (总分 10 分)
1. 语义相关性 (0-4分): 内容是否直接回答或有助于回答用户问题
2. 信息完整性 (0-3分): 信息是否完整、具体、可操作
3. 时效性 (0-2分): 信息是否最新有效
4. 可信度 (0-1分): 来源是否可靠、信息是否准确

请严格按照 JSON 格式输出，不要添加任何其他文字:
{{
    "reviews": [
        {{
            "index": <内容索引>,
            "total_score": <0-10 的整数>,
            "breakdown": {{
                "relevance": <0-4 的整数>,
                "completeness": <0-3 的整数>,
                "timeliness": <0-2 的整数>,
                "credibility": <0-1 的整数>
            }},
            "reasoning": "<一句话说明评分理由>",
            "should_use": <true 或 false>,
            "key_info": ["提取的 1-3 个关键信息点"]
        }}
    ],
    "best_index": <最相关内容的索引>,
    "overall_assessment": "<整体评估，一句话说明这些内容整体质量>"
}}"""


# 上下文优化提示词
CONTEXT_OPTIMIZATION_PROMPT = """你是一个信息整合专家。请根据用户问题，对审查后的内容进行优化整合。

## 用户问题
{query}

## 已审查内容 (按相关度排序)
{reviewed_contents}

## 任务
1. 去除冗余信息
2. 合并相似内容
3. 保留最关键的信息点
4. 按逻辑顺序组织

请输出优化后的上下文内容 (直接输出内容，不要添加任何解释):"""


# 相关性判断提示词 (快速版本，用于初步筛选)
QUICK_RELEVANCE_PROMPT = """判断以下内容是否与用户问题相关。

用户问题: {query}
内容: {content}

只输出 JSON: {{"relevant": <true/false>, "confidence": <0-1>}}"""


def format_single_review_prompt(
    query: str,
    content: str,
    source_type: str = "knowledge_base"
) -> str:
    """格式化单条内容审查提示词"""
    return SINGLE_CONTENT_REVIEW_PROMPT.format(
        query=query,
        content=content[:2000],  # 限制长度
        source_type=source_type
    )


def format_batch_review_prompt(
    query: str,
    contents: list[dict],
    max_content_length: int = 1000
) -> str:
    """格式化批量内容审查提示词
    
    Args:
        query: 用户问题
        contents: 内容列表，每项包含 content 和 source_type
        max_content_length: 每条内容的最大长度
    """
    formatted_parts = []
    for i, item in enumerate(contents):
        content = item.get("content", "")[:max_content_length]
        source = item.get("source_type", "unknown")
        formatted_parts.append(f"【内容 {i}】(来源: {source})\n{content}")
    
    contents_formatted = "\n\n---\n\n".join(formatted_parts)
    
    return BATCH_CONTENT_REVIEW_PROMPT.format(
        query=query,
        contents_formatted=contents_formatted
    )


def format_context_optimization_prompt(
    query: str,
    reviewed_contents: list[dict]
) -> str:
    """格式化上下文优化提示词"""
    formatted_parts = []
    for i, item in enumerate(reviewed_contents):
        score = item.get("total_score", 0)
        content = item.get("content", "")
        key_info = item.get("key_info", [])
        
        formatted_parts.append(
            f"【内容 {i+1}】(评分: {score}/10)\n"
            f"关键信息: {', '.join(key_info)}\n"
            f"内容: {content}"
        )
    
    contents_str = "\n\n".join(formatted_parts)
    
    return CONTEXT_OPTIMIZATION_PROMPT.format(
        query=query,
        reviewed_contents=contents_str
    )


__all__ = [
    "SINGLE_CONTENT_REVIEW_PROMPT",
    "BATCH_CONTENT_REVIEW_PROMPT",
    "CONTEXT_OPTIMIZATION_PROMPT",
    "QUICK_RELEVANCE_PROMPT",
    "format_single_review_prompt",
    "format_batch_review_prompt",
    "format_context_optimization_prompt",
]
