# 任务规格说明书

## 1. 项目概述

- **项目名称**: Hybrid-Agent
- **项目类型**: 基于 Streamlit 的多模型智能助手
- **核心功能**: 支持根据问题复杂度自动/手动切换模型 (Qwen3-omni / DeepSeek-V3)

## 2. 问题分析

### 问题1: 侧边栏按钮样式不对

**原因分析**:
- `fronted.py` 中 CSS 使用了错误的图标
  - 展开状态按钮 (collapsedControl): 使用汉堡菜单 SVG (`☰`)
  - 折叠状态按钮 (stSidebarCollapseButton): 使用关闭图标 (`X`)
- 用户期望的是双向箭头图标: `keyboard_double_arrow_right` 和 `keyboard_double_arrow_left`
- CSS 中使用 `button * { display: none }` 隐藏了原有图标，导致按钮显示不正确

**修复方案**: 
- 将展开按钮的图标改为向右箭头 `keyboard_double_arrow_right`
- 将折叠按钮的图标改为向左箭头 `keyboard_double_arrow_left`

### 问题2: 模型切换功能失效

**原因分析**:
1. **API 调用方式错误**: `model_switch.py` 使用 `from langgraph.config import get_config`，但这个 API 在 langgraph 中可能不存在或已改变
2. **配置传递断裂**: 前端选择模型后存储到 `st.session_state.modelSelector`，但 agent 配置中没有正确传递这个值
3. **select_model 函数无法获取 session_state**: 它依赖不存在的 `get_config()` API 来获取模型选择

**修复方案**:
- 移除无效的 `get_config()` 导入
- 修改 agent 构建方式，传递模型参数
- 前端在调用 agent 时正确传递模型配置

### 问题3: 代码冗余

**原因分析**:
- `model_switch.py` 中的 `get_current_model()` 全局变量与实际使用的模型不一致
- select_model 函数逻辑复杂且无法正常工作

## 3. 修复任务清单

### Task 1: 修复侧边栏按钮样式
- [ ] 修改展开按钮图标为向右箭头
- [ ] 修改折叠按钮图标为向左箭头
- [ ] 移除错误的 `button * { display: none }` 样式
- [ ] 清理 JavaScript 修复脚本

### Task 2: 修复模型切换功能
- [ ] 修复 model_switch.py 中的 get_config 导入问题
- [ ] 修改 select_model 函数接受配置参数
- [ ] 修改 agent builder 正确传递模型参数
- [ ] 修改前端在调用 agent 时传递模型配置

### Task 3: 代码优化
- [ ] 移除 model_switch.py 中的无效导入
- [ ] 简化模型选择逻辑
- [ ] 确保代码风格一致

## 4. 验收标准

1. 侧边栏展开/折叠按钮显示正确的箭头图标
2. 用户可以手动选择模型并生效
3. 自动模式根据问题复杂度正确切换模型
4. 代码无明显冗余和错误
