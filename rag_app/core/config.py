import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str | None
    deepseek_base_url: str | None
    qwen_omni_api_key: str | None
    qwen_omni_base_url: str | None
    tongyi_embedding_api_key: str | None
    tongyi_embedding_base_url: str | None


def _read_env() -> Settings:
    # 明确指定 .env 文件路径
    load_dotenv(dotenv_path=".env")
    return Settings(
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL"),
        qwen_omni_api_key=os.getenv("QWEN_OMNI_API_KEY"),
        qwen_omni_base_url=os.getenv("QWEN_OMNI_BASE_URL"),
        tongyi_embedding_api_key=(
            os.getenv("TONGYI_EMBIDDING_API_KEY")
            or os.getenv("DASHSCOPE_API_KEY")
        ),
        tongyi_embedding_base_url=(
            os.getenv("TONGYI_EMBEDDING_BASE_URL")
            or os.getenv("DASHSCOPE_BASE_URL")
        ),
    )

settings = _read_env()