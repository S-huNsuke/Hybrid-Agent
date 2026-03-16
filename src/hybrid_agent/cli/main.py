"""CLI 主入口"""

import uuid

from hybrid_agent.agent.builder import build_agent
from hybrid_agent.cli.streaming import stream_and_print


def run_cli() -> None:
    """运行 CLI 模式"""
    print("开始运行")
    print("加载中......")
    
    print("\n请选择模型模式:")
    print("1. 自动选择 (根据问题复杂度自动选择模型)")
    print("2. Qwen3 基础模型 (简单问题)")
    print("3. DeepSeek 增强模型 (复杂问题)")
    
    model_choice = input("请输入选项 (1/2/3): ").strip()
    
    model_config = {
        "1": "auto",
        "2": "qwen3-omni",
        "3": "deepseek-v3"
    }.get(model_choice, "auto")
    
    model_display = {
        "auto": "自动选择",
        "qwen3-omni": "Qwen3 基础模型",
        "deepseek-v3": "DeepSeek 增强模型"
    }.get(model_config, "自动选择")
    
    print(f"\n已选择: {model_display}")
    
    thread_id = str(uuid.uuid4())
    agent = build_agent(enable_tools=True, enable_approval=False)
    config = {"configurable": {"thread_id": thread_id, "model": model_config}}
    
    stream_and_print(agent, "介绍下你自己", config, show_reasoning=True)
    print("-" * 10)
    
    while True:
        human_input = input("请输入: ").strip()
        
        if human_input == "exit":
            stream_and_print(
                agent,
                "用户结束了对话，与用户告别",
                config,
                show_reasoning=False,
                role="system",
            )
            break
        
        stream_and_print(agent, human_input, config, show_reasoning=True)
        print("输入exit结束对话")


if __name__ == "__main__":
    run_cli()
