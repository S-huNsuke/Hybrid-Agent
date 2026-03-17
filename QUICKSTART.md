# 快速启动指南

## ✅ 修复完成

所有问题已修复，项目现在可以正常使用！

## 🚀 启动方式

### 1. 命令行模式（CLI）

```bash
# 方式1：使用入口命令（推荐）
hybrid-agent

# 方式2：直接运行
python main.py

# 方式3：使用 uv
uv run hybrid-agent
```

### 2. API 服务模式

```bash
# 启动 FastAPI 服务（需要设置 PYTHONPATH）
export PYTHONPATH="$(pwd)/src"
uvicorn hybrid_agent.api.main:app --reload --host 0.0.0.0 --port 8000

# 访问 API 文档
# http://localhost:8000/docs
```

### 3. Web 界面模式

```bash
# 启动 Streamlit Web 应用（需要设置 PYTHONPATH）
export PYTHONPATH="$(pwd)/src"
streamlit run src/hybrid_agent/web/app.py

# 浏览器自动打开
# http://localhost:8501
```

### 4. Docker 部署模式

```bash
# 复制环境变量文件
cp .env.example .env

# 编辑 .env 文件，配置你的 API Key

# 使用 docker-compose 启动
docker-compose up -d

# 访问服务
# API: http://localhost:8000
# API 文档: http://localhost:8000/docs
# Web 界面: http://localhost:8501

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 📝 已修复的问题

1. ✅ **项目安装** - 已通过 `uv pip install -e .` 安装
2. ✅ **命令行入口** - `hybrid-agent` 命令现在可用
3. ✅ **代码注释** - 修正了 document_tools.py 中的注释错误
4. ✅ **导入路径** - 统一了 web_search.py 的导入路径

## 🧪 功能测试

所有核心功能已验证：
- ✅ 配置加载正常
- ✅ RAG 系统初始化成功
- ✅ Agent 构建正常
- ✅ 工具模块导入正常
- ✅ 模型配置正确

## 📊 当前状态

- **文档数量**: 0 个（知识库为空）
- **向量数据库**: 已初始化
- **SQL 数据库**: 已初始化
- **模型配置**:
  - 基础模型: qwen3-omni-flash-2025-12-01
  - 增强模型: deepseek-chat

## 💡 使用建议

1. **首次使用**: 建议先通过 Web 界面上传一些文档到知识库
2. **API 开发**: 查看 `/docs` 端点了解所有可用的 API
3. **模型选择**:
   - 简单问题使用 Qwen3（速度快）
   - 复杂问题使用 DeepSeek（质量高）
   - 自动模式会根据问题复杂度自动切换

## 🔧 环境要求

- Python 3.12+
- 已配置的 API 密钥（.env 文件）
- 所有依赖已安装

## 📚 更多信息

详见 [README.md](README.md)
