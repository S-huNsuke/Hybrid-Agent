from __future__ import annotations

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

DEFAULT_BASE_MODEL = "qwen3-omni-flash-2025-12-01"
DEFAULT_ADVANCED_MODEL = "deepseek-v3"

# 审查器默认配置
DEFAULT_REVIEWER_ENABLED = True
DEFAULT_REVIEWER_MODEL = "qwen-turbo"
DEFAULT_REVIEWER_TEMPERATURE = 0.1
DEFAULT_REVIEWER_MAX_TOKENS = 512
DEFAULT_REVIEWER_RELEVANCE_THRESHOLD = 5.0
DEFAULT_REVIEWER_MAX_CONTENTS = 5
DEFAULT_REVIEWER_TIMEOUT = 15

# ── Agentic RAG 图配置 ─────────────────────────────────────────────────────

# 最大检索迭代次数（SELF-RAG 反思循环）
AGENTIC_MAX_ITERATIONS = 2
# 检索质量满足阈值（ContentReviewer 评分 / 10）
AGENTIC_REFLECTION_THRESHOLD = 0.5
# 最终返回 top-K（reranker 负责缩减）
AGENTIC_FINAL_TOP_K = 4

# ── 混合检索配置 ───────────────────────────────────────────────────────────

# RRF 融合公式参数（k=60 是论文推荐值）
RRF_K = 60
# 每路检索的候选数（reranker 负责缩减至 top-K）
RETRIEVE_K_PER_PATH = 10
# Rerank 返回数量
DEFAULT_RERANK_TOP_K = 4
# 单次 rerank 最大文档数（DashScope API 限制）
MAX_DOCS_PER_RERANK = 20

# ── 查询理解配置 ───────────────────────────────────────────────────────────

# 超过该长度的查询视为复杂查询，触发子问题分解
COMPLEX_QUERY_THRESHOLD = 100
# 子问题最大数量
MAX_SUB_QUERIES = 3
# qwen-turbo 调用超时（秒）
QUERY_UNDERSTANDING_TIMEOUT = 15
# qwen-turbo 最大 token 数
QUERY_UNDERSTANDING_MAX_TOKENS = 256

# ── 会话管理配置 ───────────────────────────────────────────────────────────

# 触发摘要压缩的对话轮数阈值
MAX_ROUNDS_BEFORE_SUMMARY = 20
# 会话 TTL（秒）
SESSION_TTL = 7200  # 2 小时
# 最大会话数
SESSION_MAX_SIZE = 1000
# 摘要最大 token 数
SUMMARY_MAX_TOKENS = 300


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
    # 核心模型 API Key（必须）
    missing_core_keys = []
    if not settings.deepseek_api_key:
        missing_core_keys.append("DEEPSEEK_API_KEY (高级模型 deepseek-V3.2)")
    if not settings.qwen_omni_api_key:
        missing_core_keys.append("QWEN_OMNI_API_KEY (基础模型 qwen3-omni)")
    
    if missing_core_keys:
        logger.warning(f"缺少核心 API Key，以下功能将不可用: {', '.join(missing_core_keys)}")
    
    # RAG 功能依赖（强烈建议）
    if not settings.tongyi_embedding_api_key:
        logger.warning("TONGYI_EMBEDDING_API_KEY 未配置，RAG 向量检索功能将不可用")
    
    # 扩展功能依赖（可选）
    optional_keys = []
    if not settings.qwen_api_key:
        optional_keys.append("QWEN_API_KEY")
    
    if optional_keys:
        logger.info(
            f"可选 API Key 未配置 ({', '.join(optional_keys)})，"
            f"意图分类/HyDE改写/会话摘要等功能将降级使用 TONGYI_EMBEDDING_API_KEY"
        )


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
