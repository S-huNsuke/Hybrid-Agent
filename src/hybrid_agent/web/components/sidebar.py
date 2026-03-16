"""侧边栏组件"""

import streamlit as st

from hybrid_agent.core.rag_system import get_rag_system


def _get_file_uploader_css() -> str:
    """获取文件上传器自定义CSS"""
    return """
    <style>
    div[data-testid="stFileUploader"] button[data-testid="stBaseButton-secondary"] {
        position: relative;
    }
    div[data-testid="stFileUploader"] button[data-testid="stBaseButton-secondary"] span,
    div[data-testid="stFileUploader"] button[data-testid="stBaseButton-secondary"] p {
        display: none !important;
    }
    div[data-testid="stFileUploader"] button[data-testid="stBaseButton-secondary"]::after {
        content: "📁 选择文件";
        font-size: 14px !important;
    }
    </style>
    """


def _init_delete_state() -> None:
    """初始化删除确认状态"""
    if "pending_delete_doc" not in st.session_state:
        st.session_state.pending_delete_doc = None


def _render_custom_file_uploader() -> None:
    """渲染中文文件上传器"""
    uploaded_files = st.file_uploader(
        label=" ",
        type=['pdf', 'docx', 'txt', 'md'],
        accept_multiple_files=True,
        key="fileUploader"
    )
    return uploaded_files


def render_sidebar() -> dict:
    """渲染侧边栏"""
    st.markdown(_get_file_uploader_css(), unsafe_allow_html=True)
    _init_delete_state()
    
    with st.sidebar:
        st.markdown('<div class="sidebar-title">📚 知识库管理</div>', unsafe_allow_html=True)
        
        # 文件上传
        uploaded_files = _render_custom_file_uploader()
        
        if uploaded_files:
            _handle_file_upload(uploaded_files)
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        # 统计信息
        try:
            rag_system = get_rag_system()
            stats = rag_system.get_stats()
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"""
                <div class="stats-card">
                    <div class="stats-number">{stats.get('total_documents', 0)}</div>
                    <div class="stats-label">文档数</div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                <div class="stats-card">
                    <div class="stats-number">{stats.get('total_chunks', 0)}</div>
                    <div class="stats-label">文本块</div>
                </div>
                """, unsafe_allow_html=True)
        except (KeyError, AttributeError) as e:
            st.warning(f"加载统计信息失败: 数据格式错误")
        except Exception as e:
            st.warning(f"加载统计信息失败: {str(e)}")
        
        # 文档列表
        st.markdown("### 📋 知识库文档")
        documents = st.session_state.get("documents", [])
        if documents:
            for doc in documents:
                c1, c2 = st.columns([5, 1])
                with c1:
                    st.write(f"📄 {doc.get('filename', '未命名')}")
                with c2:
                    if st.button("🗑️ 删除", key=f"del_{doc.get('id')}", help="删除此文档"):
                        st.session_state.pending_delete_doc = {
                            "id": doc.get('id'),
                            "filename": doc.get('filename', '文档')
                        }
                        st.rerun()
                st.divider()
        else:
            st.info("💡 知识库为空，上传文件后可基于文档问答")
        
        # 删除确认对话框
        _render_delete_confirmation()
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        # 设置
        st.markdown("### ⚙️ 设置")
        
        use_rag = st.toggle(
            "启用 RAG 知识库问答",
            value=st.session_state.get("use_rag", True),
            key="ragToggle"
        )
        st.session_state.use_rag = use_rag
        
        if use_rag:
            st.info("💡 已启用知识库，AI 将优先基于上传的文档回答")
        else:
            st.info("💡 已关闭知识库，使用普通对话模式")
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        # 模型选择
        model_options = ["auto", "qwen3-omni", "deepseek-v3"]
        st.selectbox(
            "选择模型",
            options=model_options,
            index=0,
            format_func=lambda x: {
                "auto": "🤖 自动选择 (推荐)",
                "qwen3-omni": "⚡ Qwen3 基础模型",
                "deepseek-v3": "🧠 DeepSeek 增强模型"
            }.get(x, x),
            key="modelSelector"
        )
        
        # 重置和主题切换
        if st.button("🔄 清空对话记录", use_container_width=True):
            st.session_state.messages = []
            st.session_state.chat_history = []
            st.session_state.agent = None
            st.rerun()
        
        theme = st.session_state.get("theme", "light")
        theme_label = "亮色模式" if theme == "dark" else "暗色模式"
        theme_icon = "☀️" if theme == "dark" else "🌙"
        if st.button(f"{theme_icon} 切换到{theme_label}", key="theme_toggle_btn", use_container_width=True):
            new_theme = "light" if theme == "dark" else "dark"
            st.session_state.theme = new_theme
            st.rerun()
        
        return {}


def _render_delete_confirmation() -> None:
    """渲染删除确认对话框"""
    pending = st.session_state.get("pending_delete_doc")
    
    if pending:
        st.warning(f"⚠️ 确定要删除文档 **{pending['filename']}** 吗？此操作不可撤销。")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ 确认删除", key="confirm_delete_btn", use_container_width=True):
                _handle_delete_document(pending["id"], pending["filename"])
                st.session_state.pending_delete_doc = None
                st.rerun()
        with col2:
            if st.button("❌ 取消", key="cancel_delete_btn", use_container_width=True):
                st.session_state.pending_delete_doc = None
                st.rerun()


def _handle_file_upload(uploaded_files) -> None:
    """处理文件上传"""
    if not uploaded_files:
        return
    
    if "processed_files" not in st.session_state:
        st.session_state.processed_files = set()
    
    rag_system = get_rag_system()
    new_files_processed = False
    
    for uploaded_file in uploaded_files:
        file_id = f"{uploaded_file.name}_{uploaded_file.size}"
        
        if file_id not in st.session_state.processed_files:
            try:
                file_content = uploaded_file.read()
                result = rag_system.add_document(file_content, uploaded_file.name)
                
                if result.get("success"):
                    st.success(f"✅ {result.get('message', '文档上传成功')}")
                    st.session_state.processed_files.add(file_id)
                    new_files_processed = True
                else:
                    st.error(f"❌ 上传失败: {result.get('error', '未知错误')}")
            except (KeyError, IOError) as e:
                st.error(f"❌ 处理文件 {uploaded_file.name} 时出错: 文件操作错误")
            except Exception as e:
                st.error(f"❌ 处理文件 {uploaded_file.name} 时出错: {str(e)}")
    
    if new_files_processed:
        stats = rag_system.get_stats()
        st.session_state.documents = stats.get("documents", [])
        st.session_state.fileUploader = None
        st.rerun()


def _handle_delete_document(doc_id: str, filename: str) -> None:
    """处理文档删除"""
    rag_system = get_rag_system()
    result = rag_system.delete_document(doc_id)
    
    if result.get("success"):
        st.success(f"✅ 已删除文档: {filename}")
    else:
        st.error(f"❌ 删除失败: {result.get('error', '未知错误')}")
    
    stats = rag_system.get_stats()
    st.session_state.documents = stats.get("documents", [])
    st.rerun()
