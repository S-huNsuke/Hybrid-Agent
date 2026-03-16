"""主题配置和 CSS 样式"""

import streamlit as st

# 颜色配置
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


def get_theme_colors() -> dict:
    """获取当前主题颜色"""
    theme = st.session_state.get("theme", "light")
    if theme == "dark":
        return DARK_COLORS
    return COLORS


def get_theme_css() -> str:
    """生成主题 CSS 样式"""
    colors = get_theme_colors()
    return f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;600;700&display=swap');
    @import url('https://fonts.googleapis.com/icon?family=Material+Icons');
    
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
    
    html, body, p, div, span, input, textarea, button {{
        font-family: "Noto Sans SC", "PingFang SC", -apple-system, BlinkMacSystemFont, sans-serif !important;
    }}
    
    #MainMenu, footer {{
        visibility: hidden;
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

    [data-testid="stBaseButton-secondary"] {{
        background-color: {colors['bg_secondary']} !important;
        color: {colors['text_primary']} !important;
        border-color: {colors['border']} !important;
    }}

    [data-testid="stBaseButton-secondary"]:hover {{
        background-color: {colors['bg_primary']} !important;
        border-color: {colors['accent_primary']} !important;
    }}

    button[data-testid="stBaseButton-secondary"] {{
        background-color: {colors['bg_secondary']} !important;
        color: {colors['text_primary']} !important;
    }}

    [data-testid="stFileUploaderDropzone"] {{
        min-height: 180px !important;
    }}

    [data-testid="stFileUploaderDropzoneInstructions"] {{
        display: none !important;
    }}

    [data-testid="stFileUploaderDropzone"] > div:first-child {{
        display: none !important;
    }}

    [data-testid="stFileUploaderDropzone"] .st-emotion-cache-kt79cc {{
        display: none !important;
    }}

    [data-testid="stFileUploaderDropzone"] .st-emotion-cache-i0nc7r {{
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 16px !important;
        padding: 20px !important;
    }}

    [data-testid="stFileUploaderDropzone"] .st-emotion-cache-i0nc7r .st-emotion-cache-yo0lzo {{
        display: none !important;
    }}

    [data-testid="stFileUploaderDropzone"] .st-emotion-cache-i0nc7r::before {{
        content: "拖放文件到此处，或点击下方按钮选择文件" !important;
        font-size: 14px !important;
        color: {colors['text_primary']} !important;
        display: block !important;
        text-align: center !important;
        line-height: 1.6 !important;
        margin-bottom: 16px !important;
    }}
    
    [data-testid="stFileUploaderDropzone"] .st-emotion-cache-i0nc7r::after {{
        content: "支持格式：PDF、DOCX、TXT、MD（单个文件最大 200MB）" !important;
        font-size: 12px !important;
        color: {colors['text_secondary']} !important;
        display: block !important;
        text-align: center !important;
        margin-top: 8px !important;
    }}

    [data-testid="stFileUploaderDropzone"] .st-emotion-cache-epvm6 {{
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        width: 100% !important;
        margin-top: 16px !important;
    }}

    [data-testid="stFileUploaderDropzone"] [data-testid="stBaseButton-secondary"] {{
        background: linear-gradient(135deg, {colors['accent_primary']} 0%, {colors['accent_secondary']} 100%) !important;
        color: white !important;
        border: none !important;
        padding: 8px 32px !important;
        font-size: 14px !important;
        border-radius: 8px !important;
        min-width: 120px !important;
    }}

    [data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-secondary"] p {{
        display: none !important;
    }}

    [data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-secondary"]::after {{
        content: "浏览文件" !important;
        font-size: 14px !important;
        color: white !important;
        display: block !important;
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
    
    [data-testid="stFileUploaderDropzone"] {{
        background: linear-gradient(135deg, {colors['bg_secondary']} 0%, {colors['bg_primary']} 100%) !important;
        border: 2px dashed {colors['accent_primary']} !important;
        border-radius: 16px !important;
        padding: 32px 24px !important;
    }}
    
    [data-testid="stMain"] {{
        background: {colors['bg_primary']};
    }}
    
    .stApp {{
        background: {colors['bg_primary']};
    }}
    
    [data-testid="stToolbar"] {{
        background-color: {colors['bg_primary']} !important;
    }}
    
    [data-testid="stChatInput"] {{
        background-color: {colors['bg_primary']} !important;
        border-color: {colors['border']} !important;
    }}
    
    [data-testid="stChatInputTextArea"] {{
        background-color: {colors['bg_primary']} !important;
        color: {colors['text_primary']} !important;
    }}

    [data-testid="stChatInputTextArea"]::placeholder {{
        color: {colors['text_placeholder']} !important;
    }}

    [data-testid="stChatInput"] > div {{
        background-color: {colors['bg_primary']} !important;
        border-color: {colors['border']} !important;
    }}

    [data-testid="stChatInput"] textarea {{
        background-color: {colors['bg_primary']} !important;
        color: {colors['text_primary']} !important;
    }}

    div[data-baseweb="select"] > div {{
        background-color: {colors['bg_secondary']} !important;
        border-color: {colors['border']} !important;
    }}

    div[data-baseweb="select"] > div > div {{
        color: {colors['text_primary']} !important;
    }}

    [data-testid="stSelectbox"] > div > div {{
        background-color: {colors['bg_secondary']} !important;
    }}

    [data-testid="stSelectbox"] [data-testid="stMarkdownContainer"] {{
        color: {colors['text_primary']} !important;
    }}

    .st-cg, .st-cg * {{
        background-color: {colors['bg_secondary']} !important;
        color: {colors['text_primary']} !important;
    }}

    [data-testid="stBottomBlockContainer"] {{
        background-color: {colors['bg_primary']} !important;
    }}

    .stChatInput {{
        background-color: {colors['bg_primary']} !important;
    }}

    div[role="combobox"] {{
        background-color: {colors['bg_secondary']} !important;
        color: {colors['text_primary']} !important;
        border-color: {colors['border']} !important;
    }}
    
    .stMarkdown p {{
        color: {colors['text_primary']} !important;
    }}
    
    h1, h2, h3, h4, h5, h6 {{
        color: {colors['text_primary']} !important;
    }}

    span[data-testid="stIconMaterial"] {{
        display: none !important;
    }}
    
    button[data-testid="stBaseButton-headerNoPadding"],
    [data-testid="stSidebarCollapseButton"] button,
    [data-testid="stSidebarExpandCollapseButton"] button,
    button[data-testid="stExpandSidebarButton"] {{
        visibility: visible !important;
        width: auto !important;
        height: auto !important;
        min-height: auto !important;
        min-width: auto !important;
        padding: 4px 8px !important;
        background: transparent !important;
        border: none !important;
    }}
    
    button[data-testid="stBaseButton-headerNoPadding"]::before,
    [data-testid="stSidebarCollapseButton"] button::before,
    [data-testid="stSidebarExpandCollapseButton"] button::before {{
        content: "◀" !important;
        font-size: 20px !important;
        font-family: system-ui, -apple-system, sans-serif !important;
        display: inline-block !important;
        visibility: visible !important;
        color: {colors['text_primary']} !important;
    }}
    
    button[data-testid="stExpandSidebarButton"]::before {{
        content: "▶" !important;
        font-size: 20px !important;
        font-family: system-ui, -apple-system, sans-serif !important;
        display: inline-block !important;
        visibility: visible !important;
        color: {colors['text_primary']} !important;
    }}
    
    button[data-testid="stBaseButton-headerNoPadding"]::after,
    [data-testid="stSidebarCollapseButton"] button::after,
    [data-testid="stSidebarExpandCollapseButton"] button::after,
    button[data-testid="stExpandSidebarButton"]::after {{
        display: none !important;
    }}
</style>
"""
