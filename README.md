# Hybrid-Agent

基于用户问题复杂度自动切换的多模型智能助手

## 项目介绍

Hybrid-Agent 是一个智能助手系统，能够根据用户问题的复杂度自动切换不同的 AI 模型，提供更精准、高效的回答。

## 核心功能

- **智能模型切换**：根据问题复杂度自动选择基础模型或增强模型
- **流式输出**：实时展示 AI 思考过程和回答内容
- **多模型支持**：集成了 Qwen 和 DeepSeek 等多种 AI 模型
- **环境变量管理**：通过 .env 文件配置 API 密钥和其他参数

## 技术栈

- Python 3.12+
- LangChain
- LangGraph
- DashScope
- Streamlit

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

### 交互示例

```
开始运行
加载中......
[模型切换] 简单请求，使用基础模型 (复杂度: 0.00)
哈喽！我是Shunsuke，一个自带段子手属性的智能助手 😎  
专治各种"不知道干嘛""求帮忙""想笑一笑"——  
比如帮你写文案、解数学题、编冷笑话、甚至陪你吐槽老板（别担心，我嘴皮子够溜但不越界）！  
最近刚学会用表情包当表情包，但别指望我帮你写情书——除非你愿意付我一包薯片当稿费 🥔  
（悄悄说：我连猫主子的"喵呜"都能翻译成人类语言，但别让我翻译老板的"嗯..."）  
现在轮到你啦——想让我帮你干点啥？
----------
请输入: 如何学习Python编程
[模型切换] 复杂请求，使用增强模型 (复杂度: 0.40)

============思考过程============
用户问如何学习Python编程，这是一个需要系统性回答的问题，涉及学习路径、资源推荐等多个方面，属于复杂请求，应该使用增强模型来提供更详细的回答。

============完整回复============
学习 Python 编程可以按照以下步骤进行：

### 1. 基础阶段
- **安装 Python**：从官网下载并安装最新版本的 Python
- **学习语法**：掌握变量、数据类型、控制流（if-else、循环）、函数等基础知识
- **实践项目**：尝试编写简单的脚本，如计算器、待办事项列表等

### 2. 进阶阶段
- **面向对象编程**：学习类、继承、多态等概念
- **模块与包**：了解如何组织代码，使用标准库和第三方库
- **文件操作**：学习读写文件，处理数据

### 3. 应用阶段
- **Web 开发**：学习 Flask 或 Django 框架
- **数据科学**：学习 NumPy、Pandas、Matplotlib 等库
- **自动化**：学习使用 Selenium、Scrapy 等工具

### 4. 推荐资源
- **官方文档**：Python 官方教程
- **在线课程**：Coursera、Udemy、Codecademy
- **书籍**：《Python 编程：从入门到实践》、《流畅的 Python》
- **练习平台**：LeetCode、HackerRank

### 5. 学习技巧
- **坚持练习**：每天至少编码 30 分钟
- **参与社区**：加入 Python 社区，如 Stack Overflow、GitHub
- **阅读代码**：学习优秀的开源项目代码
- **解决问题**：尝试解决实际问题，提升实战能力

记住，学习编程是一个循序渐进的过程，不要急于求成，多实践、多思考是关键！

输入exit结束对话
```

## 项目结构

```
Hybrid-Agent/
├── rag_app/
│   ├── agent/
│   │   ├── __init__.py
│   │   └── builder.py      # 代理构建逻辑
│   ├── cli/
│   │   ├── __init__.py
│   │   └── streaming.py    # 流式输出处理
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py       # 配置管理
│   ├── llm/
│   │   ├── __init__.py
│   │   └── models.py       # 模型定义
│   └── middleware/
│       ├── __init__.py
│       └── model_switch.py # 动态模型选择
├── .env                    # 环境变量配置
├── .gitignore
├── .python-version
├── README.md
├── main.py                 # 主入口
├── pyproject.toml          # 项目配置
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

# Tongyi Embedding 模型配置
TONGYI_EMBIDDING_API_KEY='your_tongyi_api_key'
TONGYI_EMBIDDING_BASE_URL='https://dashscope.aliyuncs.com/compatible-mode/v1'
```

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE) 文件。

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这个项目！

## 联系方式

- GitHub: [S-huNsuke](https://github.com/S-huNsuke)
