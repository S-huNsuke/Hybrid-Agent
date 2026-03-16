"""Web 工具函数"""

import re
from html import escape


def sanitize_html(text: str) -> str:
    """移除 HTML 标签并转义 HTML 实体"""
    if not text:
        return ""
    escaped = escape(text)
    cleaned = re.sub(r'<[^>]+>', '', escaped)
    return cleaned


def sanitize_user_content(text: str) -> str:
    """清理用户生成的内容以确保安全渲染"""
    if not text:
        return ""
    sanitized = sanitize_html(text)
    sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'on\w+\s*=', '', sanitized, flags=re.IGNORECASE)
    return sanitized


def truncate_text(text: str, max_length: int = 100) -> str:
    """截断文本到指定长度"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def format_file_size(size: int) -> str:
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
