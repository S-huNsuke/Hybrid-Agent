# Hybrid-Agent

基于用户问题复杂度自动切换的多模型智能助手 + RAG 知识库

## 项目介绍

Hybrid-Agent 是一个智能助手系统，能够根据用户问题的复杂度自动切换不同的 AI 模型，并支持 RAG（检索增强生成）知识库功能。

## 核心功能

- **智能模型切换**：根据问题复杂度自动选择基础模型或增强模型
- **RAG 知识库**：支持文档上传、搜索、编辑和删除
- **流式输出**：实时展示 AI 思考过程和回答内容
- **多模型支持**：集成了 Qwen 和 DeepSeek 等多种 AI 模型
- **多端支持**：提供 CLI、API 和 Streamlit Web 界面
- **内容审查**：内置回答质量审查机制
- **Docker 支持**：支持 Docker 部署

## 技术栈

- Python 3.12+
- LangChain / LangGraph
- DashScope (阿里云)
- ChromaDB (向量数据库)
- FastAPI (API 服务)
- Streamlit (Web 界面)
- Docker / Docker Compose

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/S-huNsuke/Hybrid-Agent.git
cd Hybrid-Agent
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填写你的 API 密钥
```

### 3. 本地运行

#### 命令行模式

```bash
export PYTHONPATH="$(pwd)/src"
uv run python main.py
```

#### API 服务模式

```bash
export PYTHONPATH="$(pwd)/src"
uv run uvicorn hybrid_agent.api.main:app --reload --host 0.0.0.0 --port 8000
```

#### Web 界面模式

```bash
export PYTHONPATH="$(pwd)/src"
uv run streamlit run src/hybrid_agent/web/app.py
```

#### 一键启动（推荐）

```bash
chmod +x start.sh
./start.sh
```

启动后访问：
- API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- Web: http://localhost:8501

### 4. Docker 部署

```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 项目结构

```
Hybrid-Agent/
├── src/
│   └── hybrid_agent/
│       ├── agent/                  # Agent 层
│       │   ├── __init__.py
│       │   ├── builder.py         # Agent 构建
│       │   ├── reviewer/         # 审查模块
│       │   │   ├── __init__.py
│       │   │   ├── content_reviewer.py  # 内容审查
│       │   │   ├── scorer.py     # 评分器
│       │   │   └── prompts.py    # 审查提示词
│       │   └── tools/            # Agent 工具
│       │       ├── __init__.py
│       │       ├── web_search.py # 网页搜索
│       │       └── document_tools.py  # 文档工具
│       ├── api/                   # API 层
│       │   ├── __init__.py
│       │   ├── main.py            # FastAPI 应用
│       │   ├── schemas.py         # 数据模型
│       │   ├── routes/            # 路由
│       │   │   ├── __init__.py
│       │   │   ├── chat.py        # 聊天接口
│       │   │   └── documents.py  # 文档接口
│       │   └── services/          # 服务层
│       │       ├── __init__.py
│       │       └── rag_service.py # RAG 服务
│       ├── core/                  # 核心层
│       │   ├── __init__.py
│       │   ├── config.py          # 配置管理
│       │   ├── database.py        # 数据库
│       │   ├── document_processor.py  # 文档处理
│       │   ├── rag_system.py     # RAG 系统
│       │   └── vector.py          # 向量存储
│       ├── llm/                   # LLM 层
│       │   ├── __init__.py
│       │   ├── models.py          # 模型定义
│       │   ├── model_selector.py  # 模型选择器
│       │   └── reviewer.py        # 回答审查器
│       ├── web/                   # Web UI
│       │   ├── __init__.py
│       │   ├── app.py             # Streamlit 应用
│       │   ├── components/        # UI 组件
│       │   │   ├── __init__.py
│       │   │   ├── chat.py       # 聊天组件
│       │   │   ├── sidebar.py    # 侧边栏
│       │   │   └── theme.py      # 主题
│       │   └── utils/             # 工具函数
│       │       ├── __init__.py
│       │       └── helpers.py
│       └── cli/                   # CLI
│           ├── __init__.py
│           ├── main.py            # CLI 入口
│           └── streaming.py       # 流式输出
├── main.py                        # 项目入口
├── start.sh                       # 启动脚本
├── Dockerfile                     # Docker 镜像
├── docker-compose.yml             # Docker Compose
├── .dockerignore                  # Docker 忽略文件
├── pyproject.toml                 # 项目配置
└── README.md
```

## 环境变量

```env
# DeepSeek 模型
DEEPSEEK_API_KEY='your_deepseek_api_key'
DEEPSEEK_BASE_URL='https://api.deepseek.com'

# Qwen 模型
QWEN_OMNI_API_KEY='your_qwen_api_key'
QWEN_OMNI_BASE_URL='https://dashscope.aliyuncs.com/compatible-mode/v1'

# Tongyi Embedding（用于 RAG）
TONGYI_EMBEDDING_API_KEY='your_tongyi_api_key'
TONGYI_EMBEDDING_BASE_URL='https://dashscope.aliyuncs.com/compatible-mode/v1'

# API 安全
API_KEY='your_api_key'

# CORS
ALLOWED_ORIGINS='http://localhost:3000,http://localhost:8501'
```

## API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/` | GET | 健康检查 |
| `/health` | GET | 健康状态 |
| `/api/chat` | POST | 聊天接口 |
| `/api/documents/upload` | POST | 上传文档 |
| `/api/documents` | GET | 列出文档 |
| `/api/documents/{doc_id}` | DELETE | 删除文档 |
| `/api/documents/{doc_id}` | GET | 获取文档详情 |
| `/api/models` | GET | 可用模型列表 |

## 许可证

MIT License
