from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.checkpoint.memory import InMemorySaver

from rag_app.llm.models import base_model
from rag_app.middleware.model_switch import dynamic_model_selection

SYSTEM_PROMPT = """你是Shunsuke，一个幽默风趣的智能助手。
当你第一次与用户交流时，请先简洁地介绍你自己，包括：
1. 你的名字/身份
2. 你能帮助用户做什么"""


def build_agent():
    return create_agent(
        model=base_model,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=InMemorySaver(),
        middleware=[
            SummarizationMiddleware(
                model=base_model,
                trigger=("tokens", 2048),
                keep=("messages", 20),
            ),
            dynamic_model_selection,
        ],
    )