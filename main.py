from rag_app.agent.builder import build_agent
from rag_app.cli.streaming import stream_and_print


def run_cli() -> None:
    print("开始运行")
    print("加载中......")

    agent = build_agent()
    config = {"configurable": {"thread_id": "user_123"}}

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
