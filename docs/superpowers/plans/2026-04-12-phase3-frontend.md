# Hybrid-Agent Phase 3 前端实现计划
# M9-M16 Vue 3 前端（M16 含 M18 模型提供商管理 UI）

> **For agentic workers:** 使用 `superpowers:subagent-driven-development` 执行本计划，逐任务派遣子 agent。

**Goal:** 实现完整的 Vue 3 前端应用，包含登录认证、聊天界面、文档管理、管理后台和个人设置（含模型提供商管理 UI）。

**Architecture:** Vite 5 + Vue 3.4（`<script setup>`）+ Element Plus 2 + Pinia 2 + Vue Router 4 + Axios。前端代理对接 FastAPI `/api/v1/` 接口（已在 Phase 1+2 完成）。

**Tech Stack:** Node.js 22 LTS, pnpm, Vite 5, Vue 3.4, Element Plus 2.x, Pinia 2, Vue Router 4, Axios, @vueuse/core, markdown-it, highlight.js, Vitest（单元测试）

**前提条件:**
- 后端 API 已就绪（Phase 1 + Phase 2 完成，80 个后端测试通过）
- Docker Compose 可以通过 `docker compose up` 启动后端服务

---

## 前置条件

- 安装 Node.js 22 LTS：`fnm install 22`（项目使用 fnm 管理 Node 版本）
- 安装 pnpm：`npm install -g pnpm`
- 工作目录：`/Users/caojun/Desktop/Hybrid-Agent`（或 worktree 路径）
- 前端代码放在 `frontend/` 目录

---

## 文件地图

### M9 新增文件
```
frontend/
├── index.html
├── vite.config.js              ← 含代理配置（/api → http://localhost:8000）
├── package.json
├── .eslintrc.js
├── src/
│   ├── main.js
│   ├── App.vue
│   ├── router/index.js         ← 路由定义（含守卫框架）
│   ├── stores/index.js         ← Pinia 初始化
│   ├── api/request.js          ← Axios 实例 + 拦截器
│   ├── styles/
│   │   ├── main.css            ← 全局样式重置
│   │   └── tokens.css          ← (M10 填充)
│   ├── views/
│   │   └── NotFoundView.vue    ← 404 页面
│   └── components/
│       └── AppLogo.vue
├── Dockerfile                  ← Nginx 静态托管
└── nginx.conf                  ← 含 API 反向代理
```

### M10 新增文件
```
frontend/src/styles/tokens.css              ← CSS 变量定义（颜色、间距、字体）
frontend/src/styles/element-override.css    ← Element Plus 主题覆盖
```

### M11 新增文件
```
frontend/src/views/LoginView.vue
frontend/src/stores/user.js        ← Pinia：token 存储、登录/登出 action
frontend/src/api/auth.js           ← HTTP 封装：login, logout, me, refresh
```

### M12 新增文件
```
frontend/src/components/layout/AppShell.vue
frontend/src/components/layout/AppHeader.vue
frontend/src/components/layout/AppSidebar.vue
```

### M13 新增文件
```
frontend/src/views/ChatView.vue
frontend/src/components/chat/MessageList.vue
frontend/src/components/chat/MessageItem.vue
frontend/src/components/chat/ChatInput.vue
frontend/src/components/chat/SourcePanel.vue
frontend/src/composables/useSSE.js
frontend/src/stores/chat.js
frontend/src/api/chat.js
```

### M14 新增文件
```
frontend/src/views/DocumentsView.vue
frontend/src/components/documents/UploadZone.vue
frontend/src/components/documents/DocumentList.vue
frontend/src/composables/useUpload.js
frontend/src/stores/documents.js
frontend/src/api/documents.js
```

### M15 新增文件
```
frontend/src/views/AdminView.vue
frontend/src/components/admin/UserTable.vue
frontend/src/components/admin/GroupTable.vue
frontend/src/components/admin/CreateUserModal.vue
frontend/src/components/admin/CreateGroupModal.vue
frontend/src/stores/admin.js
frontend/src/api/admin.js
```

### M16 新增文件
```
frontend/src/views/SettingsView.vue
frontend/src/components/settings/ProviderList.vue
frontend/src/components/settings/ProviderFormModal.vue
frontend/src/stores/settings.js
frontend/src/api/settings.js
```

---

## Task 1：M9 — 初始化 Vue 3 项目脚手架

**Files:** `frontend/` 整个目录

- [ ] **Step 1：创建 Vite 项目**

```bash
cd /Users/caojun/Desktop/Hybrid-Agent
pnpm create vite frontend --template vue
cd frontend && pnpm install
```

- [ ] **Step 2：安装依赖**

```bash
pnpm add element-plus pinia vue-router@4 axios @vueuse/core markdown-it highlight.js
pnpm add -D @vitejs/plugin-vue @vue/eslint-config-prettier eslint vitest @vue/test-utils
```

- [ ] **Step 3：配置 vite.config.js（含 API 代理）**

```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) }
  },
  server: {
    port: 3000,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/metrics': { target: 'http://localhost:8000', changeOrigin: true },
    }
  }
})
```

- [ ] **Step 4：初始化 main.js**

```javascript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import router from './router'
import App from './App.vue'
import './styles/main.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')
```

- [ ] **Step 5：创建基础 Axios 实例（api/request.js）**

```javascript
import axios from 'axios'
import { useUserStore } from '@/stores/user'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

request.interceptors.request.use(config => {
  const userStore = useUserStore()
  if (userStore.token) {
    config.headers.Authorization = `Bearer ${userStore.token}`
  }
  return config
})

request.interceptors.response.use(
  response => response.data,
  async error => {
    if (error.response?.status === 401) {
      const userStore = useUserStore()
      await userStore.logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default request
```

- [ ] **Step 6：创建 Nginx Dockerfile**

```dockerfile
# frontend/Dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

```nginx
# frontend/nginx.conf
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location /api {
        proxy_pass http://app:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 7：验证**

```bash
cd frontend && pnpm dev
```

Expected：`http://localhost:3000` 可访问，无控制台报错

- [ ] **Step 8：提交**

```bash
git add frontend/
git commit -m "feat(frontend): M9 Vue 3 + Vite 项目脚手架初始化"
```

---

## Task 2：M10 — 设计系统（Design Tokens）

**Files:** `frontend/src/styles/tokens.css`, `frontend/src/styles/element-override.css`

- [ ] **Step 1：创建 tokens.css**

```css
/* frontend/src/styles/tokens.css */
:root {
  /* 颜色系统 */
  --color-bg:          #FFFFFF;
  --color-bg-subtle:   #F9FAFB;
  --color-bg-muted:    #F3F4F6;
  --color-border:      #E5E7EB;
  --color-border-muted:#F3F4F6;
  --color-text:        #111827;
  --color-text-muted:  #6B7280;
  --color-text-subtle: #9CA3AF;
  --color-accent:      #7C3AED;
  --color-accent-hover:#6D28D9;
  --color-user-bubble: #F3F4F6;
  --color-code-bg:     #1E1E2E;

  /* 间距（8px 网格） */
  --space-1: 4px;   --space-2: 8px;   --space-3: 12px;
  --space-4: 16px;  --space-6: 24px;  --space-8: 32px;

  /* 字体 */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  --font-size-sm: 13px;  --font-size-base: 14px;  --font-size-lg: 16px;

  /* 圆角 */
  --radius-sm: 6px;  --radius-md: 10px;  --radius-lg: 16px;

  /* 阴影 */
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

- [ ] **Step 2：创建 element-override.css**（覆盖 Element Plus 主题色为紫色）

- [ ] **Step 3：在 main.css 中引入 tokens.css 和 element-override.css**

- [ ] **Step 4：提交**

```bash
git add frontend/src/styles/
git commit -m "feat(frontend): M10 设计系统 Design Tokens + 深色模式"
```

---

## Task 3：M11 — 登录页 + 路由守卫

**Files:** `LoginView.vue`, `stores/user.js`, `api/auth.js`, `router/index.js`

- [ ] **Step 1：创建 stores/user.js（Pinia store）**

```javascript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin, logout as apiLogout, me as apiMe } from '@/api/auth'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('access_token') || '')
  const userInfo = ref(null)

  const isLoggedIn = computed(() => !!token.value)

  async function login(username, password) {
    const data = await apiLogin(username, password)
    token.value = data.access_token
    localStorage.setItem('access_token', data.access_token)
    userInfo.value = await apiMe()
  }

  async function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('access_token')
  }

  async function fetchMe() {
    if (token.value && !userInfo.value) {
      userInfo.value = await apiMe()
    }
  }

  return { token, userInfo, isLoggedIn, login, logout, fetchMe }
})
```

- [ ] **Step 2：创建 api/auth.js**

- [ ] **Step 3：创建 LoginView.vue**

居中卡片（宽 360px），白色背景，紫色主按钮，无注册入口。

```vue
<template>
  <div class="login-page">
    <el-card class="login-card">
      <h1 class="login-title">Hybrid Agent</h1>
      <el-form @submit.prevent="handleLogin">
        <el-form-item>
          <el-input v-model="username" placeholder="用户名" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="password" type="password" placeholder="密码" />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" class="login-btn">
          登 录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>
```

- [ ] **Step 4：配置 router/index.js（路由守卫）**

```javascript
import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes = [
  { path: '/login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
  { path: '/', redirect: '/chat' },
  { path: '/chat', component: () => import('@/views/ChatView.vue') },
  { path: '/documents', component: () => import('@/views/DocumentsView.vue') },
  { path: '/admin', component: () => import('@/views/AdminView.vue'), meta: { roles: ['admin'] } },
  { path: '/settings', component: () => import('@/views/SettingsView.vue') },
  { path: '/:pathMatch(.*)*', component: () => import('@/views/NotFoundView.vue') },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  const userStore = useUserStore()
  if (!to.meta.public && !userStore.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.roles && !to.meta.roles.includes(userStore.userInfo?.role)) {
    return { path: '/chat' }
  }
})

export default router
```

- [ ] **Step 5：提交**

```bash
git add frontend/src/views/LoginView.vue frontend/src/stores/user.js frontend/src/api/auth.js frontend/src/router/
git commit -m "feat(frontend): M11 登录页 + JWT token 存储 + 路由守卫"
```

---

## Task 4：M12 — 主布局（AppShell）

**Files:** `components/layout/AppShell.vue`, `AppHeader.vue`, `AppSidebar.vue`

布局规范：
- 顶栏高 48px，固定，左侧 Logo + 组名，右侧头像下拉（退出登录）
- 侧边栏宽 240px，bg: `--color-bg-subtle`，导航项含聊天/文档库/管理后台（admin 才显示）/个人设置
- 激活项：左侧 2px 紫色边线 + `--color-bg-muted` 背景
- 移动端（< 768px）侧边栏收起为抽屉

- [ ] **Step 1：创建 AppShell.vue（主框架）**
- [ ] **Step 2：创建 AppHeader.vue（顶栏）**
- [ ] **Step 3：创建 AppSidebar.vue（侧边栏，含路由高亮和权限控制）**
- [ ] **Step 4：修改 App.vue，登录后使用 AppShell 包裹，登录页不包裹**
- [ ] **Step 5：提交**

```bash
git commit -m "feat(frontend): M12 主布局 AppShell（顶栏 + 侧边栏 + 移动端抽屉）"
```

---

## Task 5：M13 — 聊天界面

**Files:** `ChatView.vue`, `components/chat/*`, `composables/useSSE.js`, `stores/chat.js`, `api/chat.js`

- [ ] **Step 1：创建 api/chat.js（HTTP 封装）**
- [ ] **Step 2：创建 stores/chat.js（Pinia store，管理消息列表和会话）**
- [ ] **Step 3：创建 composables/useSSE.js（SSE 流式接收封装）**

```javascript
export function useSSE(url, { onChunk, onDone, onError }) {
  const isStreaming = ref(false)
  let controller = null

  async function start(body) {
    isStreaming.value = true
    controller = new AbortController()
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
    const reader = resp.body.getReader()
    // 逐块读取 SSE 数据
  }

  function stop() { controller?.abort(); isStreaming.value = false }
  return { start, stop, isStreaming }
}
```

- [ ] **Step 4：创建 MessageList.vue + MessageItem.vue（含 Markdown 渲染）**
  - AI 消息：无气泡，左对齐，markdown-it 渲染，代码块 highlight.js + 一键复制
  - 用户消息：右对齐，圆角气泡，`background: var(--color-user-bubble)`
  
- [ ] **Step 5：创建 SourcePanel.vue（来源引用折叠面板）**
- [ ] **Step 6：创建 ChatInput.vue（文本输入 + 模型选择器 + 发送按钮）**
- [ ] **Step 7：组合 ChatView.vue**
- [ ] **Step 8：提交**

```bash
git commit -m "feat(frontend): M13 聊天界面（SSE 流式输出 + Markdown 渲染 + 来源引用）"
```

---

## Task 6：M14 — 文档管理页

**Files:** `DocumentsView.vue`, `components/documents/*`, `composables/useUpload.js`, `stores/documents.js`, `api/documents.js`

- [ ] **Step 1：创建 api/documents.js + stores/documents.js**
- [ ] **Step 2：创建 UploadZone.vue（拖拽区域，虚线框样式）**
- [ ] **Step 3：创建 composables/useUpload.js（轮询 task_id 进度）**

```javascript
export function useUpload() {
  async function upload(file) {
    const formData = new FormData()
    formData.append('file', file)
    const { task_id } = await request.post('/documents/upload', formData)
    // 每 1.5s 轮询 /documents/tasks/{task_id}
    return pollProgress(task_id)
  }
}
```

- [ ] **Step 4：创建 DocumentList.vue（文件名/大小/时间/删除，删除需二次确认）**
- [ ] **Step 5：组合 DocumentsView.vue**
- [ ] **Step 6：提交**

```bash
git commit -m "feat(frontend): M14 文档管理页（拖拽上传 + 进度轮询 + 列表管理）"
```

---

## Task 7：M15 — 管理后台

**Files:** `AdminView.vue`, `components/admin/*`, `stores/admin.js`, `api/admin.js`

- [ ] **Step 1：创建 api/admin.js + stores/admin.js**
- [ ] **Step 2：创建 UserTable.vue（用户列表 + 编辑 + 停用 + 重置密码）**
- [ ] **Step 3：创建 GroupTable.vue（组列表 + 查看成员 + 编辑 + 删除）**
- [ ] **Step 4：创建 CreateUserModal.vue + CreateGroupModal.vue**
- [ ] **Step 5：组合 AdminView.vue（Tab: 用户管理 / 组管理，仅 admin 可访问）**
- [ ] **Step 6：提交**

```bash
git commit -m "feat(frontend): M15 管理后台（用户管理 + 组管理，admin 专属）"
```

---

## Task 8：M16 — 个人设置页（含 M18 模型提供商管理 UI）

**Files:** `SettingsView.vue`, `components/settings/ProviderList.vue`, `components/settings/ProviderFormModal.vue`, `stores/settings.js`, `api/settings.js`

- [ ] **Step 1：创建 api/settings.js**（对接 `/api/v1/settings/providers/*` 7 个端点）

- [ ] **Step 2：创建 stores/settings.js**（Pinia store，管理提供商列表 + 预设）

- [ ] **Step 3：创建 ProviderList.vue（提供商卡片列表）**

```
┌──────────────────────────────────────────────┐
│  🟢  我的 GPT-4                   [默认]      │
│      OpenAI · gpt-4o                         │
│      https://api.openai.com/v1               │
│                           [编辑]  [删除]     │
└──────────────────────────────────────────────┘
```

- [ ] **Step 4：创建 ProviderFormModal.vue（添加/编辑对话框）**

```
选择预设：[OpenAI] [Anthropic] [DeepSeek] [Qwen] [Groq] [Mistral] [Ollama] [自定义]

名称      [______________]
Base URL  [______________]  ← 选预设后自动填充
API Key   [**************]  [👁]
默认模型  [______________]  ← 选预设后显示推荐模型

[✓] 设为我的默认提供商

[测试连接]  → 🟢 连接成功，延迟 320ms / 🔴 连接失败：xxx

[取消]  [保存]
```

- [ ] **Step 5：组合 SettingsView.vue（Tab: 个人信息 / 修改密码 / 模型提供商 / 外观）**

- [ ] **Step 6：添加主题切换逻辑（useColorMode，localStorage 持久化）**

- [ ] **Step 7：提交**

```bash
git commit -m "feat(frontend): M16 个人设置页（含 M18 模型提供商管理 UI）"
```

---

## Phase 3 完成验收

- [ ] **前端代码检查**

```bash
cd frontend
pnpm lint && pnpm type-check && pnpm test:unit
```

Expected：全部通过

- [ ] **后端联调验证**（需启动后端）

```bash
# 终端 1：启动后端
source .venv/bin/activate
PYTHONPATH=src uvicorn hybrid_agent.api.main:app --port 8000

# 终端 2：启动前端
cd frontend && pnpm dev
```

验证核心流程：
1. 访问 `http://localhost:3000` → 跳转登录页
2. 创建测试用户（先用后端 API）→ 登录成功
3. 上传文档 → 进度显示 → 文档列表更新
4. 聊天提问 → 流式输出 → 来源引用展示
5. admin 登录 → 管理后台可见
6. 个人设置 → 添加模型提供商 → 测试连接

- [ ] **更新 claude-progress.txt**（所有 Phase 3 模块 `[x]`）

- [ ] **最终提交**

```bash
git commit -m "docs: Phase 3 全部完成，更新 claude-progress.txt"
```
