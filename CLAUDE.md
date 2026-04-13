# Hybrid-Agent — Repo Guide

## 当前事实
- 主代码位于 `src/hybrid_agent/`，按 `agent/`、`api/`、`cli/`、`core/`、`llm/`、`web/` 分层。
- 前端位于 `frontend/`，使用 Vue 3 + Vite。
- 后端主入口为 `src/hybrid_agent/api/main.py`，主 API 路径为 `/api/v1/*`；旧 `/api/*` 仅保留兼容桥接。
- 项目同时保留 CLI、FastAPI、Streamlit 三种入口。

## 根目录约定
- 根目录只保留入口级文档与工程配置：
  - `README.md`
  - `QUICKSTART.md`
  - `CLAUDE.md`
  - `KNOWN_FAILURES.md`
  - `claude-progress.txt`
  - `pyproject.toml`
  - `docker-compose.yml`
  - `Dockerfile`
- 详细技术说明统一下沉到 `docs/`。
- 本地产物不得留在仓库结构中：如向量库、SQLite 数据、上传缓存、构建产物、worktree 副本、`node_modules`、`*.egg-info`。

## 启动方式
```bash
# CLI
uv run hybrid-agent

# API
export PYTHONPATH="$(pwd)/src"
uv run uvicorn hybrid_agent.api.main:app --reload --host 0.0.0.0 --port 8000

# Streamlit
export PYTHONPATH="$(pwd)/src"
uv run streamlit run src/hybrid_agent/web/app.py

# Docker
docker compose up -d
```

## 工作规则
- 改架构或规范时，先同步 `docs/architecture.md`、`docs/conventions.md`，再更新 `claude-progress.txt`。
- 发现重复失败模式时，记录到 `KNOWN_FAILURES.md`。
- Python 命令统一用 `uv run`；前端统一在 `frontend/` 下用 `npm`。
- 提交前至少确保相关范围的 `ruff`、`mypy`、`pytest` 或前端 `npm run build` 通过。

## 文档导航
- `README.md`：项目入口与运行方式
- `QUICKSTART.md`：最短启动路径
- `docs/project-overview.md`：项目整体技术说明
- `docs/architecture.md`：当前架构现实与阶段状态
- `docs/conventions.md`：开发规范与契约
- `docs/superpowers/`：计划、阶段文档与设计规格
