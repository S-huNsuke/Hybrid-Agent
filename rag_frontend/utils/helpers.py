import re
from html import escape


def sanitize_html(text: str) -> str:
    """Remove HTML tags and escape HTML entities from text"""
    if not text:
        return ""
    escaped = escape(text)
    cleaned = re.sub(r'<[^>]+>', '', escaped)
    return cleaned


def sanitize_user_content(text: str) -> str:
    """Sanitize user-generated content for safe rendering"""
    if not text:
        return ""
    sanitized = sanitize_html(text)
    sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r'on\w+\s*=', '', sanitized, flags=re.IGNORECASE)
    return sanitized


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to specified length"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def format_file_size(size: int) -> str:
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def extract_code_blocks(text: str) -> list:
    """Extract code blocks from markdown text"""
    pattern = r'```(\w+)?\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL)
    return [{'language': lang, 'code': code} for lang, code in matches]


def is_valid_session_id(session_id: str) -> bool:
    """Validate session ID format"""
    pattern = r'^[a-zA-Z0-9-_]{8,64}$'
    return bool(re.match(pattern, session_id))
