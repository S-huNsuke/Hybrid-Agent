"""CLI 流式输出"""

def _content_to_text(content) -> str:
    """将内容转换为文本"""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    texts.append(text)
        return "".join(texts)

    return ""


def _extract_reasoning(chunk) -> str:
    """从响应块中提取思考过程"""
    additional_kwargs = getattr(chunk, "additional_kwargs", {})
    if not isinstance(additional_kwargs, dict):
        return ""

    reasoning = additional_kwargs.get("reasoning_content")
    if isinstance(reasoning, str):
        return reasoning

    return ""


def stream_and_print(
    agent,
    user_text: str,
    config: dict,
    show_reasoning: bool = True,
    role: str = "human",
) -> None:
    """流式输出并打印"""
    printed_reasoning_title = False
    printed_answer_title = False

    for chunk, _ in agent.stream(
        {"messages": [(role, user_text)]},
        config,
        stream_mode="messages",
    ):
        reasoning_piece = _extract_reasoning(chunk) if show_reasoning else ""
        if reasoning_piece:
            if not printed_reasoning_title:
                print("\n" + "=" * 20 + "思考过程" + "=" * 20 + "\n")
                printed_reasoning_title = True
            print(reasoning_piece, end="", flush=True)

        answer_piece = _content_to_text(getattr(chunk, "content", ""))
        if answer_piece:
            if show_reasoning and printed_reasoning_title and not printed_answer_title:
                print("\n" + "=" * 20 + "完整回复" + "=" * 20 + "\n")
                printed_answer_title = True
            print(answer_piece, end="", flush=True)

    print()
