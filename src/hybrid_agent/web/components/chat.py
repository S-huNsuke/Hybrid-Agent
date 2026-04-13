"""聊天组件"""

import streamlit as st

from hybrid_agent.web.utils.helpers import sanitize_user_content


def display_message(
    role: str,
    content: str,
    model_used: str | None = None,
    sources: list | None = None,
    thinking_process: str | None = None
) -> None:
    """显示消息"""
    is_user = role == "user"
    avatar_class = "avatar-user" if is_user else "avatar-assistant"
    avatar = "👤" if is_user else "🤖"
    container_class = "message-user" if is_user else "message-assistant"
    
    content = sanitize_user_content(content) if content else ""
    
    model_badge = ""
    if role == "assistant" and model_used:
        model_name = "Qwen3" if "qwen" in model_used.lower() else "DeepSeek"
        model_badge = f'<span class="model-badge">{model_name}</span>'
    
    thinking_html = ""
    if role == "assistant" and thinking_process:
        safe_thinking = sanitize_user_content(thinking_process)
        thinking_html = f"""
        <div class="thinking-panel">
            <div class="thinking-panel-header" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
                <span>🧠</span>
                <span>思考过程 (点击展开/折叠)</span>
            </div>
            <div class="thinking-panel-content" style="display: none;">{safe_thinking}</div>
        </div>
        """
    
    st.markdown(f"""
    <div class="message-container {container_class}">
        <div class="avatar {avatar_class}">{avatar}</div>
        <div class="message-bubble">{model_badge}{thinking_html}{content}</div>
    </div>
    """, unsafe_allow_html=True)
    
    if role == "assistant" and sources:
        for source in sources[:3]:
            filename = sanitize_user_content(source.get('filename', '未知文件'))
            content_preview = sanitize_user_content(source.get('content', '')[:150])
            st.markdown(f"""
            <div class="source-item">
                <div class="source-filename">📄 {filename}</div>
                <div class="source-content">{content_preview}...</div>
            </div>
            """, unsafe_allow_html=True)


def display_welcome() -> None:
    """显示欢迎页面"""
    theme = st.session_state.get("theme", "light")
    theme_status = "🌙 暗色模式" if theme == "dark" else "☀️ 亮色模式"
    use_rag = st.session_state.get("use_rag", True)
    rag_status = "📚 RAG + 智能模式" if use_rag else "💬 普通对话模式"

    st.markdown(f"""
    <div class="welcome-header">
        <div style="font-size: 48px; margin-bottom: 20px;">🤖</div>
        <h1 class="welcome-title">欢迎使用智能问答助手</h1>
        <p class="welcome-subtitle">基于问题复杂度自动切换的多模型智能助手 + RAG 知识库</p>
        <div class="mode-badge">
            <span>✨</span>
            <span>{rag_status}</span>
        </div>
        <div class="mode-badge">
            <span>🎨</span>
            <span>{theme_status}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def display_thinking_indicator() -> None:
    """显示思考中指示器"""
    st.markdown("""
    <div class="message-container message-assistant">
        <div class="avatar avatar-assistant">🤖</div>
        <div class="message-bubble">
            <div class="thinking-indicator">
                <span>💭 AI 正在思考...</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
