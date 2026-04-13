# Hybrid-Agent

基于用户问题复杂度自动切换的多模型智能助手 + RAG 知识库

## 项目介绍

Hybrid-Agent 是一个基于 **Agentic RAG**（智能体增强检索）的智能助手系统。系统通过 LangGraph 实现多阶段推理流水线，集成了混合检索、内容审查和智能模型切换能力。

核心架构：
- **Agentic RAG**：使用 LangGraph StateGraph 实现查询理解 → 多路检索 → 自我反思 → 生成的完整流程
- **混合检索**：融合 BM25 稀疏检索、向量稠密检索、HyDE 假设文档检索和子问题分解并行检索
- **智能模型切换**：根据问题复杂度自动选择 Qwen3-Omni（基础模型）或 DeepSeek-V3（增强模型）
- **内容审查**：ContentReviewer 评估检索质量，通过迭代反思提升回答准确率

近期交付能力：
- **认证与 RBAC**：新增 `auth/admin/providers` API，JWT 只承载身份标识，权限实时回源数据库
- **Provider 运行时管理**：支持按组维护 OpenAI / DeepSeek / OpenAI-compatible Provider，并在配置变更后自动失效运行时缓存
- **多组租户支持**：前后端统一支持 `group_id` 作用域选择，多组用户可在前端切换当前组
- **交付验证链路**：内置 `pytest` 回归、前端构建与 Playwright smoke E2E

## 核心功能

- **智能模型切换**：根据问题复杂度自动选择基础模型或增强模型
- **混合检索系统**：BM25 + 向量检索 + RRF 融合，提供更准确的检索结果
- **RAG 知识库**：支持批量上传、任务进度轮询、失败原因查看与重试、列表搜索/筛选/排序
- **流式输出**：实时展示 AI 思考过程和回答内容
- **多模型支持**：集成了 Qwen 和 DeepSeek 等多种 AI 模型
- **多端支持**：提供 CLI、API 和 Streamlit Web 界面
- **内容审查**：内置回答质量审查机制
- **Docker 支持**：支持 Docker 部署

## 交付状态

当前仓库已通过以下验证，可作为预发/提测基线：

```bash
./.venv/bin/pytest -q
cd frontend && npm run build
cd frontend && npm run e2e:smoke
```

## 技术栈

- Python 3.12+
- LangChain / LangGraph
- DashScope (阿里云) / Sentence Transformers
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

安全相关的最小必填项：
- `JWT_SECRET_KEY`：必填。未配置时认证接口不会签发/校验 token。
- `PROVIDER_SECRET_KEY`：建议显式配置。用于加密 Provider API Key；未配置时会回退到 `JWT_SECRET_KEY`。
- 生产环境不要使用示例密钥或默认占位值。

### 3. 本地运行

#### 命令行模式

```bash
uv run hybrid-agent
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

#### 一键启动（本地演示）

```bash
chmod +x start.sh
./start.sh
```

启动后访问：
- API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- Web: http://localhost:8501

如果你使用 Vue 前端工作台：

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 3000
```

访问 `http://127.0.0.1:3000`。

### 4. Docker 部署

```bash
# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f

# 停止服务
docker compose down
```

更完整的部署、迁移、备份与恢复说明见：
- [部署文档](./docs/deployment.md)
- [发布清单](./docs/release-checklist.md)

## 发布门槛检查（Release Check）

统一入口：

```bash
uv run python scripts/release_check.py
```

该脚本默认会检查：
- `docker-compose config/version`
- Python 回归测试
- 前端 `npm run build`
- 浏览器 `npm run e2e:smoke`

E2E 策略可通过环境变量切换：
- `RELEASE_E2E_MODE=required`：默认，E2E 必须通过
- `RELEASE_E2E_MODE=auto`：环境受限（如浏览器启动权限/依赖缺失）时允许降级并输出 `[WARN]`
- `RELEASE_E2E_MODE=skip`：显式跳过，必须同时设置 `RELEASE_E2E_SKIP_REASON`

## 浏览器 E2E 验收（Playwright）

E2E harness 位于 `tests/e2e/`，默认会在执行前检查：
- 前端地址：`E2E_BASE_URL`（默认 `http://127.0.0.1:3000`）
- API 健康检查：`E2E_API_HEALTH_URL`（默认 `http://127.0.0.1:8000/health`）

本地执行建议：

```bash
# 终端 1：启动后端
export PYTHONPATH="$(pwd)/src"
uv run uvicorn hybrid_agent.api.main:app --host 127.0.0.1 --port 8000
```

```bash
# 终端 2：启动前端
cd frontend
npm run dev -- --host 127.0.0.1 --port 3000
```

```bash
# 终端 3：执行 E2E smoke
cd frontend
npm run e2e:smoke
```

常用命令：

```bash
cd frontend
npm run e2e            # 跑 tests/e2e 全部用例
npm run e2e:headed     # 有头模式
npm run e2e:report     # 打开 HTML 报告
```

如果你只想验证命令链路，不做服务可用性检查，可临时设置：

```bash
E2E_SKIP_SERVICE_CHECK=1 npm run e2e -- --list
```

失败诊断产物输出在 `tests/e2e/artifacts/`（trace、video、screenshot、html report）。

注意：
- E2E harness 会为测试后端显式注入 `JWT_SECRET_KEY` / `PROVIDER_SECRET_KEY`，避免因弱默认值被禁用而导致注册流程失败。
- smoke 用例覆盖注册登录、Provider 创建、用户创建、文档上传、聊天主链路。

## 项目结构

```text
Hybrid-Agent/
├── src/hybrid_agent/               # Python 主代码
│   ├── agent/                      # Agentic RAG / LangGraph 编排
│   ├── api/                        # FastAPI API（auth/admin/providers/routes）
│   ├── cli/                        # CLI 入口
│   ├── core/                       # RAG / DB / retriever / 文档处理
│   ├── llm/                        # 模型解析与选择
│   └── web/                        # Streamlit 演示界面
├── frontend/                       # Vue 3 前端
│   ├── src/
│   │   ├── api/                    # Axios API 封装
│   │   ├── components/             # 布局与页面组件
│   │   ├── composables/            # 复用逻辑
│   │   ├── router/                 # 路由与守卫
│   │   ├── stores/                 # Pinia 状态管理
│   │   ├── styles/                 # 设计令牌与全局样式
│   │   └── views/                  # 页面视图
│   ├── Dockerfile
│   └── nginx.conf
├── tests/                          # Python / E2E 测试
│   └── e2e/                        # Playwright smoke
├── docs/                           # 架构、规范、阶段计划
├── scripts/                        # 检查与辅助脚本
├── alembic/                        # 数据库迁移
├── grafana/                        # Grafana provisioning / dashboards
├── prometheus/                     # Prometheus 配置与规则
├── Dockerfile
├── docker-compose.yml
├── main.py                         # 项目入口
├── start.sh                        # 本地启动脚本
├── pyproject.toml
└── README.md
```

说明：
- 根目录只保留源码、测试、文档和部署配置。
- `chroma_db/`、`documents.db`、`uploads/`、`frontend/dist/`、`*.egg-info`、worktree 副本等均视为本地产物，不纳入标准仓库结构。

## 多组租户说明

- 用户若只属于一个组，前后端会自动将该组作为默认作用域。
- 用户若属于多个组，Vue 前端会在 Header 提供“当前组”切换器；`chat/documents/models/providers` 请求会自动带上当前 `group_id`。
- 后端在多组场景下不再默认使用 `group_ids[0]` 作为隐式作用域；需要显式指定时会返回 `400`，防止跨组误操作。
- Provider 管理权限按“目标组内角色”校验，而不是按全局 `role` 粗暴放行。

## Agentic RAG 架构

```
用户输入
    ↓
┌──────────────────────────────────────────────┐
│  understand_query                            │
│  ├── 意图分类（direct/rag_only/web_only/    │
│  │         hybrid/math_code）               │
│  ├── HyDE 改写（生成假设文档）              │
│  └── 子问题分解（复杂查询拆解）              │
└──────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────┐
│  retrieval_decision                          │
│  是否需要检索？（math_code/direct 直接跳过） │
└──────────────────────────────────────────────┘
    ↓ YES
┌──────────────────────────────────────────────┐
│  hybrid_retrieve（多路融合）                │
│  ├── Path A: Dense 向量检索                 │
│  ├── Path B: BM25 稀疏检索                  │
│  ├── Path C: HyDE 向量检索                  │
│  └── Path D: 子问题并行检索                 │
│  → RRF 融合（k=60）→ DashScope Rerank      │
└──────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────┐
│  self_reflect（ContentReviewer 评估）        │
│  迭代最多 2 次，不满足则扩大查询重检         │
└──────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────┐
│  generate（生成回答 + 来源归因）             │
└──────────────────────────────────────────────┘
```

## 环境变量

```env
# DeepSeek 模型（使用 DashScope 兼容接口）
DEEPSEEK_API_KEY='your_deepseek_api_key'
DEEPSEEK_BASE_URL='https://dashscope.aliyuncs.com/compatible-mode/v1'

# Qwen 模型
QWEN_OMNI_API_KEY='your_qwen_api_key'
QWEN_OMNI_BASE_URL='https://dashscope.aliyuncs.com/compatible-mode/v1'

# Tongyi Embedding（用于 DashScope 向量后端）
TONGYI_EMBEDDING_API_KEY='your_tongyi_api_key'
TONGYI_EMBEDDING_BASE_URL='https://dashscope.aliyuncs.com/compatible-mode/v1'

# 认证 / Provider 密钥管理
JWT_SECRET_KEY='replace-with-a-long-random-secret'
PROVIDER_SECRET_KEY='replace-with-a-long-random-secret'

# Embedding backend（M17）
EMBEDDING_BACKEND='sentence_transformers'
EMBEDDING_MODEL_NAME='sentence-transformers/all-MiniLM-L6-v2'
EMBEDDING_CACHE_DIR='./.cache/huggingface'

# API 安全
API_KEY='your_api_key'

# CORS
ALLOWED_ORIGINS='http://localhost:3000,http://localhost:8501'
```

切换 embedding backend 或 embedding 模型后，建议清空本地向量库并重新导入文档，否则旧向量与新模型不兼容。

## API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/` | GET | 服务信息 |
| `/health` | GET | 健康状态 |
| `/api/v1/chat` | POST | 聊天接口 |
| `/api/v1/chat/sessions` | GET | 会话列表 |
| `/api/v1/documents/upload` | POST | 上传文档 |
| `/api/v1/documents` | GET | 列出文档 |
| `/api/v1/documents/{doc_id}` | DELETE | 删除文档 |
| `/api/v1/models` | GET | 运行时模型列表 |
| `/api/v1/providers` | GET/POST | Provider 管理 |

## 许可证

MIT License

## 文档导航

- 根目录只保留入口级文档：`README.md`、`QUICKSTART.md`、`CLAUDE.md`、`KNOWN_FAILURES.md`、`claude-progress.txt`
- 详细技术说明已下沉到 `docs/`：
  - [项目总览](./docs/project-overview.md)
  - [架构说明](./docs/architecture.md)
  - [开发规范](./docs/conventions.md)
