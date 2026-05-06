# 快速启动指南

## 🚀 启动方式

### 1. 命令行模式（CLI）

```bash
# 方式1：使用入口命令（推荐）
hybrid-agent

# 方式2：使用 uv
uv run hybrid-agent
```

### 2. API 服务模式

```bash
# 启动 FastAPI 服务
export PYTHONPATH="$(pwd)/src"
uv run uvicorn hybrid_agent.api.main:app --reload --host 0.0.0.0 --port 8000

# 访问 API 文档
# http://localhost:8000/docs
```

### 3. Vue 前端 + API 模式（推荐）

```bash
# 一键启动（后端 API + Vue 前端）
./start.sh

# 后端 API:  http://localhost:8000
# Vue 前端:  http://localhost:3000
```

### 4. Docker 部署模式

```bash
# 复制环境变量文件
cp .env.example .env

# 编辑 .env 文件，配置你的 API Key

# 使用 docker compose 启动
docker compose up -d

# 访问服务
# API: http://localhost:8000
# API 文档: http://localhost:8000/docs
# Vue 前端: http://localhost:3000

# 查看日志
docker compose logs -f

# 停止服务
docker compose down
```

## 💡 使用建议

1. **首次使用**: 建议先通过 Web 界面上传一些文档到知识库
2. **API 开发**: 查看 `/docs` 端点了解所有可用的 API
3. **模型选择**:
   - 简单问题使用 Qwen3（速度快）
   - 复杂问题使用 DeepSeek（质量高）
   - 自动模式会根据问题复杂度自动切换
4. **Embedding 后端**:
   - 默认可使用开源 `sentence-transformers` embedding
   - 若切回 DashScope embedding，请配置 `TONGYI_EMBEDDING_*`
   - 切换 embedding backend 或模型后，建议清空本地向量库并重新入库

## 🔧 环境要求

- Python 3.12+
- 已配置的 API 密钥（.env 文件）
- 所有依赖已安装

## 📚 更多信息

详见 [README.md](README.md)
