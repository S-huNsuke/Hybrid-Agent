# Hybrid-Agent 项目技术分析文档

> 生成日期：2026-04-12

---

## 1. 项目概述

**Hybrid-Agent** 是一个基于 **Agentic RAG**（智能体增强检索生成）架构的高级智能助手系统。系统通过 LangGraph StateGraph 实现多阶段推理流水线，集成了混合检索、内容质量自评估和智能模型自适应切换能力。

**核心定位**：企业级 RAG 问答系统，支持私有知识库构建与多轮对话。

**运行模式**：CLI / FastAPI RESTful API / Streamlit Web UI 三种方式。

---

## 2. 设计目标

| 目标 | 具体实现 |
|------|----------|
| **高精准召回** | 四路混合检索（BM25 + 向量 + HyDE + 子问题）+ RRF 融合 |
| **高质量生成** | SELF-RAG 自我反思机制，低质检索结果触发重试（最多 2 次） |
| **多模型自适应** | 根据问题复杂度自动在 Qwen3 / DeepSeek-V3 之间切换 |
| **查询理解增强** | 意图分类 + HyDE 改写 + 子问题分解，提升复杂问题处理能力 |
| **长对话支持** | TTLCache + SQLite 持久化 + 自动摘要压缩（每 20 轮触发） |
| **生产可用性** | 完整错误处理、API 降级策略、安全防护、Docker 部署支持 |
| **扩展性** | 分层架构，检索路径/工具/模型均可独立扩展 |

---

## 3. 技术栈

### 3.1 总览

| 层级 | 技术 | 说明 |
|------|------|------|
| **LLM** | Qwen3-Omni-Flash, DeepSeek-V3 | 双模型自适应，通过 DashScope / 兼容 OpenAI 协议接入 |
| **流程编排** | LangGraph >= 1.1.2 | 有状态 StateGraph，实现 Agentic RAG 节点流水线 |
| **LLM 框架** | LangChain >= 1.2.12 | 消息处理、提示词管理、工具调用 |
| **向量数据库** | ChromaDB >= 0.4.22 | 持久化向量存储，语义相似度检索 |
| **嵌入模型** | DashScope text-embedding-v4 | 文本向量化 |
| **稀疏检索** | rank-bm25 >= 0.2.2 | BM25 算法，字符 bigram 分词（无 jieba 依赖） |
| **重排序** | DashScope gte-rerank | 语义重排序，降级为 ContentReviewer 评分 |
| **关系数据库** | SQLite + SQLAlchemy >= 2.0.48 | 文档元数据、BM25 索引、会话摘要持久化 |
| **Web API** | FastAPI >= 0.104.0 + Uvicorn | 异步 RESTful 服务 |
| **Web UI** | Streamlit >= 1.55.0 | 交互式问答界面 |
| **缓存** | cachetools >= 5.3.0 (TTLCache) | 会话管理，LRU 内容审查缓存 |
| **文档处理** | pypdf, python-docx, unstructured, python-pptx, openpyxl | 多格式文档解析 |
| **网页搜索** | duckduckgo-search >= 4.0.0 | 实时网络检索（可选工具） |
| **包管理** | uv | 高速 Python 包管理器 |
| **容器化** | Docker + Docker Compose | 生产部署支持 |

### 3.2 外部 API 依赖

| 服务 | 用途 | 环境变量 |
|------|------|----------|
| DashScope (阿里云) | LLM 生成（Qwen3-Omni）、嵌入、重排、查询理解 | `QWEN_API_KEY`, `TONGYI_EMBEDDING_API_KEY` |
| DeepSeek API | 高级推理生成 | `DEEPSEEK_API_KEY` |

---

## 4. 系统架构

### 4.1 目录结构

```
Hybrid-Agent/
├── src/hybrid_agent/              # Python 主代码
│   ├── agent/                     # Agent 层（LangGraph 编排）
│   ├── api/                       # FastAPI 服务层（auth/admin/providers/routes）
│   ├── cli/                       # CLI 交互入口
│   ├── core/                      # RAG 核心引擎
│   ├── llm/                       # 模型解析与选择
│   └── web/                       # Streamlit Web 应用
├── frontend/                      # Vue 3 前端
├── tests/                         # Python + E2E 测试
├── docs/                          # 架构、规范、计划文档
├── scripts/                       # 检查与辅助脚本
├── alembic/                       # 数据库迁移
├── grafana/                       # Grafana provisioning / dashboards
├── prometheus/                    # Prometheus 配置与规则
├── pyproject.toml
├── Dockerfile
└── docker-compose.yml
```

### 4.2 Agentic RAG 流程图

```
用户输入 (original_query)
        │
        ▼
┌─────────────────┐
│  understand_query│  ← 意图分类(5类) + HyDE 改写 + 子问题分解
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│retrieval_decision│  ← 路由：direct / math_code → 直接生成
└────────┬────────┘         其他 → 进入检索流程
         │
         ▼
┌─────────────────┐
│ hybrid_retrieve  │  ← 四路并发 + RRF 融合
│  Path A: Dense   │
│  Path B: BM25    │
│  Path C: HyDE    │
│  Path D: SubQuery│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  post_process    │  ← DashScope gte-rerank + 上下文压缩
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  self_reflect    │  ← ContentReviewer SELF-RAG 评分
└────────┬────────┘
         │ score < 阈值 且 iteration < 2
         ├──────────────────────────────────→ 回到 hybrid_retrieve
         │ score ≥ 阈值 或 达到最大迭代
         ▼
┌─────────────────┐
│    generate      │  ← 调用 LLM 生成最终回答 + 来源归因
└─────────────────┘
```

---

## 5. 核心模块详解

### 5.1 查询理解（`query_understanding.py`）

三层查询增强：

**IntentRouter** — 意图分类（使用 qwen-turbo）
- `direct`：日常闲聊，跳过检索
- `rag_only`：知识库可解答
- `web_only`：需实时网络信息
- `hybrid`：知识库 + 网络结合
- `math_code`：数学计算 / 代码推理

**HyDERewriter** — 假设文档嵌入改写
- 先生成假设性回答（≤100 字），再用其嵌入向量检索
- 提升稀疏、模糊问题的召回质量

**SubQueryDecomposer** — 子问题分解
- 触发条件：查询 > 100 字符（`COMPLEX_QUERY_THRESHOLD`）
- 拆解为 2-3 个子问题，各自独立检索后 RRF 合并

---

### 5.2 混合检索（`hybrid_retriever.py`）

**四路检索并发架构**（asyncio.gather）：

| 路径 | 方法 | 始终激活 |
|------|------|----------|
| Path A | Dense 向量检索（ChromaDB） | 是 |
| Path B | BM25 稀疏检索（SQLite） | 是 |
| Path C | HyDE 向量检索 | 条件激活（意图非 direct） |
| Path D | 子问题并行检索 | 条件激活（查询超阈值） |

**RRF 融合算法**：
```
score(d) = Σ 1/(k + rank_i(d))   k = 60
```
- 以 chunk_id 或内容前 200 字符去重
- 结果携带来源标记（`retrieval_path` 字段）

---

### 5.3 重排序（`reranker.py`）

两级降级策略：
1. **主选**：DashScope gte-rerank（最多 20 个候选块）
2. **降级**：ContentReviewer 四维评分（相关性/完整性/时效性/可信度）

---

### 5.4 自适应模型选择（`model_selector.py`）

**复杂度评分算法**：

| 维度 | 条件 | 加分 |
|------|------|------|
| 长度 | > 300 字 | +0.3 |
| 长度 | > 1000 字 | 再 +0.3 |
| 语义 | 含"为什么/如何/分析/比较"等 | +0.2 |
| 代码 | 含反引号或 `//` | +0.2 |

- 总分 ≥ 0.4 → **DeepSeek-V3**（深度推理）
- 总分 < 0.4 → **Qwen3-Omni-Flash**（快速响应）
- 支持手动强制指定模型

---

### 5.5 SELF-RAG 内容审查（`content_reviewer.py`）

- 四维评分：相关性、完整性、时效性、可信度（总分 0-10）
- **LRU 缓存**：以 SHA256 哈希为键，缓存最多 1000 条审查结果
- **批量优化**：多条内容一次 API 调用批量审查
- 动态阈值：根据问题复杂度自动调整最低分要求
- 自动过滤低分内容，触发迭代重检索（最多 2 次）

---

### 5.6 会话管理（`session_manager.py`）

| 特性 | 实现 |
|------|------|
| 快速存取 | TTLCache（maxsize=1000，TTL=2小时） |
| 持久化 | SQLite `conversation_summaries` 表 |
| 摘要触发 | 每 20 轮对话自动压缩 |
| 摘要模型 | qwen-turbo，最多 300 token |
| 输入窗口 | 压缩最近 40 条消息 + 融合旧摘要 |

---

### 5.7 文档处理（`document_processor.py`）

**支持格式**：PDF, DOCX, TXT, Markdown, PPTX, XLSX, JSON

**分割策略**：
- 父级分块：chunk_size=2000，overlap=400（向量存储用）
- 子级分块：chunk_size=500，overlap=100（备用）
- 分隔符优先级：`\n\n` → `\n` → 中文句号 → 英文标点

---

## 6. 数据库设计

```text
DATABASE_URL / SQLite fallback
├── documents               # 文档元数据
├── bm25_chunks             # BM25 稀疏索引
├── conversation_summaries  # 会话摘要
├── users / groups          # 认证与组织
├── user_groups             # 成员关系
├── chat_sessions           # 会话持久化
├── llm_usage_logs          # 使用日志
└── providers               # Provider 配置

ChromaDB（本地开发默认）
└── 向量集合                # 文档块 embedding
```

---

## 7. API 接口

### FastAPI 端点

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/api/v1/chat` | 聊天（支持流式 SSE） |
| GET | `/api/v1/chat/sessions` | 会话列表 |
| POST | `/api/v1/documents/upload` | 上传文档 |
| GET | `/api/v1/documents` | 列出所有文档 |
| DELETE | `/api/v1/documents/{doc_id}` | 删除文档 |
| GET | `/api/v1/models` | 获取运行时模型列表 |
| GET/POST | `/api/v1/providers` | Provider 管理 |

### 安全机制

- 可选 API Key Header 认证
- CORS 白名单（`ALLOWED_ORIGINS` 环境变量）
- 文件上传：50MB 大小限制、格式白名单、路径遍历防护
- SQLAlchemy ORM 参数化查询（防 SQL 注入）

---

## 8. 关键参数配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| RRF k 值 | 60 | 倒数排名融合参数 |
| 每路检索 K | 10 | 各路召回数量 |
| Rerank top-K | 4 | 重排后保留数量 |
| 最终返回 K | 4 | 生成阶段上下文块数 |
| 复杂度阈值 | 0.4 | 切换高级模型阈值 |
| SELF-RAG 阈值 | 0.5 | 触发重检索评分下限 |
| 最大迭代次数 | 2 | SELF-RAG 最大重试 |
| 父块大小 | 2000 字符 | 文档分块粒度 |
| 父块重叠 | 400 字符 | 分块重叠区域 |
| 会话 TTL | 7200 秒 | 2 小时会话超时 |
| 摘要触发轮数 | 20 | 超过后自动压缩 |

---

## 9. 部署方式

### 环境变量（`.env`）

```env
DEEPSEEK_API_KEY=...          # 高级模型
QWEN_OMNI_API_KEY=...         # 基础模型
QWEN_API_KEY=...              # 查询理解 / 摘要
TONGYI_EMBEDDING_API_KEY=...  # 向量嵌入

API_KEY=...                   # API 认证密钥（可选）
ALLOWED_ORIGINS=...           # CORS 允许来源
```

### 启动命令

```bash
# CLI 模式
uv run hybrid-agent

# API 服务
PYTHONPATH=src uv run uvicorn hybrid_agent.api.main:app --host 0.0.0.0 --port 8000

# Web UI
PYTHONPATH=src uv run streamlit run src/hybrid_agent/web/app.py

# Docker
docker compose up -d
```

---

## 10. 设计模式总结

| 模式 | 应用场景 |
|------|----------|
| **单例模式** | `get_rag_system()`, `get_vector_store()` 等全局实例 |
| **工厂模式** | `build_agent()`, `get_base_model()` 模型创建 |
| **策略模式** | 多路检索策略、Reranker 降级策略 |
| **状态机模式** | LangGraph StateGraph Agentic RAG 流程 |
| **装饰器模式** | StructuredTool 工具定义 |
| **降级模式** | DashScope API 失败 → ContentReviewer 评分排序 |

---

## 11. 架构亮点

1. **Agentic RAG**：非单轮问答，而是具备意图理解、多路检索、自我反思的智能体流程
2. **四路混合检索**：BM25 + Dense + HyDE + SubQuery，兼顾精确匹配与语义召回
3. **SELF-RAG 机制**：检索质量不满足时自动重试，保障最终回答质量
4. **双模型切换**：轻量 Qwen3 处理简单问题，DeepSeek-V3 处理复杂推理，兼顾速度与质量
5. **完整会话管理**：超长对话自动摘要压缩，避免上下文窗口溢出
6. **接口兼容性**：API 层未修改，核心升级对外透明

---

## 11. 企业级升级状态（2026-04-12）

### Phase 1 + Phase 2 后端完成

Phase 1 和 Phase 2 所有后端模块已在分支 `worktree-phase1-backend` 实现并通过验收。

**新增能力**：

| 能力 | 实现方式 |
|------|----------|
| 用户认证 | JWT（python-jose）+ bcrypt 密码哈希 |
| RBAC 权限 | `require_role()` 依赖工厂，3 级角色（admin / group_admin / member） |
| 文档组隔离 | ChromaDB collection per group_id + BM25 group_id 过滤 |
| API 版本化 | 所有路由迁移至 `/api/v1/`，旧路由保留兼容 |
| 开源嵌入模型 | EmbeddingFactory，BAAI/bge-m3 默认（本地推理），DashScope 可选 |
| 模型提供商管理 | 用户配置任意 OpenAI 兼容接口，Fernet 加密存储 API Key |
| 异步文档上传 | TaskStore + FastAPI BackgroundTask，支持进度轮询 |
| 监控 | Prometheus `/metrics` + structlog 结构化日志 + LLM 成本追踪 |
| Docker Compose | postgres + app + prometheus + grafana + backup，一键启动 |

**测试覆盖**：80 个后端测试（unit + integration），全部通过

**下一步**：Phase 3 前端（M9-M16），详见 `docs/superpowers/plans/2026-04-12-phase3-frontend.md`
