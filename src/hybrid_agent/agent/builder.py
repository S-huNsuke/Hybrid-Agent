from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
import threading

from hybrid_agent.llm.model_selector import select_model
from hybrid_agent.agent.tools import (
    web_search,
    document_edit,
    document_delete,
    list_documents,
    search_documents,
)

SYSTEM_PROMPT = """你是Shunsuke，一个幽默风趣的智能助手。
当你第一次与用户交流时，请先简洁地介绍你自己，包括：
1. 你的名字/身份
2. 你能帮助用户做什么

你可以使用以下工具：
- web_search: 当需要实时信息时搜索网页
- search_documents: 在知识库中搜索相关文档
- list_documents: 查看知识库中的文档列表
- document_delete: 删除知识库中的文档（需要用户确认）
- document_edit: 编辑知识库中的文档内容（需要用户确认）

重要：删除和编辑文档是危险操作，必须先征得用户明确同意才能执行。
- 如果用户要求删除或编辑文档，请先调用 list_documents 列出所有文档，让用户确认要操作的文档ID
- 获取用户确认后，再执行删除或编辑操作
- 如果用户没有明确确认，请拒绝执行"""

TOOLS = [
    web_search,
    search_documents,
    list_documents,
    document_delete,
    document_edit,
]

AGENT_CONFIGS: dict = {}
_default_agent_instance = None
_agent_lock = threading.Lock()


def _get_or_create_config(thread_id: str, model: str = "auto") -> dict:
    if thread_id not in AGENT_CONFIGS:
        AGENT_CONFIGS[thread_id] = {
            "configurable": {
                "thread_id": thread_id,
                "model": model,
                "pending_confirmation": None
            }
        }
    else:
        AGENT_CONFIGS[thread_id]["configurable"]["model"] = model
    return AGENT_CONFIGS[thread_id]


def _create_agent(enable_tools: bool = True, enable_approval: bool = False):
    """创建新的 Agent 实例（内部方法）"""
    checkpointer = InMemorySaver()
    
    tools_to_use = TOOLS if enable_tools else []
    
    if enable_approval and enable_tools:
        interrupt_before = ["tools"]
    else:
        interrupt_before = []
    
    return create_react_agent(
        model=select_model,
        tools=tools_to_use,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
        interrupt_before=interrupt_before,
    )


def build_agent(enable_tools: bool = True, enable_approval: bool = False):
    """构建 Agent 实例（每次调用都返回新的实例）"""
    return _create_agent(enable_tools=enable_tools, enable_approval=enable_approval)


def get_agent_instance():
    """获取默认的 Agent 单例实例（用于 API 和 Web 服务）"""
    global _default_agent_instance
    
    if _default_agent_instance is not None:
        return _default_agent_instance
    
    with _agent_lock:
        if _default_agent_instance is not None:
            return _default_agent_instance
        
        _default_agent_instance = _create_agent(enable_tools=True, enable_approval=False)
        return _default_agent_instance


def reset_agent_instance():
    """重置 Agent 单例实例"""
    global _default_agent_instance
    with _agent_lock:
        _default_agent_instance = None


def get_tools():
    """获取所有可用工具"""
    return TOOLS
