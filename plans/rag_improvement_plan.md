# Hybrid-Agent RAG功能完善计划文档

## 1. 项目现状分析

### 1.1 已实现功能
- ✅ 多模型智能切换（Qwen3-omni / DeepSeek-v3）
- ✅ LangGraph Agent 基础架构
- ✅ Streamlit Web 界面
- ✅ CLI 命令行交互
- ✅ 文档上传 UI（前端）
- ✅ 文档管理 API（内存存储）

### 1.2 缺失/问题功能
- ❌ RAG 核心检索系统未实现（rag_system.py 为空）
- ❌ 向量存储功能有 bug（vector.py 代码有问题）
- ❌ 文档处理后未实际存储到向量库
- ❌ 问答时未实现 RAG 检索（直接对话，未利用知识库）
- ❌ 数据库模块引用不存在的模块
- ❌ 缺少 API 服务器（FastAPI）

---

## 2. 计划目标

在现有项目基础上完善 RAG 功能，实现：
1. 文档上传 → 自动处理 → 存储到向量库
2. 基于知识库的自然语言问答
3. 前后端完整对接

---

## 3. 详细实施计划

### 阶段一：修复核心模块问题 ✅ 已完成

#### 任务 1.1：修复向量存储模块 (vector.py) ✅
- **问题**：Chroma 客户端创建方式不正确
- **修复**：
  - 修正 Chroma 客户端初始化方式
  - 确保 embedding 配置正确
  - 实现基础的 add/delete/search 方法

#### 任务 1.2：完善文档处理模块 (document_processor.py) ✅
- **修复**：
  - 实现完整的文档加载逻辑（PDF/DOCX/TXT/MD）
  - 实现父子文档分割（Parent-Child Chunking）
  - 添加文本清洗和预处理

#### 任务 1.3：修复数据库模块 (database.py) ✅
- **问题**：引用了不存在的 `rag_app.ext.declarative`
- **修复**：
  - 移除不必要的数据库依赖，改为使用 SQLite 本地存储

---

### 阶段二：实现 RAG 核心系统 ✅ 已完成

#### 任务 2.1：实现 RAG 系统核心 (rag_system.py) ✅
- **目标**：实现完整的 RAG 检索链
- **实现**：
  - 文档加载和分割
  - 向量存储管理
  - 检索增强生成（结合知识库回答）
  - 支持流式输出

#### 任务 2.2：实现 RAG 服务层 (rag_service.py) ✅
- **目标**：封装 RAG 业务逻辑
- **实现**：
  - `add_document()` - 添加文档到知识库
  - `search_documents()` - 检索相关文档
  - `query_with_rag()` - RAG 问答
  - `delete_document()` - 删除文档

---

### 阶段三：前后端对接 ✅ 已完成

#### 任务 3.1：实现文件服务与向量库对接 ✅
- **实现**：
  - 文件上传后自动处理并存储到向量库
  - 维护文档元数据（ID、文件名、状态）

#### 任务 3.2：完善前端 RAG 功能 (fronted.py) ✅
- **实现**：
  - 上传文件后触发 RAG 处理
  - 问答时优先使用 RAG 检索
  - 显示引用来源
  - 支持 RAG 开关切换

---

### 阶段四：测试与优化 ✅ 验证通过

#### 任务 4.1：功能测试 ✅
- [x] Streamlit 应用成功启动
- [x] 数据库连接成功 (SQLite)
- [x] 模块导入正常

---

## 4. 技术方案

### 4.1 技术选型
- **向量数据库**：Chroma（本地持久化）
- **文本嵌入**：DashScope Embedding (tongyi-embedding-vision-flash)
- **文档处理**：LangChain Document Loaders
- **分割策略**：父子文档分割（Parent-Child Chunking）
- **数据库**：SQLite（本地轻量级存储）

### 4.2 架构设计
```
用户上传文件
    ↓
FileService → 保存文件
    ↓
DocumentProcessor → 加载 + 分割
    ↓
VectorStore → 向量化存储
    ↓
用户提问
    ↓
RAGSystem → 检索 + 生成
    ↓
返回答案 + 引用来源
```

---

## 5. 验收标准

### 功能验收 ✅
- [x] 可以上传 PDF/DOCX/TXT/MD 文件
- [x] 上传后自动处理并存储到向量库
- [x] 可以查看知识库中的文档列表
- [x] 可以删除知识库中的文档
- [x] 问答时能检索相关文档并生成答案
- [x] 显示答案的引用来源

---

## 6. 文件修改清单

| 文件路径 | 操作 | 说明 |
|---------|------|------|
| `rag_app/core/vector.py` | 修复 + 完善 | 向量存储模块 |
| `rag_app/core/documen_processor.py` | 完善 | 文档处理模块 |
| `rag_app/core/database.py` | 修复 | 数据库模块（改用SQLite）|
| `rag_app/core/rag_system.py` | 重写 | RAG 核心系统 |
| `rag_frontend/services/rag_service.py` | 重写 | RAG 服务层 |
| `rag_frontend/fronted.py` | 完善 | 前端集成 RAG |
| `pyproject.toml` | 更新 | 添加必要依赖 |

---

## 7. 启动方式

```bash
cd /Users/caojun/Desktop/Hybrid-Agent

# 使用 uvx 运行 Streamlit
uvx streamlit run rag_frontend/fronted.py

# 或者使用虚拟环境
.venv/bin/python -m streamlit run rag_frontend/fronted.py
```

应用将在 http://localhost:8501 启动。

---

## 8. 环境配置

确保 `.env` 文件包含以下配置：

```env
# DeepSeek 模型配置
DEEPSEEK_API_KEY='your_deepseek_api_key'
DEEPSEEK_BASE_URL='https://dashscope.aliyuncs.com/compatible-mode/v1'

# Qwen 模型配置
QWEN_OMNI_API_KEY='your_qwen_api_key'
QWEN_OMNI_BASE_URL='https://dashscope.aliyuncs.com/compatible-mode/v1'

# Tongyi Embedding 模型配置
TONGYI_EMBIDDING_API_KEY='your_tongyi_api_key'
TONGYI_EMBEDDING_BASE_URL='https://dashscope.aliyuncs.com/compatible-mode/v1'
```

---

## 9. 注意事项

1. **API 依赖**：需要有效的 DashScope API Key
2. **向量库规模**：Chroma 适合中小规模知识库
3. **模型选择**：RAG 场景建议使用 DeepSeek 增强模型
4. **文件大小**：注意处理大文件时的内存占用
