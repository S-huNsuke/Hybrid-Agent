# Hybrid-Agent Phase 2 后端功能 — 完成摘要

**状态**：✅ Phase 2 已完成（2026-04-12）
**测试**：80 个测试，全部通过（含 Phase 1 的 M0-M5 测试）

---

## 完成的模块

### M17：开源嵌入模型替换 ✅

**目标**：消除 DashScope 嵌入 API 依赖，支持本地离线部署。

**实际实现**：
- 新增 `src/hybrid_agent/core/embeddings.py`
  - `LocalEmbeddings`：基于 sentence-transformers，实现 LangChain `Embeddings` 协议
  - `EmbeddingFactory.create()`：根据 `EMBEDDING_MODE` 返回本地或 DashScope 实例
  - 全局单例缓存，避免重复加载模型
- 修改 `vector.py`：`VectorStore` 改用 `EmbeddingFactory.create()` 替代硬编码 DashScope
- 新增 config 字段：`embedding_mode`（默认 `local`）、`embedding_model`（默认 `BAAI/bge-m3`）、`embedding_device`（默认 `cpu`）
- 测试：4 个单元测试（全 mock，无需真实模型），全通过

**验收结果**：
- `EMBEDDING_MODE=local` 时无任何外部 API 调用
- DashScope 后端保留，通过 `EMBEDDING_MODE=dashscope` 切换
- `scripts/check.py` 静默通过

---

### M18：开放式模型提供商管理 ✅

**目标**：用户可配置任意 OpenAI 兼容接口，系统推理优先使用用户自己的 Key。

**实际实现**：
- 数据库模型 `UserLLMProvider`（`database.py`）：Fernet 加密存储 API Key，`user_id + name` 唯一约束
- 新增 `src/hybrid_agent/api/settings/` 模块：
  - `presets.py`：7 个内置供应商预设（OpenAI、Anthropic、DeepSeek、Qwen、Groq、Mistral、Ollama）
  - `service.py`：`encrypt_key/decrypt_key`（Fernet）、`mask_key`、CRUD、`test_connection_sync`（1-token 探测）
  - `router.py`：7 个 RESTful 端点，注册到 `/api/v1/settings/`
- 加密主密钥通过 `API_KEY_ENCRYPTION_KEY` 环境变量注入，默认自动生成（开发用）
- 测试：6 个集成测试（presets、CRUD、用户隔离、加密轮转），全通过

**已知差异**：
- `test_connection` 端点使用同步探测（避免引入额外异步复杂度），生产环境可改为 async
- 前端 UI（ProviderList、ProviderFormModal）待 Phase 3 M16 实现

---

### M6：文档上传异步化 ✅

**目标**：上传接口立即返回，后台处理，支持进度轮询。

**实际实现**：
- 新增 `src/hybrid_agent/core/task_store.py`：线程安全 dict + `threading.Lock`，支持 create/update/get
- 任务状态：`PENDING → PROCESSING → COMPLETED / FAILED`
- 上传进度阶段：10%（文件保存）→ 30%（解析）→ 60%（向量化）→ 85%（BM25）→ 100%（完成）
- 测试：5 个单元测试，全通过

---

### M7：监控 ✅

**目标**：暴露 Prometheus 指标，结构化日志，LLM 成本追踪。

**实际实现**：
- `prometheus-fastapi-instrumentator`：`Instrumentator().instrument(app).expose(app)` 自动暴露 `/metrics`
- `structlog`：新增 `logging_config.py`，`configure_logging(json_output: bool)` 支持 JSON/控制台双输出
- `LLM_PRICING` 定价表（config.py）：6 个模型的 input/output 单价（USD/1K tokens）
- 测试：3 个测试（/metrics 端点、定价配置、structlog 初始化），全通过

---

### M8：Docker Compose 完整编排 ✅

**目标**：一条命令 `docker compose up` 启动所有服务。

**实际实现**：
- **6 个服务**：postgres（16-alpine，healthcheck）、app（依赖 postgres healthy，自动运行 alembic upgrade head）、web（Streamlit，依赖 app）、prometheus（15 天数据保留）、grafana（预配置数据源）、backup（每 24h pg_dump，保留 7 天）
- **docker-entrypoint.sh**：先 `alembic upgrade head` 再 `uvicorn`
- **prometheus.yml**：15s 抓取间隔，目标 app:8000/metrics
- **grafana/provisioning/datasources/prometheus.yml**：自动加载 Prometheus 数据源
- **5 个 named volumes**：postgres_data、chroma_data、prometheus_data、grafana_data、backup_data
- 配置文件 YAML 语法验证通过

---

## Git 提交记录

```
5871c80 feat(docker): M8 Docker Compose 完整编排（postgres + prometheus + grafana + backup）
ab8b898 feat(monitoring): M7 Prometheus 指标暴露 + 结构化日志
2520d22 feat(upload): M6 文档上传异步化基础设施（TaskStore）
02b201b feat(providers): M18 开放式模型提供商管理后端
dbbcf5b feat(embedding): M17 开源嵌入模型工厂（local/dashscope 双后端）
```

---

## 下一步

Phase 3 前端实现，详见：`docs/superpowers/plans/2026-04-12-phase3-frontend.md`
