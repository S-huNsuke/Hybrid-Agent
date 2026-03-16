"""Streamlit Web 应用主入口"""

import uuid

import streamlit as st

from hybrid_agent.agent.builder import build_agent, get_agent_instance, get_tools
from hybrid_agent.core.rag_system import get_rag_system
from hybrid_agent.llm.model_selector import resolve_model_type
from hybrid_agent.web.components import (
    get_theme_css,
    display_message,
    display_welcome,
    display_thinking_indicator,
    render_sidebar,
)


def init_session_state() -> None:
    """初始化 session state"""
    defaults = {
        "agent": None,
        "messages": [],
        "documents": [],
        "selected_model": "auto",
        "chat_history": [],
        "session_id": None,
        "use_rag": True,
        "pending_tool_call": None,
        "thinking_process": "",
        "processed_files": set(),
        "theme": "light"
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    if st.session_state.session_id is None:
        st.session_state.session_id = str(uuid.uuid4())
    
    # 加载文档列表
    try:
        rag_system = get_rag_system()
        stats = rag_system.get_stats()
        st.session_state.documents = stats.get("documents", [])
    except Exception as e:
        print(f"加载 RAG 系统失败: {e}")


def extract_thinking_from_chunk(chunk) -> str:
    """从响应块中提取思考过程"""
    thinking = ""
    if hasattr(chunk, 'additional_kwargs'):
        kwargs = chunk.additional_kwargs
        if isinstance(kwargs, dict):
            reasoning = kwargs.get('reasoning_content', '')
            if reasoning:
                thinking = reasoning
    return thinking


def handle_rag_query(prompt: str) -> None:
    """处理 RAG 查询"""
    rag_system = get_rag_system()
    selected_model = st.session_state.get("modelSelector", "auto")
    
    model_type = resolve_model_type(selected_model)
    
    placeholder = st.empty()
    display_thinking_indicator()
    
    try:
        result = rag_system.query(
            query=prompt,
            use_rag=True,
            model=model_type,
            k=4
        )
        
        if result.get("success"):
            answer = result.get("answer", "")
            sources = result.get("sources", [])
            thinking_process = result.get("thinking_process", "")
            
            display_message("assistant", answer, "DeepSeek + RAG", sources, thinking_process)
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "model": "DeepSeek + RAG",
                "sources": sources,
                "thinking_process": thinking_process
            })
        else:
            error_msg = result.get("error", "未知错误")
            display_message("assistant", f"抱歉，我遇到了一些问题: {error_msg}", "Error")
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"抱歉，我遇到了一些问题: {error_msg}",
                "model": "Error",
                "sources": []
            })
        
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ 处理消息时出错: {str(e)}")
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"抱歉，我遇到了一些问题: {str(e)}",
            "model": "Error",
            "sources": []
        })
        st.rerun()


def handle_direct_query(prompt: str) -> None:
    """处理直接查询（不使用 RAG）"""
    agent = get_agent_instance()
    
    if agent is None:
        st.error("❌ Agent 初始化失败，请检查配置")
        return
    
    selected_model = st.session_state.get("modelSelector", "auto")
    
    try:
        config = {
            "configurable": {
                "thread_id": st.session_state.session_id,
                "model": selected_model
            }
        }
        
        full_response = ""
        thinking_process = ""
        
        message_placeholder = st.empty()
        
        for chunk, metadata in agent.stream(
            {"messages": [("user", prompt)]},
            config,
            stream_mode="messages"
        ):
            reasoning = extract_thinking_from_chunk(chunk)
            if reasoning:
                thinking_process += reasoning
            
            if hasattr(chunk, 'content') and chunk.content:
                if isinstance(chunk.content, str):
                    full_response += chunk.content
                elif isinstance(chunk.content, list):
                    for item in chunk.content:
                        if isinstance(item, dict) and item.get('text'):
                            full_response += item['text']
            
            message_placeholder.markdown(f"""
            <div class="message-container message-assistant">
                <div class="avatar avatar-assistant">🤖</div>
                <div class="message-bubble">{full_response}</div>
            </div>
            """, unsafe_allow_html=True)
        
        model_display = "Qwen3/DeepSeek (自动选择)"
        if "qwen" in selected_model.lower():
            model_display = "Qwen3"
        elif selected_model == "deepseek-v3":
            model_display = "DeepSeek"
        
        st.session_state.messages.append({
            "role": "assistant",
            "content": full_response,
            "model": model_display,
            "sources": [],
            "thinking_process": thinking_process
        })
        
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ 处理消息时出错: {str(e)}")
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"抱歉，我遇到了一些问题: {str(e)}",
            "model": "Error",
            "sources": []
        })
        st.rerun()


def main() -> None:
    """主函数"""
    # 页面配置
    st.set_page_config(
        page_title="Hybrid-Agent",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 初始化 session state
    init_session_state()
    
    # 应用主题样式
    st.markdown(get_theme_css(), unsafe_allow_html=True)
    
    # 渲染侧边栏
    render_sidebar()
    
    # 主内容区域
    st.markdown('<div style="padding: 20px;"></div>', unsafe_allow_html=True)
    
    # 显示欢迎页面或消息历史
    if not st.session_state.messages:
        display_welcome()
    
    # 显示消息历史
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.messages:
            model_used = msg.get("model")
            sources = msg.get("sources", [])
            thinking_process = msg.get("thinking_process", "")
            display_message(msg["role"], msg["content"], model_used, sources, thinking_process)
    
    # 处理用户输入
    if prompt := st.chat_input(placeholder="输入消息，按回车键发送...", key="chatInput"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        display_message("user", prompt)
        
        use_rag = st.session_state.get("use_rag", True)
        
        if use_rag:
            handle_rag_query(prompt)
        else:
            handle_direct_query(prompt)


if __name__ == "__main__":
    main()
