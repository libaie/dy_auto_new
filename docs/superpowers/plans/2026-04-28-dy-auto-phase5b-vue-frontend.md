# Phase 5b: Vue 管理后台前端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建完整的 Vue 3 管理后台，覆盖仪表盘、账号管理、设备管理、任务中心、选择器管理、数据统计 6 个页面

**Architecture:** Vue 3 + Vite SPA，Headless UI 提供无样式交互组件（Dialog、Menu、Switch），Tailwind CSS 负责样式，Pinia 管理状态，Axios 封装 API 调用。所有页面通过 JWT token 认证访问 Phase 5a 已实现的后端 API。

**Tech Stack:** Vue 3 / Vite / Pinia / Vue Router / Axios / Headless UI / Tailwind CSS / Chart.js

---

## 文件结构

```
web/
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
├── src/
│   ├── main.js                      # Vue app 入口
│   ├── App.vue                      # 根组件，RouterView
│   ├── router.js                    # Vue Router 配置
│   ├── stores/
│   │   ├── auth.js                  # 认证 store (login/logout/token)
│   │   └── app.js                   # 全局状态 (sidebar, notifications)
│   ├── api/
│   │   ├── client.js                # Axios 实例 + 拦截器
│   │   ├── auth.js                  # 认证 API
│   │   ├── accounts.js              # 账号 API
│   │   ├── devices.js               # 设备 API
│   │   ├── tasks.js                 # 任务 API
│   │   ├── selectors.js             # 选择器 API
│   │   └── stats.js                 # 统计 API
│   ├── layouts/
│   │   └── AdminLayout.vue          # 侧边栏 + 顶栏 + 内容区
│   ├── components/
│   │   ├── DataTable.vue            # 通用数据表格（分页、排序）
│   │   ├── ConfirmDialog.vue        # 确认对话框
│   │   ├── StatusBadge.vue          # 状态标签
│   │   ├── LoadingSpinner.vue       # 加载动画
│   │   ├── EmptyState.vue           # 空状态提示
│   │   └── NotificationToast.vue    # 通知提示
│   └── views/
│       ├── LoginPage.vue            # 登录页
│       ├── DashboardPage.vue        # 仪表盘
│       ├── AccountsPage.vue         # 账号管理
│       ├── DevicesPage.vue          # 设备管理
│       ├── TasksPage.vue            # 任务中心
│       ├── SelectorsPage.vue        # 选择器管理
│       └── StatsPage.vue            # 数据统计
```

---

## Task 1: 项目初始化

**Files:**
- Create: `web/package.json`
- Create: `web/vite.config.js`
- Create: `web/tailwind.config.js`
- Create: `web/postcss.config.js`
- Create: `web/index.html`
- Create: `web/src/main.js`
- Create: `web/src/App.vue`

- [ ] **Step 1: 初始化 Vite + Vue 3 项目**

```bash
cd d:/devWorkspace/jsProjects/dy_auto
npm create vite@latest web -- --template vue
cd web
```

- [ ] **Step 2: 安装依赖**

```bash
cd d:/devWorkspace/jsProjects/dy_auto/web
npm install vue-router@4 pinia axios @headlessui/vue chart.js
npm install -D tailwindcss @tailwindcss/vite
```

- [ ] **Step 3: 配置 Vite**

```js
// web/vite.config.js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 4: 配置 Tailwind CSS**

```css
/* web/src/style.css */
@import "tailwindcss";
```

- [ ] **Step 5: 创建入口文件**

```js
// web/src/main.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router.js'
import './style.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
```

```vue
<!-- web/src/App.vue -->
<template>
  <RouterView />
</template>
```

- [ ] **Step 6: 验证项目启动**

```bash
cd d:/devWorkspace/jsProjects/dy_auto/web
npm run dev
```

Expected: Vite dev server running at http://localhost:3000

- [ ] **Step 7: Commit**

```bash
git add web/
git commit -m "chore: initialize Vue 3 + Vite + Tailwind project"
```

---

## Task 2: API 客户端与认证

**Files:**
- Create: `web/src/api/client.js`
- Create: `web/src/api/auth.js`
- Create: `web/src/stores/auth.js`
- Create: `web/src/router.js`
- Create: `web/src/views/LoginPage.vue`

- [ ] **Step 1: 创建 Axios 客户端**

```js
// web/src/api/client.js
import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor: attach JWT token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor: handle 401
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default client
```

- [ ] **Step 2: 创建认证 API**

```js
// web/src/api/auth.js
import client from './client.js'

export function login(username, password) {
  return client.post('/auth/login', { username, password })
}
```

- [ ] **Step 3: 创建认证 Store**

```js
// web/src/stores/auth.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi } from '../api/auth.js'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const username = ref(localStorage.getItem('username') || '')

  const isLoggedIn = computed(() => !!token.value)

  async function login(user, password) {
    const { data } = await loginApi(user, password)
    token.value = data.token
    username.value = user
    localStorage.setItem('token', data.token)
    localStorage.setItem('username', user)
  }

  function logout() {
    token.value = ''
    username.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('username')
  }

  return { token, username, isLoggedIn, login, logout }
})
```

- [ ] **Step 4: 创建路由**

```js
// web/src/router.js
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './stores/auth.js'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('./views/LoginPage.vue'),
  },
  {
    path: '/',
    component: () => import('./layouts/AdminLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'Dashboard', component: () => import('./views/DashboardPage.vue') },
      { path: 'accounts', name: 'Accounts', component: () => import('./views/AccountsPage.vue') },
      { path: 'devices', name: 'Devices', component: () => import('./views/DevicesPage.vue') },
      { path: 'tasks', name: 'Tasks', component: () => import('./views/TasksPage.vue') },
      { path: 'selectors', name: 'Selectors', component: () => import('./views/SelectorsPage.vue') },
      { path: 'stats', name: 'Stats', component: () => import('./views/StatsPage.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return { name: 'Login' }
  }
  if (to.name === 'Login' && auth.isLoggedIn) {
    return { name: 'Dashboard' }
  }
})

export default router
```

- [ ] **Step 5: 创建登录页**

```vue
<!-- web/src/views/LoginPage.vue -->
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const router = useRouter()
const auth = useAuthStore()

const form = ref({ username: '', password: '' })
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(form.value.username, form.value.password)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Login failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50">
    <div class="w-full max-w-sm bg-white rounded-lg shadow p-8">
      <h1 class="text-2xl font-bold text-center mb-6">抖音自动化助手</h1>
      <form @submit.prevent="handleLogin" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">用户名</label>
          <input v-model="form.username" type="text" required
            class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">密码</label>
          <input v-model="form.password" type="password" required
            class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <p v-if="error" class="text-red-600 text-sm">{{ error }}</p>
        <button type="submit" :disabled="loading"
          class="w-full bg-blue-600 text-white rounded-md py-2 hover:bg-blue-700 disabled:opacity-50">
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>
    </div>
  </div>
</template>
```

- [ ] **Step 6: 创建占位页面**

为 Dashboard、Accounts、Devices、Tasks、Selectors、Stats 各创建一个最小占位页面：

```vue
<!-- web/src/views/DashboardPage.vue (其他页面类似) -->
<template>
  <div>
    <h1 class="text-2xl font-bold">仪表盘</h1>
    <p class="text-gray-500 mt-2">即将实现...</p>
  </div>
</template>
```

- [ ] **Step 7: 验证登录流程**

```bash
cd d:/devWorkspace/jsProjects/dy_auto/web
npm run dev
```

访问 http://localhost:3000，应重定向到登录页。输入 admin/admin123 登录后跳转到仪表盘。

- [ ] **Step 8: Commit**

```bash
git add web/src/api/ web/src/stores/ web/src/router.js web/src/views/LoginPage.vue web/src/views/DashboardPage.vue web/src/views/AccountsPage.vue web/src/views/DevicesPage.vue web/src/views/TasksPage.vue web/src/views/SelectorsPage.vue web/src/views/StatsPage.vue
git commit -m "feat: add API client, auth store, router, and login page"
```

---

## Task 3: 管理后台布局

**Files:**
- Create: `web/src/layouts/AdminLayout.vue`
- Create: `web/src/components/NotificationToast.vue`

- [ ] **Step 1: 创建管理后台布局**

```vue
<!-- web/src/layouts/AdminLayout.vue -->
<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const sidebarOpen = ref(true)

const navItems = [
  { name: '仪表盘', path: '/', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
  { name: '账号管理', path: '/accounts', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z' },
  { name: '设备管理', path: '/devices', icon: 'M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z' },
  { name: '任务中心', path: '/tasks', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01' },
  { name: '选择器管理', path: '/selectors', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
  { name: '数据统计', path: '/stats', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
]

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="min-h-screen flex bg-gray-100">
    <!-- Sidebar -->
    <aside :class="[sidebarOpen ? 'w-64' : 'w-16', 'bg-gray-900 text-white flex flex-col transition-all duration-200']">
      <div class="p-4 flex items-center justify-between">
        <span v-if="sidebarOpen" class="font-bold text-lg">抖音助手</span>
        <button @click="sidebarOpen = !sidebarOpen" class="text-gray-400 hover:text-white">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      </div>

      <nav class="flex-1 mt-4">
        <router-link v-for="item in navItems" :key="item.path" :to="item.path"
          class="flex items-center px-4 py-3 text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
          :class="{ 'bg-gray-800 text-white': route.path === item.path }">
          <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="item.icon" />
          </svg>
          <span v-if="sidebarOpen" class="ml-3">{{ item.name }}</span>
        </router-link>
      </nav>

      <div class="p-4 border-t border-gray-800">
        <button @click="handleLogout" class="flex items-center text-gray-400 hover:text-white w-full">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          <span v-if="sidebarOpen" class="ml-3">退出登录</span>
        </button>
      </div>
    </aside>

    <!-- Main content -->
    <main class="flex-1 overflow-auto">
      <div class="p-6">
        <RouterView />
      </div>
    </main>
  </div>
</template>
```

- [ ] **Step 2: 创建通知组件**

```vue
<!-- web/src/components/NotificationToast.vue -->
<script setup>
import { ref, onMounted } from 'vue'

const props = defineProps({
  message: String,
  type: { type: String, default: 'success' },
  duration: { type: Number, default: 3000 },
})

const emit = defineEmits(['close'])
const visible = ref(true)

onMounted(() => {
  setTimeout(() => {
    visible.value = false
    emit('close')
  }, props.duration)
})
</script>

<template>
  <div v-if="visible"
    class="fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg text-sm"
    :class="{
      'bg-green-100 text-green-800 border border-green-200': type === 'success',
      'bg-red-100 text-red-800 border border-red-200': type === 'error',
      'bg-yellow-100 text-yellow-800 border border-yellow-200': type === 'warning',
    }">
    {{ message }}
  </div>
</template>
```

- [ ] **Step 3: 验证布局**

登录后应看到侧边栏导航，点击各菜单可切换页面。侧边栏可折叠。

- [ ] **Step 4: Commit**

```bash
git add web/src/layouts/ web/src/components/
git commit -m "feat: add admin layout with sidebar navigation and notification toast"
```

---

## Task 4: 通用组件

**Files:**
- Create: `web/src/components/DataTable.vue`
- Create: `web/src/components/ConfirmDialog.vue`
- Create: `web/src/components/StatusBadge.vue`
- Create: `web/src/components/LoadingSpinner.vue`
- Create: `web/src/components/EmptyState.vue`

- [ ] **Step 1: 创建数据表格组件**

```vue
<!-- web/src/components/DataTable.vue -->
<script setup>
defineProps({
  columns: { type: Array, required: true },
  data: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
})

const emit = defineEmits(['page-change'])
</script>

<template>
  <div>
    <div v-if="loading" class="flex justify-center py-12">
      <LoadingSpinner />
    </div>
    <div v-else-if="data.length === 0" class="py-12">
      <EmptyState message="暂无数据" />
    </div>
    <div v-else>
      <div class="overflow-x-auto bg-white rounded-lg shadow">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th v-for="col in columns" :key="col.key"
                class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {{ col.label }}
              </th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr v-for="(row, i) in data" :key="i" class="hover:bg-gray-50">
              <td v-for="col in columns" :key="col.key" class="px-6 py-4 whitespace-nowrap text-sm">
                <slot :name="col.key" :row="row" :value="row[col.key]">
                  {{ row[col.key] }}
                </slot>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <!-- Pagination -->
      <div v-if="total > pageSize" class="flex justify-between items-center mt-4 text-sm text-gray-600">
        <span>共 {{ total }} 条</span>
        <div class="flex gap-2">
          <button @click="emit('page-change', page - 1)" :disabled="page <= 1"
            class="px-3 py-1 border rounded disabled:opacity-50">上一页</button>
          <span class="px-3 py-1">{{ page }}</span>
          <button @click="emit('page-change', page + 1)" :disabled="page * pageSize >= total"
            class="px-3 py-1 border rounded disabled:opacity-50">下一页</button>
        </div>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: 创建确认对话框**

```vue
<!-- web/src/components/ConfirmDialog.vue -->
<script setup>
import { Dialog, DialogPanel, DialogTitle, TransitionRoot, TransitionChild } from '@headlessui/vue'

defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '确认操作' },
  message: { type: String, default: '确定要执行此操作吗？' },
  confirmText: { type: String, default: '确定' },
  danger: { type: Boolean, default: false },
})

const emit = defineEmits(['confirm', 'cancel'])
</script>

<template>
  <TransitionRoot :show="open" as="template">
    <Dialog @close="emit('cancel')" class="relative z-50">
      <TransitionChild enter="ease-out duration-200" enter-from="opacity-0" enter-to="opacity-100"
        leave="ease-in duration-150" leave-from="opacity-100" leave-to="opacity-0">
        <div class="fixed inset-0 bg-black/30" />
      </TransitionChild>

      <div class="fixed inset-0 flex items-center justify-center p-4">
        <TransitionChild enter="ease-out duration-200" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100"
          leave="ease-in duration-150" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
          <DialogPanel class="w-full max-w-sm bg-white rounded-lg p-6 shadow-xl">
            <DialogTitle class="text-lg font-medium text-gray-900">{{ title }}</DialogTitle>
            <p class="mt-2 text-sm text-gray-500">{{ message }}</p>
            <div class="mt-4 flex justify-end gap-3">
              <button @click="emit('cancel')"
                class="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50">取消</button>
              <button @click="emit('confirm')"
                class="px-4 py-2 text-sm text-white rounded-md"
                :class="danger ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'">
                {{ confirmText }}
              </button>
            </div>
          </DialogPanel>
        </TransitionChild>
      </div>
    </Dialog>
  </TransitionRoot>
</template>
```

- [ ] **Step 3: 创建 StatusBadge、LoadingSpinner、EmptyState**

```vue
<!-- web/src/components/StatusBadge.vue -->
<script setup>
defineProps({
  status: { type: String, required: true },
})

const colorMap = {
  active: 'bg-green-100 text-green-800',
  online: 'bg-green-100 text-green-800',
  offline: 'bg-gray-100 text-gray-800',
  pending: 'bg-yellow-100 text-yellow-800',
  running: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-800',
  risk_controlled: 'bg-red-100 text-red-800',
  disabled: 'bg-gray-100 text-gray-800',
}

const labelMap = {
  active: '正常',
  online: '在线',
  offline: '离线',
  pending: '待执行',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
  risk_controlled: '风控中',
  disabled: '已禁用',
}
</script>

<template>
  <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
    :class="colorMap[status] || 'bg-gray-100 text-gray-800'">
    {{ labelMap[status] || status }}
  </span>
</template>
```

```vue
<!-- web/src/components/LoadingSpinner.vue -->
<template>
  <div class="flex items-center justify-center">
    <svg class="animate-spin h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24">
      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  </div>
</template>
```

```vue
<!-- web/src/components/EmptyState.vue -->
<script setup>
defineProps({
  message: { type: String, default: '暂无数据' },
})
</script>

<template>
  <div class="text-center py-12">
    <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
        d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
    </svg>
    <p class="mt-2 text-sm text-gray-500">{{ message }}</p>
  </div>
</template>
```

- [ ] **Step 4: Commit**

```bash
git add web/src/components/
git commit -m "feat: add reusable components (DataTable, ConfirmDialog, StatusBadge, LoadingSpinner, EmptyState)"
```

---

## Task 5: Dashboard 仪表盘

**Files:**
- Create: `web/src/api/stats.js`
- Modify: `web/src/views/DashboardPage.vue`

- [ ] **Step 1: 创建统计 API**

```js
// web/src/api/stats.js
import client from './client.js'

export function getDashboard() {
  return client.get('/stats/dashboard')
}

export function getDailyStats(date) {
  return client.get('/stats/daily', { params: { date } })
}

export function getAccountStats(accountId) {
  return client.get(`/stats/accounts/${accountId}`)
}

export function getRealtimeStats() {
  return client.get('/stats/realtime')
}
```

- [ ] **Step 2: 实现仪表盘页面**

```vue
<!-- web/src/views/DashboardPage.vue -->
<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { getDashboard, getRealtimeStats } from '../api/stats.js'
import StatusBadge from '../components/StatusBadge.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'

const loading = ref(true)
const dashboard = ref(null)
const realtime = ref(null)
let timer = null

async function fetchData() {
  try {
    const [dashRes, rtRes] = await Promise.all([
      getDashboard(),
      getRealtimeStats(),
    ])
    dashboard.value = dashRes.data
    realtime.value = rtRes.data
  } catch (e) {
    console.error('Failed to fetch dashboard data:', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
  timer = setInterval(fetchData, 10000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold mb-6">仪表盘</h1>

    <LoadingSpinner v-if="loading" />

    <template v-else-if="dashboard">
      <!-- Summary cards -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <!-- Accounts card -->
        <div class="bg-white rounded-lg shadow p-6">
          <h3 class="text-sm font-medium text-gray-500">账号</h3>
          <p class="text-3xl font-bold mt-2">{{ dashboard.accounts.total }}</p>
          <div class="mt-2 flex gap-4 text-sm">
            <span class="text-green-600">正常 {{ dashboard.accounts.active }}</span>
            <span class="text-red-600">风控 {{ dashboard.accounts.risk_controlled }}</span>
          </div>
        </div>

        <!-- Devices card -->
        <div class="bg-white rounded-lg shadow p-6">
          <h3 class="text-sm font-medium text-gray-500">设备</h3>
          <p class="text-3xl font-bold mt-2">{{ dashboard.devices.total }}</p>
          <p class="mt-2 text-sm text-green-600">在线 {{ realtime?.online_devices ?? dashboard.devices.online }}</p>
        </div>

        <!-- Tasks card -->
        <div class="bg-white rounded-lg shadow p-6">
          <h3 class="text-sm font-medium text-gray-500">任务</h3>
          <p class="text-3xl font-bold mt-2">{{ dashboard.tasks.total }}</p>
          <div class="mt-2 flex gap-3 text-sm">
            <span class="text-yellow-600">待执行 {{ realtime?.pending_tasks ?? dashboard.tasks.pending }}</span>
            <span class="text-blue-600">运行中 {{ realtime?.running_tasks ?? dashboard.tasks.running }}</span>
            <span class="text-green-600">完成 {{ dashboard.tasks.completed }}</span>
            <span class="text-red-600">失败 {{ dashboard.tasks.failed }}</span>
          </div>
        </div>
      </div>

      <!-- Quick actions -->
      <div class="bg-white rounded-lg shadow p-6">
        <h3 class="text-lg font-medium mb-4">快速操作</h3>
        <div class="flex gap-4">
          <router-link to="/tasks" class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
            创建任务
          </router-link>
          <router-link to="/accounts" class="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50">
            管理账号
          </router-link>
          <router-link to="/devices" class="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50">
            管理设备
          </router-link>
        </div>
      </div>
    </template>
  </div>
</template>
```

- [ ] **Step 3: 验证仪表盘**

登录后应看到账号/设备/任务统计卡片，数据每 10 秒自动刷新。

- [ ] **Step 4: Commit**

```bash
git add web/src/api/stats.js web/src/views/DashboardPage.vue
git commit -m "feat: add dashboard page with summary cards and realtime refresh"
```

---

## Task 6: 账号管理页面

**Files:**
- Create: `web/src/api/accounts.js`
- Modify: `web/src/views/AccountsPage.vue`

- [ ] **Step 1: 创建账号 API**

```js
// web/src/api/accounts.js
import client from './client.js'

export function listAccounts(params = {}) {
  return client.get('/accounts', { params })
}

export function getAccount(id) {
  return client.get(`/accounts/${id}`)
}

export function createAccount(data) {
  return client.post('/accounts', data)
}

export function updateAccount(id, data) {
  return client.put(`/accounts/${id}`, data)
}

export function deleteAccount(id) {
  return client.delete(`/accounts/${id}`)
}
```

- [ ] **Step 2: 实现账号管理页面**

```vue
<!-- web/src/views/AccountsPage.vue -->
<script setup>
import { ref, onMounted } from 'vue'
import { listAccounts, createAccount, updateAccount, deleteAccount } from '../api/accounts.js'
import DataTable from '../components/DataTable.vue'
import StatusBadge from '../components/StatusBadge.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { Dialog, DialogPanel, DialogTitle, TransitionRoot, TransitionChild } from '@headlessui/vue'

const accounts = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(true)

// Form state
const showForm = ref(false)
const editingId = ref(null)
const form = ref({ nickname: '', douyin_id: '', group: 'default', status: 'active' })

// Delete confirm
const showDeleteConfirm = ref(false)
const deletingId = ref(null)

const columns = [
  { key: 'nickname', label: '昵称' },
  { key: 'douyin_id', label: '抖音号' },
  { key: 'group', label: '分组' },
  { key: 'status', label: '状态' },
  { key: 'created_at', label: '创建时间' },
  { key: 'actions', label: '操作' },
]

async function fetchData() {
  loading.value = true
  try {
    const { data } = await listAccounts({ skip: (page.value - 1) * 20, limit: 20 })
    accounts.value = data.accounts
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.value = { nickname: '', douyin_id: '', group: 'default', status: 'active' }
  showForm.value = true
}

function openEdit(acc) {
  editingId.value = acc.id
  form.value = { nickname: acc.nickname, douyin_id: acc.douyin_id, group: acc.group, status: acc.status }
  showForm.value = true
}

async function handleSubmit() {
  if (editingId.value) {
    await updateAccount(editingId.value, form.value)
  } else {
    await createAccount(form.value)
  }
  showForm.value = false
  fetchData()
}

function confirmDelete(id) {
  deletingId.value = id
  showDeleteConfirm.value = true
}

async function handleDelete() {
  await deleteAccount(deletingId.value)
  showDeleteConfirm.value = false
  fetchData()
}

onMounted(fetchData)
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold">账号管理</h1>
      <button @click="openCreate" class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
        + 添加账号
      </button>
    </div>

    <DataTable :columns="columns" :data="accounts" :loading="loading" :total="total" :page="page"
      @page-change="(p) => { page = p; fetchData() }">
      <template #status="{ value }">
        <StatusBadge :status="value" />
      </template>
      <template #created_at="{ value }">
        <span class="text-gray-500">{{ value?.split('T')[0] ?? value }}</span>
      </template>
      <template #actions="{ row }">
        <div class="flex gap-2">
          <button @click="openEdit(row)" class="text-blue-600 hover:text-blue-800 text-sm">编辑</button>
          <button @click="confirmDelete(row.id)" class="text-red-600 hover:text-red-800 text-sm">删除</button>
        </div>
      </template>
    </DataTable>

    <!-- Create/Edit Dialog -->
    <TransitionRoot :show="showForm" as="template">
      <Dialog @close="showForm = false" class="relative z-50">
        <div class="fixed inset-0 bg-black/30" />
        <div class="fixed inset-0 flex items-center justify-center p-4">
          <DialogPanel class="w-full max-w-md bg-white rounded-lg p-6 shadow-xl">
            <DialogTitle class="text-lg font-medium">{{ editingId ? '编辑账号' : '添加账号' }}</DialogTitle>
            <form @submit.prevent="handleSubmit" class="mt-4 space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">昵称</label>
                <input v-model="form.nickname" required
                  class="w-full border rounded-md px-3 py-2" />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">抖音号</label>
                <input v-model="form.douyin_id" class="w-full border rounded-md px-3 py-2" />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">分组</label>
                <input v-model="form.group" class="w-full border rounded-md px-3 py-2" />
              </div>
              <div class="flex justify-end gap-3 mt-6">
                <button type="button" @click="showForm = false"
                  class="px-4 py-2 border rounded-md">取消</button>
                <button type="submit"
                  class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">保存</button>
              </div>
            </form>
          </DialogPanel>
        </div>
      </Dialog>
    </TransitionRoot>

    <ConfirmDialog :open="showDeleteConfirm" title="删除账号" message="确定要删除此账号吗？此操作不可撤销。"
      danger confirm-text="删除" @confirm="handleDelete" @cancel="showDeleteConfirm = false" />
  </div>
</template>
```

- [ ] **Step 3: 验证账号管理**

可查看账号列表、创建新账号、编辑账号信息、删除账号。

- [ ] **Step 4: Commit**

```bash
git add web/src/api/accounts.js web/src/views/AccountsPage.vue
git commit -m "feat: add accounts management page with CRUD operations"
```

---

## Task 7: 设备管理页面

**Files:**
- Create: `web/src/api/devices.js`
- Modify: `web/src/views/DevicesPage.vue`

- [ ] **Step 1: 创建设备 API**

```js
// web/src/api/devices.js
import client from './client.js'

export function listDevices(params = {}) {
  return client.get('/devices', { params })
}

export function getDevice(id) {
  return client.get(`/devices/${id}`)
}

export function createDevice(data) {
  return client.post('/devices', data)
}

export function updateDevice(id, data) {
  return client.put(`/devices/${id}`, data)
}

export function deleteDevice(id) {
  return client.delete(`/devices/${id}`)
}
```

- [ ] **Step 2: 实现设备管理页面**

```vue
<!-- web/src/views/DevicesPage.vue -->
<script setup>
import { ref, onMounted } from 'vue'
import { listDevices, createDevice, updateDevice, deleteDevice } from '../api/devices.js'
import DataTable from '../components/DataTable.vue'
import StatusBadge from '../components/StatusBadge.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { Dialog, DialogPanel, DialogTitle, TransitionRoot } from '@headlessui/vue'

const devices = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(true)

const showForm = ref(false)
const editingId = ref(null)
const form = ref({ name: '', ip: '', bound_account_id: '' })

const showDeleteConfirm = ref(false)
const deletingId = ref(null)

const columns = [
  { key: 'name', label: '名称' },
  { key: 'ip', label: 'IP 地址' },
  { key: 'status', label: '状态' },
  { key: 'bound_account_id', label: '绑定账号' },
  { key: 'last_seen_at', label: '最后在线' },
  { key: 'actions', label: '操作' },
]

async function fetchData() {
  loading.value = true
  try {
    const { data } = await listDevices({ skip: (page.value - 1) * 20, limit: 20 })
    devices.value = data.devices
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.value = { name: '', ip: '', bound_account_id: '' }
  showForm.value = true
}

function openEdit(dev) {
  editingId.value = dev.id
  form.value = { name: dev.name, ip: dev.ip, bound_account_id: dev.bound_account_id || '' }
  showForm.value = true
}

async function handleSubmit() {
  if (editingId.value) {
    await updateDevice(editingId.value, form.value)
  } else {
    await createDevice(form.value)
  }
  showForm.value = false
  fetchData()
}

function confirmDelete(id) {
  deletingId.value = id
  showDeleteConfirm.value = true
}

async function handleDelete() {
  await deleteDevice(deletingId.value)
  showDeleteConfirm.value = false
  fetchData()
}

onMounted(fetchData)
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold">设备管理</h1>
      <button @click="openCreate" class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
        + 添加设备
      </button>
    </div>

    <DataTable :columns="columns" :data="devices" :loading="loading" :total="total" :page="page"
      @page-change="(p) => { page = p; fetchData() }">
      <template #status="{ value }">
        <StatusBadge :status="value" />
      </template>
      <template #last_seen_at="{ value }">
        <span class="text-gray-500">{{ value ? value.split('.')[0] : '-' }}</span>
      </template>
      <template #actions="{ row }">
        <div class="flex gap-2">
          <button @click="openEdit(row)" class="text-blue-600 hover:text-blue-800 text-sm">编辑</button>
          <button @click="confirmDelete(row.id)" class="text-red-600 hover:text-red-800 text-sm">删除</button>
        </div>
      </template>
    </DataTable>

    <!-- Create/Edit Dialog -->
    <TransitionRoot :show="showForm" as="template">
      <Dialog @close="showForm = false" class="relative z-50">
        <div class="fixed inset-0 bg-black/30" />
        <div class="fixed inset-0 flex items-center justify-center p-4">
          <DialogPanel class="w-full max-w-md bg-white rounded-lg p-6 shadow-xl">
            <DialogTitle class="text-lg font-medium">{{ editingId ? '编辑设备' : '添加设备' }}</DialogTitle>
            <form @submit.prevent="handleSubmit" class="mt-4 space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">设备名称</label>
                <input v-model="form.name" required class="w-full border rounded-md px-3 py-2" />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">IP 地址</label>
                <input v-model="form.ip" class="w-full border rounded-md px-3 py-2" />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">绑定账号 ID</label>
                <input v-model="form.bound_account_id" class="w-full border rounded-md px-3 py-2" />
              </div>
              <div class="flex justify-end gap-3 mt-6">
                <button type="button" @click="showForm = false" class="px-4 py-2 border rounded-md">取消</button>
                <button type="submit" class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">保存</button>
              </div>
            </form>
          </DialogPanel>
        </div>
      </Dialog>
    </TransitionRoot>

    <ConfirmDialog :open="showDeleteConfirm" title="删除设备" message="确定要删除此设备吗？" danger
      confirm-text="删除" @confirm="handleDelete" @cancel="showDeleteConfirm = false" />
  </div>
</template>
```

- [ ] **Step 3: Commit**

```bash
git add web/src/api/devices.js web/src/views/DevicesPage.vue
git commit -m "feat: add devices management page with CRUD operations"
```

---

## Task 8: 任务中心页面

**Files:**
- Create: `web/src/api/tasks.js`
- Modify: `web/src/views/TasksPage.vue`

- [ ] **Step 1: 创建任务 API**

```js
// web/src/api/tasks.js
import client from './client.js'

export function listTasks(params = {}) {
  return client.get('/tasks', { params })
}

export function getTask(id) {
  return client.get(`/tasks/${id}`)
}

export function createTask(data) {
  return client.post('/tasks', data)
}

export function cancelTask(id) {
  return client.post(`/tasks/${id}/cancel`)
}
```

- [ ] **Step 2: 实现任务中心页面**

```vue
<!-- web/src/views/TasksPage.vue -->
<script setup>
import { ref, onMounted } from 'vue'
import { listTasks, createTask, cancelTask } from '../api/tasks.js'
import { listAccounts } from '../api/accounts.js'
import DataTable from '../components/DataTable.vue'
import StatusBadge from '../components/StatusBadge.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { Dialog, DialogPanel, DialogTitle, TransitionRoot, Listbox, ListboxButton, ListboxOptions, ListboxOption } from '@headlessui/vue'

const tasks = ref([])
const accounts = ref([])
const total = ref(0)
const page = ref(1)
const statusFilter = ref('')
const loading = ref(true)

const showForm = ref(false)
const form = ref({ type: 'nurture', account_id: '', params: '{}' })

const showCancelConfirm = ref(false)
const cancellingId = ref(null)

const taskTypes = [
  { value: 'nurture', label: '养号' },
  { value: 'search_comment', label: '搜索评论' },
  { value: 'search_like', label: '搜索点赞' },
  { value: 'search_dm', label: '搜索私信' },
  { value: 'reply_comment', label: '评论回复' },
]

const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 'pending', label: '待执行' },
  { value: 'running', label: '运行中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
  { value: 'cancelled', label: '已取消' },
]

const columns = [
  { key: 'type', label: '类型' },
  { key: 'account_id', label: '账号' },
  { key: 'status', label: '状态' },
  { key: 'created_at', label: '创建时间' },
  { key: 'actions', label: '操作' },
]

const typeLabelMap = {
  nurture: '养号',
  search_comment: '搜索评论',
  search_like: '搜索点赞',
  search_dm: '搜索私信',
  reply_comment: '评论回复',
}

async function fetchData() {
  loading.value = true
  try {
    const params = { skip: (page.value - 1) * 20, limit: 20 }
    if (statusFilter.value) params.status = statusFilter.value
    const { data } = await listTasks(params)
    tasks.value = data.tasks
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function fetchAccounts() {
  const { data } = await listAccounts({ limit: 100 })
  accounts.value = data.accounts
}

function openCreate() {
  form.value = { type: 'nurture', account_id: accounts.value[0]?.id || '', params: '{}' }
  showForm.value = true
}

async function handleSubmit() {
  const params = JSON.parse(form.value.params)
  await createTask({ type: form.value.type, account_id: form.value.account_id, params })
  showForm.value = false
  fetchData()
}

function confirmCancel(id) {
  cancellingId.value = id
  showCancelConfirm.value = true
}

async function handleCancel() {
  await cancelTask(cancellingId.value)
  showCancelConfirm.value = false
  fetchData()
}

onMounted(() => {
  fetchData()
  fetchAccounts()
})
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold">任务中心</h1>
      <div class="flex gap-3">
        <select v-model="statusFilter" @change="page = 1; fetchData()"
          class="border rounded-md px-3 py-2 text-sm">
          <option v-for="opt in statusOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
        <button @click="openCreate" class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
          + 创建任务
        </button>
      </div>
    </div>

    <DataTable :columns="columns" :data="tasks" :loading="loading" :total="total" :page="page"
      @page-change="(p) => { page = p; fetchData() }">
      <template #type="{ value }">
        <span class="font-medium">{{ typeLabelMap[value] || value }}</span>
      </template>
      <template #status="{ value }">
        <StatusBadge :status="value" />
      </template>
      <template #created_at="{ value }">
        <span class="text-gray-500">{{ value?.split('.')[0] ?? value }}</span>
      </template>
      <template #actions="{ row }">
        <button v-if="row.status === 'pending' || row.status === 'running'"
          @click="confirmCancel(row.id)" class="text-red-600 hover:text-red-800 text-sm">
          取消
        </button>
      </template>
    </DataTable>

    <!-- Create Dialog -->
    <TransitionRoot :show="showForm" as="template">
      <Dialog @close="showForm = false" class="relative z-50">
        <div class="fixed inset-0 bg-black/30" />
        <div class="fixed inset-0 flex items-center justify-center p-4">
          <DialogPanel class="w-full max-w-md bg-white rounded-lg p-6 shadow-xl">
            <DialogTitle class="text-lg font-medium">创建任务</DialogTitle>
            <form @submit.prevent="handleSubmit" class="mt-4 space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">任务类型</label>
                <select v-model="form.type" class="w-full border rounded-md px-3 py-2">
                  <option v-for="t in taskTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">执行账号</label>
                <select v-model="form.account_id" required class="w-full border rounded-md px-3 py-2">
                  <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
                    {{ acc.nickname }} ({{ acc.douyin_id }})
                  </option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">任务参数 (JSON)</label>
                <textarea v-model="form.params" rows="4"
                  class="w-full border rounded-md px-3 py-2 font-mono text-sm"></textarea>
              </div>
              <div class="flex justify-end gap-3 mt-6">
                <button type="button" @click="showForm = false" class="px-4 py-2 border rounded-md">取消</button>
                <button type="submit" class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">创建</button>
              </div>
            </form>
          </DialogPanel>
        </div>
      </Dialog>
    </TransitionRoot>

    <ConfirmDialog :open="showCancelConfirm" title="取消任务" message="确定要取消此任务吗？" danger
      confirm-text="取消任务" @confirm="handleCancel" @cancel="showCancelConfirm = false" />
  </div>
</template>
```

- [ ] **Step 3: Commit**

```bash
git add web/src/api/tasks.js web/src/views/TasksPage.vue
git commit -m "feat: add tasks page with create, filter, and cancel"
```

---

## Task 9: 选择器管理页面

**Files:**
- Create: `web/src/api/selectors.js`
- Modify: `web/src/views/SelectorsPage.vue`

- [ ] **Step 1: 创建选择器 API**

```js
// web/src/api/selectors.js
import client from './client.js'

export function listSelectors(includeDisabled = false) {
  return client.get('/selectors', { params: { include_disabled: includeDisabled } })
}

export function getSelector(actionName) {
  return client.get(`/selectors/${actionName}`)
}

export function createSelector(data) {
  return client.post('/selectors', data)
}

export function updateSelector(actionName, data) {
  return client.put(`/selectors/${actionName}`, data)
}

export function deleteSelector(actionName) {
  return client.delete(`/selectors/${actionName}`)
}

export function toggleSelector(actionName, enabled) {
  return client.patch(`/selectors/${actionName}/toggle`, { enabled })
}
```

- [ ] **Step 2: 实现选择器管理页面**

```vue
<!-- web/src/views/SelectorsPage.vue -->
<script setup>
import { ref, onMounted } from 'vue'
import { listSelectors, createSelector, updateSelector, deleteSelector, toggleSelector } from '../api/selectors.js'
import StatusBadge from '../components/StatusBadge.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import EmptyState from '../components/EmptyState.vue'
import { Dialog, DialogPanel, DialogTitle, TransitionRoot, Switch } from '@headlessui/vue'

const selectors = ref([])
const loading = ref(true)
const includeDisabled = ref(false)

const showForm = ref(false)
const editingName = ref(null)
const form = ref({ action_name: '', strategies: '[]', platform_version: 'default' })

const showDeleteConfirm = ref(false)
const deletingName = ref('')

async function fetchData() {
  loading.value = true
  try {
    const { data } = await listSelectors(includeDisabled.value)
    selectors.value = data.selectors
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingName.value = null
  form.value = { action_name: '', strategies: '[]', platform_version: 'default' }
  showForm.value = true
}

function openEdit(sel) {
  editingName.value = sel.action_name
  form.value = {
    action_name: sel.action_name,
    strategies: JSON.stringify(sel.strategies, null, 2),
    platform_version: sel.platform_version || 'default',
  }
  showForm.value = true
}

async function handleSubmit() {
  const strategies = JSON.parse(form.value.strategies)
  if (editingName.value) {
    await updateSelector(editingName.value, { strategies, platform_version: form.value.platform_version })
  } else {
    await createSelector({
      action_name: form.value.action_name,
      strategies,
      platform_version: form.value.platform_version,
    })
  }
  showForm.value = false
  fetchData()
}

async function handleToggle(sel) {
  await toggleSelector(sel.action_name, !sel.enabled)
  fetchData()
}

function confirmDelete(name) {
  deletingName.value = name
  showDeleteConfirm.value = true
}

async function handleDelete() {
  await deleteSelector(deletingName.value)
  showDeleteConfirm.value = false
  fetchData()
}

onMounted(fetchData)
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold">选择器管理</h1>
      <div class="flex gap-3 items-center">
        <label class="flex items-center gap-2 text-sm">
          <input type="checkbox" v-model="includeDisabled" @change="fetchData" class="rounded" />
          显示已禁用
        </label>
        <button @click="openCreate" class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
          + 添加选择器
        </button>
      </div>
    </div>

    <LoadingSpinner v-if="loading" />
    <EmptyState v-else-if="selectors.length === 0" message="暂无选择器配置" />

    <div v-else class="space-y-3">
      <div v-for="sel in selectors" :key="sel.action_name"
        class="bg-white rounded-lg shadow p-4 flex items-center justify-between"
        :class="{ 'opacity-50': !sel.enabled }">
        <div class="flex-1">
          <div class="flex items-center gap-3">
            <span class="font-mono font-medium text-lg">{{ sel.action_name }}</span>
            <span class="text-xs text-gray-400">v{{ sel.version }}</span>
            <span class="text-xs text-gray-400">{{ sel.platform_version }}</span>
          </div>
          <div class="mt-1 text-sm text-gray-500">
            {{ sel.strategies.length }} 个策略:
            <span v-for="(s, i) in sel.strategies" :key="i" class="inline-block ml-1">
              <code class="bg-gray-100 px-1 rounded text-xs">{{ s.type }}:{{ s.value || s.x_percent + ',' + s.y_percent }}</code>
            </span>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <Switch :modelValue="sel.enabled" @update:modelValue="handleToggle(sel)"
            :class="[sel.enabled ? 'bg-blue-600' : 'bg-gray-200', 'relative inline-flex h-6 w-11 items-center rounded-full transition-colors']">
            <span :class="[sel.enabled ? 'translate-x-6' : 'translate-x-1', 'inline-block h-4 w-4 transform rounded-full bg-white transition-transform']" />
          </Switch>
          <button @click="openEdit(sel)" class="text-blue-600 hover:text-blue-800 text-sm">编辑</button>
          <button @click="confirmDelete(sel.action_name)" class="text-red-600 hover:text-red-800 text-sm">删除</button>
        </div>
      </div>
    </div>

    <!-- Create/Edit Dialog -->
    <TransitionRoot :show="showForm" as="template">
      <Dialog @close="showForm = false" class="relative z-50">
        <div class="fixed inset-0 bg-black/30" />
        <div class="fixed inset-0 flex items-center justify-center p-4">
          <DialogPanel class="w-full max-w-lg bg-white rounded-lg p-6 shadow-xl">
            <DialogTitle class="text-lg font-medium">{{ editingName ? '编辑选择器' : '添加选择器' }}</DialogTitle>
            <form @submit.prevent="handleSubmit" class="mt-4 space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Action Name</label>
                <input v-model="form.action_name" :disabled="!!editingName" required
                  class="w-full border rounded-md px-3 py-2 font-mono" placeholder="like_button" />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Platform Version</label>
                <input v-model="form.platform_version" class="w-full border rounded-md px-3 py-2" />
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Strategies (JSON)</label>
                <textarea v-model="form.strategies" rows="8"
                  class="w-full border rounded-md px-3 py-2 font-mono text-sm"></textarea>
                <p class="text-xs text-gray-400 mt-1">
                  格式: [{"type":"text","value":"赞","priority":1}, ...]
                </p>
              </div>
              <div class="flex justify-end gap-3 mt-6">
                <button type="button" @click="showForm = false" class="px-4 py-2 border rounded-md">取消</button>
                <button type="submit" class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">保存</button>
              </div>
            </form>
          </DialogPanel>
        </div>
      </Dialog>
    </TransitionRoot>

    <ConfirmDialog :open="showDeleteConfirm" title="删除选择器"
      :message="`确定要删除选择器 '${deletingName}' 吗？`" danger
      confirm-text="删除" @confirm="handleDelete" @cancel="showDeleteConfirm = false" />
  </div>
</template>
```

- [ ] **Step 3: Commit**

```bash
git add web/src/api/selectors.js web/src/views/SelectorsPage.vue
git commit -m "feat: add selectors management page with CRUD and toggle"
```

---

## Task 10: 数据统计页面

**Files:**
- Modify: `web/src/views/StatsPage.vue`

- [ ] **Step 1: 实现数据统计页面**

```vue
<!-- web/src/views/StatsPage.vue -->
<script setup>
import { ref, onMounted, computed } from 'vue'
import { getDailyStats } from '../api/stats.js'
import { Chart, registerables } from 'chart.js'
import { nextTick, watch } from 'vue'

Chart.register(...registerables)

const stats = ref(null)
const date = ref(new Date().toISOString().split('T')[0])
const loading = ref(true)
const chartRef = ref(null)
let chartInstance = null

async function fetchData() {
  loading.value = true
  try {
    const { data } = await getDailyStats(date.value)
    stats.value = data
    await nextTick()
    renderChart()
  } finally {
    loading.value = false
  }
}

function renderChart() {
  if (chartInstance) chartInstance.destroy()
  if (!chartRef.value || !stats.value?.accounts?.length) return

  const labels = stats.value.accounts.map(a => a.nickname)
  chartInstance = new Chart(chartRef.value, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: '点赞', data: stats.value.accounts.map(a => a.likes), backgroundColor: '#3b82f6' },
        { label: '评论', data: stats.value.accounts.map(a => a.comments), backgroundColor: '#10b981' },
        { label: '关注', data: stats.value.accounts.map(a => a.follows), backgroundColor: '#f59e0b' },
        { label: '私信', data: stats.value.accounts.map(a => a.dms), backgroundColor: '#ef4444' },
      ],
    },
    options: {
      responsive: true,
      scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } },
    },
  })
}

const totals = computed(() => {
  if (!stats.value?.accounts?.length) return null
  const accs = stats.value.accounts
  return {
    likes: accs.reduce((s, a) => s + a.likes, 0),
    comments: accs.reduce((s, a) => s + a.comments, 0),
    follows: accs.reduce((s, a) => s + a.follows, 0),
    dms: accs.reduce((s, a) => s + a.dms, 0),
    replies: accs.reduce((s, a) => s + a.replies, 0),
  }
})

onMounted(fetchData)
</script>

<template>
  <div>
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold">数据统计</h1>
      <div class="flex items-center gap-3">
        <input type="date" v-model="date" @change="fetchData"
          class="border rounded-md px-3 py-2 text-sm" />
      </div>
    </div>

    <!-- Summary cards -->
    <div v-if="totals" class="grid grid-cols-5 gap-4 mb-8">
      <div class="bg-white rounded-lg shadow p-4 text-center">
        <p class="text-2xl font-bold text-blue-600">{{ totals.likes }}</p>
        <p class="text-sm text-gray-500">点赞</p>
      </div>
      <div class="bg-white rounded-lg shadow p-4 text-center">
        <p class="text-2xl font-bold text-green-600">{{ totals.comments }}</p>
        <p class="text-sm text-gray-500">评论</p>
      </div>
      <div class="bg-white rounded-lg shadow p-4 text-center">
        <p class="text-2xl font-bold text-yellow-600">{{ totals.follows }}</p>
        <p class="text-sm text-gray-500">关注</p>
      </div>
      <div class="bg-white rounded-lg shadow p-4 text-center">
        <p class="text-2xl font-bold text-red-600">{{ totals.dms }}</p>
        <p class="text-sm text-gray-500">私信</p>
      </div>
      <div class="bg-white rounded-lg shadow p-4 text-center">
        <p class="text-2xl font-bold text-purple-600">{{ totals.replies }}</p>
        <p class="text-sm text-gray-500">回复</p>
      </div>
    </div>

    <!-- Chart -->
    <div class="bg-white rounded-lg shadow p-6">
      <h3 class="text-lg font-medium mb-4">{{ date }} 各账号操作统计</h3>
      <div v-if="loading" class="flex justify-center py-12">
        <LoadingSpinner />
      </div>
      <div v-else-if="!stats?.accounts?.length" class="text-center py-12 text-gray-500">
        暂无数据
      </div>
      <canvas v-else ref="chartRef" class="max-h-96"></canvas>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Commit**

```bash
git add web/src/views/StatsPage.vue
git commit -m "feat: add stats page with daily chart and summary cards"
```

---

## Task 11: 最终集成验证

- [ ] **Step 1: 启动后端和前端**

```bash
# 终端 1: 启动后端
cd d:/devWorkspace/jsProjects/dy_auto/server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2: 启动前端
cd d:/devWorkspace/jsProjects/dy_auto/web
npm run dev
```

- [ ] **Step 2: 验证所有页面**

1. 访问 http://localhost:3000 → 重定向到登录页
2. 输入 admin/admin123 → 登录成功，跳转仪表盘
3. 仪表盘：显示账号/设备/任务统计卡片
4. 账号管理：创建、编辑、删除账号
5. 设备管理：创建、编辑、删除设备
6. 任务中心：创建任务、按状态筛选、取消任务
7. 选择器管理：查看、创建、编辑、删除、启用/禁用选择器
8. 数据统计：查看当日统计图表

- [ ] **Step 3: 最终 Commit**

```bash
git add web/
git commit -m "feat: complete Vue admin dashboard with all 6 pages"
```

---

## 任务依赖关系

```
Task 1 (项目初始化)
  └─> Task 2 (API 客户端 + 认证 + 登录页)
       └─> Task 3 (管理后台布局)
            └─> Task 4 (通用组件)
                 ├─> Task 5 (仪表盘)
                 ├─> Task 6 (账号管理)
                 ├─> Task 7 (设备管理)
                 ├─> Task 8 (任务中心)
                 ├─> Task 9 (选择器管理)
                 └─> Task 10 (数据统计)
                      └─> Task 11 (集成验证)
```

Tasks 5-10 可以并行实现（互不依赖），但建议按顺序逐个完成以便及时验证。
