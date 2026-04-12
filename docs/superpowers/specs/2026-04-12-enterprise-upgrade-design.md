# Hybrid-Agent 企业级升级设计文档

**日期**：2026-04-12
**目标场景**：10-50 人内部团队 / 组级文档隔离 / 账密登录 / 监控面板 / 数据不丢
**改造策略**：渐进式最小改造 + Vue 3 前端替换
**开发规范**：全程遵循 Harness Engineering，M0 为所有模块的前置基础

---

## 一、整体架构

```
Vue 3 前端（Vite + Element Plus）
        ↓ HTTP / SSE
FastAPI /api/v1/...（JWT 认证中间件）
        ├── PostgreSQL（用户/组/文档元数据/LLM 日志）
        ├── ChromaDB（按 group_id namespace 隔离）
        └── /metrics → Prometheus → Grafana

Docker Compose 服务：
  app（FastAPI）| frontend（Nginx + Vue 3 静态）
  postgres | prometheus | grafana | backup
```

---

## 二、数据模型

### 新增表

```sql
-- 用户表
users (
  id UUID PRIMARY KEY,
  username VARCHAR(64) UNIQUE NOT NULL,
  hashed_password VARCHAR NOT NULL,
  role ENUM('admin','group_admin','member') DEFAULT 'member',
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP
)

-- 组表
groups (
  id UUID PRIMARY KEY,
  name VARCHAR(64) UNIQUE NOT NULL,
  description TEXT,
  created_at TIMESTAMP
)

-- 用户-组关联（支持一人多组）
user_groups (
  user_id UUID REFERENCES users(id),
  group_id UUID REFERENCES groups(id),
  role ENUM('group_admin','member') DEFAULT 'member',
  PRIMARY KEY (user_id, group_id)
)

-- LLM 调用成本日志
llm_usage_logs (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  session_id VARCHAR,
  model VARCHAR(64),
  prompt_tokens INT,
  completion_tokens INT,
  cost_usd DECIMAL(10,6),
  created_at TIMESTAMP
)
```

### 现有表变更

```sql
-- documents 表新增
ALTER TABLE documents ADD COLUMN group_id UUID REFERENCES groups(id);
ALTER TABLE documents ADD COLUMN uploaded_by UUID REFERENCES users(id);

-- bm25_chunks 表新增
ALTER TABLE bm25_chunks ADD COLUMN group_id UUID;
```

---

## 三、RBAC 权限矩阵

| 操作 | admin | group_admin | member |
|------|-------|-------------|--------|
| 查看本组文档 | ✓ | ✓ | ✓ |
| 上传本组文档 | ✓ | ✓ | ✓ |
| 删除本组文档 | ✓ | ✓ | ✗ |
| 查看所有组文档 | ✓ | ✗ | ✗ |
| 管理组成员 | ✓ | ✓ | ✗ |
| 创建/删除组 | ✓ | ✗ | ✗ |
| 创建用户 | ✓ | ✗ | ✗ |
| 查看监控面板 | ✓ | ✓ | ✗ |

---

## 四、API 路由总览

### 认证
```
POST /api/v1/auth/login          账密登录，返回 JWT
POST /api/v1/auth/refresh         刷新 access_token
POST /api/v1/auth/logout          登出（客户端清除 token）
GET  /api/v1/auth/me              获取当前用户信息
```

### 聊天
```
POST /api/v1/chat                 发起对话（SSE 流式响应）
GET  /api/v1/chat/sessions        获取会话列表
DELETE /api/v1/chat/sessions/{id} 删除会话
```

### 文档
```
POST   /api/v1/documents/upload        上传文档（异步，返回 task_id）
GET    /api/v1/documents/tasks/{id}    查询上传进度
GET    /api/v1/documents               列出本组文档
GET    /api/v1/documents/{id}          获取文档详情
DELETE /api/v1/documents/{id}          删除文档
```

### 管理（admin 专属）
```
POST   /api/v1/admin/users             创建用户
GET    /api/v1/admin/users             用户列表
PATCH  /api/v1/admin/users/{id}        修改用户/重置密码
DELETE /api/v1/admin/users/{id}        停用用户

POST   /api/v1/admin/groups            创建组
GET    /api/v1/admin/groups            组列表
PATCH  /api/v1/admin/groups/{id}       修改组信息
POST   /api/v1/admin/groups/{id}/members    添加成员
DELETE /api/v1/admin/groups/{id}/members/{uid} 移除成员
```

### 监控
```
GET /metrics          Prometheus 指标端点
GET /api/v1/stats     LLM 成本统计（JSON，供前端用）
```

---

## 五、Harness Engineering 开发规范

> **所有模块（M1–M16）必须在 M0 完成后才能开始实现。每个模块的开发过程均须遵守本节规范。**

### 5.1 四大核心组件

| 组件 | 作用 | 本项目中的实现 |
|------|------|--------------|
| **约束 Constrain** | 限制 Agent 能做什么 | 架构边界测试（`tests/test_architecture.py`）强制执行依赖方向 |
| **告知 Inform** | 让 Agent 知道该做什么 | `CLAUDE.md`（目录表）+ `docs/` 规范文档 |
| **验证 Verify** | 确认 Agent 做对了 | CI 流水线：ruff + mypy + pytest，通过静默，失败详细 |
| **纠正 Correct** | 出错时的恢复机制 | 失败信号简洁可读；二次失败升级人工；`KNOWN_FAILURES.md` 累积禁止行为 |

### 5.2 每个模块的开发流程

```
开始实现模块 Mx
  │
  ├─ 1. 更新 claude-progress.txt（记录当前模块 + 状态）
  │
  ├─ 2. 实现代码
  │
  ├─ 3. 本地运行检查脚本（scripts/check.py）
  │       ├─ 通过（静默）→ 提交
  │       └─ 失败 → Agent 自修复 → 再次检查
  │               └─ 二次失败 → 升级人工处理
  │
  ├─ 4. 提交前确认：
  │       - 新增函数是否有函数级注释（Google style）
  │       - 是否有对应测试（新功能必须）
  │       - 架构边界测试是否通过
  │
  ├─ 5. 提交 commit（原子提交，信息格式：feat/fix/refactor: 模块名 - 描述）
  │
  └─ 6. 更新 claude-progress.txt（标记模块完成）
         如遇到新的 Agent 失败模式 → 追加到 KNOWN_FAILURES.md
```

### 5.3 架构依赖方向规则（CI 强制执行）

```
后端依赖方向（单向，不得逆向）：
  Models / Schemas
      ↓
  Repositories（数据访问）
      ↓
  Services（业务逻辑）
      ↓
  API Routes（接口层）

  core/ 模块不得 import agent/ 模块
  api/ 模块不得直接 import core/database.py 的 ORM 模型

前端依赖方向：
  api/（HTTP 封装）← stores/（Pinia）← composables/ ← views/ / components/
  views/ 不得直接调用 api/，必须通过 stores/ 或 composables/
```

### 5.4 commit 信息规范

```
格式：<type>(<scope>): <description>

type：
  feat     新功能
  fix      Bug 修复
  refactor 重构（不改变行为）
  test     添加或修改测试
  docs     文档变更
  chore    构建/配置/依赖变更

示例：
  feat(auth): 添加 JWT 登录接口
  fix(vector): 修复 group_id 过滤条件缺失
  test(architecture): 添加后端依赖方向结构性测试
```

### 5.5 两次失败升级规则（Two-Strike Rule）

```
Agent 修复 CI 失败
  → 第一次修复后仍失败 → 允许 Agent 再尝试一次
  → 第二次修复后仍失败 → 停止，升级给人工，在 KNOWN_FAILURES.md 记录模式
```

---

## 六、实现模块拆解

### Harness 基础模块（1 个，所有模块前置）

---

#### M0：Harness Engineering 基础设施

**目标**：建立整个项目的 Agent 工作环境，让所有后续模块在约束、告知、验证、纠正四个维度上有基础保障。**此模块必须最先完成。**

**新增 / 改动文件清单**：

**① 升级 `CLAUDE.md`（目录表格式）**

```markdown
# Hybrid-Agent — Agent 工作手册

## 项目概述
企业级 RAG 问答系统。FastAPI 后端 + Vue 3 前端 + PostgreSQL + ChromaDB。
详细架构见 docs/architecture.md。

## 快速启动
\`\`\`bash
# 后端
cd /Users/caojun/Desktop/Hybrid-Agent
source .venv/bin/activate
uvicorn hybrid_agent.api.main:app --reload

# 前端
cd frontend && pnpm dev

# 全部检查（通过静默，失败输出错误）
python scripts/check.py
\`\`\`

## 架构约束（CI 强制执行，违反则构建失败）
- 依赖方向：Models → Repositories → Services → API Routes
- core/ 不得 import agent/
- api/ 不得直接使用 ORM 模型，必须通过 services/
- 详见 docs/architecture.md

## 代码规范
- 所有函数必须有函数级注释（Google style docstring）
- Python：类型注解必须完整
- Vue：使用 <script setup> + Composition API
- 详见 docs/conventions.md

## 测试要求
- 新功能必须附带测试
- 运行：python -m pytest tests/ --tb=short -q
- 结构性测试：tests/test_architecture.py（不得删除或跳过）

## 已知失败模式（禁止重复）
见 KNOWN_FAILURES.md
```

**② `docs/architecture.md`**（架构决策记录）
- 系统分层图（core / agent / api / web）
- 依赖方向规则（文字 + ASCII 图）
- ChromaDB namespace 隔离策略
- JWT 认证流程图
- 每个重大技术决策的选型理由

**③ `docs/conventions.md`**（代码规范详细版）
- Python 函数注释模板（Google style）
- 类型注解要求
- SQLAlchemy 模型命名规范
- Vue 组件命名规范（PascalCase 文件名，kebab-case 使用）
- CSS 变量使用规范（禁止硬编码颜色值）
- 禁止使用 `import *`
- 必须使用 `uv`，不得使用 `pip`

**④ `tests/test_architecture.py`**（结构性测试）
```python
"""
架构边界验证测试。
验证后端依赖方向：Models → Repositories → Services → API。
此测试由 CI 强制执行，失败表示架构边界被违反。
"""
import ast
from pathlib import Path
import pytest

def get_imports(filepath: Path) -> list[str]:
    """解析 Python 文件，返回所有 import 的模块名列表。"""
    tree = ast.parse(filepath.read_text())
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports

def test_api_routes_do_not_import_repositories():
    """API 路由层不得直接导入 Repository 层，必须通过 Service 层。"""
    for f in Path("src/hybrid_agent/api/routes").rglob("*.py"):
        for imp in get_imports(f):
            assert "repositories" not in imp, (
                f"{f.name}: API 路由直接导入了 Repository '{imp}'。"
                f"请改为在对应 service 中封装，再从 service 调用。"
            )

def test_core_does_not_import_agent():
    """core/ 模块不得依赖 agent/ 模块，避免循环依赖。"""
    for f in Path("src/hybrid_agent/core").rglob("*.py"):
        for imp in get_imports(f):
            assert "hybrid_agent.agent" not in imp, (
                f"{f.name}: core/ 模块导入了 agent/ 模块 '{imp}'。"
                f"依赖方向应为 core → agent，不得逆向。"
            )
```

**⑤ `.github/workflows/ci.yml`**（CI 流水线）
```yaml
name: CI

on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - name: Lint (ruff)
        run: uv run ruff check src/ --output-format=concise
      - name: Type check (mypy)
        run: uv run mypy src/hybrid_agent/ --ignore-missing-imports
      - name: Tests (pytest)
        run: uv run pytest tests/ --tb=short -q
        # -q 静默通过，--tb=short 简洁失败信息，供 Agent 自修复

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - run: pnpm install
      - run: pnpm lint
      - run: pnpm type-check
      - run: pnpm test:unit --reporter=dot
        # dot reporter：通过显示点，失败显示详情
```

**⑥ `scripts/check.py`**（本地一键检查，Agent 可直接调用）
```python
"""
本地检查脚本：运行所有 lint/type/test 检查。
通过时完全静默（exit 0）。
失败时输出简洁错误信息（exit 2），供 Agent 自修复。
用法：python scripts/check.py
"""
import subprocess
import sys

CHECKS = [
    ["uv", "run", "ruff", "check", "src/", "--output-format=concise"],
    ["uv", "run", "mypy", "src/hybrid_agent/", "--ignore-missing-imports"],
    ["uv", "run", "pytest", "tests/", "--tb=short", "-q"],
]

errors = []
for cmd in CHECKS:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        errors.append(f"[FAILED] {' '.join(cmd)}\n{result.stdout}{result.stderr}")

if errors:
    print("\n".join(errors))
    sys.exit(2)
# 全部通过：完全静默
```

**⑦ `claude-progress.txt`**（跨会话进度桥接，纳入版本控制）
```
# Hybrid-Agent 企业级升级进度
# 每次开始新会话前，Agent 必须先读取此文件

当前阶段：M0 进行中
已完成模块：无
下一步：完成 M0 所有文件后，开始 M1

## 模块状态
[ ] M0  Harness 基础设施
[ ] M1  PostgreSQL + Alembic
[ ] M2  用户认证（JWT）
[ ] M3  用户/组管理 + RBAC
[ ] M4  文档组隔离
[ ] M5  API 路由版本化
[ ] M6  文档上传异步化
[ ] M7  监控
[ ] M8  Docker Compose 编排
[ ] M9  Vue 3 脚手架
[ ] M10 设计系统
[ ] M11 登录页 + 路由守卫
[ ] M12 主布局（AppShell）
[ ] M13 聊天界面
[ ] M14 文档管理页
[ ] M15 管理后台
[ ] M16 个人设置页
```

**⑧ `KNOWN_FAILURES.md`**（初始为空，持续累积）
```markdown
# 已知 Agent 失败模式

> 每次发现新的 Agent 错误后，在此添加一条规则。
> 这些规则会在 CLAUDE.md 中被引用，防止重复犯错。

## 规则列表

（初始为空，随项目推进持续累积）
```

**验收标准**：
- `python scripts/check.py` 对当前代码库无报错（静默通过）
- `pytest tests/test_architecture.py -v` 通过
- `.github/workflows/ci.yml` push 后 GitHub Actions 绿色
- `CLAUDE.md` 已更新为目录表格式
- `claude-progress.txt` 已纳入版本控制

---

### 后端模块（8 个）

---

#### M1：PostgreSQL + Alembic 数据库迁移

**目标**：将 SQLite 替换为 PostgreSQL，建立迁移管理机制。

**改动文件**：
- `pyproject.toml`：新增 `asyncpg`, `alembic`, `psycopg2-binary`
- `src/hybrid_agent/core/config.py`：`DATABASE_URL` 从环境变量读取
- `src/hybrid_agent/core/database.py`：engine 改为 `create_async_engine`，新增 users/groups/user_groups/llm_usage_logs 模型
- 新增 `alembic.ini` + `alembic/env.py` + 初始迁移文件

**验收标准**：
- `alembic upgrade head` 成功建表
- 原有文档增删查功能不受影响

---

#### M2：用户认证（JWT）

**目标**：账密登录、JWT 签发/验证、token 刷新。

**新增文件**：
- `src/hybrid_agent/api/auth/`
  - `router.py`：`/login` `/refresh` `/logout` `/me` 路由
  - `service.py`：密码验证、JWT 生成/解析
  - `dependencies.py`：`get_current_user(token)` 依赖注入函数
  - `schemas.py`：`LoginRequest`, `TokenResponse`, `UserInfo`

**依赖新增**：`python-jose[cryptography]`, `passlib[bcrypt]`

**JWT Payload**：
```json
{ "sub": "user_id", "group_ids": ["gid1"], "role": "member", "exp": 1234567890 }
```

**验收标准**：
- 正确密码返回 token，错误密码返回 401
- 过期 token 返回 401，有效 token 正确解析用户信息

---

#### M3：用户/组管理 + RBAC 中间件

**目标**：管理员可增删用户/组，权限中间件自动校验角色。

**新增文件**：
- `src/hybrid_agent/api/admin/`
  - `router.py`：用户/组 CRUD 路由
  - `service.py`：业务逻辑
  - `schemas.py`：请求/响应模型
- `src/hybrid_agent/api/auth/permissions.py`：
  - `require_role(*roles)` 装饰器工厂
  - `require_group_access(group_id)` 组访问校验

**用法示例**：
```python
@router.delete("/{doc_id}", dependencies=[Depends(require_role("admin","group_admin"))])
async def delete_document(...): ...
```

**验收标准**：
- member 调用删除接口返回 403
- group_admin 只能操作本组资源

---

#### M4：文档组隔离（ChromaDB Namespace）

**目标**：不同组的文档在向量库和 BM25 中完全隔离。

**改动文件**：
- `src/hybrid_agent/core/vector.py`：
  - `VectorStore.__init__` 接收 `group_id` 参数
  - collection name 改为 `f"group_{group_id}"`
- `src/hybrid_agent/core/hybrid_retriever.py`：
  - `BM25Retriever.search(query, k, group_id)` 增加 group_id 过滤
  - `MultiPathRetriever` 构造时传入 group_id
- `src/hybrid_agent/core/rag_system.py`：
  - 所有方法签名增加 `group_id` 参数
  - `get_multi_path_retriever(group_id)` 按组返回实例
- `src/hybrid_agent/api/routes/`：从 `current_user.group_ids` 获取 group_id 注入

**验收标准**：
- A 组用户上传的文档不出现在 B 组的检索结果中
- admin 可通过参数跨组检索

---

#### M5：API 路由版本化

**目标**：所有路由统一迁移到 `/api/v1/`，保留向后兼容。

**改动文件**：
- `src/hybrid_agent/api/main.py`：
  - 注册 `v1_router`，prefix `/api/v1`
  - 旧路由 `/api/chat` 等做 301 重定向到 `/api/v1/chat`（过渡期）
- 各 `routes/*.py`：router prefix 去掉 `/api`

**验收标准**：
- `/api/v1/health` 正常响应
- 旧路径返回 301 跳转

---

#### M6：文档上传异步化

**目标**：上传接口立即返回，后台处理，前端可轮询进度。

**新增文件**：
- `src/hybrid_agent/core/task_store.py`：
  - 基于内存 dict 存储 `{task_id: {status, progress, error}}`
  - `create_task()`, `update_task()`, `get_task()`

**改动文件**：
- `src/hybrid_agent/api/routes/documents.py`：
  - `POST /upload` 改为：生成 task_id → 启动 BackgroundTask → 立即返回 task_id
  - 新增 `GET /tasks/{task_id}` 查询进度端点
- `src/hybrid_agent/core/rag_system.py`：
  - `add_document()` 接受 `task_callback` 参数，处理各阶段回调进度

**进度阶段定义**：
```
10% → 文件保存完成
30% → 文档解析完成
60% → 向量化写入完成
85% → BM25 索引完成
100% → 全部完成
```

**验收标准**：
- 上传 10MB PDF 接口在 200ms 内返回
- 轮询 task_id 可看到进度从 10% 到 100%

---

#### M7：监控（结构化日志 + Prometheus + LLM 成本）

**目标**：暴露指标端点，记录 LLM 调用成本，输出结构化日志。

**依赖新增**：`prometheus-fastapi-instrumentator`, `structlog`

**改动文件**：
- `src/hybrid_agent/api/main.py`：
  ```python
  Instrumentator().instrument(app).expose(app)  # 自动 /metrics 端点
  ```
- `src/hybrid_agent/core/config.py`：新增 LLM 单价常量
  ```python
  LLM_PRICING = {
      "qwen3-omni-flash": {"input": 0.0003, "output": 0.0006},  # USD/1K tokens
      "deepseek-v3": {"input": 0.00027, "output": 0.0011},
  }
  ```
- `src/hybrid_agent/agent/agentic_rag_graph.py`：
  - `generate` 节点完成后调用 `log_llm_usage(user_id, model, usage)`
- `src/hybrid_agent/core/logging.py`（新增）：
  - `configure_logging()` 配置 structlog JSON 输出
  - 所有模块 `import structlog; logger = structlog.get_logger()`

**新增文件**：
- `prometheus.yml`：scrape_configs 指向 `app:8000/metrics`
- `grafana/dashboards/hybrid_agent.json`：4 个面板的 Grafana dashboard 模板

**验收标准**：
- `GET /metrics` 返回 Prometheus 格式文本
- 每次 LLM 调用后 `llm_usage_logs` 表有新记录
- 日志输出为 JSON 格式

---

#### M8：Docker Compose 完整编排

**目标**：一条命令启动所有服务。

**改动文件** `docker-compose.yml`：

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment: [POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD]
    volumes: [postgres_data:/var/lib/postgresql/data]
    healthcheck: pg_isready

  app:
    build: .
    depends_on: [postgres]
    environment: [DATABASE_URL, JWT_SECRET, ...]
    ports: ["8000:8000"]

  frontend:
    build: ./frontend
    ports: ["80:80"]
    depends_on: [app]

  prometheus:
    image: prom/prometheus:latest
    volumes: [./prometheus.yml:/etc/prometheus/prometheus.yml]
    ports: ["9090:9090"]

  grafana:
    image: grafana/grafana:latest
    volumes: [grafana_data:/var/lib/grafana, ./grafana:/etc/grafana/provisioning]
    ports: ["3000:3000"]

  backup:
    image: postgres:16-alpine
    entrypoint: |
      sh -c "while true; do
        pg_dump $$DATABASE_URL > /backup/$$(date +%Y%m%d_%H%M).sql
        find /backup -mtime +7 -delete
        sleep 86400
      done"
    volumes: [./backup:/backup]
    depends_on: [postgres]

volumes: [postgres_data, grafana_data]
```

**验收标准**：
- `docker-compose up -d` 全部服务健康启动
- Grafana `localhost:3000` 可正常访问

---

### 前端模块（8 个）

---

#### M9：Vue 3 项目脚手架

**目标**：初始化前端项目，建立工程化基础。

**目录**：`/frontend`（与 `src/` 并列）

**技术栈**：
- Vite 5 + Vue 3.4（`<script setup>`）
- Element Plus 2（UI 组件库）
- Pinia 2（状态管理）
- Vue Router 4
- Axios（HTTP 请求 + 拦截器）
- `@vueuse/core`（组合式工具函数）
- `markdown-it` + `highlight.js`（Markdown 渲染）

**目录结构**：
```
frontend/
├── src/
│   ├── api/           HTTP 请求封装（auth.js, chat.js, documents.js, admin.js）
│   ├── stores/        Pinia store（user.js, chat.js, documents.js）
│   ├── router/        路由定义 + 导航守卫
│   ├── composables/   可复用逻辑（useSSE, useUpload, useTheme）
│   ├── components/    通用组件
│   ├── views/         页面组件
│   ├── styles/        全局样式 + CSS 变量
│   └── main.js
├── Dockerfile
└── nginx.conf
```

**验收标准**：`pnpm dev` 启动无报错，路由跳转正常

---

#### M10：设计系统（Design Tokens + 主题）

**目标**：定义极简白视觉规范，全局 CSS 变量，支持深色模式切换。

**新增文件**：`frontend/src/styles/tokens.css`

```css
:root {
  /* 颜色 */
  --color-bg:          #FFFFFF;
  --color-bg-subtle:   #F9FAFB;
  --color-bg-muted:    #F3F4F6;
  --color-border:      #E5E7EB;
  --color-border-muted:#F3F4F6;
  --color-text:        #111827;
  --color-text-muted:  #6B7280;
  --color-text-subtle: #9CA3AF;
  --color-accent:      #7C3AED;   /* Claude 紫，用于主操作按钮 */
  --color-accent-hover:#6D28D9;
  --color-user-bubble: #F3F4F6;   /* 用户消息气泡 */
  --color-code-bg:     #1E1E2E;   /* 代码块深色背景 */

  /* 间距（8px 网格） */
  --space-1: 4px;   --space-2: 8px;
  --space-3: 12px;  --space-4: 16px;
  --space-6: 24px;  --space-8: 32px;

  /* 字体 */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  --font-size-sm: 13px;
  --font-size-base: 14px;
  --font-size-lg: 16px;

  /* 圆角 */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;

  /* 阴影（极轻） */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 6px rgba(0,0,0,0.07);

  /* 过渡 */
  --transition: 150ms ease;
}

[data-theme="dark"] {
  --color-bg:         #0D0D0D;
  --color-bg-subtle:  #141414;
  --color-bg-muted:   #1A1A1A;
  --color-border:     #2A2A2A;
  --color-text:       #F9FAFB;
  --color-text-muted: #9CA3AF;
  --color-user-bubble:#1E1E1E;
}
```

**Element Plus 主题覆盖**：`styles/element-override.css`
- 主色改为 `#7C3AED`
- 去除默认阴影，使用自定义 `--shadow-sm`
- 输入框 border-radius 改为 `--radius-sm`

**验收标准**：深色/浅色切换时全页颜色平滑过渡，无闪烁

---

#### M11：登录页 + 路由守卫

**目标**：账密登录，未登录自动跳转，token 过期自动刷新。

**新增文件**：
- `frontend/src/views/LoginView.vue`
- `frontend/src/router/index.js`
- `frontend/src/api/auth.js`
- `frontend/src/stores/user.js`

**页面设计**（参考 Claude 登录页）：
```
页面居中卡片（宽 360px）
┌──────────────────────┐
│  [Logo]  Hybrid Agent│
│                      │
│  用户名 ____________ │
│  密  码 ____________ │
│                      │
│  [      登 录      ] │  ← 紫色主按钮，全宽
│                      │
└──────────────────────┘
背景：纯白 #FFFFFF
无注册入口（内部系统，admin 创建账号）
```

**路由守卫逻辑**：
```
访问受保护路由
  → 有 token？
      → 是：放行
      → 否：跳转 /login，记录 redirect 参数
登录成功后跳转到 redirect 或默认 /chat
```

**Axios 拦截器**（`src/api/request.js`）：
- 请求拦截：自动添加 `Authorization: Bearer <token>`
- 响应拦截：401 时自动调用 `/auth/refresh`，刷新失败跳转登录

**验收标准**：
- 未登录访问 `/chat` 跳转 `/login`
- 登录成功跳转目标页
- token 过期后自动无感刷新

---

#### M12：主布局（AppShell）

**目标**：实现顶栏 + 侧边栏 + 内容区的整体框架。

**新增文件**：
- `frontend/src/components/layout/AppShell.vue`
- `frontend/src/components/layout/AppHeader.vue`
- `frontend/src/components/layout/AppSidebar.vue`

**布局规范**：
```
┌─────────────────────────────────────────────┐  height: 48px
│ [≡]  Hybrid Agent    [当前组：研发部]  [头像]│  顶栏
├─────────────┬───────────────────────────────┤
│             │                               │
│  侧边栏     │   <router-view />             │
│  240px      │   内容区（自适应）             │
│  bg-subtle  │   bg: #FFFFFF                 │
│             │                               │
│  导航项：   │                               │
│  ○ 对话     │                               │
│  ○ 文档库   │                               │
│  ─────────  │                               │
│  ○ 管理后台 │                               │  仅 admin 显示
│  ─────────  │                               │
│  ○ 个人设置 │                               │
│             │                               │
└─────────────┴───────────────────────────────┘

移动端（< 768px）：侧边栏收起为抽屉
```

**侧边栏导航项样式**：
- 未激活：`color: --text-muted`，无背景
- 激活：`color: --color-accent`，`background: --color-bg-muted`，左侧 2px 紫色边线
- hover：`background: --color-bg-muted`，`transition: --transition`

**验收标准**：
- 路由切换侧边栏高亮正确
- 移动端侧边栏抽屉正常开关

---

#### M13：聊天界面

**目标**：核心功能页，流式输出 + Markdown 渲染 + 来源引用展示。

**新增文件**：
- `frontend/src/views/ChatView.vue`
- `frontend/src/components/chat/MessageList.vue`
- `frontend/src/components/chat/MessageItem.vue`
- `frontend/src/components/chat/ChatInput.vue`
- `frontend/src/components/chat/SourcePanel.vue`
- `frontend/src/composables/useSSE.js`

**页面布局**：
```
┌──────────────────────────────────────────┐
│ 会话列表（侧边栏内嵌）  │  消息区域       │
│ ─────────────────      │                 │
│ + 新建对话             │  [AI 消息]      │
│                        │  内容全宽，无气泡│
│ ▸ 今天                 │  Markdown 渲染  │
│   会话标题...          │                 │
│   会话标题...          │  [用户消息]     │
│                        │  右对齐，灰色气泡│
│ ▸ 昨天                 │                 │
│   ...                  │  [来源引用]     │
│                        │  折叠面板，      │
│                        │  点击展开文档片段│
│                        │                 │
│                        ├─────────────────┤
│                        │ 输入框          │
│                        │ [附件] [发送]   │
└────────────────────────┴─────────────────┘
```

**消息气泡规范**（对标 Claude 风格）：
- AI 消息：无气泡，左对齐，全宽，`font-size: 14px`，`line-height: 1.7`
- 用户消息：右对齐，圆角气泡，`background: --color-user-bubble`
- AI 消息底部：显示模型名 + 耗时（小字，muted 色）

**流式输出**（`useSSE.js`）：
```javascript
// EventSource 封装，支持中止
const { start, stop, isStreaming } = useSSE('/api/v1/chat', {
  onChunk: (text) => appendToLastMessage(text),
  onDone: (sources) => attachSources(sources),
  onError: (err) => showError(err),
})
```

**来源引用组件**（`SourcePanel.vue`）：
```
▼ 参考了 3 个来源        ← 默认折叠，点击展开
  ┌──────────────────┐
  │ 📄 产品手册.pdf  │
  │ 第 12 页 · 相关度 92%  │
  │ "...对应文档片段内容..." │
  └──────────────────┘
```

**Markdown 渲染**：`markdown-it` + `highlight.js`
- 代码块：深色背景 `--color-code-bg`，一键复制按钮
- 表格：带边框，stripe 行
- 行内代码：`background: --color-bg-muted`，monospace

**模型选择器**（输入框左侧）：
- 下拉选项：自动 / Qwen3 快速 / DeepSeek 深思
- 默认：自动

**验收标准**：
- 流式输出逐字显示，无闪烁
- 来源引用折叠/展开正常
- 代码块高亮 + 复制正常

---

#### M14：文档管理页

**目标**：本组文档的上传、列表查看、删除，带进度显示。

**新增文件**：
- `frontend/src/views/DocumentsView.vue`
- `frontend/src/components/documents/UploadZone.vue`
- `frontend/src/components/documents/DocumentList.vue`
- `frontend/src/composables/useUpload.js`

**页面布局**：
```
┌─────────────────────────────────────────┐
│ 文档库                        [上传文档] │
├─────────────────────────────────────────┤
│ ┌─────────────────────────────────────┐ │
│ │  拖拽文件到此处，或点击选择          │ │  上传区（虚线框）
│ │  支持 PDF / DOCX / TXT / MD 等      │ │
│ └─────────────────────────────────────┘ │
│                                         │
│  上传中：报告.pdf  ████████░░  80%      │  上传进度条
│                                         │
├─────────────────────────────────────────┤
│ 文件名          大小   上传时间   操作  │
│ ─────────────────────────────────────── │
│ 产品手册.pdf    2.3MB  04-11     [删除] │
│ 技术规范.docx   1.1MB  04-10     [删除] │
└─────────────────────────────────────────┘
```

**上传流程**（`useUpload.js`）：
```
选择/拖拽文件
  → POST /api/v1/documents/upload
  → 获取 task_id
  → 每 1.5 秒轮询 /tasks/{task_id}
  → progress 到 100% 刷新列表
  → 失败显示错误原因
```

**验收标准**：
- 拖拽上传文件，进度条实时更新
- 上传完成自动刷新列表
- 删除有二次确认弹窗

---

#### M15：管理后台

**目标**：admin 专属页，管理用户和组。仅在角色为 admin 时菜单可见。

**新增文件**：
- `frontend/src/views/AdminView.vue`
- `frontend/src/components/admin/UserTable.vue`
- `frontend/src/components/admin/GroupTable.vue`
- `frontend/src/components/admin/CreateUserModal.vue`
- `frontend/src/components/admin/CreateGroupModal.vue`

**页面结构**：
```
标签页：[用户管理]  [组管理]

用户管理：
  [+ 创建用户]
  用户名    角色    所属组    状态    操作
  ─────────────────────────────────────
  alice     admin   研发部    启用    [编辑] [重置密码]
  bob       member  研发部    启用    [编辑] [停用]

组管理：
  [+ 创建组]
  组名      成员数   操作
  ──────────────────────
  研发部    12人     [查看成员] [编辑] [删除]
```

**验收标准**：
- 非 admin 路由守卫重定向
- 创建用户/组表单校验正常
- 重置密码生成随机密码并提示复制

---

#### M16：个人设置页

**目标**：修改密码、主题切换、查看本人所属组信息。

**新增文件**：
- `frontend/src/views/SettingsView.vue`

**页面内容**：
```
个人信息
  用户名：alice（不可修改）
  角色：member
  所属组：研发部

修改密码
  当前密码 ___________
  新密码   ___________
  确认密码 ___________
  [保存修改]

外观
  主题：[浅色]  [深色]  [跟随系统]
```

**验收标准**：
- 旧密码错误时显示错误提示
- 主题切换即时生效，刷新后保持

---

## 七、实现顺序

```
第零阶段（Harness 基础，必须最先完成）：
  M0

第一阶段（后端基础）：
  M1 → M2 → M3 → M4 → M5

第二阶段（后端功能）：
  M6 → M7 → M8

第三阶段（前端）：
  M9 → M10 → M11 → M12 → M13 → M14 → M15 → M16
```

**模块间依赖关系**：
- **M0 是所有模块的前置**，未完成 M0 不得开始任何其他模块
- M2 依赖 M1（需要 users 表）
- M3 依赖 M2（需要 JWT 解析）
- M4 依赖 M3（需要 group_id 来自当前用户）
- M5 独立，可与 M1-M4 并行
- M6 依赖 M4（上传需知道 group_id）
- M7 依赖 M1（LLM 日志写 DB）
- M8 依赖 M1-M7 全部完成
- 前端 M11 依赖后端 M2 接口就绪
- 前端 M13 依赖后端 M4+M5
- 前端 M14 依赖后端 M6
- 前端 M15 依赖后端 M3

**每个模块完成后必须**：
1. `python scripts/check.py` 静默通过（零错误）
2. 更新 `claude-progress.txt` 标记模块完成
3. 有新的 Agent 失败模式 → 追加到 `KNOWN_FAILURES.md`

---

## 八、不在本次范围内

- HA / 多实例部署（10-50 人规模不需要）
- SSO / LDAP 集成（已选账密登录）
- ChromaDB 替换（单机 ChromaDB 满足当前规模）
- 消息队列（BackgroundTasks 满足当前吞吐）
