import os
import logging
from dataclasses import dataclass
from dotenv import load_dotenv
from pathlib import Path

logger = logging.getLogger(__name__)


def get_project_root() -> Path:
    """获取项目根目录的统一方法"""
    # src/hybrid_agent/core/config.py -> Hybrid-Agent/
    return Path(__file__).parent.parent.parent.parent


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

# 审查器默认配置
DEFAULT_REVIEWER_ENABLED = True
DEFAULT_REVIEWER_MODEL = "qwen-turbo"
DEFAULT_REVIEWER_TEMPERATURE = 0.1
DEFAULT_REVIEWER_MAX_TOKENS = 512
DEFAULT_REVIEWER_RELEVANCE_THRESHOLD = 5.0
DEFAULT_REVIEWER_MAX_CONTENTS = 5
DEFAULT_REVIEWER_TIMEOUT = 15


@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str | None
    deepseek_base_url: str | None
    qwen_omni_api_key: str | None
    qwen_omni_base_url: str | None
    qwen_api_key: str | None
    qwen_base_url: str | None
    tongyi_embedding_api_key: str | None
    tongyi_embedding_base_url: str | None
    mysql_user: str | None
    mysql_password: str | None
    mysql_host: str | None
    mysql_port: str | None
    mysql_database: str | None
    api_key: str | None
    allowed_origins: str | None


@dataclass
class ReviewerSettings:
    """内容审查器配置"""
    enabled: bool = DEFAULT_REVIEWER_ENABLED
    model_name: str = DEFAULT_REVIEWER_MODEL
    temperature: float = DEFAULT_REVIEWER_TEMPERATURE
    max_tokens: int = DEFAULT_REVIEWER_MAX_TOKENS
    relevance_threshold: float = DEFAULT_REVIEWER_RELEVANCE_THRESHOLD
    max_contents: int = DEFAULT_REVIEWER_MAX_CONTENTS
    timeout: int = DEFAULT_REVIEWER_TIMEOUT


# 默认审查器配置实例
default_reviewer_settings = ReviewerSettings()


def _get_env_path() -> str:
    project_root = get_project_root()
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
    
    if not settings.qwen_api_key:
        logger.warning("QWEN_API_KEY not set, reviewer may use fallback credentials")


def _read_env() -> Settings:
    env_path = _get_env_path()
    load_dotenv(dotenv_path=env_path)
    
    settings = Settings(
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL"),
        qwen_omni_api_key=os.getenv("QWEN_OMNI_API_KEY"),
        qwen_omni_base_url=os.getenv("QWEN_OMNI_BASE_URL"),
        qwen_api_key=os.getenv("QWEN_API_KEY"),
        qwen_base_url=os.getenv("QWEN_BASE_URL"),
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
