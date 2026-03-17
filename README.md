# Hybrid-Agent

基于用户问题复杂度自动切换的多模型智能助手 + RAG 知识库

## 项目介绍

Hybrid-Agent 是一个智能助手系统，能够根据用户问题的复杂度自动切换不同的 AI 模型，并支持 RAG（检索增强生成）知识库功能。

## 核心功能

- **智能模型切换**：根据问题复杂度自动选择基础模型或增强模型
- **RAG 知识库**：支持文档上传、搜索、编辑和删除
- **流式输出**：实时展示 AI 思考过程和回答内容
- **多模型支持**：集成了 Qwen 和 DeepSeek 等多种 AI 模型
- **多端支持**：提供 CLI、FastAPI 和 Streamlit Web 界面
- **内容审查**：内置回答质量审查机制，支持自定义评分规则
- **一键启动**：提供启动脚本，同时启动后端 API 和前端 Web 界面

## 技术栈

- Python 3.12+
- LangChain / LangGraph
- DashScope (阿里云)
- ChromaDB (向量数据库)
- FastAPI (API 服务)
- Streamlit (Web 界面)

## 安装步骤

1. **克隆仓库**
   ```bash
   git clone https://github.com/S-huNsuke/Hybrid-Agent.git
   cd Hybrid-Agent
   ```

2. **安装依赖**
   ```bash
   uv pip install -e .
   ```

3. **配置环境变量**
   复制 `.env` 文件并填写相应的 API 密钥：
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，填写 API 密钥
   ```

## 使用方法

### 命令行模式

```bash
uv run python main.py
```

或使用入口命令：
```bash
uv run hybrid-agent
```

### API 服务模式

```bash
export PYTHONPATH="$(pwd)/src"
uv run uvicorn hybrid_agent.api.main:app --reload
```

### Web 界面模式

```bash
export PYTHONPATH="$(pwd)/src"
uv run streamlit run src/hybrid_agent/web/app.py
```

### 一键启动（推荐）

项目提供了启动脚本，可以同时启动后端 API 和前端 Web 界面：

```bash
# 给脚本添加执行权限
chmod +x start.sh

# 运行启动脚本
./start.sh
```

启动后访问：
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- 前端 Web: http://localhost:8501

### Docker 部署

```bash
# 1. 复制环境变量文件
cp .env.example .env

# 2. 编辑 .env 文件，配置你的 API Key

# 3. 使用 docker-compose 启动
docker-compose up -d

# 4. 访问服务
# API: http://localhost:8000
# API 文档: http://localhost:8000/docs
# Web 界面: http://localhost:8501

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```
开始运行
加载中......

请选择模型模式:
1. 自动选择 (根据问题复杂度自动选择模型)
2. Qwen3 基础模型 (简单问题)
3. DeepSeek 增强模型 (复杂问题)

请输入选项 (1/2/3): 1

已选择: 自动选择
哈喽！我是Shunsuke，一个自带段子手属性的智能助手 😎
...

请输入: 如何学习Python编程
[模型切换] 复杂请求，使用增强模型
...
输入exit结束对话
```

## 项目结构

```
Hybrid-Agent/
├── src/
│   └── hybrid_agent/           # 主包
│       ├── core/               # 核心层
│       │   ├── config.py       # 配置管理
│       │   ├── database.py     # 数据库
│       │   ├── document_processor.py  # 文档处理
│       │   ├── rag_system.py   # RAG 系统
│       │   └── vector.py       # 向量存储
│       ├── llm/                # LLM 层
│       │   ├── models.py       # 模型定义
│       │   ├── model_selector.py  # 模型选择器
│       │   └── reviewer.py     # 回答审查器
│       ├── agent/              # Agent 层
│       │   ├── builder.py      # Agent 构建
│       │   ├── reviewer/       # 审查模块
│       │   │   ├── content_reviewer.py  # 内容审查
│       │   │   ├── scorer.py    # 评分器
│       │   │   └── prompts.py   # 审查提示词
│       │   └── tools/          # Agent 工具
│       │       ├── web_search.py
│       │       └── document_tools.py
│       ├── api/                # API 层
│       │   ├── main.py         # FastAPI 应用
│       │   ├── schemas.py      # 数据模型
│       │   ├── routes/         # 路由
│       │   │   ├── chat.py
│       │   │   └── documents.py
│       │   └── services/       # 服务层
│       │       └── rag_service.py
│       ├── web/                # Web UI
│       │   ├── app.py          # Streamlit 应用
│       │   ├── components/     # UI 组件
│       │   │   ├── theme.py
│       │   │   ├── chat.py
│       │   │   └── sidebar.py
│       │   └── utils/
│       │       └── helpers.py
│       └── cli/                # CLI
│           ├── main.py         # CLI 入口
│           └── streaming.py    # 流式输出
├── main.py                     # 项目入口
├── start.sh                    # 一键启动脚本
├── Dockerfile                  # Docker 镜像构建
├── docker-compose.yml          # Docker Compose 配置
├── .dockerignore               # Docker 忽略文件
├── pyproject.toml              # 项目配置
└── README.md
```

## 模型切换逻辑

系统会根据以下因素判断问题复杂度：

- **问题长度**：超过 300 字或 1000 字会增加复杂度分数
- **问题类型**：包含"为什么"、"如何"、"分析"、"代码"等关键词会增加复杂度分数
- **代码内容**：包含代码块或代码注释会增加复杂度分数

当复杂度分数达到 0.4 及以上时，会使用增强模型（DeepSeek），否则使用基础模型（Qwen）。

## 内容审查机制

系统内置回答质量审查机制，确保输出内容的质量：

- **自动审查**：在模型生成回答后自动进行质量审查
- **多维度评分**：从准确性、完整性、可读性等多个维度评分
- **可自定义**：支持自定义评分规则和阈值
- **流式集成**：与流式输出完美集成，不影响响应速度

审查模块位于 `src/hybrid_agent/agent/reviewer/` 目录下，包含：
- `content_reviewer.py`：内容审查核心逻辑
- `scorer.py`：评分器实现
- `prompts.py`：审查提示词模板

## 环境变量配置

```env
# DeepSeek 模型配置
DEEPSEEK_API_KEY='your_deepseek_api_key'
DEEPSEEK_BASE_URL='https://api.deepseek.com'

# Qwen 模型配置
QWEN_OMNI_API_KEY='your_qwen_api_key'
QWEN_OMNI_BASE_URL='https://dashscope.aliyuncs.com/compatible-mode/v1'

# Tongyi Embedding 模型配置（用于 RAG）
TONGYI_EMBEDDING_API_KEY='your_tongyi_api_key'
TONGYI_EMBEDDING_BASE_URL='https://dashscope.aliyuncs.com/compatible-mode/v1'

# API 安全配置
API_KEY='your_api_key'

# CORS 配置
ALLOWED_ORIGINS='http://localhost:3000,http://localhost:8501'
```

## API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/` | GET | 服务健康检查 |
| `/health` | GET | 健康状态 |
| `/api/chat` | POST | 聊天接口 |
| `/api/documents/upload` | POST | 上传文档 |
| `/api/documents` | GET | 列出文档 |
| `/api/documents/{doc_id}` | DELETE | 删除文档 |
| `/api/documents/{doc_id}` | GET | 获取文档详情 |
| `/api/models` | GET | 列出可用模型 |

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这个项目！

## 联系方式

- GitHub: [S-huNsuke](https://github.com/S-huNsuke)