FROM python:3.12-slim

LABEL maintainer="Hybrid-Agent Team"
LABEL description="基于问题复杂度自动切换的多模型智能助手 + RAG 知识库"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml uv.lock ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY docker-entrypoint.sh ./docker-entrypoint.sh

RUN uv sync --frozen --no-dev
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["./docker-entrypoint.sh"]
