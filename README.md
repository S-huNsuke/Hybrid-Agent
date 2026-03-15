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

### API 服务模式

```bash
uv run uvicorn rag_frontend.api.main:app --reload
```

### Web 界面模式

```bash
uv run streamlit run rag_frontend/fronted.py
```

### 交互示例

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
├── rag_app/                    # 核心应用
│   ├── agent/
│   │   └── builder.py          # Agent 构建
│   ├── cli/
│   │   └── streaming.py        # 流式输出
│   ├── core/
│   │   ├── config.py           # 配置管理
│   │   ├── database.py         # 数据库
│   │   ├── document_processor.py  # 文档处理
│   │   ├── rag_system.py       # RAG 系统
│   │   └── vector.py          # 向量存储
│   ├── llm/
│   │   └── models.py           # 模型定义
│   ├── middleware/
│   │   └── model_switch.py     # 动态模型选择
│   └── tools/
│       ├── document_tools.py   # 文档工具
│       └── web_search.py       # 网页搜索
├── rag_frontend/               # 前端服务
│   ├── api/
│   │   ├── chat.py             # 聊天 API
│   │   ├── documents.py        # 文档 API
│   │   └── main.py             # FastAPI 入口
│   ├── services/
│   │   └── rag_service.py      # RAG 服务
│   └── fronted.py              # Streamlit 入口
├── .env                        # 环境变量
├── .gitignore
├── .python-version
├── main.py                     # CLI 入口
├── pyproject.toml              # 项目配置
└── uv.lock
```

## 模型切换逻辑

系统会根据以下因素判断问题复杂度：

- **问题长度**：超过 300 字或 1000 字会增加复杂度分数
- **问题类型**：包含"为什么"、"如何"、"分析"、"代码"等关键词会增加复杂度分数
- **代码内容**：包含代码块或代码注释会增加复杂度分数

当复杂度分数达到 0.4 及以上时，会使用增强模型（DeepSeek），否则使用基础模型（Qwen）。

## 环境变量配置

```env
# DeepSeek 模型配置
DEEPSEEK_API_KEY='your_deepseek_api_key'
DEEPSEEK_BASE_URL='https://dashscope.aliyuncs.com/compatible-mode/v1'

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

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这个项目！

## 联系方式

- GitHub: [S-huNsuke](https://github.com/S-huNsuke)
