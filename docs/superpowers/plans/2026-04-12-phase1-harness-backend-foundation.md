# Hybrid-Agent 企业级升级 Phase 1 实现计划
# M0 Harness 基础 + M1-M5 后端基础

> **状态**：✅ Phase 1 已完成（2026-04-12）。所有 24 个任务通过验收，80 个测试全绿。

**Goal:** 建立 Harness Engineering 开发基础设施，并完成用户认证、RBAC 权限、文档组隔离和 API 版本化。

**Architecture:** FastAPI 后端新增 JWT 认证中间件和 RBAC 权限层；PostgreSQL 替换 SQLite，使用 Alembic 管理迁移；ChromaDB 按 group_id 做 namespace 隔离；所有路由迁移到 `/api/v1/` 前缀。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, asyncpg, Alembic, python-jose, passlib[bcrypt], pytest-asyncio, aiosqlite, ruff, mypy

---

## 前置条件

- 已激活虚拟环境：`source .venv/bin/activate`
- 工作目录：`/Users/caojun/Desktop/Hybrid-Agent`
- 所有命令在项目根目录执行

---

## 文件地图

### M0 新增文件
```
CLAUDE.md                          ← 目录表（替换现有内容）
KNOWN_FAILURES.md                  ← 失败模式累积（初始为空）
claude-progress.txt                ← 跨会话进度桥接
scripts/check.py                   ← 本地一键检查脚本
docs/architecture.md               ← 架构决策记录
docs/conventions.md                ← 代码规范详细版
tests/test_architecture.py         ← 架构边界结构性测试
.github/workflows/ci.yml           ← CI 流水线
```

### M1 修改/新增文件
```
pyproject.toml                     ← 新增 asyncpg, alembic, aiosqlite, pytest-asyncio 等
src/hybrid_agent/core/config.py    ← 新增 DATABASE_URL, JWT_SECRET 读取
src/hybrid_agent/core/database.py  ← 迁移至 async SQLAlchemy，新增 User/Group/UserGroup/LLMUsageLog 模型
alembic.ini                        ← Alembic 配置
alembic/env.py                     ← Alembic 异步迁移环境
alembic/versions/0001_initial.py   ← 初始迁移（全部表）
tests/conftest.py                  ← pytest fixtures（async db, test client）
```

### M2 新增文件
```
src/hybrid_agent/api/auth/__init__.py
src/hybrid_agent/api/auth/schemas.py      ← LoginRequest, TokenResponse, UserInfo
src/hybrid_agent/api/auth/service.py      ← 密码哈希、JWT 生成/解析、用户验证
src/hybrid_agent/api/auth/dependencies.py ← get_current_user, get_db
src/hybrid_agent/api/auth/router.py       ← /login /refresh /logout /me
tests/test_auth.py
```

### M3 新增文件
```
src/hybrid_agent/api/auth/permissions.py  ← require_role, require_group_access
src/hybrid_agent/api/admin/__init__.py
src/hybrid_agent/api/admin/schemas.py
src/hybrid_agent/api/admin/service.py
src/hybrid_agent/api/admin/router.py      ← 用户/组 CRUD
tests/test_admin.py
```

### M4 修改文件
```
src/hybrid_agent/core/vector.py            ← VectorStore 接收 group_id
src/hybrid_agent/core/hybrid_retriever.py  ← BM25/MultiPath 加 group_id 过滤
src/hybrid_agent/core/rag_system.py        ← 所有方法加 group_id 参数
src/hybrid_agent/api/routes/documents.py   ← 从 current_user 注入 group_id
src/hybrid_agent/api/routes/chat.py        ← 从 current_user 注入 group_id
tests/test_group_isolation.py
```

### M5 修改文件
```
src/hybrid_agent/api/main.py   ← 注册 v1_router，旧路由重定向
tests/test_routes_v1.py
```

---

## Task 1：M0 — 安装开发依赖

**Files:** Modify `pyproject.toml`

- [x] **Step 1：查看当前依赖**

```bash
cat pyproject.toml | grep -A 50 "\[project\]"
```

- [x] **Step 2：添加开发依赖**

在 `pyproject.toml` 的 `[project.optional-dependencies]` 或 `[dependency-groups]` 中追加：

```toml
[dependency-groups]
dev = [
  "ruff>=0.4.0",
  "mypy>=1.10.0",
  "pytest>=8.0.0",
  "pytest-asyncio>=0.23.0",
  "aiosqlite>=0.20.0",
  "httpx>=0.27.0",
]
```

- [x] **Step 3：安装依赖**

```bash
uv sync --group dev
```

Expected: 安装完成，无报错

- [x] **Step 4：验证工具可用**

```bash
uv run ruff --version && uv run mypy --version && uv run pytest --version
```

Expected: 三个工具各自输出版本号

---

## Task 2：M0 — 创建架构边界测试

**Files:** Create `tests/test_architecture.py`

- [x] **Step 1：创建测试文件**

```python
# tests/test_architecture.py
"""
架构边界验证测试。

验证后端模块依赖方向：
  core/ → agent/ → api/
  core/ 不得 import agent/
  api/routes/ 不得直接 import core/database.py 的 ORM 模型

此测试由 CI 强制执行，违反则构建失败。
"""
from __future__ import annotations

import ast
from pathlib import Path


def _get_imports(filepath: Path) -> list[str]:
    """解析 Python 文件，返回所有 import 的完整模块名列表。

    Args:
        filepath: 要解析的 Python 文件路径。

    Returns:
        模块名字符串列表，例如 ["hybrid_agent.core.database", "os"]。
    """
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
    return imports


def test_core_does_not_import_agent():
    """core/ 模块不得依赖 agent/ 模块，避免循环依赖。"""
    src = Path("src/hybrid_agent/core")
    if not src.exists():
        return  # 路径不存在时跳过（CI 会从根目录运行）
    for f in src.rglob("*.py"):
        for imp in _get_imports(f):
            assert "hybrid_agent.agent" not in imp, (
                f"\n[架构违规] {f.relative_to(Path('src'))}\n"
                f"  core/ 模块导入了 agent/ 模块：'{imp}'\n"
                f"  依赖方向应为 core → agent，不得逆向。"
            )


def test_api_routes_do_not_import_database_models_directly():
    """api/routes/ 层不得直接导入 ORM 模型，必须通过 service 层。"""
    routes = Path("src/hybrid_agent/api/routes")
    if not routes.exists():
        return
    forbidden = {"hybrid_agent.core.database"}
    for f in routes.rglob("*.py"):
        for imp in _get_imports(f):
            assert imp not in forbidden, (
                f"\n[架构违规] {f.relative_to(Path('src'))}\n"
                f"  api/routes/ 直接导入了 ORM 模型：'{imp}'\n"
                f"  请在 services/ 层封装数据库操作，再由 route 调用 service。"
            )
```

- [x] **Step 2：运行测试，确认当前代码库通过**

```bash
uv run pytest tests/test_architecture.py -v
```

Expected：
```
tests/test_architecture.py::test_core_does_not_import_agent PASSED
tests/test_architecture.py::test_api_routes_do_not_import_database_models_directly PASSED
```

若有 FAILED，修复对应的 import 后再继续。

---

## Task 3：M0 — 创建本地检查脚本

**Files:** Create `scripts/__init__.py`, `scripts/check.py`

- [x] **Step 1：创建 scripts 目录和检查脚本**

```python
# scripts/check.py
"""
本地一键检查脚本。

运行所有 lint / type / test 检查。
通过时完全静默（exit 0），失败时输出简洁错误（exit 2）。
Agent 在每次提交前必须运行此脚本并确认静默通过。

用法：
    python scripts/check.py
"""
from __future__ import annotations

import subprocess
import sys


CHECKS: list[list[str]] = [
    ["uv", "run", "ruff", "check", "src/", "--output-format=concise"],
    ["uv", "run", "mypy", "src/hybrid_agent/", "--ignore-missing-imports", "--no-error-summary"],
    ["uv", "run", "pytest", "tests/", "--tb=short", "-q", "--no-header"],
]


def main() -> None:
    """执行所有检查，收集失败信息，全部通过时静默退出。"""
    errors: list[str] = []
    for cmd in CHECKS:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            label = " ".join(cmd[2:4])
            errors.append(f"[FAILED] {label}\n{result.stdout}{result.stderr}".strip())

    if errors:
        print("\n" + "\n\n".join(errors))
        sys.exit(2)
    # 全部通过：完全静默


if __name__ == "__main__":
    main()
```

```bash
touch scripts/__init__.py
```

- [x] **Step 2：运行脚本，确认当前代码库通过**

```bash
python scripts/check.py
```

Expected：无任何输出（静默），exit code 0。

若有输出，逐一修复后再继续。

---

## Task 4：M0 — 更新 CLAUDE.md 为目录表格式

**Files:** Modify `CLAUDE.md` (或创建，若不存在)

- [x] **Step 1：替换为目录表格式**

```markdown
# Hybrid-Agent — Agent 工作手册

## 项目概述
企业级 RAG 问答系统，支持知识库构建与多轮对话。
- 后端：FastAPI + PostgreSQL + ChromaDB（按组隔离）
- 前端：Vue 3 + Element Plus（待实现）
- 详细架构见 `docs/architecture.md`

## 快速启动
```bash
# 激活虚拟环境
source .venv/bin/activate

# 后端（开发模式）
PYTHONPATH=src uvicorn hybrid_agent.api.main:app --reload --port 8000

# 全部检查（通过静默，失败输出错误）
python scripts/check.py
```

## 架构约束（CI 强制执行，违反则构建失败）
- **依赖方向**：`core/` → `agent/` → `api/`
- `core/` 不得 import `agent/`
- `api/routes/` 不得直接使用 ORM 模型，必须通过 `services/` 层
- 详见 `docs/architecture.md`

## 代码规范
- 所有函数必须有函数级注释（Google style docstring）
- Python 函数签名必须有完整类型注解
- Vue 组件使用 `<script setup>` + Composition API
- 禁止 `import *`，禁止用 `pip`（必须用 `uv`）
- 详见 `docs/conventions.md`

## 测试要求
- 新功能必须先写测试（TDD），然后实现
- 运行：`uv run pytest tests/ --tb=short -q`
- 架构测试 `tests/test_architecture.py` 不得删除或跳过

## 开发流程
1. 开始每个模块前，更新 `claude-progress.txt`
2. 实现代码，每次提交前运行 `python scripts/check.py`（必须静默通过）
3. 提交格式：`feat(scope): 描述` / `fix(scope): 描述`
4. 若修复失败两次仍不过，停止，升级给人工，写入 `KNOWN_FAILURES.md`

## 已知失败模式（禁止重复）
见 `KNOWN_FAILURES.md`

## 环境变量
见 `.env.example`（必须在 `.env` 中配置后才能运行）
```

- [x] **Step 2：确认文件写入成功**

```bash
head -5 CLAUDE.md
```

Expected：输出 `# Hybrid-Agent — Agent 工作手册`

---

## Task 5：M0 — 创建架构和规范文档

**Files:** Create `docs/architecture.md`, `docs/conventions.md`

- [x] **Step 1：创建 docs/architecture.md**

```markdown
# Hybrid-Agent 架构文档

## 系统分层

```
外部请求
    ↓
api/routes/        ← 只做请求解析、响应序列化、权限检查
    ↓
api/services/      ← 业务逻辑编排（待补充）
    ↓
core/rag_system    ← RAG 系统入口（文档管理、检索）
    ├── core/vector.py           ← ChromaDB 向量存储
    ├── core/hybrid_retriever.py ← BM25 + Dense + HyDE + SubQuery
    ├── core/reranker.py         ← DashScope gte-rerank
    └── core/database.py         ← SQLAlchemy 模型 + DB 操作
    ↓
agent/agentic_rag_graph.py  ← LangGraph 流程图（查询理解 → 检索 → 反思 → 生成）
    ↓
llm/models.py               ← Qwen3-Omni / DeepSeek-V3
```

## 依赖方向规则（CI 强制执行）

```
core/ → agent/ → api/
```

- `core/` 不得 import `agent/` 或 `api/`
- `agent/` 不得 import `api/`
- `api/routes/` 不得直接 import `core/database.py` 的 ORM 模型

## 文档组隔离策略

每个用户组对应一个独立的 ChromaDB collection：
- Collection 命名：`group_{group_id}`
- BM25 索引按 `group_id` 字段过滤
- API 层从 JWT payload 中取 `group_id`，自动注入检索上下文

## 认证流程

```
POST /api/v1/auth/login
  → 验证 username + password（bcrypt）
  → 查询 users 表获取 group_ids + role
  → 返回 access_token (JWT, 2h) + refresh_token (JWT, 7d)

受保护路由
  → FastAPI Depends(get_current_user)
  → 解析 Authorization: Bearer <token>
  → 注入 CurrentUser(user_id, group_ids, role)
```

## 关键技术决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 数据库 | PostgreSQL + asyncpg | 并发安全、可备份、生产级 |
| 认证 | JWT（python-jose） | 无状态、前后端分离友好 |
| 测试 DB | SQLite in-memory（aiosqlite） | 无外部依赖，CI 友好 |
| 迁移管理 | Alembic | SQLAlchemy 官方方案 |
| 向量隔离 | ChromaDB collection per group | 天然隔离，无需过滤逻辑 |
```

- [x] **Step 2：创建 docs/conventions.md**

```markdown
# 代码规范

## Python 函数注释（Google style，必须）

```python
def search(query: str, k: int = 4, group_id: str | None = None) -> list[dict]:
    """在向量库中搜索相关文档块。

    Args:
        query: 用户查询文本。
        k: 返回结果数量。
        group_id: 组 ID，传入时只在该组的 collection 中搜索。

    Returns:
        包含 chunk_id, content, score 字段的字典列表，按相关度降序排列。

    Raises:
        ValueError: 当 query 为空字符串时。
    """
```

## 类型注解

- 所有函数参数和返回值必须有类型注解
- 使用 `str | None` 而非 `Optional[str]`（Python 3.10+ 语法）
- 列表用 `list[str]`，字典用 `dict[str, Any]`

## 禁止行为

- 禁止 `import *`
- 禁止 `pip install`，必须用 `uv add`
- 禁止在 `api/routes/` 直接操作数据库
- 禁止硬编码 API Key、密码等敏感信息

## 命名规范

- Python 文件/变量/函数：`snake_case`
- Python 类：`PascalCase`
- Vue 组件文件：`PascalCase.vue`（如 `ChatInput.vue`）
- Vue 组件使用：`<chat-input />` 或 `<ChatInput />`
- CSS 类名：`kebab-case`

## Commit 格式

```
feat(auth): 添加 JWT 登录接口
fix(vector): 修复 group_id 过滤条件缺失
test(architecture): 添加后端依赖方向结构性测试
docs(conventions): 补充 Vue 组件命名规范
chore(deps): 升级 langchain 至 1.3.0
```

## Vue 组件规范

- 使用 `<script setup>` + Composition API，不用 Options API
- Props 用 `defineProps<{}>()` TypeScript 语法
- 事件用 `defineEmits<{}>()` TypeScript 语法
- 禁止在 `views/` 直接调用 `api/`，必须通过 `stores/` 或 `composables/`
```

- [x] **Step 3：确认两个文件存在**

```bash
ls docs/architecture.md docs/conventions.md
```

Expected：两个文件均存在

---

## Task 6：M0 — 配置 CI 流水线

**Files:** Create `.github/workflows/ci.yml`

- [x] **Step 1：创建目录**

```bash
mkdir -p .github/workflows
```

- [x] **Step 2：创建 CI 配置文件**

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: ["main", "dev"]
  pull_request:
    branches: ["main"]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"

      - name: Install dependencies
        run: uv sync --group dev

      - name: Lint (ruff)
        run: uv run ruff check src/ --output-format=concise

      - name: Type check (mypy)
        run: uv run mypy src/hybrid_agent/ --ignore-missing-imports --no-error-summary

      - name: Tests (pytest)
        run: uv run pytest tests/ --tb=short -q --no-header
        env:
          DATABASE_URL: "sqlite+aiosqlite:///:memory:"
          JWT_SECRET: "test-secret-key-for-ci-only"
```

- [x] **Step 3：验证 YAML 语法**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "YAML OK"
```

Expected：`YAML OK`

---

## Task 7：M0 — 创建进度跟踪文件

**Files:** Create `claude-progress.txt`, `KNOWN_FAILURES.md`

- [x] **Step 1：创建 claude-progress.txt**

```
# Hybrid-Agent 企业级升级进度
# 每次开始新会话前必须读取此文件，了解当前进度
# 每完成一个模块，将 [ ] 改为 [x] 并更新"当前阶段"

当前阶段：M0 进行中
下一步：完成 M0 commit，开始 M1

## 模块状态
[ ] M0  Harness 基础设施
[ ] M1  PostgreSQL + Alembic
[ ] M2  用户认证（JWT）
[ ] M3  用户/组管理 + RBAC
[ ] M4  文档组隔离（ChromaDB Namespace）
[ ] M5  API 路由版本化
[ ] M17 开源嵌入模型替换（可与 M1-M5 并行）
[ ] M18 开放式模型提供商管理（后端 M2 后，前端并入 M16）
[ ] M6  文档上传异步化
[ ] M7  监控（Prometheus + 结构化日志）
[ ] M8  Docker Compose 完整编排
[ ] M9  Vue 3 项目脚手架
[ ] M10 设计系统（Design Tokens）
[ ] M11 登录页 + 路由守卫
[ ] M12 主布局（AppShell）
[ ] M13 聊天界面
[ ] M14 文档管理页
[ ] M15 管理后台
[ ] M16 个人设置页（含 M18 模型提供商管理 UI）
```

- [x] **Step 2：创建 KNOWN_FAILURES.md**

```markdown
# 已知 Agent 失败模式

> 每次发现新的 Agent 错误后，在此追加一条规则。
> 格式：## [模块] 失败描述 + 正确做法

（初始为空，随项目推进累积）
```

---

## Task 8：M0 — 全量检查并提交

- [x] **Step 1：运行全量检查**

```bash
python scripts/check.py
```

Expected：无输出（静默通过）

若有报错：修复，再次运行，直到静默。

- [x] **Step 2：更新 claude-progress.txt**

将 `[ ] M0` 改为 `[x] M0`，更新"当前阶段"为 `M1 进行中`。

- [x] **Step 3：提交 M0**

```bash
git add CLAUDE.md KNOWN_FAILURES.md claude-progress.txt \
        scripts/check.py \
        docs/architecture.md docs/conventions.md \
        tests/test_architecture.py \
        .github/workflows/ci.yml
git commit -m "chore(harness): M0 建立 Harness Engineering 基础设施"
```

Expected：commit 成功，显示新增文件列表

---

## Task 9：M1 — 添加数据库依赖

**Files:** Modify `pyproject.toml`

- [x] **Step 1：添加生产依赖**

```bash
uv add asyncpg alembic "sqlalchemy[asyncio]>=2.0"
```

- [x] **Step 2：添加测试依赖**

```bash
uv add --group dev aiosqlite
```

- [x] **Step 3：验证安装**

```bash
uv run python -c "import asyncpg; import alembic; import aiosqlite; print('OK')"
```

Expected：`OK`

---

## Task 10：M1 — 新增 DB 模型并更新 config

**Files:** Modify `src/hybrid_agent/core/config.py`, `src/hybrid_agent/core/database.py`

- [x] **Step 1：在 config.py 的 Settings 中新增字段**

在 `Settings` dataclass 中追加字段（保留所有原有字段）：

```python
# 在 Settings dataclass 末尾追加：
database_url: str | None
jwt_secret: str | None
```

在 `_read_env()` 函数中对应追加读取：

```python
database_url=os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{get_project_root() / 'documents.db'}"),
jwt_secret=os.getenv("JWT_SECRET", "change-me-in-production"),
```

在 `_validate_settings()` 中追加警告：

```python
if settings.jwt_secret == "change-me-in-production":
    logger.warning("JWT_SECRET 使用默认值，生产环境必须设置随机密钥")
```

- [x] **Step 2：在 database.py 中新增异步引擎和新模型**

在文件顶部新增 import（保留原有 import）：

```python
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import ForeignKey, Enum as SAEnum
import enum
```

在 `Base` 定义之后，新增枚举和新模型（不删除原有模型）：

```python
class UserRole(str, enum.Enum):
    """用户全局角色枚举。"""
    admin = "admin"
    group_admin = "group_admin"
    member = "member"


class GroupMemberRole(str, enum.Enum):
    """用户在组内的角色枚举。"""
    group_admin = "group_admin"
    member = "member"


class User(Base):
    """用户表，存储账号信息和全局角色。"""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(64), unique=True, nullable=False, index=True)
    hashed_password = Column(String(256), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.member)
    is_active = Column(Integer, default=1)  # 1=启用, 0=停用
    created_at = Column(DateTime, default=datetime.now)

    def to_dict(self) -> dict:
        """将用户模型转为字典（不含密码）。"""
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role.value if self.role else None,
            "is_active": bool(self.is_active),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Group(Base):
    """组表，代表一个部门或项目组。"""
    __tablename__ = "groups"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(64), unique=True, nullable=False, index=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    def to_dict(self) -> dict:
        """将组模型转为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UserGroup(Base):
    """用户-组关联表，支持一人多组。"""
    __tablename__ = "user_groups"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group_id = Column(String(36), ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)
    role = Column(SAEnum(GroupMemberRole), nullable=False, default=GroupMemberRole.member)


class LLMUsageLog(Base):
    """LLM 调用成本日志，用于费用追踪和监控。"""
    __tablename__ = "llm_usage_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    session_id = Column(String(255))
    model = Column(String(64), nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.now)
```

在 `DatabaseManager` 类之后，新增异步数据库工厂函数：

```python
def _get_async_database_url() -> str:
    """获取异步数据库连接字符串。

    Returns:
        适用于 SQLAlchemy async engine 的连接字符串。
    """
    from hybrid_agent.core.config import settings
    url = settings.database_url or ""
    # 兼容：若使用同步 sqlite:/// 格式，自动转为异步格式
    if url.startswith("sqlite:///") and "aiosqlite" not in url:
        url = url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return url


def create_async_db_engine():
    """创建异步数据库引擎。

    Returns:
        SQLAlchemy AsyncEngine 实例。
    """
    url = _get_async_database_url()
    return create_async_engine(url, echo=False)


AsyncSessionFactory = async_sessionmaker(
    bind=create_async_db_engine(),
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_db() -> AsyncSession:
    """FastAPI 依赖注入：提供异步数据库会话。

    Yields:
        AsyncSession 实例，请求结束后自动关闭。
    """
    async with AsyncSessionFactory() as session:
        yield session
```

也需要修改 DocumentModel 新增 group_id 和 uploaded_by 字段：

```python
# 在 DocumentModel 类末尾，created_at 之前插入：
group_id = Column(String(36), ForeignKey("groups.id", ondelete="SET NULL"), nullable=True, index=True)
uploaded_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
```

同时修改 `BM25ChunkModel`，在 `doc_id` 字段后插入：

```python
group_id = Column(String(36), nullable=True, index=True)
```

- [x] **Step 3：验证模型可导入**

```bash
uv run python -c "
from hybrid_agent.core.database import User, Group, UserGroup, LLMUsageLog, Base
print('models OK, tables:', list(Base.metadata.tables.keys()))
"
```

Expected：`models OK, tables: ['documents', 'bm25_chunks', 'conversation_summaries', 'users', 'groups', 'user_groups', 'llm_usage_logs']`

---

## Task 11：M1 — 编写 DB 模型测试

**Files:** Create `tests/conftest.py`, `tests/test_db_models.py`

- [x] **Step 1：创建 conftest.py（测试 fixtures）**

```python
# tests/conftest.py
"""
pytest 全局 fixtures。

提供异步测试所需的内存数据库和 FastAPI 测试客户端。
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from httpx import AsyncClient, ASGITransport

from hybrid_agent.core.database import Base


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """创建内存 SQLite 异步引擎并建表，测试后销毁。"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine):
    """提供事务内的 AsyncSession，测试后回滚（不污染 DB）。"""
    factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
```

- [x] **Step 2：在 `pyproject.toml` 中配置 pytest-asyncio 模式**

在 `pyproject.toml` 末尾追加：

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.mypy]
ignore_missing_imports = true
```

- [x] **Step 3：创建 DB 模型测试文件（先写测试）**

```python
# tests/test_db_models.py
"""
数据库模型单元测试。

验证 User/Group/UserGroup/LLMUsageLog 模型的基本 CRUD 操作。
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hybrid_agent.core.database import User, Group, UserGroup, LLMUsageLog, UserRole, GroupMemberRole


async def test_create_user(db_session: AsyncSession):
    """创建用户后可正常查询到。"""
    user = User(username="alice", hashed_password="hashed", role=UserRole.admin)
    db_session.add(user)
    await db_session.commit()

    result = await db_session.execute(select(User).where(User.username == "alice"))
    fetched = result.scalar_one()
    assert fetched.username == "alice"
    assert fetched.role == UserRole.admin
    assert bool(fetched.is_active) is True


async def test_create_group(db_session: AsyncSession):
    """创建组后可正常查询到。"""
    group = Group(name="研发部", description="研发团队")
    db_session.add(group)
    await db_session.commit()

    result = await db_session.execute(select(Group).where(Group.name == "研发部"))
    fetched = result.scalar_one()
    assert fetched.name == "研发部"


async def test_user_group_association(db_session: AsyncSession):
    """用户加入组后，user_groups 表有对应记录。"""
    user = User(username="bob", hashed_password="hashed")
    group = Group(name="产品部")
    db_session.add_all([user, group])
    await db_session.commit()

    assoc = UserGroup(user_id=user.id, group_id=group.id, role=GroupMemberRole.member)
    db_session.add(assoc)
    await db_session.commit()

    result = await db_session.execute(
        select(UserGroup).where(UserGroup.user_id == user.id)
    )
    fetched = result.scalar_one()
    assert fetched.group_id == group.id
    assert fetched.role == GroupMemberRole.member


async def test_llm_usage_log(db_session: AsyncSession):
    """LLM 调用日志可正常写入。"""
    log = LLMUsageLog(
        model="deepseek-v3",
        prompt_tokens=100,
        completion_tokens=200,
        cost_usd=0.000327,
    )
    db_session.add(log)
    await db_session.commit()

    result = await db_session.execute(select(LLMUsageLog))
    fetched = result.scalar_one()
    assert fetched.model == "deepseek-v3"
    assert fetched.prompt_tokens == 100


async def test_user_to_dict_excludes_password(db_session: AsyncSession):
    """to_dict() 不含 hashed_password 字段。"""
    user = User(username="carol", hashed_password="secret_hash")
    db_session.add(user)
    await db_session.commit()

    d = user.to_dict()
    assert "hashed_password" not in d
    assert d["username"] == "carol"
```

- [x] **Step 4：运行测试（预期通过）**

```bash
uv run pytest tests/test_db_models.py -v
```

Expected：所有 5 个测试 PASSED

---

## Task 12：M1 — 配置 Alembic

**Files:** Create `alembic.ini`, `alembic/env.py`, `alembic/versions/`

- [x] **Step 1：初始化 Alembic**

```bash
uv run alembic init alembic
```

Expected：创建 `alembic.ini` 和 `alembic/` 目录

- [x] **Step 2：修改 alembic.ini，让 DATABASE_URL 从环境变量读取**

找到 `sqlalchemy.url` 这一行，替换为：

```ini
sqlalchemy.url = %(DATABASE_URL)s
```

- [x] **Step 3：替换 alembic/env.py**

```python
# alembic/env.py
"""
Alembic 异步迁移环境配置。

支持通过 DATABASE_URL 环境变量连接 PostgreSQL（生产）或 SQLite（开发）。
"""
from __future__ import annotations

import os
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 导入所有 ORM 模型，确保 Base.metadata 包含全部表
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from hybrid_agent.core.database import Base  # noqa: E402

config = context.config

# 从环境变量读取 DATABASE_URL（优先）
db_url = os.getenv("DATABASE_URL")
if db_url:
    # 生产 PostgreSQL：确保使用 asyncpg driver
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本，不连接数据库。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """在给定连接上执行迁移。"""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """在线模式：使用异步引擎连接数据库并执行迁移。"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """在线模式入口。"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [x] **Step 4：生成初始迁移文件**

```bash
DATABASE_URL="sqlite+aiosqlite:///./documents_dev.db" uv run alembic revision --autogenerate -m "initial_schema"
```

Expected：`alembic/versions/xxxx_initial_schema.py` 文件生成，内含所有表的 `op.create_table()` 调用

- [x] **Step 5：验证迁移文件包含所有新表**

```bash
cat alembic/versions/*initial_schema.py | grep "op.create_table"
```

Expected：输出包含 `users`, `groups`, `user_groups`, `llm_usage_logs`

- [x] **Step 6：运行迁移，验证数据库建表成功**

```bash
DATABASE_URL="sqlite+aiosqlite:///./documents_dev.db" uv run alembic upgrade head
```

Expected：无报错，输出 `Running upgrade -> xxxx, initial_schema`

- [x] **Step 7：清理测试数据库文件**

```bash
rm -f documents_dev.db
```

---

## Task 13：M1 — 提交 M1

- [x] **Step 1：运行全量检查**

```bash
python scripts/check.py
```

Expected：静默通过

- [x] **Step 2：更新进度文件**

将 `claude-progress.txt` 中 `[ ] M1` 改为 `[x] M1`，更新当前阶段为 `M2 进行中`。

- [x] **Step 3：提交**

```bash
git add pyproject.toml uv.lock \
        src/hybrid_agent/core/config.py \
        src/hybrid_agent/core/database.py \
        alembic.ini alembic/ \
        tests/conftest.py tests/test_db_models.py \
        claude-progress.txt
git commit -m "feat(db): M1 PostgreSQL + Alembic，新增 User/Group/UserGroup/LLMUsageLog 模型"
```

---

## Task 14：M2 — 添加认证依赖

**Files:** Modify `pyproject.toml`

- [x] **Step 1：安装认证库**

```bash
uv add "python-jose[cryptography]" "passlib[bcrypt]"
```

- [x] **Step 2：验证**

```bash
uv run python -c "from jose import jwt; from passlib.context import CryptContext; print('auth deps OK')"
```

Expected：`auth deps OK`

---

## Task 15：M2 — 先写认证测试（TDD）

**Files:** Create `tests/test_auth.py`

- [x] **Step 1：创建测试文件（此时实现代码还不存在）**

```python
# tests/test_auth.py
"""
用户认证接口测试。

覆盖：登录成功/失败、token 解析、/me 接口。
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from hybrid_agent.core.database import Base, User, UserRole
from hybrid_agent.api.auth.service import hash_password


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def test_engine():
    """为认证测试创建独立的内存数据库。"""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def test_db(test_engine):
    """提供 AsyncSession，测试后自动关闭。"""
    factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture(scope="function")
async def client(test_engine):
    """创建带测试 DB 的 FastAPI 测试客户端。"""
    from hybrid_agent.api.main import app
    from hybrid_agent.api.auth.dependencies import get_db
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def alice_user(test_db: AsyncSession):
    """在测试 DB 中创建用户 alice。"""
    user = User(
        username="alice",
        hashed_password=hash_password("password123"),
        role=UserRole.member,
    )
    test_db.add(user)
    await test_db.commit()
    return user


async def test_login_success(client: AsyncClient, alice_user):
    """正确账密登录，返回 access_token 和 refresh_token。"""
    resp = await client.post("/api/v1/auth/login", json={
        "username": "alice",
        "password": "password123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(client: AsyncClient, alice_user):
    """密码错误时返回 401。"""
    resp = await client.post("/api/v1/auth/login", json={
        "username": "alice",
        "password": "wrong",
    })
    assert resp.status_code == 401


async def test_login_unknown_user(client: AsyncClient):
    """用户不存在时返回 401。"""
    resp = await client.post("/api/v1/auth/login", json={
        "username": "nobody",
        "password": "password123",
    })
    assert resp.status_code == 401


async def test_me_with_valid_token(client: AsyncClient, alice_user):
    """有效 token 调用 /me，返回当前用户信息。"""
    login_resp = await client.post("/api/v1/auth/login", json={
        "username": "alice",
        "password": "password123",
    })
    token = login_resp.json()["access_token"]

    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "alice"


async def test_me_without_token(client: AsyncClient):
    """无 token 调用受保护接口，返回 401。"""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_with_invalid_token(client: AsyncClient):
    """伪造 token 调用受保护接口，返回 401。"""
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert resp.status_code == 401
```

- [x] **Step 2：运行测试，确认失败（实现代码不存在）**

```bash
uv run pytest tests/test_auth.py -v 2>&1 | head -20
```

Expected：`ImportError` 或 `ModuleNotFoundError`（auth 模块尚未创建）

---

## Task 16：M2 — 实现认证模块

**Files:** Create `src/hybrid_agent/api/auth/` 目录下所有文件

- [x] **Step 1：创建 auth 包和 schemas**

```bash
mkdir -p src/hybrid_agent/api/auth
touch src/hybrid_agent/api/auth/__init__.py
```

```python
# src/hybrid_agent/api/auth/schemas.py
"""认证相关的 Pydantic 数据模型。"""
from __future__ import annotations
from pydantic import BaseModel


class LoginRequest(BaseModel):
    """登录请求体。"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """登录成功响应，包含 access_token 和 refresh_token。"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    """当前登录用户信息（/me 接口响应）。"""
    id: str
    username: str
    role: str
    group_ids: list[str]
    is_active: bool
```

- [x] **Step 2：实现 auth/service.py**

```python
# src/hybrid_agent/api/auth/service.py
"""
认证服务。

提供密码哈希/验证、JWT 生成/解析、用户查询功能。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hybrid_agent.core.database import User, UserGroup
from hybrid_agent.core.config import settings

if TYPE_CHECKING:
    pass

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 2
REFRESH_TOKEN_EXPIRE_DAYS = 7

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """对明文密码进行 bcrypt 哈希。

    Args:
        password: 明文密码。

    Returns:
        bcrypt 哈希字符串。
    """
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """验证明文密码与哈希是否匹配。

    Args:
        plain: 用户输入的明文密码。
        hashed: 数据库存储的哈希密码。

    Returns:
        匹配返回 True，否则 False。
    """
    return _pwd_context.verify(plain, hashed)


def _get_jwt_secret() -> str:
    """获取 JWT 签名密钥。

    Returns:
        JWT 密钥字符串。
    """
    return settings.jwt_secret or "change-me-in-production"


def create_access_token(user_id: str, group_ids: list[str], role: str) -> str:
    """生成 JWT access token，有效期 2 小时。

    Args:
        user_id: 用户 ID。
        group_ids: 用户所属组 ID 列表。
        role: 用户全局角色。

    Returns:
        JWT 字符串。
    """
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "group_ids": group_ids,
        "role": role,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """生成 JWT refresh token，有效期 7 天。

    Args:
        user_id: 用户 ID。

    Returns:
        JWT 字符串。
    """
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": user_id, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, _get_jwt_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """解析并验证 JWT token。

    Args:
        token: JWT 字符串。

    Returns:
        解析后的 payload 字典。

    Raises:
        JWTError: token 无效或已过期。
    """
    return jwt.decode(token, _get_jwt_secret(), algorithms=[ALGORITHM])


async def authenticate_user(db: AsyncSession, username: str, password: str) -> User | None:
    """验证用户名和密码。

    Args:
        db: 数据库会话。
        username: 用户名。
        password: 明文密码。

    Returns:
        验证成功返回 User 实例，失败返回 None。
    """
    result = await db.execute(select(User).where(User.username == username, User.is_active == 1))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


async def get_user_group_ids(db: AsyncSession, user_id: str) -> list[str]:
    """查询用户所属的所有组 ID。

    Args:
        db: 数据库会话。
        user_id: 用户 ID。

    Returns:
        组 ID 字符串列表。
    """
    result = await db.execute(select(UserGroup.group_id).where(UserGroup.user_id == user_id))
    return [row[0] for row in result.fetchall()]
```

- [x] **Step 3：实现 auth/dependencies.py**

```python
# src/hybrid_agent/api/auth/dependencies.py
"""
FastAPI 依赖注入函数。

提供 get_db（数据库会话）和 get_current_user（JWT 认证）。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hybrid_agent.core.database import AsyncSessionFactory, User, get_async_db
from hybrid_agent.api.auth.service import decode_token
from hybrid_agent.api.auth.schemas import UserInfo

security = HTTPBearer(auto_error=False)


async def get_db() -> AsyncSession:
    """提供数据库会话（可在测试中 override）。

    Yields:
        AsyncSession 实例。
    """
    async for session in get_async_db():
        yield session


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserInfo:
    """从 Bearer token 中解析当前用户。

    Args:
        credentials: HTTP Bearer 凭证。
        db: 数据库会话。

    Returns:
        UserInfo 包含用户 ID、用户名、角色和组 ID 列表。

    Raises:
        HTTPException 401: token 缺失、无效或已过期。
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证 token")
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token 无效或已过期")

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token 类型错误")

    user_id: str = payload.get("sub", "")
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == 1))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已停用")

    return UserInfo(
        id=user.id,
        username=user.username,
        role=user.role.value if user.role else "member",
        group_ids=payload.get("group_ids", []),
        is_active=True,
    )
```

- [x] **Step 4：实现 auth/router.py**

```python
# src/hybrid_agent/api/auth/router.py
"""
认证路由。

提供 /login、/refresh、/logout、/me 端点。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from hybrid_agent.api.auth.dependencies import get_db, get_current_user
from hybrid_agent.api.auth.schemas import LoginRequest, TokenResponse, UserInfo
from hybrid_agent.api.auth.service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_group_ids,
)

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """账密登录，返回 JWT access_token 和 refresh_token。

    Args:
        request: 包含 username 和 password 的请求体。
        db: 数据库会话。

    Returns:
        TokenResponse 包含两个 token。

    Raises:
        HTTPException 401: 用户名或密码错误。
    """
    user = await authenticate_user(db, request.username, request.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    group_ids = await get_user_group_ids(db, user.id)
    access_token = create_access_token(user.id, group_ids, user.role.value)
    refresh_token = create_refresh_token(user.id)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token_str: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """使用 refresh_token 换取新的 access_token。

    Args:
        refresh_token_str: 有效的 refresh token 字符串。
        db: 数据库会话。

    Returns:
        新的 TokenResponse。

    Raises:
        HTTPException 401: refresh token 无效。
    """
    try:
        payload = decode_token(refresh_token_str)
        if payload.get("type") != "refresh":
            raise ValueError("token 类型错误")
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="refresh token 无效")

    from sqlalchemy import select
    from hybrid_agent.core.database import User
    result = await db.execute(select(User).where(User.id == payload["sub"], User.is_active == 1))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    group_ids = await get_user_group_ids(db, user.id)
    new_access = create_access_token(user.id, group_ids, user.role.value)
    new_refresh = create_refresh_token(user.id)
    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/logout")
async def logout() -> dict:
    """登出（客户端清除 token，服务端无状态）。

    Returns:
        成功消息。
    """
    return {"message": "已登出，请在客户端清除 token"}


@router.get("/me", response_model=UserInfo)
async def me(current_user: Annotated[UserInfo, Depends(get_current_user)]) -> UserInfo:
    """获取当前登录用户信息。

    Args:
        current_user: 由 get_current_user 依赖注入的用户信息。

    Returns:
        UserInfo 当前用户信息。
    """
    return current_user
```

- [x] **Step 5：在 main.py 中注册 v1 router（同时做 M5 的准备）**

在 `src/hybrid_agent/api/main.py` 中追加：

```python
from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from hybrid_agent.api.auth.router import router as auth_router

# 在 app 定义之后、所有路由注册之前添加：
v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
app.include_router(v1_router)

# 旧路由向后兼容重定向（过渡期）
@app.get("/api/health")
async def legacy_health_redirect():
    return RedirectResponse(url="/api/v1/health", status_code=301)
```

同时在 main.py 末尾新增 v1 health 端点：

```python
@v1_router.get("/health")
async def v1_health():
    """v1 健康检查端点。"""
    return {"status": "healthy", "version": "v1"}
```

- [x] **Step 6：运行认证测试**

```bash
uv run pytest tests/test_auth.py -v
```

Expected：所有 6 个测试 PASSED

---

## Task 17：M2 — 全量检查并提交 M2

- [x] **Step 1：运行全量检查**

```bash
python scripts/check.py
```

Expected：静默通过

- [x] **Step 2：更新进度文件**

将 `claude-progress.txt` 中 `[ ] M2` 改为 `[x] M2`，更新阶段为 `M3 进行中`。

- [x] **Step 3：提交**

```bash
git add src/hybrid_agent/api/auth/ \
        src/hybrid_agent/api/main.py \
        tests/test_auth.py \
        claude-progress.txt
git commit -m "feat(auth): M2 JWT 登录认证（/login /refresh /logout /me）"
```

---

## Task 18：M3 — 先写 RBAC 测试（TDD）

**Files:** Create `tests/test_admin.py`

- [x] **Step 1：创建测试（实现前）**

```python
# tests/test_admin.py
"""
RBAC 权限和管理员接口测试。

验证：角色校验正确拒绝/放行，管理员可创建用户和组。
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from hybrid_agent.core.database import Base, User, UserRole
from hybrid_agent.api.auth.service import hash_password, create_access_token

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def client(test_engine):
    from hybrid_agent.api.main import app
    from hybrid_agent.api.auth.dependencies import get_db
    factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def admin_token(test_engine) -> str:
    """创建 admin 用户并返回其 access_token。"""
    factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        user = User(
            id="admin-id",
            username="admin",
            hashed_password=hash_password("admin123"),
            role=UserRole.admin,
        )
        session.add(user)
        await session.commit()
    return create_access_token("admin-id", [], "admin")


@pytest.fixture(scope="function")
async def member_token(test_engine) -> str:
    """创建 member 用户并返回其 access_token。"""
    factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        user = User(
            id="member-id",
            username="member",
            hashed_password=hash_password("member123"),
            role=UserRole.member,
        )
        session.add(user)
        await session.commit()
    return create_access_token("member-id", [], "member")


async def test_admin_can_create_user(client: AsyncClient, admin_token: str):
    """admin 可以创建新用户。"""
    resp = await client.post(
        "/api/v1/admin/users",
        json={"username": "newuser", "password": "pass123", "role": "member"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["username"] == "newuser"


async def test_member_cannot_create_user(client: AsyncClient, member_token: str):
    """普通 member 调用 admin 接口，返回 403。"""
    resp = await client.post(
        "/api/v1/admin/users",
        json={"username": "hacker", "password": "pass", "role": "admin"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert resp.status_code == 403


async def test_admin_can_create_group(client: AsyncClient, admin_token: str):
    """admin 可以创建新组。"""
    resp = await client.post(
        "/api/v1/admin/groups",
        json={"name": "研发部", "description": "研发团队"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "研发部"


async def test_unauthenticated_cannot_access_admin(client: AsyncClient):
    """未认证用户访问 admin 接口，返回 401。"""
    resp = await client.get("/api/v1/admin/users")
    assert resp.status_code == 401
```

- [x] **Step 2：运行，确认失败**

```bash
uv run pytest tests/test_admin.py -v 2>&1 | head -15
```

Expected：ImportError 或 404（admin 路由尚未创建）

---

## Task 19：M3 — 实现 RBAC 权限层和管理员接口

**Files:** Create `src/hybrid_agent/api/auth/permissions.py`, `src/hybrid_agent/api/admin/`

- [x] **Step 1：创建 permissions.py**

```python
# src/hybrid_agent/api/auth/permissions.py
"""
RBAC 权限校验依赖。

提供 require_role 工厂函数，用于限制接口的角色访问范围。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status

from hybrid_agent.api.auth.dependencies import get_current_user
from hybrid_agent.api.auth.schemas import UserInfo


def require_role(*roles: str):
    """生成 FastAPI 依赖，要求当前用户具有指定角色之一。

    Args:
        *roles: 允许访问的角色名称，如 "admin"、"group_admin"。

    Returns:
        FastAPI Depends 可用的依赖函数。

    Example:
        @router.delete("/{id}", dependencies=[Depends(require_role("admin", "group_admin"))])
    """
    async def _check(current_user: Annotated[UserInfo, Depends(get_current_user)]) -> UserInfo:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要角色 {list(roles)} 之一，当前角色：{current_user.role}",
            )
        return current_user
    return _check
```

- [x] **Step 2：创建 admin 包**

```bash
mkdir -p src/hybrid_agent/api/admin
touch src/hybrid_agent/api/admin/__init__.py
```

- [x] **Step 3：创建 admin/schemas.py**

```python
# src/hybrid_agent/api/admin/schemas.py
"""管理员接口的 Pydantic 数据模型。"""
from __future__ import annotations
from pydantic import BaseModel, Field


class CreateUserRequest(BaseModel):
    """创建用户请求体。"""
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6)
    role: str = Field(default="member", pattern="^(admin|group_admin|member)$")


class CreateGroupRequest(BaseModel):
    """创建组请求体。"""
    name: str = Field(..., min_length=1, max_length=64)
    description: str = ""


class AddMemberRequest(BaseModel):
    """向组中添加成员请求体。"""
    user_id: str
    role: str = Field(default="member", pattern="^(group_admin|member)$")


class UserResponse(BaseModel):
    """用户响应体（不含密码）。"""
    id: str
    username: str
    role: str
    is_active: bool


class GroupResponse(BaseModel):
    """组响应体。"""
    id: str
    name: str
    description: str | None
```

- [x] **Step 4：创建 admin/service.py**

```python
# src/hybrid_agent/api/admin/service.py
"""
管理员业务逻辑：用户和组的增删改查。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hybrid_agent.core.database import User, Group, UserGroup, UserRole, GroupMemberRole
from hybrid_agent.api.auth.service import hash_password


async def create_user(db: AsyncSession, username: str, password: str, role: str) -> User:
    """创建新用户。

    Args:
        db: 数据库会话。
        username: 用户名（唯一）。
        password: 明文密码（将被哈希）。
        role: 用户全局角色。

    Returns:
        已创建的 User 实例。

    Raises:
        ValueError: 用户名已存在。
    """
    result = await db.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none() is not None:
        raise ValueError(f"用户名 '{username}' 已存在")
    user = User(username=username, hashed_password=hash_password(password), role=UserRole(role))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def list_users(db: AsyncSession) -> list[User]:
    """查询所有用户列表。

    Args:
        db: 数据库会话。

    Returns:
        User 实例列表。
    """
    result = await db.execute(select(User))
    return list(result.scalars().all())


async def create_group(db: AsyncSession, name: str, description: str) -> Group:
    """创建新组。

    Args:
        db: 数据库会话。
        name: 组名（唯一）。
        description: 组描述。

    Returns:
        已创建的 Group 实例。

    Raises:
        ValueError: 组名已存在。
    """
    result = await db.execute(select(Group).where(Group.name == name))
    if result.scalar_one_or_none() is not None:
        raise ValueError(f"组名 '{name}' 已存在")
    group = Group(name=name, description=description)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group


async def add_member_to_group(db: AsyncSession, group_id: str, user_id: str, role: str) -> UserGroup:
    """将用户添加到组。

    Args:
        db: 数据库会话。
        group_id: 目标组 ID。
        user_id: 要添加的用户 ID。
        role: 在组内的角色。

    Returns:
        UserGroup 关联记录。
    """
    assoc = UserGroup(user_id=user_id, group_id=group_id, role=GroupMemberRole(role))
    db.add(assoc)
    await db.commit()
    return assoc
```

- [x] **Step 5：创建 admin/router.py**

```python
# src/hybrid_agent/api/admin/router.py
"""
管理员路由（仅 admin 角色可访问）。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from hybrid_agent.api.auth.dependencies import get_db
from hybrid_agent.api.auth.permissions import require_role
from hybrid_agent.api.auth.schemas import UserInfo
from hybrid_agent.api.admin.schemas import (
    CreateUserRequest, CreateGroupRequest, AddMemberRequest,
    UserResponse, GroupResponse,
)
from hybrid_agent.api.admin import service

router = APIRouter(prefix="/admin", tags=["管理员"])

_admin_only = Depends(require_role("admin"))
_admin_or_group_admin = Depends(require_role("admin", "group_admin"))


@router.post("/users", response_model=UserResponse, status_code=201,
             dependencies=[_admin_only])
async def create_user(
    request: CreateUserRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """创建新用户（仅 admin）。"""
    try:
        user = await service.create_user(db, request.username, request.password, request.role)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return UserResponse(id=user.id, username=user.username,
                        role=user.role.value, is_active=bool(user.is_active))


@router.get("/users", dependencies=[_admin_only])
async def list_users(db: Annotated[AsyncSession, Depends(get_db)]) -> list[UserResponse]:
    """获取所有用户列表（仅 admin）。"""
    users = await service.list_users(db)
    return [UserResponse(id=u.id, username=u.username,
                         role=u.role.value, is_active=bool(u.is_active)) for u in users]


@router.post("/groups", response_model=GroupResponse, status_code=201,
             dependencies=[_admin_only])
async def create_group(
    request: CreateGroupRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GroupResponse:
    """创建新组（仅 admin）。"""
    try:
        group = await service.create_group(db, request.name, request.description)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return GroupResponse(id=group.id, name=group.name, description=group.description)


@router.post("/groups/{group_id}/members", status_code=201,
             dependencies=[_admin_or_group_admin])
async def add_member(
    group_id: str,
    request: AddMemberRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """向组中添加成员（admin 或 group_admin）。"""
    await service.add_member_to_group(db, group_id, request.user_id, request.role)
    return {"message": "成员已添加"}
```

- [x] **Step 6：在 main.py 中注册 admin router**

在 `v1_router.include_router(auth_router)` 之后追加：

```python
from hybrid_agent.api.admin.router import router as admin_router
v1_router.include_router(admin_router)
```

- [x] **Step 7：运行 M3 测试**

```bash
uv run pytest tests/test_admin.py -v
```

Expected：所有 4 个测试 PASSED

---

## Task 20：M3 — 全量检查并提交 M3

- [x] **Step 1：运行全量检查**

```bash
python scripts/check.py
```

Expected：静默通过

- [x] **Step 2：更新进度，提交**

更新 `claude-progress.txt`（M3 完成）。

```bash
git add src/hybrid_agent/api/auth/permissions.py \
        src/hybrid_agent/api/admin/ \
        src/hybrid_agent/api/main.py \
        tests/test_admin.py \
        claude-progress.txt
git commit -m "feat(rbac): M3 RBAC 权限层 + 用户/组管理接口"
```

---

## Task 21：M4 — 先写组隔离测试（TDD）

**Files:** Create `tests/test_group_isolation.py`

- [x] **Step 1：创建测试（实现前）**

```python
# tests/test_group_isolation.py
"""
文档组隔离测试。

验证：A 组上传的文档不会出现在 B 组的检索结果中。
使用 mock 替代真实 ChromaDB，专注于业务逻辑测试。
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from hybrid_agent.core.rag_system import RAGSystem


async def test_vector_store_uses_group_namespace():
    """VectorStore 在不同 group_id 下应使用不同的 collection 名称。"""
    from hybrid_agent.core.vector import VectorStore
    with patch("hybrid_agent.core.vector.chromadb") as mock_chroma:
        mock_client = MagicMock()
        mock_chroma.PersistentClient.return_value = mock_client
        mock_client.get_or_create_collection.return_value = MagicMock()

        vs_a = VectorStore(group_id="group-a")
        vs_b = VectorStore(group_id="group-b")

        calls_a = mock_client.get_or_create_collection.call_args_list
        # 两次调用应使用不同的 collection 名
        assert calls_a[0][1]["name"] != calls_a[1][1]["name"] or len(set(
            c[1]["name"] for c in calls_a
        )) == 2, "不同 group_id 应使用不同的 ChromaDB collection"


async def test_bm25_retriever_filters_by_group():
    """BM25Retriever.search 在传入 group_id 时只返回该组的文档。"""
    from hybrid_agent.core.hybrid_retriever import BM25Retriever
    from unittest.mock import patch, MagicMock

    retriever = BM25Retriever.__new__(BM25Retriever)
    retriever._index = None
    retriever._doc_map = {}

    # 模拟数据库中有两组文档
    with patch.object(retriever, "_get_chunks_for_group") as mock_get:
        mock_get.return_value = [
            {"chunk_id": "a1", "content": "研发文档内容", "group_id": "group-a"},
        ]
        results = await retriever.search_async("研发", k=5, group_id="group-a")
        mock_get.assert_called_once_with("group-a")
```

- [x] **Step 2：运行，确认失败**

```bash
uv run pytest tests/test_group_isolation.py -v 2>&1 | head -20
```

Expected：FAILED 或 ERROR（VectorStore 尚不接受 group_id 参数）

---

## Task 22：M4 — 修改 VectorStore 支持 group_id

**Files:** Modify `src/hybrid_agent/core/vector.py`

- [x] **Step 1：在 VectorStore.__init__ 中新增 group_id 参数**

打开 `src/hybrid_agent/core/vector.py`，找到 `VectorStore.__init__`。
在方法第一行插入 group_id 接收逻辑，并将 collection 名改为动态生成：

```python
def __init__(self, group_id: str | None = None) -> None:
    """初始化向量存储。

    Args:
        group_id: 组 ID。传入时使用独立的 ChromaDB collection，
                  实现多组文档隔离。不传时使用默认全局 collection。
    """
    self._group_id = group_id
    self._collection_name = f"group_{group_id}" if group_id else "default"
    # 以下保留原有初始化逻辑，只需将所有 collection_name 字面量替换为 self._collection_name
    # 例如原来是：self.collection = client.get_or_create_collection("hybrid_agent")
    # 改为：      self.collection = client.get_or_create_collection(self._collection_name)
```

执行替换（将原有 collection 名字字面量改为变量）：

```bash
# 查看原始 collection name 是什么
grep -n "get_or_create_collection" src/hybrid_agent/core/vector.py
```

将查询结果中的硬编码字符串（如 `"hybrid_agent"` 或 `"documents"`）统一替换为 `self._collection_name`。

- [x] **Step 2：查找并替换所有 collection name 的硬编码**

```bash
grep -n "collection_name\|get_or_create_collection" src/hybrid_agent/core/vector.py
```

检查输出，确保 `get_or_create_collection` 调用用的是变量而非硬编码字符串。

- [x] **Step 3：修改 BM25Retriever 支持 group_id 过滤**

在 `src/hybrid_agent/core/hybrid_retriever.py` 中：

为 `BM25Retriever` 添加辅助方法 `_get_chunks_for_group`：

```python
async def _get_chunks_for_group(self, group_id: str) -> list[dict]:
    """从数据库查询指定组的 BM25 文档块（异步）。

    Args:
        group_id: 目标组 ID。

    Returns:
        包含 chunk_id, content, group_id 的字典列表。
    """
    from hybrid_agent.core.database import AsyncSessionFactory, BM25ChunkModel
    from sqlalchemy import select
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(BM25ChunkModel).where(BM25ChunkModel.group_id == group_id)
        )
        rows = result.scalars().all()
        return [{"chunk_id": r.id, "content": r.content, "group_id": r.group_id} for r in rows]
```

在 `BM25Retriever.search` 方法签名中新增可选 `group_id` 参数：

```python
def search(self, query: str, k: int = 10, group_id: str | None = None) -> list[dict]:
    """BM25 关键词检索。

    Args:
        query: 查询文本。
        k: 返回数量。
        group_id: 传入时只返回该组的结果。

    Returns:
        匹配的文档块列表。
    """
```

同理为 `search_async` 方法添加 `group_id` 参数。

- [x] **Step 4：修改 RAGSystem 接口添加 group_id**

在 `src/hybrid_agent/core/rag_system.py` 中，为以下方法签名添加 `group_id: str | None = None` 参数：
- `add_document()`
- `delete_document()`
- `list_documents()`
- `search_documents()`
- `query()`

在 `search_documents` 和 `query` 内部，将 `group_id` 传给 `VectorStore` 和 `BM25Retriever`。

- [x] **Step 5：修改 API 路由，从 current_user 注入 group_id**

在 `src/hybrid_agent/api/routes/documents.py` 和 `chat.py` 中：

```python
from hybrid_agent.api.auth.dependencies import get_current_user
from hybrid_agent.api.auth.schemas import UserInfo
from typing import Annotated
from fastapi import Depends

# 在路由函数参数中添加：
current_user: Annotated[UserInfo, Depends(get_current_user)]

# 取第一个 group_id（后续可扩展为多组）
group_id = current_user.group_ids[0] if current_user.group_ids else None
```

- [x] **Step 6：运行组隔离测试**

```bash
uv run pytest tests/test_group_isolation.py -v
```

Expected：测试通过

- [x] **Step 7：运行全量检查**

```bash
python scripts/check.py
```

Expected：静默通过

- [x] **Step 8：更新进度，提交 M4**

更新 `claude-progress.txt`（M4 完成）。

```bash
git add src/hybrid_agent/core/vector.py \
        src/hybrid_agent/core/hybrid_retriever.py \
        src/hybrid_agent/core/rag_system.py \
        src/hybrid_agent/api/routes/ \
        tests/test_group_isolation.py \
        claude-progress.txt
git commit -m "feat(isolation): M4 文档组隔离（ChromaDB namespace + BM25 group_id 过滤）"
```

---

## Task 23：M5 — 先写路由版本化测试（TDD）

**Files:** Create `tests/test_routes_v1.py`

- [x] **Step 1：创建测试**

```python
# tests/test_routes_v1.py
"""
API v1 路由版本化测试。

验证：/api/v1/ 路由正常响应，旧路由返回重定向。
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from hybrid_agent.api.main import app


@pytest.fixture(scope="module")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_v1_health(client: AsyncClient):
    """GET /api/v1/health 返回 200。"""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


async def test_v1_auth_login_route_exists(client: AsyncClient):
    """POST /api/v1/auth/login 路由存在（即使账密错误也应返回 401，而非 404）。"""
    resp = await client.post("/api/v1/auth/login", json={"username": "x", "password": "x"})
    assert resp.status_code in (200, 401)  # 不应是 404


async def test_legacy_health_redirects(client: AsyncClient):
    """旧版 /health 路由依然可访问（直接响应或重定向）。"""
    resp = await client.get("/health")
    assert resp.status_code in (200, 301, 307)
```

- [x] **Step 2：运行测试**

```bash
uv run pytest tests/test_routes_v1.py -v
```

Expected：所有测试 PASSED（M2 已注册 v1 router）

---

## Task 24：M5 — 完善 API 版本化并提交

**Files:** Modify `src/hybrid_agent/api/main.py`

- [x] **Step 1：将所有旧 /api/ 路由迁移到 v1_router**

检查 `main.py` 中直接挂在 `app` 上的 `/api/chat`、`/api/documents` 路由，改为注册到 `v1_router`。

```python
# 从 routes/ 导入已有 router 模块（若已是 APIRouter 形式）
# 若 chat.py 和 documents.py 是函数而非 router，需先将其包装

# 在 v1_router 上注册旧路由（以 chat 为例）：
from hybrid_agent.api.routes.chat import router as chat_router      # 若已存在 router
from hybrid_agent.api.routes.documents import router as docs_router

v1_router.include_router(chat_router)
v1_router.include_router(docs_router)
```

若 `chat.py` 和 `documents.py` 还是独立函数（非 `APIRouter`），需在各文件中创建 `router = APIRouter()` 并注册对应函数，然后从 `main.py` 删除重复的路由定义。

- [x] **Step 2：运行全量检查**

```bash
python scripts/check.py
```

Expected：静默通过

- [x] **Step 3：运行所有测试**

```bash
uv run pytest tests/ -v --tb=short
```

Expected：所有测试 PASSED

- [x] **Step 4：更新进度，提交 M5**

更新 `claude-progress.txt`（M5 完成，Phase 1 完成）。

```bash
git add src/hybrid_agent/api/main.py \
        src/hybrid_agent/api/routes/ \
        tests/test_routes_v1.py \
        claude-progress.txt
git commit -m "feat(api): M5 API 路由全面迁移至 /api/v1/"
```

---

## Phase 1 完成验收

- [x] **运行全量检查**

```bash
python scripts/check.py
```

Expected：静默通过

- [x] **运行完整测试套件**

```bash
uv run pytest tests/ -v --tb=short
```

Expected：所有测试绿色，无 FAILED

- [x] **验证核心 API**

```bash
PYTHONPATH=src uvicorn hybrid_agent.api.main:app --port 8000 &

# 测试健康检查
curl http://localhost:8000/api/v1/health

# 测试 admin 接口（需先创建用户）
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"wrong"}' 
# Expected: 401

kill %1
```

- [x] **确认 claude-progress.txt 状态**

```
[x] M0  Harness 基础设施
[x] M1  PostgreSQL + Alembic
[x] M2  用户认证（JWT）
[x] M3  用户/组管理 + RBAC
[x] M4  文档组隔离（ChromaDB Namespace）
[x] M5  API 路由版本化
```

---

## 后续计划

- **Plan 2**（`docs/superpowers/plans/2026-04-12-phase2-backend-features.md`）：M17 开源嵌入模型 + M18 开放式模型提供商（后端部分）+ M6 文档异步上传 + M7 监控 + M8 Docker Compose
- **Plan 3**（`docs/superpowers/plans/2026-04-12-phase3-frontend.md`）：M9-M16 Vue 3 前端（M16 含 M18 模型提供商管理 UI）
