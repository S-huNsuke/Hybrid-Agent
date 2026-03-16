"""Hybrid-Agent - 基于问题复杂度自动切换的多模型智能助手 + RAG 知识库"""

from hybrid_agent.core.config import settings, get_project_root
from hybrid_agent.core.rag_system import get_rag_system
from hybrid_agent.agent.builder import build_agent, get_agent_instance
from hybrid_agent.llm.models import base_model, advanced_model
from hybrid_agent.llm.model_selector import select_model, resolve_model_type

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "settings",
    "get_project_root",
    "get_rag_system",
    "build_agent",
    "get_agent_instance",
    "base_model",
    "advanced_model",
    "select_model",
    "resolve_model_type",
]
