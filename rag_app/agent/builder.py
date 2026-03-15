from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
import threading

from rag_app.middleware.model_switch import select_model
from rag_app.tools import web_search, document_edit, document_delete, list_documents, search_documents

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
_agent_instance = None
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


def build_agent(enable_tools: bool = True, enable_approval: bool = True, use_singleton: bool = True):
    global _agent_instance
    
    if use_singleton and _agent_instance is not None:
        return _agent_instance
    
    with _agent_lock:
        if use_singleton and _agent_instance is not None:
            return _agent_instance
        
        checkpointer = InMemorySaver()
        
        tools_to_use = TOOLS if enable_tools else []
        
        if enable_approval and enable_tools:
            interrupt_before = ["tools"]
        else:
            interrupt_before = []
        
        agent = create_react_agent(
            model=select_model,
            tools=tools_to_use,
            prompt=SYSTEM_PROMPT,
            checkpointer=checkpointer,
            interrupt_before=interrupt_before,
        )
        
        if use_singleton:
            _agent_instance = agent
        
        return agent


def get_agent_instance():
    return build_agent(enable_tools=True, enable_approval=False, use_singleton=True)


def reset_agent_instance():
    global _agent_instance
    with _agent_lock:
        _agent_instance = None


def get_tools():
    return TOOLS


def extract_tool_calls(response) -> list:
    tool_calls = []
    if hasattr(response, 'tool_calls'):
        for tc in response.tool_calls:
            tool_calls.append({
                "id": tc.get("id", ""),
                "name": tc.get("name", ""),
                "args": tc.get("args", {})
            })
    return tool_calls
