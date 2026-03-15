import sys
import uuid
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from rag_app.agent.builder import build_agent
from rag_app.core.rag_system import get_rag_system
from rag_frontend.utils.helpers import sanitize_user_content

st.set_page_config(
    page_title="Hybrid-Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

COLORS = {
    "bg_primary": "#FFFBF7",
    "bg_secondary": "#FFF5E6",
    "bg_sidebar": "#FFFFFF",
    "accent_primary": "#FF6B35",
    "accent_secondary": "#FF8C42",
    "text_primary": "#1A1A1A",
    "text_secondary": "#6B7280",
    "text_placeholder": "#9CA3AF",
    "border": "#E5E7EB",
    "shadow": "rgba(0, 0, 0, 0.08)"
}

DARK_COLORS = {
    "bg_primary": "#0D1117",
    "bg_secondary": "#161B22",
    "bg_sidebar": "#0D1117",
    "accent_primary": "#FF6B35",
    "accent_secondary": "#FF8C42",
    "text_primary": "#E6EDF3",
    "text_secondary": "#8B949E",
    "text_placeholder": "#6E7681",
    "border": "#30363D",
    "shadow": "rgba(0, 0, 0, 0.4)"
}


def get_theme_colors():
    theme = st.session_state.get("theme", "light")
    if theme == "dark":
        return DARK_COLORS
    return COLORS

def get_theme_css():
    colors = get_theme_colors()
    return f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');
    
    :root {{
        --bg-primary: {colors['bg_primary']};
        --bg-secondary: {colors['bg_secondary']};
        --bg-sidebar: {colors['bg_sidebar']};
        --accent-primary: {colors['accent_primary']};
        --accent-secondary: {colors['accent_secondary']};
        --text-primary: {colors['text_primary']};
        --text-secondary: {colors['text_secondary']};
        --text-placeholder: {colors['text_placeholder']};
        --border-color: {colors['border']};
        --shadow: {colors['shadow']};
    }}
    
    * {{
        font-family: "Noto Sans SC", "PingFang SC", -apple-system, BlinkMacSystemFont, sans-serif !important;
    }}
    
    #MainMenu, footer {{
        visibility: hidden;
    }}
    
    .material-icons {{
        font-family: 'Material Symbols Outlined' !important;
        font-weight: normal !important;
        font-style: normal !important;
        font-size: 24px !important;
        line-height: 1 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        white-space: nowrap !important;
        word-wrap: normal !important;
        direction: ltr !important;
        -webkit-font-smoothing: antialiased !important;
        text-rendering: optimizeLegibility !important;
        -moz-osx-font-smoothing: grayscale !important;
    }}
    
    [data-testid="collapsedControl"] {{
        visibility: visible !important;
        display: flex !important;
        position: fixed !important;
        top: 10px !important;
        left: 10px !important;
        z-index: 9999 !important;
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
        width: 44px !important;
        height: 44px !important;
    }}
    
    [data-testid="collapsedControl"]:hover {{
        background: transparent !important;
    }}
    
    [data-testid="collapsedControl"] button {{
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
        width: 44px !important;
        height: 44px !important;
        min-width: auto !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }}
    
    [data-testid="collapsedControl"] button:hover {{
        background: {colors['bg_secondary']} !important;
    }}
    
    [data-testid="collapsedControl"] button * {{
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-family: 'Material Symbols Outlined' !important;
        color: {colors['accent_primary']} !important;
    }}
    
    [data-testid="stIconMaterial"] {{
        font-family: 'Material Symbols Outlined' !important;
        font-size: 24px !important;
        color: {colors['accent_primary']} !important;
    }}
    
    [data-testid="stHeader"] button {{
        background: transparent !important;
        border: none !important;
    }}
    
    [data-testid="stHeader"] button span {{
        color: {colors['accent_primary']} !important;
    }}
    
    [data-testid="stSidebarHeader"] {{
        display: flex !important;
        justify-content: flex-end !important;
        padding: 8px !important;
        align-items: center !important;
        height: auto !important;
    }}
    
    [data-testid="stSidebarCollapseButton"] {{
        display: flex !important;
    }}
    
    [data-testid="stSidebarCollapseButton"] button {{
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
        width: 44px !important;
        height: 44px !important;
        min-width: auto !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }}
    
    [data-testid="stSidebarCollapseButton"] button:hover {{
        background: {colors['bg_secondary']} !important;
    }}
    
    [data-testid="stSidebar"] {{
        background: {colors['bg_sidebar']};
        box-shadow: 2px 0 8px {colors['shadow']};
    }}
    
    [data-testid="stSidebar"] * {{
        color: {colors['text_primary']} !important;
    }}
    
    .sidebar-title {{
        font-size: 20px;
        font-weight: 600;
        color: {colors['accent_primary']};
        padding: 16px;
        border-bottom: 1px solid {colors['border']};
        margin-bottom: 16px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }}
    
    .theme-toggle {{
        cursor: pointer;
        font-size: 20px;
        padding: 8px;
        border-radius: 8px;
        transition: background 0.2s ease;
        display: flex;
        align-items: center;
        justify-content: center;
    }}
    
    .theme-toggle:hover {{
        background: {colors['bg_secondary']};
    }}
    
    [data-testid="stFileUploaderDropzone"] {{
        background: linear-gradient(135deg, {colors['bg_secondary']} 0%, {colors['bg_primary']} 100%) !important;
        border: 2px dashed {colors['accent_primary']} !important;
        border-radius: 16px !important;
        padding: 32px 24px !important;
        transition: all 0.3s ease !important;
        position: relative !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        min-height: 160px !important;
    }}
    
    [data-testid="stFileUploaderDropzone"]:hover {{
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(255, 107, 53, 0.2) !important;
        border-color: {colors['accent_secondary']} !important;
    }}
    
    [data-testid="stFileUploaderDropzoneInstructions"] {{
        text-align: center !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        gap: 12px !important;
    }}
    
    section[data-testid="stFileUploader"] > div {{
        padding: 0 !important;
    }}
    
    section[data-testid="stFileUploader"] label {{
        display: none !important;
    }}
    
    [data-testid="stFileUploaderDropzoneInstructions"] * {{
        font-size: 0 !important;
    }}
    
    [data-testid="stFileUploaderDropzoneInstructions"]::before {{
        content: "📁" !important;
        display: block !important;
        font-size: 40px !important;
        margin-bottom: 8px !important;
    }}
    
    [data-testid="stFileUploaderDropzone"]::before {{
        content: "拖放文件到此处上传" !important;
        display: block !important;
        font-size: 15px !important;
        color: {colors['text_primary']} !important;
        font-weight: 600 !important;
        margin-bottom: 8px !important;
        text-align: center !important;
    }}
    
    [data-testid="stFileUploaderDropzone"]::after {{
        content: "支持 PDF、DOCX、TXT、Markdown 格式" !important;
        display: block !important;
        font-size: 12px !important;
        color: {colors['text_secondary']} !important;
        margin-top: 12px !important;
        text-align: center !important;
    }}
    
    [data-testid="stFileUploaderDropzone"] button {{
        background: linear-gradient(135deg, {colors['accent_primary']} 0%, {colors['accent_secondary']} 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 10px 20px !important;
        font-weight: 500 !important;
        font-size: 0 !important;
        margin-top: 8px !important;
    }}
    
    [data-testid="stFileUploaderDropzone"] button::before {{
        content: "浏览文件" !important;
        font-size: 14px !important;
    }}
    
    [data-testid="stFileUploaderDropzone"] button:hover {{
        transform: scale(1.02) !important;
        box-shadow: 0 4px 12px rgba(255, 107, 53, 0.3) !important;
    }}
    
    .doc-item {{
        background: {colors['bg_primary']};
        border: 1px solid {colors['border']};
        border-radius: 12px;
        padding: 12px;
        margin: 8px 0;
        display: flex;
        align-items: center;
        justify-content: space-between;
        transition: all 0.2s ease;
    }}
    
    .doc-item:hover {{
        border-color: {colors['accent_primary']};
        box-shadow: 0 2px 8px rgba(255, 107, 53, 0.1);
    }}
    
    .doc-info {{
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    
    .doc-icon {{
        font-size: 20px;
    }}
    
    .doc-name {{
        font-size: 13px;
        color: {colors['text_primary']};
        font-weight: 500;
    }}
    
    .stButton > button {{
        border-radius: 12px;
        transition: all 0.3s ease;
        background: linear-gradient(135deg, {colors['accent_primary']} 0%, {colors['accent_secondary']} 100%);
        color: white;
        border: none;
    }}
    
    .stButton > button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(255, 107, 53, 0.3);
    }}
    
    .message-container {{
        display: flex;
        gap: 12px;
        margin: 16px 0;
    }}
    
    .message-user {{
        flex-direction: row-reverse;
    }}
    
    .avatar {{
        width: 40px;
        height: 40px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        flex-shrink: 0;
    }}
    
    .avatar-user {{
        background: linear-gradient(135deg, {colors['accent_primary']} 0%, {colors['accent_secondary']} 100%);
    }}
    
    .avatar-assistant {{
        background: {colors['bg_secondary']};
        border: 1px solid {colors['border']};
    }}
    
    .message-bubble {{
        max-width: 70%;
        padding: 14px 18px;
        border-radius: 16px;
        font-size: 14px;
        line-height: 1.6;
        white-space: pre-wrap;
        word-wrap: break-word;
    }}
    
    .message-user .message-bubble {{
        background: linear-gradient(135deg, {colors['accent_primary']} 0%, {colors['accent_secondary']} 100%);
        color: white;
        border-bottom-right-radius: 4px;
    }}
    
    .message-assistant .message-bubble {{
        background: {colors['bg_sidebar']};
        color: {colors['text_primary']};
        border: 1px solid {colors['border']};
        border-bottom-left-radius: 4px;
    }}
    
    [data-testid="stChatInput"] {{
        background: {colors['bg_primary']};
        border-radius: 24px;
        border: 1px solid {colors['border']};
        padding: 4px;
    }}
    
    [data-testid="stChatInput"] > div {{
        background: transparent !important;
        border: none !important;
    }}
    
    [data-testid="stChatInput"] input {{
        color: {colors['text_primary']} !important;
        padding: 12px 16px !important;
    }}
    
    [data-testid="stChatInput"] input::placeholder {{
        color: {colors['text_placeholder']} !important;
    }}
    
    .welcome-header {{
        text-align: center;
        padding: 60px 20px;
    }}
    
    .welcome-title {{
        font-size: 32px;
        font-weight: 700;
        color: {colors['text_primary']};
        margin-bottom: 12px;
    }}
    
    .welcome-subtitle {{
        font-size: 16px;
        color: {colors['text_secondary']};
    }}
    
    .mode-badge {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: {colors['bg_secondary']};
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 13px;
        color: {colors['accent_primary']};
        margin-top: 16px;
    }}
    
    .divider {{
        height: 1px;
        background: {colors['border']};
        margin: 16px 0;
    }}
    
    .stSelectbox div[data-baseweb="select"] {{
        border-radius: 12px;
    }}
    
    [data-testid="stToast"] {{
        border-radius: 12px;
    }}
    
    .thinking-indicator {{
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 12px;
        color: {colors['text_secondary']};
        font-size: 13px;
    }}
    
    .thinking-dots span {{
        display: inline-block;
        width: 6px;
        height: 6px;
        background: {colors['accent_primary']};
        border-radius: 50%;
        animation: bounce 1.4s infinite ease-in-out both;
    }}
    
    .thinking-dots span:nth-child(1) {{ animation-delay: -0.32s; }}
    .thinking-dots span:nth-child(2) {{ animation-delay: -0.16s; }}
    
    @keyframes bounce {{
        0%, 80%, 100% {{ transform: scale(0); }}
        40% {{ transform: scale(1); }}
    }}
    
    .model-badge {{
        display: inline-block;
        background: linear-gradient(135deg, {colors['accent_primary']} 0%, {colors['accent_secondary']} 100%);
        color: white;
        font-size: 10px;
        padding: 2px 8px;
        border-radius: 10px;
        margin-bottom: 6px;
        font-weight: 500;
    }}
    
    .streaming-cursor {{
        display: inline-block;
        width: 2px;
        height: 16px;
        background: {colors['accent_primary']};
        animation: blink 1s infinite;
    }}
    
    @keyframes blink {{
        0%, 50% {{ opacity: 1; }}
        51%, 100% {{ opacity: 0; }}
    }}
    
    .stSuccess, .stError, .stInfo, .stWarning {{
        border-radius: 12px;
    }}
    
    .source-item {{
        background: {colors['bg_secondary']};
        border-left: 3px solid {colors['accent_primary']};
        padding: 10px 14px;
        margin: 8px 0;
        border-radius: 0 8px 8px 0;
        font-size: 12px;
    }}
    
    .source-filename {{
        font-weight: 600;
        color: {colors['accent_primary']};
        margin-bottom: 4px;
    }}
    
    .source-content {{
        color: {colors['text_secondary']};
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
    }}
    
    .rag-toggle {{
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 12px;
        background: {colors['bg_secondary']};
        border-radius: 12px;
        margin: 12px 0;
    }}
    
    .stats-card {{
        background: linear-gradient(135deg, {colors['bg_secondary']} 0%, {colors['bg_primary']} 100%);
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
    }}
    
    .stats-number {{
        font-size: 24px;
        font-weight: 700;
        color: {colors['accent_primary']};
    }}
    
    .stats-label {{
        font-size: 12px;
        color: {colors['text_secondary']};
    }}
    
    .delete-btn {{
        background: #ff4757 !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 4px 12px !important;
        font-size: 12px !important;
    }}
    
    .thinking-panel {{
        background: linear-gradient(135deg, {colors['bg_secondary']} 0%, {colors['bg_primary']} 100%);
        border: 1px solid {colors['border']};
        border-radius: 12px;
        padding: 12px 16px;
        margin: 8px 0;
        font-size: 13px;
        color: {colors['text_primary']};
    }}
    
    .thinking-panel-header {{
        display: flex;
        align-items: center;
        gap: 8px;
        cursor: pointer;
        font-weight: 600;
        color: {colors['text_primary']};
    }}
    
    .thinking-panel-content {{
        margin-top: 10px;
        padding-top: 10px;
        border-top: 1px solid {colors['border']};
        white-space: pre-wrap;
        line-height: 1.6;
        font-family: 'Courier New', monospace;
        color: {colors['text_secondary']};
    }}
    
    .tool-approval-panel {{
        background: linear-gradient(135deg, {colors['bg_secondary']} 0%, {colors['bg_primary']} 100%);
        border: 2px dashed {colors['accent_primary']};
        border-radius: 12px;
        padding: 16px;
        margin: 12px 0;
    }}
    
    .tool-approval-title {{
        font-weight: 600;
        color: {colors['accent_primary']};
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    
    .tool-approval-info {{
        background: {colors['bg_primary']};
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 12px;
        font-size: 13px;
        color: {colors['text_primary']};
    }}
    
    .tool-approval-buttons {{
        display: flex;
        gap: 12px;
    }}
    
    .tool-approval-buttons button {{
        flex: 1;
        padding: 10px 16px;
        border-radius: 8px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
    }}
    
    .tool-approve-btn {{
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        border: none;
    }}
    
    .tool-reject-btn {{
        background: {colors['bg_primary']};
        color: #ef4444;
        border: 2px solid #ef4444;
    }}
    
    [data-testid="stMain"] {{
        background: {colors['bg_primary']};
    }}
    
    .stApp {{
        background: {colors['bg_primary']};
    }}
    
    [data-testid="stSidebar"] {{
        background-color: {colors['bg_sidebar']} !important;
    }}
    
    section[data-testid="stSidebar"] {{
        background-color: {colors['bg_sidebar']} !important;
    }}
    
    .stSidebarContent {{
        background-color: {colors['bg_sidebar']} !important;
    }}
    
    [data-testid="stChatInput"] textarea {{
        background-color: {colors['bg_primary']} !important;
        color: {colors['text_primary']} !important;
        border-color: {colors['border']} !important;
    }}
    
    [data-testid="stChatInput"] {{
        background-color: {colors['bg_primary']} !important;
        border-color: {colors['border']} !important;
    }}
    
    .stChatInputInput {{
        background-color: {colors['bg_primary']} !important;
        color: {colors['text_primary']} !important;
    }}
    
    [data-testid="stBaseButton-secondary"] {{
        background-color: {colors['bg_secondary']} !important;
        color: {colors['text_primary']} !important;
        border-color: {colors['border']} !important;
    }}
    
    div[data-baseweb="select"] > div {{
        background-color: {colors['bg_primary']} !important;
        color: {colors['text_primary']} !important;
        border-color: {colors['border']} !important;
    }}
    
    [data-testid="stSelectbox"] * {{
        background-color: {colors['bg_primary']} !important;
        color: {colors['text_primary']} !important;
    }}
    
    input[type="text"] {{
        background-color: {colors['bg_primary']} !important;
        color: {colors['text_primary']} !important;
        border-color: {colors['border']} !important;
    }}
    
    .stTextInput > div > div {{
        background-color: {colors['bg_primary']} !important;
        border-color: {colors['border']} !important;
    }}
    
    .stTextInput input {{
        background-color: {colors['bg_primary']} !important;
        color: {colors['text_primary']} !important;
    }}
    
    .stMultiSelect {{
        background-color: {colors['bg_primary']} !important;
    }}
    
    div[data-baseweb="tag"] {{
        background-color: {colors['bg_secondary']} !important;
    }}
    
    [data-testid="stFileUploader"] {{
        background-color: {colors['bg_secondary']} !important;
    }}
    
    [data-testid="stToast"] {{
        background-color: {colors['bg_primary']} !important;
        color: {colors['text_primary']} !important;
    }}
    
    .stSuccess {{
        background-color: {colors['bg_secondary']} !important;
        color: {colors['text_primary']} !important;
    }}
    
    .stError {{
        background-color: #fee2e2 !important;
        color: #991b1b !important;
    }}
    
    .stInfo {{
        background-color: {colors['bg_secondary']} !important;
        color: {colors['text_primary']} !important;
    }}
    
    .stWarning {{
        background-color: #fef3c7 !important;
        color: #92400e !important;
    }}
    
    .stMarkdown {{
        color: {colors['text_primary']} !important;
    }}
    
    p {{
        color: {colors['text_primary']} !important;
    }}
    
    span {{
        color: {colors['text_primary']} !important;
    }}
    
    label {{
        color: {colors['text_primary']} !important;
    }}
    
    .stMarkdown p {{
        color: {colors['text_primary']} !important;
    }}
    
    h1, h2, h3, h4, h5, h6 {{
        color: {colors['text_primary']} !important;
    }}
    
    .stDivider {{
        background-color: {colors['border']} !important;
    }}
    
    hr {{
        border-color: {colors['border']} !important;
    }}
    
    [data-testid="stMetric"], .stMetric {{
        background-color: {colors['bg_secondary']} !important;
    }}
    
    [data-testid="stMetricLabel"], .stMetricLabel {{
        color: {colors['text_secondary']} !important;
    }}
    
    [data-testid="stMetricValue"], .stMetricValue {{
        color: {colors['text_primary']} !important;
    }}
    
    div[data-baseweb="textarea"] {{
        background-color: {colors['bg_primary']} !important;
        color: {colors['text_primary']} !important;
    }}
    
    div[data-baseweb="base-input"] {{
        background-color: {colors['bg_primary']} !important;
    }}
    
    textarea {{
        background-color: {colors['bg_primary']} !important;
        color: {colors['text_primary']} !important;
    }}
    
    .stChatInput {{
        background-color: {colors['bg_primary']} !important;
        border-color: {colors['border']} !important;
    }}
    
    .stChatInput > div {{
        background-color: {colors['bg_primary']} !important;
    }}
    
    div[class*="stChatInput"] {{
        background-color: {colors['bg_primary']} !important;
    }}
    
    [data-testid="stBottomBlockContainer"] {{
        background-color: {colors['bg_primary']} !important;
    }}
    
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: {colors['bg_primary']} !important;
    }}
    
    .stElementContainer {{
        background-color: {colors['bg_primary']} !important;
    }}
    
    html, body, .stApp, [data-testid="stApp"] {{
        background-color: {colors['bg_primary']} !important;
    }}
    
    .stApp > div:first-child {{
        background-color: {colors['bg_primary']} !important;
    }}
    
    div[role="main"] {{
        background-color: {colors['bg_primary']} !important;
    }}
    
    [data-testid="stChatInputTextArea"] {{
        background-color: {colors['bg_primary']} !important;
        color: {colors['text_primary']} !important;
    }}
    
    [data-testid="stChatInputTextArea"]::placeholder {{
        color: {colors['text_placeholder']} !important;
    }}
    
    textarea[data-testid="stChatInputTextArea"] {{
        background-color: {colors['bg_primary']} !important;
        color: {colors['text_primary']} !important;
    }}
    
    [data-testid="stChatInputSubmitButton"] {{
        background-color: {colors['accent_primary']} !important;
        color: white !important;
    }}
    
    [data-testid="stChatInputSubmitButton"]:disabled {{
        background-color: {colors['border']} !important;
        color: {colors['text_secondary']} !important;
    }}
    
    [data-testid="stToolbar"] {{
        background-color: {colors['bg_primary']} !important;
    }}
    
    .stAppToolbar {{
        background-color: {colors['bg_primary']} !important;
    }}
    
    header[data-testid="stHeader"] {{
        background-color: {colors['bg_primary']} !important;
    }}
    
    [data-testid="stBaseButton-secondary"]:hover {{
        background-color: {colors['bg_secondary']} !important;
    }}
    
    button[data-testid="stBaseButton-secondary"]:hover {{
        background-color: {colors['bg_secondary']} !important;
    }}
</style>
"""


def display_message(role: str, content: str, model_used: str = None, sources: list = None, thinking_process: str = None) -> None:
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
        for i, source in enumerate(sources[:3]):
            filename = sanitize_user_content(source.get('filename', '未知文件'))
            content_preview = sanitize_user_content(source.get('content', '')[:150])
            st.markdown(f"""
            <div class="source-item">
                <div class="source-filename">📄 {filename}</div>
                <div class="source-content">{content_preview}...</div>
            </div>
            """, unsafe_allow_html=True)


def display_welcome() -> None:
    theme = st.session_state.get("theme", "light")
    theme_status = "🌙 暗色模式" if theme == "dark" else "☀️ 亮色模式"
    use_rag = st.session_state.get("use_rag", True)
    rag_status = "📚 RAG + 智能模式" if use_rag else "💬 普通对话模式"
    
    st.markdown(f"""
    <div class="welcome-header">
        <div style="font-size: 48px; margin-bottom: 20px;">🤖</div>
        <h1 class="welcome-title">欢迎来到 Hybrid-Agent</h1>
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


def init_session_state() -> None:
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
    
    # 每次都尝试加载文档列表
    try:
        rag_system = get_rag_system()
        stats = rag_system.get_stats()
        st.session_state.documents = stats.get("documents", [])
    except Exception as e:
        print(f"加载 RAG 系统失败: {e}")


def get_agent():
    if st.session_state.agent is None:
        try:
            from rag_app.agent.builder import build_agent
            st.session_state.agent = build_agent(enable_tools=True, enable_approval=True)
        except Exception as e:
            st.error(f"❌ 初始化 Agent 失败: {str(e)}")
            return None
    return st.session_state.agent


def get_tools():
    from rag_app.agent.builder import get_tools as _get_tools
    return _get_tools()


def display_tool_approval(tool_call: dict) -> None:
    tool_name = tool_call.get("name", "未知工具")
    tool_args = tool_call.get("args", {})
    
    tool_descriptions = {
        "web_search": "🔍 网页搜索",
        "search_documents": "📚 搜索知识库",
        "list_documents": "📋 列出文档",
        "document_delete": "🗑️ 删除文档"
    }
    
    tool_icon = tool_descriptions.get(tool_name, "🔧 工具")
    
    args_str = ", ".join([f"{k}: {v}" for k, v in tool_args.items()])
    
    st.markdown(f"""
    <div class="tool-approval-panel">
        <div class="tool-approval-title">
            <span>⚠️</span>
            <span>工具调用请求</span>
        </div>
        <div class="tool-approval-info">
            <strong>{tool_icon}</strong><br>
            <span style="color: #666;">参数: {args_str or '无'}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("✅ 确认执行", key="approve_tool", use_container_width=True):
            st.session_state.pending_tool_call = {
                "approved": True,
                "tool_call": tool_call
            }
            st.rerun()
    with col2:
        if st.button("❌ 拒绝", key="reject_tool", use_container_width=True):
            st.session_state.pending_tool_call = {
                "approved": False,
                "tool_call": tool_call
            }
            st.rerun()


def extract_thinking_from_chunk(chunk) -> str:
    thinking = ""
    if hasattr(chunk, 'additional_kwargs'):
        kwargs = chunk.additional_kwargs
        if isinstance(kwargs, dict):
            reasoning = kwargs.get('reasoning_content', '')
            if reasoning:
                thinking = reasoning
    return thinking


def handle_file_upload(uploaded_files) -> None:
    if not uploaded_files:
        return
    
    # 初始化已处理文件集合
    if "processed_files" not in st.session_state:
        st.session_state.processed_files = set()
    
    rag_system = get_rag_system()
    new_files_processed = False
    
    for uploaded_file in uploaded_files:
        # 使用文件名+大小作为唯一标识
        file_id = f"{uploaded_file.name}_{uploaded_file.size}"
        
        # 只处理新文件
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
            except Exception as e:
                st.error(f"❌ 处理文件 {uploaded_file.name} 时出错: {str(e)}")
    
    if new_files_processed:
        stats = rag_system.get_stats()
        st.session_state.documents = stats.get("documents", [])
        # 清空文件上传器
        st.session_state.fileUploader = []
        st.rerun()


def handle_delete_document(doc_id: str, filename: str) -> None:
    rag_system = get_rag_system()
    result = rag_system.delete_document(doc_id)
    
    if result.get("success"):
        st.success(f"✅ 已删除文档: {filename}")
    else:
        st.error(f"❌ 删除失败: {result.get('error', '未知错误')}")
    
    stats = rag_system.get_stats()
    st.session_state.documents = stats.get("documents", [])
    st.rerun()


def render_sidebar() -> dict:
    with st.sidebar:
        colors = get_theme_colors()
        theme = st.session_state.get("theme", "light")
        theme_icon = "☀️" if theme == "dark" else "🌙"
        theme_label = "亮色模式" if theme == "dark" else "暗色模式"
        
        st.markdown('<div class="sidebar-title">📚 知识库管理</div>', unsafe_allow_html=True)
        
        uploaded_files = st.file_uploader(
            label="上传文件",
            type=['pdf', 'docx', 'txt', 'md'],
            accept_multiple_files=True,
            key="fileUploader",
            label_visibility="collapsed"
        )
        
        if uploaded_files:
            handle_file_upload(uploaded_files)
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
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
        except Exception as e:
            st.warning(f"加载统计信息失败: {str(e)}")
        
        st.markdown("### 📋 知识库文档")
        
        documents = st.session_state.documents
        if documents:
            for doc in documents:
                c1, c2 = st.columns([5, 1])
                with c1:
                    st.write(f"📄 {doc.get('filename', '未命名')}")
                with c2:
                    if st.button("删除", key=f"del_{doc.get('id')}", help="删除此文档"):
                        handle_delete_document(doc.get('id'), doc.get('filename', '文档'))
                st.divider()
        else:
            st.info("💡 知识库为空，上传文件后可基于文档问答")
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
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
        
        if st.button("🔄 重置对话", use_container_width=True):
            st.session_state.messages = []
            st.session_state.chat_history = []
            st.session_state.agent = None
            st.rerun()
        
        if st.button(f"🌓 切换到{theme_label}", key="theme_toggle_btn", use_container_width=True):
            new_theme = "light" if theme == "dark" else "dark"
            st.session_state.theme = new_theme
            st.rerun()
        
        return {}


def handle_pending_tool_approval() -> bool:
    """处理待审批的工具调用。返回 True 表示已处理，返回 False 表示没有待处理的工具调用。"""
    pending_tool = st.session_state.get("pending_tool_call")
    
    if not pending_tool:
        return False
    
    st.session_state.pending_tool_call = None
    
    agent = get_agent()
    if agent is None:
        st.error("❌ Agent 初始化失败，请检查配置")
        return True
    
    selected_model = st.session_state.get("modelSelector", "auto")
    
    if not pending_tool.get("approved"):
        st.session_state.messages.append({
            "role": "assistant",
            "content": "已拒绝工具执行，请告诉我您想如何修改问题。",
            "model": "System",
            "sources": []
        })
        st.rerun()
        return True
    
    tool_call = pending_tool.get("tool_call", {})
    tool_name = tool_call.get("name", "")
    tool_args = tool_call.get("args", {})
    tool_call_id = tool_call.get("id", "call_0")
    
    placeholder = st.empty()
    placeholder.markdown(f"""
    <div class="message-container message-assistant">
        <div class="avatar avatar-assistant">🤖</div>
        <div class="message-bubble">
            <div class="thinking-indicator">
                <span>⚙️ 正在执行工具: {tool_name}...</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    try:
        tool_result = None
        for tool in get_tools():
            if tool.name == tool_name:
                tool_result = tool.invoke(tool_args)
                break
        
        if tool_result is None:
            tool_result = f"工具 {tool_name} 未找到"
        
        config = {
            "configurable": {
                "thread_id": st.session_state.session_id,
                "model": selected_model
            }
        }
        
        full_response = ""
        thinking_process = ""
        
        messages_with_result = [
            HumanMessage(content=st.session_state.messages[-1]["content"] if st.session_state.messages else ""),
            AIMessage(content="", tool_calls=[tool_call]),
            ToolMessage(content=str(tool_result), tool_call_id=tool_call_id)
        ]
        
        for chunk, _ in agent.stream(
            {"messages": messages_with_result},
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
        
        model_display = "DeepSeek"
        if "qwen" in selected_model.lower():
            model_display = "Qwen3"
        elif selected_model == "auto":
            model_display = "Qwen3/DeepSeek (自动选择)"
        
        thinking_html = ""
        if thinking_process:
            thinking_html = f"""
            <div class="thinking-panel">
                <div class="thinking-panel-header" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
                    <span>🧠</span>
                    <span>思考过程 (点击展开/折叠)</span>
                </div>
                <div class="thinking-panel-content" style="display: none;">{thinking_process}</div>
            </div>
            """
        
        placeholder.markdown(f"""
        <div class="message-container message-assistant">
            <div class="avatar avatar-assistant">🤖</div>
            <div class="message-bubble">
                <span class="model-badge">{model_display}</span>
                {thinking_html}
                {full_response}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.session_state.messages.append({
            "role": "assistant",
            "content": full_response,
            "model": model_display,
            "sources": [],
            "thinking_process": thinking_process
        })
        
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ 工具执行失败: {str(e)}")
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"工具执行失败: {str(e)}",
            "model": "Error",
            "sources": []
        })
        st.rerun()
    
    return True


def main() -> None:
    init_session_state()
    
    st.markdown(get_theme_css(), unsafe_allow_html=True)
    
    # 先处理待审批的工具调用
    if handle_pending_tool_approval():
        return
    
    render_sidebar()
    
    st.markdown('<div style="padding: 20px;"></div>', unsafe_allow_html=True)
    
    if not st.session_state.messages:
        display_welcome()
    
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.messages:
            model_used = msg.get("model")
            sources = msg.get("sources", [])
            thinking_process = msg.get("thinking_process", "")
            display_message(msg["role"], msg["content"], model_used, sources, thinking_process)
    
    if prompt := st.chat_input(placeholder="输入消息，按 Enter 发送...", key="chatInput"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        display_message("user", prompt)
        
        use_rag = st.session_state.get("use_rag", True)
        
        if use_rag:
            handle_rag_query(prompt)
        else:
            handle_direct_query(prompt)


def handle_rag_query(prompt: str) -> None:
    rag_system = get_rag_system()
    selected_model = st.session_state.get("modelSelector", "auto")
    
    if selected_model == "auto":
        model_type = "advanced"
    elif selected_model == "deepseek-v3":
        model_type = "advanced"
    else:
        model_type = "base"
    
    placeholder = st.empty()
    placeholder.markdown(f"""
    <div class="message-container message-assistant">
        <div class="avatar avatar-assistant">🤖</div>
        <div class="message-bubble">
            <div class="thinking-indicator">
                <div class="thinking-dots">
                    <span></span><span></span><span></span>
                </div>
                <span>AI 正在检索知识库并生成回答...</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
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
            context_chunks = result.get("context_chunks", 0)
            thinking_process = result.get("thinking_process", "")
            
            thinking_html = ""
            if thinking_process:
                thinking_html = f"""
            <div class="thinking-panel">
                <div class="thinking-panel-header" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
                    <span>🧠</span>
                    <span>思考过程 (点击展开/折叠)</span>
                </div>
                <div class="thinking-panel-content" style="display: none;">{thinking_process}</div>
            </div>
                """
            
            placeholder.markdown(f"""
            <div class="message-container message-assistant">
                <div class="avatar avatar-assistant">🤖</div>
                <div class="message-bubble">
                    <span class="model-badge">DeepSeek + RAG</span>
                    {thinking_html}
                    {answer}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            for i, source in enumerate(sources[:3]):
                filename = source.get('filename', '未知文件')
                content_preview = source.get('content', '')[:150]
                st.markdown(f"""
                <div class="source-item">
                    <div class="source-filename">📄 {filename}</div>
                    <div class="source-content">{content_preview}...</div>
                </div>
                """, unsafe_allow_html=True)
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "model": "DeepSeek + RAG",
                "sources": sources,
                "thinking_process": thinking_process
            })
        else:
            error_msg = result.get("error", "未知错误")
            placeholder.markdown(f"""
            <div class="message-container message-assistant">
                <div class="avatar avatar-assistant">🤖</div>
                <div class="message-bubble">
                    <span class="model-badge" style="background: #ff4757;">错误</span>
                    {error_msg}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"抱歉，我遇到了一些问题: {error_msg}",
                "model": "Error",
                "sources": []
            })
        
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ 处理消息时出错: {str(e)}")
        
        error_msg = f"抱歉，我遇到了一些问题: {str(e)}"
        st.session_state.messages.append({
            "role": "assistant",
            "content": error_msg,
            "model": "Error",
            "sources": []
        })
        st.rerun()


def handle_direct_query(prompt: str) -> None:
    agent = get_agent()
    
    if agent is None:
        st.error("❌ Agent 初始化失败，请检查配置")
        return
    
    selected_model = st.session_state.get("modelSelector", "auto")
    
    placeholder = st.empty()
    placeholder.markdown(f"""
    <div class="message-container message-assistant">
        <div class="avatar avatar-assistant">🤖</div>
        <div class="message-bubble">
            <div class="thinking-indicator">
                <div class="thinking-dots">
                    <span></span><span></span><span></span>
                </div>
                <span>AI 正在思考...</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    try:
        config = {
            "configurable": {
                "thread_id": st.session_state.session_id,
                "model": selected_model
            }
        }
        
        full_response = ""
        thinking_process = ""
        
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
            
            thinking_html = ""
            if thinking_process:
                thinking_html = f"""
                <div class="thinking-panel">
                    <div class="thinking-panel-header" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
                        <span>🧠</span>
                        <span>思考过程 (点击展开/折叠)</span>
                    </div>
                    <div class="thinking-panel-content" style="display: none;">{thinking_process}</div>
                </div>
                """
            
            placeholder.markdown(f"""
            <div class="message-container message-assistant">
                <div class="avatar avatar-assistant">🤖</div>
                <div class="message-bubble">
                    <span class="model-badge">AI 回复中...</span>
                    {thinking_html}
                    {full_response}<span class="streaming-cursor"></span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            tool_calls = []
            if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                for tc in chunk.tool_calls:
                    tool_calls.append({
                        "id": tc.get("id", ""),
                        "name": tc.get("name", ""),
                        "args": tc.get("args", {})
                    })
            
            if tool_calls:
                placeholder.empty()
                for tc in tool_calls:
                    display_tool_approval(tc)
                return
        
        model_used = selected_model
        if selected_model == "auto":
            model_display = "Qwen3/DeepSeek (自动选择)"
        elif "qwen" in selected_model.lower():
            model_display = "Qwen3"
        else:
            model_display = "DeepSeek"
        
        thinking_html = ""
        if thinking_process:
            thinking_html = f"""
            <div class="thinking-panel">
                <div class="thinking-panel-header" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
                    <span>🧠</span>
                    <span>思考过程 (点击展开/折叠)</span>
                </div>
                <div class="thinking-panel-content" style="display: none;">{thinking_process}</div>
            </div>
            """
        
        placeholder.markdown(f"""
        <div class="message-container message-assistant">
            <div class="avatar avatar-assistant">🤖</div>
            <div class="message-bubble">
                <span class="model-badge">{model_display}</span>
                {thinking_html}
                {full_response}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
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
        
        error_msg = f"抱歉，我遇到了一些问题: {str(e)}"
        st.session_state.messages.append({
            "role": "assistant",
            "content": error_msg,
            "model": "Error",
            "sources": []
        })
        st.rerun()


if __name__ == "__main__":
    main()
