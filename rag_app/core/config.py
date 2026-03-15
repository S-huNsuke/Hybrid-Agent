import os
import logging
from dataclasses import dataclass
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_SEARCH_K = 4
DEFAULT_CHUNK_SIZE = 2000
DEFAULT_CHUNK_OVERLAP = 400
DEFAULT_CHILD_CHUNK_SIZE = 500
DEFAULT_CHILD_CHUNK_OVERLAP = 100
DEFAULT_TEMPERATURE = 0.5
DEFAULT_MAX_TOKENS = 1024
DEFAULT_ADVANCED_MAX_TOKENS = 2048
DEFAULT_TIMEOUT = 60
DEFAULT_COMPLEXITY_THRESHOLD = 0.4


@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str | None
    deepseek_base_url: str | None
    qwen_omni_api_key: str | None
    qwen_omni_base_url: str | None
    tongyi_embedding_api_key: str | None
    tongyi_embedding_base_url: str | None
    mysql_user: str | None
    mysql_password: str | None
    mysql_host: str | None
    mysql_port: str | None
    mysql_database: str | None
    api_key: str | None
    allowed_origins: str | None


def _get_env_path() -> str:
    project_root = Path(__file__).parent.parent.parent
    env_path = project_root / ".env"
    return str(env_path)


def _validate_settings(settings: Settings) -> None:
    required_keys = []
    if not settings.deepseek_api_key:
        required_keys.append("DEEPSEEK_API_KEY")
    if not settings.qwen_omni_api_key:
        required_keys.append("QWEN_OMNI_API_KEY")
    
    if required_keys:
        logger.warning(f"Missing API keys: {', '.join(required_keys)}")
    
    if not settings.tongyi_embedding_api_key:
        logger.warning("TONGYI_EMBEDDING_API_KEY not set, RAG features may not work")


def _read_env() -> Settings:
    env_path = _get_env_path()
    load_dotenv(dotenv_path=env_path)
    
    settings = Settings(
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL"),
        qwen_omni_api_key=os.getenv("QWEN_OMNI_API_KEY"),
        qwen_omni_base_url=os.getenv("QWEN_OMNI_BASE_URL"),
        tongyi_embedding_api_key=(
            os.getenv("TONGYI_EMBEDDING_API_KEY")
            or os.getenv("DASHSCOPE_API_KEY")
        ),
        tongyi_embedding_base_url=(
            os.getenv("TONGYI_EMBEDDING_BASE_URL")
            or os.getenv("DASHSCOPE_BASE_URL")
        ),
        mysql_user=os.getenv("MYSQL_USER"),
        mysql_password=os.getenv("MYSQL_PASSWORD"),
        mysql_host=os.getenv("MYSQL_HOST"),
        mysql_port=os.getenv("MYSQL_PORT"),
        mysql_database=os.getenv("MYSQL_DATABASE"),
        api_key=os.getenv("API_KEY"),
        allowed_origins=os.getenv("ALLOWED_ORIGINS"),
    )
    
    _validate_settings(settings)
    return settings


settings = _read_env()
