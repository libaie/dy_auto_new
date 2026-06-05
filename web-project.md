# Web — Complete Source
Total files: 104

---
## src/main.js

```javascript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import { setupAuthInterceptor, setupToastInterceptor } from './api/client.js'
import { useAuthStore } from './stores/auth.js'
import { useToastStore } from './stores/toast.js'
import './style.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

// Set up interceptors after pinia and router are ready
const authStore = useAuthStore(pinia)
setupAuthInterceptor(authStore, router)

const toastStore = useToastStore(pinia)
setupToastInterceptor(toastStore)

app.mount('#app')
```

## src/router/index.js

```javascript
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginPage.vue'),
  },
  {
    path: '/',
    component: () => import('../views/AdminLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('../views/DashboardPage.vue'),
      },
      {
        path: 'accounts',
        name: 'Accounts',
        component: () => import('../views/AccountsPage.vue'),
      },
      {
        path: 'account-groups',
        name: 'AccountGroups',
        component: () => import('../views/AccountGroupsPage.vue'),
      },
      {
        path: 'devices',
        name: 'Devices',
        component: () => import('../views/DevicesPage.vue'),
      },
      {
        path: 'tasks',
        name: 'Tasks',
        component: () => import('../views/TasksPage.vue'),
      },
      {
        path: 'chain-templates',
        name: 'ChainTemplates',
        component: () => import('../views/ChainTemplatesPage.vue'),
      },
      {
        path: 'chain-instances',
        name: 'ChainInstances',
        component: () => import('../views/ChainInstancesPage.vue'),
      },
      {
        path: 'selectors',
        name: 'Selectors',
        component: () => import('../views/SelectorsPage.vue'),
      },
      {
        path: 'channels',
        redirect: '/tasks',
      },
      {
        path: 'stats',
        name: 'Stats',
        component: () => import('../views/StatsPage.vue'),
      },
      {
        path: 'content',
        name: 'Content',
        component: () => import('../views/ContentPage.vue'),
      },
      {
        path: 'prompt-templates',
        name: 'PromptTemplates',
        component: () => import('../views/PromptTemplatesPage.vue'),
      },
      {
        path: 'data',
        name: 'DataCenter',
        component: () => import('../views/DataCenterPage.vue'),
      },
      {
        path: 'video-studio',
        name: 'VideoStudio',
        component: () => import('../views/VideoStudio.vue'),
      },
      {
        path: 'videos',
        name: 'Videos',
        component: () => import('../views/VideosPage.vue'),
      },
      {
        path: 'ai-config',
        name: 'AIConfig',
        component: () => import('../views/AIConfigPage.vue'),
      },
      {
        path: 'characters',
        name: 'Characters',
        component: () => import('../views/CharactersPage.vue'),
      },
      {
        path: 'scenes',
        name: 'Scenes',
        component: () => import('../views/ScenesPage.vue'),
      },
      {
        path: 'dict-manage',
        name: 'DictManage',
        component: () => import('../views/DictManagePage.vue'),
      },
      {
        path: 'dm-sequences',
        name: 'DMSequences',
        component: () => import('../views/DMSequenceManagePage.vue'),
      },
      {
        path: 'director/:seriesId/:episodeId',
        name: 'Director',
        component: () => import('../views/DirectorPage.vue'),
      },
      {
        path: 'series',
        name: 'SeriesList',
        component: () => import('../views/SeriesListPage.vue'),
      },
      {
        path: 'series/:id',
        name: 'SeriesDetail',
        component: () => import('../views/SeriesDetailPage.vue'),
      },
      {
        path: 'pipeline/:runId',
        name: 'PipelineMonitor',
        component: () => import('../views/PipelineMonitorPage.vue'),
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('../views/UsersPage.vue'),
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('../views/SettingsPage.vue'),
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const ADMIN_ONLY_PATHS = [
  '/accounts', '/account-groups', '/devices', '/chain-templates', '/chain-instances',
  '/selectors', '/settings', '/prompt-templates', '/ai-config', '/dict-manage',
  '/characters', '/scenes', '/series', '/director', '/pipeline', '/stats',
  '/users',
]

router.beforeEach((to, from, next) => {
  if (!router._authStore) {
    router._authStore = useAuthStore()
  }
  const authStore = router._authStore

  if (to.matched.some((record) => record.meta.requiresAuth) && !authStore.isLoggedIn) {
    next('/login')
    return
  }

  if (authStore.isLoggedIn && !authStore.isAdmin && ADMIN_ONLY_PATHS.some(p => to.path.startsWith(p))) {
    next('/')
    return
  }

  if (to.path === '/login' && authStore.isLoggedIn) {
    next('/')
    return
  }

  next()
})

export default router
```

## src/stores/auth.js

```javascript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi } from '../api/auth.js'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const username = ref(localStorage.getItem('username') || '')
  const userId = ref(localStorage.getItem('userId') || '')
  const role = ref(localStorage.getItem('role') || '')

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => role.value === 'admin')

  async function login(user, password) {
    const response = await loginApi(user, password)
    const data = response.data
    token.value = data.token
    username.value = user
    userId.value = data.user_id || ''
    role.value = data.role || 'operator'
    localStorage.setItem('token', data.token)
    localStorage.setItem('username', user)
    localStorage.setItem('userId', data.user_id || '')
    localStorage.setItem('role', data.role || 'operator')
  }

  function logout() {
    token.value = ''
    username.value = ''
    userId.value = ''
    role.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    localStorage.removeItem('userId')
    localStorage.removeItem('role')
  }

  return { token, username, userId, role, isLoggedIn, isAdmin, login, logout }
})
```

## src/stores/toast.js

```javascript
import { defineStore } from 'pinia'
import { ref } from 'vue'

let _nextId = 0

export const useToastStore = defineStore('toast', () => {
  const toasts = ref([])

  function addToast({ type = 'error', message, duration = 4000 }) {
    const id = ++_nextId
    toasts.value.push({ id, type, message })
    if (duration > 0) {
      setTimeout(() => removeToast(id), duration)
    }
  }

  function removeToast(id) {
    const idx = toasts.value.findIndex(t => t.id === id)
    if (idx !== -1) toasts.value.splice(idx, 1)
  }

  function error(message, duration) {
    addToast({ type: 'error', message, duration })
  }

  function warning(message, duration) {
    addToast({ type: 'warning', message, duration })
  }

  function success(message, duration) {
    addToast({ type: 'success', message, duration })
  }

  function info(message, duration) {
    addToast({ type: 'info', message, duration })
  }

  return { toasts, addToast, removeToast, error, warning, success, info }
})
```

## src/api/accountGroups.js

```javascript
import client from './client.js'

export function listGroups(params = {}) {
  return client.get('/account-groups', { params })
}

export function getGroup(id) {
  return client.get(`/account-groups/${id}`)
}

export function createGroup(data) {
  return client.post('/account-groups', data)
}

export function updateGroup(id, data) {
  return client.put(`/account-groups/${id}`, data)
}

export function deleteGroup(id) {
  return client.delete(`/account-groups/${id}`)
}

export function listMembers(groupId, params = {}) {
  return client.get(`/account-groups/${groupId}/members`, { params })
}

export function addMembers(groupId, accountIds) {
  return client.post(`/account-groups/${groupId}/members`, { account_ids: accountIds })
}

export function removeMembers(groupId, accountIds) {
  return client.delete(`/account-groups/${groupId}/members`, { data: { account_ids: accountIds } })
}
```

## src/api/accounts.js

```javascript
import client from './client.js'

export function listAccounts(params = {}) {
  return client.get('/accounts', { params })
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

## src/api/aiConfig.js

```javascript
import client from './client.js'

// AIModel CRUD
export function listModels(params) { return client.get('/ai-models', { params }) }
export function getModelOptions(modelType) { return client.get('/ai-models/options', { params: { model_type: modelType } }) }
export function getModel(id) { return client.get(`/ai-models/${id}`) }
export function createModel(data) { return client.post('/ai-models', data) }
export function updateModel(id, data) { return client.put(`/ai-models/${id}`, data) }
export function deleteModel(id) { return client.delete(`/ai-models/${id}`) }
export function testModelConnection(id) { return client.post(`/ai-models/${id}/test`) }
```

## src/api/auth.js

```javascript
import client from './client.js'

export function login(username, password) {
  return client.post('/auth/login', { username, password })
}

export function registerUser(data) {
  return client.post('/auth/register', data)
}

export function listUsers(params) {
  return client.get('/auth/users', { params })
}
```

## src/api/chains.js

```javascript
import client from './client.js'

// Templates
export function listTemplates(params = {}) {
  return client.get('/chains/templates', { params })
}

export function getTemplate(id) {
  return client.get(`/chains/templates/${id}`)
}

export function createTemplate(data) {
  return client.post('/chains/templates', data)
}

export function updateTemplate(id, data) {
  return client.put(`/chains/templates/${id}`, data)
}

export function deleteTemplate(id) {
  return client.delete(`/chains/templates/${id}`)
}

// Instances
export function listInstances(params = {}) {
  return client.get('/chains/instances', { params })
}

export function getInstance(id) {
  return client.get(`/chains/instances/${id}`)
}

export function createInstances(data) {
  return client.post('/chains/instances', data)
}

export function cancelInstance(id) {
  return client.post(`/chains/instances/${id}/cancel`)
}

export function retryInstance(id) {
  return client.post(`/chains/instances/${id}/retry`)
}
```

## src/api/channels.js

```javascript
import client from './client';

export function listChannels() {
  return client.get('/channels');
}

export function getChannel(id) {
  return client.get(`/channels/${id}`);
}

export function createChannel(data) {
  return client.post('/channels', data);
}

export function updateChannel(id, data) {
  return client.patch(`/channels/${id}`, data);
}

export function deleteChannel(id) {
  return client.delete(`/channels/${id}`);
}

export function appendChannelItems(id, keywords) {
  return client.post(`/channels/${id}/items`, { keywords });
}

export function updateChannelItem(channelId, itemId, data) {
  return client.patch(`/channels/${channelId}/items/${itemId}`, data);
}

export function editChannelMeta(id, data) {
  return client.put(`/channels/${id}`, data);
}

export function editChannelItem(itemId, data) {
  return client.put(`/channels/items/${itemId}`, data);
}

export function batchEditItems(data) {
  return client.put('/channels/items/batch', data);
}
```

## src/api/characters.js

```javascript
import client from './client.js'

export function listCharacters() { return client.get('/characters') }
export function createCharacter(data) { return client.post('/characters', data) }
export function updateCharacter(id, data) { return client.put(`/characters/${id}`, data) }
export function deleteCharacter(id) { return client.delete(`/characters/${id}`) }
export function autoGenerateCharacters(text, genre = 'drama', count = 4) { return client.post('/characters/auto-generate', { text, genre, count }) }
```

## src/api/client.js

```javascript
import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// Request interceptor: attach JWT token
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: handle 401 + global toast
// Handlers are set up lazily by setupAuthInterceptor() in main.js
// to avoid circular dependency with router/store
let _authHandler = null
let _toastHandler = null

client.interceptors.response.use(
  (response) => response,
  (error) => {
    // 401 → redirect to login
    if (error.response && error.response.status === 401) {
      if (_authHandler) {
        _authHandler()
      } else {
        localStorage.removeItem('token')
        localStorage.removeItem('username')
        window.location.href = '/login'
      }
      return Promise.reject(error)
    }

    // All other errors → show toast
    if (_toastHandler) {
      const data = error.response?.data
      const message = data?.detail || data?.message || (error.response ? `请求失败 (${error.response.status})` : '网络连接失败，请检查网络')
      _toastHandler(message)
    }

    return Promise.reject(error)
  }
)

/**
 * Call this after router and pinia are initialized.
 * Sets up the 401 handler to properly log out via the store and redirect via the router.
 */
export function setupAuthInterceptor(authStore, router) {
  _authHandler = () => {
    authStore.logout()
    router.push('/login')
  }
}

/**
 * Call this after pinia is initialized.
 * Sets up the global toast handler for all non-401 errors.
 */
export function setupToastInterceptor(toastStore) {
  _toastHandler = (message) => {
    toastStore.error(message)
  }
}

export default client
```

## src/api/content.js

```javascript
import client from './client.js'

// --- Templates ---
export function listTemplates(params = {}) {
  return client.get('/content/templates', { params })
}

export function getTemplate(id) {
  return client.get(`/content/templates/${id}`)
}

export function createTemplate(data) {
  return client.post('/content/templates', data)
}

export function updateTemplate(id, data) {
  return client.put(`/content/templates/${id}`, data)
}

export function deleteTemplate(id) {
  return client.delete(`/content/templates/${id}`)
}

// --- Sensitive Words ---
export function listSensitiveWords(params = {}) {
  return client.get('/content/sensitive-words', { params })
}

export function addSensitiveWord(word) {
  return client.post('/content/sensitive-words', { word })
}

export function deleteSensitiveWord(id) {
  return client.delete(`/content/sensitive-words/${id}`)
}

// --- AI Generation ---
export function generateContent(templateId, context) {
  return client.post('/content/generate', {
    template_id: templateId,
    context,
  })
}

export function generateKeywords(keyword, count = 10) {
  return client.post('/content/generate-keywords', { keyword, count })
}
```

## src/api/data.js

```javascript
import client from './client.js'

export function listComments(params = {}) {
  return client.get('/data/comments', { params })
}

export function listUsers(params = {}) {
  return client.get('/data/users', { params })
}

export function listConversations(params = {}) {
  return client.get('/data/conversations', { params })
}
```

## src/api/devices.js

```javascript
import client from './client.js'

export function listDevices(params = {}) {
  return client.get('/devices', { params })
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

export function disconnectDevice(id) {
  return client.post(`/devices/${id}/disconnect`)
}

// --- Pairing requests ---

export function listPairRequests(status = 'pending') {
  return client.get('/devices/pair-requests', { params: { status } })
}

export function approvePairRequest(requestId) {
  return client.post(`/devices/pair-requests/${requestId}/approve`)
}

export function rejectPairRequest(requestId) {
  return client.post(`/devices/pair-requests/${requestId}/reject`)
}
```

## src/api/dmSequences.js

```javascript
import client from './client.js'

export function listDMSequences(params = {}) {
  return client.get('/dm-sequences', params)
}

export function getDMSequence(id) {
  return client.get(`/dm-sequences/${id}`)
}

export function createDMSequence(data) {
  return client.post('/dm-sequences', data)
}

export function updateDMSequence(id, data) {
  return client.put(`/dm-sequences/${id}`, data)
}

export function deleteDMSequence(id) {
  return client.delete(`/dm-sequences/${id}`)
}
```

## src/api/pipeline.js

```javascript
import client from './client.js'

export function startPipeline(seriesId, episodeId, mode, modelIds, directorPlan) {
  return client.post('/pipeline/start', {
    series_id: seriesId,
    episode_id: episodeId || null,
    mode: mode || 'step_by_step',
    model_ids: modelIds || null,
    director_plan: directorPlan || null,
  })
}
export function resumePipeline(runId) { return client.post(`/pipeline/resume/${runId}`) }
export function listRuns(seriesId) { return client.get(`/pipeline/runs/${seriesId}`) }
export function getRun(seriesId, runId) { return client.get(`/pipeline/runs/${seriesId}/${runId}`) }
```

## src/api/pixelle-client.js

```javascript
/**
 * Pixelle-Video API 客户端 — 通过 dy_auto 后端透明代理转发到 Pixelle-Video 服务。
 *
 * 所有请求走 /api/pixelle-proxy/{path}，后端根据 SystemSetting 中的
 * pixelle_video_url 将请求透明转发到 Pixelle-Video 的 FastAPI 服务。
 */
import axios from 'axios'

const proxy = axios.create({
  baseURL: '/api/pixelle-proxy',
  timeout: 600000, // 视频生成可能需要 10 分钟
})

// Attach JWT Bearer token (same pattern as api/client.js)
proxy.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ==================== 视频生成 ====================

export function generateVideoAsync(payload) {
  return proxy.post('/api/video/generate/async', payload)
}

export function generateVideoSync(payload) {
  return proxy.post('/api/video/generate/sync', payload)
}

// ==================== 任务管理 ====================

export function getTask(taskId) {
  return proxy.get(`/api/tasks/${taskId}`)
}

export function listTasks() {
  return proxy.get('/api/tasks')
}

// ==================== 资源 ====================

export function listTemplates() {
  return proxy.get('/api/resources/templates')
}

export function listMediaWorkflows() {
  return proxy.get('/api/resources/workflows/media')
}

export function listTTSWorkflows() {
  return proxy.get('/api/resources/workflows/tts')
}

export function listImageWorkflows() {
  return proxy.get('/api/resources/workflows/image')
}

export function listBGMs() {
  return proxy.get('/api/resources/bgm')
}

export function renderFrame(template, text) {
  return proxy.post('/api/frame/render', { template, text })
}

export function getOpenAPISpec() {
  return proxy.get('/openapi.json')
}

// ==================== 内容生成 (AI) ====================

export function generateNarration(payload) {
  return proxy.post('/api/content/narration', payload)
}

export function generateImagePrompt(payload) {
  return proxy.post('/api/content/image-prompt', payload)
}

export function generateTitle(payload) {
  return proxy.post('/api/content/title', payload)
}

// ==================== TTS ====================

export function synthesizeTTS(payload) {
  return proxy.post('/api/tts/synthesize', payload)
}

// ==================== 图像生成 ====================

export function generateImage(payload) {
  return proxy.post('/api/image/generate', payload)
}

// ==================== 文件上传（BGM / 参考音频） ====================

export function uploadFile(formData) {
  return proxy.post('/api/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// ==================== 获取视频文件 URL ====================

export function getVideoFileUrl(videoPath) {
  // Pixelle-Video serves files at GET /api/files/{file_path}
  if (!videoPath) return ''
  const encoded = encodeURIComponent(videoPath)
  return `/api/pixelle-proxy/api/files/${encoded}`
}
```

## src/api/pixelle.js

```javascript
import client from './client.js'

export function testConnection() {
  return client.get('/pixelle/test-connection')
}

export function getPixelleConfig() {
  return client.get('/pixelle/config')
}

export function updatePixelleConfig(updates) {
  return client.put('/pixelle/config', { updates })
}
```

## src/api/promptTemplates.js

```javascript
import client from './client.js'

export function listTemplates(includeDisabled = false) {
  return client.get('/prompt-templates', { params: { include_disabled: includeDisabled } })
}

export function getTemplate(name) {
  return client.get(`/prompt-templates/${name}`)
}

export function createTemplate(data) {
  return client.post('/prompt-templates', data)
}

export function updateTemplate(name, data) {
  return client.put(`/prompt-templates/${name}`, data)
}

export function deleteTemplate(name) {
  return client.delete(`/prompt-templates/${name}`)
}

export function generateTemplate(description, industry = 'health') {
  return client.post('/prompt-templates/generate', { description, industry })
}

export function toggleTemplate(name, enabled) {
  return client.patch(`/prompt-templates/${name}/toggle`, { enabled })
}
```

## src/api/referenceData.js

```javascript
import client from './client.js'

// Category CRUD
export function listCategories() { return client.get('/reference-categories') }
export function createCategory(data) { return client.post('/reference-categories', data) }
export function updateCategory(id, data) { return client.put(`/reference-categories/${id}`, data) }
export function deleteCategory(id) { return client.delete(`/reference-categories/${id}`) }

// Item CRUD
export function listItems(category) { return client.get(`/reference-data/${category}`) }
export function listAllItems(category) { return client.get(`/reference-data/admin/${category}`) }
export function createItem(data) { return client.post('/reference-data', data) }
export function updateItem(id, data) { return client.put(`/reference-data/${id}`, data) }
export function deleteItem(id) { return client.delete(`/reference-data/${id}`) }
```

## src/api/scenes.js

```javascript
import client from './client.js'

export function listScenes() { return client.get('/scenes') }
export function createScene(data) { return client.post('/scenes', data) }
export function updateScene(id, data) { return client.put(`/scenes/${id}`, data) }
export function deleteScene(id) { return client.delete(`/scenes/${id}`) }
export function autoGenerateScenes(text, genre = 'drama', count = 5) { return client.post('/scenes/auto-generate', { text, genre, count }) }
```

## src/api/seedance-client.js

```javascript
/**
 * Seedance 2.0 API 客户端 — 通过 dy_auto 后端代理转发到火山方舟 Ark API.
 */
import axios from 'axios'

const proxy = axios.create({
  baseURL: '/api/seedance',
  timeout: 600000,
})

proxy.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/** 提交 Seedance 视频生成任务 (便捷端点) */
export function seedanceGenerate(payload) {
  return proxy.post('/generate', payload)
}

/** 查询 Seedance 任务状态 (便捷端点) */
export function seedanceGetTask(taskId) {
  return proxy.get(`/task/${taskId}`)
}
```

## src/api/selectors.js

```javascript
import client from './client.js'

export function listSelectors(includeDisabled = false, category = '') {
  return client.get('/selectors', { params: { include_disabled: includeDisabled, category: category || undefined } })
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

export function uploadTemplate(file, actionName, resolution = 'default') {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('action_name', actionName)
  return client.post('/selectors/templates/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params: { resolution: resolution || 'default' },
  })
}

export function listTemplates() {
  return client.get('/selectors/templates')
}

export function deleteTemplate(filename) {
  return client.delete(`/selectors/templates/${filename}`)
}
export function generateRegex(description) {
  return client.post('/content/generate-regex', { description })
}

export function generateCleanPrompt(description) {
  return client.post('/content/generate-clean-prompt', { description })
}
```

## src/api/series.js

```javascript
import client from './client.js'

export function listSeries(params) { return client.get('/series', { params }) }
export function createSeries(data) { return client.post('/series', data) }
export function getSeries(id) { return client.get(`/series/${id}`) }
export function deleteSeries(id) { return client.delete(`/series/${id}`) }
export function linkCharacter(seriesId, characterId) { return client.post(`/series/${seriesId}/characters/${characterId}`) }
export function linkScene(seriesId, sceneId) { return client.post(`/series/${seriesId}/scenes/${sceneId}`) }
export function updateEpisode(seriesId, episodeId, data) { return client.put(`/series/${seriesId}/episodes/${episodeId}`, data) }
export function autoGenerateAssets(seriesId) { return client.post(`/series/${seriesId}/auto-generate`) }
```

## src/api/settings.js

```javascript
import client from './client.js'

export function getSettings() {
  return client.get('/settings')
}

export function updateSettings(settings) {
  return client.put('/settings', { settings })
}
```

## src/api/stats.js

```javascript
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

## src/api/tasks.js

```javascript
import client from './client.js'

export function listTasks(params = {}) {
  return client.get('/tasks', { params })
}

export function createTask(data) {
  return client.post('/tasks', data)
}

export function batchCreateTasks(data) {
  return client.post('/tasks/batch', data)
}

export function cancelTask(id) {
  return client.post(`/tasks/${id}/cancel`)
}

export function deleteTask(id) {
  return client.delete(`/tasks/${id}`)
}

export function batchDeleteTasks(taskIds) {
  return client.post('/tasks/batch-delete', { task_ids: taskIds })
}
```

## src/api/videos.js

```javascript
import client from './client.js'

export function listVideos(params = {}) {
  return client.get('/videos', { params })
}

export function getVideo(id) {
  return client.get(`/videos/${id}`)
}

export function deleteVideo(id) {
  return client.delete(`/videos/${id}`)
}

export function getVideoDownloadUrl(id) {
  const token = localStorage.getItem('token') || ''
  return `/api/videos/${id}/download?token=${encodeURIComponent(token)}`
}
```

## src/composables/useConfirm.js

```javascript
import { ref } from 'vue'

export function useConfirm() {
  const isOpen = ref(false)
  const title = ref('')
  const message = ref('')
  const danger = ref(false)
  const confirmAction = ref(null)

  function open(opts, action) {
    title.value = opts.title || ''
    message.value = opts.message || ''
    danger.value = opts.danger || false
    confirmAction.value = action
    isOpen.value = true
  }

  async function handleConfirm() {
    if (confirmAction.value) {
      await confirmAction.value()
    }
    isOpen.value = false
  }

  function handleCancel() {
    isOpen.value = false
  }

  return { isOpen, title, message, danger, open, handleConfirm, handleCancel }
}
```

## src/composables/useDialog.js

```javascript
import { ref, reactive } from 'vue'

/**
 * @param {Object} defaultForm — default values for the form
 */
export function useDialog(defaultForm = {}) {
  const isOpen = ref(false)
  const isEditing = ref(false)
  const saving = ref(false)
  const error = ref(null)
  const editingId = ref(null)
  const form = reactive({ ...defaultForm })

  function open(data = null) {
    if (data) {
      isEditing.value = true
      editingId.value = data.id ?? null
      Object.assign(form, data)
    } else {
      isEditing.value = false
      editingId.value = null
      Object.assign(form, defaultForm)
    }
    error.value = null
    isOpen.value = true
  }

  function close() {
    isOpen.value = false
    error.value = null
    Object.assign(form, defaultForm)
  }

  function reset() {
    Object.assign(form, defaultForm)
    error.value = null
  }

  return { isOpen, isEditing, saving, error, editingId, form, open, close, reset }
}
```

## src/composables/usePagination.js

```javascript
import { ref, watch } from 'vue'

/**
 * @param {Function} fetchFn — async function that returns { data, total } from API
 * @param {Object} options
 * @param {number} [options.pageSize=10]
 * @param {Object} [options.filters] — reactive filters object (e.g. { status, type, search })
 */
export function usePagination(fetchFn, { pageSize = 10, filters = {} } = {}) {
  const data = ref([])
  const total = ref(0)
  const page = ref(1)
  const loading = ref(false)
  const error = ref(null)

  async function fetch(resetPage = false) {
    if (resetPage) page.value = 1
    loading.value = true
    error.value = null
    try {
      const skip = (page.value - 1) * pageSize
      const result = await fetchFn({ skip, limit: pageSize, page: page.value, ...filters })
      data.value = result.data ?? []
      total.value = result.total ?? 0
    } catch (e) {
      error.value = e
      data.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  function goToPage(p) {
    if (p < 1 || p > totalPages.value) return
    page.value = p
    fetch()
  }

  function reset() {
    page.value = 1
    data.value = []
    total.value = 0
    error.value = null
  }

  const totalPages = () => Math.ceil(total.value / pageSize)

  // Auto-refetch when page or filters change
  if (filters && typeof filters === 'object') {
    const filterKeys = Object.keys(filters)
    if (filterKeys.length > 0) {
      watch(
        () => filterKeys.map(k => filters[k]),
        () => fetch(true),
        { deep: true }
      )
    }
  }

  return { data, total, page, loading, error, fetch, goToPage, reset, totalPages }
}
```

## src/composables/usePolling.js

```javascript
import { onMounted, onUnmounted } from 'vue'

/**
 * @param {Function} fetchFn — async function to call on each tick
 * @param {number} [interval=10000] — polling interval in ms
 */
export function usePolling(fetchFn, interval = 10000) {
  let timer = null

  function start() {
    stop()
    timer = setInterval(fetchFn, interval)
  }

  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  function handleVisibilityChange() {
    if (document.hidden) {
      stop()
    } else {
      fetchFn()
      start()
    }
  }

  onMounted(() => {
    fetchFn()
    start()
    document.addEventListener('visibilitychange', handleVisibilityChange)
  })

  onUnmounted(() => {
    stop()
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  })

  return { start, stop }
}
```

## src/composables/useSavedPrompt.js

```javascript
import { ref, watch } from 'vue'

const STORE_PREFIX = 'ai_prompt_'

/**
 * 持久化的 AI 提示词 ref — 自动同步到 localStorage
 * @param {string} key - 唯一标识，如 'template_generator', 'selector_regex'
 * @param {string} defaultValue - 默认值
 * @returns {import('vue').Ref<string>}
 */
export function useSavedPrompt(key, defaultValue) {
  const storageKey = STORE_PREFIX + key
  let saved = defaultValue
  try {
    const raw = localStorage.getItem(storageKey)
    if (raw != null) saved = raw
  } catch (e) { /* ignore */ }

  const val = ref(saved)

  watch(val, (v) => {
    try { localStorage.setItem(storageKey, v || '') } catch (e) { /* ignore */ }
  }, { flush: 'sync' })

  return val
}
```

## src/composables/useWebSocket.js

```javascript
import { ref, onUnmounted } from 'vue'

/**
 * @param {string|Function} urlOrFn — WebSocket URL or function that returns one
 * @param {Object} options
 * @param {Function} [options.onMessage] — called with parsed JSON message
 * @param {number} [options.reconnectDelay=5000]
 */
export function useWebSocket(urlOrFn, { onMessage, reconnectDelay = 5000 } = {}) {
  const connected = ref(false)
  let ws = null
  let timer = null

  function connect() {
    const url = typeof urlOrFn === 'function' ? urlOrFn() : urlOrFn
    if (!url) return

    cleanup()

    ws = new WebSocket(url)
    ws.onopen = () => { connected.value = true }
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        onMessage?.(msg)
      } catch { /* ignore malformed messages */ }
    }
    ws.onclose = () => {
      connected.value = false
      ws = null
      timer = setTimeout(connect, reconnectDelay)
    }
    ws.onerror = () => {
      ws?.close()
    }
  }

  function send(data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }

  function disconnect() {
    cleanup()
    connected.value = false
  }

  function cleanup() {
    if (timer) { clearTimeout(timer); timer = null }
    if (ws) { ws.onclose = null; ws.close(); ws = null }
  }

  onUnmounted(cleanup)

  return { connected, connect, send, disconnect }
}
```

## src/constants/channels.js

```javascript
export const CHANNEL_TASK_TYPE_LABEL = {
  search_comment: '评论搜索',
  search_like: '点赞搜索',
  search_dm: '私信搜索',
  reply_comment: '回复评论',
  collect: '采集',
  nurture: '养号',
}

export const CHANNEL_STATUS_LABEL = {
  active: '运行中',
  paused: '已暂停',
  completed: '已完成',
  cancelled: '已取消',
}

export const CHANNEL_STATUS_CLASS = {
  active: 'bg-green-500/20 text-green-400',
  paused: 'bg-yellow-500/20 text-yellow-400',
  completed: 'bg-blue-500/20 text-blue-400',
  cancelled: 'bg-slate-600/50 text-slate-400',
}
```

## src/constants/content.js

```javascript
export const CATEGORY_LABELS = {
  comment: '评论',
  dm: '私信',
  reply: '回复',
}

export const CATEGORY_COLORS = {
  comment: 'bg-blue-100 text-blue-800',
  dm: 'bg-green-100 text-green-800',
  reply: 'bg-purple-100 text-purple-800',
}
```

## src/constants/navigation.js

```javascript
export const NAV_CATEGORIES = [
  {
    key: 'ops',
    label: '运营',
    items: [
      { name: '仪表盘', path: '/', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
      { name: '账号管理', path: '/accounts', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z' },
      { name: '账号分组', path: '/account-groups', icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z' },
      { name: '设备管理', path: '/devices', icon: 'M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z' },
    ],
  },
  {
    key: 'tasks',
    label: '任务',
    items: [
      { name: '任务中心', path: '/tasks', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01' },
      { name: '任务链模板', path: '/chain-templates', icon: 'M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z' },
      { name: '链实例', path: '/chain-instances', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
      { name: '选择器管理', path: '/selectors', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
    ],
  },
  {
    key: 'data',
    label: '数据',
    items: [
      { name: '数据中心', path: '/data', icon: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4' },
      { name: '数据统计', path: '/stats', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
    ],
  },
  {
    key: 'ai-video',
    label: 'AI 视频',
    items: [
      { name: 'AI 视频工坊', path: '/video-studio', icon: 'M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z' },
      { name: '系列管理', path: '/series', icon: 'M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10' },
      { name: '角色资产库', path: '/characters', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
      { name: '场景资产库', path: '/scenes', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
      { name: 'AI 模型配置', path: '/ai-config', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
      { name: '视频管理', path: '/videos', icon: 'M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z' },
      { name: '提示词模板', path: '/prompt-templates', icon: 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z' },
    ],
  },
  {
    key: 'system',
    label: '系统',
    items: [
      { name: '内容管理', path: '/content', icon: 'M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z' },
      { name: 'DM 序列', path: '/dm-sequences', icon: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z' },
      { name: '系统字典', path: '/dict-manage', icon: 'M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4' },
      { name: '用户管理', path: '/users', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z' },
      { name: '系统设置', path: '/settings', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
    ],
  },
]

// 静态路由精确匹配。动态路由由 getCategoryByRoute 通过 route.matched 处理。
export const ROUTE_CATEGORY_MAP = {
  '/': 'ops',
  '/accounts': 'ops',
  '/account-groups': 'ops',
  '/devices': 'ops',
  '/tasks': 'tasks',
  '/chain-templates': 'tasks',
  '/chain-instances': 'tasks',
  '/selectors': 'tasks',
  '/data': 'data',
  '/stats': 'data',
  '/video-studio': 'ai-video',
  '/series': 'ai-video',
  '/characters': 'ai-video',
  '/scenes': 'ai-video',
  '/ai-config': 'ai-video',
  '/videos': 'ai-video',
  '/prompt-templates': 'ai-video',
  '/series/:id': 'ai-video',
  '/director/:seriesId/:episodeId': 'ai-video',
  '/pipeline/:runId': 'ai-video',
  '/content': 'system',
  '/dict-manage': 'system',
  '/users': 'system',
  '/settings': 'system',
}

export function getCategoryByRoute(route) {
  // 1. exact path match
  if (ROUTE_CATEGORY_MAP[route.path] != null) {
    return ROUTE_CATEGORY_MAP[route.path]
  }
  // 2. route definition pattern match (dynamic routes like /series/:id)
  // Vue Router matched[] is parent→child ordered; use deepest (last) match
  if (route.matched?.length) {
    const pattern = route.matched[route.matched.length - 1].path
    if (ROUTE_CATEGORY_MAP[pattern] != null) {
      return ROUTE_CATEGORY_MAP[pattern]
    }
  }
  // 3. fallback
  return 'ops'
}
```

## src/constants/tasks.js

```javascript
export const TASK_TYPE_LABEL_MAP = {
  nurture: '养号',
  search_comment: '搜索评论',
  search_like: '搜索点赞',
  search_dm: '搜索私信',
  reply_comment: '评论回复',
  collect: '数据采集',
}

export const TASK_TYPE_OPTIONS = [
  { value: 'nurture', label: '养号' },
  { value: 'search_comment', label: '搜索评论' },
  { value: 'search_like', label: '搜索点赞' },
  { value: 'search_dm', label: '搜索私信' },
  { value: 'reply_comment', label: '评论回复' },
  { value: 'collect', label: '数据采集' },
]

export const STATUS_FILTER_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'pending', label: '待执行' },
  { value: 'running', label: '运行中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
  { value: 'cancelled', label: '已取消' },
]

export const SUB_TASK_TYPE_OPTIONS = [
  { value: 'browse', label: '浏览' },
  { value: 'watch', label: '观看' },
  { value: 'like', label: '点赞' },
  { value: 'comment', label: '评论' },
  { value: 'follow', label: '关注' },
]

export const TASK_TABLE_COLUMNS = [
  { key: 'select', label: '', headerClass: 'w-8', cellClass: 'w-8' },
  { key: 'type', label: '任务类型', sortable: true },
  { key: 'keyword', label: '关键词' },
  { key: 'account_id', label: '账号ID' },
  { key: 'device_id', label: '执行设备' },
  { key: 'progress', label: '执行进度' },
  { key: 'status', label: '状态' },
  { key: 'created_at', label: '创建时间', sortable: true },
  { key: 'actions', label: '操作', headerClass: 'text-right', cellClass: 'text-right' },
]

export const KEYWORD_ACTION_TYPE_OPTIONS = [
  { value: 'search_comment', label: '搜索评论' },
  { value: 'search_like', label: '搜索点赞' },
  { value: 'search_dm', label: '搜索私信' },
  { value: 'reply_comment', label: '评论回复' },
  { value: 'collect', label: '数据采集' },
]

export const SORT_BY_OPTIONS = [
  { value: '', label: '默认排序' },
  { value: 'latest', label: '最新发布' },
  { value: 'most_liked', label: '最多点赞' },
]

export const NURTURE_DEFAULT_FORM = {
  type: 'nurture',
  account_id: '',
  device_id: '',
  keyword: '',
  content: '',
  count: 10,
  video_count: 5,  // reply_comment / search_comment / collect 共用
  sort_by: '',
  max_age_days: 5,
  duration: 30,
}
```

## src/utils/format.js

```javascript
export function formatDate(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Shanghai',
  })
}
```

## src/components/layout/AppSidebar.vue

```html
<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { NAV_CATEGORIES } from '../../constants/navigation.js'

const props = defineProps({
  activeCategory: { type: String, required: true },
})

const route = useRoute()
const expanded = ref(false)

const visibleItems = computed(() => {
  const cat = NAV_CATEGORIES.find(c => c.key === props.activeCategory)
  return cat ? cat.items : []
})
</script>

<template>
  <nav
    class="flex flex-col shrink-0 border-r transition-all duration-300 relative z-10"
    :class="expanded ? 'w-52' : 'w-[56px]'"
    style="background: rgba(10, 15, 30, 0.5); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border-color: var(--border-subtle);"
    @mouseenter="expanded = true"
    @mouseleave="expanded = false"
  >
    <div class="flex-1 py-3 space-y-0.5 overflow-y-auto overflow-x-hidden">
      <!-- Category label -->
      <div
        class="px-4 pt-1 pb-2 text-[10px] uppercase tracking-widest font-semibold whitespace-nowrap transition-all duration-200"
        :class="expanded ? 'opacity-100' : 'opacity-0'"
        style="color: var(--accent-400);"
      >
        {{ NAV_CATEGORIES.find(c => c.key === props.activeCategory)?.label || '' }}
      </div>

      <router-link
        v-for="item in visibleItems"
        :key="item.path"
        :to="item.path"
        class="flex items-center h-10 mx-2 rounded-lg transition-all duration-200 group relative no-underline"
        :class="route.path === item.path
          ? 'text-sky-300'
          : 'text-slate-300 hover:text-slate-100'"
        :aria-label="item.name"
      >
        <!-- Active indicator bar -->
        <div
          v-if="route.path === item.path"
          class="absolute left-0 top-2 bottom-2 w-0.5 rounded-r-full"
          style="background: linear-gradient(180deg, var(--accent-500), var(--accent-400));"
        ></div>

        <!-- Icon -->
        <div class="w-[56px] flex items-center justify-center shrink-0">
          <svg class="w-5 h-5 transition-transform duration-200 group-hover:scale-110" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" :d="item.icon" />
          </svg>
        </div>

        <!-- Label -->
        <span
          class="text-[13px] font-medium whitespace-nowrap transition-all duration-200"
          :class="expanded ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-2 w-0 overflow-hidden'"
        >{{ item.name }}</span>

        <!-- Hover glow -->
        <div
          v-if="route.path === item.path"
          class="absolute inset-0 rounded-lg opacity-20 pointer-events-none"
          style="background: linear-gradient(90deg, rgba(14,165,233,0.3), transparent);"
        ></div>
      </router-link>
    </div>

    <!-- Bottom decoration -->
    <div class="p-3 border-t" style="border-color: var(--border-subtle);">
      <div class="flex items-center justify-center">
        <div class="w-6 h-6 rounded-full flex items-center justify-center opacity-30" style="background: var(--accent-glow-soft);">
          <svg class="w-3 h-3" style="color: var(--accent-400);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
      </div>
    </div>
  </nav>
</template>
```

## src/components/layout/AppTopNav.vue

```html
<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../../stores/auth.js'
import { getRealtimeStats } from '../../api/stats.js'

const props = defineProps({
  activeCategory: { type: String, required: true },
})

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const stats = ref({ online_devices: 0, running_tasks: 0, pending_tasks: 0 })
const currentTime = ref('')
let clockTimer = null
let statsTimer = null

function updateClock() {
  currentTime.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
}

async function fetchStats() {
  try { const res = await getRealtimeStats(); stats.value = res.data || stats.value } catch {}
}

onMounted(() => {
  updateClock(); clockTimer = setInterval(updateClock, 1000)
  fetchStats(); statsTimer = setInterval(fetchStats, 15000)
})
onUnmounted(() => { clearInterval(clockTimer); clearInterval(statsTimer) })

function handleLogout() { auth.logout(); router.push('/login') }

const categories = [
  { key: 'ops', label: '运营', to: '/' },
  { key: 'tasks', label: '任务', to: '/tasks' },
  { key: 'data', label: '数据', to: '/data' },
  { key: 'ai-video', label: 'AI 视频', to: '/video-studio' },
  { key: 'system', label: '系统', to: '/settings' },
]

function handleCategoryClick(cat) {
  if (props.activeCategory !== cat.key) {
    router.push(cat.to)
  }
}
</script>

<template>
  <header
    class="h-14 flex items-center justify-between px-6 shrink-0 relative z-20"
    style="background: rgba(10, 15, 30, 0.75); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); border-bottom: 1px solid var(--border-subtle);"
  >
    <!-- Left -->
    <div class="flex items-center gap-6">
      <router-link to="/" class="flex items-center gap-2.5 no-underline group">
        <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background: linear-gradient(135deg, var(--accent-600), var(--accent-500));">
          <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <span class="text-base font-extrabold tracking-tight gradient-text">抖音助手</span>
      </router-link>

      <div class="hidden lg:flex items-center gap-1 tab-bar">
        <button
          v-for="cat in categories" :key="cat.key"
          class="no-underline"
          :class="props.activeCategory === cat.key ? 'active' : ''"
          @click="handleCategoryClick(cat)"
        >{{ cat.label }}</button>
      </div>
    </div>

    <!-- Center: Live Indicators -->
    <div class="hidden md:flex items-center gap-5 text-xs tracking-wide">
      <div class="flex items-center gap-2 px-2.5 py-1 rounded-full" style="background: rgba(52, 211, 153, 0.06); border: 1px solid rgba(52, 211, 153, 0.12);">
        <span class="pulse-dot"></span>
        <span class="font-mono font-semibold text-emerald-400 tabular-nums">{{ stats.online_devices }}</span>
        <span class="text-slate-300">设备</span>
      </div>
      <div class="flex items-center gap-2 px-2.5 py-1 rounded-full" style="background: rgba(251, 191, 36, 0.06); border: 1px solid rgba(251, 191, 36, 0.12);">
        <span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span>
        <span class="font-mono font-semibold text-amber-400 tabular-nums">{{ stats.running_tasks }}</span>
        <span class="text-slate-300">运行中</span>
      </div>
      <div class="flex items-center gap-2 px-2.5 py-1 rounded-full" style="background: rgba(96, 165, 250, 0.06); border: 1px solid rgba(96, 165, 250, 0.12);">
        <span class="w-1.5 h-1.5 rounded-full bg-sky-400"></span>
        <span class="font-mono font-semibold text-sky-400 tabular-nums">{{ stats.pending_tasks }}</span>
        <span class="text-slate-300">待处理</span>
      </div>
    </div>

    <!-- Right -->
    <div class="flex items-center gap-4">
      <span class="hidden sm:block font-mono text-sm text-slate-300 tabular-nums tracking-wider">{{ currentTime }}</span>
      <span class="text-sm font-medium text-slate-200">{{ auth.username }}</span>
      <button @click="handleLogout" class="p-1.5 rounded-lg text-slate-300 hover:text-red-400 hover:bg-red-400/5 transition-all" title="退出">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
        </svg>
      </button>
    </div>
  </header>
</template>
```

## src/components/layout/PageContainer.vue

```html
<script setup>
defineProps({
  title: { type: String, required: true },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})
</script>

<template>
  <div>
    <div v-if="error" class="mb-4 glass-card border-red-500/30 text-red-400 px-4 py-3 rounded-xl flex items-center justify-between">
      <span>{{ error }}</span>
      <button class="text-red-400 hover:text-red-300 font-bold" @click="$emit('dismissError')">&times;</button>
    </div>

    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white">{{ title }}</h1>
      <slot name="actions" />
    </div>

    <slot />
  </div>
</template>
```

## src/components/ui/AppBadge.vue

```html
<script setup>
defineProps({
  variant: {
    type: String,
    default: 'info',
    validator: (v) => ['success', 'warning', 'danger', 'info', 'neutral'].includes(v),
  },
  size: {
    type: String,
    default: 'sm',
    validator: (v) => ['xs', 'sm'].includes(v),
  },
})

const variantClasses = {
  success: 'badge-success',
  warning: 'badge-warning',
  danger: 'badge-danger',
  info: 'badge-info',
  neutral: 'bg-slate-600/50 text-slate-400 border border-slate-600/50 rounded-lg px-2 py-0.5 text-xs',
}

const sizeClasses = {
  xs: 'text-[11px] px-2 py-0.5',
  sm: 'text-xs px-2.5 py-0.5',
}
</script>

<template>
  <span :class="[variantClasses[variant], sizeClasses[size], 'inline-flex items-center rounded-full font-medium']">
    <slot />
  </span>
</template>
```

## src/components/ui/AppButton.vue

```html
<script setup>
defineProps({
  variant: {
    type: String,
    default: 'primary',
    validator: (v) => ['primary', 'secondary', 'danger', 'ghost', 'success'].includes(v),
  },
  size: {
    type: String,
    default: 'md',
    validator: (v) => ['sm', 'md', 'lg'].includes(v),
  },
  disabled: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
})

const variantClasses = {
  primary: 'btn-aurora text-white',
  secondary: 'border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10',
  danger: 'bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/25',
  ghost: 'text-slate-400 hover:text-white hover:bg-white/5',
  success: 'bg-gradient-to-r from-emerald-600 to-emerald-500 text-white hover:from-emerald-500 hover:to-emerald-400 shadow-lg shadow-emerald-500/25',
}

const sizeClasses = {
  sm: 'px-3 py-1 text-xs rounded-lg',
  md: 'px-4 py-2 text-sm font-medium rounded-xl',
  lg: 'px-6 py-2.5 text-base font-medium rounded-xl',
}
</script>

<template>
  <button
    :disabled="disabled || loading"
    :class="[variantClasses[variant], sizeClasses[size], { 'opacity-50 cursor-not-allowed': disabled || loading }]"
    class="inline-flex items-center transition-colors"
  >
    <span v-if="variant === 'primary' || variant === 'success'" class="relative z-10">
      <slot />
    </span>
    <template v-else>
      <slot />
    </template>
  </button>
</template>
```

## src/components/ui/AppDialog.vue

```html
<script setup>
import {
  Dialog,
  DialogPanel,
  DialogTitle,
  TransitionRoot,
  TransitionChild,
} from '@headlessui/vue'

defineProps({
  open: { type: Boolean, required: true },
  title: { type: String, default: '' },
  maxWidth: { type: String, default: 'max-w-lg' },
})

const emit = defineEmits(['close'])
</script>

<template>
  <TransitionRoot :show="open" as="template">
    <Dialog as="div" class="relative z-50" @close="emit('close')">
      <TransitionChild
        as="template"
        enter="ease-out duration-300"
        enter-from="opacity-0"
        enter-to="opacity-100"
        leave="ease-in duration-200"
        leave-from="opacity-100"
        leave-to="opacity-0"
      >
        <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
      </TransitionChild>

      <div class="fixed inset-0 overflow-y-auto">
        <div class="flex min-h-full items-center justify-center p-4">
          <TransitionChild
            as="template"
            enter="ease-out duration-300"
            enter-from="opacity-0 scale-95"
            enter-to="opacity-100 scale-100"
            leave="ease-in duration-200"
            leave-from="opacity-100 scale-100"
            leave-to="opacity-0 scale-95"
          >
            <DialogPanel :class="[maxWidth]" class="glass-card w-full p-6 gradient-border">
              <DialogTitle v-if="title" class="text-lg font-medium text-white">
                {{ title }}
              </DialogTitle>
              <slot />
            </DialogPanel>
          </TransitionChild>
        </div>
      </div>
    </Dialog>
  </TransitionRoot>
</template>
```

## src/components/ui/AppInput.vue

```html
<script setup>
defineProps({
  modelValue: { type: [String, Number], default: '' },
  type: { type: String, default: 'text' },
  placeholder: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  error: { type: String, default: '' },
  inputClass: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <input
    :type="type"
    :value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    :class="[
      'w-full rounded-lg border bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 transition-colors',
      error ? 'border-red-500/50 focus:border-red-500' : 'border-white/10',
      disabled ? 'opacity-50 cursor-not-allowed' : '',
      inputClass,
    ]"
    @input="emit('update:modelValue', $event.target.value)"
  />
</template>
```

## src/components/ui/AppSelect.vue

```html
<script setup>
defineProps({
  modelValue: { type: [String, Number], default: '' },
  options: { type: Array, required: true },
  placeholder: { type: String, default: '请选择' },
  disabled: { type: Boolean, default: false },
  selectClass: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <select
    :value="modelValue"
    :disabled="disabled"
    :class="[
      'w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 transition-colors',
      disabled ? 'opacity-50 cursor-not-allowed' : '',
      selectClass,
    ]"
    @change="emit('update:modelValue', $event.target.value)"
  >
    <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
    <option
      v-for="opt in options"
      :key="opt.value"
      :value="opt.value"
    >
      {{ opt.label }}
    </option>
  </select>
</template>
```

## src/components/business/ChannelCard.vue

```html
<script setup>
import { CHANNEL_TASK_TYPE_LABEL, CHANNEL_STATUS_LABEL, CHANNEL_STATUS_CLASS } from '../../constants/channels.js'

defineProps({
  channel: { type: Object, required: true },
})

defineEmits(['pause', 'resume', 'cancel', 'delete', 'click'])
</script>

<template>
  <div
    class="bg-slate-800/50 backdrop-blur rounded-lg shadow p-4 border border-slate-700 hover:border-slate-500 transition-all cursor-pointer"
    @click="$emit('click', channel)"
  >
    <div class="flex items-center justify-between mb-2">
      <span class="text-sm font-medium text-white">
        {{ channel.group_name }} · {{ CHANNEL_TASK_TYPE_LABEL[channel.task_type] || channel.task_type }}
      </span>
      <span :class="CHANNEL_STATUS_CLASS[channel.status] || 'bg-slate-600/50 text-slate-400'" class="px-2 py-0.5 text-xs rounded-full">
        {{ CHANNEL_STATUS_LABEL[channel.status] || channel.status }}
      </span>
    </div>
    <div class="mb-2">
      <div class="flex justify-between text-xs text-slate-400 mb-1">
        <span>{{ channel.completed }}/{{ channel.total }} 完成</span>
        <span>{{ channel.pending }} 待处理</span>
      </div>
      <div class="w-full bg-slate-700 rounded-full h-2">
        <div class="bg-green-500 h-2 rounded-full transition-all" :style="{ width: channel.total ? (channel.completed / channel.total * 100) + '%' : '0%' }" />
      </div>
    </div>
    <div class="flex items-center justify-between text-xs text-slate-500">
      <span>{{ channel.account_mode === 'single_account' ? '单账号' : '轮转' }}</span>
      <span>{{ channel.assigned }} 执行中</span>
    </div>
    <div class="flex gap-2 mt-3">
      <button v-if="channel.status === 'active'" @click.stop="$emit('pause', channel)" class="px-3 py-1 text-xs bg-yellow-500/20 text-yellow-400 rounded hover:bg-yellow-500/30 transition-colors">暂停</button>
      <button v-if="channel.status === 'paused'" @click.stop="$emit('resume', channel)" class="px-3 py-1 text-xs bg-green-500/20 text-green-400 rounded hover:bg-green-500/30 transition-colors">恢复</button>
      <button v-if="channel.status !== 'cancelled' && channel.status !== 'completed'" @click.stop="$emit('cancel', channel)" class="px-3 py-1 text-xs bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 transition-colors">取消</button>
      <button @click.stop="$emit('delete', channel)" class="px-3 py-1 text-xs bg-slate-600/50 text-slate-300 rounded hover:bg-slate-600 transition-colors">删除</button>
    </div>
  </div>
</template>
```

## src/components/business/ChannelList.vue

```html
<script setup>
import { ref } from 'vue'
import ChannelCard from './ChannelCard.vue'
import ConfirmDialog from '../ConfirmDialog.vue'
import { updateChannel, deleteChannel as deleteChannelApi } from '../../api/channels.js'

const props = defineProps({
  channels: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['refresh', 'detail'])

const confirmOpen = ref(false)
const confirmTitle = ref('')
const confirmMessage = ref('')
const confirmAction = ref(null)
const confirmDanger = ref(false)

function openConfirm(title, message, action, danger) {
  confirmTitle.value = title
  confirmMessage.value = message
  confirmAction.value = action
  confirmDanger.value = danger
  confirmOpen.value = true
}

async function handleConfirm() {
  if (confirmAction.value) await confirmAction.value()
  confirmOpen.value = false
  emit('refresh')
}

async function pauseChannel(ch) {
  openConfirm('暂停通道', '确定暂停此通道？',
    () => updateChannel(ch.id, { status: 'paused' }), false)
}

async function resumeChannel(ch) {
  await updateChannel(ch.id, { status: 'active' })
  emit('refresh')
}

async function cancelChannel(ch) {
  openConfirm('取消通道', '确定取消此通道？已分发的任务将继续执行，未分发的关键词将被跳过。',
    () => updateChannel(ch.id, { status: 'cancelled' }), false)
}

async function deleteChannel(ch) {
  openConfirm('删除通道', `确定要删除此通道吗？此操作不可撤销。`,
    () => deleteChannelApi(ch.id), true)
}
</script>

<template>
  <div v-if="loading" class="text-center py-12 text-slate-400">加载中...</div>
  <div v-else-if="channels.length === 0" class="text-center py-12 text-slate-400">暂无通道，点击上方按钮创建</div>
  <div v-else class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
    <ChannelCard
      v-for="ch in channels"
      :key="ch.id"
      :channel="ch"
      @click="emit('detail', ch)"
      @pause="pauseChannel"
      @resume="resumeChannel"
      @cancel="cancelChannel"
      @delete="deleteChannel"
    />
  </div>

  <ConfirmDialog
    :open="confirmOpen"
    :title="confirmTitle"
    :message="confirmMessage"
    :danger="confirmDanger"
    @confirm="handleConfirm"
    @cancel="confirmOpen = false"
  />
</template>
```

## src/components/business/KeywordSearchDialog.vue

```html
<script setup>
import { ref, watch } from 'vue'
import { Dialog, DialogPanel, DialogTitle, TransitionRoot, TransitionChild } from '@headlessui/vue'
import TipIcon from '../TipIcon.vue'
import { batchCreateTasks } from '../../api/tasks.js'
import { generateKeywords } from '../../api/content.js'
import { listDMSequences } from '../../api/dmSequences.js'
import { useToastStore } from '../../stores/toast.js'
import { KEYWORD_ACTION_TYPE_OPTIONS, SORT_BY_OPTIONS } from '../../constants/tasks.js'

const props = defineProps({
  open: { type: Boolean, required: true },
  accounts: { type: Array, default: () => [] },
  groups: { type: Array, default: () => [] },
  devices: { type: Array, default: () => [] },
  templates: { type: Array, default: () => [] },
  promptTemplates: { type: Array, default: () => [] },
})

const emit = defineEmits(['close', 'created'])

const toast = useToastStore()

const keywordSeed = ref('')
const keywordList = ref([])
const keywordGenerating = ref(false)
const keywordError = ref(null)
const keywordActionType = ref('search_comment')
const keywordSelectionMode = ref('single')
const keywordSelectedGroupIds = ref([])
const keywordSingleAccountId = ref('')
const keywordDeviceId = ref('')
const keywordSortBy = ref('')
const keywordTemplateId = ref('')
const keywordPromptTemplateId = ref('')
const keywordContent = ref('')
const keywordDMSequenceId = ref('')
const dmSequences = ref([])
const keywordMaxAgeDays = ref(5)
const keywordGenerateCount = ref(10)
const keywordProcessingCount = ref(5)
const keywordVideoCount = ref(3)
const keywordShareLinks = ref('')  // 分享链接（collect 类型专用）
const creating = ref(false)

function resetForm() {
  keywordSeed.value = ''
  keywordList.value = []
  keywordError.value = null
  creating.value = false
  keywordActionType.value = 'search_comment'
  keywordSelectionMode.value = 'single'
  keywordSelectedGroupIds.value = []
  keywordSingleAccountId.value = ''
  keywordDeviceId.value = ''
  keywordSortBy.value = ''
  keywordTemplateId.value = ''
  keywordPromptTemplateId.value = ''
  keywordContent.value = ''
  keywordMaxAgeDays.value = 5
  keywordGenerateCount.value = 10
  keywordProcessingCount.value = 5
  keywordVideoCount.value = 3
}

watch(() => props.open, async (val) => {
  if (val) {
    resetForm()
    try { const res = await listDMSequences(); dmSequences.value = res.data.sequences || [] } catch (e) {}
  }
})

async function handleGenerateKeywords() {
  if (!keywordSeed.value.trim()) { keywordError.value = '请输入种子关键词'; return }
  keywordGenerating.value = true
  keywordError.value = null
  try {
    const res = await generateKeywords(keywordSeed.value.trim(), keywordGenerateCount.value)
    const expanded = res.data.keywords || []
    const seen = new Set([keywordSeed.value.trim()])
    const merged = [keywordSeed.value.trim()]
    for (const kw of expanded) { if (!seen.has(kw)) { seen.add(kw); merged.push(kw) } }
    keywordList.value = merged
  } catch (e) {
    keywordError.value = e.response?.data?.detail || '生成失败，请重试'
  } finally {
    keywordGenerating.value = false
  }
}

function removeKeyword(idx) { keywordList.value.splice(idx, 1) }

async function handleBatchCreateKeywordTasks() {
  if (keywordList.value.length === 0) { keywordError.value = '请先生成关键词'; return }
  if (keywordSelectionMode.value === 'single' && !keywordSingleAccountId.value) { keywordError.value = '请选择账号'; return }
  if (keywordSelectionMode.value === 'group' && keywordSelectedGroupIds.value.length === 0) { keywordError.value = '请至少选择一个分组'; return }

  creating.value = true
  keywordError.value = null

  try {
    const kwList = keywordList.value.map(k => typeof k === 'string' ? k.trim() : k).filter(Boolean)
    if (kwList.length === 0) { keywordError.value = '关键词列表为空'; return }

    const params = { keyword: kwList[0] || '', keywords: kwList, count: keywordProcessingCount.value }
    if (keywordSortBy.value) params.sort_by = keywordSortBy.value
    params.max_age_days = keywordMaxAgeDays.value || 30
    if (keywordDMSequenceId.value) { params.dm_sequence_id = keywordDMSequenceId.value }
    else if (keywordTemplateId.value) { params.content_template_id = keywordTemplateId.value }
    else if (keywordContent.value) { params.content = keywordContent.value }
    if (keywordPromptTemplateId.value) params.prompt_template_id = keywordPromptTemplateId.value
    if (['reply_comment', 'search_comment', 'collect'].includes(keywordActionType.value)) {
      params.video_count = keywordVideoCount.value
    }
    if (keywordActionType.value === 'collect' && keywordShareLinks.value.trim()) {
      params.share_links = (keywordShareLinks.value.match(/https?:\/\/v\.douyin\.com\/[A-Za-z0-9_?=&%]+\/?/g) || [])
    }

    const payload = {
      type: keywordActionType.value,
      params,
      ...(keywordDeviceId.value ? { device_id: keywordDeviceId.value } : {}),
    }

    if (keywordSelectionMode.value === 'group') {
      payload.group_ids = keywordSelectedGroupIds.value
    } else {
      payload.account_ids = [keywordSingleAccountId.value]
    }

    const resp = await batchCreateTasks(payload)
    const created = resp.data?.created || 0
    const mode = resp.data?.mode || ''
    toast.success(mode === 'channel' ? `通道已创建，${created} 个关键词任务将自动分发` : `成功创建 ${created} 个任务`)
    emit('created')
  } catch (e) {
    keywordError.value = e.response?.data?.detail || '创建失败'
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <TransitionRoot :show="open" as="template">
    <Dialog as="div" class="relative z-50" @close="emit('close')">
      <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
        <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
      </TransitionChild>
      <div class="fixed inset-0 overflow-y-auto">
        <div class="flex min-h-full items-center justify-center p-4">
          <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
            <DialogPanel class="glass-card w-full max-w-xl p-6 gradient-border">
              <DialogTitle class="text-lg font-medium text-white">关键词搜索</DialogTitle>

              <div v-if="keywordError" class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-3 py-2 rounded-lg">{{ keywordError }}</div>

              <div class="mt-4 space-y-4 max-h-[70vh] overflow-y-auto pr-1">
                <!-- Seed keyword -->
                <div class="flex gap-2 items-end">
                  <div class="flex-1">
                    <label class="block text-sm font-medium text-slate-300 mb-1">种子关键词 <TipIcon text="输入一个基础关键词，AI 会自动扩展出多个相关搜索词" /></label>
                    <input v-model="keywordSeed" type="text" maxlength="50" class="block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="输入种子关键词，如：美食" @keyup.enter="handleGenerateKeywords" />
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-slate-300 mb-1">生成数量</label>
                    <input v-model.number="keywordGenerateCount" type="number" min="1" max="30" class="w-20 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                  </div>
                  <button type="button" :disabled="keywordGenerating" class="px-4 py-2 bg-gradient-to-r from-emerald-600 to-emerald-500 text-white text-sm font-medium rounded-lg hover:from-emerald-500 hover:to-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-emerald-500/25" @click="handleGenerateKeywords">
                    {{ keywordGenerating ? '生成中...' : 'AI 扩展' }}
                  </button>
                </div>

                <!-- Keyword matrix -->
                <div v-if="keywordList.length > 0">
                  <label class="block text-sm font-medium text-slate-300 mb-1">关键词矩阵 <TipIcon text="AI 生成的关键词列表，点击 X 可删除不需要的，最终保留的将各创建一个任务" /></label>
                  <div class="flex flex-wrap gap-2 p-3 border border-white/10 rounded-lg max-h-32 overflow-y-auto">
                    <span v-for="(kw, idx) in keywordList" :key="idx" class="inline-flex items-center gap-1 px-2.5 py-1 bg-purple-500/15 text-purple-300 text-sm rounded-full border border-purple-500/25">
                      {{ kw }}
                      <button type="button" @click="removeKeyword(idx)" class="text-purple-400 hover:text-purple-300">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                      </button>
                    </span>
                  </div>
                </div>

                <!-- 分享链接（collect 专用） -->
                <div v-if="keywordActionType === 'collect'">
                  <label class="block text-sm font-medium text-slate-300 mb-1">分享链接 <TipIcon text="粘贴抖音分享链接，每行一个。通过链接直接打开视频采集，无需关键词" width="w-72" /></label>
                  <textarea v-model="keywordShareLinks" rows="3" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="直接粘贴抖音分享口令，自动提取链接"></textarea>
                </div>

                <!-- Action type + count + video_count -->
                <div class="grid grid-cols-3 gap-3">
                  <div>
                    <label class="block text-sm font-medium text-slate-300">操作类型 <TipIcon text="批量创建任务时使用的操作类型" /></label>
                    <select v-model="keywordActionType" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                      <option v-for="opt in KEYWORD_ACTION_TYPE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                    </select>
                  </div>
                  <div v-if="['reply_comment', 'search_comment', 'collect'].includes(keywordActionType)">
                    <label class="block text-sm font-medium text-slate-300">处理视频数 <TipIcon text="每个关键词要处理的视频数量，-1=全量" /></label>
                    <input v-model.number="keywordVideoCount" type="number" min="-1" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-slate-300">每视频评论数 <TipIcon text="每个视频要处理的评论数量，-1=全量" /></label>
                    <input v-model.number="keywordProcessingCount" type="number" min="-1" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                  </div>
                </div>

                <!-- Selection mode -->
                <div>
                  <label class="block text-sm font-medium text-slate-300 mb-2">选择方式</label>
                  <div class="flex gap-4">
                    <label class="flex items-center gap-2 cursor-pointer"><input type="radio" v-model="keywordSelectionMode" value="single" class="text-purple-500 focus:ring-purple-500" /><span class="text-sm text-slate-300">单账号</span></label>
                    <label class="flex items-center gap-2 cursor-pointer"><input type="radio" v-model="keywordSelectionMode" value="group" class="text-purple-500 focus:ring-purple-500" /><span class="text-sm text-slate-300">按分组批量</span></label>
                  </div>
                </div>

                <div v-if="keywordSelectionMode === 'single'">
                  <label class="block text-sm font-medium text-slate-300">选择账号 <span class="text-red-400">*</span></label>
                  <select v-model="keywordSingleAccountId" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                    <option value="" disabled>请选择账号</option>
                    <option v-for="acct in accounts" :key="acct.id" :value="acct.id">{{ acct.nickname || acct.douyin_id || acct.id }}</option>
                  </select>
                </div>

                <div v-if="keywordSelectionMode === 'group'">
                  <label class="block text-sm font-medium text-slate-300 mb-1">选择分组 <span class="text-red-400">*</span></label>
                  <div class="max-h-32 overflow-y-auto rounded-lg border border-white/10 bg-white/5 p-2 space-y-1">
                    <label v-for="grp in groups" :key="grp.id" class="flex items-center gap-2 px-2 py-1 rounded hover:bg-white/5 cursor-pointer">
                      <input type="checkbox" :value="grp.id" v-model="keywordSelectedGroupIds" class="rounded border-white/20 bg-white/5 text-purple-500 focus:ring-purple-500" />
                      <span class="text-sm text-slate-300">{{ grp.name }} <span class="text-slate-500">({{ grp.member_count || 0 }})</span></span>
                    </label>
                    <p v-if="groups.length === 0" class="text-sm text-slate-500 px-2 py-1">暂无分组</p>
                  </div>
                </div>

                <!-- Sort by -->
                <div>
                  <label class="block text-sm font-medium text-slate-300">排序方式</label>
                  <select v-model="keywordSortBy" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                    <option v-for="opt in SORT_BY_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                  </select>
                </div>

                <div v-if="['search_comment', 'reply_comment', 'collect'].includes(keywordActionType)">
                  <label class="block text-sm font-medium text-slate-300">评论最大天数 <TipIcon text="只处理在此天数内发布的评论，-1=不限天数" /></label>
                  <input v-model.number="keywordMaxAgeDays" type="number" min="-1" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                </div>

                <template v-if="['search_comment', 'search_dm', 'reply_comment'].includes(keywordActionType)">
                  <div v-if="dmSequences.length > 0 && ['search_dm', 'reply_comment'].includes(keywordActionType)">
                    <label class="block text-sm font-medium text-slate-300">DM 序列模板</label>
                    <select v-model="keywordDMSequenceId" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                      <option value="">不使用序列</option>
                      <option v-for="seq in dmSequences" :key="seq.id" :value="seq.id">{{ seq.name }} ({{ seq.message_count }}条)</option>
                    </select>
                  </div>
                  <div v-if="!keywordDMSequenceId && templates.length > 0">
                    <label class="block text-sm font-medium text-slate-300">内容模板</label>
                    <select v-model="keywordTemplateId" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                      <option value="">不使用模板</option>
                      <option v-for="tpl in templates" :key="tpl.id" :value="tpl.id">{{ tpl.name }} ({{ tpl.category }})</option>
                    </select>
                  </div>
                  <div v-if="!keywordDMSequenceId">
                    <label class="block text-sm font-medium text-slate-300">评论/私信内容 <TipIcon text="留空则使用模板或 AI 生成" /></label>
                    <textarea v-model="keywordContent" rows="2" maxlength="500" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="输入内容...（留空用模板）" />
                  </div>
                </template>

                <div v-if="promptTemplates.length > 0">
                  <label class="block text-sm font-medium text-slate-300">提示词模版 <TipIcon text="选择 AI 提示词模版，留空则使用设备端默认模版" /></label>
                  <select v-model="keywordPromptTemplateId" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                    <option value="">设备默认模版</option>
                    <option v-for="tpl in promptTemplates" :key="tpl.id" :value="tpl.id">{{ tpl.name }} ({{ tpl.industry }})</option>
                  </select>
                </div>

                <div>
                  <label class="block text-sm font-medium text-slate-300">执行设备</label>
                  <select v-model="keywordDeviceId" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                    <option value="">自动分配</option>
                    <option v-for="dev in devices" :key="dev.id" :value="dev.id">{{ dev.name }} {{ dev.status === 'online' ? '(在线)' : '(离线)' }}</option>
                  </select>
                </div>
              </div>

              <div class="flex justify-end gap-3 pt-4">
                <button type="button" class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors" @click="emit('close')">取消</button>
                <button type="button" :disabled="creating || keywordList.length === 0" class="btn-aurora rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed" @click="handleBatchCreateKeywordTasks">
                  <span class="relative z-10">{{ creating ? '创建中...' : `批量创建 ${keywordList.length} 个任务` }}</span>
                </button>
              </div>
            </DialogPanel>
          </TransitionChild>
        </div>
      </div>
    </Dialog>
  </TransitionRoot>
</template>
```

## src/components/business/TaskCreateDialog.vue

```html
<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { Dialog, DialogPanel, DialogTitle, TransitionRoot, TransitionChild } from '@headlessui/vue'
import TipIcon from '../TipIcon.vue'
import { createTask, batchCreateTasks } from '../../api/tasks.js'
import { generateKeywords } from '../../api/content.js'
import { listDMSequences } from '../../api/dmSequences.js'
import { useToastStore } from '../../stores/toast.js'
import { TASK_TYPE_OPTIONS, SUB_TASK_TYPE_OPTIONS, NURTURE_DEFAULT_FORM } from '../../constants/tasks.js'

const props = defineProps({
  open: { type: Boolean, required: true },
  accounts: { type: Array, default: () => [] },
  groups: { type: Array, default: () => [] },
  devices: { type: Array, default: () => [] },
  templates: { type: Array, default: () => [] },
  promptTemplates: { type: Array, default: () => [] },
})

const emit = defineEmits(['close', 'created'])

const toast = useToastStore()

const creating = ref(false)
const createError = ref(null)
const selectionMode = ref('single')
const selectedGroupIds = ref([])
const selectedTemplateId = ref('')
const selectedPromptTemplateId = ref('')
const keywordDMSequenceId = ref('')
const dmSequences = ref([])
const keywordExpandCount = ref(8)
const keywordGenerating = ref(false)
const shareLinksText = ref('')  // 分享链接输入（collect 类型专用）

const form = reactive({ ...NURTURE_DEFAULT_FORM })

const nurtureMode = ref('simple')
const subTasks = ref([{ type: 'browse', count: 10, content_template_id: '' }])
const completionMode = ref('all')
const maxDuration = ref(60)
const nurtureKeywords = ref('')
const nurtureKeywordMatrix = ref([])
const nurtureKeywordGenerating = ref(false)
const nurtureKeywordExpandCount = ref(8)

function addSubTask() {
  subTasks.value.push({ type: 'browse', count: 5, content_template_id: '' })
}

function removeSubTask(index) {
  if (subTasks.value.length <= 1) return
  subTasks.value.splice(index, 1)
}

const filteredDevices = computed(() => {
  if (!form.account_id) return props.devices
  return props.devices.filter(d => !d.bound_account_id || d.bound_account_id === form.account_id)
})

const filteredTemplates = computed(() => {
  if (form.type === 'nurture') return []
  return props.templates
})

const isSearchType = computed(() =>
  ['search_comment', 'search_like', 'search_dm', 'reply_comment', 'collect'].includes(form.type)
)

watch(() => form.type, (newType) => {
  if (newType === 'nurture') selectedTemplateId.value = ''
})

watch(() => form.account_id, () => {
  form.device_id = ''
})

function buildParams() {
  if (form.type === 'nurture') {
    if (nurtureMode.value === 'advanced') {
      if (subTasks.value.length === 0) throw new Error('高级模式下至少需要一个子任务')
      const params = {
        sub_tasks: subTasks.value.map(st => ({
          type: st.type, count: st.count,
          ...(st.type === 'comment' && st.content_template_id ? { content_template_id: st.content_template_id } : {}),
        })),
        completion_mode: completionMode.value,
        duration: maxDuration.value,
      }
      const seeds = nurtureKeywords.value.split(/[,，\s]+/).map(s => s.trim()).filter(Boolean)
      if (seeds.length > 0) { params.keywords = seeds; params.expand_count = nurtureKeywordExpandCount.value }
      return params
    }
    return { duration: form.duration }
  }

  const params = { keyword: form.keyword, count: form.count }
  if (form.type === 'collect' && shareLinksText.value.trim()) {
    params.share_links = (shareLinksText.value.match(/https?:\/\/v\.douyin\.com\/[A-Za-z0-9_?=&%]+\/?/g) || [])
  }
  if (form.sort_by) params.sort_by = form.sort_by

  if (['search_dm', 'reply_comment'].includes(form.type) && keywordDMSequenceId.value) {
    params.dm_sequence_id = keywordDMSequenceId.value
  }
  if (['search_comment', 'search_dm', 'reply_comment', 'collect'].includes(form.type) && !keywordDMSequenceId.value) {
    if (selectedTemplateId.value) { params.content_template_id = selectedTemplateId.value }
    else if (form.content) { params.content = form.content }
  }

  if (['search_comment', 'search_dm', 'reply_comment', 'nurture'].includes(form.type)) {
    if (selectedPromptTemplateId.value) params.prompt_template_id = selectedPromptTemplateId.value
  }

  if (['reply_comment', 'search_comment', 'collect'].includes(form.type)) {
    params.video_count = form.video_count
    params.max_age_days = form.max_age_days
  }

  return params
}

async function handleCreate() {
  if (!form.type) { createError.value = '请选择任务类型'; return }
  if (selectionMode.value === 'single' && !form.account_id) { createError.value = '请选择账号'; return }
  if (selectionMode.value === 'group' && selectedGroupIds.value.length === 0) { createError.value = '请至少选择一个分组'; return }
  if (isSearchType.value && !form.keyword && !shareLinksText.value.trim()) { createError.value = '请输入搜索关键词或分享链接'; return }

  creating.value = true
  createError.value = null

  try {
    const params = buildParams()
    if (selectionMode.value === 'group') {
      const payload = { type: form.type, group_ids: selectedGroupIds.value, params }
      if (form.device_id) payload.device_id = form.device_id
      const res = await batchCreateTasks(payload)
      toast.success(`批量创建成功：${res.data?.created || 0} 个任务`)
    } else {
      const payload = { type: form.type, account_id: form.account_id, params }
      if (form.device_id) payload.device_id = form.device_id
      await createTask(payload)
    }
    emit('created')
  } catch (e) {
    createError.value = e.response?.data?.message || e.response?.data?.detail || '创建失败，请重试'
  } finally {
    creating.value = false
  }
}

async function expandNurtureKeywords() {
  const seeds = nurtureKeywords.value.split(/[,，\s]+/).map(s => s.trim()).filter(Boolean)
  if (seeds.length === 0) return
  nurtureKeywordGenerating.value = true
  try {
    const allExpanded = []
    for (const seed of seeds) {
      const res = await generateKeywords(seed, nurtureKeywordExpandCount.value)
      allExpanded.push(...(res.data.keywords || []))
    }
    nurtureKeywordMatrix.value = [...new Set(allExpanded)]
    toast.success(`已扩展 ${nurtureKeywordMatrix.value.length} 个关键词`)
  } catch (e) {
    toast.error('关键词扩展失败，请重试')
  } finally {
    nurtureKeywordGenerating.value = false
  }
}

async function expandCreateKeyword() {
  const seed = form.keyword.trim()
  if (!seed) return
  keywordGenerating.value = true
  try {
    const seeds = seed.split(/[,，]/).map(s => s.trim()).filter(Boolean)
    const allExpanded = []
    for (const s of seeds) {
      const res = await generateKeywords(s, keywordExpandCount.value)
      allExpanded.push(...(res.data.keywords || []))
    }
    const seen = {}
    const merged = []
    for (const s of seeds) { if (!seen[s]) { seen[s] = true; merged.push(s) } }
    for (const kw of allExpanded) { if (!seen[kw]) { seen[kw] = true; merged.push(kw) } }
    form.keyword = merged.join('，')
  } catch (e) {
    toast.error('关键词扩展失败')
  } finally {
    keywordGenerating.value = false
  }
}

function openDialog() {
  Object.assign(form, NURTURE_DEFAULT_FORM)
  selectedTemplateId.value = ''
  selectedPromptTemplateId.value = ''
  keywordDMSequenceId.value = ''
  dmSequences.value = []
  selectionMode.value = 'single'
  selectedGroupIds.value = []
  createError.value = null
  nurtureKeywords.value = ''
  nurtureKeywordMatrix.value = []
  nurtureKeywordExpandCount.value = 8
}

watch(() => props.open, async (val) => {
  if (val) {
    openDialog()
    try { const res = await listDMSequences(); dmSequences.value = res.data.sequences || [] } catch (e) {}
  }
})
</script>

<template>
  <TransitionRoot :show="open" as="template">
    <Dialog as="div" class="relative z-50" @close="emit('close')">
      <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
        <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
      </TransitionChild>
      <div class="fixed inset-0 overflow-y-auto">
        <div class="flex min-h-full items-center justify-center p-4">
          <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
            <DialogPanel class="glass-card w-full max-w-lg p-6 gradient-border">
              <DialogTitle class="text-lg font-medium text-white">创建任务</DialogTitle>

              <div v-if="createError" class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-3 py-2 rounded-lg">
                {{ createError }}
              </div>

              <form class="mt-4 space-y-4" @submit.prevent="handleCreate">
                <!-- Task Type -->
                <div>
                  <label class="block text-sm font-medium text-slate-300">
                    任务类型 <TipIcon text="选择要执行的任务类型。养号=模拟真实用户行为提升权重；搜索评论/点赞/私信=按关键词搜索视频后自动操作；评论回复=回复已有评论引流" /> <span class="text-red-400">*</span>
                  </label>
                  <select v-model="form.type" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                    <option v-for="opt in TASK_TYPE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                  </select>
                </div>

                <!-- Selection mode -->
                <div>
                  <label class="block text-sm font-medium text-slate-300 mb-2">选择方式 <TipIcon text="单账号=为一个账号创建任务；按分组=为分组内所有活跃账号批量创建任务" /></label>
                  <div class="flex gap-4">
                    <label class="flex items-center gap-2 cursor-pointer">
                      <input type="radio" v-model="selectionMode" value="single" class="text-purple-500 focus:ring-purple-500" />
                      <span class="text-sm text-slate-300">单账号</span>
                    </label>
                    <label class="flex items-center gap-2 cursor-pointer">
                      <input type="radio" v-model="selectionMode" value="group" class="text-purple-500 focus:ring-purple-500" />
                      <span class="text-sm text-slate-300">按分组批量</span>
                    </label>
                  </div>
                </div>

                <!-- Account (single) -->
                <div v-if="selectionMode === 'single'">
                  <label class="block text-sm font-medium text-slate-300">账号 <TipIcon text="选择执行此任务的抖音账号" /> <span class="text-red-400">*</span></label>
                  <select v-model="form.account_id" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                    <option value="" disabled>请选择账号</option>
                    <option v-for="acct in accounts" :key="acct.id" :value="acct.id">{{ acct.nickname || acct.douyin_id || acct.id }}</option>
                  </select>
                </div>

                <!-- Groups (batch) -->
                <div v-if="selectionMode === 'group'">
                  <label class="block text-sm font-medium text-slate-300 mb-1">选择分组 <TipIcon text="选中的分组内所有活跃账号都会创建相同任务" /> <span class="text-red-400">*</span></label>
                  <div class="max-h-40 overflow-y-auto rounded-lg border border-white/10 bg-white/5 p-2 space-y-1">
                    <label v-for="grp in groups" :key="grp.id" class="flex items-center gap-2 px-2 py-1 rounded hover:bg-white/5 cursor-pointer">
                      <input type="checkbox" :value="grp.id" v-model="selectedGroupIds" class="rounded border-white/20 bg-white/5 text-purple-500 focus:ring-purple-500" />
                      <span class="text-sm text-slate-300">{{ grp.name }} <span class="text-slate-500">({{ grp.member_count || 0 }} 个账号)</span></span>
                    </label>
                    <p v-if="groups.length === 0" class="text-sm text-slate-500 px-2 py-1">暂无分组，请先创建账号分组</p>
                  </div>
                </div>

                <!-- Device -->
                <div>
                  <label class="block text-sm font-medium text-slate-300">执行设备 <TipIcon text="选择运行任务的设备。留空则自动分配给该账号绑定的在线设备" /></label>
                  <select v-model="form.device_id" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                    <option value="">自动分配（绑定设备领取）</option>
                    <option v-for="dev in filteredDevices" :key="dev.id" :value="dev.id">{{ dev.name }} {{ dev.status === 'online' ? '(在线)' : '(离线)' }}</option>
                  </select>
                </div>

                <!-- Nurture params -->
                <template v-if="form.type === 'nurture'">
                  <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">养号模式 <TipIcon text="简单模式=设定总时长，系统自动随机操作；高级模式=自定义多个子任务按顺序执行" width="w-80" /></label>
                    <div class="flex gap-4">
                      <label class="flex items-center gap-2 cursor-pointer"><input type="radio" v-model="nurtureMode" value="simple" class="text-purple-500 focus:ring-purple-500" /><span class="text-sm text-slate-300">简单模式</span></label>
                      <label class="flex items-center gap-2 cursor-pointer"><input type="radio" v-model="nurtureMode" value="advanced" class="text-purple-500 focus:ring-purple-500" /><span class="text-sm text-slate-300">高级模式（子任务）</span></label>
                    </div>
                  </div>

                  <div v-if="nurtureMode === 'simple'">
                    <label class="block text-sm font-medium text-slate-300">养号时长（分钟） <TipIcon text="简单模式下养号操作的总持续时间，建议 15-60 分钟" /></label>
                    <input v-model.number="form.duration" type="number" min="1" max="120" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                  </div>

                  <div v-else class="space-y-3">
                    <div>
                      <label class="block text-sm font-medium text-slate-300 mb-1">子任务列表 <TipIcon text="按顺序配置多个操作步骤。每个子任务指定类型和执行次数" /></label>
                      <p class="mt-1 text-xs text-slate-500">浏览/观看=刷视频，点赞/评论/关注=互动操作</p>
                      <div class="space-y-2">
                        <div v-for="(st, idx) in subTasks" :key="idx" class="flex items-center gap-2">
                          <select v-model="st.type" class="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-slate-200">
                            <option v-for="opt in SUB_TASK_TYPE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                          </select>
                          <input v-model.number="st.count" type="number" min="1" max="100" class="w-20 rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-slate-200" placeholder="次数" />
                          <select v-if="st.type === 'comment'" v-model="st.content_template_id" class="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-slate-200">
                            <option value="">选择模板</option>
                            <option v-for="tpl in templates" :key="tpl.id" :value="tpl.id">{{ tpl.name }}</option>
                          </select>
                          <button type="button" @click="removeSubTask(idx)" class="text-red-400 hover:text-red-300">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                          </button>
                        </div>
                      </div>
                      <button type="button" @click="addSubTask" class="mt-2 text-sm text-cyan-400 hover:text-cyan-300">+ 添加子任务</button>
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                      <div>
                        <label class="block text-sm font-medium text-slate-300">完成模式 <TipIcon text="全部完成=所有子任务都必须完成才算成功；任一完成=任意一个子任务完成即可" /></label>
                        <select v-model="completionMode" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                          <option value="all">全部完成</option><option value="any">任一完成</option>
                        </select>
                      </div>
                      <div>
                        <label class="block text-sm font-medium text-slate-300">最大时长（分钟） <TipIcon text="高级模式下整个养号任务的最大执行时间，超时自动停止" /></label>
                        <input v-model.number="maxDuration" type="number" min="1" max="240" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                      </div>
                    </div>
                  </div>

                  <!-- Nurture keyword filter -->
                  <div>
                    <label class="block text-sm font-medium text-slate-300 mb-1">关键词过滤 <TipIcon text="输入种子关键词，AI 扩展为关键词矩阵。养号时只对匹配关键词的内容进行点赞/评论/关注，不匹配的内容直接跳过。留空则不限制" /></label>
                    <div class="flex gap-2">
                      <input v-model="nurtureKeywords" type="text" class="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="输入种子关键词，逗号分隔，如：养生,中医,食疗" />
                      <input v-model.number="nurtureKeywordExpandCount" type="number" min="3" max="30" class="w-16 rounded-lg border border-white/10 bg-white/5 px-2 py-2 text-sm text-slate-200 text-center" title="扩展数量" />
                      <button type="button" @click="expandNurtureKeywords" :disabled="nurtureKeywordGenerating || !nurtureKeywords.trim()" class="px-3 py-2 rounded-lg text-sm font-medium bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30 disabled:opacity-50">
                        {{ nurtureKeywordGenerating ? '扩展中...' : 'AI 扩展' }}
                      </button>
                    </div>
                    <div v-if="nurtureKeywordMatrix.length > 0" class="mt-2 flex flex-wrap gap-1.5">
                      <span v-for="(kw, idx) in nurtureKeywordMatrix" :key="idx" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-purple-500/20 text-purple-300">
                        {{ kw }}<button type="button" @click="nurtureKeywordMatrix.splice(idx, 1)" class="hover:text-purple-100">&times;</button>
                      </span>
                    </div>
                  </div>
                </template>

                <!-- Search type params -->
                <template v-if="isSearchType">
                  <div>
                    <label class="block text-sm font-medium text-slate-300">搜索关键词 <TipIcon text="输入种子词，点击 AI 扩展自动生成相关关键词" /> <span class="text-red-400">*</span></label>
                    <div class="flex gap-2 mt-1">
                      <input v-model="form.keyword" type="text" maxlength="200" class="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="例：美食、养生" />
                      <input v-model.number="keywordExpandCount" type="number" min="3" max="30" class="w-16 rounded-lg border border-white/10 bg-white/5 px-2 py-2 text-sm text-slate-200 text-center" title="扩展数量" />
                      <button type="button" @click="expandCreateKeyword" :disabled="keywordGenerating" class="px-3 py-2 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-500 disabled:opacity-50 transition-colors whitespace-nowrap">{{ keywordGenerating ? '...' : 'AI 扩展' }}</button>
                    </div>
                  </div>

                  <!-- 分享链接（collect 专用） -->
                  <div v-if="form.type === 'collect'">
                    <label class="block text-sm font-medium text-slate-300">分享链接 <TipIcon text="粘贴抖音分享链接，每行一个。通过链接直接打开视频进行数据采集，无需关键词搜索" width="w-72" /></label>
                    <textarea v-model="shareLinksText" rows="3" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="直接粘贴抖音分享口令，自动提取链接"></textarea>
                  </div>

                  <div>
                    <label class="block text-sm font-medium text-slate-300">排序方式 <TipIcon text="控制搜索结果排序，影响目标视频选择优先级" /></label>
                    <select v-model="form.sort_by" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                      <option value="">默认排序</option>
                      <option value="latest">最新发布</option>
                      <option value="most_liked">最多点赞</option>
                    </select>
                  </div>

                  <div>
                    <label class="block text-sm font-medium text-slate-300">{{ form.type === 'reply_comment' ? '每视频评论数' : form.type === 'collect' ? '每视频采集数' : form.type === 'search_like' ? '点赞数' : '处理数量' }} <TipIcon text="每个视频中要处理的数量，-1=全量" /></label>
                    <input v-model.number="form.count" type="number" min="-1" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                  </div>

                  <!-- 视频数（reply_comment / search_comment / collect 共用） -->
                  <div v-if="['reply_comment', 'search_comment', 'collect'].includes(form.type)">
                    <label class="block text-sm font-medium text-slate-300">处理视频数 <TipIcon text="每个关键词要处理的视频数量，-1=全量" /></label>
                    <input v-model.number="form.video_count" type="number" min="-1" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                  </div>
                </template>

                <!-- 评论最大天数（reply_comment / search_comment / collect 共用） -->
                <div v-if="['reply_comment', 'search_comment', 'collect'].includes(form.type)">
                  <label class="block text-sm font-medium text-slate-300">评论最大天数 <TipIcon text="只处理在此天数内发布的评论，-1=不限天数" /></label>
                  <input v-model.number="form.max_age_days" type="number" min="-1" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                </div>

                <!-- Content template + DM sequence + text -->
                <template v-if="['search_comment', 'search_dm', 'reply_comment', 'collect'].includes(form.type)">
                  <div v-if="dmSequences.length > 0 && ['search_dm', 'reply_comment'].includes(form.type)">
                    <label class="block text-sm font-medium text-slate-300">DM 序列模板</label>
                    <select v-model="keywordDMSequenceId" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                      <option value="">不使用序列</option>
                      <option v-for="seq in dmSequences" :key="seq.id" :value="seq.id">{{ seq.name }} ({{ seq.message_count }}条)</option>
                    </select>
                  </div>
                  <div v-if="!keywordDMSequenceId && filteredTemplates.length > 0">
                    <label class="block text-sm font-medium text-slate-300">内容模板 <TipIcon text="选择预设的评论/私信模板，模板中的变量会自动替换为实际值" /></label>
                    <select v-model="selectedTemplateId" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                      <option value="">不使用模板</option>
                      <option v-for="tpl in filteredTemplates" :key="tpl.id" :value="tpl.id">{{ tpl.name }} ({{ tpl.category }})</option>
                    </select>
                  </div>
                  <div v-if="!keywordDMSequenceId">
                    <label class="block text-sm font-medium text-slate-300">{{ form.type === 'search_dm' ? '私信内容' : '评论/私信内容' }} <TipIcon text="发送的内容文本。支持 {keyword}、{username}、{video_title} 变量。留空则使用模板或 AI 生成" width="w-80" /></label>
                    <textarea v-model="form.content" rows="3" maxlength="500" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" :placeholder="form.type === 'reply_comment' ? '留空则使用 AI 生成招呼语' : '输入内容...'" />
                  </div>
                </template>

                <!-- Prompt template -->
                <div v-if="promptTemplates.length > 0">
                  <label class="block text-sm font-medium text-slate-300">提示词模版 <TipIcon text="选择 AI 提示词模版，控制 AI 分析评论、生成回复的风格策略。留空则使用设备端默认模版" /></label>
                  <select v-model="selectedPromptTemplateId" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                    <option value="">设备默认模版</option>
                    <option v-for="tpl in promptTemplates" :key="tpl.id" :value="tpl.id">{{ tpl.name }} ({{ tpl.industry }})</option>
                  </select>
                </div>

                <div class="flex justify-end gap-3 pt-2">
                  <button type="button" class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors" @click="emit('close')">取消</button>
                  <button type="submit" :disabled="creating" class="btn-aurora rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed">
                    <span class="relative z-10">{{ creating ? '创建中...' : '创建' }}</span>
                  </button>
                </div>
              </form>
            </DialogPanel>
          </TransitionChild>
        </div>
      </div>
    </Dialog>
  </TransitionRoot>
</template>
```

## src/components/video-studio/ActionTransferPanel.vue

```html
<script setup>
import { ref } from 'vue'
import { generateVideoAsync, getTask } from '../../api/pixelle-client.js'

const sourceVideo = ref(null)
const sourcePreview = ref('')
const actionPrompt = ref('')
const transferWorkflow = ref('')

const generating = ref(false)
const progress = ref({ percent: 0, message: '' })
const result = ref(null)

function handleVideo(e) {
  const file = e.target.files?.[0]
  if (file) {
    sourceVideo.value = file
    sourcePreview.value = URL.createObjectURL(file)
  }
}

async function handleGenerate() {
  if (!sourceVideo.value) return
  generating.value = true; result.value = null
  try {
    const payload = {
      text: actionPrompt.value || 'action transfer',
      mode: 'generate',
      n_scenes: 1,
    }
    if (transferWorkflow.value) payload.media_workflow = transferWorkflow.value
    const resp = await generateVideoAsync(payload)
    const taskId = resp.data?.task_id
    if (!taskId) throw new Error('No task ID')
    await new Promise((resolve, reject) => {
      let a = 0; const t = setInterval(async () => {
        a++; if (a > 120) { clearInterval(t); reject(new Error('Timeout')); return }
        try {
          const r = await getTask(taskId)
          if (r.data.status === 'completed') { clearInterval(t); result.value = { success: true, taskId }; resolve() }
          else if (r.data.status === 'failed') { clearInterval(t); reject(new Error(r.data.error)) }
          else { progress.value.percent = Math.min(95, r.data.progress || progress.value.percent + 0.5); progress.value.message = r.data.status }
        } catch {}
      }, 5000)
    })
  } catch (e) { result.value = { success: false, error: e.message } }
  finally { generating.value = false }
}
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
    <!-- Left: Video Upload -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">上传源视频</h3>
      <input type="file" accept="video/*" @change="handleVideo"
        class="w-full text-xs text-slate-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:text-xs file:bg-pink-500/20 file:text-pink-300 file:border-0"/>
      <div v-if="sourcePreview" class="mt-3 rounded-lg overflow-hidden bg-slate-800">
        <video :src="sourcePreview" class="w-full max-h-40 object-cover" controls/>
      </div>
      <p class="text-[11px] text-slate-500 mt-2">上传一段视频作为动作源，AI 将提取动作并迁移</p>
    </div>

    <!-- Middle: Config -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">迁移配置</h3>
      <div class="space-y-3">
        <div>
          <label class="block text-xs text-slate-400 mb-1">动作描述</label>
          <textarea v-model="actionPrompt" rows="3" placeholder="描述您想要的动作效果..."
            class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm resize-none"/>
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">迁移工作流</label>
          <select v-model="transferWorkflow" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm">
            <option value="">默认工作流</option>
            <option value="runninghub/af_scail.json">AF Scail — Runninghub</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Right: Generate -->
    <div class="glass-card p-5 flex flex-col">
      <h3 class="text-sm font-semibold text-white mb-4">生成视频</h3>
      <button @click="handleGenerate" :disabled="generating || !sourceVideo"
        class="w-full py-3 rounded-xl font-medium text-white text-sm transition-all mb-4"
        :class="generating ? 'bg-slate-700' : 'bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-400 hover:to-rose-400'">
        {{ generating ? '生成中...' : '开始动作迁移' }}
      </button>
      <div v-if="generating" class="mb-4">
        <div class="h-2 rounded-full bg-white/10 overflow-hidden">
          <div class="h-full rounded-full bg-gradient-to-r from-pink-500 to-rose-500 transition-all" :style="{width: progress.percent+'%'}"/>
        </div>
        <p class="text-xs text-slate-400 mt-1">{{ progress.message }}</p>
      </div>
      <div v-if="result?.success" class="text-xs text-emerald-400">生成完成!</div>
      <div v-if="result && !result.success" class="text-xs text-red-400">{{ result.error }}</div>
    </div>
  </div>
</template>
```

## src/components/video-studio/AuditReport.vue

```html
<template>
  <div class="rounded-xl border border-gray-700/50 overflow-hidden" style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);">
    <div class="px-4 py-3 border-b border-gray-700/50 font-medium text-sm text-slate-200 flex items-center justify-between">
      <span>审图报告</span><span :class="scoreColor(props.score)" class="text-lg font-bold">{{ props.score.toFixed(0) }}</span>
    </div>
    <div class="p-4 space-y-2 max-h-64 overflow-y-auto">
      <div v-if="!props.issues || props.issues.length === 0" class="text-xs text-emerald-400 flex items-center gap-1">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
        未发现问题
      </div>
      <div v-for="(issue, i) in props.issues" :key="i" class="flex items-start gap-2 text-xs p-2 rounded-lg"
           :class="issue.severity === 'critical' ? 'bg-red-900/30 text-red-400' : 'bg-yellow-900/30 text-yellow-400'">
        <span class="mt-0.5">{{ issue.severity === 'critical' ? '!' : '?' }}</span>
        <span>{{ issue.description }}</span>
      </div>
    </div>
    <div class="px-4 py-2 border-t border-gray-700/50 text-xs text-slate-500 flex justify-between">
      <span>{{ props.auditor_model }}</span>
      <span :class="props.pass_fail ? 'text-emerald-400' : 'text-red-400'">{{ props.pass_fail ? 'PASS' : 'FAIL' }}</span>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({ score: { type: Number, default: 0 }, pass_fail: { type: Boolean, default: false }, issues: { type: Array, default: () => [] }, auditor_model: { type: String, default: 'gemini-2.5-pro' } })
function scoreColor(s) { if (s >= 85) return 'text-emerald-400'; if (s >= 70) return 'text-yellow-400'; return 'text-red-400' }
</script>
```

## src/components/video-studio/ContentPanel.vue

```html
<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  modelValue: { type: Object, required: true },
  bgmList: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue', 'bgm-upload'])

function updateField(key, value) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

const isFixedMode = computed(() => props.modelValue.mode === 'fixed')

// BGM preview
const bgmPreviewUrl = ref('')
function previewBGM() {
  const bgm = props.modelValue.bgmId
  if (bgm) bgmPreviewUrl.value = `/api/pixelle-proxy/api/files/${encodeURIComponent(bgm)}`
  else bgmPreviewUrl.value = ''
}
</script>

<template>
  <div class="glass-card p-5 h-full flex flex-col">
    <div class="flex items-center gap-2 mb-5">
      <div class="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
        <svg class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
        </svg>
      </div>
      <h3 class="text-sm font-semibold text-white">内容创作</h3>
    </div>

    <div class="flex-1 overflow-y-auto space-y-4">
      <!-- Mode toggle -->
      <div>
        <div class="flex gap-2">
          <button @click="updateField('mode', 'generate')" class="flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all"
            :class="modelValue.mode === 'generate' ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' : 'bg-white/5 text-slate-400 border border-white/10 hover:border-white/20'">
            <div class="text-sm mb-0.5">AI 生成脚本</div><div class="text-[11px] opacity-60">LLM 自动编撰</div>
          </button>
          <button @click="updateField('mode', 'fixed')" class="flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all"
            :class="modelValue.mode === 'fixed' ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30' : 'bg-white/5 text-slate-400 border border-white/10 hover:border-white/20'">
            <div class="text-sm mb-0.5">固定文本</div><div class="text-[11px] opacity-60">使用自定义脚本</div>
          </button>
        </div>
      </div>

      <!-- Text input -->
      <div>
        <label class="block text-xs text-slate-400 mb-1.5">
          {{ isFixedMode ? '视频脚本文本' : '视频主题 / 话题' }}
        </label>
        <textarea
          :value="modelValue.text"
          @input="updateField('text', $event.target.value)"
          :rows="isFixedMode ? 7 : 4"
          maxlength="5000"
          :placeholder="isFixedMode ? '输入完整的视频脚本...' : '输入一个话题或关键词，AI 将自动生成视频脚本。例如：养生茶的5大功效'"
          class="w-full px-3 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-blue-500/50 resize-none"
        />
        <p class="text-[11px] text-slate-500 mt-1">{{ (modelValue.text || '').length }} / 5000</p>
      </div>

      <!-- Title input -->
      <div>
        <label class="block text-xs text-slate-400 mb-1.5">视频标题 <span class="text-slate-500">(可选)</span></label>
        <input
          :value="modelValue.title"
          @input="updateField('title', $event.target.value)"
          type="text" maxlength="200"
          placeholder="留空则自动生成标题"
          class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-blue-500/50"
        />
      </div>

      <!-- Split mode (fixed only) -->
      <div v-if="isFixedMode">
        <label class="block text-xs text-slate-400 mb-1.5">文本拆分方式</label>
        <select :value="modelValue.splitMode" @change="updateField('splitMode', $event.target.value)"
          class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-purple-500/50">
          <option value="paragraph">按段落拆分</option>
          <option value="line">按行拆分</option>
          <option value="sentence">按句子拆分</option>
        </select>
      </div>

      <!-- Scene count -->
      <div>
        <label class="block text-xs text-slate-400 mb-1.5">场景数量: <span class="text-white font-semibold">{{ modelValue.nScenes }}</span></label>
        <input type="range" min="1" max="30" :value="modelValue.nScenes" @input="updateField('nScenes', Number($event.target.value))" class="w-full accent-blue-500"/>
        <div class="flex justify-between text-[11px] text-slate-500 mt-0.5"><span>1</span><span>30</span></div>
      </div>

      <!-- BGM Section -->
      <div class="border-t border-white/5 pt-4">
        <label class="block text-xs text-slate-400 mb-2">背景音乐 (BGM)</label>
        <div class="flex gap-2 mb-3">
          <button v-for="opt in [{v:'none',l:'无'},{v:'builtin',l:'内置'},{v:'custom',l:'自定义'}]" :key="opt.v"
            @click="updateField('bgmMode', opt.v)"
            class="px-3 py-1.5 rounded-lg text-xs transition-all"
            :class="modelValue.bgmMode === opt.v ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' : 'bg-white/5 text-slate-400 border border-white/10'"
          >{{ opt.l }}</button>
        </div>

        <!-- Built-in BGM -->
        <div v-if="modelValue.bgmMode === 'builtin'" class="mb-3">
          <div class="flex gap-2">
            <select :value="modelValue.bgmId" @change="updateField('bgmId', $event.target.value)"
              class="flex-1 px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-blue-500/50">
              <option v-for="bgm in bgmList" :key="bgm.path || bgm.name" :value="bgm.path || bgm.name">{{ bgm.name }}</option>
            </select>
            <button @click="previewBGM" class="px-3 py-2 rounded-lg bg-purple-500/20 text-purple-300 text-xs hover:bg-purple-500/30 transition-colors whitespace-nowrap">试听</button>
          </div>
          <audio v-if="bgmPreviewUrl" :src="bgmPreviewUrl" controls class="mt-2 w-full h-7" controlslist="nodownload"/>
        </div>

        <!-- Custom BGM upload -->
        <div v-if="modelValue.bgmMode === 'custom'" class="mb-3">
          <input type="file" accept=".mp3,.wav" @change="$emit('bgm-upload', $event)"
            class="w-full text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:text-xs file:bg-white/10 file:text-white file:border-0 hover:file:bg-white/20"/>
        </div>

        <!-- Volume -->
        <div v-if="modelValue.bgmMode !== 'none'">
          <label class="block text-xs text-slate-400 mb-1">音量: <span class="text-white font-semibold">{{ modelValue.bgmVolume.toFixed(2) }}</span></label>
          <input type="range" min="0" max="0.5" step="0.01" :value="modelValue.bgmVolume" @input="updateField('bgmVolume', Number($event.target.value))" class="w-full accent-blue-500"/>
        </div>
      </div>
    </div>
  </div>
</template>
```

## src/components/video-studio/CustomMediaPanel.vue

```html
<script setup>
import { ref } from 'vue'
import { generateVideoAsync, getTask } from '../../api/pixelle-client.js'

const emit = defineEmits(['generate-start', 'generate-result'])

// Left: Asset input
const assetFiles = ref([])
const assetPreviews = ref([])
const videoTitle = ref('')
const videoText = ref('')

// Middle: Video config
const ttsVoice = ref('zh-CN-XiaoxiaoNeural')
const mediaWorkflow = ref('')

// BGM
const bgmPath = ref('')
const bgmVolume = ref(0.2)

// Right: Output
const generating = ref(false)
const progress = ref({ percent: 0, message: '' })
const result = ref(null)
const videoUrl = ref('')

function handleFiles(e) {
  const files = Array.from(e.target.files || [])
  assetFiles.value = files
  assetPreviews.value = files.map(f => URL.createObjectURL(f))
}

async function handleGenerate() {
  if (assetFiles.value.length === 0) return
  generating.value = true; result.value = null
  try {
    const payload = {
      text: videoText.value || 'generated video',
      mode: 'generate',
      n_scenes: 1,
      tts_voice: ttsVoice.value,
      bgm_volume: bgmVolume.value,
    }
    if (mediaWorkflow.value) payload.media_workflow = mediaWorkflow.value
    if (bgmPath.value) payload.bgm_path = bgmPath.value

    const resp = await generateVideoAsync(payload)
    const taskId = resp.data?.task_id
    if (!taskId) throw new Error('No task ID')

    // Poll for result
    await new Promise((resolve, reject) => {
      let attempts = 0
      const timer = setInterval(async () => {
        attempts++; if (attempts > 120) { clearInterval(timer); reject(new Error('Timeout')); return }
        try {
          const r = await getTask(taskId)
          if (r.data.status === 'completed') { clearInterval(timer); result.value = { success: true, taskId }; resolve() }
          else if (r.data.status === 'failed') { clearInterval(timer); reject(new Error(r.data.error)) }
          else { progress.value = { percent: Math.min(95, r.data.progress || progress.value.percent + 0.5), message: r.data.status } }
        } catch {}
      }, 5000)
    })
  } catch (e) {
    result.value = { success: false, error: e.message }
  } finally { generating.value = false }
}
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
    <!-- Left: Asset Upload -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">素材上传</h3>
      <div class="mb-4">
        <label class="block text-xs text-slate-400 mb-1.5">选择图片/视频/音频</label>
        <input type="file" multiple accept="image/*,video/*,audio/*" @change="handleFiles"
          class="w-full text-xs text-slate-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:text-xs file:bg-purple-500/20 file:text-purple-300 file:border-0"/>
      </div>
      <div v-if="assetPreviews.length" class="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto">
        <div v-for="(url, i) in assetPreviews" :key="i" class="rounded-lg overflow-hidden bg-slate-800">
          <img v-if="assetFiles[i]?.type?.startsWith('image')" :src="url" class="w-full h-20 object-cover"/>
          <video v-else-if="assetFiles[i]?.type?.startsWith('video')" :src="url" class="w-full h-20 object-cover"/>
          <div v-else class="text-xs text-slate-400 p-2 truncate">{{ assetFiles[i]?.name }}</div>
        </div>
      </div>
      <p class="text-[11px] text-slate-500 mt-2">上传您的素材文件，Pixelle-Video 将基于它们生成视频</p>
    </div>

    <!-- Middle: Config -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">视频配置</h3>
      <div class="space-y-3">
        <div>
          <label class="block text-xs text-slate-400 mb-1">配音角色</label>
          <select v-model="ttsVoice" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm">
            <option value="zh-CN-XiaoxiaoNeural">晓晓 (女)</option>
            <option value="zh-CN-YunxiNeural">云希 (男)</option>
            <option value="zh-CN-XiaoyiNeural">晓伊 (女)</option>
            <option value="zh-CN-YunjianNeural">云健 (男)</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">BGM 音量</label>
          <input type="range" min="0" max="0.5" step="0.01" v-model.number="bgmVolume" class="w-full accent-purple-500"/>
          <span class="text-[11px] text-slate-500">{{ bgmVolume.toFixed(2) }}</span>
        </div>
      </div>
    </div>

    <!-- Right: Generate -->
    <div class="glass-card p-5 flex flex-col">
      <h3 class="text-sm font-semibold text-white mb-4">生成视频</h3>
      <button @click="handleGenerate" :disabled="generating || assetFiles.length === 0"
        class="w-full py-3 rounded-xl font-medium text-white text-sm transition-all mb-4"
        :class="generating ? 'bg-slate-700' : 'bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-400 hover:to-pink-400'">
        {{ generating ? '生成中...' : '生成视频' }}
      </button>
      <div v-if="generating" class="mb-4">
        <div class="h-2 rounded-full bg-white/10 overflow-hidden">
          <div class="h-full rounded-full bg-gradient-to-r from-purple-500 to-pink-500 transition-all" :style="{width: progress.percent+'%'}"/>
        </div>
        <p class="text-xs text-slate-400 mt-1">{{ progress.message }}</p>
      </div>
      <div v-if="result?.success" class="text-xs text-emerald-400">生成完成!</div>
      <div v-if="result && !result.success" class="text-xs text-red-400">{{ result.error }}</div>
    </div>
  </div>
</template>
```

## src/components/video-studio/DigitalHumanPanel.vue

```html
<script setup>
import { ref } from 'vue'
import { generateVideoAsync, getTask } from '../../api/pixelle-client.js'

const characterFiles = ref([])
const goodsFiles = ref([])
const goodsTitle = ref('')
const goodsText = ref('')
const ttsVoice = ref('zh-CN-YunjianNeural')
const ttsSpeed = ref(1.2)
const showAdvanced = ref(false)

const generating = ref(false)
const progress = ref({ percent: 0, message: '' })
const result = ref(null)

function handleCharacters(e) { characterFiles.value = Array.from(e.target.files || []) }
function handleGoods(e) { goodsFiles.value = Array.from(e.target.files || []) }

async function handleGenerate() {
  generating.value = true; result.value = null
  try {
    const payload = {
      text: goodsText.value || goodsTitle.value || 'digital human video',
      mode: 'generate',
      n_scenes: 1,
      tts_voice: ttsVoice.value,
      tts_speed: ttsSpeed.value,
    }
    const resp = await generateVideoAsync(payload)
    const taskId = resp.data?.task_id
    if (!taskId) throw new Error('No task ID')
    await new Promise((resolve, reject) => {
      let a = 0; const t = setInterval(async () => {
        a++; if (a > 120) { clearInterval(t); reject(new Error('Timeout')); return }
        try {
          const r = await getTask(taskId)
          if (r.data.status === 'completed') { clearInterval(t); result.value = { success: true, taskId }; resolve() }
          else if (r.data.status === 'failed') { clearInterval(t); reject(new Error(r.data.error)) }
          else { progress.value.percent = Math.min(95, r.data.progress || progress.value.percent + 0.5); progress.value.message = r.data.status }
        } catch {}
      }, 5000)
    })
  } catch (e) { result.value = { success: false, error: e.message } }
  finally { generating.value = false }
}
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
    <!-- Left: Character Assets -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">数字人角色素材</h3>
      <input type="file" multiple accept="image/*,video/*" @change="handleCharacters"
        class="w-full text-xs text-slate-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:text-xs file:bg-cyan-500/20 file:text-cyan-300 file:border-0"/>
      <p class="text-[11px] text-slate-500 mt-2">上传数字人角色图片或视频</p>
      <div v-if="characterFiles.length" class="mt-2 text-xs text-slate-400">已选 {{ characterFiles.length }} 个文件</div>

      <div class="border-t border-white/5 pt-4 mt-4">
        <h3 class="text-sm font-semibold text-white mb-3">商品素材 <span class="text-slate-500 text-xs">(可选)</span></h3>
        <input type="file" multiple accept="image/*" @change="handleGoods"
          class="w-full text-xs text-slate-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:text-xs file:bg-amber-500/20 file:text-amber-300 file:border-0"/>
        <div class="mt-3 space-y-2">
          <input v-model="goodsTitle" placeholder="商品标题" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm"/>
          <textarea v-model="goodsText" placeholder="商品描述" rows="2" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm resize-none"/>
        </div>
      </div>
    </div>

    <!-- Middle: TTS Config -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">配音设置</h3>
      <div class="space-y-3">
        <div>
          <label class="block text-xs text-slate-400 mb-1">语音角色</label>
          <select v-model="ttsVoice" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm">
            <option value="zh-CN-YunjianNeural">云健 (男) — 推荐</option>
            <option value="zh-CN-YunxiNeural">云希 (男)</option>
            <option value="zh-CN-XiaoxiaoNeural">晓晓 (女)</option>
            <option value="zh-CN-XiaobeiNeural">晓北 (女)</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">语速: {{ ttsSpeed.toFixed(1) }}x</label>
          <input type="range" min="0.5" max="2.0" step="0.1" v-model.number="ttsSpeed" class="w-full accent-cyan-500"/>
        </div>
      </div>
    </div>

    <!-- Right: Generate -->
    <div class="glass-card p-5 flex flex-col">
      <h3 class="text-sm font-semibold text-white mb-4">生成数字人视频</h3>
      <button @click="handleGenerate" :disabled="generating || characterFiles.length === 0"
        class="w-full py-3 rounded-xl font-medium text-white text-sm transition-all mb-4"
        :class="generating ? 'bg-slate-700' : 'bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400'">
        {{ generating ? '生成中...' : '生成数字人视频' }}
      </button>
      <div v-if="generating" class="mb-4">
        <div class="h-2 rounded-full bg-white/10 overflow-hidden">
          <div class="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all" :style="{width: progress.percent+'%'}"/>
        </div>
        <p class="text-xs text-slate-400 mt-1">{{ progress.message }}</p>
      </div>
      <div v-if="result?.success" class="text-xs text-emerald-400">生成完成!</div>
      <div v-if="result && !result.success" class="text-xs text-red-400">{{ result.error }}</div>
    </div>
  </div>
</template>
```

## src/components/video-studio/GeneratePanel.vue

```html
<script setup>
import { computed } from 'vue'

const props = defineProps({
  generating: { type: Boolean, default: false },
  progress: { type: Object, default: () => ({}) },
  result: { type: Object, default: null },
  history: { type: Array, default: () => [] },
  videoUrl: { type: String, default: '' },
  configValid: { type: Boolean, default: false },
})

const emit = defineEmits(['generate', 'download', 'clear-result'])

const progressPercent = computed(() => {
  if (!props.progress) return 0
  return props.progress.percent || 0
})

const progressLabel = computed(() => {
  if (!props.progress) return '准备中...'
  return props.progress.message || props.progress.status || '处理中...'
})

function formatDuration(seconds) {
  if (!seconds) return '-'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

function formatFileSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<template>
  <div class="glass-card p-5 h-full flex flex-col">
    <div class="flex items-center gap-2 mb-5">
      <div class="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
        <svg class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <h3 class="text-sm font-semibold text-white">生成 & 预览</h3>
    </div>

    <!-- Config validation warning -->
    <div v-if="!configValid" class="mb-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300">
      <div class="flex items-start gap-2">
        <svg class="w-4 h-4 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        <span>请先在「系统配置」中填入 LLM API Key 和 RunningHub API Key 后再生成视频</span>
      </div>
    </div>

    <!-- Generate button -->
    <button
      @click="$emit('generate')"
      :disabled="generating"
      class="w-full py-3 rounded-xl font-medium text-white text-sm transition-all mb-4"
      :class="generating
        ? 'bg-slate-700 cursor-not-allowed'
        : 'bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 shadow-lg shadow-emerald-500/20'"
    >
      <span v-if="generating" class="flex items-center justify-center gap-2">
        <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" class="opacity-25" />
          <path stroke-linecap="round" stroke-width="3" d="M12 2a10 10 0 019.95 9" fill="currentColor" />
        </svg>
        生成中...
      </span>
      <span v-else>生成视频</span>
    </button>

    <!-- Progress -->
    <div v-if="generating" class="mb-4">
      <div class="flex justify-between text-xs text-slate-400 mb-1">
        <span>{{ progressLabel }}</span>
        <span>{{ progressPercent }}%</span>
      </div>
      <div class="h-2 rounded-full bg-white/10 overflow-hidden">
        <div
          class="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-all duration-500"
          :style="{ width: progressPercent + '%' }"
        />
      </div>
    </div>

    <!-- Result: Video Preview -->
    <div v-if="result && result.success" class="flex-1 flex flex-col">
      <div class="relative bg-black rounded-lg overflow-hidden mb-3 flex-1 min-h-[200px] flex items-center justify-center">
        <video
          v-if="videoUrl"
          :src="videoUrl"
          controls
          aria-label="视频预览"
          class="w-full max-h-[360px]"
        />
        <div v-else class="text-slate-500 text-sm">视频加载中...</div>
      </div>

      <!-- Info -->
      <div class="space-y-1.5 text-xs">
        <div class="flex justify-between">
          <span class="text-slate-400">时长</span>
          <span class="text-white">{{ formatDuration(result.duration) }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-slate-400">文件大小</span>
          <span class="text-white">{{ formatFileSize(result.fileSize) }}</span>
        </div>
        <div v-if="result.frames" class="flex justify-between">
          <span class="text-slate-400">帧数</span>
          <span class="text-white">{{ result.frames }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-slate-400">任务 ID</span>
          <span class="text-white text-[11px] font-mono">{{ result.taskId }}</span>
        </div>
      </div>

      <!-- Actions -->
      <div class="flex gap-2 mt-3">
        <a
          v-if="videoUrl"
          :href="videoUrl"
          download
          class="flex-1 text-center px-3 py-2 rounded-lg bg-emerald-500/20 text-emerald-300 text-xs hover:bg-emerald-500/30 transition-colors"
        >
          下载视频
        </a>
        <button
          @click="$emit('clear-result')"
          class="px-3 py-2 rounded-lg bg-white/5 text-slate-400 text-xs hover:bg-white/10 transition-colors"
        >
          清除
        </button>
      </div>
    </div>

    <!-- Result: Error -->
    <div v-if="result && !result.success" class="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
      <p class="text-sm text-red-400 font-medium mb-1">生成失败</p>
      <p class="text-xs text-red-300/70">{{ result.error || '未知错误' }}</p>
      <button
        @click="$emit('clear-result')"
        class="mt-2 text-xs text-red-400 hover:text-red-300"
      >清除</button>
    </div>

    <!-- Idle state -->
    <div v-if="!generating && !result" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <svg class="w-12 h-12 mx-auto text-slate-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
        <p class="text-slate-500 text-sm">在左侧填入话题关键词</p>
        <p class="text-slate-600 text-xs mt-1">然后点击「生成视频」</p>
      </div>
    </div>

    <!-- History -->
    <div v-if="history.length > 0" class="border-t border-white/5 pt-3 mt-auto">
      <p class="text-xs text-slate-400 mb-2">生成历史</p>
      <div class="space-y-1.5 max-h-36 overflow-y-auto">
        <div
          v-for="(item, idx) in history" :key="idx"
          class="flex items-center justify-between text-xs px-2 py-1.5 rounded bg-white/[0.02]"
        >
          <span class="text-slate-300 truncate flex-1">{{ item.text || '未命名' }}</span>
          <span
            class="ml-2 px-1.5 py-0.5 rounded text-[11px]"
            :class="item.success
              ? 'bg-emerald-500/15 text-emerald-400'
              : 'bg-red-500/15 text-red-400'"
          >{{ item.success ? '完成' : '失败' }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
```

## src/components/video-studio/ImageToVideoPanel.vue

```html
<script setup>
import { ref } from 'vue'
import { generateVideoAsync, getTask } from '../../api/pixelle-client.js'

const imageFiles = ref([])
const imagePreviews = ref([])
const promptText = ref('')
const mediaWorkflow = ref('')
const videoDuration = ref(5)

const generating = ref(false)
const progress = ref({ percent: 0, message: '' })
const result = ref(null)

function handleImages(e) {
  const files = Array.from(e.target.files || [])
  imageFiles.value = files
  imagePreviews.value = files.map(f => URL.createObjectURL(f))
}

async function handleGenerate() {
  if (imageFiles.value.length === 0) return
  generating.value = true; result.value = null
  try {
    const payload = {
      text: promptText.value || 'animated scene',
      mode: 'generate',
      n_scenes: 1,
    }
    if (mediaWorkflow.value) payload.media_workflow = mediaWorkflow.value
    const resp = await generateVideoAsync(payload)
    const taskId = resp.data?.task_id
    if (!taskId) throw new Error('No task ID')
    await new Promise((resolve, reject) => {
      let a = 0; const t = setInterval(async () => {
        a++; if (a > 120) { clearInterval(t); reject(new Error('Timeout')); return }
        try {
          const r = await getTask(taskId)
          if (r.data.status === 'completed') { clearInterval(t); result.value = { success: true, taskId }; resolve() }
          else if (r.data.status === 'failed') { clearInterval(t); reject(new Error(r.data.error)) }
          else { progress.value.percent = Math.min(95, r.data.progress || progress.value.percent + 0.5); progress.value.message = r.data.status }
        } catch {}
      }, 5000)
    })
  } catch (e) { result.value = { success: false, error: e.message } }
  finally { generating.value = false }
}
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
    <!-- Left: Image Upload -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">上传图片/视频</h3>
      <input type="file" multiple accept="image/*,video/*" @change="handleImages"
        class="w-full text-xs text-slate-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:text-xs file:bg-orange-500/20 file:text-orange-300 file:border-0"/>
      <div v-if="imagePreviews.length" class="grid grid-cols-2 gap-2 mt-3 max-h-40 overflow-y-auto">
        <div v-for="(url, i) in imagePreviews" :key="i" class="rounded-lg overflow-hidden bg-slate-800">
          <img v-if="imageFiles[i]?.type?.startsWith('image')" :src="url" class="w-full h-24 object-cover"/>
          <video v-else :src="url" class="w-full h-24 object-cover"/>
        </div>
      </div>
      <p class="text-[11px] text-slate-500 mt-2">上传静态图片或视频片段，AI 将基于素材生成动态视频</p>
    </div>

    <!-- Middle: Config -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">生成配置</h3>
      <div class="space-y-3">
        <div>
          <label class="block text-xs text-slate-400 mb-1">描述文本</label>
          <textarea v-model="promptText" rows="3" placeholder="描述您想要的视频效果..."
            class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm resize-none"/>
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">视频时长: {{ videoDuration }}s</label>
          <input type="range" min="2" max="15" v-model.number="videoDuration" class="w-full accent-orange-500"/>
        </div>
      </div>
    </div>

    <!-- Right: Generate -->
    <div class="glass-card p-5 flex flex-col">
      <h3 class="text-sm font-semibold text-white mb-4">生成视频</h3>
      <button @click="handleGenerate" :disabled="generating || imageFiles.length === 0"
        class="w-full py-3 rounded-xl font-medium text-white text-sm transition-all mb-4"
        :class="generating ? 'bg-slate-700' : 'bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-400 hover:to-red-400'">
        {{ generating ? '生成中...' : '开始生成' }}
      </button>
      <div v-if="generating" class="mb-4">
        <div class="h-2 rounded-full bg-white/10 overflow-hidden">
          <div class="h-full rounded-full bg-gradient-to-r from-orange-500 to-red-500 transition-all" :style="{width: progress.percent+'%'}"/>
        </div>
        <p class="text-xs text-slate-400 mt-1">{{ progress.message }}</p>
      </div>
      <div v-if="result?.success" class="text-xs text-emerald-400">生成完成!</div>
      <div v-if="result && !result.success" class="text-xs text-red-400">{{ result.error }}</div>
    </div>
  </div>
</template>
```

## src/components/video-studio/ModelRouter.vue

```html
<template>
  <div class="rounded-xl border border-gray-700/50 p-4" style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);">
    <h3 class="text-sm font-semibold text-slate-200 mb-3">模型路由配置</h3>
    <div class="space-y-2">
      <div v-for="m in models" :key="m.id"
           class="flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-all duration-200"
           :class="props.selected === m.id ? 'ring-2 ring-sky-500/50' : 'hover:bg-gray-800/50'"
           style="background: rgba(255,255,255,0.03);"
           @click="$emit('select', m.id)">
        <div class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold" :class="providerColor(m.provider)">{{ m.name?.[0] || '?' }}</div>
        <div class="flex-1">
          <div class="text-sm font-medium text-slate-200">{{ m.name }}</div>
          <div class="text-xs text-slate-500">{{ m.provider }}</div>
        </div>
        <div v-if="props.selected === m.id" class="w-5 h-5 rounded-full bg-sky-500 flex items-center justify-center transition">
          <svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" /></svg>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({ models: { type: Array, default: () => [] }, selected: { type: String, default: '' } })
defineEmits(['select'])
function providerColor(p) { return { volcengine: 'bg-purple-900/40 text-purple-400', kuaishou: 'bg-emerald-900/40 text-emerald-400', runninghub: 'bg-orange-900/40 text-orange-400' }[p] || 'bg-gray-800 text-slate-400' }
</script>
```

## src/components/video-studio/PipelineLayerConfig.vue

```html
<script setup>
import { ref, onMounted } from 'vue'
import { getModelOptions } from '../../api/aiConfig.js'

const props = defineProps({
  modelValue: { type: Object, required: true },
})

const emit = defineEmits(['update:modelValue'])

function setLayer(layer, value) {
  emit('update:modelValue', { ...props.modelValue, [layer]: value })
}

const layers = [
  { key: 'scriptLLM', label: '脚本生成', modelType: 'llm', color: 'sky',
    icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z' },
  { key: 'imageModel', label: '画面生成', modelType: 'image', color: 'emerald',
    icon: 'M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z' },
  { key: 'videoModel', label: '视频渲染', modelType: 'video', color: 'purple',
    icon: 'M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
  { key: 'ttsModel', label: '语音合成', modelType: 'tts', color: 'amber',
    icon: 'M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z' },
  { key: 'auditModel', label: '质量审计', modelType: 'audit', color: 'rose',
    icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
]

const colorMap = {
  sky: { active: 'bg-sky-500/15 text-sky-300 border-sky-500/30', dot: 'bg-sky-400' },
  emerald: { active: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', dot: 'bg-emerald-400' },
  purple: { active: 'bg-purple-500/15 text-purple-300 border-purple-500/30', dot: 'bg-purple-400' },
  amber: { active: 'bg-amber-500/15 text-amber-300 border-amber-500/30', dot: 'bg-amber-400' },
  rose: { active: 'bg-rose-500/15 text-rose-300 border-rose-500/30', dot: 'bg-rose-400' },
}

const modelOptions = ref({})
const loading = ref(true)

onMounted(async () => {
  try {
    const results = await Promise.all(
      layers.map(l => getModelOptions(l.modelType).catch(() => ({ data: { ok: false, options: [] } })))
    )
    layers.forEach((l, i) => {
      const data = results[i].data
      modelOptions.value[l.key] = data.ok ? data.options : []
    })
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="rounded-xl border border-gray-700/50 p-4" style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);">
    <h3 class="text-xs font-medium text-slate-400 mb-3 flex items-center gap-2">
      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"/></svg>
      各环节模型配置
      <span v-if="loading" class="text-slate-600 text-[10px]">加载中...</span>
      <span v-else class="text-slate-600 text-[10px]">— 在系统字典中管理</span>
    </h3>
    <div class="grid grid-cols-5 gap-3">
      <div v-for="layer in layers" :key="layer.key" class="relative">
        <div class="flex items-center gap-1.5 mb-2">
          <div class="w-5 h-5 rounded flex items-center justify-center" :class="colorMap[layer.color].dot" style="--tw-bg-opacity: 0.2;">
            <svg class="w-3 h-3" :class="colorMap[layer.color].dot.replace('bg-', 'text-')" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="layer.icon"/>
            </svg>
          </div>
          <span class="text-xs font-medium text-slate-300">{{ layer.label }}</span>
        </div>

        <div v-if="loading" class="w-full rounded-lg px-2.5 py-2 text-xs bg-gray-800/30 border border-gray-700/30 text-slate-600 animate-pulse">加载中...</div>

        <select
          v-else
          :value="modelValue[layer.key]"
          @change="setLayer(layer.key, $event.target.value)"
          class="layer-select w-full rounded-lg px-2.5 py-2 text-xs bg-gray-800/80 border border-gray-600 text-slate-100 cursor-pointer focus:outline-none focus:ring-2 transition appearance-none"
          :class="`focus:ring-${layer.color}-500/50`"
        >
          <option v-for="opt in (modelOptions[layer.key] || [])" :key="opt.id" :value="opt.id">{{ opt.name }}</option>
        </select>

        <p class="text-[10px] text-slate-500 mt-1 leading-tight truncate">
          {{ ((modelOptions[layer.key] || []).find(o => o.id === modelValue[layer.key]) || {}).provider || '' }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.layer-select {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3E%3Cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3E%3C/svg%3E");
  background-position: right 0.25rem center;
  background-repeat: no-repeat;
  background-size: 1.25em;
}
</style>
```

## src/components/video-studio/PromptDebugger.vue

```html
<template>
  <div class="rounded-xl border border-gray-700 overflow-hidden" style="background: rgba(2, 6, 23, 0.9);">
    <div class="px-4 py-2 border-b border-gray-700/50 flex items-center justify-between">
      <span class="text-xs font-medium text-slate-400 font-mono">Prompt Debugger</span>
      <span class="text-xs text-slate-500">{{ props.entries?.length || 0 }} entries</span>
    </div>
    <div class="divide-y divide-gray-800 max-h-96 overflow-y-auto">
      <div v-for="(entry, i) in props.entries" :key="i" class="p-3">
        <div class="flex items-center gap-2 mb-1">
          <span class="text-xs text-slate-500 font-mono">{{ entry.timestamp }}</span>
          <span class="px-1.5 py-0.5 rounded text-xs font-medium" :class="typeColor(entry.type)">{{ entry.type }}</span>
          <span class="text-xs text-slate-500">{{ entry.model }}</span>
        </div>
        <div class="text-xs text-slate-300 font-mono whitespace-pre-wrap rounded p-2 mt-1" style="background: rgba(255,255,255,0.04);">
          {{ entry.prompt?.slice(0, 500) }}{{ entry.prompt?.length > 500 ? '...' : '' }}
        </div>
        <div v-if="entry.response" class="text-xs text-emerald-400 font-mono mt-1 rounded p-2" style="background: rgba(16, 185, 129, 0.06);">
          {{ entry.response?.slice(0, 300) }}{{ entry.response?.length > 300 ? '...' : '' }}
        </div>
      </div>
      <div v-if="!props.entries || props.entries.length === 0" class="p-6 text-center text-xs text-slate-600">暂无 AI 调用记录</div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({ entries: { type: Array, default: () => [] } })
function typeColor(t) { return { llm: 'bg-sky-900/40 text-sky-400', render: 'bg-purple-900/40 text-purple-400', audit: 'bg-emerald-900/40 text-emerald-400', tts: 'bg-yellow-900/40 text-yellow-400', image: 'bg-orange-900/40 text-orange-400' }[t] || 'bg-gray-800 text-slate-400' }
</script>
```

## src/components/video-studio/SeedancePanel.vue

```html
<script setup>
import { ref } from 'vue'
import { seedanceGenerate, seedanceGetTask } from '../../api/seedance-client.js'

const prompt = ref('')
const aspectRatio = ref('9:16')
const duration = ref(5)
const resolution = ref('720p')
const imageFiles = ref([])
const imagePreviews = ref([])

const generating = ref(false)
const progress = ref({ percent: 0, message: '' })
const result = ref(null)
const videoUrl = ref('')

const ratios = [
  { value: '9:16', label: '竖屏 9:16 (抖音)' },
  { value: '16:9', label: '横屏 16:9' },
  { value: '1:1', label: '方形 1:1' },
  { value: '3:4', label: '3:4' },
  { value: '4:3', label: '4:3' },
]

function handleImages(e) {
  const files = Array.from(e.target.files || [])
  imageFiles.value = files
  imagePreviews.value = files.map(f => URL.createObjectURL(f))
}

async function handleGenerate() {
  if (!prompt.value.trim()) return

  generating.value = true
  result.value = null
  videoUrl.value = ''
  progress.value = { percent: 0, message: '正在提交 Seedance 任务...' }

  try {
    const payload = {
      prompt: prompt.value,
      aspect_ratio: aspectRatio.value,
      duration: duration.value,
      resolution: resolution.value,
      image_urls: [],
    }

    // 如果有上传图片，先占位；实际需上传到可公网访问的 URL 后填入
    // 注：Seedance 的 image_url 需要公网可访问的 URL，后续可扩展上传功能

    const resp = await seedanceGenerate(payload)
    if (!resp.data?.ok) {
      throw new Error(resp.data?.error || '任务提交失败')
    }
    const taskId = resp.data.task_id
    if (!taskId) throw new Error('未获取到任务 ID')

    progress.value.message = 'Seedance 正在生成视频...'
    progress.value.percent = 5

    await new Promise((resolve, reject) => {
      let attempts = 0
      const t = setInterval(async () => {
        attempts++
        if (attempts > 180) { clearInterval(t); reject(new Error('生成超时 (15分钟)')); return }
        try {
          const r = await seedanceGetTask(taskId)
          const d = r.data
          if (d.status === 'succeeded') {
            clearInterval(t)
            videoUrl.value = d.video_url || ''
            result.value = { success: true, taskId }
            progress.value = { percent: 100, message: '生成完成！' }
            resolve()
          } else if (d.status === 'failed') {
            clearInterval(t)
            reject(new Error(d.error || '任务失败'))
          } else {
            const pct = d.progress != null ? Math.min(95, d.progress) : Math.min(95, progress.value.percent + 0.3)
            progress.value = { percent: pct, message: `生成中... (${d.status || 'running'})` }
          }
        } catch { /* 忽略单次轮询错误 */ }
      }, 5000)
    })
  } catch (e) {
    result.value = { success: false, error: e.message }
  } finally {
    generating.value = false
  }
}
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
    <!-- Left: Input -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">创作输入</h3>
      <div class="space-y-3">
        <div>
          <label class="block text-xs text-slate-400 mb-1">视频描述 (Prompt)</label>
          <textarea v-model="prompt" rows="5"
            placeholder="描述你想要的视频内容，支持中文和英文..."
            class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm resize-none"/>
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">参考图片 (可选)</label>
          <input type="file" multiple accept="image/*" @change="handleImages"
            class="w-full text-xs text-slate-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:text-xs file:bg-emerald-500/20 file:text-emerald-300 file:border-0"/>
          <div v-if="imagePreviews.length" class="flex gap-2 mt-2 overflow-x-auto">
            <img v-for="(url, i) in imagePreviews" :key="i" :src="url" class="w-16 h-16 object-cover rounded-lg"/>
          </div>
          <p class="text-[11px] text-slate-500 mt-1">图生视频模式，图片需上传至公网 URL 后填入（后续支持）</p>
        </div>
      </div>
    </div>

    <!-- Middle: Config -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">生成参数</h3>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-slate-400 mb-1">画面比例</label>
          <div class="grid grid-cols-5 gap-1">
            <button v-for="r in ratios" :key="r.value" @click="aspectRatio = r.value"
              class="px-2 py-1.5 rounded text-[11px] font-medium transition-all"
              :class="aspectRatio === r.value ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-white/5 text-slate-400 border border-white/10 hover:border-white/20'">
              {{ r.label }}
            </button>
          </div>
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">时长: {{ duration }}s</label>
          <input type="range" min="4" max="15" v-model.number="duration" class="w-full accent-emerald-500"/>
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">分辨率</label>
          <select v-model="resolution" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm">
            <option value="480p">480p (标清)</option>
            <option value="720p">720p (高清)</option>
            <option value="1080p">1080p (全高清)</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Right: Generate -->
    <div class="glass-card p-5 flex flex-col">
      <h3 class="text-sm font-semibold text-white mb-4">Seedance 2.0 生成</h3>
      <button @click="handleGenerate" :disabled="generating || !prompt.trim()"
        class="w-full py-3 rounded-xl font-medium text-white text-sm transition-all mb-4"
        :class="generating ? 'bg-slate-700' : 'bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400'">
        {{ generating ? '生成中...' : '开始生成' }}
      </button>
      <div v-if="generating" class="mb-4">
        <div class="h-2 rounded-full bg-white/10 overflow-hidden">
          <div class="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-all" :style="{width: progress.percent+'%'}"/>
        </div>
        <p class="text-xs text-slate-400 mt-1">{{ progress.message }}</p>
      </div>
      <div v-if="result?.success" class="mb-4">
        <div class="text-xs text-emerald-400 mb-2">生成完成！</div>
        <video v-if="videoUrl" :src="videoUrl" controls class="w-full rounded-lg" style="max-height:260px"/>
      </div>
      <div v-if="result && !result.success" class="text-xs text-red-400">{{ result.error }}</div>
    </div>
  </div>
</template>
```

## src/components/video-studio/SystemConfigPanel.vue

```html
<script setup>
import { ref } from 'vue'

const props = defineProps({
  modelValue: { type: Object, required: true },
})

const emit = defineEmits(['update:modelValue', 'test-connection'])

const expanded = ref(false)

const llmPresets = [
  { name: 'Qwen Max', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-max' },
  { name: 'GPT-4o', baseUrl: 'https://api.openai.com/v1', model: 'gpt-4o' },
  { name: 'DeepSeek', baseUrl: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  { name: 'Ollama', baseUrl: 'http://localhost:11434/v1', model: 'llama3.2' },
]

function applyLLMPreset(preset) {
  emit('update:modelValue', {
    ...props.modelValue,
    llmBaseUrl: preset.baseUrl,
    llmModel: preset.model,
  })
}

function updateField(key, value) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}
</script>

<template>
  <div class="glass-card mb-4 overflow-hidden">
    <button
      @click="expanded = !expanded"
      :aria-expanded="expanded"
      class="w-full flex items-center justify-between p-4 hover:bg-white/[0.02] transition-colors"
    >
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center">
          <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
        </div>
        <div class="text-left">
          <h3 class="text-sm font-semibold text-white">系统配置</h3>
          <p class="text-xs text-slate-400">LLM · ComfyUI · RunningHub · 默认工作流</p>
        </div>
        <!-- Config status -->
        <div class="flex items-center gap-1.5 ml-auto">
          <span class="w-2 h-2 rounded-full" :class="modelValue.llmApiKey ? 'bg-emerald-400' : 'bg-red-400'" title="LLM 配置状态"/>
          <span class="w-2 h-2 rounded-full" :class="modelValue.runninghubApiKey ? 'bg-emerald-400' : 'bg-amber-400'" title="RunningHub 配置状态"/>
          <span class="text-[10px] text-slate-500 ml-1">{{ (modelValue.llmApiKey && modelValue.runninghubApiKey) ? '已配置' : '未完成' }}</span>
        </div>
      </div>
      <svg class="w-5 h-5 text-slate-400 transition-transform" :class="expanded ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
    </button>

    <div v-show="expanded" class="px-4 pb-4 space-y-5 border-t border-white/5 pt-4">
      <!-- LLM Section -->
      <div>
        <h4 class="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">LLM 配置（脚本生成）</h4>
        <div class="flex flex-wrap gap-2 mb-3">
          <button v-for="p in llmPresets" :key="p.name" @click="applyLLMPreset(p)" class="px-3 py-1.5 rounded-lg text-xs border transition-colors" :class="modelValue.llmModel === p.model ? 'border-cyan-500/50 bg-cyan-500/15 text-cyan-300' : 'border-white/10 bg-white/5 text-slate-400 hover:border-white/20'">{{ p.name }}</button>
        </div>
        <div class="grid grid-cols-3 gap-3">
          <div><label for="sc-llm-apikey" class="block text-[11px] text-slate-400 mb-1">API Key</label><input id="sc-llm-apikey" type="password" :value="modelValue.llmApiKey" @input="updateField('llmApiKey', $event.target.value)" placeholder="sk-..." class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"/></div>
          <div><label for="sc-llm-baseurl" class="block text-[11px] text-slate-400 mb-1">Base URL</label><input id="sc-llm-baseurl" type="text" :value="modelValue.llmBaseUrl" @input="updateField('llmBaseUrl', $event.target.value)" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"/></div>
          <div><label for="sc-llm-model" class="block text-[11px] text-slate-400 mb-1">Model</label><input id="sc-llm-model" type="text" :value="modelValue.llmModel" @input="updateField('llmModel', $event.target.value)" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"/></div>
        </div>
      </div>

      <!-- ComfyUI Section -->
      <div class="border-t border-white/5 pt-4">
        <h4 class="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">ComfyUI & RunningHub</h4>
        <div class="grid grid-cols-2 gap-3">
          <div><label for="sc-comfyui-url" class="block text-[11px] text-slate-400 mb-1">ComfyUI URL</label><input id="sc-comfyui-url" type="text" :value="modelValue.comfyuiUrl" @input="updateField('comfyuiUrl', $event.target.value)" placeholder="http://127.0.0.1:8188" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-purple-500/50"/></div>
          <div><label for="sc-comfyui-key" class="block text-[11px] text-slate-400 mb-1">ComfyUI API Key</label><input id="sc-comfyui-key" type="password" :value="modelValue.comfyuiApiKey" @input="updateField('comfyuiApiKey', $event.target.value)" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-purple-500/50"/></div>
          <div><label for="sc-rh-key" class="block text-[11px] text-slate-400 mb-1">RunningHub API Key</label><input id="sc-rh-key" type="password" :value="modelValue.runninghubApiKey" @input="updateField('runninghubApiKey', $event.target.value)" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-purple-500/50"/></div>
          <div><label for="sc-rh-concurrent" class="block text-[11px] text-slate-400 mb-1">并发限制</label><input id="sc-rh-concurrent" type="number" min="1" max="10" :value="modelValue.runninghubConcurrent" @input="updateField('runninghubConcurrent', Number($event.target.value))" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-purple-500/50"/></div>
        </div>
      </div>

      <!-- Default Workflows -->
      <div class="border-t border-white/5 pt-4">
        <h4 class="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">默认工作流</h4>
        <div class="grid grid-cols-3 gap-3">
          <div><label for="sc-tts-wf" class="block text-[11px] text-slate-400 mb-1">TTS Workflow</label><input id="sc-tts-wf" type="text" :value="modelValue.defaultTtsWorkflow" @input="updateField('defaultTtsWorkflow', $event.target.value)" placeholder="selfhost/tts_edge.json" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"/></div>
          <div><label for="sc-img-wf" class="block text-[11px] text-slate-400 mb-1">Image Workflow</label><input id="sc-img-wf" type="text" :value="modelValue.defaultImageWorkflow" @input="updateField('defaultImageWorkflow', $event.target.value)" placeholder="runninghub/image_flux.json" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"/></div>
          <div><label for="sc-video-wf" class="block text-[11px] text-slate-400 mb-1">Video Workflow</label><input id="sc-video-wf" type="text" :value="modelValue.defaultVideoWorkflow" @input="updateField('defaultVideoWorkflow', $event.target.value)" placeholder="runninghub/video_wan2.1_fusionx.json" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"/></div>
        </div>
      </div>

      <!-- Template custom params -->
      <div class="border-t border-white/5 pt-4">
        <h4 class="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">模板自定义参数</h4>
        <div class="grid grid-cols-3 gap-3">
          <div><label for="sc-tpl-fontsize" class="block text-[11px] text-slate-400 mb-1">Font Size</label><input id="sc-tpl-fontsize" type="text" :value="modelValue.templateFontSize" @input="updateField('templateFontSize', $event.target.value)" placeholder="28px" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"/></div>
          <div><label for="sc-tpl-txtcolor" class="block text-[11px] text-slate-400 mb-1">Text Color</label><input id="sc-tpl-txtcolor" type="text" :value="modelValue.templateTextColor" @input="updateField('templateTextColor', $event.target.value)" placeholder="#ffffff" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"/></div>
          <div><label for="sc-tpl-bgcolor" class="block text-[11px] text-slate-400 mb-1">Background</label><input id="sc-tpl-bgcolor" type="text" :value="modelValue.templateBgColor" @input="updateField('templateBgColor', $event.target.value)" placeholder="#000000" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"/></div>
        </div>
      </div>

      <div class="flex items-center gap-3 pt-2">
        <button @click="$emit('test-connection')" class="px-4 py-2 rounded-lg bg-purple-500/20 text-purple-300 text-xs hover:bg-purple-500/30 transition-colors">测试连接</button>
        <span class="text-xs text-slate-500">配置自动保存到本地浏览器</span>
      </div>
    </div>
  </div>
</template>
```

## src/components/video-studio/VoiceVisualPanel.vue

```html
<script setup>
import { ref } from 'vue'
import { renderFrame, synthesizeTTS, generateImage } from '../../api/pixelle-client.js'

const props = defineProps({
  modelValue: { type: Object, required: true },
  templates: { type: Array, default: () => [] },
  mediaWorkflows: { type: Array, default: () => [] },
  ttsWorkflows: { type: Array, default: () => [] },
  resourcesLoading: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'ref-audio-upload'])

const templateTab = ref('1080x1920')
const templateType = ref('image')

const templateResolutions = [
  { key: '1080x1920', label: '竖屏 9:16 (抖音)' },
  { key: '1920x1080', label: '横屏 16:9' },
  { key: '1080x1080', label: '方形 1:1' },
]
const templateTypes = [
  { key: 'static', label: '静态', hint: '纯文字模板，无需AI配图' },
  { key: 'image', label: '配图', hint: '需要AI生成配图' },
  { key: 'video', label: '视频', hint: '需要AI生成视频画面' },
]

function updateField(key, value) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

const edgeTtsVoices = [
  { id: 'zh-CN-XiaoxiaoNeural', name: '晓晓 (女)', gender: 'female' },
  { id: 'zh-CN-YunxiNeural', name: '云希 (男)', gender: 'male' },
  { id: 'zh-CN-XiaoyiNeural', name: '晓伊 (女)', gender: 'female' },
  { id: 'zh-CN-YunjianNeural', name: '云健 (男)', gender: 'male' },
  { id: 'zh-CN-XiaobeiNeural', name: '晓北 (女)', gender: 'female' },
  { id: 'zh-CN-YunyangNeural', name: '云扬 (男)', gender: 'male' },
  { id: 'zh-CN-XiaohanNeural', name: '晓涵 (女)', gender: 'female' },
  { id: 'en-US-GuyNeural', name: 'Guy (男-英文)', gender: 'male' },
  { id: 'en-US-JennyNeural', name: 'Jenny (女-英文)', gender: 'female' },
]

const ttsEngines = [
  { value: 'edge-tts', label: 'Edge-TTS', desc: '免费在线引擎' },
  { value: 'index-tts', label: 'Index-TTS', desc: '声音克隆' },
  { value: 'spark-tts', label: 'Spark-TTS', desc: '高级合成' },
  { value: 'custom', label: '自定义 ComfyUI', desc: '自托管工作流' },
]

// TTS preview
const showTTSPreview = ref(false)
const ttsPreviewText = ref('大家好，这是一段测试语音。')
const ttsPreviewLoading = ref(false)
const ttsPreviewAudio = ref('')

async function handleTTSPreview() {
  ttsPreviewLoading.value = true
  ttsPreviewAudio.value = ''
  try {
    const resp = await synthesizeTTS({
      text: ttsPreviewText.value,
      mode: props.modelValue.ttsEngine === 'comfyui' ? 'comfyui' : 'edge',
      voice: props.modelValue.ttsVoice,
      speed: props.modelValue.ttsSpeed || 1.0,
    })
    // TTS API returns audio path; build URL through proxy
    const data = resp.data
    if (data.audio_path) {
      const p = (data.audio_path || '').replace(/\\/g, '/')
      const rel = p.replace(/^.*\/Pixelle-Video\//, '')
      ttsPreviewAudio.value = `/api/pixelle-proxy/api/files/${encodeURIComponent(rel)}`
    }
  } catch { /* preview failed */ }
  finally { ttsPreviewLoading.value = false }
}

function getTemplatePreviewUrl(tpl) {
  const key = (tpl.key || tpl.path || tpl.name || '').replace(/\\/g, '/')
  const parts = key.split('/')
  if (parts.length >= 2) {
    const size = parts[0]
    const tplName = parts[1].replace('.html', '')
    const token = localStorage.getItem('token') || ''
    return `/api/pixelle/template-preview/${size}/${tplName}.jpg?token=${encodeURIComponent(token)}`
  }
  return ''
}

function isSelected(tpl) {
  return (props.modelValue.frameTemplate || '') === (tpl.key || tpl.path || tpl.name)
}

function filteredTemplates() {
  let list = props.templates || []
  list = list.filter(t => {
    const key = t.key || t.path || t.name || ''
    return key.includes(templateTab.value)
  })
  if (templateType.value !== 'all') {
    list = list.filter(t => {
      const name = (t.name || t.key || '').toLowerCase()
      return name.includes(templateType.value + '_') || name.startsWith(templateType.value)
    })
  }
  return list
}

// Template preview lightbox
const previewTemplate = ref(null)
const previewImage = ref('')
const previewLoading = ref(false)
const showPreview = ref(false)
const previewRenderText = ref('AI 视频工坊')

function openRenderPreview(tpl) {
  if (tpl) {
    previewTemplate.value = tpl
  } else if (props.modelValue.frameTemplate) {
    previewTemplate.value = (props.templates || []).find(
      t => (t.key || t.path || t.name) === props.modelValue.frameTemplate
    ) || null
  }
  showPreview.value = true
  if (previewTemplate.value) {
    previewImage.value = getTemplatePreviewUrl(previewTemplate.value)
  }
}

async function handlePlaywrightRender() {
  previewLoading.value = true
  try {
    const key = (previewTemplate.value?.key || previewTemplate.value?.path || previewTemplate.value?.name || '')
    const resp = await renderFrame(key, previewRenderText.value || '预览')
    const data = resp.data
    if (data.frame_path) {
      const p = data.frame_path.replace(/\\/g, '/')
      const rel = p.replace(/^.*\/Pixelle-Video\//, '')
      previewImage.value = `/api/pixelle-proxy/api/files/${encodeURIComponent(rel)}`
    }
  } catch { /* keep static preview */ }
  finally { previewLoading.value = false }
}

function closePreview() {
  showPreview.value = false
  previewTemplate.value = null
  previewImage.value = ''
}

function getTemplateSize(tplPath) {
  if (!tplPath) return ''
  const key = tplPath.replace(/\\/g, '/')
  if (key.includes('1080x1920')) return '1080 × 1920 (竖屏 9:16)'
  if (key.includes('1920x1080')) return '1920 × 1080 (横屏 16:9)'
  if (key.includes('1080x1080')) return '1080 × 1080 (方形 1:1)'
  return ''
}

// Media preview
const showMediaPreview = ref(false)
const mediaPreviewLoading = ref(false)
const mediaPreviewUrl = ref('')
const mediaPreviewPrompt = ref('')

async function handleMediaPreview() {
  mediaPreviewLoading.value = true
  mediaPreviewUrl.value = ''
  try {
    const resp = await generateImage({
      prompt: mediaPreviewPrompt.value || 'a beautiful landscape',
      workflow: props.modelValue.mediaWorkflow || undefined,
    })
    const data = resp.data
    if (data.url) {
      mediaPreviewUrl.value = data.url
    } else if (data.image_path) {
      const p = (data.image_path || '').replace(/\\/g, '/')
      const rel = p.replace(/^.*\/Pixelle-Video\//, '')
      mediaPreviewUrl.value = `/api/pixelle-proxy/api/files/${encodeURIComponent(rel)}`
    }
  } catch { mediaPreviewUrl.value = '' }
  finally { mediaPreviewLoading.value = false }
}
</script>

<template>
  <div class="glass-card p-5 h-full overflow-y-auto">
    <div class="flex items-center gap-2 mb-5">
      <div class="w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
        <svg class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"/>
        </svg>
      </div>
      <h3 class="text-sm font-semibold text-white">声音 & 视觉</h3>
    </div>

    <!-- TTS Engine -->
    <div class="mb-5">
      <label class="block text-xs text-slate-400 mb-2">TTS 语音引擎</label>
      <div class="grid grid-cols-2 gap-1.5">
        <button
          v-for="eng in ttsEngines" :key="eng.value"
          @click="updateField('ttsEngine', eng.value)"
          class="text-left px-3 py-2 rounded-lg text-xs transition-all"
          :class="modelValue.ttsEngine === eng.value
            ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
            : 'bg-white/5 text-slate-400 border border-white/10 hover:border-white/20'"
        >
          <div class="font-medium">{{ eng.label }}</div>
          <div class="text-[11px] opacity-60">{{ eng.desc }}</div>
        </button>
      </div>
    </div>

    <!-- Voice selector (Edge-TTS) -->
    <div v-if="modelValue.ttsEngine === 'edge-tts'" class="mb-5">
      <label class="block text-xs text-slate-400 mb-1.5">语音角色</label>
      <select
        :value="modelValue.ttsVoice"
        @change="updateField('ttsVoice', $event.target.value)"
        class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-purple-500/50"
      >
        <option v-for="v in edgeTtsVoices" :key="v.id" :value="v.id">{{ v.name }}</option>
      </select>
      <!-- Speed slider -->
      <label class="block text-xs text-slate-400 mt-3 mb-1">语速: <span class="text-white font-semibold">{{ (modelValue.ttsSpeed || 1.0).toFixed(1) }}x</span></label>
      <input type="range" min="0.5" max="2.0" step="0.1" :value="modelValue.ttsSpeed || 1.0"
        @input="updateField('ttsSpeed', Number($event.target.value))" class="w-full accent-purple-500"/>
    </div>

    <!-- TTS Preview -->
    <div class="mb-5 border-t border-white/5 pt-3">
      <button type="button" @click="showTTSPreview = !showTTSPreview"
        class="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1">
        <svg class="w-3 h-3 transition-transform" :class="showTTSPreview ? 'rotate-90' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
        语音试听
      </button>
      <div v-if="showTTSPreview" class="mt-2 space-y-2">
        <input v-model="ttsPreviewText" type="text" placeholder="输入试听文字..."
          class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder-slate-500"/>
        <button @click="handleTTSPreview" :disabled="ttsPreviewLoading"
          class="w-full px-3 py-2 rounded-lg bg-purple-500/20 text-purple-300 text-xs hover:bg-purple-500/30 disabled:opacity-50">
          {{ ttsPreviewLoading ? '生成中...' : '试听' }}
        </button>
        <audio v-if="ttsPreviewAudio" :src="ttsPreviewAudio" controls class="w-full h-7" controlslist="nodownload"/>
      </div>
    </div>

    <!-- Voice cloning (Index-TTS) -->
    <div v-if="modelValue.ttsEngine === 'index-tts'" class="mb-5">
      <label class="block text-xs text-slate-400 mb-1.5">参考音频（声音克隆）</label>
      <input type="file" accept=".mp3,.wav,.flac" @change="$emit('ref-audio-upload', $event)" class="w-full text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:text-xs file:bg-purple-500/20 file:text-purple-300 file:border-0 hover:file:bg-purple-500/30"/>
      <p class="text-[11px] text-slate-500 mt-1">上传一个人的声音样本（10-30 秒），AI 将模仿其声音</p>
    </div>

    <!-- Custom TTS workflow -->
    <div v-if="modelValue.ttsEngine === 'custom'" class="mb-5">
      <label class="block text-xs text-slate-400 mb-1.5">TTS 工作流路径</label>
      <input
        :value="modelValue.ttsWorkflow"
        @input="updateField('ttsWorkflow', $event.target.value)"
        placeholder="selfhost/tts_edge.json"
        class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-purple-500/50"
      />
    </div>

    <!-- Media Workflow -->
    <div class="mb-5">
      <label class="block text-xs text-slate-400 mb-1.5">画面/视频生成引擎</label>
      <select
        :value="modelValue.mediaWorkflow"
        @change="updateField('mediaWorkflow', $event.target.value)"
        class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-purple-500/50"
      >
        <option value="">使用系统默认</option>
        <option v-for="wf in mediaWorkflows" :key="wf.key" :value="wf.key">
          {{ wf.display_name || wf.name }}
        </option>
      </select>
    </div>

    <!-- Prompt Prefix -->
    <div class="mb-5">
      <label class="block text-xs text-slate-400 mb-1.5">画面风格提示词</label>
      <input
        :value="modelValue.promptPrefix"
        @input="updateField('promptPrefix', $event.target.value)"
        placeholder="例如：极简黑白火柴人风格、中国水墨画风..."
        class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-purple-500/50"
      />
    </div>

    <!-- Media Preview expander -->
    <div class="border-t border-white/5 pt-4 mb-5">
      <button type="button" @click="showMediaPreview = !showMediaPreview"
        class="text-xs text-purple-400 hover:text-purple-300 flex items-center gap-1">
        <svg class="w-3 h-3 transition-transform" :class="showMediaPreview ? 'rotate-90' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
        媒体预览（生成引擎测试）
      </button>
      <div v-if="showMediaPreview" class="mt-2 space-y-2">
        <input v-model="mediaPreviewPrompt" type="text" placeholder="输入测试 prompt..."
          class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder-slate-500"/>
        <button @click="handleMediaPreview" :disabled="mediaPreviewLoading"
          class="w-full px-3 py-2 rounded-lg bg-pink-500/20 text-pink-300 text-xs hover:bg-pink-500/30 disabled:opacity-50">
          {{ mediaPreviewLoading ? '生成中...' : '生成预览' }}
        </button>
        <div v-if="mediaPreviewUrl" class="rounded-lg overflow-hidden bg-slate-900">
          <img v-if="mediaPreviewUrl" :src="mediaPreviewUrl" class="w-full max-h-48 object-contain"/>
        </div>
      </div>
    </div>

    <!-- Template Browser -->
    <div class="border-t border-white/5 pt-4">
      <label class="block text-xs text-slate-400 mb-2">画面模板</label>

      <!-- Type selector -->
      <div class="flex gap-1 mb-2">
        <button
          v-for="t in templateTypes" :key="t.key"
          @click="templateType = t.key"
          class="flex-1 px-2 py-1.5 rounded text-[11px] transition-all"
          :class="templateType === t.key ? 'bg-white/10 text-white' : 'text-slate-500 hover:text-slate-300'"
          :title="t.hint"
        >{{ t.label }}</button>
      </div>

      <!-- Resolution tabs -->
      <div class="flex gap-1 mb-3">
        <button
          v-for="res in templateResolutions" :key="res.key"
          @click="templateTab = res.key"
          class="flex-1 px-2 py-1.5 rounded text-[11px] font-medium transition-all"
          :class="templateTab === res.key ? 'bg-purple-500/20 text-purple-300' : 'bg-white/5 text-slate-400 hover:text-slate-300'"
        >{{ res.label }}</button>
      </div>

      <!-- Template grid with preview images -->
      <div v-if="resourcesLoading" class="text-xs text-slate-500 py-4 text-center">加载资源中...</div>
      <div v-else-if="filteredTemplates().length > 0" class="grid grid-cols-3 gap-2 max-h-72 overflow-y-auto pr-1">
        <div
          v-for="tpl in filteredTemplates()" :key="tpl.key || tpl.path || tpl.name"
          class="group rounded-lg transition-all overflow-hidden cursor-pointer"
          :class="isSelected(tpl) ? 'ring-2 ring-purple-400/60' : 'hover:ring-1 hover:ring-white/20'"
        >
          <!-- Preview image -->
          <div class="relative bg-slate-800 overflow-hidden" style="aspect-ratio: 9/16">
            <!-- Fallback behind image -->
            <div class="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-slate-700 to-slate-900 text-slate-600 z-0">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/>
              </svg>
            </div>
            <!-- Preview image on top -->
            <img
              :src="getTemplatePreviewUrl(tpl)"
              class="absolute inset-0 w-full h-full object-cover z-[1]"
              :alt="tpl.display_name || tpl.name"
              @error="$event.target.style.display='none'"
              @click="openRenderPreview(tpl)"
            />
            <!-- Selected check -->
            <div v-if="isSelected(tpl)" class="absolute top-1 right-1 w-4 h-4 rounded-full bg-purple-500 flex items-center justify-center z-10">
              <svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/>
              </svg>
            </div>
          </div>
          <!-- Name + select button -->
          <div class="px-1.5 py-1">
            <p class="text-[10px] text-slate-400 truncate mb-1">{{ tpl.display_name || tpl.name || tpl.key }}</p>
            <button
              @click="updateField('frameTemplate', tpl.key || tpl.path || tpl.name)"
              class="w-full px-2 py-1 rounded text-[11px] font-medium transition-all"
              :class="isSelected(tpl) ? 'bg-purple-500/20 text-purple-300' : 'bg-white/5 text-slate-400 hover:bg-white/10'"
            >
              {{ isSelected(tpl) ? '已选中' : '选择' }}
            </button>
          </div>
        </div>
      </div>
      <div v-else class="text-xs text-slate-500 py-4 text-center">
        暂无模板
      </div>

      <!-- Selected template info + preview + media size -->
      <div v-if="modelValue.frameTemplate" class="mt-3 p-3 rounded-lg bg-white/[0.02] border border-white/5 space-y-2">
        <div class="flex items-center justify-between">
          <span class="text-xs text-slate-300">已选: <span class="text-white text-[11px]">{{ modelValue.frameTemplate }}</span></span>
          <button @click="openRenderPreview()" class="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
            </svg>
            渲染预览
          </button>
        </div>
        <!-- Media size info -->
        <div class="text-[11px] text-slate-400 flex items-center gap-1">
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"/></svg>
          <span>模板尺寸: <span class="text-slate-300">{{ getTemplateSize(modelValue.frameTemplate) }}</span></span>
        </div>
      </div>
    </div>

    <!-- Render Preview Lightbox -->
    <Teleport to="body">
      <div v-if="showPreview" class="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-sm" @click.self="closePreview">
        <div class="w-full max-w-lg mx-4">
          <div class="flex items-center justify-between mb-3">
            <span class="text-white text-sm font-medium">{{ modelValue.frameTemplate || '模板渲染预览' }}</span>
            <button @click="closePreview" class="text-slate-400 hover:text-white transition-colors">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>
          <div class="space-y-2 mb-3">
            <input v-model="previewRenderText" type="text" placeholder="预览文字..." class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder-slate-500"/>
            <button @click="handlePlaywrightRender" :disabled="previewLoading" class="w-full px-4 py-2 rounded-lg bg-purple-500/20 text-purple-300 text-xs hover:bg-purple-500/30 disabled:opacity-50">
              {{ previewLoading ? '渲染中...' : '重新渲染' }}
            </button>
          </div>
          <div class="rounded-lg overflow-hidden bg-slate-900 flex items-center justify-center min-h-[300px]">
            <div v-if="previewLoading" class="flex items-center gap-2 text-slate-400 py-16">
              <svg class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" class="opacity-25"/>
                <path stroke-linecap="round" stroke-width="3" d="M12 2a10 10 0 019.95 9" fill="currentColor"/>
              </svg>
              <span class="text-sm">正在渲染模板预览...</span>
            </div>
            <img v-else-if="previewImage" :src="previewImage" class="w-full object-contain max-h-[70vh]"/>
            <div v-else class="text-slate-500 text-sm py-16">渲染失败</div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
```

## src/components/ChannelDetail.vue

```html
<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="bg-slate-800 rounded-xl shadow-xl w-full max-w-3xl mx-4 p-6 max-h-[85vh] overflow-y-auto border border-slate-700">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-bold text-white">通道详情</h2>
        <button @click="$emit('close')" class="text-slate-400 hover:text-white text-2xl leading-none">&times;</button>
      </div>

      <!-- Channel Info Card -->
      <div class="bg-slate-700/30 rounded-lg p-4 mb-4 border border-slate-600/30">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold text-slate-300">通道配置</h3>
          <button
            v-if="!editingChannel && canEditChannel"
            @click="startEditChannel"
            class="text-xs px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded transition-colors"
          >编辑</button>
        </div>

        <!-- Display mode -->
        <div v-if="!editingChannel" class="grid grid-cols-2 gap-2 text-sm">
          <div><span class="text-slate-500">分组：</span><span class="text-white">{{ detail.group_name || '-' }}</span></div>
          <div><span class="text-slate-500">模式：</span><span class="text-white">{{ detail.account_mode === 'single_account' ? '单账号' : '轮询' }}</span></div>
          <div><span class="text-slate-500">冷却：</span><span class="text-white">{{ detail.cooldown_seconds }}s</span></div>
          <div><span class="text-slate-500">任务类型：</span><span class="text-white">{{ detail.task_type }}</span></div>
          <div class="col-span-2"><span class="text-slate-500">参数模板：</span><span class="text-slate-400 text-xs">{{ JSON.stringify(detail.params_template) }}</span></div>
        </div>

        <!-- Edit mode -->
        <div v-else class="space-y-3">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="text-xs text-slate-400 block mb-1">分组</label>
              <select v-model="channelForm.group_id" class="w-full bg-slate-800 border border-slate-600 rounded px-3 py-2 text-white text-sm">
                <option value="">不变更</option>
                <option v-for="g in groups" :key="g.id" :value="g.id">{{ g.name }}</option>
              </select>
            </div>
            <div>
              <label class="text-xs text-slate-400 block mb-1">账号模式</label>
              <select v-model="channelForm.account_mode" class="w-full bg-slate-800 border border-slate-600 rounded px-3 py-2 text-white text-sm">
                <option value="">不变更</option>
                <option value="round_robin">轮询</option>
                <option value="single_account">单账号</option>
              </select>
            </div>
            <div>
              <label class="text-xs text-slate-400 block mb-1">账号</label>
              <select v-model="channelForm.account_id" class="w-full bg-slate-800 border border-slate-600 rounded px-3 py-2 text-white text-sm">
                <option value="">不变更</option>
                <option v-for="a in editableAccounts" :key="a.id" :value="a.id">{{ a.nickname || a.id }}</option>
              </select>
            </div>
            <div>
              <label class="text-xs text-slate-400 block mb-1">冷却时间(s)</label>
              <input v-model.number="channelForm.cooldown_seconds" type="number" min="30" max="3600" class="w-full bg-slate-800 border border-slate-600 rounded px-3 py-2 text-white text-sm" />
            </div>
          </div>
          <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
            <input type="checkbox" v-model="channelForm.sync_to_items" class="accent-indigo-600" />
            同步应用到所有待处理和执行中的子项
          </label>
          <div class="flex gap-2">
            <button @click="saveChannel" :disabled="savingChannel" class="text-xs px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded transition-colors disabled:opacity-50">保存</button>
            <button @click="editingChannel = false" class="text-xs px-4 py-1.5 bg-slate-600 hover:bg-slate-500 text-white rounded transition-colors">取消</button>
          </div>
        </div>
      </div>

      <!-- Stats -->
      <div class="grid grid-cols-6 gap-2 mb-4">
        <div class="text-center p-2 bg-slate-700/50 rounded">
          <div class="text-lg font-bold text-white">{{ detail.total }}</div>
          <div class="text-xs text-slate-400">总计</div>
        </div>
        <div class="text-center p-2 bg-yellow-500/10 rounded">
          <div class="text-lg font-bold text-yellow-400">{{ detail.pending }}</div>
          <div class="text-xs text-slate-400">待处理</div>
        </div>
        <div class="text-center p-2 bg-blue-500/10 rounded">
          <div class="text-lg font-bold text-blue-400">{{ detail.assigned }}</div>
          <div class="text-xs text-slate-400">执行中</div>
        </div>
        <div class="text-center p-2 bg-green-500/10 rounded">
          <div class="text-lg font-bold text-green-400">{{ detail.completed }}</div>
          <div class="text-xs text-slate-400">完成</div>
        </div>
        <div class="text-center p-2 bg-red-500/10 rounded">
          <div class="text-lg font-bold text-red-400">{{ detail.failed }}</div>
          <div class="text-xs text-slate-400">失败</div>
        </div>
        <div class="text-center p-2 bg-slate-500/10 rounded">
          <div class="text-lg font-bold text-slate-400">{{ detail.skipped }}</div>
          <div class="text-xs text-slate-400">跳过</div>
        </div>
      </div>

      <!-- Items table -->
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-slate-700">
              <th class="text-left py-2 px-1 w-8">
                <input
                  type="checkbox"
                  :disabled="editableItems.length === 0"
                  :checked="allSelected"
                  @change="toggleSelectAll"
                  class="accent-indigo-600"
                />
              </th>
              <th class="text-left py-2 px-2 text-slate-400 font-medium">关键词</th>
              <th class="text-left py-2 px-2 text-slate-400 font-medium">账号</th>
              <th class="text-left py-2 px-2 text-slate-400 font-medium">状态</th>
              <th class="text-left py-2 px-2 text-slate-400 font-medium">设备</th>
              <th class="text-left py-2 px-2 text-slate-400 font-medium w-12"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in detail.items" :key="item.id" class="border-b border-slate-700/50 hover:bg-slate-700/30">
              <td class="py-2 px-1">
                <input
                  type="checkbox"
                  :disabled="!isItemEditable(item)"
                  :checked="selectedIds.has(item.id)"
                  @change="toggleItem(item.id)"
                  class="accent-indigo-600 disabled:opacity-30"
                />
              </td>
              <td class="py-2 px-2 text-white">{{ item.keyword }}</td>
              <td class="py-2 px-2 text-slate-300">{{ item.account_nickname || item.account_id }}</td>
              <td class="py-2 px-2">
                <span :class="itemStatusClass(item.status)" class="px-2 py-0.5 text-xs rounded-full">
                  {{ itemStatusLabel(item.status) }}
                </span>
              </td>
              <td class="py-2 px-2 text-slate-500">{{ item.device_name || '-' }}</td>
              <td class="py-2 px-1">
                <button
                  v-if="isItemEditable(item)"
                  @click="openItemEdit(item)"
                  class="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
                >编辑</button>
              </td>
            </tr>
            <tr v-if="!detail.items || detail.items.length === 0">
              <td colspan="6" class="py-4 text-center text-slate-500">暂无子项</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Batch toolbar -->
      <div v-if="selectedIds.size > 0" class="mt-4 p-3 bg-indigo-600/10 border border-indigo-500/30 rounded-lg flex items-center justify-between">
        <span class="text-sm text-indigo-300">已选 {{ selectedIds.size }} 项</span>
        <button @click="openBatchEdit" class="text-sm px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded transition-colors">批量编辑</button>
      </div>

      <!-- Item Edit Dialog -->
      <div v-if="editDialog.open" class="fixed inset-0 bg-black/60 flex items-center justify-center z-[60]" @click.self="editDialog.open = false">
        <div class="bg-slate-800 rounded-xl shadow-xl w-full max-w-md mx-4 p-6 border border-slate-700">
          <h3 class="text-base font-bold text-white mb-4">
            {{ editDialog.isBatch ? `批量编辑 (${selectedIds.size} 项)` : '编辑子项' }}
          </h3>
          <div class="space-y-3">
            <div v-if="!editDialog.isBatch">
              <label class="text-xs text-slate-400 block mb-1">关键词</label>
              <input v-model="editDialog.keyword" class="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white text-sm" :placeholder="editDialog.currentKeyword || '不变更'" />
            </div>
            <div>
              <label class="text-xs text-slate-400 block mb-1">账号</label>
              <select v-model="editDialog.account_id" class="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white text-sm">
                <option value="">不变更</option>
                <option v-for="a in editableAccounts" :key="a.id" :value="a.id">{{ a.nickname || a.id }}</option>
              </select>
            </div>
            <div>
              <label class="text-xs text-slate-400 block mb-1">设备</label>
              <select v-model="editDialog.assigned_device_id" class="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white text-sm">
                <option value="">不变更</option>
                <option v-for="d in editableDevices" :key="d.id" :value="d.id">{{ d.name }}</option>
              </select>
            </div>
          </div>
          <div class="flex justify-end gap-2 mt-5">
            <button @click="editDialog.open = false" class="text-sm px-4 py-2 bg-slate-600 hover:bg-slate-500 text-white rounded transition-colors">取消</button>
            <button @click="saveItemEdit" :disabled="savingItem" class="text-sm px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded transition-colors disabled:opacity-50">保存</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { getChannel, editChannelMeta, editChannelItem, batchEditItems } from '../api/channels.js'
import { listAccounts } from '../api/accounts.js'
import { listDevices } from '../api/devices.js'
import { listGroups, listMembers } from '../api/accountGroups.js'

const props = defineProps({ channel: Object })
const emit = defineEmits(['close', 'refresh'])

const detail = ref({ items: [], total: 0, pending: 0, assigned: 0, completed: 0, failed: 0, skipped: 0 })

// Reference data for edit forms
const accounts = ref([])
const devices = ref([])
const groups = ref([])

// Channel edit state
const editingChannel = ref(false)
const savingChannel = ref(false)
const channelForm = ref({})

// Item selection state
const selectedIds = ref(new Set())
const editDialog = ref({ open: false, isBatch: false, itemId: '', currentKeyword: '', keyword: '', account_id: '', assigned_device_id: '' })
const savingItem = ref(false)

const itemStatusLabel = (s) => ({
  pending: '待处理', assigned: '执行中', completed: '已完成', failed: '失败', skipped: '已跳过',
}[s] || s)

const itemStatusClass = (s) => ({
  pending: 'bg-yellow-500/20 text-yellow-400',
  assigned: 'bg-blue-500/20 text-blue-400',
  completed: 'bg-green-500/20 text-green-400',
  failed: 'bg-red-500/20 text-red-400',
  skipped: 'bg-slate-600/50 text-slate-400',
}[s] || 'bg-slate-600/50 text-slate-400')

const canEditChannel = computed(() => {
  return detail.value.status === 'active' || detail.value.status === 'paused'
})

const editableItems = computed(() => {
  return (detail.value.items || []).filter(isItemEditable)
})

const allSelected = computed(() => {
  const items = editableItems.value
  return items.length > 0 && items.every(i => selectedIds.value.has(i.id))
})

const groupMemberIds = ref(new Set())
const membersLoaded = ref(false)

const editableAccounts = computed(() => {
  if (!membersLoaded.value) return accounts.value
  return accounts.value.filter(a => groupMemberIds.value.has(a.id))
})

async function loadMembersForGroup(gid) {
  if (!gid) return
  try {
    const resp = await listMembers(gid)
    const members = resp.data.members || []
    groupMemberIds.value = new Set(members.map(m => m.id))
    membersLoaded.value = true
  } catch (e) {
    console.error('Failed to load members for group:', gid, e)
    // On failure, clear — don't silently show all accounts
    groupMemberIds.value = new Set()
    membersLoaded.value = true
  }
}

// Watch group selector changes → re-fetch members
watch(() => channelForm.value.group_id, async (gid) => {
  if (!gid || !editingChannel.value) return
  await loadMembersForGroup(gid)
})

// Device filtering by bound account
const editableDevices = computed(() => {
  const aid = editDialog.value.account_id
  if (!aid) return devices.value
  return devices.value.filter(d => !d.bound_account_id || d.bound_account_id === aid)
})

function isItemEditable(item) {
  return item.status === 'pending'
}

function toggleItem(id) {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

function toggleSelectAll() {
  if (allSelected.value) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(editableItems.value.map(i => i.id))
  }
}

function startEditChannel() {
  channelForm.value = {
    group_id: '',
    account_mode: '',
    account_id: '',
    cooldown_seconds: detail.value.cooldown_seconds,
    sync_to_items: false,
  }
  editingChannel.value = true
}

async function saveChannel() {
  savingChannel.value = true
  try {
    const payload = {}
    for (const [k, v] of Object.entries(channelForm.value)) {
      if (v !== '' && v !== null && v !== undefined) payload[k] = v
    }
    await editChannelMeta(props.channel.id, payload)
    editingChannel.value = false
    await loadDetail()
    if (detail.value.group_id) await loadMembersForGroup(detail.value.group_id)
    emit('refresh')
  } catch (e) {
    alert('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    savingChannel.value = false
  }
}

function openItemEdit(item) {
  editDialog.value = {
    open: true,
    isBatch: false,
    itemId: item.id,
    currentKeyword: item.keyword,
    keyword: '',
    account_id: '',
    assigned_device_id: '',
  }
}

function openBatchEdit() {
  editDialog.value = {
    open: true,
    isBatch: true,
    itemId: '',
    currentKeyword: '',
    keyword: '',
    account_id: '',
    assigned_device_id: '',
  }
}

async function saveItemEdit() {
  savingItem.value = true
  try {
    if (editDialog.value.isBatch) {
      const payload = { item_ids: [...selectedIds.value] }
      if (editDialog.value.account_id) payload.account_id = editDialog.value.account_id
      if (editDialog.value.assigned_device_id) payload.assigned_device_id = editDialog.value.assigned_device_id
      const resp = await batchEditItems(payload)
      if (resp.data.errors && resp.data.errors.length > 0) {
        alert('部分失败: ' + resp.data.errors.join(', '))
      }
    } else {
      const payload = {}
      if (editDialog.value.keyword) payload.keyword = editDialog.value.keyword
      if (editDialog.value.account_id) payload.account_id = editDialog.value.account_id
      if (editDialog.value.assigned_device_id) payload.assigned_device_id = editDialog.value.assigned_device_id
      await editChannelItem(editDialog.value.itemId, payload)
    }
    editDialog.value.open = false
    selectedIds.value = new Set()
    await loadDetail()
    emit('refresh')
  } catch (e) {
    alert('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    savingItem.value = false
  }
}

async function loadDetail() {
  try {
    const resp = await getChannel(props.channel.id)
    detail.value = resp.data
  } catch (e) {
    console.error('Failed to load channel detail:', e)
  }
}

onMounted(async () => {
  await loadDetail()
  const gid = detail.value.group_id
  try {
    const [accResp, devResp, grpResp] = await Promise.all([
      listAccounts(),
      listDevices(),
      listGroups(),
    ])
    accounts.value = accResp.data.accounts || accResp.data || []
    devices.value = devResp.data.devices || devResp.data || []
    groups.value = grpResp.data.groups || grpResp.data || []
    if (gid) await loadMembersForGroup(gid)
    else membersLoaded.value = true
  } catch (e) {
    console.error('Failed to load ref data:', e)
  }
})
</script>
```

## src/components/ConfirmDialog.vue

```html
<script setup>
import {
  Dialog,
  DialogPanel,
  DialogTitle,
  TransitionRoot,
  TransitionChild,
} from '@headlessui/vue'

defineProps({
  open: { type: Boolean, required: true },
  title: { type: String, default: '确认操作' },
  message: { type: String, default: '确定要执行此操作吗？' },
  confirmText: { type: String, default: '确认' },
  danger: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['confirm', 'cancel'])
</script>

<template>
  <TransitionRoot :show="open" as="template">
    <Dialog as="div" class="relative z-50" @close="loading ? null : emit('cancel')">
      <!-- Backdrop -->
      <TransitionChild
        as="template"
        enter="ease-out duration-200"
        enter-from="opacity-0"
        enter-to="opacity-100"
        leave="ease-in duration-150"
        leave-from="opacity-100"
        leave-to="opacity-0"
      >
        <div class="fixed inset-0 bg-black/60 backdrop-blur-md" />
      </TransitionChild>

      <!-- Panel -->
      <div class="fixed inset-0 overflow-y-auto">
        <div class="flex min-h-full items-center justify-center p-4">
          <TransitionChild
            as="template"
            enter="ease-out duration-300"
            enter-from="opacity-0 scale-90 -translate-y-4"
            enter-to="opacity-100 scale-100 translate-y-0"
            leave="ease-in duration-200"
            leave-from="opacity-100 scale-100 translate-y-0"
            leave-to="opacity-0 scale-90 -translate-y-4"
          >
            <DialogPanel
              :class="[
                'relative overflow-hidden w-full max-w-md p-6 rounded-2xl border backdrop-blur-xl',
                danger
                  ? 'bg-slate-900/95 border-red-500/20 shadow-2xl shadow-red-500/10'
                  : 'bg-slate-900/95 border-white/10 shadow-2xl shadow-purple-500/10',
              ]"
            >
              <!-- Background glow orb -->
              <div
                :class="[
                  'absolute -top-12 -right-12 w-40 h-40 rounded-full blur-3xl pointer-events-none transition-colors duration-500',
                  danger ? 'bg-red-500/15' : 'bg-purple-500/15',
                ]"
              />
              <div
                :class="[
                  'absolute -bottom-12 -left-12 w-32 h-32 rounded-full blur-3xl pointer-events-none transition-colors duration-500',
                  danger ? 'bg-orange-500/10' : 'bg-cyan-500/10',
                ]"
              />

              <div class="relative">
                <!-- Icon + Title -->
                <div class="flex items-center gap-4">
                  <!-- Animated icon ring -->
                  <div
                    :class="[
                      'relative flex-shrink-0 w-12 h-12 rounded-2xl flex items-center justify-center',
                      danger
                        ? 'bg-red-500/10 border border-red-500/20'
                        : 'bg-purple-500/10 border border-purple-500/20',
                    ]"
                  >
                    <!-- Outer pulse ring -->
                    <span
                      :class="[
                        'absolute inset-0 rounded-2xl animate-ping opacity-30',
                        danger ? 'bg-red-500/20' : 'bg-purple-500/20',
                      ]"
                      style="animation-duration: 2s"
                    />
                    <!-- Danger: exclamation triangle -->
                    <svg v-if="danger" class="relative w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                    </svg>
                    <!-- Normal: question mark -->
                    <svg v-else class="relative w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>

                  <DialogTitle class="text-lg font-semibold text-white leading-tight">
                    {{ title }}
                  </DialogTitle>
                </div>

                <!-- Message -->
                <p class="mt-4 pl-[56px] text-sm text-slate-400 leading-relaxed">
                  {{ message }}
                </p>

                <!-- Divider -->
                <div class="mt-5 mb-5 border-t border-white/5" />

                <!-- Buttons -->
                <div class="flex justify-end gap-3">
                  <button
                    type="button"
                    :disabled="loading"
                    class="px-5 py-2.5 text-sm font-medium text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-xl transition-all duration-200 disabled:opacity-50"
                    @click="emit('cancel')"
                  >
                    取消
                  </button>
                  <button
                    type="button"
                    :disabled="loading"
                    :class="[
                      'relative px-5 py-2.5 text-sm font-semibold text-white rounded-xl transition-all duration-200',
                      'hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98]',
                      'disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0',
                      danger
                        ? 'bg-gradient-to-r from-red-600 to-rose-500 hover:from-red-500 hover:to-rose-400 shadow-lg shadow-red-500/30 hover:shadow-red-500/40'
                        : 'bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 shadow-lg shadow-purple-500/30 hover:shadow-purple-500/40',
                    ]"
                    @click="emit('confirm')"
                  >
                    <!-- Loading spinner -->
                    <span v-if="loading" class="flex items-center gap-2">
                      <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      处理中...
                    </span>
                    <span v-else>{{ confirmText }}</span>
                  </button>
                </div>
              </div>
            </DialogPanel>
          </TransitionChild>
        </div>
      </div>
    </Dialog>
  </TransitionRoot>
</template>
```

## src/components/CreateChannelDialog.vue

```html
<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="bg-slate-800 rounded-xl shadow-xl w-full max-w-lg mx-4 p-6 border border-slate-700">
      <h2 class="text-lg font-bold text-white mb-4">创建通道</h2>
      <form @submit.prevent="submit">
        <!-- Group select -->
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-300 mb-1">账号分组</label>
          <select v-model="form.group_id" class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500">
            <option value="" disabled>选择分组</option>
            <option v-for="g in groups" :key="g.id" :value="g.id">{{ g.name }}</option>
          </select>
        </div>

        <!-- Task type -->
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-300 mb-1">任务类型</label>
          <select v-model="form.task_type" class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500">
            <option value="search_comment">评论搜索</option>
            <option value="search_like">点赞搜索</option>
            <option value="search_dm">私信搜索</option>
            <option value="reply_comment">回复评论</option>
          </select>
        </div>

        <!-- Account mode -->
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-300 mb-1">账号模式</label>
          <select v-model="form.account_mode" class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500">
            <option value="round_robin">分摊（轮转）</option>
            <option value="single_account">单账号</option>
          </select>
        </div>

        <!-- Single account select -->
        <div v-if="form.account_mode === 'single_account'" class="mb-4">
          <label class="block text-sm font-medium text-slate-300 mb-1">指定账号</label>
          <select v-model="form.account_id" class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500">
            <option value="" disabled>选择账号</option>
            <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.nickname }}</option>
          </select>
        </div>

        <!-- Keywords -->
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-300 mb-1">种子关键词（每行一个）</label>
          <div class="flex gap-2 mb-2">
            <input
              v-model="seedKeyword"
              class="flex-1 bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-blue-500"
              placeholder="输入主题词，如：美食探店"
              @keydown.enter.prevent="expandKeywords"
            />
            <button
              type="button"
              @click="expandKeywords"
              :disabled="keywordGenerating"
              class="px-3 py-2 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-500 disabled:opacity-50 transition-colors whitespace-nowrap"
            >
              {{ keywordGenerating ? '生成中...' : 'AI 扩展' }}
            </button>
          </div>
          <textarea
            v-model="keywordsText"
            rows="4"
            class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            placeholder="种子关键词 + AI 扩展词&#10;每行一个关键词&#10;也可手动编辑"
          />
        </div>

        <!-- Common params -->
        <div class="grid grid-cols-2 gap-3 mb-4">
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-1">处理数量</label>
            <input
              v-model.number="formParams.count"
              type="number"
              min="-1"
              class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
            />
          </div>
          <div v-if="['reply_comment', 'search_comment', 'collect'].includes(form.task_type)">
            <label class="block text-sm font-medium text-slate-300 mb-1">处理视频数 <span class="text-slate-500 text-xs">-1=全量</span></label>
            <input
              v-model.number="formParams.video_count"
              type="number"
              min="-1"
              class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        <!-- 评论最大天数（reply_comment / search_comment / collect 共用） -->
        <template v-if="['reply_comment', 'search_comment', 'collect'].includes(form.task_type)">
          <div class="grid grid-cols-2 gap-3 mb-4">
            <div>
              <label class="block text-sm font-medium text-slate-300 mb-1">评论最大天数 <span class="text-slate-500 text-xs">-1=不限</span></label>
              <input
                v-model.number="formParams.max_age_days"
                type="number"
                min="-1"
                class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-300 mb-1">排序方式</label>
              <select v-model="formParams.sort_by" class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500">
                <option value="">默认</option>
                <option value="latest">最新发布</option>
                <option value="most_liked">最多点赞</option>
              </select>
            </div>
          </div>
        </template>

        <!-- DM sequence -->
        <div v-if="['search_dm', 'reply_comment'].includes(form.task_type) && dmSequences.length > 0" class="mb-4">
          <label class="block text-sm font-medium text-slate-300 mb-1">DM 序列模板（可选）</label>
          <select v-model="dmSequenceId" class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500">
            <option value="">不使用序列</option>
            <option v-for="seq in dmSequences" :key="seq.id" :value="seq.id">{{ seq.name }} ({{ seq.message_count }}条)</option>
          </select>
        </div>

        <!-- DM / comment content -->
        <div v-if="['search_comment', 'search_dm', 'reply_comment'].includes(form.task_type)" class="mb-4">
          <label class="block text-sm font-medium text-slate-300 mb-1">
            {{ form.task_type === 'search_dm' ? '私信' : '评论/私信' }}内容（可选）
          </label>
          <textarea
            v-model="formParams.content"
            rows="2"
            maxlength="500"
            :disabled="!!dmSequenceId"
            class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-blue-500 disabled:opacity-50"
            :placeholder="dmSequenceId ? '已选择DM序列模板，此处内容将被忽略' : (form.task_type === 'reply_comment' ? '留空则 AI 生成回复和私信' : '留空则 AI 自动生成')"
          />
        </div>

        <!-- Params template (JSON) for advanced -->
        <details class="mb-4">
          <summary class="text-sm text-slate-400 cursor-pointer hover:text-slate-300">高级参数 (JSON)</summary>
          <textarea
            v-model="paramsText"
            rows="2"
            class="mt-2 w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 font-mono text-sm focus:outline-none focus:border-blue-500"
            placeholder='{"count": 5}'
          />
        </details>

        <!-- Error -->
        <p v-if="error" class="text-red-400 text-sm mb-4">{{ error }}</p>

        <!-- Actions -->
        <div class="flex justify-end gap-3">
          <button type="button" @click="$emit('close')" class="px-4 py-2 text-slate-400 hover:text-white transition-colors">取消</button>
          <button type="submit" :disabled="submitting" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
            {{ submitting ? '创建中...' : '创建' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { createChannel } from '../api/channels.js'
import { listGroups, listMembers } from '../api/accountGroups.js'
import { generateKeywords } from '../api/content.js'
import { listDMSequences } from '../api/dmSequences.js'

const emit = defineEmits(['close', 'created'])

const groups = ref([])
const accounts = ref([])
const form = ref({
  group_id: '',
  task_type: 'search_comment',
  account_mode: 'round_robin',
  account_id: '',
})
const keywordsText = ref('')
const seedKeyword = ref('')
const keywordGenerating = ref(false)
const paramsText = ref('{}')
const formParams = ref({
  count: 10,
  video_count: 5,
  max_age_days: 5,
  sort_by: '',
  content: '',
})
const dmSequenceId = ref('')
const dmSequences = ref([])
const error = ref('')
const submitting = ref(false)

onMounted(async () => {
  try {
    const resp = await listGroups()
    groups.value = resp.data.groups || resp.data || []
  } catch (e) {
    console.error('Failed to load groups:', e)
  }
  try { var sr = await listDMSequences(); dmSequences.value = sr.data.sequences || [] } catch (e) {}
})

// Load group members when group changes
watch(() => form.value.group_id, async (gid) => {
  if (!gid) return
  try {
    const resp = await listMembers(gid, { status: 'active' })
    accounts.value = resp.data.members || resp.data || []
  } catch (e) {
    console.error('Failed to load group members:', e)
  }
})

async function expandKeywords() {
  var seed = seedKeyword.value.trim()
  if (!seed) return
  keywordGenerating.value = true
  try {
    var resp = await generateKeywords(seed, 10)
    var newKeywords = resp.data.keywords || []
    // 合并种子关键词和 AI 扩展词，去重
    var existing = keywordsText.value.split('\n').map(function (k) { return k.trim() }).filter(Boolean)
    var seedWords = seed.split(/[,，\s]+/).filter(Boolean)
    var all = seedWords.slice()
    for (var i = 0; i < newKeywords.length; i++) {
      var kw = newKeywords[i].trim()
      if (all.indexOf(kw) === -1) all.push(kw)
    }
    // 追加已有手动输入的关键词（不在种子词和扩展词中的）
    for (var j = 0; j < existing.length; j++) {
      if (all.indexOf(existing[j]) === -1) all.push(existing[j])
    }
    keywordsText.value = all.join('\n')
    seedKeyword.value = ''
  } catch (e) {
    console.error('AI keyword expansion failed:', e)
  } finally {
    keywordGenerating.value = false
  }
}

async function submit() {
  error.value = ''
  const keywords = keywordsText.value.split('\n').map(k => k.trim()).filter(Boolean)
  if (keywords.length === 0) {
    error.value = '请至少输入一个关键词'
    return
  }

  let params = {}
  try {
    params = JSON.parse(paramsText.value || '{}')
  } catch {
    error.value = '参数模板 JSON 格式错误'
    return
  }

  // 合并表单参数（JSON 优先级更高）
  var fp = formParams.value
  var merged = {
    count: params.count !== undefined ? params.count : fp.count,
    content: params.content !== undefined ? params.content : (fp.content || undefined),
    dm_sequence_id: dmSequenceId.value || undefined,
  }
  if (['reply_comment', 'search_comment', 'collect'].includes(form.value.task_type)) {
    merged.video_count = params.video_count !== undefined ? params.video_count : fp.video_count
  }
  if (['reply_comment', 'search_comment', 'collect'].includes(form.value.task_type)) {
    merged.max_age_days = params.max_age_days !== undefined ? params.max_age_days : fp.max_age_days
    if (fp.sort_by) merged.sort_by = params.sort_by || fp.sort_by
  }
  // 其他 JSON 参数
  Object.keys(params).forEach(function (k) {
    if (merged[k] === undefined) merged[k] = params[k]
  })

  submitting.value = true
  try {
    await createChannel({
      ...form.value,
      keywords,
      params_template: merged,
    })
    emit('created')
  } catch (e) {
    error.value = e.response?.data?.detail || '创建失败'
  } finally {
    submitting.value = false
  }
}
</script>
```

## src/components/DataTable.vue

```html
<script setup>
import LoadingSpinner from './LoadingSpinner.vue'
import EmptyState from './EmptyState.vue'

const props = defineProps({
  columns: {
    type: Array,
    required: true,
  },
  data: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  total: {
    type: Number,
    default: 0,
  },
  page: {
    type: Number,
    default: 1,
  },
  pageSize: {
    type: Number,
    default: 10,
  },
})

const emit = defineEmits(['page-change'])

const totalPages = () => Math.ceil(props.total / props.pageSize)

const goToPage = (p) => {
  if (p >= 1 && p <= totalPages()) {
    emit('page-change', p)
  }
}
</script>

<template>
  <div class="glass-card overflow-hidden rounded-xl">
    <!-- Loading state -->
    <LoadingSpinner v-if="loading" />

    <!-- Empty state -->
    <EmptyState v-else-if="!data || data.length === 0" />

    <!-- Table -->
    <template v-else>
      <div class="overflow-x-auto">
        <table class="min-w-full">
          <thead>
            <tr>
              <th
                v-for="col in columns"
                :key="col.key"
                scope="col"
                class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider"
                :class="col.headerClass"
              >
                <slot :name="`header-${col.key}`" :col="col">
                  {{ col.label }}
                </slot>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, rowIndex) in data" :key="rowIndex" class="hover:bg-white/[0.03] transition-colors">
              <td
                v-for="col in columns"
                :key="col.key"
                class="whitespace-nowrap px-6 py-4 text-sm"
                :class="col.cellClass"
              >
                <slot :name="`cell-${col.key}`" :row="row" :value="row[col.key]">
                  {{ row[col.key] }}
                </slot>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination footer -->
      <div
        v-if="total > pageSize"
        class="flex items-center justify-between border-t border-white/5 px-6 py-3"
      >
        <p class="text-sm text-slate-400">
          共 <span class="font-medium text-slate-300">{{ total }}</span> 条，第
          <span class="font-medium text-slate-300">{{ page }}</span> / {{ totalPages() }} 页
        </p>
        <div class="flex gap-1">
          <button
            :disabled="page <= 1"
            class="rounded-lg border border-white/10 bg-white/5 px-3 py-1 text-sm text-slate-300 hover:bg-white/10 transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
            @click="goToPage(page - 1)"
          >
            上一页
          </button>
          <button
            :disabled="page >= totalPages()"
            class="rounded-lg border border-white/10 bg-white/5 px-3 py-1 text-sm text-slate-300 hover:bg-white/10 transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
            @click="goToPage(page + 1)"
          >
            下一页
          </button>
        </div>
      </div>
    </template>
  </div>
</template>
```

## src/components/EmptyState.vue

```html
<script setup>
defineProps({
  message: {
    type: String,
    default: '暂无数据',
  },
})
</script>

<template>
  <div class="flex flex-col items-center justify-center py-16 text-slate-400">
    <div class="relative mb-4">
      <div class="absolute inset-0 rounded-full blur-xl opacity-20" style="background: var(--accent-glow-soft);"></div>
      <svg
        class="h-14 w-14 relative opacity-40"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="1.2"
          d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
        />
      </svg>
    </div>
    <p class="text-sm text-slate-500">{{ message }}</p>
  </div>
</template>
```

## src/components/LoadingSpinner.vue

```html
<script setup>
</script>

<template>
  <div class="flex items-center justify-center py-12">
    <svg
      class="animate-spin h-8 w-8 text-cyan-400"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        class="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        stroke-width="4"
      />
      <path
        class="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  </div>
</template>
```

## src/components/StatusBadge.vue

```html
<script setup>
defineProps({
  status: {
    type: String,
    required: true,
  },
})

const badgeClassMap = {
  active: 'badge-success',
  online: 'badge-success',
  offline: 'badge-info',
  pending: 'badge-warning',
  running: 'badge-info',
  completed: 'badge-success',
  failed: 'badge-danger',
  cancelled: 'badge-info',
  risk_controlled: 'badge-danger',
  disabled: 'badge-info',
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

const titleMap = {
  active: '账号状态正常，可执行任务',
  online: '设备当前在线，可执行任务',
  offline: '设备当前离线，无法执行任务',
  pending: '排队中等待设备执行的任务',
  running: '正在设备上执行的任务',
  completed: '已成功完成的任务',
  failed: '执行出错的任务，可查看详情或重试',
  cancelled: '被手动取消的任务',
  risk_controlled: '账号触发抖音平台风控，暂停任务执行',
  disabled: '手动禁用的账号，不会分配任何任务',
}
</script>

<template>
  <span
    :class="badgeClassMap[status] || 'badge-info'"
    :title="titleMap[status] || ''"
    class="inline-flex items-center"
  >
    {{ labelMap[status] || status }}
  </span>
</template>
```

## src/components/StrategyCard.vue

```html
<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  strategy: { type: Object, required: true },
  index: { type: Number, required: true },
  totalCount: { type: Number, required: true },
  actionName: { type: String, default: '' },
  resolutionProfile: { type: String, default: 'default' },
  purpose: { type: String, default: 'locate' },
})

const emit = defineEmits(['update', 'delete', 'move-up', 'move-down'])

const STRATEGY_TYPES = [
  { value: 'text', label: '文本', placeholder: '例如：赞', fields: 'value' },
  { value: 'id', label: '资源 ID', placeholder: 'com.ss.android.ugc.aweme:id/like_btn', fields: 'value', mono: true },
  { value: 'desc', label: '描述', placeholder: '元素描述文字', fields: 'value' },
  { value: 'className', label: '类名', placeholder: 'android.widget.TextView', fields: 'value', mono: true },
  { value: 'package', label: '包名', placeholder: 'com.ss.android.ugc.aweme', fields: 'value', mono: true },
  { value: 'coordinate', label: '坐标', fields: 'xy' },
  { value: 'image', label: '图片匹配', fields: 'image' },
  { value: 'chain', label: '链式查找', fields: 'chain' },
]

const CONDITION_TYPES = [
  { value: 'text', label: '文本', placeholder: '例如：评论' },
  { value: 'id', label: '资源 ID', placeholder: 'com.ss.android.ugc.aweme:id/title' },
  { value: 'desc', label: '描述', placeholder: '例如：按钮' },
  { value: 'className', label: '类名', placeholder: 'android.widget.TextView' },
]

const showAdvanced = ref(false)

const isMultiCondition = computed(() =>
  !!(props.strategy.conditions && props.strategy.conditions.length > 0)
)

const isLocate = computed(() => props.purpose !== 'extract')

const typeConfig = computed(() =>
  STRATEGY_TYPES.find(t => t.value === props.strategy.type) || STRATEGY_TYPES[0]
)

const canHaveMatchMode = computed(() =>
  ['text', 'id', 'desc', 'className'].includes(props.strategy.type) && !isMultiCondition.value
)

function updateField(key, value) {
  emit('update', { ...props.strategy, [key]: value })
}

function onTypeChange(newType) {
  const base = { type: newType }
  if (newType === 'coordinate') {
    base.x_percent = props.strategy.x_percent || 0.5
    base.y_percent = props.strategy.y_percent || 0.5
  } else if (newType === 'chain') {
    base.steps = props.strategy.steps || [{ type: 'text', value: '' }]
  } else if (newType === 'image') {
    base.template = props.strategy.template || ''
    base.threshold = props.strategy.threshold || 0.8
  } else {
    base.value = props.strategy.value || ''
  }
  emit('update', base)
}

// --- Multi-condition helpers ---

function toggleConditionMode() {
  if (isMultiCondition.value) {
    const first = props.strategy.conditions[0]
    const { conditions, logic, ...rest } = props.strategy
    rest.type = first.type || 'text'
    rest.value = first.value || ''
    rest.match_mode = first.match_mode || 'exact'
    emit('update', rest)
  } else {
    const firstCond = {
      type: props.strategy.type || 'text',
      value: props.strategy.value || '',
      match_mode: props.strategy.match_mode || 'exact',
    }
    const { match_mode, value, type, ...rest } = props.strategy
    rest.conditions = [firstCond]
    rest.logic = 'and'
    emit('update', rest)
  }
}

function setLogic(val) {
  emit('update', { ...props.strategy, logic: val })
}

function addCondition() {
  const conds = [...(props.strategy.conditions || []), { type: 'text', value: '', match_mode: 'exact' }]
  emit('update', { ...props.strategy, conditions: conds })
}

function removeCondition(index) {
  const conds = props.strategy.conditions.filter((_, i) => i !== index)
  if (conds.length === 0) {
    toggleConditionMode()
    return
  }
  emit('update', { ...props.strategy, conditions: conds })
}

function updateCondition(index, key, value) {
  const conds = props.strategy.conditions.map((c, i) =>
    i === index ? { ...c, [key]: value } : c
  )
  emit('update', { ...props.strategy, conditions: conds })
}

function onCondTypeChange(index, newType) {
  const conds = props.strategy.conditions.map((c, i) =>
    i === index ? { type: newType, value: '', match_mode: 'exact' } : c
  )
  emit('update', { ...props.strategy, conditions: conds })
}

function addStep() {
  const steps = [...(props.strategy.steps || []), { type: 'text', value: '' }]
  emit('update', { ...props.strategy, steps })
}
function addNavStep(nav) {
  const step = nav === 'parent' ? { nav: 'parent' } : { nav, type: 'text', value: '' }
  const steps = [...(props.strategy.steps || []), step]
  emit('update', { ...props.strategy, steps })
}
function removeStep(index) {
  const steps = props.strategy.steps.filter((_, i) => i !== index)
  emit('update', { ...props.strategy, steps })
}
function updateStep(index, key, value) {
  const steps = props.strategy.steps.map((s, i) =>
    i === index ? { ...s, [key]: value } : s
  )
  emit('update', { ...props.strategy, steps })
}

async function onImageFileSelect(e) {
  const file = e.target.files?.[0]
  if (!file) return
  const { uploadTemplate } = await import('../api/selectors.js')
  try {
    const res = await uploadTemplate(file, props.actionName || 'template', props.resolutionProfile || 'default')
    updateField('template', res.data.filename)
  } catch (err) {
    alert('上传失败: ' + (err.response?.data?.detail || err.message))
  }
  e.target.value = ''
}
</script>

<template>
  <div class="glass-card p-4 border border-white/10 hover:border-white/20 transition-colors">
    <!-- Header: handle + number + type + delete -->
    <div class="flex items-center gap-3 mb-3">
      <!-- Reorder arrows -->
      <div class="flex flex-col gap-0.5">
        <button
          type="button"
          :disabled="index === 0"
          class="text-slate-500 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
          @click="$emit('move-up')"
          title="上移（提高优先级）"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" /></svg>
        </button>
        <button
          type="button"
          :disabled="index === totalCount - 1"
          class="text-slate-500 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
          @click="$emit('move-down')"
          title="下移（降低优先级）"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" /></svg>
        </button>
      </div>

      <!-- Priority number -->
      <span class="text-xs font-mono text-slate-500 w-6 text-center">#{{ index + 1 }}</span>

      <!-- Type selector (hidden in multi-condition mode) -->
      <select
        v-if="!isMultiCondition"
        :value="strategy.type"
        @change="onTypeChange($event.target.value)"
        class="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-slate-200 focus:border-purple-500/50 focus:outline-none"
      >
        <option v-for="t in STRATEGY_TYPES" :key="t.value" :value="t.value">
          {{ t.label }}
        </option>
      </select>

      <!-- Spacer -->
      <div class="flex-1"></div>

      <!-- Delete -->
      <button
        type="button"
        class="text-slate-500 hover:text-red-400 transition-colors"
        @click="$emit('delete')"
        title="删除此策略"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
      </button>
    </div>

    <!-- Fields based on type -->
    <div class="space-y-2">
      <!-- text / id / desc / className / package: single value input -->
      <div v-if="typeConfig.fields === 'value' && !isMultiCondition">
        <label class="text-xs text-slate-400 mb-1 block">查找值</label>
        <input
          :value="strategy.value"
          @input="updateField('value', $event.target.value)"
          :placeholder="typeConfig.placeholder"
          :class="[
            'w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none',
            typeConfig.mono && 'font-mono',
          ]"
        />
      </div>

      <!-- match_mode dropdown (single-condition text/id/desc/className only) -->
      <div v-if="canHaveMatchMode" class="mt-2">
        <label class="text-xs text-slate-400 mb-1 block">匹配模式</label>
        <select
          :value="strategy.match_mode || 'exact'"
          @change="updateField('match_mode', $event.target.value)"
          class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 focus:border-purple-500/50 focus:outline-none"
        >
          <option value="exact">精确匹配</option>
          <option value="contains">包含</option>
        </select>
      </div>

            <!-- click_mode dropdown (hidden for extract purpose) -->
      <div v-if="isLocate && (canHaveMatchMode || ['text','id','desc','className','package','image'].includes(strategy.type) || isMultiCondition)" class="mt-2">
        <label class="text-xs text-slate-400 mb-1 block">点击方式</label>
        <select
          :value="strategy.click_mode || 'click'"
          @change="updateField('click_mode', $event.target.value)"
          class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 focus:border-purple-500/50 focus:outline-none"
        >
          <option value="click">普通点击 (click)</option>
          <option value="press">按压 (press)</option>
        </select>
      </div>

            <!-- press_duration (shown when click_mode=press) -->
      <div v-if="strategy.click_mode === 'press'" class="mt-2">
        <label class="text-xs text-slate-400 mb-1 block">按压时长 (ms)</label>
        <input
          type="number"
          min="50"
          max="1000"
          :value="strategy.press_duration || 150"
          @input="updateField('press_duration', Number($event.target.value) || 150)"
          class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 focus:border-purple-500/50 focus:outline-none"
        />
      </div>

      <!-- Toggle: single <-> multi condition -->
      <div v-if="['text','id','desc','className'].includes(strategy.type) || isMultiCondition" class="mt-2">
        <button
          type="button"
          class="text-xs text-purple-400 hover:text-purple-300 transition-colors"
          @click="toggleConditionMode"
        >
          {{ isMultiCondition ? '← 切换为单条件' : '→ 切换为多条件组合（AND/OR）' }}
        </button>
      </div>

      <!-- Multi-condition mode -->
      <div v-if="isMultiCondition" class="mt-3 space-y-3">
        <!-- AND/OR toggle -->
        <div class="flex items-center gap-2">
          <span class="text-xs text-slate-400">逻辑关系：</span>
          <button
            type="button"
            :class="(strategy.logic || 'and') === 'and'
              ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30'
              : 'text-slate-500 hover:text-slate-300 border-transparent'"
            class="px-3 py-1 text-xs font-medium rounded-lg border transition-colors"
            @click="setLogic('and')"
          >
            并且 (AND)
          </button>
          <button
            type="button"
            :class="(strategy.logic || 'and') === 'or'
              ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
              : 'text-slate-500 hover:text-slate-300 border-transparent'"
            class="px-3 py-1 text-xs font-medium rounded-lg border transition-colors"
            @click="setLogic('or')"
          >
            或者 (OR)
          </button>
        </div>

        <!-- Condition rows -->
        <div
          v-for="(cond, ci) in strategy.conditions"
          :key="ci"
          class="p-3 rounded-lg border border-white/10 bg-white/[0.03] space-y-2"
        >
          <div class="flex items-center gap-2">
            <span class="text-xs text-slate-500 font-mono w-5">#{{ ci + 1 }}</span>
            <select
              :value="cond.type"
              @change="onCondTypeChange(ci, $event.target.value)"
              class="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-xs text-slate-200 focus:border-purple-500/50 focus:outline-none"
            >
              <option v-for="ct in CONDITION_TYPES" :key="ct.value" :value="ct.value">
                {{ ct.label }}
              </option>
            </select>
            <button
              type="button"
              class="ml-auto text-slate-500 hover:text-red-400 transition-colors"
              @click="removeCondition(ci)"
              title="删除此条件"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          </div>
          <input
            :value="cond.value"
            @input="updateCondition(ci, 'value', $event.target.value)"
            :placeholder="CONDITION_TYPES.find(ct => ct.value === cond.type)?.placeholder || ''"
            class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none"
          />
          <select
            :value="cond.match_mode || 'exact'"
            @change="updateCondition(ci, 'match_mode', $event.target.value)"
            class="w-full rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-xs text-slate-200 focus:border-purple-500/50 focus:outline-none"
          >
            <option value="exact">精确匹配</option>
            <option value="contains">包含</option>
          </select>
        </div>

        <button
          type="button"
          class="w-full py-2 border border-dashed border-white/20 rounded-lg text-sm text-slate-400 hover:text-purple-300 hover:border-purple-500/30 transition-colors"
          @click="addCondition"
        >
          + 添加条件
        </button>
      </div>

            <!-- chain: step builder -->
      <div v-if="typeConfig.fields === 'chain'" class="space-y-2">
        <div class="flex items-center justify-between">
          <label class="text-xs text-slate-400">链式步骤</label>
          <span class="text-xs text-slate-500">filter=同元素 | parent=父 | child=子[0] | sibling=兄弟[0] （[0]内为索引，0=第1个）</span>
        </div>
        <div
          v-for="(step, si) in (strategy.steps || [])"
          :key="si"
          class="space-y-1.5 p-2 rounded-lg border border-white/10 bg-white/[0.03]"
        >
          <div class="flex items-center gap-2">
            <span class="text-xs text-slate-500 font-mono w-5">#{{ si + 1 }}</span>
            <!-- nav mode -->
            <select
              :value="step.nav || 'filter'"
              @change="updateStep(si, 'nav', $event.target.value)"
              class="rounded-lg border border-white/10 px-2 py-1 text-xs focus:border-purple-500/50 focus:outline-none"
              :class="(step.nav || 'filter') === 'parent' ? 'bg-amber-500/10 text-amber-300' : (step.nav || 'filter') === 'child' ? 'bg-emerald-500/10 text-emerald-300' : (step.nav || 'filter') === 'sibling' ? 'bg-cyan-500/10 text-cyan-300' : 'bg-white/5 text-slate-200'"
            >
              <option value="filter">filter 过滤</option>
              <option value="parent">parent 父节点</option>
              <option value="child">child 子节点</option>
              <option value="sibling">sibling 兄弟节点</option>
            </select>
            <!-- type + value (hidden for parent nav) -->
            <template v-if="(step.nav || 'filter') !== 'parent'">
              <select
                :value="step.type"
                @change="updateStep(si, 'type', $event.target.value)"
                class="rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-xs text-slate-200 focus:border-purple-500/50 focus:outline-none"
              >
                <option value="className">类名</option>
                <option value="id">资源 ID</option>
                <option value="text">文本</option>
                <option value="desc">描述</option>
                <option value="classNameContains">类名包含</option>
                <option value="idContains">ID 包含</option>
                <option value="textContains">文本包含</option>
                <option value="descContains">描述包含</option>
              </select>
              <input
                :value="step.value"
                @input="updateStep(si, 'value', $event.target.value)"
                placeholder="值"
                class="flex-1 rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-xs text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none font-mono"
              />
              <input
                v-if="(step.nav || 'filter') === 'child' || (step.nav || 'filter') === 'sibling'"
                type="number" min="0"
                :value="step.index || 0"
                @input="updateStep(si, 'index', Number($event.target.value))"
                class="w-12 rounded-lg border border-white/10 bg-white/5 px-1 py-1 text-xs text-slate-200 text-center" placeholder="#"
                title="索引从0开始：0=第1个, 1=第2个, 2=第3个..."
              />
            </template>
            <span v-else class="flex-1 text-xs text-slate-500">不需要参数</span>
          </div>
          <button type="button" class="w-full text-xs text-slate-500 hover:text-red-400" @click="removeStep(si)">删除此步骤</button>
        </div>
        <div class="flex gap-2">
          <button type="button" class="flex-1 py-1.5 border border-dashed border-white/20 rounded-lg text-xs text-slate-400 hover:text-purple-300" @click="addStep">
            + filter 步骤
          </button>
          <button type="button" class="px-3 py-1.5 border border-dashed border-amber-500/20 rounded-lg text-xs text-amber-400 hover:text-amber-300" @click="addNavStep('parent')">
            + 父节点
          </button>
          <button type="button" class="px-3 py-1.5 border border-dashed border-cyan-500/20 rounded-lg text-xs text-cyan-400 hover:text-cyan-300" @click="addNavStep('sibling')">
            + 兄弟
          </button>
          <button type="button" class="px-3 py-1.5 border border-dashed border-emerald-500/20 rounded-lg text-xs text-emerald-400 hover:text-emerald-300" @click="addNavStep('child')">
            + 子节点
          </button>
        </div>
      </div>

      <!-- coordinate: x + y inputs (0-1 比例) -->
      <div v-else-if="typeConfig.fields === 'xy'" class="flex gap-3">
        <div class="flex-1">
          <label class="text-xs text-slate-400 mb-1 block">X 比例 (0-1)</label>
          <input
            type="number"
            min="0"
            max="1"
            step="0.01"
            :value="strategy.x_percent"
            @input="updateField('x_percent', Number($event.target.value))"
            placeholder="0.5"
            class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none"
          />
        </div>
        <div class="flex-1">
          <label class="text-xs text-slate-400 mb-1 block">Y 比例 (0-1)</label>
          <input
            type="number"
            min="0"
            max="1"
            step="0.01"
            :value="strategy.y_percent"
            @input="updateField('y_percent', Number($event.target.value))"
            placeholder="0.5"
            class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none"
          />
        </div>
      </div>

      <!-- image: template + threshold -->
      <div v-else-if="typeConfig.fields === 'image'" class="space-y-2">
        <div>
          <label class="text-xs text-slate-400 mb-1 block">模板图片</label>
          <div class="flex gap-2">
            <input
              :value="strategy.template"
              @input="updateField('template', $event.target.value)"
              placeholder="文件名，例如 like_btn.png"
              class="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 font-mono focus:border-purple-500/50 focus:outline-none"
            />
            <label class="btn-aurora rounded-lg px-3 py-2 text-sm font-medium cursor-pointer whitespace-nowrap">
              <span class="relative z-10">选择文件</span>
              <input
                type="file"
                accept=".png,.jpg,.jpeg"
                class="hidden"
                @change="onImageFileSelect"
              />
            </label>
          </div>
        </div>
        <div>
          <label class="text-xs text-slate-400 mb-1 block">
            匹配阈值: {{ (strategy.threshold || 0.8).toFixed(2) }}
          </label>
          <input
            type="range"
            min="0.5"
            max="1"
            step="0.05"
            :value="strategy.threshold || 0.8"
            @input="updateField('threshold', Number($event.target.value))"
            class="w-full accent-purple-500"
          />
          <div class="flex justify-between text-xs text-slate-600">
            <span>0.5（宽松）</span>
            <span>1.0（精确）</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Advanced: x/y offset (for non-coordinate types) -->
    <div v-if="typeConfig.fields !== 'xy'" class="mt-2">
      <button
        type="button"
        class="text-xs text-slate-500 hover:text-slate-300 flex items-center gap-1"
        @click="showAdvanced = !showAdvanced"
      >
        <svg
          class="w-3 h-3 transition-transform"
          :class="{ 'rotate-90': showAdvanced }"
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        ><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" /></svg>
        点击位置偏移
      </button>
      <div v-if="showAdvanced" class="mt-2 space-y-2">
        <p class="text-xs text-slate-500 leading-relaxed">
          相对控件<strong class="text-slate-400">中心点</strong>的偏移量，按<strong class="text-slate-400">控件自身宽高百分比</strong>计算，不受分辨率影响。<br/>
          不填=点中心 &middot; 正数=右/下 &middot; 负数=左/上 &middot; 例如填 <code class="text-purple-400">150</code> 向右偏移 1.5 倍控件宽
        </p>
        <div class="flex gap-3">
          <div class="flex-1">
            <label class="text-xs text-slate-400 mb-1 block">水平偏移 %</label>
            <input
              type="number"
              :value="strategy.x_percent"
              @input="updateField('x_percent', $event.target.value !== '' ? Number($event.target.value) : undefined)"
              placeholder="0"
              class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none"
            />
          </div>
          <div class="flex-1">
            <label class="text-xs text-slate-400 mb-1 block">垂直偏移 %</label>
            <input
              type="number"
              :value="strategy.y_percent"
              @input="updateField('y_percent', $event.target.value !== '' ? Number($event.target.value) : undefined)"
              placeholder="0"
              class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
```

## src/components/TipIcon.vue

```html
<script setup>
defineProps({
  text: { type: String, default: '' },
  width: { type: String, default: 'w-72' },
})
</script>

<template>
  <span class="group relative inline-flex items-center">
    <svg
      class="w-4 h-4 text-slate-500 cursor-help hover:text-slate-400 transition-colors"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <circle cx="12" cy="12" r="10" stroke-width="2" />
      <path stroke-linecap="round" d="M12 16v-4m0-4h.01" stroke-width="2" />
    </svg>
    <span
      :class="[
        width,
        'invisible group-hover:visible absolute z-50 left-6 top-0 p-3 text-xs font-normal text-slate-300 bg-slate-800/95 backdrop-blur-sm border border-white/10 rounded-lg shadow-xl leading-relaxed whitespace-pre-line',
      ]"
    >
      <slot>{{ text }}</slot>
    </span>
  </span>
</template>
```

## src/components/ToastNotification.vue

```html
<script setup>
import { useToastStore } from '../stores/toast.js'

const toast = useToastStore()

const typeStyles = {
  error: {
    bg: 'bg-red-500/15 border-red-500/30',
    icon: 'text-red-400',
    iconPath: 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  },
  warning: {
    bg: 'bg-amber-500/15 border-amber-500/30',
    icon: 'text-amber-400',
    iconPath: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z',
  },
  success: {
    bg: 'bg-emerald-500/15 border-emerald-500/30',
    icon: 'text-emerald-400',
    iconPath: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  },
  info: {
    bg: 'bg-cyan-500/15 border-cyan-500/30',
    icon: 'text-cyan-400',
    iconPath: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  },
}
</script>

<template>
  <div class="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
    <TransitionGroup
      enter-active-class="transition-all duration-300 ease-out"
      enter-from-class="translate-x-full opacity-0"
      enter-to-class="translate-x-0 opacity-100"
      leave-active-class="transition-all duration-200 ease-in"
      leave-from-class="translate-x-0 opacity-100"
      leave-to-class="translate-x-full opacity-0"
    >
      <div
        v-for="t in toast.toasts"
        :key="t.id"
        :class="[
          typeStyles[t.type]?.bg || typeStyles.error.bg,
          'pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl border backdrop-blur-xl shadow-lg max-w-sm',
        ]"
      >
        <svg
          class="w-5 h-5 flex-shrink-0 mt-0.5"
          :class="typeStyles[t.type]?.icon || typeStyles.error.icon"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            :d="typeStyles[t.type]?.iconPath || typeStyles.error.iconPath"
          />
        </svg>
        <p class="text-sm text-slate-200 flex-1">{{ t.message }}</p>
        <button
          class="text-slate-500 hover:text-slate-300 transition-colors flex-shrink-0"
          @click="toast.removeToast(t.id)"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>
```

## src/views/AccountGroupsPage.vue

```html
<script setup>
import { ref, reactive, onMounted } from 'vue'
import {
  Dialog,
  DialogPanel,
  DialogTitle,
  TransitionRoot,
  TransitionChild,
} from '@headlessui/vue'
import DataTable from '../components/DataTable.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import TipIcon from '../components/TipIcon.vue'
import {
  listGroups,
  createGroup,
  updateGroup,
  deleteGroup,
  listMembers,
  addMembers,
  removeMembers,
} from '../api/accountGroups.js'
import { listAccounts } from '../api/accounts.js'
import { formatDate } from '../utils/format.js'
import { useToastStore } from '../stores/toast.js'
import { useWebSocket } from '../composables/useWebSocket.js'

// --- Data state ---
const groups = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

// --- Form / Dialog state ---
const showFormDialog = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const formError = ref(null)

const defaultForm = {
  name: '',
  description: '',
}
const form = reactive({ ...defaultForm })
const editingId = ref(null)

// --- Delete confirmation state ---
const showDeleteDialog = ref(false)
const deletingGroup = ref(false)
const deleting = ref(false)

// --- Member management state ---
const showMembersDialog = ref(false)
const managingGroupId = ref(null)
const managingGroupName = ref('')
const members = ref([])
const membersLoading = ref(false)
const allAccounts = ref([])
const selectedAccountIds = ref([])

// --- Page-level error ---
const pageError = ref(null)
const toast = useToastStore()

// --- WebSocket ---
function wsUrl() {
  const token = localStorage.getItem('token') || ''
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/api/devices/ws/pair-events?token=${encodeURIComponent(token)}`
}
useWebSocket(wsUrl, {
  onMessage(msg) {
    if (msg.event === 'account_groups_changed') fetchGroups()
  },
})

// --- Table columns ---
const columns = [
  { key: 'name', label: '分组名称' },
  { key: 'description', label: '描述' },
  { key: 'member_count', label: '成员数' },
  { key: 'created_at', label: '创建时间' },
  { key: 'actions', label: '操作', headerClass: 'text-right', cellClass: 'text-right' },
]

// --- Fetch groups ---
async function fetchGroups() {
  loading.value = true
  try {
    const skip = (page.value - 1) * pageSize
    const res = await listGroups({ skip, limit: pageSize })
    groups.value = res.data.groups || []
    total.value = res.data.total || 0
  } catch (e) {
    toast.error('加载分组列表失败')
    groups.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handlePageChange(p) {
  page.value = p
  fetchGroups()
}

// --- Open create dialog ---
function openCreateDialog() {
  isEditing.value = false
  editingId.value = null
  Object.assign(form, defaultForm)
  formError.value = null
  showFormDialog.value = true
}

// --- Open edit dialog ---
function openEditDialog(group) {
  isEditing.value = true
  editingId.value = group.id
  form.name = group.name || ''
  form.description = group.description || ''
  formError.value = null
  showFormDialog.value = true
}

// --- Save (create or update) ---
async function handleSave() {
  if (!form.name.trim()) {
    formError.value = '分组名称不能为空'
    return
  }

  saving.value = true
  formError.value = null

  const payload = {
    name: form.name.trim(),
    description: form.description.trim(),
  }

  try {
    if (isEditing.value) {
      await updateGroup(editingId.value, payload)
    } else {
      await createGroup(payload)
    }
    showFormDialog.value = false
    fetchGroups()
  } catch (e) {
    formError.value =
      e.response?.data?.message ||
      e.response?.data?.detail ||
      '保存失败，请重试'
  } finally {
    saving.value = false
  }
}

// --- Delete ---
function openDeleteDialog(group) {
  deletingGroup.value = group
  showDeleteDialog.value = true
}

async function handleDelete() {
  if (!deletingGroup.value) return
  deleting.value = true
  try {
    await deleteGroup(deletingGroup.value.id)
    showDeleteDialog.value = false
    deletingGroup.value = null
    if (groups.value.length === 1 && page.value > 1) {
      page.value--
    }
    fetchGroups()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '删除失败，请重试'
  } finally {
    deleting.value = false
  }
}

// --- Member management ---
async function openMembersDialog(group) {
  managingGroupId.value = group.id
  managingGroupName.value = group.name
  showMembersDialog.value = true
  selectedAccountIds.value = []
  await Promise.all([fetchMembers(group.id), fetchAllAccounts()])
}

async function fetchMembers(groupId) {
  membersLoading.value = true
  try {
    const res = await listMembers(groupId)
    members.value = res.data.members || []
  } catch (e) {
    toast.error('加载成员列表失败')
    members.value = []
  } finally {
    membersLoading.value = false
  }
}

async function fetchAllAccounts() {
  try {
    const res = await listAccounts({ limit: 200 })
    allAccounts.value = res.data.accounts || []
  } catch (e) {
    toast.error('加载账号列表失败')
    allAccounts.value = []
  }
}

// Available accounts = all active accounts not already in the group
const availableAccounts = ref([])

function updateAvailableAccounts() {
  const memberIds = new Set(members.value.map(m => m.id))
  availableAccounts.value = allAccounts.value.filter(
    a => a.status === 'active' && !memberIds.has(a.id)
  )
}

async function handleAddMembers() {
  if (selectedAccountIds.value.length === 0) return
  try {
    await addMembers(managingGroupId.value, selectedAccountIds.value)
    selectedAccountIds.value = []
    await fetchMembers(managingGroupId.value)
    fetchGroups() // refresh member count
  } catch (e) {
    pageError.value = e.response?.data?.detail || '添加成员失败'
  }
}

async function handleRemoveMember(accountId) {
  try {
    await removeMembers(managingGroupId.value, [accountId])
    await fetchMembers(managingGroupId.value)
    fetchGroups() // refresh member count
  } catch (e) {
    pageError.value = e.response?.data?.detail || '移除成员失败'
  }
}

// Watch members change to update available accounts
import { watch } from 'vue'
watch(members, updateAvailableAccounts, { immediate: true })

// --- Init ---
onMounted(fetchGroups)
</script>

<template>
  <div>
    <!-- Page error banner -->
    <div v-if="pageError" class="mb-4 glass-card border-red-500/30 text-red-400 rounded-xl px-4 py-3 flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-400 hover:text-red-300 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white flex items-center gap-1.5">账号分组<TipIcon text="将账号分组管理，方便批量创建链实例和统计" /></h1>
      <button
        class="btn-aurora inline-flex items-center px-4 py-2 text-sm font-medium rounded-xl"
        @click="openCreateDialog"
      >
        <span class="relative z-10 inline-flex items-center">
          <svg class="-ml-1 mr-2 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" />
          </svg>
          创建分组
        </span>
      </button>
    </div>

    <!-- Data Table -->
    <DataTable
      :columns="columns"
      :data="groups"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      @page-change="handlePageChange"
    >
      <template #cell-member_count="{ value }">
        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium badge-info">
          {{ value }} 人
        </span>
      </template>

      <template #cell-created_at="{ value }">
        {{ formatDate(value) }}
      </template>

      <template #cell-actions="{ row }">
        <div class="flex justify-end gap-2">
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-emerald-400 hover:text-emerald-300 hover:bg-emerald-400/10 rounded transition-colors"
            @click="openMembersDialog(row)"
          >
            成员管理
          </button>
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-cyan-400 hover:text-cyan-300 hover:bg-cyan-400/10 rounded transition-colors"
            @click="openEditDialog(row)"
          >
            编辑
          </button>
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-400/10 rounded transition-colors"
            @click="openDeleteDialog(row)"
          >
            删除
          </button>
        </div>
      </template>
    </DataTable>

    <!-- Create / Edit Dialog -->
    <TransitionRoot :show="showFormDialog" as="template">
      <Dialog as="div" class="relative z-50" @close="showFormDialog = false">
        <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-lg glass-card p-6 gradient-border">
                <DialogTitle class="text-lg font-medium text-white">
                  {{ isEditing ? '编辑分组' : '创建分组' }}
                </DialogTitle>
                <div v-if="formError" class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-3 py-2 rounded-lg">
                  {{ formError }}
                </div>
                <form class="mt-4 space-y-4" @submit.prevent="handleSave">
                  <div>
                    <label class="block text-sm font-medium text-slate-300">分组名称 <span class="text-red-400">*</span></label>
                    <input v-model="form.name" type="text" required class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="请输入分组名称" />
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-slate-300">描述</label>
                    <textarea v-model="form.description" rows="3" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="请输入分组描述"></textarea>
                  </div>
                  <div class="flex justify-end gap-3 pt-2">
                    <button type="button" class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors" @click="showFormDialog = false">取消</button>
                    <button type="submit" :disabled="saving" class="btn-aurora rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed">
                      <span class="relative z-10">{{ saving ? '保存中...' : '保存' }}</span>
                    </button>
                  </div>
                </form>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>

    <!-- Members Management Dialog -->
    <TransitionRoot :show="showMembersDialog" as="template">
      <Dialog as="div" class="relative z-50" @close="showMembersDialog = false">
        <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-2xl glass-card p-6 gradient-border">
                <DialogTitle class="text-lg font-medium text-white">
                  成员管理 — {{ managingGroupName }}
                </DialogTitle>

                <div class="mt-4 grid grid-cols-2 gap-4">
                  <!-- Left: Available accounts -->
                  <div>
                    <h3 class="text-sm font-medium text-slate-300 mb-2 flex items-center gap-1.5">可选账号<TipIcon text="状态为'正常'且尚未加入此分组的账号，勾选后点击添加选中加入分组" /></h3>
                    <div class="border border-white/10 rounded-lg p-3 h-64 overflow-y-auto">
                      <div v-if="availableAccounts.length === 0" class="text-sm text-slate-500 text-center py-4">
                        暂无可选账号
                      </div>
                      <label
                        v-for="account in availableAccounts"
                        :key="account.id"
                        class="flex items-center gap-2 py-1 px-2 hover:bg-white/5 rounded cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          :value="account.id"
                          v-model="selectedAccountIds"
                          class="rounded border-white/10 text-cyan-400 focus:ring-cyan-500"
                        />
                        <span class="text-sm text-slate-300">{{ account.nickname || account.douyin_id || account.id }}</span>
                      </label>
                    </div>
                    <button
                      v-if="selectedAccountIds.length > 0"
                      class="btn-aurora mt-2 w-full inline-flex items-center justify-center px-3 py-2 text-sm font-medium rounded-lg"
                      @click="handleAddMembers"
                    >
                      <span class="relative z-10">添加选中 ({{ selectedAccountIds.length }})</span>
                    </button>
                  </div>

                  <!-- Right: Current members -->
                  <div>
                    <h3 class="text-sm font-medium text-slate-300 mb-2 flex items-center gap-1.5">当前成员 ({{ members.length }})<TipIcon text="已加入此分组的账号。非活跃状态的账号在创建链实例时会被自动跳过" /></h3>
                    <div class="border border-white/10 rounded-lg p-3 h-64 overflow-y-auto">
                      <div v-if="membersLoading" class="text-sm text-slate-500 text-center py-4">加载中...</div>
                      <div v-else-if="members.length === 0" class="text-sm text-slate-500 text-center py-4">暂无成员</div>
                      <div
                        v-for="member in members"
                        :key="member.id"
                        class="flex items-center justify-between py-1 px-2 hover:bg-white/5 rounded"
                      >
                        <div>
                          <span class="text-sm text-slate-300">{{ member.nickname || member.douyin_id || member.id }}</span>
                          <span v-if="member.status !== 'active'" class="ml-1 text-xs text-red-400">({{ member.status }})</span>
                        </div>
                        <button
                          class="text-xs text-red-400 hover:text-red-300 px-2 py-1 hover:bg-red-400/10 rounded"
                          @click="handleRemoveMember(member.id)"
                        >
                          移除
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                <div class="flex justify-end mt-4">
                  <button
                    class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors"
                    @click="showMembersDialog = false"
                  >
                    关闭
                  </button>
                </div>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>

    <!-- Delete Confirmation Dialog -->
    <ConfirmDialog
      :open="showDeleteDialog"
      title="删除分组"
      :message="`确定要删除分组「${deletingGroup?.name || ''}」吗？此操作不可撤销。`"
      confirm-text="删除"
      :danger="true"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>
```

## src/views/AccountsPage.vue

```html
<script setup>
import { ref, reactive, onMounted } from 'vue'
import {
  Dialog,
  DialogPanel,
  DialogTitle,
  TransitionRoot,
  TransitionChild,
} from '@headlessui/vue'
import DataTable from '../components/DataTable.vue'
import StatusBadge from '../components/StatusBadge.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import {
  listAccounts,
  createAccount,
  updateAccount,
  deleteAccount,
} from '../api/accounts.js'
import { formatDate } from '../utils/format.js'
import { useToastStore } from '../stores/toast.js'
import TipIcon from '../components/TipIcon.vue'
import { useWebSocket } from '../composables/useWebSocket.js'

const DAILY_LIMIT_FIELDS = [
  { key: 'likes', label: '点赞', max: 200 },
  { key: 'comments', label: '评论', max: 100 },
  { key: 'follows', label: '关注', max: 100 },
  { key: 'dms', label: '私信', max: 100 },
  { key: 'replies', label: '回复', max: 500 },
]

const DEFAULT_LIMITS = { likes: 50, comments: 20, follows: 20, dms: 10, replies: 15 }

// --- Data state ---
const accounts = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)

// --- Form / Dialog state ---
const showFormDialog = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const formError = ref(null)

const defaultForm = {
  nickname: '',
  douyin_id: '',
  group: '',
  status: 'active',
  unlimited: false,
  limits: { ...DEFAULT_LIMITS },
}
const form = reactive({ ...defaultForm })
const editingId = ref(null)

// --- Delete confirmation state ---
const showDeleteDialog = ref(false)
const deletingAccount = ref(null)
const deleting = ref(false)

// --- Page-level error ---
const pageError = ref(null)

const toast = useToastStore()

// --- WebSocket ---
function wsUrl() {
  const token = localStorage.getItem('token') || ''
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/api/devices/ws/pair-events?token=${encodeURIComponent(token)}`
}
useWebSocket(wsUrl, {
  onMessage(msg) {
    if (msg.event === 'accounts_changed') fetchAccounts()
  },
})

// --- Status options for the dropdown ---
const statusOptions = [
  { value: 'active', label: '正常' },
  { value: 'risk_controlled', label: '风控中' },
  { value: 'banned', label: '已禁用' },
]

// --- Table columns ---
const columns = [
  { key: 'nickname', label: '昵称' },
  { key: 'douyin_id', label: '抖音号' },
  { key: 'group', label: '分组' },
  { key: 'status', label: '状态' },
  { key: 'created_at', label: '创建时间' },
  { key: 'actions', label: '操作', headerClass: 'text-right', cellClass: 'text-right' },
]

// --- Fetch accounts ---
async function fetchAccounts() {
  loading.value = true
  try {
    const skip = (page.value - 1) * pageSize
    const res = await listAccounts({ skip, limit: pageSize })
    accounts.value = res.data.accounts || []
    total.value = res.data.total || 0
  } catch (e) {
    toast.error('加载账号列表失败')
    accounts.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handlePageChange(p) {
  page.value = p
  fetchAccounts()
}

// --- Open create dialog ---
function openCreateDialog() {
  isEditing.value = false
  editingId.value = null
  Object.assign(form, defaultForm)
  form.limits = { ...DEFAULT_LIMITS }
  form.unlimited = false
  formError.value = null
  showFormDialog.value = true
}

// --- Open edit dialog ---
function openEditDialog(account) {
  isEditing.value = true
  editingId.value = account.id
  form.nickname = account.nickname || ''
  form.douyin_id = account.douyin_id || ''
  form.group = account.group || ''
  form.status = account.status || 'active'
  const dl = account.daily_limits
  if (dl && typeof dl === 'object' && Object.keys(dl).length > 0) {
    form.unlimited = false
    form.limits = {
      likes: dl.likes ?? DEFAULT_LIMITS.likes,
      comments: dl.comments ?? DEFAULT_LIMITS.comments,
      follows: dl.follows ?? DEFAULT_LIMITS.follows,
      dms: dl.dms ?? DEFAULT_LIMITS.dms,
      replies: dl.replies ?? DEFAULT_LIMITS.replies,
    }
  } else {
    form.unlimited = true
    form.limits = { ...DEFAULT_LIMITS }
  }
  formError.value = null
  showFormDialog.value = true
}

// --- Save (create or update) ---
async function handleSave() {
  if (!form.nickname.trim()) {
    formError.value = '昵称不能为空'
    return
  }

  saving.value = true
  formError.value = null

  const payload = {
    nickname: form.nickname.trim(),
    douyin_id: form.douyin_id.trim() || undefined,
    group: form.group.trim() || undefined,
    status: form.status,
    daily_limits: form.unlimited ? {} : { ...form.limits },
  }

  try {
    if (isEditing.value) {
      await updateAccount(editingId.value, payload)
    } else {
      await createAccount(payload)
    }
    showFormDialog.value = false
    fetchAccounts()
  } catch (e) {
    formError.value =
      e.response?.data?.message ||
      e.response?.data?.detail ||
      '保存失败，请重试'
  } finally {
    saving.value = false
  }
}

// --- Delete ---
function openDeleteDialog(account) {
  deletingAccount.value = account
  showDeleteDialog.value = true
}

async function handleDelete() {
  if (!deletingAccount.value) return
  deleting.value = true
  try {
    await deleteAccount(deletingAccount.value.id)
    showDeleteDialog.value = false
    deletingAccount.value = null
    // If we deleted the last item on the current page, go back one page
    if (accounts.value.length === 1 && page.value > 1) {
      page.value--
    }
    fetchAccounts()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '删除失败，请重试'
  } finally {
    deleting.value = false
  }
}

// --- Init ---
onMounted(fetchAccounts)
</script>

<template>
  <div>
    <!-- Page error banner -->
    <div v-if="pageError" class="mb-4 glass-card border-red-500/30 text-red-400 px-4 py-3 rounded-xl flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-400 hover:text-red-300 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white inline-flex items-center gap-1.5">账号管理 <TipIcon text="管理抖音账号，配置状态、分组和每日操作限额" /></h1>
      <button
        class="btn-aurora inline-flex items-center px-4 py-2 text-sm font-medium rounded-xl"
        @click="openCreateDialog"
      >
        <svg
          class="-ml-1 mr-2 h-5 w-5 relative z-10"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"
          />
        </svg>
        <span class="relative z-10">添加账号</span>
      </button>
    </div>

    <!-- Data Table -->
    <DataTable
      :columns="columns"
      :data="accounts"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      @page-change="handlePageChange"
    >
      <!-- Status column -->
      <template #cell-status="{ value }">
        <StatusBadge :status="value" />
      </template>

      <!-- Created at column -->
      <template #cell-created_at="{ value }">
        {{ formatDate(value) }}
      </template>

      <!-- Actions column -->
      <template #cell-actions="{ row }">
        <div class="flex justify-end gap-2">
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-cyan-400 hover:text-cyan-300 hover:bg-cyan-400/10 rounded-lg transition-colors"
            @click="openEditDialog(row)"
          >
            编辑
          </button>
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-400/10 rounded-lg transition-colors"
            @click="openDeleteDialog(row)"
          >
            删除
          </button>
        </div>
      </template>
    </DataTable>

    <!-- Create / Edit Dialog -->
    <TransitionRoot :show="showFormDialog" as="template">
      <Dialog
        as="div"
        class="relative z-50"
        @close="showFormDialog = false"
      >
        <TransitionChild
          as="template"
          enter="ease-out duration-300"
          enter-from="opacity-0"
          enter-to="opacity-100"
          leave="ease-in duration-200"
          leave-from="opacity-100"
          leave-to="opacity-0"
        >
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>

        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild
              as="template"
              enter="ease-out duration-300"
              enter-from="opacity-0 scale-95"
              enter-to="opacity-100 scale-100"
              leave="ease-in duration-200"
              leave-from="opacity-100 scale-100"
              leave-to="opacity-0 scale-95"
            >
              <DialogPanel
                class="glass-card w-full max-w-lg p-6 gradient-border"
              >
                <DialogTitle class="text-lg font-medium text-white">
                  {{ isEditing ? '编辑账号' : '添加账号' }}
                </DialogTitle>

                <!-- Error message -->
                <div
                  v-if="formError"
                  class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-3 py-2 rounded-lg"
                >
                  {{ formError }}
                </div>
                <form class="mt-4 space-y-4" @submit.prevent="handleSave">
                  <!-- Nickname -->
                  <div>
                    <label
                      for="nickname"
                      class="block text-sm font-medium text-slate-300"
                    >
                      昵称 <span class="text-red-400">*</span>
                    </label>
                    <input
                      id="nickname"
                      v-model="form.nickname"
                      type="text"
                      required
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                      placeholder="请输入昵称"
                    />
                  </div>

                  <!-- Douyin ID -->
                  <div>
                    <label
                      for="douyin_id"
                      class="block text-sm font-medium text-slate-300"
                    >
                      抖音号
                    </label>
                    <input
                      id="douyin_id"
                      v-model="form.douyin_id"
                      type="text"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                      placeholder="请输入抖音号"
                    />
                  </div>

                  <!-- Group -->
                  <div>
                    <label
                      for="group"
                      class="flex items-center gap-1.5 text-sm font-medium text-slate-300"
                    >
                      分组
                      <TipIcon text="为账号分配分组标签，方便批量管理和创建链实例" />
                    </label>
                    <input
                      id="group"
                      v-model="form.group"
                      type="text"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                      placeholder="请输入分组"
                    />
                  </div>

                  <!-- Status -->
                  <div>
                    <label
                      for="status"
                      class="flex items-center gap-1.5 text-sm font-medium text-slate-300"
                    >
                      状态
                      <TipIcon text="正常=可执行任务；风控中=触发抖音风控，暂停任务；已禁用=手动禁用，不分配任务" width="w-80" />
                    </label>
                    <select
                      id="status"
                      v-model="form.status"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
                    >
                      <option
                        v-for="opt in statusOptions"
                        :key="opt.value"
                        :value="opt.value"
                      >
                        {{ opt.label }}
                      </option>
                    </select>
                  </div>

                  <!-- Daily Limits -->
                  <div>
                    <div class="flex items-center justify-between mb-4">
                      <label class="flex items-center gap-1.5 text-sm font-semibold text-slate-200">
                        <svg class="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        每日限额
                        <TipIcon :text="'每种操作类型每日执行上限，超出后自动跳过该操作\n\n点赞 (search_like)\n  搜索结果页对视频点赞\n\n评论 (search_comment)\n  搜索结果页对视频发表评论\n\n关注 (follow)\n  评论回复流程中关注评论者\n\n私信 (search_dm)\n  搜索视频作者或评论者发送私信，一个用户计 1 次\n\n回复 (reply_comment)\n  对视频评论区留言进行 AI 回复'" width="w-72" />
                      </label>
                      <label class="flex items-center gap-2 text-xs text-slate-400 cursor-pointer select-none hover:text-slate-300 transition-colors">
                        <input type="checkbox" v-model="form.unlimited" class="accent-indigo-600 rounded" />
                        不限制
                      </label>
                    </div>
                    <div v-if="!form.unlimited" class="space-y-2">
                      <div v-for="f in DAILY_LIMIT_FIELDS" :key="f.key"
                           class="flex items-center gap-3 rounded-lg px-3 py-2"
                           :style="{ background: 'rgba(255,255,255,0.02)' }">
                        <span class="w-10 text-xs font-medium shrink-0"
                          :class="[
                            f.key === 'likes' ? 'text-pink-400' :
                            f.key === 'comments' ? 'text-emerald-400' :
                            f.key === 'follows' ? 'text-amber-400' :
                            f.key === 'dms' ? 'text-sky-400' :
                            'text-violet-400'
                          ]">{{ f.label }}</span>
                        <input
                          :id="'limit-' + f.key"
                          v-model.number="form.limits[f.key]"
                          type="number"
                          min="-1"
                          :max="f.max"
                          title="-1 表示不限制"
                          class="w-16 rounded-lg border border-white/10 bg-white/[0.06] px-2 py-1.5 text-sm font-semibold text-white text-center focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-transparent transition-shadow shrink-0"
                        />
                        <div class="flex-1 h-1.5 rounded-full bg-white/5 overflow-hidden">
                          <div class="h-full rounded-full transition-all duration-300"
                            :style="{ width: Math.min(100, Math.max(0, (form.limits[f.key] || 0)) / f.max * 100) + '%' }"
                            :class="[
                              f.key === 'likes' ? 'bg-gradient-to-r from-pink-500 to-pink-300' :
                              f.key === 'comments' ? 'bg-gradient-to-r from-emerald-500 to-emerald-300' :
                              f.key === 'follows' ? 'bg-gradient-to-r from-amber-500 to-amber-300' :
                              f.key === 'dms' ? 'bg-gradient-to-r from-sky-500 to-sky-300' :
                              'bg-gradient-to-r from-violet-500 to-violet-300'
                            ]"></div>
                        </div>
                        <span class="text-[11px] text-slate-500 w-9 text-right shrink-0">/{{ f.max }}</span>
                      </div>
                    </div>
                  </div>

                  <!-- Buttons -->
                  <div class="flex justify-end gap-3 pt-2">
                    <button
                      type="button"
                      class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors"
                      @click="showFormDialog = false"
                    >
                      取消
                    </button>
                    <button
                      type="submit"
                      :disabled="saving"
                      class="btn-aurora rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <span class="relative z-10">{{ saving ? '保存中...' : '保存' }}</span>
                    </button>
                  </div>
                </form>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>

    <!-- Delete Confirmation Dialog -->
    <ConfirmDialog
      :open="showDeleteDialog"
      title="删除账号"
      :message="`确定要删除账号「${deletingAccount?.nickname || ''}」吗？此操作不可撤销。`"
      confirm-text="删除"
      :danger="true"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>
```

## src/views/AdminLayout.vue

```html
<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppTopNav from '../components/layout/AppTopNav.vue'
import AppSidebar from '../components/layout/AppSidebar.vue'
import { getCategoryByRoute } from '../constants/navigation.js'

const route = useRoute()
const activeCategory = computed(() => getCategoryByRoute(route))
</script>

<template>
  <div class="h-screen flex flex-col overflow-hidden" style="background: var(--bg-void);">
    <AppTopNav :activeCategory="activeCategory" />
    <div class="flex flex-1 overflow-hidden">
      <AppSidebar :activeCategory="activeCategory" />
      <main class="flex-1 overflow-auto">
        <div class="p-6 animate-in">
          <RouterView />
        </div>
      </main>
    </div>
  </div>
</template>
```

## src/views/AIConfigPage.vue

```html
<template>
  <div class="aicfg-root">
    <!-- Header -->
    <div class="aicfg-header">
      <div>
        <h1 class="aicfg-title">AI 模型配置中心</h1>
        <p class="aicfg-subtitle">管理所有 AI 模型的 API 密钥和端点配置</p>
      </div>
      <button @click="startCreate" class="aicfg-btn aicfg-btn-add" aria-label="新增模型">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
        新增模型
      </button>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="aicfg-loading">
      <div v-for="i in 4" :key="i" class="aicfg-skeleton-card">
        <div class="flex gap-3">
          <div class="skeleton-pulse w-10 h-10 rounded-lg flex-shrink-0"></div>
          <div class="flex-1 space-y-2">
            <div class="skeleton-pulse h-3 w-32 rounded"></div>
            <div class="skeleton-pulse h-2.5 w-48 rounded"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Main content -->
    <div v-else class="aicfg-main">
      <!-- LEFT PANEL -->
      <nav class="aicfg-left" aria-label="模型列表">
        <template v-for="group in groupedModels" :key="group.key">
          <div class="aicfg-group-label" :class="'text-' + group.color">{{ group.label }}</div>
          <button
            v-for="m in group.models"
            :key="m.id"
            @click="selectModel(m.id)"
            :aria-current="selectedId === m.id ? 'true' : undefined"
            class="aicfg-model-item"
            :class="{ 'aicfg-model-item--active': selectedId === m.id }"
          >
            <span class="aicfg-model-dot" :class="'bg-' + group.color"></span>
            <span class="aicfg-model-name">{{ m.name }}</span>
            <span v-if="m.enabled === false" class="aicfg-badge aicfg-badge--warn">禁用</span>
            <span v-else-if="!m.api_key_configured" class="aicfg-badge aicfg-badge--err">未配置</span>
            <span v-else class="aicfg-badge aicfg-badge--ok">已配置</span>
          </button>
        </template>
        <div v-if="!allModels.length" class="aicfg-empty-left">暂无模型，点击右上角"新增模型"</div>
      </nav>

      <!-- RIGHT PANEL -->
      <div class="aicfg-right">
        <!-- Empty state -->
        <div v-if="!selectedModel" class="aicfg-empty-right">
          <div class="aicfg-empty-icon">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
          </div>
          <p>从左侧选择一个模型进行编辑</p>
        </div>

        <!-- Edit card -->
        <div v-else class="aicfg-card" :class="{ 'aicfg-card--new': isNew }">
          <!-- Card header -->
          <div class="aicfg-card-header">
            <div>
              <div class="aicfg-card-title-row">
                <span v-if="isNew" class="aicfg-pill aicfg-pill--new">新建</span>
                <h2>{{ isNew ? '新建模型' : form.name }}</h2>
              </div>
              <p class="aicfg-card-meta">
                <span class="aicfg-type-tag">{{ typeLabels[form.model_type] || form.model_type }}</span>
                <span v-if="!isNew" class="aicfg-id">ID: {{ selectedModel.id }}</span>
              </p>
            </div>
            <label v-if="!isNew" class="aicfg-toggle-row" title="启用/禁用">
              <span class="aicfg-toggle-label">启用</span>
              <button
                @click="toggleEnabled"
                role="switch"
                :aria-checked="form.enabled"
                class="aicfg-toggle"
                :class="{ 'aicfg-toggle--on': form.enabled }"
              >
                <span class="aicfg-toggle-knob"></span>
              </button>
            </label>
          </div>

          <!-- Generic fields -->
          <div class="aicfg-fields">
            <label class="aicfg-field">
              <span class="aicfg-field-label">模型名称 <b class="text-red-400">*</b></span>
              <input v-model="form.name" placeholder="如 DeepSeek V3" class="aicfg-input" />
            </label>
            <label class="aicfg-field">
              <span class="aicfg-field-label">模型类型 <b class="text-red-400" v-if="isNew">*</b></span>
              <select v-model="form.model_type" :disabled="!isNew" class="aicfg-input" :class="{ 'opacity-50': !isNew }">
                <option value="llm">LLM · 脚本生成</option>
                <option value="image">Image · 画面生成</option>
                <option value="video">Video · 视频渲染</option>
                <option value="tts">TTS · 语音合成</option>
                <option value="audit">Audit · 质量审计</option>
              </select>
            </label>
            <label class="aicfg-field">
              <span class="aicfg-field-label">服务商 (Provider) <b class="text-red-400">*</b></span>
              <select v-model="form.provider" class="aicfg-input">
                <option v-for="p in providerOptions" :key="p" :value="p">{{ p }}</option>
              </select>
            </label>
            <label class="aicfg-field">
              <span class="aicfg-field-label">接口地址 (Base URL)</span>
              <input v-model="form.base_url" placeholder="https://api.deepseek.com/v1" class="aicfg-input" />
            </label>
            <label class="aicfg-field">
              <span class="aicfg-field-label">API Key</span>
              <input type="password" v-model="form.api_key" placeholder="sk-xxx..." class="aicfg-input" />
            </label>
            <label class="aicfg-field" v-if="form.provider === 'kling'">
              <span class="aicfg-field-label">API Secret</span>
              <input type="password" v-model="form.api_secret" placeholder="Kling Secret Key" class="aicfg-input" />
            </label>
            <label class="aicfg-field">
              <span class="aicfg-field-label">模型标识 (model_name)</span>
              <input v-model="form.model_name" placeholder="deepseek-chat" class="aicfg-input" />
            </label>
          </div>

          <!-- Type-specific config -->
          <div v-if="form.model_type" class="aicfg-config-block">
            <h3 class="aicfg-config-title">{{ typeLabels[form.model_type] }} 专属配置</h3>

            <!-- LLM -->
            <div v-if="form.model_type === 'llm'" class="aicfg-fields">
              <label class="aicfg-field aicfg-field--toggle">
                <span>启用思考模式 (Thinking)</span>
                <button
                  @click="cfg.thinking_enabled = !cfg.thinking_enabled"
                  role="switch"
                  :aria-checked="cfg.thinking_enabled"
                  class="aicfg-toggle"
                  :class="{ 'aicfg-toggle--on': cfg.thinking_enabled }"
                >
                  <span class="aicfg-toggle-knob"></span>
                </button>
              </label>
              <label class="aicfg-field">
                <span class="aicfg-field-label">思考预算 (thinking_budget)</span>
                <input type="number" v-model.number="cfg.thinking_budget" class="aicfg-input" />
              </label>
              <label class="aicfg-field">
                <span class="aicfg-field-label">最大 Token (max_tokens)</span>
                <input type="number" v-model.number="cfg.max_tokens" class="aicfg-input" />
              </label>
              <label class="aicfg-field">
                <span class="aicfg-field-label">温度 (temperature)</span>
                <input type="number" v-model.number="cfg.temperature" step="0.1" min="0" max="2" class="aicfg-input" />
              </label>
            </div>

            <!-- Image -->
            <div v-if="form.model_type === 'image'" class="aicfg-fields">
              <label class="aicfg-field">
                <span class="aicfg-field-label">默认尺寸 (default_size)</span>
                <select v-model="cfg.default_size" class="aicfg-input">
                  <option value="1024x1024">1024×1024</option>
                  <option value="1792x1024">1792×1024</option>
                  <option value="1024x1792">1024×1792</option>
                </select>
              </label>
              <label class="aicfg-field">
                <span class="aicfg-field-label">默认质量 (default_quality)</span>
                <select v-model="cfg.default_quality" class="aicfg-input">
                  <option value="standard">Standard</option>
                  <option value="hd">HD</option>
                </select>
              </label>
            </div>

            <!-- Video -->
            <div v-if="form.model_type === 'video'" class="aicfg-fields">
              <label class="aicfg-field">
                <span class="aicfg-field-label">默认分辨率 (default_resolution)</span>
                <select v-model="cfg.default_resolution" class="aicfg-input">
                  <option value="480p">480p</option>
                  <option value="720p">720p</option>
                  <option value="1080p">1080p</option>
                </select>
              </label>
              <label class="aicfg-field">
                <span class="aicfg-field-label">默认时长/秒 (default_duration)</span>
                <input type="number" v-model.number="cfg.default_duration" class="aicfg-input" />
              </label>
              <label class="aicfg-field">
                <span class="aicfg-field-label">默认比例 (default_aspect_ratio)</span>
                <select v-model="cfg.default_aspect_ratio" class="aicfg-input">
                  <option value="16:9">16:9</option>
                  <option value="9:16">9:16</option>
                  <option value="1:1">1:1</option>
                  <option value="4:3">4:3</option>
                </select>
              </label>
            </div>

            <!-- TTS -->
            <div v-if="form.model_type === 'tts'" class="aicfg-fields">
              <label class="aicfg-field">
                <span class="aicfg-field-label">默认语音 (default_voice)</span>
                <input v-model="cfg.default_voice" placeholder="zh-CN-XiaoxiaoNeural" class="aicfg-input" />
              </label>
              <label class="aicfg-field">
                <span class="aicfg-field-label">默认语言 (default_language)</span>
                <input v-model="cfg.default_language" placeholder="zh-CN" class="aicfg-input" />
              </label>
              <label class="aicfg-field">
                <span class="aicfg-field-label">默认语速 (default_speed)</span>
                <input type="number" v-model.number="cfg.default_speed" step="0.1" min="0.5" max="3" class="aicfg-input" />
              </label>
            </div>

            <!-- Audit -->
            <div v-if="form.model_type === 'audit'" class="aicfg-fields">
              <label class="aicfg-field">
                <span class="aicfg-field-label">审计模式 (audit_mode)</span>
                <select v-model="cfg.audit_mode" class="aicfg-input">
                  <option value="single">Single · 单条审计</option>
                  <option value="multi">Multi · 多重审计</option>
                  <option value="batch">Batch · 批量审计</option>
                  <option value="skip">Skip · 跳过审计</option>
                </select>
              </label>
            </div>
          </div>

          <!-- Actions -->
          <div class="aicfg-actions">
            <div class="aicfg-actions-left">
              <button @click="save" class="aicfg-btn aicfg-btn-save" :disabled="saving">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
                {{ saving ? '保存中...' : (isNew ? '创建模型' : '保存修改') }}
              </button>
              <button
                v-if="!isNew"
                @click="testConnection"
                class="aicfg-btn aicfg-btn-ghost"
                :disabled="testing"
              >
                <svg class="w-4 h-4" :class="{ 'animate-spin': testing }" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                {{ testing ? '测试中...' : '测试连接' }}
              </button>
            </div>
            <button
              v-if="!isNew"
              @click="confirmDelete"
              class="aicfg-btn aicfg-btn-del"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
              删除
            </button>
          </div>

          <!-- Messages -->
          <Transition name="msg">
            <div v-if="testResult" class="aicfg-msg" :class="testResult.ok ? 'aicfg-msg--ok' : 'aicfg-msg--err'">
              {{ testResult.ok ? '✓ 连接成功' : '✗ ' + testResult.error }}
            </div>
          </Transition>
          <Transition name="msg">
            <div v-if="saveMsg" class="aicfg-msg" :class="saveMsg.type === 'ok' ? 'aicfg-msg--ok' : 'aicfg-msg--err'">
              {{ saveMsg.text }}
            </div>
          </Transition>
        </div>
      </div>
    </div>

    <!-- Delete confirm modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div v-if="showDeleteConfirm" class="aicfg-modal-overlay" @click.self="showDeleteConfirm = false">
          <div class="aicfg-modal" role="dialog" aria-modal="true" aria-labelledby="delete-title">
            <h3 id="delete-title">确认删除</h3>
            <p>确定要删除模型「{{ form.name }}」吗？此操作不可撤销，依赖此模型的 Pipeline 将无法运行。</p>
            <div class="aicfg-modal-btns">
              <button @click="showDeleteConfirm = false" class="aicfg-btn aicfg-btn-ghost">取消</button>
              <button @click="doDelete" class="aicfg-btn aicfg-btn-del" :disabled="saving">{{ saving ? '删除中...' : '确认删除' }}</button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { listModels, getModel, createModel, updateModel, deleteModel, testModelConnection } from '../api/aiConfig.js'

const loading = ref(true)
const saving = ref(false)
const testing = ref(false)
const allModels = ref([])
const selectedId = ref(null)
const showDeleteConfirm = ref(false)
const testResult = ref(null)
const saveMsg = ref(null)

const TYPE_GROUPS = [
  { key: 'llm', label: '脚本生成 (LLM)', color: 'sky' },
  { key: 'image', label: '画面生成 (Image)', color: 'emerald' },
  { key: 'video', label: '视频渲染 (Video)', color: 'purple' },
  { key: 'tts', label: '语音合成 (TTS)', color: 'amber' },
  { key: 'audit', label: '质量审计 (Audit)', color: 'rose' },
]

const typeLabels = { llm: 'LLM', image: 'Image', video: 'Video', tts: 'TTS', audit: 'Audit' }

const PROVIDERS = {
  llm: ['deepseek', 'openai', 'anthropic', 'custom'],
  image: ['seedance', 'openai', 'comfyui', 'runninghub'],
  video: ['seedance', 'kling', 'wan', 'pixelle'],
  tts: ['edge-tts', 'index-tts', 'spark-tts', 'custom'],
  audit: ['openai', 'gemini', 'local', 'none'],
}

const DEFAULT_CONFIG = {
  llm: { thinking_enabled: false, thinking_budget: 8192, max_tokens: 4096, temperature: 0.7 },
  image: { default_size: '1024x1024', default_quality: 'hd' },
  video: { default_resolution: '720p', default_duration: 5, default_aspect_ratio: '9:16' },
  tts: { default_voice: 'zh-CN-XiaoxiaoNeural', default_language: 'zh-CN', default_speed: 1.0 },
  audit: { audit_mode: 'single' },
}

const groupedModels = computed(() =>
  TYPE_GROUPS.map(g => ({
    ...g,
    models: allModels.value.filter(m => m.model_type === g.key),
  }))
)

const selectedModel = computed(() => allModels.value.find(m => m.id === selectedId.value))

const isNew = computed(() => {
  const m = selectedModel.value
  return m && m.id.startsWith('__new__')
})

const providerOptions = computed(() => PROVIDERS[form.model_type] || [])

const form = reactive({
  name: '', model_type: 'llm', provider: 'deepseek',
  base_url: '', api_key: '', api_secret: '',
  model_name: '', enabled: true,
})

const cfg = reactive({ ...DEFAULT_CONFIG.llm })

// Load full detail when selecting a model
watch(selectedId, async (id) => {
  testResult.value = null
  saveMsg.value = null
  if (!id) return
  const m = allModels.value.find(x => x.id === id)
  if (!m) return

  if (m.id.startsWith('__new__')) {
    // New unsaved model — reset form
    Object.assign(form, {
      name: m.name, model_type: m.model_type, provider: PROVIDERS[m.model_type][0],
      base_url: '', api_key: '', api_secret: '', model_name: '', enabled: true,
    })
    Object.assign(cfg, { ...DEFAULT_CONFIG[m.model_type] })
    return
  }

  // Load full detail from API (to get decrypted api_key)
  try {
    const { data } = await getModel(id)
    if (data.ok) {
      const d = data.model
      Object.assign(form, {
        name: d.name, model_type: d.model_type, provider: d.provider,
        base_url: d.base_url || '', api_key: d.api_key || '', api_secret: d.api_secret || '',
        model_name: d.model_name || '', enabled: d.enabled,
      })
      if (d.config_json) {
        Object.assign(cfg, { ...DEFAULT_CONFIG[d.model_type] || {}, ...d.config_json })
      } else {
        Object.assign(cfg, { ...DEFAULT_CONFIG[d.model_type] || {} })
      }
    }
  } catch (e) {
    saveMsg.value = { type: 'err', text: '加载详情失败: ' + (e.message || '未知错误') }
  }
})

// Switch config defaults when model_type changes in new mode
watch(() => form.model_type, (mt) => {
  if (isNew.value) {
    form.provider = PROVIDERS[mt]?.[0] || ''
    Object.assign(cfg, { ...DEFAULT_CONFIG[mt] || {} })
  }
})

function startCreate() {
  const id = '__new__' + Date.now()
  allModels.value.push({
    id, name: '新模型', model_type: 'llm', provider: '', api_key_configured: false, enabled: true, config_json: {},
  })
  selectedId.value = id
}

function selectModel(id) {
  selectedId.value = id
}

async function toggleEnabled() {
  if (isNew.value) return
  const newEnabled = !form.enabled
  form.enabled = newEnabled
  try {
    await updateModel(selectedId.value, { enabled: newEnabled })
    const m = allModels.value.find(x => x.id === selectedId.value)
    if (m) m.enabled = newEnabled
    saveMsg.value = { type: 'ok', text: newEnabled ? '已启用' : '已禁用' }
    setTimeout(() => saveMsg.value = null, 2000)
  } catch (e) {
    form.enabled = !newEnabled
    saveMsg.value = { type: 'err', text: '操作失败: ' + (e.message || '未知错误') }
  }
}

async function save() {
  saving.value = true
  testResult.value = null
  saveMsg.value = null

  const payload = {
    name: form.name,
    model_type: form.model_type,
    provider: form.provider,
    base_url: form.base_url || '',
    api_key: form.api_key || '',
    api_secret: form.api_secret || '',
    model_name: form.model_name || '',
    config_json: { ...cfg },
  }

  try {
    if (isNew.value) {
      const { data } = await createModel(payload)
      if (data.ok) {
        const idx = allModels.value.findIndex(m => m.id === selectedId.value)
        if (idx >= 0) allModels.value[idx] = data.model
        selectedId.value = data.model.id
        saveMsg.value = { type: 'ok', text: '模型创建成功' }
      }
    } else {
      const updatePayload = { ...payload }
      if (!form.api_key && selectedModel.value?.api_key_configured) {
        delete updatePayload.api_key
        delete updatePayload.api_secret
      }
      const { data } = await updateModel(selectedId.value, updatePayload)
      if (data.ok) {
        const idx = allModels.value.findIndex(m => m.id === selectedId.value)
        if (idx >= 0) allModels.value[idx] = data.model
        saveMsg.value = { type: 'ok', text: '保存成功' }
      }
    }
    setTimeout(() => saveMsg.value = null, 3000)
  } catch (e) {
    saveMsg.value = { type: 'err', text: '保存失败: ' + (e.response?.data?.detail || e.message || '未知错误') }
  } finally {
    saving.value = false
  }
}

async function testConnection() {
  if (isNew.value) return
  testing.value = true
  testResult.value = null
  try {
    const { data } = await testModelConnection(selectedId.value)
    testResult.value = data
  } catch (e) {
    testResult.value = { ok: false, error: e.message || '请求失败' }
  } finally {
    testing.value = false
  }
}

function confirmDelete() {
  showDeleteConfirm.value = true
}

async function doDelete() {
  saving.value = true
  try {
    await deleteModel(selectedId.value)
    allModels.value = allModels.value.filter(m => m.id !== selectedId.value)
    selectedId.value = allModels.value.length > 0 ? allModels.value[0].id : null
    showDeleteConfirm.value = false
  } catch (e) {
    saveMsg.value = { type: 'err', text: '删除失败: ' + (e.response?.data?.detail || e.message || '未知错误') }
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const { data } = await listModels()
    if (data.ok) allModels.value = data.models || []
    if (allModels.value.length > 0) selectedId.value = allModels.value[0].id
  } catch (e) {
    saveMsg.value = { type: 'err', text: '加载模型列表失败' }
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
/* ============================================================
   AI Config Page — Design System: Glassmorphism + Dark Dashboard
   Colors: bg #020617, surface #0F172A, border rgba(255,255,255,0.06-0.12)
   CTA: #22C55E (green), Accent: #38BDF8 (sky)
   Typography: system-ui, with tabular-nums for data
   Motion: 200ms ease-out, respects prefers-reduced-motion
   ============================================================ */

/* ---- Root layout ---- */
.aicfg-root {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 1.5rem;
  min-height: 0;
}
.aicfg-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.25rem;
  flex-shrink: 0;
}
.aicfg-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #F8FAFC;
  letter-spacing: -0.01em;
}
.aicfg-subtitle {
  font-size: 0.8125rem;
  color: #94A3B8;
  margin-top: 0.125rem;
}

/* ---- Main layout ---- */
.aicfg-main {
  display: flex;
  gap: 1.25rem;
  flex: 1;
  min-height: 0;
}

/* ---- Loading skeleton ---- */
.aicfg-loading { display: flex; flex-direction: column; gap: 0.5rem; padding-top: 1rem; }
.aicfg-skeleton-card {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255,255,255,0.05);
  border-radius: 0.75rem;
  padding: 1rem;
}
.skeleton-pulse {
  background: linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%);
  background-size: 200% 100%;
  animation: sk-pulse 1.5s ease-in-out infinite;
}
@keyframes sk-pulse { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }

/* ---- LEFT PANEL ---- */
.aicfg-left {
  width: 16rem;
  flex-shrink: 0;
  overflow-y: auto;
  padding-right: 0.25rem;
}
.aicfg-left::-webkit-scrollbar { width: 3px; }
.aicfg-left::-webkit-scrollbar-track { background: transparent; }
.aicfg-left::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.06); border-radius: 2px; }

.aicfg-group-label {
  font-size: 0.8125rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 0.75rem 0.5rem 0.5rem;
}
.aicfg-group-label:first-child { padding-top: 0.125rem; }
.text-sky    { color: #38BDF8; }
.text-emerald{ color: #34D399; }
.text-purple { color: #A78BFA; }
.text-amber  { color: #FBBF24; }
.text-rose   { color: #FB7185; }
.bg-sky    { background: #38BDF8; }
.bg-emerald{ background: #34D399; }
.bg-purple { background: #A78BFA; }
.bg-amber  { background: #FBBF24; }
.bg-rose   { background: #FB7185; }

.aicfg-model-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  text-align: left;
  padding: 0.5rem 0.625rem;
  border-radius: 0.5rem;
  font-size: 0.75rem;
  color: #CBD5E1;
  background: transparent;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease;
  font-family: inherit;
}
.aicfg-model-item:hover {
  background: rgba(255,255,255,0.04);
  border-color: rgba(255,255,255,0.06);
  color: #F1F5F9;
}
.aicfg-model-item:focus-visible {
  outline: 2px solid #38BDF8;
  outline-offset: -2px;
}
.aicfg-model-item--active {
  background: rgba(56, 189, 248, 0.1);
  border-color: rgba(56, 189, 248, 0.25);
  color: #F8FAFC;
  box-shadow: 0 0 12px rgba(56, 189, 248, 0.06);
}

.aicfg-model-dot { width: 0.375rem; height: 0.375rem; border-radius: 9999px; flex-shrink: 0; }
.aicfg-model-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.aicfg-badge {
  font-size: 0.625rem;
  padding: 0.0625rem 0.375rem;
  border-radius: 0.25rem;
  flex-shrink: 0;
  line-height: 1.4;
  font-weight: 500;
}
.aicfg-badge--ok  { background: rgba(52, 211, 153, 0.12); color: #34D399; border: 1px solid rgba(52, 211, 153, 0.15); }
.aicfg-badge--warn{ background: rgba(251, 191, 36, 0.12); color: #FBBF24; border: 1px solid rgba(251, 191, 36, 0.15); }
.aicfg-badge--err { background: rgba(248, 113, 113, 0.12); color: #F87171; border: 1px solid rgba(248, 113, 113, 0.15); }
.aicfg-empty-left { font-size: 0.75rem; color: #64748B; text-align: center; padding-top: 2rem; }

/* ---- RIGHT PANEL ---- */
.aicfg-right {
  flex: 1;
  overflow-y: auto;
  min-width: 0;
}
.aicfg-right::-webkit-scrollbar { width: 3px; }
.aicfg-right::-webkit-scrollbar-track { background: transparent; }
.aicfg-right::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.06); border-radius: 2px; }

/* Empty state */
.aicfg-empty-right { text-align: center; padding: 4rem 0; color: #64748B; }
.aicfg-empty-icon { width: 3.5rem; height: 3.5rem; margin: 0 auto 0.75rem; opacity: 0.3; }
.aicfg-empty-icon svg { width: 100%; height: 100%; }

/* ---- Card ---- */
.aicfg-card {
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 0.875rem;
  padding: 1.25rem;
  box-shadow:
    0 4px 24px rgba(0,0,0,0.3),
    inset 0 1px 0 rgba(255,255,255,0.03);
}
.aicfg-card--new {
  border-color: rgba(52, 211, 153, 0.15);
  box-shadow: 0 4px 24px rgba(0,0,0,0.3), 0 0 40px rgba(52, 211, 153, 0.04);
}

.aicfg-card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.25rem; }
.aicfg-card-title-row { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem; }
.aicfg-card-title-row h2 { font-size: 1rem; font-weight: 600; color: #E2E8F0; }

.aicfg-pill {
  font-size: 0.625rem;
  padding: 0.0625rem 0.5rem;
  border-radius: 0.375rem;
  font-weight: 500;
}
.aicfg-pill--new { background: rgba(52, 211, 153, 0.12); color: #34D399; border: 1px solid rgba(52, 211, 153, 0.2); }

.aicfg-card-meta { font-size: 0.6875rem; color: #64748B; display: flex; align-items: center; gap: 0.75rem; }
.aicfg-type-tag { color: #94A3B8; }
.aicfg-id { font-family: ui-monospace, 'Fira Code', monospace; font-size: 0.625rem; color: #475569; }

/* ---- Toggle ---- */
.aicfg-toggle-row { display: flex; align-items: center; gap: 0.5rem; cursor: pointer; user-select: none; }
.aicfg-toggle-label { font-size: 0.75rem; color: #94A3B8; }
.aicfg-toggle {
  position: relative;
  width: 2.25rem;
  height: 1.25rem;
  border-radius: 9999px;
  background: #334155;
  border: 1px solid rgba(255,255,255,0.08);
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
  flex-shrink: 0;
}
.aicfg-toggle:focus-visible { outline: 2px solid #38BDF8; outline-offset: 2px; }
.aicfg-toggle--on { background: #22C55E; border-color: rgba(34, 197, 94, 0.3); }
.aicfg-toggle-knob {
  position: absolute;
  top: 0.125rem;
  left: 0.125rem;
  width: 0.875rem;
  height: 0.875rem;
  border-radius: 9999px;
  background: #F8FAFC;
  box-shadow: 0 1px 3px rgba(0,0,0,0.3);
  transition: transform 0.2s ease;
}
.aicfg-toggle--on .aicfg-toggle-knob { transform: translateX(1rem); }

/* ---- Fields grid ---- */
.aicfg-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}
.aicfg-field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.aicfg-field--toggle {
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  padding: 0.375rem 0.5rem;
  border-radius: 0.375rem;
  font-size: 0.75rem;
  color: #94A3B8;
  cursor: pointer;
}
.aicfg-field--toggle:hover { background: rgba(255,255,255,0.03); }
.aicfg-field-label { font-size: 0.6875rem; color: #94A3B8; }

/* ---- Input ---- */
.aicfg-input {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(255,255,255,0.08);
  color: #F1F5F9;
  font-size: 0.8125rem;
  font-family: inherit;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.aicfg-input::placeholder { color: #475569; }
.aicfg-input:hover { border-color: rgba(255,255,255,0.12); }
.aicfg-input:focus {
  outline: none;
  border-color: rgba(56, 189, 248, 0.4);
  box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.08);
}
select.aicfg-input { cursor: pointer; appearance: none; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3E%3Cpath stroke='%23475569' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 0.375rem center; background-size: 1.25em; padding-right: 2rem; }

/* ---- Config block ---- */
.aicfg-config-block {
  margin-top: 1rem;
  padding: 0.875rem;
  border-radius: 0.625rem;
  background: rgba(255,255,255,0.02);
  border: 1px solid rgba(255,255,255,0.04);
}
.aicfg-config-title {
  font-size: 0.6875rem;
  font-weight: 600;
  color: #94A3B8;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 0.75rem;
}

/* ---- Actions ---- */
.aicfg-actions {
  display: flex;
  align-items: center;
  padding-top: 1rem;
  margin-top: 1rem;
  border-top: 1px solid rgba(255,255,255,0.05);
}
.aicfg-actions-left { display: flex; align-items: center; gap: 0.5rem; flex: 1; }

/* ---- Buttons ---- */
.aicfg-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  font-size: 0.8125rem;
  font-weight: 500;
  font-family: inherit;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.2s ease;
}
.aicfg-btn:focus-visible { outline: 2px solid #38BDF8; outline-offset: 1px; }
.aicfg-btn:disabled { opacity: 0.45; cursor: not-allowed; }
.aicfg-btn-add {
  background: rgba(56, 189, 248, 0.12);
  color: #7DD3FC;
  border-color: rgba(56, 189, 248, 0.2);
}
.aicfg-btn-add:hover:not(:disabled) { background: rgba(56, 189, 248, 0.18); border-color: rgba(56, 189, 248, 0.3); color: #BAE6FD; }
.aicfg-btn-save {
  background: #16A34A;
  color: white;
  border-color: #16A34A;
}
.aicfg-btn-save:hover:not(:disabled) { background: #22C55E; border-color: #22C55E; }
.aicfg-btn-ghost {
  background: transparent;
  color: #94A3B8;
  border-color: rgba(255,255,255,0.08);
}
.aicfg-btn-ghost:hover:not(:disabled) { background: rgba(255,255,255,0.04); color: #CBD5E1; border-color: rgba(255,255,255,0.12); }
.aicfg-btn-del {
  background: transparent;
  color: #F87171;
  border-color: rgba(248, 113, 113, 0.2);
}
.aicfg-btn-del:hover:not(:disabled) { background: rgba(248, 113, 113, 0.08); color: #FCA5A5; border-color: rgba(248, 113, 113, 0.3); }

/* ---- Messages ---- */
.aicfg-msg {
  margin-top: 0.75rem;
  padding: 0.625rem 0.75rem;
  border-radius: 0.5rem;
  font-size: 0.75rem;
  font-weight: 500;
}
.aicfg-msg--ok { background: rgba(34, 197, 94, 0.08); color: #4ADE80; border: 1px solid rgba(34, 197, 94, 0.12); }
.aicfg-msg--err{ background: rgba(248, 113, 113, 0.08); color: #F87171; border: 1px solid rgba(248, 113, 113, 0.12); }

/* ---- Modal ---- */
.aicfg-modal-overlay {
  position: fixed; inset: 0; z-index: 50;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0,0,0,0.55);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}
.aicfg-modal {
  width: 24rem;
  max-width: 90vw;
  padding: 1.5rem;
  border-radius: 0.875rem;
  background: rgba(15, 23, 42, 0.97);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255,255,255,0.08);
  box-shadow: 0 16px 48px rgba(0,0,0,0.5);
}
.aicfg-modal h3 { font-size: 1rem; font-weight: 600; color: #E2E8F0; margin-bottom: 0.5rem; }
.aicfg-modal p  { font-size: 0.8125rem; color: #94A3B8; margin-bottom: 1.25rem; line-height: 1.5; }
.aicfg-modal-btns { display: flex; justify-content: flex-end; gap: 0.5rem; }

/* ---- Transitions ---- */
.modal-enter-active, .modal-leave-active { transition: opacity 0.2s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.msg-enter-active, .msg-leave-active { transition: opacity 0.2s ease, transform 0.2s ease; }
.msg-enter-from, .msg-leave-to { opacity: 0; transform: translateY(-0.25rem); }

/* ---- Reduced motion ---- */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
</style>
```

## src/views/ChainInstancesPage.vue

```html
<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import {
  Dialog,
  DialogPanel,
  DialogTitle,
  TransitionRoot,
  TransitionChild,
} from '@headlessui/vue'
import DataTable from '../components/DataTable.vue'
import StatusBadge from '../components/StatusBadge.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import TipIcon from '../components/TipIcon.vue'
import { listInstances, getInstance, createInstances, cancelInstance, retryInstance } from '../api/chains.js'
import { listTemplates } from '../api/chains.js'
import { listAccounts } from '../api/accounts.js'
import { listDevices } from '../api/devices.js'
import { listGroups } from '../api/accountGroups.js'
import { formatDate } from '../utils/format.js'
import { useToastStore } from '../stores/toast.js'
import { useWebSocket } from '../composables/useWebSocket.js'

const statusMap = {
  pending: '待执行',
  running: '执行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

// --- Data state ---
const instances = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const statusFilter = ref('')

// --- Create dialog state ---
const showCreateDialog = ref(false)
const creating = ref(false)
const createError = ref(null)
const templates = ref([])
const accounts = ref([])
const groups = ref([])
const devices = ref([])

const createForm = reactive({
  template_id: '',
  selectionMode: 'accounts', // 'accounts' or 'groups'
  account_ids: [],
  group_ids: [],
  device_id: '',
})

// --- Detail dialog state ---
const showDetailDialog = ref(false)
const detailInstance = ref(null)
const detailLoading = ref(false)

// --- Cancel / Retry ---
const showCancelDialog = ref(false)
const cancellingInstance = ref(null)
const cancelling = ref(false)

// --- Page-level error ---
const pageError = ref(null)

const toast = useToastStore()

// --- WebSocket ---
function wsUrl() {
  const token = localStorage.getItem('token') || ''
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/api/devices/ws/pair-events?token=${encodeURIComponent(token)}`
}
useWebSocket(wsUrl, {
  onMessage(msg) {
    if (msg.event === 'chains_changed') fetchInstances()
  },
})

// --- Table columns ---
const columns = [
  { key: 'template_name', label: '模板' },
  { key: 'account_nickname', label: '账号' },
  { key: 'device_name', label: '设备' },
  { key: 'current_step', label: '当前步骤' },
  { key: 'status', label: '状态' },
  { key: 'created_at', label: '创建时间' },
  { key: 'actions', label: '操作', headerClass: 'text-right', cellClass: 'text-right' },
]

// --- Fetch instances ---
async function fetchInstances() {
  loading.value = true
  try {
    const skip = (page.value - 1) * pageSize
    const params = { skip, limit: pageSize }
    if (statusFilter.value) params.status = statusFilter.value
    const res = await listInstances(params)
    instances.value = res.data.instances || []
    total.value = res.data.total || 0
  } catch (e) {
    toast.error('加载实例列表失败')
    instances.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handlePageChange(p) {
  page.value = p
  fetchInstances()
}

watch(statusFilter, () => {
  page.value = 1
  fetchInstances()
})

// --- Create dialog ---
async function openCreateDialog() {
  createForm.template_id = ''
  createForm.selectionMode = 'accounts'
  createForm.account_ids = []
  createForm.group_ids = []
  createForm.device_id = ''
  createError.value = null
  showCreateDialog.value = true
  await Promise.all([fetchTemplatesForSelect(), fetchAccountsForSelect(), fetchGroupsForSelect(), fetchDevicesForSelect()])
}

async function fetchTemplatesForSelect() {
  try {
    const res = await listTemplates({ limit: 100 })
    templates.value = res.data.templates || []
  } catch (e) {
    templates.value = []
  }
}

async function fetchAccountsForSelect() {
  try {
    const res = await listAccounts({ limit: 200 })
    accounts.value = (res.data.accounts || []).filter(a => a.status === 'active')
  } catch (e) {
    accounts.value = []
  }
}

async function fetchGroupsForSelect() {
  try {
    const res = await listGroups({ limit: 100 })
    groups.value = res.data.groups || []
  } catch (e) {
    groups.value = []
  }
}

async function fetchDevicesForSelect() {
  try {
    const res = await listDevices({ limit: 100 })
    devices.value = (res.data.devices || []).filter(d => d.status === 'online')
  } catch (e) {
    devices.value = []
  }
}

async function handleCreate() {
  if (!createForm.template_id) {
    createError.value = '请选择模板'
    return
  }
  if (createForm.selectionMode === 'accounts' && createForm.account_ids.length === 0) {
    createError.value = '请选择至少一个账号'
    return
  }
  if (createForm.selectionMode === 'groups' && createForm.group_ids.length === 0) {
    createError.value = '请选择至少一个分组'
    return
  }

  creating.value = true
  createError.value = null

  const payload = { template_id: createForm.template_id }
  if (createForm.selectionMode === 'accounts') {
    payload.account_ids = createForm.account_ids
  } else {
    payload.group_ids = createForm.group_ids
  }
  if (createForm.device_id) {
    payload.device_id = createForm.device_id
  }

  try {
    const res = await createInstances(payload)
    const data = res.data
    showCreateDialog.value = false
    page.value = 1
    fetchInstances()

    if (data.skipped_busy_count > 0) {
      pageError.value = `创建成功 ${data.created_count} 个，跳过 ${data.skipped_busy_count} 个（账号繁忙）`
    }
  } catch (e) {
    createError.value = e.response?.data?.detail || '创建失败，请重试'
  } finally {
    creating.value = false
  }
}

// --- Detail dialog ---
async function openDetailDialog(instance) {
  showDetailDialog.value = true
  detailLoading.value = true
  try {
    const res = await getInstance(instance.id)
    detailInstance.value = res.data
  } catch (e) {
    pageError.value = '获取详情失败'
    showDetailDialog.value = false
  } finally {
    detailLoading.value = false
  }
}

// --- Cancel ---
function openCancelDialog(instance) {
  cancellingInstance.value = instance
  showCancelDialog.value = true
}

async function handleCancel() {
  if (!cancellingInstance.value) return
  cancelling.value = true
  try {
    await cancelInstance(cancellingInstance.value.id)
    showCancelDialog.value = false
    cancellingInstance.value = null
    fetchInstances()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '取消失败'
  } finally {
    cancelling.value = false
  }
}

// --- Retry ---
async function handleRetry(instance) {
  try {
    await retryInstance(instance.id)
    fetchInstances()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '重试失败'
  }
}

onMounted(fetchInstances)
</script>

<template>
  <div>
    <!-- Page error banner -->
    <div v-if="pageError" class="mb-4 glass-card border-red-500/30 text-red-400 rounded-xl px-4 py-3 flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-400 hover:text-red-300 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white flex items-center gap-1.5">链实例<TipIcon text="任务链的运行实例，每个实例对应一个账号正在执行或已完成的任务链" /></h1>
      <div class="flex items-center gap-3">
        <select
          v-model="statusFilter"
          class="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
        >
          <option value="">全部状态</option>
          <option value="pending">待执行</option>
          <option value="running">执行中</option>
          <option value="completed">已完成</option>
          <option value="failed">失败</option>
          <option value="cancelled">已取消</option>
        </select>
        <button
          class="btn-aurora inline-flex items-center px-4 py-2 text-sm font-medium rounded-xl"
          @click="openCreateDialog"
        >
          <span class="relative z-10 inline-flex items-center">
            <svg class="-ml-1 mr-2 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
              <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" />
            </svg>
            批量创建
          </span>
        </button>
        <TipIcon text="选择模板和账号后，为每个账号创建一个链实例。繁忙的账号会自动跳过" />
      </div>
    </div>

    <!-- Data Table -->
    <DataTable
      :columns="columns"
      :data="instances"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      @page-change="handlePageChange"
    >
      <template #cell-current_step="{ row }">
        <div class="flex items-center gap-2">
          <span class="text-sm">{{ row.current_step }} / {{ row.total_steps }}</span>
          <div class="flex-1 bg-white/10 rounded-full h-1.5 max-w-[60px]">
            <div
              class="bg-cyan-400 h-1.5 rounded-full"
              :style="{ width: Math.round(row.current_step / row.total_steps * 100) + '%' }"
            ></div>
          </div>
        </div>
      </template>

      <template #cell-device_name="{ value }">
        <span class="text-sm" :class="value ? 'text-slate-200' : 'text-slate-500'">{{ value || '自动分配' }}</span>
      </template>

      <template #cell-status="{ value }">
        <StatusBadge :status="value" />
      </template>

      <template #cell-created_at="{ value }">
        {{ formatDate(value) }}
      </template>

      <template #cell-actions="{ row }">
        <div class="flex justify-end gap-2">
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-cyan-400 hover:text-cyan-300 hover:bg-cyan-400/10 rounded transition-colors"
            @click="openDetailDialog(row)"
          >
            详情
          </button>
          <button
            v-if="row.status === 'pending' || row.status === 'running'"
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-400/10 rounded transition-colors"
            @click="openCancelDialog(row)"
          >
            取消
          </button>
          <button
            v-if="row.status === 'failed'"
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-emerald-400 hover:text-emerald-300 hover:bg-emerald-400/10 rounded transition-colors"
            @click="handleRetry(row)"
          >
            重试
          </button>
        </div>
      </template>
    </DataTable>

    <!-- Create Dialog -->
    <TransitionRoot :show="showCreateDialog" as="template">
      <Dialog as="div" class="relative z-50" @close="showCreateDialog = false">
        <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-lg glass-card p-6 gradient-border">
                <DialogTitle class="text-lg font-medium text-white">批量创建链实例</DialogTitle>
                <div v-if="createError" class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-3 py-2 rounded-lg">
                  {{ createError }}
                </div>
                <form class="mt-4 space-y-4" @submit.prevent="handleCreate">
                  <!-- Template selection -->
                  <div>
                    <label class="block text-sm font-medium text-slate-300">选择模板 <span class="text-red-400">*</span></label>
                    <select v-model="createForm.template_id" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500">
                      <option value="" disabled>请选择模板</option>
                      <option v-for="tpl in templates" :key="tpl.id" :value="tpl.id">
                        {{ tpl.name }} ({{ tpl.steps?.length || 0 }} 步)
                      </option>
                    </select>
                  </div>

                  <!-- Selection mode -->
                  <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">账号选择方式 <TipIcon text="直接选账号=逐个选择；按分组选=选择账号分组，组内所有活跃账号都会创建实例" width="w-80" /></label>
                    <div class="flex gap-4">
                      <label class="flex items-center gap-2 cursor-pointer">
                        <input type="radio" v-model="createForm.selectionMode" value="accounts" class="text-cyan-400 focus:ring-cyan-500" />
                        <span class="text-sm text-slate-300">直接选账号</span>
                      </label>
                      <label class="flex items-center gap-2 cursor-pointer">
                        <input type="radio" v-model="createForm.selectionMode" value="groups" class="text-cyan-400 focus:ring-cyan-500" />
                        <span class="text-sm text-slate-300">按分组选</span>
                      </label>
                    </div>
                  </div>

                  <!-- Account selection -->
                  <div v-if="createForm.selectionMode === 'accounts'">
                    <label class="block text-sm font-medium text-slate-300 mb-1">选择账号</label>
                    <div class="border border-white/10 rounded-lg p-3 max-h-48 overflow-y-auto">
                      <label v-for="acct in accounts" :key="acct.id" class="flex items-center gap-2 py-1 px-2 hover:bg-white/5 rounded cursor-pointer">
                        <input type="checkbox" :value="acct.id" v-model="createForm.account_ids" class="rounded border-white/10 text-cyan-400 focus:ring-cyan-500" />
                        <span class="text-sm text-slate-300">{{ acct.nickname || acct.douyin_id || acct.id }}</span>
                      </label>
                    </div>
                  </div>

                  <!-- Group selection -->
                  <div v-if="createForm.selectionMode === 'groups'">
                    <label class="block text-sm font-medium text-slate-300 mb-1">选择分组</label>
                    <div class="border border-white/10 rounded-lg p-3 max-h-48 overflow-y-auto">
                      <div v-if="groups.length === 0" class="text-sm text-slate-500 text-center py-2">暂无分组</div>
                      <label v-for="group in groups" :key="group.id" class="flex items-center gap-2 py-1 px-2 hover:bg-white/5 rounded cursor-pointer">
                        <input type="checkbox" :value="group.id" v-model="createForm.group_ids" class="rounded border-white/10 text-cyan-400 focus:ring-cyan-500" />
                        <span class="text-sm text-slate-300">{{ group.name }} ({{ group.member_count }} 人)</span>
                      </label>
                    </div>
                  </div>

                  <!-- Device selection -->
                  <div>
                    <label class="block text-sm font-medium text-slate-300 mb-1">指定设备 <TipIcon text="可选。指定后所有任务推送到该设备执行。不指定则自动分配账号绑定的设备" /></label>
                    <select v-model="createForm.device_id" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                      <option value="">自动分配</option>
                      <option v-for="dev in devices" :key="dev.id" :value="dev.id">
                        {{ dev.name }}{{ dev.bound_account_id ? ' (已绑定)' : '' }}
                      </option>
                    </select>
                  </div>

                  <div class="flex justify-end gap-3 pt-2">
                    <button type="button" class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors" @click="showCreateDialog = false">取消</button>
                    <button type="submit" :disabled="creating" class="btn-aurora rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed">
                      <span class="relative z-10">{{ creating ? '创建中...' : '创建' }}</span>
                    </button>
                  </div>
                </form>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>

    <!-- Detail Dialog -->
    <TransitionRoot :show="showDetailDialog" as="template">
      <Dialog as="div" class="relative z-50" @close="showDetailDialog = false">
        <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-lg glass-card p-6 gradient-border">
                <DialogTitle class="text-lg font-medium text-white">
                  链实例详情
                </DialogTitle>
                <div v-if="detailLoading" class="mt-4 text-center text-slate-500">加载中...</div>
                <div v-else-if="detailInstance" class="mt-4 space-y-4">
                  <div class="grid grid-cols-2 gap-3 text-sm">
                    <div><span class="text-slate-400">模板：</span>{{ detailInstance.template_name }}</div>
                    <div><span class="text-slate-400">账号：</span>{{ detailInstance.account_nickname }}</div>
                    <div><span class="text-slate-400">设备：</span>{{ detailInstance.device_name || '自动分配' }}</div>
                    <div><span class="text-slate-400">状态：</span><StatusBadge :status="detailInstance.status" /></div>
                    <div><span class="text-slate-400">进度：</span>{{ detailInstance.current_step }} / {{ detailInstance.total_steps }}</div>
                  </div>

                  <!-- Step timeline -->
                  <div>
                    <h4 class="text-sm font-medium text-slate-300 mb-2 flex items-center gap-1.5">步骤时间线<TipIcon text="灰色=待执行，蓝色=执行中，绿色=已完成，红色=失败" /></h4>
                    <div class="space-y-2">
                      <div
                        v-for="task in (detailInstance.tasks || [])"
                        :key="task.id"
                        class="flex items-start gap-3 p-2 rounded-lg"
                        :class="{
                          'bg-emerald-500/10': task.status === 'completed',
                          'bg-cyan-400/10': task.status === 'running' || task.status === 'pending',
                          'bg-red-500/10': task.status === 'failed',
                          'bg-white/5': task.status === 'cancelled',
                        }"
                      >
                        <div class="flex-shrink-0 mt-0.5">
                          <div v-if="task.status === 'completed'" class="w-5 h-5 rounded-full bg-emerald-500 flex items-center justify-center">
                            <svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/></svg>
                          </div>
                          <div v-else-if="task.status === 'running'" class="w-5 h-5 rounded-full bg-cyan-400 animate-pulse"></div>
                          <div v-else-if="task.status === 'failed'" class="w-5 h-5 rounded-full bg-red-500 flex items-center justify-center">
                            <svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M6 18L18 6M6 6l12 12"/></svg>
                          </div>
                          <div v-else class="w-5 h-5 rounded-full bg-white/20"></div>
                        </div>
                        <div class="flex-1 min-w-0">
                          <div class="text-sm font-medium text-slate-200">步骤 {{ task.step_order }}: {{ task.type }}</div>
                          <div class="text-xs text-slate-400 mt-0.5">
                            <span v-if="task.started_at">开始: {{ formatDate(task.started_at) }}</span>
                            <span v-if="task.completed_at"> | 完成: {{ formatDate(task.completed_at) }}</span>
                          </div>
                          <div v-if="task.result" class="text-xs text-slate-400 mt-1">{{ JSON.stringify(task.result) }}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="flex justify-end mt-4">
                  <button class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors" @click="showDetailDialog = false">关闭</button>
                </div>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>

    <!-- Cancel Confirmation Dialog -->
    <ConfirmDialog
      :open="showCancelDialog"
      title="取消链实例"
      message="确定要取消该链实例吗？当前执行中的步骤也会被取消。"
      confirm-text="取消链"
      :danger="true"
      @confirm="handleCancel"
      @cancel="showCancelDialog = false"
    />
  </div>
</template>
```

## src/views/ChainTemplatesPage.vue

```html
<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import {
  Dialog,
  DialogPanel,
  DialogTitle,
  TransitionRoot,
  TransitionChild,
} from '@headlessui/vue'
import DataTable from '../components/DataTable.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import TipIcon from '../components/TipIcon.vue'
import { listTemplates, createTemplate, updateTemplate, deleteTemplate } from '../api/chains.js'
import { formatDate } from '../utils/format.js'
import { useToastStore } from '../stores/toast.js'

const typeOptions = [
  { value: 'nurture', label: '养号' },
  { value: 'search_comment', label: '搜索评论' },
  { value: 'search_like', label: '搜索点赞' },
  { value: 'search_dm', label: '搜索私信' },
  { value: 'reply_comment', label: '评论回复' },
]

const typeParamDefaults = {
  nurture: { duration: 30 },
  search_comment: { keyword: '', count: 5 },
  search_like: { keyword: '', count: 5 },
  search_dm: { keyword: '', count: 5 },
  reply_comment: { keyword: '', count: 5, video_count: 3 },
}

// --- Data state ---
const templates = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

// --- Form / Dialog state ---
const showFormDialog = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const formError = ref(null)
const editingId = ref(null)

const defaultForm = {
  name: '',
  description: '',
  steps: [],
}
const form = reactive({ ...defaultForm })

// --- Delete confirmation state ---
const showDeleteDialog = ref(false)
const deletingTemplate = ref(null)
const deleting = ref(false)

// --- Page-level error ---
const pageError = ref(null)

const toast = useToastStore()

// --- Table columns ---
const columns = [
  { key: 'name', label: '模板名称' },
  { key: 'description', label: '描述' },
  { key: 'steps_count', label: '步骤数' },
  { key: 'created_at', label: '创建时间' },
  { key: 'actions', label: '操作', headerClass: 'text-right', cellClass: 'text-right' },
]

// --- Fetch templates ---
async function fetchTemplates() {
  loading.value = true
  try {
    const skip = (page.value - 1) * pageSize
    const res = await listTemplates({ skip, limit: pageSize })
    templates.value = (res.data.templates || []).map(t => ({
      ...t,
      steps_count: t.steps?.length || 0,
    }))
    total.value = res.data.total || 0
  } catch (e) {
    toast.error('加载模板列表失败')
    templates.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handlePageChange(p) {
  page.value = p
  fetchTemplates()
}

// --- Open create dialog ---
function openCreateDialog() {
  isEditing.value = false
  editingId.value = null
  form.name = ''
  form.description = ''
  form.steps = []
  formError.value = null
  showFormDialog.value = true
}

// --- Open edit dialog ---
function openEditDialog(template) {
  isEditing.value = true
  editingId.value = template.id
  form.name = template.name || ''
  form.description = template.description || ''
  form.steps = (template.steps || []).map(s => ({ ...s }))
  formError.value = null
  showFormDialog.value = true
}

// --- Step management ---
function addStep() {
  const nextOrder = form.steps.length + 1
  form.steps.push({
    step_order: nextOrder,
    type: 'nurture',
    label: '步骤 ' + nextOrder,
    params: { duration: 30 },
  })
}

function removeStep(index) {
  form.steps.splice(index, 1)
  // Re-number steps
  form.steps.forEach((s, i) => { s.step_order = i + 1 })
}

function moveStepUp(index) {
  if (index === 0) return
  const temp = form.steps[index]
  form.steps[index] = form.steps[index - 1]
  form.steps[index - 1] = temp
  form.steps.forEach((s, i) => { s.step_order = i + 1 })
}

function moveStepDown(index) {
  if (index === form.steps.length - 1) return
  const temp = form.steps[index]
  form.steps[index] = form.steps[index + 1]
  form.steps[index + 1] = temp
  form.steps.forEach((s, i) => { s.step_order = i + 1 })
}

function onStepTypeChange(step) {
  step.params = { ...typeParamDefaults[step.type] || {} }
  step.label = typeOptions.find(o => o.value === step.type)?.label || step.type
}

// --- Save ---
async function handleSave() {
  if (!form.name.trim()) {
    formError.value = '模板名称不能为空'
    return
  }
  if (form.steps.length === 0) {
    formError.value = '至少添加一个步骤'
    return
  }

  saving.value = true
  formError.value = null

  const payload = {
    name: form.name.trim(),
    description: form.description.trim(),
    steps: form.steps,
  }

  try {
    if (isEditing.value) {
      await updateTemplate(editingId.value, payload)
    } else {
      await createTemplate(payload)
    }
    showFormDialog.value = false
    fetchTemplates()
  } catch (e) {
    formError.value =
      e.response?.data?.message ||
      e.response?.data?.detail ||
      '保存失败，请重试'
  } finally {
    saving.value = false
  }
}

// --- Delete ---
function openDeleteDialog(template) {
  deletingTemplate.value = template
  showDeleteDialog.value = true
}

async function handleDelete() {
  if (!deletingTemplate.value) return
  deleting.value = true
  try {
    await deleteTemplate(deletingTemplate.value.id)
    showDeleteDialog.value = false
    deletingTemplate.value = null
    if (templates.value.length === 1 && page.value > 1) {
      page.value--
    }
    fetchTemplates()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '删除失败，请重试'
  } finally {
    deleting.value = false
  }
}

onMounted(fetchTemplates)
</script>

<template>
  <div>
    <!-- Page error banner -->
    <div v-if="pageError" class="mb-4 glass-card border-red-500/30 text-red-400 rounded-xl px-4 py-3 flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-400 hover:text-red-300 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white flex items-center gap-1.5">任务链模板<TipIcon text="创建多步骤任务模板，定义任务链的执行顺序和参数。模板可在链实例中批量分配给多个账号" width="w-80" /></h1>
      <button
        class="btn-aurora inline-flex items-center px-4 py-2 text-sm font-medium rounded-xl"
        @click="openCreateDialog"
      >
        <span class="relative z-10 inline-flex items-center">
          <svg class="-ml-1 mr-2 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" />
          </svg>
          创建模板
        </span>
      </button>
    </div>

    <!-- Data Table -->
    <DataTable
      :columns="columns"
      :data="templates"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      @page-change="handlePageChange"
    >
      <template #cell-created_at="{ value }">
        {{ formatDate(value) }}
      </template>

      <template #cell-actions="{ row }">
        <div class="flex justify-end gap-2">
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-cyan-400 hover:text-cyan-300 hover:bg-cyan-400/10 rounded transition-colors"
            @click="openEditDialog(row)"
          >
            编辑
          </button>
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-400/10 rounded transition-colors"
            @click="openDeleteDialog(row)"
          >
            删除
          </button>
        </div>
      </template>
    </DataTable>

    <!-- Create / Edit Dialog -->
    <TransitionRoot :show="showFormDialog" as="template">
      <Dialog as="div" class="relative z-50" @close="showFormDialog = false">
        <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-2xl glass-card p-6 gradient-border">
                <DialogTitle class="text-lg font-medium text-white">
                  {{ isEditing ? '编辑模板' : '创建模板' }}
                </DialogTitle>
                <div v-if="formError" class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-3 py-2 rounded-lg">
                  {{ formError }}
                </div>
                <form class="mt-4 space-y-4" @submit.prevent="handleSave">
                  <div>
                    <label class="block text-sm font-medium text-slate-300">模板名称 <span class="text-red-400">*</span></label>
                    <input v-model="form.name" type="text" required class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="请输入模板名称" />
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-slate-300">描述</label>
                    <textarea v-model="form.description" rows="2" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="请输入模板描述"></textarea>
                  </div>

                  <!-- Steps editor -->
                  <div>
                    <div class="flex items-center justify-between mb-2">
                      <label class="text-sm font-medium text-slate-300 flex items-center gap-1.5">步骤配置<TipIcon text="定义任务链中的每个执行步骤，按顺序依次执行。每个步骤可配置不同类型的任务" width="w-80" /></label>
                      <button type="button" class="text-sm text-cyan-400 hover:text-cyan-300" @click="addStep">+ 添加步骤</button>
                    </div>
                    <div v-if="form.steps.length === 0" class="border-2 border-dashed border-white/10 rounded-lg p-6 text-center text-sm text-slate-500">
                      点击「添加步骤」开始配置任务链
                    </div>
                    <div v-else class="space-y-3">
                      <div v-for="(step, index) in form.steps" :key="index" class="border border-white/10 rounded-lg p-3 bg-white/5">
                        <div class="flex items-center justify-between mb-2">
                          <span class="text-sm font-medium text-slate-400">步骤 {{ step.step_order }}</span>
                          <div class="flex gap-1">
                            <button type="button" class="text-slate-500 hover:text-slate-300 px-1" :disabled="index === 0" @click="moveStepUp(index)">
                              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7"/></svg>
                            </button>
                            <button type="button" class="text-slate-500 hover:text-slate-300 px-1" :disabled="index === form.steps.length - 1" @click="moveStepDown(index)">
                              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
                            </button>
                            <button type="button" class="text-red-400 hover:text-red-300 px-1" @click="removeStep(index)">
                              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                            </button>
                          </div>
                        </div>
                        <div class="grid grid-cols-2 gap-2">
                          <div>
                            <label class="text-xs text-slate-400 flex items-center gap-1.5">任务类型<TipIcon text="养号=模拟真实用户提升权重；搜索评论/点赞/私信=按关键词搜索后自动操作；评论回复=回复已有评论" width="w-80" /></label>
                            <select v-model="step.type" @change="onStepTypeChange(step)" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-slate-200 placeholder-slate-500">
                              <option v-for="opt in typeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                            </select>
                          </div>
                          <div>
                            <label class="text-xs text-slate-400 flex items-center gap-1.5">步骤标签<TipIcon text="给步骤命名以便识别，如'先养号'、'再评论'，执行时会显示此标签" /></label>
                            <input v-model="step.label" type="text" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-slate-200 placeholder-slate-500" />
                          </div>
                        </div>
                        <!-- Params for the step -->
                        <div class="mt-2 grid grid-cols-2 gap-2">
                          <template v-if="step.type === 'nurture'">
                            <div>
                              <label class="text-xs text-slate-400 flex items-center gap-1.5">时长(分钟)<TipIcon text="养号步骤的执行时长" /></label>
                              <input v-model.number="step.params.duration" type="number" min="1" max="120" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-slate-200" />
                            </div>
                          </template>
                          <template v-else>
                            <div>
                              <label class="block text-xs text-slate-400">关键词</label>
                              <input v-model="step.params.keyword" type="text" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-slate-200" />
                            </div>
                            <div>
                              <label class="text-xs text-slate-400 flex items-center gap-1.5">数量<TipIcon text="搜索类任务要处理的视频/评论数量" /></label>
                              <input v-model.number="step.params.count" type="number" min="1" max="20" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-slate-200" />
                            </div>
                            <div v-if="step.type === 'reply_comment'">
                              <label class="text-xs text-slate-400 flex items-center gap-1.5">视频数<TipIcon text="要回复评论的视频数量" /></label>
                              <input v-model.number="step.params.video_count" type="number" min="1" max="10" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-slate-200" />
                            </div>
                            <div v-if="['search_comment', 'search_dm', 'reply_comment'].includes(step.type)">
                              <label class="text-xs text-slate-400 flex items-center gap-1.5">内容<TipIcon text="评论/私信的文本内容，支持 {keyword} 等变量" /></label>
                              <input v-model="step.params.content" type="text" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-slate-200" />
                            </div>
                          </template>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class="flex justify-end gap-3 pt-2">
                    <button type="button" class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors" @click="showFormDialog = false">取消</button>
                    <button type="submit" :disabled="saving" class="btn-aurora rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed">
                      <span class="relative z-10">{{ saving ? '保存中...' : '保存' }}</span>
                    </button>
                  </div>
                </form>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>

    <!-- Delete Confirmation Dialog -->
    <ConfirmDialog
      :open="showDeleteDialog"
      title="删除模板"
      :message="`确定要删除模板「${deletingTemplate?.name || ''}」吗？此操作不可撤销。`"
      confirm-text="删除"
      :danger="true"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>
```

## src/views/ChannelsPage.vue

```html
<script setup>
import { ref, onMounted } from 'vue'
import { listChannels } from '../api/channels.js'
import ChannelList from '../components/business/ChannelList.vue'
import CreateChannelDialog from '../components/CreateChannelDialog.vue'
import ChannelDetail from '../components/ChannelDetail.vue'
import PageContainer from '../components/layout/PageContainer.vue'
import { useWebSocket } from '../composables/useWebSocket.js'

const channels = ref([])
const loading = ref(true)
const showCreateDialog = ref(false)
const detailChannel = ref(null)

async function fetchChannels() {
  loading.value = true
  try {
    const resp = await listChannels()
    channels.value = resp.data.channels || []
  } catch (e) {
    console.error('Failed to fetch channels:', e)
  } finally {
    loading.value = false
  }
}

function onChannelCreated() {
  showCreateDialog.value = false
  fetchChannels()
}

function wsUrl() {
  const token = localStorage.getItem('token') || ''
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/api/devices/ws/pair-events?token=${encodeURIComponent(token)}`
}
useWebSocket(wsUrl, {
  onMessage(msg) {
    if (msg.event === 'channels_changed') fetchChannels()
  },
})

onMounted(fetchChannels)
</script>

<template>
  <PageContainer title="任务通道">
    <template #actions>
      <button @click="showCreateDialog = true" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
        创建通道
      </button>
    </template>

    <ChannelList :channels="channels" :loading="loading" @refresh="fetchChannels" @detail="detailChannel = $event" />

    <CreateChannelDialog v-if="showCreateDialog" @close="showCreateDialog = false" @created="onChannelCreated" />

    <ChannelDetail v-if="detailChannel" :channel="detailChannel" @close="detailChannel = null" @refresh="fetchChannels" />
  </PageContainer>
</template>
```

## src/views/CharactersPage.vue

```html
<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-100">角色资产库</h1>
        <p class="text-sm text-slate-400 mt-1">管理剧中角色，配置外观描述和参考图</p>
      </div>
      <div class="flex gap-2">
        <button @click="showAiGen = true" class="bg-purple-500 hover:bg-purple-400 text-white px-4 py-2 rounded-lg transition cursor-pointer text-sm" title="输入故事概要，AI 自动生成角色档案">
          AI 批量生成
        </button>
        <button @click="showCreate = true" class="bg-sky-500 hover:bg-sky-400 text-white px-4 py-2 rounded-lg transition cursor-pointer" title="创建新角色，填写描述后可通过 FLUX 自动生成角色参考图">
          + 新建角色
        </button>
      </div>
    </div>

    <div v-if="loading" class="text-slate-400 text-center py-12">加载中...</div>
    <div v-else-if="error" class="text-red-400 text-center py-12">{{ error }}</div>
    <div v-else-if="characters.length === 0" class="text-slate-500 text-center py-12">
      暂无角色<br><span class="text-xs text-slate-600 mt-1">提示：创建角色后可在系列详情中关联到具体剧集</span>
    </div>
    <div v-else class="grid grid-cols-4 gap-4">
      <div v-for="c in characters" :key="c.id"
           class="rounded-xl border border-gray-700/50 p-4 text-center hover:shadow-lg hover:shadow-sky-900/10 transition-all duration-200 cursor-pointer"
           style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);"
           :title="`${c.name} — ${c.personality || '未设置性格'}`">
        <div class="w-20 h-20 mx-auto rounded-full flex items-center justify-center text-2xl mb-3" style="background: rgba(255,255,255,0.06);">
          {{ c.name[0] }}
        </div>
        <h3 class="font-semibold text-slate-100">{{ c.name }}</h3>
        <span class="text-xs px-2 py-1 rounded mt-1 inline-block" :class="roleClass(c.role_type)">{{ roleLabel(c.role_type) }}</span>
        <div class="mt-2 text-xs text-slate-500">{{ c.gender === 'male' ? '男' : '女' }}</div>
        <div v-if="c.avatar_front_url" class="mt-2 text-xs text-emerald-400">参考图已就绪</div>
        <div v-else class="mt-2 text-xs text-yellow-400">待生成参考图</div>
      </div>
    </div>

    <!-- AI 批量生成对话框 -->
    <div v-if="showAiGen" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50" @click.self="showAiGen = false">
      <div class="rounded-xl p-6 w-full max-w-lg shadow-2xl border border-gray-700/50 max-h-[85vh] overflow-y-auto" style="background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(20px);">
        <h2 class="text-lg font-semibold text-slate-100 mb-4">AI 批量生成角色</h2>
        <p class="text-xs text-slate-500 mb-4">输入故事概要，AI 自动分析并生成角色档案。确认后批量创建。</p>
        <div class="space-y-3">
          <div>
            <textarea v-model="aiForm.text" placeholder="输入故事概要/剧本片段..." rows="4" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500/50 transition" />
            <p class="text-xs text-slate-500 mt-1 ml-1">更详细的描述可以得到更准确的角色生成结果</p>
          </div>
          <div class="flex gap-3">
            <div class="flex-1">
              <select v-model="aiForm.genre" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 cursor-pointer">
                <option v-for="g in genreOptions" :key="g.value" :value="g.value">{{ g.label }}</option>
              </select>
              <p class="text-xs text-slate-500 mt-1 ml-1">故事类型</p>
            </div>
            <div class="w-24">
              <input v-model.number="aiForm.count" type="number" min="1" max="10" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 focus:outline-none focus:ring-2 focus:ring-purple-500/50 transition" />
              <p class="text-xs text-slate-500 mt-1 ml-1">数量</p>
            </div>
          </div>
        </div>

        <div v-if="aiGenerating" class="text-center py-8">
          <div class="animate-spin w-8 h-8 border-2 border-purple-400 border-t-transparent rounded-full mx-auto mb-3"></div>
          <p class="text-sm text-slate-400">AI 正在分析故事，生成角色...</p>
        </div>

        <div v-else-if="aiResult.length" class="mt-4 space-y-2 max-h-[300px] overflow-y-auto">
          <p class="text-xs text-slate-500 mb-2">AI 生成了 {{ aiResult.length }} 个角色，勾选需要创建的：</p>
          <div v-for="(c, i) in aiResult" :key="i" class="flex items-start gap-3 rounded-lg p-3 border border-gray-700/50 hover:border-purple-500/30 transition" style="background: rgba(255,255,255,0.03);">
            <input type="checkbox" v-model="c._selected" class="mt-1" />
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="font-semibold text-slate-100">{{ c.name }}</span>
                <span class="text-xs px-2 py-0.5 rounded" :class="roleClass(c.role_type)">{{ roleLabel(c.role_type) }}</span>
                <span class="text-xs text-slate-500">{{ c.gender === 'male' ? '男' : '女' }} · {{ c.age_range }}</span>
              </div>
              <p class="text-xs text-slate-400 mt-1">性格：{{ c.personality }}</p>
              <p class="text-xs text-slate-500 mt-0.5">外貌：{{ c.appearance_desc }}</p>
              <p class="text-xs text-slate-500 mt-0.5">着装：{{ c.outfit_desc }}</p>
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-3 mt-6">
          <button @click="showAiGen = false; aiResult = []" class="px-4 py-2 rounded-lg border border-gray-600 text-slate-300 hover:bg-gray-700 transition cursor-pointer">取消</button>
          <button v-if="!aiResult.length" @click="doAiGenerate" :disabled="!aiForm.text || aiGenerating" class="px-4 py-2 bg-purple-500 hover:bg-purple-400 disabled:opacity-50 text-white rounded-lg transition cursor-pointer">{{ aiGenerating ? '生成中...' : 'AI 生成' }}</button>
          <button v-else @click="doBatchCreate" :disabled="aiBatchCreating" class="px-4 py-2 bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-white rounded-lg transition cursor-pointer">{{ aiBatchCreating ? '创建中...' : `批量创建 (${aiResult.filter(c => c._selected).length})` }}</button>
        </div>
      </div>
    </div>

    <div v-if="showCreate" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50" @click.self="showCreate = false">
      <div class="rounded-xl p-6 w-full max-w-md shadow-2xl border border-gray-700/50" style="background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(20px);">
        <h2 class="text-lg font-semibold text-slate-100 mb-4">新建角色</h2>
        <div class="space-y-3">
          <div>
            <input v-model="form.name" placeholder="角色名称" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
            <p class="text-xs text-slate-500 mt-1 ml-1">角色的显示名称</p>
          </div>
          <div class="flex gap-3">
            <div class="flex-1">
              <select v-model="form.role_type" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 cursor-pointer">
                <option v-for="r in roleOptions" :key="r.value" :value="r.value">{{ r.label }}</option>
              </select>
              <p class="text-xs text-slate-500 mt-1 ml-1">可在"系统字典"中管理角色类型</p>
            </div>
            <div>
              <select v-model="form.gender" class="rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 cursor-pointer">
                <option value="male">男</option><option value="female">女</option>
              </select>
              <p class="text-xs text-slate-500 mt-1 ml-1">性别</p>
            </div>
          </div>
          <div>
            <textarea v-model="form.appearance_desc" placeholder="外观描述 — 用于 FLUX 生成角色参考图" rows="2" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
            <p class="text-xs text-slate-500 mt-1 ml-1">描述越详细，FLUX 生成的参考图越准确</p>
          </div>
          <div>
            <textarea v-model="form.outfit_desc" placeholder="服装描述" rows="2" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </div>
          <div>
            <textarea v-model="form.personality" placeholder="性格描述 — 影响剧本中角色的对话和行为" rows="2" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
            <p class="text-xs text-slate-500 mt-1 ml-1">性格描述会被注入 LLM prompt，影响 AI 剧本生成</p>
          </div>
        </div>
        <div class="flex justify-end gap-3 mt-6">
          <button @click="showCreate = false" class="px-4 py-2 rounded-lg border border-gray-600 text-slate-300 hover:bg-gray-700 transition cursor-pointer">取消</button>
          <button @click="doCreate" class="px-4 py-2 bg-sky-500 hover:bg-sky-400 text-white rounded-lg transition cursor-pointer">创建</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { listCharacters, createCharacter, autoGenerateCharacters } from '../api/characters.js'
import { listItems } from '../api/referenceData.js'

const characters = ref([]); const loading = ref(true); const showCreate = ref(false); const showAiGen = ref(false); const error = ref('')
const roleOptions = ref([]); const genreOptions = ref([])
const aiGenerating = ref(false); const aiBatchCreating = ref(false); const aiResult = ref([])
const form = reactive({ name: '', role_type: 'protagonist', gender: 'male', appearance_desc: '', outfit_desc: '', personality: '' })
const aiForm = reactive({ text: '', genre: 'drama', count: 4 })

async function loadRoles() { try { const { data } = await listItems('character_role'); if (data.ok) { roleOptions.value = data.items; if (data.items.length) form.role_type = data.items[0].value } } catch (e) {} }
async function loadGenres() { try { const { data } = await listItems('series_genre'); if (data.ok) genreOptions.value = data.items } catch (e) {} }
async function load() { loading.value = true; error.value = ''; try { const { data } = await listCharacters(); characters.value = data.ok ? data.characters : [] } catch (e) { error.value = e.message || '加载失败' } finally { loading.value = false } }
async function doCreate() { try { await createCharacter({ ...form }); showCreate.value = false; await load() } catch (e) { error.value = e.message || '创建失败' } }
async function doAiGenerate() {
  aiGenerating.value = true; aiResult.value = []; error.value = ''
  try {
    const { data } = await autoGenerateCharacters(aiForm.text, aiForm.genre, aiForm.count)
    if (data.ok) {
      aiResult.value = (data.characters || []).map(c => ({ ...c, _selected: true }))
    } else throw new Error('生成失败')
  } catch (e) { error.value = e.response?.data?.detail || e.message || 'AI 生成失败' } finally { aiGenerating.value = false }
}
async function doBatchCreate() {
  const selected = aiResult.value.filter(c => c._selected)
  if (!selected.length) return
  aiBatchCreating.value = true; error.value = ''
  try {
    for (const c of selected) {
      await createCharacter({
        name: c.name, role_type: c.role_type, gender: c.gender,
        age_range: c.age_range, personality: c.personality,
        appearance_desc: c.appearance_desc, outfit_desc: c.outfit_desc,
        default_voice_id: c.default_voice_id,
      })
    }
    showAiGen.value = false; aiResult.value = []
    await load()
  } catch (e) { error.value = e.response?.data?.detail || e.message || '批量创建失败' } finally { aiBatchCreating.value = false }
}
function roleClass(r) { return { protagonist: 'bg-sky-900/40 text-sky-400', antagonist: 'bg-red-900/40 text-red-400', supporting: 'bg-emerald-900/40 text-emerald-400', cameo: 'bg-gray-800 text-slate-400' }[r] || 'bg-gray-800 text-slate-400' }
function roleLabel(v) { const r = roleOptions.value.find(x => x.value === v); return r ? r.label : v }
onMounted(async () => { await loadRoles(); await loadGenres(); await load() })
</script>
```

## src/views/ContentPage.vue

```html
<script setup>
import { ref, reactive, onMounted } from 'vue'
import {
  Dialog, DialogPanel, DialogTitle, TransitionRoot, TransitionChild,
} from '@headlessui/vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import EmptyState from '../components/EmptyState.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import {
  listTemplates, createTemplate, updateTemplate, deleteTemplate,
  listSensitiveWords, addSensitiveWord, deleteSensitiveWord,
  generateContent,
} from '../api/content.js'
import { formatDate } from '../utils/format.js'
import { useToastStore } from '../stores/toast.js'
import TipIcon from '../components/TipIcon.vue'
import { useWebSocket } from '../composables/useWebSocket.js'

// --- Templates state ---
const templates = ref([])
const loading = ref(false)
const pageError = ref(null)
const toast = useToastStore()

// --- WebSocket ---
function wsUrl() {
  const token = localStorage.getItem('token') || ''
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/api/devices/ws/pair-events?token=${encodeURIComponent(token)}`
}
useWebSocket(wsUrl, {
  onMessage(msg) {
    if (msg.event === 'content_changed') { fetchTemplates(); fetchWords() }
  },
})

// --- Template form dialog ---
const showFormDialog = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const formError = ref(null)
const defaultForm = { name: '', category: 'comment', body: '', variables: '' }
const form = reactive({ ...defaultForm })
const editingId = ref(null)

// --- Delete confirmation ---
const showDeleteDialog = ref(false)
const deletingTemplate = ref(null)
const deleting = ref(false)

// --- Sensitive words ---
const words = ref([])
const wordsLoading = ref(false)
const newWord = ref('')
const addingWord = ref(false)
const showWords = ref(false)

// --- AI Generate dialog ---
const showGenerateDialog = ref(false)
const generatingTemplate = ref(null)
const generateForm = reactive({ keyword: '', username: '', video_title: '' })
const generating = ref(false)
const generateResult = ref(null)
const generateError = ref(null)

const categoryLabels = { comment: '评论', dm: '私信', reply: '回复' }
const categoryColors = {
  comment: 'bg-blue-100 text-blue-800',
  dm: 'bg-green-100 text-green-800',
  reply: 'bg-purple-100 text-purple-800',
}

// --- Fetch templates ---
async function fetchTemplates() {
  loading.value = true
  try {
    const res = await listTemplates()
    templates.value = res.data.templates || []
  } catch (e) {
    toast.error('加载模板失败')
    pageError.value = e.response?.data?.detail || '加载模板失败'
    templates.value = []
  } finally {
    loading.value = false
  }
}

// --- Template CRUD ---
function openCreateDialog() {
  isEditing.value = false
  editingId.value = null
  Object.assign(form, defaultForm)
  formError.value = null
  showFormDialog.value = true
}

function openEditDialog(tpl) {
  isEditing.value = true
  editingId.value = tpl.id
  form.name = tpl.name
  form.category = tpl.category
  form.body = tpl.body
  form.variables = (tpl.variables || []).join(', ')
  formError.value = null
  showFormDialog.value = true
}

async function handleSave() {
  if (!form.name.trim()) { formError.value = '名称不能为空'; return }
  if (!form.body.trim()) { formError.value = '模板内容不能为空'; return }

  saving.value = true
  formError.value = null

  const vars = form.variables.split(',').map(v => v.trim()).filter(Boolean)
  const payload = {
    name: form.name.trim(),
    category: form.category,
    body: form.body.trim(),
    variables: vars,
  }

  try {
    if (isEditing.value) {
      await updateTemplate(editingId.value, payload)
    } else {
      await createTemplate(payload)
    }
    showFormDialog.value = false
    fetchTemplates()
  } catch (e) {
    formError.value = e.response?.data?.detail || '保存失败'
  } finally {
    saving.value = false
  }
}

function openDeleteDialog(tpl) {
  deletingTemplate.value = tpl
  showDeleteDialog.value = true
}

async function handleDelete() {
  if (!deletingTemplate.value) return
  deleting.value = true
  try {
    await deleteTemplate(deletingTemplate.value.id)
    showDeleteDialog.value = false
    deletingTemplate.value = null
    fetchTemplates()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '删除失败'
  } finally {
    deleting.value = false
  }
}

// --- Sensitive words ---
async function fetchWords() {
  wordsLoading.value = true
  try {
    const res = await listSensitiveWords()
    words.value = res.data.words || []
  } catch (e) {
    toast.error('加载敏感词库失败')
  } finally {
    wordsLoading.value = false
  }
}

async function handleAddWord() {
  const w = newWord.value.trim()
  if (!w) return
  addingWord.value = true
  try {
    await addSensitiveWord(w)
    newWord.value = ''
    fetchWords()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '添加失败'
  } finally {
    addingWord.value = false
  }
}

async function handleDeleteWord(word) {
  try {
    await deleteSensitiveWord(word.id)
    fetchWords()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '删除失败'
  }
}

// --- AI Generate ---
function openGenerateDialog(tpl) {
  generatingTemplate.value = tpl
  generateForm.keyword = ''
  generateForm.username = ''
  generateForm.video_title = ''
  generateResult.value = null
  generateError.value = null
  showGenerateDialog.value = true
}

async function handleGenerate() {
  generating.value = true
  generateError.value = null
  generateResult.value = null
  try {
    const res = await generateContent(generatingTemplate.value.id, {
      keyword: generateForm.keyword,
      username: generateForm.username,
      video_title: generateForm.video_title,
    })
    generateResult.value = res.data.content
  } catch (e) {
    generateError.value = e.response?.data?.detail || '生成失败'
  } finally {
    generating.value = false
  }
}

function copyResult() {
  if (generateResult.value) {
    navigator.clipboard.writeText(generateResult.value)
  }
}

// --- Init ---
onMounted(() => {
  fetchTemplates()
  fetchWords()
})
</script>

<template>
  <div>
    <!-- Page error banner -->
    <div v-if="pageError" class="mb-4 glass-card border-red-500/30 text-red-400 px-4 py-3 rounded-xl flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-400 hover:text-red-300 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white inline-flex items-center gap-1.5">内容管理 <TipIcon text="管理评论/私信内容模板和敏感词库" /></h1>
      <button
        class="inline-flex items-center btn-aurora text-sm font-medium rounded-xl"
        @click="openCreateDialog"
      >
        <svg class="-ml-1 mr-2 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
          <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" />
        </svg>
        <span class="relative z-10">添加模板</span>
      </button>
    </div>

    <!-- Loading -->
    <LoadingSpinner v-if="loading" />

    <!-- Empty -->
    <EmptyState v-else-if="templates.length === 0" message="暂无内容模板" />

    <!-- Template cards -->
    <div v-else class="grid gap-4 mb-8">
      <div
        v-for="tpl in templates"
        :key="tpl.id"
        class="glass-card p-5"
      >
        <div class="flex items-start justify-between">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-3 flex-wrap">
              <span class="font-semibold text-white">{{ tpl.name }}</span>
              <span :class="[categoryColors[tpl.category] || 'bg-gray-100 text-gray-800']"
                class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium">
                {{ categoryLabels[tpl.category] || tpl.category }}
              </span>
              <span v-if="tpl.variables && tpl.variables.length > 0"
                class="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700">
                {{ tpl.variables.length }} 个变量
              </span>
            </div>
            <p class="mt-2 text-sm text-slate-400 whitespace-pre-wrap">{{ tpl.body }}</p>
            <p v-if="tpl.variables && tpl.variables.length > 0" class="mt-1 text-xs text-slate-500">
              变量: {{ tpl.variables.map(v => '{' + v + '}').join(', ') }}
            </p>
          </div>
          <div class="ml-4 flex items-center gap-2 flex-shrink-0">
            <button
              class="inline-flex items-center px-3 py-1 text-sm font-medium text-emerald-400 hover:text-emerald-300 hover:bg-emerald-400/10 rounded transition-colors"
              @click="openGenerateDialog(tpl)"
            >
              AI 生成
            </button>
            <button
              class="inline-flex items-center px-3 py-1 text-sm font-medium text-cyan-400 hover:text-cyan-300 hover:bg-cyan-400/10 rounded transition-colors"
              @click="openEditDialog(tpl)"
            >
              编辑
            </button>
            <button
              class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-400/10 rounded transition-colors"
              @click="openDeleteDialog(tpl)"
            >
              删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Sensitive Words Section -->
    <div class="glass-card">
      <button
        class="w-full flex items-center justify-between px-6 py-4 text-left"
        @click="showWords = !showWords"
      >
        <h2 class="text-lg font-semibold text-slate-300 inline-flex items-center gap-1.5">敏感词库 ({{ words.length }}) <TipIcon text="包含敏感词的内容会被自动过滤不会发布，用于避免触发平台审核" /></h2>
        <svg :class="showWords ? 'rotate-180' : ''" class="w-5 h-5 text-slate-400 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      <div v-if="showWords" class="px-6 pb-4 border-t border-white/5">
        <!-- Add word input -->
        <div class="flex gap-2 mt-4 mb-4">
          <input
            v-model="newWord"
            type="text"
            class="flex-1 border border-white/10 bg-white/5 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
            placeholder="输入敏感词"
            @keyup.enter="handleAddWord"
          />
          <button
            :disabled="addingWord || !newWord.trim()"
            class="btn-aurora text-sm font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
            @click="handleAddWord"
          >
            <span class="relative z-10">添加</span>
          </button>
        </div>
        <!-- Word list -->
        <LoadingSpinner v-if="wordsLoading" />
        <div v-else-if="words.length === 0" class="text-sm text-slate-400 py-2">暂无敏感词</div>
        <div v-else class="flex flex-wrap gap-2">
          <span
            v-for="word in words"
            :key="word.id"
            class="inline-flex items-center gap-1 rounded-full bg-red-500/10 px-3 py-1 text-sm text-red-400 border border-red-500/20"
          >
            {{ word.word }}
            <button class="text-red-400 hover:text-red-600" @click="handleDeleteWord(word)">&times;</button>
          </span>
        </div>
      </div>
    </div>

    <!-- Template Create/Edit Dialog -->
    <TransitionRoot :show="showFormDialog" as="template">
      <Dialog as="div" class="relative z-50" @close="showFormDialog = false">
        <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-lg glass-card p-6 gradient-border">
                <DialogTitle class="text-lg font-medium text-white">
                  {{ isEditing ? '编辑模板' : '添加模板' }}
                </DialogTitle>
                <div v-if="formError" class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-sm px-3 py-2">
                  {{ formError }}
                </div>
                <form class="mt-4 space-y-4" @submit.prevent="handleSave">
                  <div>
                    <label for="tpl-name" class="block text-sm font-medium text-slate-300">名称 <span class="text-red-400">*</span></label>
                    <input id="tpl-name" v-model="form.name" type="text" required class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="例如：美食评论模板" />
                  </div>
                  <div>
                    <label for="tpl-category" class="flex items-center gap-1.5 text-sm font-medium text-slate-300">分类 <TipIcon text="评论=视频下方评论模板；私信=用户私信模板；回复=回复已有评论的模板" /></label>
                    <select id="tpl-category" v-model="form.category" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500">
                      <option value="comment">评论</option>
                      <option value="dm">私信</option>
                      <option value="reply">回复</option>
                    </select>
                  </div>
                  <div>
                    <label for="tpl-body" class="block text-sm font-medium text-slate-300">模板内容 <span class="text-red-400">*</span></label>
                    <textarea id="tpl-body" v-model="form.body" rows="4" required class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="支持 {keyword}、{username}、{video_title} 变量" />
                  </div>
                  <div>
                    <label for="tpl-vars" class="flex items-center gap-1.5 text-sm font-medium text-slate-300">变量 (逗号分隔) <TipIcon text="定义模板中的动态占位符。常用：keyword（搜索关键词）、username（目标用户名）、video_title（视频标题）" width="w-80" /></label>
                    <input id="tpl-vars" v-model="form.variables" type="text" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="keyword, username, video_title" />
                    <p class="mt-1 text-xs text-slate-400">在模板中使用 {变量名} 引用</p>
                  </div>
                  <div class="flex justify-end gap-3 pt-2">
                    <button type="button" class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors" @click="showFormDialog = false">取消</button>
                    <button type="submit" :disabled="saving" class="btn-aurora rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed">
                      <span class="relative z-10">{{ saving ? '保存中...' : '保存' }}</span>
                    </button>
                  </div>
                </form>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>

    <!-- Delete Confirmation -->
    <ConfirmDialog
      :open="showDeleteDialog"
      title="删除模板"
      :message="`确定要删除模板「${deletingTemplate?.name || ''}」吗？`"
      confirm-text="删除"
      :danger="true"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />

    <!-- AI Generate Dialog -->
    <TransitionRoot :show="showGenerateDialog" as="template">
      <Dialog as="div" class="relative z-50" @close="showGenerateDialog = false">
        <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-lg glass-card p-6 gradient-border">
                <DialogTitle class="text-lg font-medium text-white">AI 内容生成</DialogTitle>
                <p class="mt-1 text-sm text-slate-400">模板: {{ generatingTemplate?.name }}</p>
                <div class="mt-3 bg-white/5 border border-white/5 rounded-lg p-3 text-sm text-slate-400 whitespace-pre-wrap">{{ generatingTemplate?.body }}</div>

                <div v-if="generateError" class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-sm px-3 py-2">
                  {{ generateError }}
                </div>

                <form class="mt-4 space-y-3" @submit.prevent="handleGenerate">
                  <div>
                    <label class="flex items-center gap-1.5 text-sm font-medium text-slate-300">搜索关键词 <TipIcon text="AI 生成内容时的上下文关键词，帮助生成更相关的内容" /></label>
                    <input v-model="generateForm.keyword" type="text" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="例如：美食探店" />
                  </div>
                  <div>
                    <label class="flex items-center gap-1.5 text-sm font-medium text-slate-300">目标用户名 <TipIcon text="要互动的目标用户昵称，AI 会在生成内容中引用" /></label>
                    <input v-model="generateForm.username" type="text" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="例如：美食家小明" />
                  </div>
                  <div>
                    <label class="flex items-center gap-1.5 text-sm font-medium text-slate-300">视频标题 <TipIcon text="目标视频的标题，AI 会基于此生成相关评论内容" /></label>
                    <input v-model="generateForm.video_title" type="text" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="例如：今天去了一家超好吃的火锅店" />
                  </div>

                  <!-- Result -->
                  <div v-if="generateResult" class="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-3">
                    <div class="flex items-start justify-between">
                      <p class="text-sm text-emerald-300 flex-1">{{ generateResult }}</p>
                      <button type="button" class="ml-2 text-emerald-400 hover:text-emerald-300 text-xs" @click="copyResult">复制</button>
                    </div>
                  </div>

                  <div class="flex justify-end gap-3 pt-2">
                    <button type="button" class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors" @click="showGenerateDialog = false">关闭</button>
                    <button type="submit" :disabled="generating" class="rounded-lg bg-gradient-to-r from-emerald-600 to-emerald-500 px-4 py-2 text-sm font-medium text-white hover:from-emerald-500 hover:to-emerald-400 shadow-lg shadow-emerald-500/25 disabled:opacity-50 disabled:cursor-not-allowed">
                      {{ generating ? '生成中...' : 'AI 生成' }}
                    </button>
                  </div>
                </form>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>
  </div>
</template>
```

## src/views/DashboardPage.vue

```html
<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { Chart, registerables } from 'chart.js'
import { getDashboard, getRealtimeStats } from '../api/stats.js'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import { useToastStore } from '../stores/toast.js'
import { usePolling } from '../composables/usePolling.js'

Chart.register(...registerables)

const loading = ref(true)
const error = ref(null)

const accounts = ref({ total: 0, active: 0, risk_controlled: 0 })
const devices = ref({ total: 0, online: 0 })
const tasks = ref({ total: 0, pending: 0, running: 0, completed: 0, failed: 0, cancelled: 0 })
const realtime = ref({ online_devices: 0, running_tasks: 0, pending_tasks: 0 })

const toast = useToastStore()

let taskChart = null
let deviceChart = null

async function fetchDashboardData() {
  try {
    const [dashRes, rtRes] = await Promise.all([getDashboard(), getRealtimeStats()])
    const dash = dashRes.data
    accounts.value = dash.accounts || accounts.value
    devices.value = dash.devices || devices.value
    tasks.value = dash.tasks || tasks.value
    realtime.value = rtRes.data || realtime.value
    error.value = null
    await nextTick()
    updateCharts()
  } catch (e) {
    toast.error('加载仪表盘数据失败')
    error.value = e.response?.data?.message || '加载仪表盘数据失败'
  } finally {
    loading.value = false
  }
}

function createSparkline(canvasId, data, color) {
  const canvas = document.getElementById(canvasId)
  if (!canvas) return null
  const ctx = canvas.getContext('2d')
  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map((_, i) => i),
      datasets: [{
        data,
        borderColor: color,
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0.4,
        fill: false,
      }],
    },
    options: {
      responsive: false,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: {
        x: { display: false },
        y: { display: false, min: Math.min(...data) * 0.8 },
      },
      animation: { duration: 600, easing: 'easeOutQuart' },
    },
  })
}

function updateCharts() {
  // Dummy history — in production, fetch real history from API
  const t = tasks.value
  const d = realtime.value
  const taskHistory = [t.pending || 0, t.running || 0, t.completed || 0, t.failed || 0, t.cancelled || 0]
  const deviceHistory = [Math.max(0, d.online_devices - 2), Math.max(0, d.online_devices - 1), d.online_devices, d.online_devices, d.online_devices]

  if (taskChart) { taskChart.data.datasets[0].data = taskHistory; taskChart.update() }
  else { taskChart = createSparkline('task-spark', taskHistory, '#f59e0b') }

  if (deviceChart) { deviceChart.data.datasets[0].data = deviceHistory; deviceChart.update() }
  else { deviceChart = createSparkline('device-spark', deviceHistory, '#34d399') }
}

const taskCompletionRate = () => tasks.value.total ? Math.round((tasks.value.completed / tasks.value.total) * 100) : 0
const deviceOnlineRate = () => devices.value.total ? Math.round((realtime.value.online_devices / devices.value.total) * 100) : 0

usePolling(fetchDashboardData, 10000)

onUnmounted(() => {
  if (taskChart) taskChart.destroy()
  if (deviceChart) deviceChart.destroy()
})
</script>

<template>
  <div>
    <LoadingSpinner v-if="loading" />

    <div v-else-if="error" class="card border-red-500/30 text-red-400 px-4 py-3 mb-6">
      {{ error }}
      <button class="ml-2 underline text-red-300 hover:text-red-200" @click="loading = true; fetchDashboardData()">重试</button>
    </div>

    <!-- Bento Grid Dashboard -->
    <div v-else class="space-y-4">
      <!-- Row 1: Hero + Sparklines -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <!-- Hero: 账号总数 (2 cols) -->
        <router-link to="/accounts" class="stat-card lg:col-span-2 no-underline cursor-pointer group">
          <span class="stat-label">账号总数</span>
          <div class="flex items-end justify-between mt-2">
            <span class="stat-value text-6xl animate-count" style="background: linear-gradient(135deg, var(--accent-400), #fff); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
              {{ accounts.total }}
            </span>
            <div class="flex gap-6 text-sm">
              <span class="flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-emerald-400"></span><span class="text-emerald-400 font-semibold tabular-nums">{{ accounts.active }}</span><span class="text-slate-500">活跃</span></span>
              <span class="flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-red-400"></span><span class="text-red-400 font-semibold tabular-nums">{{ accounts.risk_controlled }}</span><span class="text-slate-500">风控</span></span>
            </div>
          </div>
        </router-link>

        <!-- 设备在线率 + Sparkline (1 col) -->
        <router-link to="/devices" class="stat-card no-underline cursor-pointer group">
          <span class="stat-label">在线设备</span>
          <div class="flex items-baseline gap-2 mt-1">
            <span class="text-4xl tabular-nums" style="font-family: var(--font-mono); font-weight: 700; color: var(--status-online);">{{ realtime.online_devices }}</span>
            <span class="text-base text-slate-500">/ {{ devices.total }}</span>
          </div>
          <div class="mt-2 w-full h-1 rounded-full bg-white/5">
            <div class="h-full rounded-full transition-all duration-700" style="background: linear-gradient(90deg, #34d399, #22d3ee);" :style="{ width: deviceOnlineRate() + '%' }"></div>
          </div>
          <div class="mt-3 h-12">
            <canvas id="device-spark" width="200" height="48"></canvas>
          </div>
        </router-link>
      </div>

      <!-- Row 2: Tasks + Quick Actions -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <!-- 运行中 -->
        <router-link to="/tasks" class="stat-card no-underline cursor-pointer group">
          <span class="stat-label">运行中</span>
          <div class="flex items-center gap-2 mt-1">
            <span class="stat-value text-5xl" style="color: var(--amber-400);">{{ realtime.running_tasks }}</span>
            <span class="flex gap-0.5 mt-2">
              <span class="w-1 h-4 rounded-full bg-amber-400 animate-pulse"></span>
              <span class="w-1 h-4 rounded-full bg-amber-400 animate-pulse" style="animation-delay: 0.2s;"></span>
            </span>
          </div>
          <div class="mt-3 h-12">
            <canvas id="task-spark" width="160" height="48"></canvas>
          </div>
        </router-link>

        <!-- 完成率 Donut -->
        <router-link to="/tasks" class="stat-card no-underline cursor-pointer group flex flex-col items-center">
          <span class="stat-label self-start">任务完成率</span>
          <svg class="w-24 h-24 -rotate-90 mt-2" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="40" fill="none" stroke="rgba(255,255,255,0.04)" stroke-width="8" />
            <circle cx="50" cy="50" r="40" fill="none" stroke="url(#donutGrad)" stroke-width="8" stroke-linecap="round"
              :stroke-dasharray="2 * Math.PI * 40"
              :stroke-dashoffset="2 * Math.PI * 40 * (1 - taskCompletionRate() / 100)"
              class="transition-all duration-1000" />
            <defs>
              <linearGradient id="donutGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="#22d3ee" />
                <stop offset="100%" stop-color="#34d399" />
              </linearGradient>
            </defs>
          </svg>
          <span class="text-2xl font-bold mt-1" style="font-family: var(--font-mono);">{{ taskCompletionRate() }}<span class="text-xs text-slate-500">%</span></span>
          <span class="text-[10px] text-slate-500 mt-0.5"><span class="text-emerald-400">{{ tasks.completed }}</span> 完成 · <span class="text-red-400">{{ tasks.failed }}</span> 失败</span>
        </router-link>

        <!-- 待处理 -->
        <router-link to="/tasks" class="stat-card no-underline cursor-pointer group">
          <span class="stat-label">待处理</span>
          <span class="stat-value text-5xl mt-1 block" style="color: var(--status-info);">{{ realtime.pending_tasks }}</span>
          <span class="text-xs text-slate-500 mt-2 block">共 <span class="text-white font-semibold tabular-nums">{{ tasks.total }}</span> 个任务 · <span class="text-slate-500">{{ tasks.cancelled }} 已取消</span></span>
        </router-link>

        <!-- 快捷操作 -->
        <div class="stat-card flex flex-col justify-between">
          <span class="stat-label">快捷操作</span>
          <div class="flex flex-col gap-2 mt-2">
            <router-link to="/tasks" class="btn-primary w-full text-center justify-center text-sm no-underline">创建任务</router-link>
            <router-link to="/accounts" class="btn-ghost w-full text-center justify-center text-sm no-underline">添加账号</router-link>
            <router-link to="/devices" class="btn-ghost w-full text-center justify-center text-sm no-underline">查看设备</router-link>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
```

## src/views/DataCenterPage.vue

```html
<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { listComments, listUsers, listConversations } from '../api/data.js'
import { listAccounts } from '../api/accounts.js'
import { useToastStore } from '../stores/toast.js'
import { useWebSocket } from '../composables/useWebSocket.js'
import { formatDate } from '../utils/format.js'

const route = useRoute()
const router = useRouter()
const toast = useToastStore()

const tabs = [
  { key: 'comments', label: '评论采集' },
  { key: 'users', label: '用户资料' },
  { key: 'conversations', label: '私信会话' },
]
const activeTab = ref('comments')
const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20

// Filters
const searchQuery = ref('')
const filterKeyword = ref('')
const filterAccountId = ref('')
const filterStage = ref('')
const filterStatus = ref('')
const filterTaskId = ref('')
const filterPrivate = ref('')
const filterDateFrom = ref('')
const filterDateTo = ref('')
const sortBy = ref('')
const sortOrder = ref('desc')

// Ref data
const accounts = ref([])
const newDataBadge = ref({ comments: 0, users: 0, conversations: 0 })

// URL sync
watch(() => route.query.tab, (val) => {
  if (val && tabs.some(t => t.key === val)) activeTab.value = val
})
watch(() => route.query.task_id, (val) => {
  filterTaskId.value = val || ''
  if (val) fetchData()
})

function switchTab(key) {
  activeTab.value = key
  page.value = 1
  newDataBadge.value[key] = 0
  router.replace({ query: { tab: key, ...(filterTaskId.value ? { task_id: filterTaskId.value } : {}) } })
  fetchData()
}

function wsUrl() {
  const token = localStorage.getItem('token') || ''
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/api/devices/ws/pair-events?token=${encodeURIComponent(token)}`
}
const VALID_WS_TYPES = ['comments', 'users', 'conversations']
const { connect: wsConnect } = useWebSocket(wsUrl, {
  onMessage(msg) {
    if (msg.event === 'data_changed' && VALID_WS_TYPES.includes(msg.type)) {
      newDataBadge.value[msg.type] = (newDataBadge.value[msg.type] || 0) + 1
    }
  },
})

async function fetchData() {
  loading.value = true
  try {
    const params = { skip: (page.value - 1) * pageSize, limit: pageSize }
    if (searchQuery.value) params.search = searchQuery.value
    if (filterTaskId.value) params.task_id = filterTaskId.value

    let resp
    if (activeTab.value === 'comments') {
      if (filterKeyword.value) params.keyword = filterKeyword.value
      if (filterAccountId.value) params.account_id = filterAccountId.value
      resp = await listComments(params)
    } else if (activeTab.value === 'users') {
      if (filterKeyword.value) params.keyword = filterKeyword.value
      if (filterAccountId.value) params.account_id = filterAccountId.value
      if (filterPrivate.value) params.is_private = filterPrivate.value
      if (filterDateFrom.value) params.date_from = filterDateFrom.value
      if (filterDateTo.value) params.date_to = filterDateTo.value
      if (sortBy.value) { params.sort_by = sortBy.value; params.sort_order = sortOrder.value }
      resp = await listUsers(params)
    } else {
      if (filterAccountId.value) params.account_id = filterAccountId.value
      if (filterStage.value) params.stage = filterStage.value
      if (filterStatus.value) params.status = filterStatus.value
      resp = await listConversations(params)
    }
    items.value = resp.data.items || []
    total.value = resp.data.total || 0
  } catch {
    toast.error('加载数据失败')
    items.value = []
    total.value = 0
  } finally { loading.value = false }
}

function handlePageChange(p) { page.value = p; fetchData() }
function handleSearch() { page.value = 1; fetchData() }

const exporting = ref(false)
async function doExport(all) {
  exporting.value = true
  try {
    const params = {}
    if (filterTaskId.value) params.task_id = filterTaskId.value
    if (searchQuery.value) params.search = searchQuery.value

    if (activeTab.value === 'comments') {
      if (filterKeyword.value) params.keyword = filterKeyword.value
      if (filterAccountId.value) params.account_id = filterAccountId.value
    } else if (activeTab.value === 'users') {
      if (filterKeyword.value) params.keyword = filterKeyword.value
      if (filterAccountId.value) params.account_id = filterAccountId.value
      if (filterPrivate.value) params.is_private = filterPrivate.value
      if (filterDateFrom.value) params.date_from = filterDateFrom.value
      if (filterDateTo.value) params.date_to = filterDateTo.value
      if (sortBy.value) { params.sort_by = sortBy.value; params.sort_order = sortOrder.value }
    } else if (activeTab.value === 'conversations') {
      if (filterAccountId.value) params.account_id = filterAccountId.value
      if (filterStage.value) params.stage = filterStage.value
    }

    if (!all) {
      params.skip = (page.value - 1) * pageSize
      params.limit = pageSize
    }

    const token = localStorage.getItem('token') || ''
    const resp = await fetch(`/api/data/export/${activeTab.value}?${new URLSearchParams(params)}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error(err.detail || '导出失败')
    }
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const suffix = all ? 'all' : `page${page.value}`
    a.href = url
    a.download = `${activeTab.value}_${suffix}_${new Date().toISOString().slice(0, 10)}.xlsx`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    toast.success(all ? '全部导出完成' : '本页导出完成')
  } catch (e) {
    toast.error('导出失败: ' + (e.message || '未知错误'))
  } finally { exporting.value = false }
}

const avatarGradients = [
  'linear-gradient(135deg, #6366f1, #a855f7)',
  'linear-gradient(135deg, #06b6d4, #3b82f6)',
  'linear-gradient(135deg, #f59e0b, #ef4444)',
  'linear-gradient(135deg, #10b981, #06b6d4)',
  'linear-gradient(135deg, #ec4899, #f97316)',
  'linear-gradient(135deg, #8b5cf6, #3b82f6)',
  'linear-gradient(135deg, #14b8a6, #84cc16)',
  'linear-gradient(135deg, #f43f5e, #a855f7)',
]
function avatarGradient(name) {
  if (!name) return avatarGradients[0]
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
  return avatarGradients[Math.abs(hash) % avatarGradients.length]
}

const stageBadgeClass = (s) => ({
  qualifying: 'bg-blue-500/20 text-blue-300',
  nurturing: 'bg-emerald-500/20 text-emerald-300',
  converting: 'bg-amber-500/20 text-amber-300',
  follow_up: 'bg-purple-500/20 text-purple-300',
}[s] || 'bg-slate-500/20 text-slate-300')

const stageLabel = (s) => ({
  qualifying: '触达', nurturing: '培育', converting: '转化', follow_up: '跟进',
}[s] || s)

// Init
onMounted(async () => {
  wsConnect()
  try {
    const res = await listAccounts({ limit: 100 })
    accounts.value = res.data.accounts || []
  } catch { accounts.value = [] }
  if (route.query.tab) activeTab.value = route.query.tab
  if (route.query.task_id) filterTaskId.value = route.query.task_id
  fetchData()
})
</script>

<template>
  <div>
    <h1 class="text-xl font-bold text-white mb-5">数据中心</h1>

    <!-- Tabs -->
    <div class="flex gap-1 mb-4 border-b" style="border-color: var(--border-subtle);">
      <button
        v-for="tab in tabs" :key="tab.key"
        @click="switchTab(tab.key)"
        class="relative px-4 py-2.5 text-sm font-medium transition-colors duration-200 cursor-pointer"
        :class="activeTab === tab.key ? 'text-sky-300' : 'text-slate-400 hover:text-slate-200'"
      >
        {{ tab.label }}
        <span v-if="newDataBadge[tab.key]" class="ml-1.5 px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-sky-500 text-white">{{ newDataBadge[tab.key] > 99 ? '99+' : newDataBadge[tab.key] }}</span>
        <div v-if="activeTab === tab.key" class="absolute bottom-0 left-0 right-0 h-0.5 rounded-t-full" style="background: linear-gradient(90deg, var(--accent-500), var(--accent-400));"></div>
      </button>
    </div>

    <!-- Filters -->
    <div class="flex items-center gap-3 mb-4 flex-wrap">
      <input v-model="searchQuery" @keyup.enter="handleSearch" placeholder="搜索..." class="w-40 rounded-lg border px-3 py-1.5 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);" />

      <input v-if="activeTab === 'comments' || activeTab === 'users'" v-model="filterKeyword" @keyup.enter="handleSearch" placeholder="行业/关键词" class="w-32 rounded-lg border px-3 py-1.5 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);" />

      <select v-model="filterAccountId" @change="handleSearch" class="rounded-lg border px-3 py-1.5 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);">
        <option value="">全部账号</option>
        <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.nickname || a.douyin_id || a.id }}</option>
      </select>

      <select v-if="activeTab === 'conversations'" v-model="filterStage" @change="handleSearch" class="rounded-lg border px-3 py-1.5 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);">
        <option value="">全部阶段</option>
        <option value="qualifying">触达</option>
        <option value="nurturing">培育</option>
        <option value="converting">转化</option>
        <option value="follow_up">跟进</option>
      </select>

      <span v-if="filterTaskId" class="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-sky-500/20 text-sky-300">
        任务: {{ filterTaskId.slice(0, 8) }}...
        <button @click="filterTaskId = ''; router.replace({ query: { tab: activeTab } }); fetchData()" class="hover:text-sky-100">&times;</button>
      </span>

      <div class="ml-auto flex gap-1.5">
        <button @click="doExport(false)" :disabled="exporting"
          class="px-3 py-1.5 text-sm rounded-lg border transition cursor-pointer"
          :class="exporting ? 'opacity-50 cursor-not-allowed' : 'hover:bg-sky-500/10 hover:border-sky-500/30'"
          style="border-color: var(--border-default); color: var(--text-secondary);">
          {{ exporting ? '...' : '导出本页' }}
        </button>
        <button @click="doExport(true)" :disabled="exporting"
          class="px-3 py-1.5 text-sm rounded-lg border transition cursor-pointer"
          :class="exporting ? 'opacity-50 cursor-not-allowed' : 'hover:bg-sky-500/10 hover:border-sky-500/30'"
          style="border-color: var(--border-default); color: var(--accent-400);">
          {{ exporting ? '...' : '导出全部' }}
        </button>
      </div>
    </div>

    <!-- Comments Tab -->
    <div v-if="activeTab === 'comments'">
      <div v-if="loading" class="flex items-center justify-center py-16">
        <svg class="animate-spin h-7 w-7 text-cyan-400/60" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
      </div>
      <div v-else-if="items.length === 0" class="flex flex-col items-center justify-center py-16 text-slate-400">
        <div class="relative mb-4">
          <div class="absolute inset-0 rounded-full blur-xl opacity-20" style="background: var(--accent-glow-soft);"></div>
          <svg class="h-14 w-14 relative opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
        </div>
        <p class="text-sm text-slate-500">暂无评论数据</p>
      </div>
      <div v-else class="card overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr>
                <th class="px-4 py-3 text-left">昵称</th>
                <th class="px-4 py-3 text-left w-[18%]">评论内容</th>
                <th class="px-4 py-3 text-left w-[18%]">AI回复</th>
                <th class="px-4 py-3 text-left">关键词</th>
                <th class="px-4 py-3 text-right w-14">点赞</th>
                <th class="px-4 py-3 text-left">IP属地</th>
                <th class="px-4 py-3 text-left">意向省份</th>
                <th class="px-4 py-3 text-left">意向城市</th>
                <th class="px-4 py-3 text-left">意向景点</th>
                <th class="px-4 py-3 text-center w-14">作者</th>
                <th class="px-4 py-3 text-center w-16">来源</th>
                <th class="px-4 py-3 text-right w-24">评论时间</th>
                <th class="px-4 py-3 text-right w-24">采集时间</th>
              </tr>
            </thead>
            <tbody class="divide-y" style="border-color: var(--border-subtle);">
              <tr v-for="item in items" :key="item.id" class="group transition-colors duration-150" style="background: transparent;">
                <td class="px-4 py-3">
                  <span class="text-slate-200 font-medium">{{ item.nickname }}</span>
                </td>
                <td class="px-4 py-3">
                  <span class="text-slate-400 line-clamp-2 text-xs leading-relaxed" :title="item.content">{{ item.content }}</span>
                </td>
                <td class="px-4 py-3">
                  <span v-if="item.ai_reply" class="text-emerald-400/80 line-clamp-2 text-xs leading-relaxed" :title="item.ai_reply">{{ item.ai_reply }}</span>
                  <span v-else class="text-slate-600">-</span>
                </td>
                <td class="px-4 py-3">
                  <span v-if="item.keyword" class="inline-block text-[11px] px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400/80">{{ item.keyword }}</span>
                  <span v-else class="text-slate-600">-</span>
                </td>
                <td class="px-4 py-3 text-right font-mono text-xs tabular-nums" :class="item.like_count > 0 ? 'text-amber-400/80' : 'text-slate-600'">{{ item.like_count || '0' }}</td>
                <td class="px-4 py-3 text-xs text-slate-500">{{ item.location || '-' }}</td>
                <td class="px-4 py-3 text-xs">
                  <span v-if="item.intended_province" class="text-amber-300/80">{{ item.intended_province }}</span>
                  <span v-else class="text-slate-600">-</span>
                </td>
                <td class="px-4 py-3 text-xs">
                  <span v-if="item.intended_city" class="text-purple-300/80">{{ item.intended_city }}</span>
                  <span v-else class="text-slate-600">-</span>
                </td>
                <td class="px-4 py-3 text-xs">
                  <span v-if="item.intended_attraction" class="text-cyan-300/80">{{ item.intended_attraction }}</span>
                  <span v-else class="text-slate-600">-</span>
                </td>
                <td class="px-4 py-3 text-center">
                  <span v-if="item.is_author" class="inline-block text-[10px] px-1.5 py-0.5 rounded font-medium" style="background: rgba(245,158,11,0.15); color: #fbbf24;">作者</span>
                  <span v-else class="text-slate-600">-</span>
                </td>
                <td class="px-4 py-3 text-center">
                  <span class="inline-block text-[10px] px-1.5 py-0.5 rounded font-medium" :class="item.data_source_type === 1 ? 'bg-rose-500/15 text-rose-400' : 'bg-slate-500/10 text-slate-500'">{{ item.data_source_type === 1 ? '带货' : '普通' }}</span>
                </td>
                <td class="px-4 py-3 text-right text-xs text-slate-500 tabular-nums whitespace-nowrap">{{ item.time_str ? formatDate(item.time_str) : '-' }}</td>
                <td class="px-4 py-3 text-right text-xs text-slate-500 tabular-nums whitespace-nowrap">{{ formatDate(item.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Users Tab -->
    <div v-if="activeTab === 'users'">
      <!-- User-specific filters -->
      <div class="flex items-center gap-3 mb-4 flex-wrap">
        <select v-model="filterPrivate" @change="handleSearch" class="rounded-lg border px-3 py-1.5 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);">
          <option value="">全部账号</option>
          <option value="no">公开账号</option>
          <option value="yes">私密账号</option>
        </select>
        <input type="date" v-model="filterDateFrom" @change="handleSearch" class="rounded-lg border px-3 py-1.5 text-sm w-36" title="采集开始日期" />
        <span class="text-slate-500 text-xs">至</span>
        <input type="date" v-model="filterDateTo" @change="handleSearch" class="rounded-lg border px-3 py-1.5 text-sm w-36" title="采集结束日期" />
        <select v-model="sortBy" @change="handleSearch" class="rounded-lg border px-3 py-1.5 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);">
          <option value="">默认排序</option>
          <option value="fans_count">粉丝数</option>
          <option value="likes_count">获赞数</option>
          <option value="follow_count">关注数</option>
          <option value="works_count">作品数</option>
          <option value="created_at">采集时间</option>
        </select>
        <button
          v-if="sortBy"
          @click="sortOrder = sortOrder === 'desc' ? 'asc' : 'desc'; fetchData()"
          class="rounded-lg border px-2.5 py-1.5 text-sm transition cursor-pointer"
          style="border-color: var(--border-default); color: var(--text-secondary);"
          :class="sortOrder === 'asc' ? 'bg-sky-500/10 border-sky-500/30 text-sky-300' : 'hover:bg-white/5'"
          :title="sortOrder === 'desc' ? '降序' : '升序'"
        >
          <svg class="w-3.5 h-3.5 inline transition-transform duration-200" :class="sortOrder === 'asc' ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7"/></svg>
          {{ sortOrder === 'desc' ? '降序' : '升序' }}
        </button>
      </div>

      <div v-if="loading" class="flex items-center justify-center py-16">
        <svg class="animate-spin h-7 w-7 text-cyan-400/60" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
      </div>
      <div v-else-if="items.length === 0" class="flex flex-col items-center justify-center py-16 text-slate-400">
        <div class="relative mb-4">
          <div class="absolute inset-0 rounded-full blur-xl opacity-20" style="background: var(--accent-glow-soft);"></div>
          <svg class="h-14 w-14 relative opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
        </div>
        <p class="text-sm text-slate-500">暂无用户数据</p>
      </div>
      <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <div v-for="user in items" :key="user.id"
             class="group cursor-default transition-all duration-300 rounded-2xl overflow-hidden"
             style="background: linear-gradient(145deg, rgba(15,23,42,0.9), rgba(30,41,59,0.6)); border: 1px solid rgba(148,163,184,0.06);">
          <!-- Top accent bar -->
          <div class="h-1 w-full" :style="{ background: avatarGradient(user.nickname) }"></div>

          <!-- Header: Avatar + Identity -->
          <div class="flex items-start gap-3 px-4 pt-4 pb-3">
            <div class="relative shrink-0">
              <img v-if="user.avatar_url" :src="user.avatar_url" class="w-12 h-12 rounded-full object-cover ring-2 ring-white/10" :alt="user.nickname" />
              <div v-else class="w-12 h-12 rounded-full flex items-center justify-center text-base font-bold text-white shadow-lg"
                   :style="{ backgroundImage: avatarGradient(user.nickname) }">
                {{ (user.nickname || '?')[0] }}
              </div>
              <span v-if="user.is_private === '是'" class="absolute -bottom-0.5 -right-0.5 w-4 h-4 rounded-full bg-rose-500 flex items-center justify-center ring-2 ring-slate-900" title="私密账号">
                <svg class="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/></svg>
              </span>
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-1.5 mb-0.5">
                <p class="text-sm font-semibold text-white truncate">{{ user.nickname || '未知' }}</p>
                <span class="text-[9px] px-1.5 py-0.5 rounded-full font-medium shrink-0 tracking-wide"
                      :class="user.data_source_type === 1 ? 'bg-pink-500/15 text-pink-400 border border-pink-500/20' : 'bg-slate-500/10 text-slate-400 border border-slate-500/10'">
                  {{ user.data_source_type === 1 ? '带货' : '普通' }}
                </span>
              </div>
              <p class="text-[11px] text-slate-500 font-mono truncate">抖音号 {{ user.douyin_id || '-' }}</p>
            </div>
          </div>

          <!-- Stats grid -->
          <div class="grid grid-cols-4 gap-px mx-4 mb-3 rounded-xl overflow-hidden" style="background: rgba(255,255,255,0.03);">
            <div class="text-center py-2.5" style="background: rgba(15,23,42,0.6);">
              <p class="text-base font-bold tabular-nums" style="background: linear-gradient(135deg, #818cf8, #6366f1); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{{ user.fans_count || '-' }}</p>
              <p class="text-[10px] text-slate-500 mt-0.5">粉丝</p>
            </div>
            <div class="text-center py-2.5" style="background: rgba(15,23,42,0.6);">
              <p class="text-base font-bold tabular-nums" style="background: linear-gradient(135deg, #fbbf24, #f59e0b); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{{ user.likes_count || '-' }}</p>
              <p class="text-[10px] text-slate-500 mt-0.5">获赞</p>
            </div>
            <div class="text-center py-2.5" style="background: rgba(15,23,42,0.6);">
              <p class="text-base font-bold tabular-nums text-slate-300">{{ user.follow_count || '-' }}</p>
              <p class="text-[10px] text-slate-500 mt-0.5">关注</p>
            </div>
            <div class="text-center py-2.5" style="background: rgba(15,23,42,0.6);">
              <p class="text-base font-bold tabular-nums text-slate-300">{{ user.works_count || '-' }}</p>
              <p class="text-[10px] text-slate-500 mt-0.5">作品</p>
            </div>
          </div>

          <!-- Destination -->
          <div v-if="user.intended_province || user.intended_city || user.intended_attraction"
               class="mx-4 mb-3 px-3 py-2 rounded-xl flex items-center gap-2 text-xs"
               style="background: rgba(139,92,246,0.06); border: 1px solid rgba(139,92,246,0.1);">
            <svg class="w-3.5 h-3.5 text-purple-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
            <span class="text-slate-400 truncate">{{ [user.intended_province, user.intended_city, user.intended_attraction].filter(Boolean).join(' · ') }}</span>
          </div>

          <!-- Footer: Meta -->
          <div class="flex items-center gap-2 text-[11px] text-slate-500 px-4 py-2.5 border-t" style="border-color: rgba(255,255,255,0.04);">
            <span v-if="user.gender || user.age" class="inline-flex items-center gap-1">
              <svg class="w-3 h-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
              <template v-if="user.gender">{{ user.gender }} </template><template v-if="user.age">{{ user.age }}</template>
            </span>
            <span class="opacity-30" v-if="(user.gender || user.age) && user.ip_location">|</span>
            <span v-if="user.ip_location" class="inline-flex items-center gap-1 truncate">
              <svg class="w-3 h-3 opacity-50 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
              {{ user.ip_location }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Conversations Tab -->
    <div v-if="activeTab === 'conversations'">
      <div v-if="loading" class="flex items-center justify-center py-16">
        <svg class="animate-spin h-7 w-7 text-cyan-400/60" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
      </div>
      <div v-else-if="items.length === 0" class="flex flex-col items-center justify-center py-16 text-slate-400">
        <div class="relative mb-4">
          <div class="absolute inset-0 rounded-full blur-xl opacity-20" style="background: var(--accent-glow-soft);"></div>
          <svg class="h-14 w-14 relative opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
        </div>
        <p class="text-sm text-slate-500">暂无私信数据</p>
      </div>
      <div v-else class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <div v-for="conv in items" :key="conv.id" class="card p-4 hover:border-sky-500/30 transition-colors cursor-default">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-3 min-w-0">
              <div class="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0" style="background: linear-gradient(135deg, #06b6d4, #3b82f6);">
                {{ (conv.recipient_nickname || '?')[0] }}
              </div>
              <div class="min-w-0">
                <p class="text-sm font-semibold text-slate-200 truncate">{{ conv.recipient_nickname }}</p>
                <p class="text-[11px] text-slate-500 font-mono truncate">{{ conv.recipient_douyin_id || '-' }}</p>
              </div>
            </div>
            <span class="px-2 py-0.5 text-[10px] rounded-full font-medium shrink-0" :class="stageBadgeClass(conv.current_stage)">
              {{ stageLabel(conv.current_stage) }}
            </span>
          </div>
          <p class="text-xs text-slate-400 line-clamp-2 mb-3 min-h-[2rem]">{{ conv.last_dm_content || '暂无消息' }}</p>
          <div class="flex items-center justify-between text-[11px] text-slate-500 pt-3 border-t" style="border-color: var(--border-subtle);">
            <span>共 {{ conv.total_dm_count || 0 }} 条</span>
            <span>{{ conv.last_dm_at ? formatDate(conv.last_dm_at) : '-' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="total > pageSize" class="flex items-center justify-between mt-6">
      <span class="text-sm text-slate-500">共 {{ total }} 条</span>
      <div class="flex gap-2">
        <button :disabled="page <= 1" @click="handlePageChange(page - 1)" class="px-3 py-1.5 text-sm rounded-lg border disabled:opacity-30" style="border-color: var(--border-default); color: var(--text-secondary);">上一页</button>
        <span class="px-3 py-1.5 text-sm font-mono" style="color: var(--accent-400);">{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
        <button :disabled="page >= Math.ceil(total / pageSize)" @click="handlePageChange(page + 1)" class="px-3 py-1.5 text-sm rounded-lg border disabled:opacity-30" style="border-color: var(--border-default); color: var(--text-secondary);">下一页</button>
      </div>
    </div>
  </div>
</template>
```

## src/views/DevicesPage.vue

```html
<script setup>
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import {
  Dialog,
  DialogPanel,
  DialogTitle,
  TransitionRoot,
  TransitionChild,
} from '@headlessui/vue'
import DataTable from '../components/DataTable.vue'
import StatusBadge from '../components/StatusBadge.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import {
  listDevices,
  createDevice,
  updateDevice,
  deleteDevice,
  disconnectDevice,
  listPairRequests,
  approvePairRequest,
  rejectPairRequest,
} from '../api/devices.js'
import { listAccounts } from '../api/accounts.js'
import { formatDate } from '../utils/format.js'
import { useToastStore } from '../stores/toast.js'
import TipIcon from '../components/TipIcon.vue'

// --- Tab state ---
const activeTab = ref('devices') // "devices" | "pairing"

// --- Data state ---
const devices = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)

// --- Accounts list for binding dropdown ---
const accounts = ref([])
async function fetchAccounts() {
  try {
    const res = await listAccounts({ limit: 200 })
    accounts.value = res.data.accounts || []
  } catch { /* ignore */ }
}

// --- Pair requests state ---
const pairRequests = ref([])
const pairLoading = ref(false)
const pairActionLoading = ref(null) // request id being acted on
const pendingCount = computed(() => pairRequests.value.length)

// --- Form / Dialog state ---
const showFormDialog = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const formError = ref(null)

const defaultForm = {
  name: '',
  ip: '',
  bound_account_id: '',
  proxy_config: '',
}
const form = reactive({ ...defaultForm })
const editingId = ref(null)
const proxyError = ref(null)

// --- Delete confirmation state ---
const showDeleteDialog = ref(false)
const deletingDevice = ref(null)
const deleting = ref(false)

// --- Page-level error ---
const pageError = ref(null)

const toast = useToastStore()

// --- Table columns ---
const columns = [
  { key: 'name', label: '设备名称' },
  { key: 'id', label: '设备ID' },
  { key: 'ip', label: 'IP 地址' },
  { key: 'status', label: '状态' },
  { key: 'bound_account_id', label: '绑定账号' },
  { key: 'last_seen_at', label: '最近在线' },
  { key: 'actions', label: '操作', headerClass: 'text-right', cellClass: 'text-right' },
]

// --- Fetch devices ---
async function fetchDevices() {
  loading.value = true
  try {
    const skip = (page.value - 1) * pageSize
    const res = await listDevices({ skip, limit: pageSize })
    devices.value = res.data.devices || []
    total.value = res.data.total || 0
  } catch (e) {
    toast.error('加载设备列表失败')
    devices.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handlePageChange(p) {
  page.value = p
  fetchDevices()
}

// --- Fetch pair requests ---
async function fetchPairRequests() {
  pairLoading.value = true
  try {
    const res = await listPairRequests('pending')
    pairRequests.value = res.data.requests || []
  } catch (e) {
    toast.error('加载配对请求失败')
    pairRequests.value = []
  } finally {
    pairLoading.value = false
  }
}

async function handleApprove(req) {
  pairActionLoading.value = req.id
  try {
    await approvePairRequest(req.id)
    // WS will handle list update; fallback refresh if WS disconnected
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      fetchPairRequests()
      fetchDevices()
    }
  } catch (e) {
    pageError.value = e.response?.data?.detail || '审批失败，请重试'
  } finally {
    pairActionLoading.value = null
  }
}

async function handleReject(req) {
  pairActionLoading.value = req.id
  try {
    await rejectPairRequest(req.id)
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      fetchPairRequests()
    }
  } catch (e) {
    pageError.value = e.response?.data?.detail || '拒绝失败，请重试'
  } finally {
    pairActionLoading.value = null
  }
}

function switchTab(tab) {
  activeTab.value = tab
  if (tab === 'pairing') fetchPairRequests()
  else fetchDevices()
}

// --- Open create dialog ---
function openCreateDialog() {
  isEditing.value = false
  editingId.value = null
  Object.assign(form, defaultForm)
  formError.value = null
  proxyError.value = null
  showFormDialog.value = true
}

// --- Open edit dialog ---
function openEditDialog(device) {
  isEditing.value = true
  editingId.value = device.id
  form.name = device.name || ''
  form.ip = device.ip || ''
  form.bound_account_id = device.bound_account_id != null ? String(device.bound_account_id) : ''
  form.proxy_config = device.proxy_config ? JSON.stringify(device.proxy_config) : ''
  formError.value = null
  proxyError.value = null
  showFormDialog.value = true
}

// --- Save (create or update) ---
async function handleSave() {
  if (!form.name.trim()) {
    formError.value = '设备名称不能为空'
    return
  }

  saving.value = true
  formError.value = null

  const payload = {
    name: form.name.trim(),
    ip: form.ip.trim() || undefined,
  }

  if (form.proxy_config.trim()) {
    try {
      const parsed = JSON.parse(form.proxy_config)
      if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
        payload.proxy_config = parsed
        proxyError.value = null
      } else {
        proxyError.value = '代理配置需为 JSON 对象格式，如 {"server": "socks5://host:port"}'
        saving.value = false
        return
      }
    } catch {
      proxyError.value = 'JSON 格式不正确，请检查'
      saving.value = false
      return
    }
  }

  payload.bound_account_id = form.bound_account_id || null

  try {
    if (isEditing.value) {
      await updateDevice(editingId.value, payload)
    } else {
      await createDevice(payload)
    }
    showFormDialog.value = false
    fetchDevices()
  } catch (e) {
    formError.value =
      e.response?.data?.message ||
      e.response?.data?.detail ||
      '保存失败，请重试'
  } finally {
    saving.value = false
  }
}

// --- Delete ---
function openDeleteDialog(device) {
  deletingDevice.value = device
  showDeleteDialog.value = true
}

async function handleDelete() {
  if (!deletingDevice.value) return
  deleting.value = true
  try {
    await deleteDevice(deletingDevice.value.id)
    showDeleteDialog.value = false
    deletingDevice.value = null
    if (devices.value.length === 1 && page.value > 1) {
      page.value--
    }
    fetchDevices()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '删除失败，请重试'
  } finally {
    deleting.value = false
  }
}

// --- Force disconnect ---
const disconnectingId = ref(null)

async function handleDisconnect(device) {
  disconnectingId.value = device.id
  try {
    await disconnectDevice(device.id)
    // Status will update via WS event; fallback refresh
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      fetchDevices()
    }
  } catch (e) {
    pageError.value = e.response?.data?.detail || '断开失败，请重试'
  } finally {
    disconnectingId.value = null
  }
}

// --- WebSocket for real-time pair events ---
let ws = null
let wsReconnectTimer = null
let wsDisposed = false

function connectPairWS() {
  if (wsDisposed || ws) return
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const token = localStorage.getItem('token') || ''
  const wsUrl = `${proto}//${window.location.host}/api/devices/ws/pair-events?token=${encodeURIComponent(token)}`
  ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    console.log('Pair events WS connected')
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.event === 'new_pair_request') {
        // New device requesting pairing — add to list and switch tab
        pairRequests.value.unshift(data.request)
        if (activeTab.value !== 'pairing') {
          activeTab.value = 'pairing'
        }
      } else if (data.event === 'pair_approved' || data.event === 'pair_rejected') {
        // Request resolved — remove from pending list
        pairRequests.value = pairRequests.value.filter(r => r.id !== data.request_id)
        if (data.event === 'pair_approved') {
          fetchDevices() // refresh device list
        }
      } else if (data.event === 'device_status_changed') {
        if (data.status === 'deleted') {
          // Device was removed — remove from list
          devices.value = devices.value.filter(d => d.id !== data.device_id)
        } else {
          // Device status changed (e.g. went offline/online)
          const dev = devices.value.find(d => d.id === data.device_id)
          if (dev) {
            dev.status = data.status
          }
        }
      } else if (data.event === 'devices_changed') {
        fetchDevices()
      }
    } catch (e) {
      console.error('WS message parse error:', e)
    }
  }

  ws.onclose = () => {
    ws = null
    // Reconnect after 3s (only if component is still mounted)
    if (!wsDisposed) {
      wsReconnectTimer = setTimeout(connectPairWS, 3000)
    }
  }

  ws.onerror = () => {
    ws?.close()
  }
}

function disconnectPairWS() {
  wsDisposed = true
  if (wsReconnectTimer) {
    clearTimeout(wsReconnectTimer)
    wsReconnectTimer = null
  }
  if (ws) {
    ws.close()
    ws = null
  }
}

// --- Init ---
onMounted(() => {
  fetchDevices()
  fetchAccounts()
  fetchPairRequests()
  connectPairWS()
})

onUnmounted(() => {
  disconnectPairWS()
})
</script>

<template>
  <div>
    <!-- Page error banner -->
    <div v-if="pageError" class="mb-4 glass-card border-red-500/30 text-red-400 px-4 py-3 rounded-xl flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-400 hover:text-red-300 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white inline-flex items-center gap-1.5">设备管理 <TipIcon text="管理自动化设备，配置绑定关系和网络代理" /></h1>
      <button
        v-if="activeTab === 'devices'"
        class="btn-aurora inline-flex items-center px-4 py-2 text-sm font-medium rounded-xl"
        @click="openCreateDialog"
      >
        <svg
          class="-ml-1 mr-2 h-5 w-5 relative z-10"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"
          />
        </svg>
        <span class="relative z-10">添加设备</span>
      </button>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 border-b border-white/10 mb-6">
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors"
        :class="activeTab === 'devices'
          ? 'border-cyan-400 text-cyan-400'
          : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-white/20'"
        @click="switchTab('devices')"
      >
        设备列表
      </button>
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors relative"
        :class="activeTab === 'pairing'
          ? 'border-cyan-400 text-cyan-400'
          : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-white/20'"
        @click="switchTab('pairing')"
      >
        待配对
        <TipIcon text="新设备发起配对请求后需要在此审批通过才能加入系统" />
        <span
          v-if="pendingCount > 0"
          class="ml-1.5 inline-flex items-center justify-center px-1.5 py-0.5 text-xs font-bold leading-none text-white bg-red-500 rounded-full"
        >
          {{ pendingCount }}
        </span>
      </button>
    </div>

    <!-- Pair Requests List -->
    <div v-if="activeTab === 'pairing'">
      <div v-if="pairLoading" class="text-center py-12 text-slate-400">加载中...</div>
      <div v-else-if="pairRequests.length === 0" class="text-center py-12">
        <svg class="mx-auto h-12 w-12 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p class="mt-2 text-sm text-slate-400">暂无待配对设备</p>
      </div>
      <div v-else class="space-y-3">
        <div
          v-for="req in pairRequests"
          :key="req.id"
          class="glass-card p-4 flex items-center justify-between"
        >
          <div class="flex-1">
            <div class="flex items-center gap-3">
              <span class="text-sm font-semibold text-white">{{ req.device_name }}</span>
              <span class="text-xs text-slate-500 font-mono">{{ req.device_id }}</span>
            </div>
            <div class="mt-1 flex items-center gap-4 text-xs text-slate-400">
              <span v-if="req.os_version">系统: {{ req.os_version }}</span>
              <span v-if="req.app_version">版本: {{ req.app_version }}</span>
              <span>申请时间: {{ formatDate(req.created_at) }}</span>
            </div>
          </div>
          <div class="flex gap-2 ml-4">
            <button
              class="inline-flex items-center px-3 py-1.5 text-sm font-medium text-white bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 rounded-lg transition-all shadow-lg shadow-emerald-500/25 disabled:opacity-50"
              :disabled="pairActionLoading === req.id"
              @click="handleApprove(req)"
            >
              {{ pairActionLoading === req.id ? '处理中...' : '批准' }}
            </button>
            <button
              class="inline-flex items-center px-3 py-1.5 text-sm font-medium text-red-400 hover:text-red-300 border border-red-500/30 hover:bg-red-500/10 rounded-lg transition-colors disabled:opacity-50"
              :disabled="pairActionLoading === req.id"
              @click="handleReject(req)"
            >
              拒绝
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Data Table -->
    <DataTable v-if="activeTab === 'devices'"
      :columns="columns"
      :data="devices"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      @page-change="handlePageChange"
    >
      <!-- Status column -->
      <template #cell-status="{ value }">
        <StatusBadge :status="value" />
      </template>

      <!-- Bound account column -->
      <template #cell-bound_account_id="{ value }">
        <span v-if="value" class="text-slate-200">
          {{ accounts.find(a => a.id === value)?.nickname || value }}
        </span>
        <span v-else class="text-slate-500">—</span>
      </template>

      <!-- Last seen at column -->
      <template #cell-last_seen_at="{ value }">
        {{ formatDate(value) }}
      </template>

      <!-- Actions column -->
      <template #cell-actions="{ row }">
        <div class="flex justify-end gap-2">
          <button
            v-if="row.status === 'online'"
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-amber-400 hover:text-amber-300 hover:bg-amber-400/10 rounded-lg transition-colors disabled:opacity-50"
            :disabled="disconnectingId === row.id"
            @click="handleDisconnect(row)"
          >
            {{ disconnectingId === row.id ? '断开中...' : '断开' }}
          </button>
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-cyan-400 hover:text-cyan-300 hover:bg-cyan-400/10 rounded-lg transition-colors"
            @click="openEditDialog(row)"
          >
            编辑
          </button>
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-400/10 rounded-lg transition-colors"
            @click="openDeleteDialog(row)"
          >
            删除
          </button>
        </div>
      </template>
    </DataTable>

    <!-- Create / Edit Dialog -->
    <TransitionRoot :show="showFormDialog" as="template">
      <Dialog
        as="div"
        class="relative z-50"
        @close="showFormDialog = false"
      >
        <TransitionChild
          as="template"
          enter="ease-out duration-300"
          enter-from="opacity-0"
          enter-to="opacity-100"
          leave="ease-in duration-200"
          leave-from="opacity-100"
          leave-to="opacity-0"
        >
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>

        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild
              as="template"
              enter="ease-out duration-300"
              enter-from="opacity-0 scale-95"
              enter-to="opacity-100 scale-100"
              leave="ease-in duration-200"
              leave-from="opacity-100 scale-100"
              leave-to="opacity-0 scale-95"
            >
              <DialogPanel
                class="glass-card w-full max-w-lg p-6 gradient-border"
              >
                <DialogTitle class="text-lg font-medium text-white">
                  {{ isEditing ? '编辑设备' : '添加设备' }}
                </DialogTitle>

                <!-- Error message -->
                <div
                  v-if="formError"
                  class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-3 py-2 rounded-lg"
                >
                  {{ formError }}
                </div>
                <div
                  v-if="proxyError"
                  class="mt-3 bg-amber-500/10 border border-amber-500/20 text-amber-400 text-sm px-3 py-2 rounded-lg"
                >
                  {{ proxyError }}
                </div>

                <form class="mt-4 space-y-4" @submit.prevent="handleSave">
                  <!-- Name -->
                  <div>
                    <label
                      for="device-name"
                      class="block text-sm font-medium text-slate-300"
                    >
                      设备名称 <span class="text-red-400">*</span>
                    </label>
                    <input
                      id="device-name"
                      v-model="form.name"
                      type="text"
                      required
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                      placeholder="请输入设备名称"
                    />
                  </div>

                  <!-- IP -->
                  <div>
                    <label
                      for="device-ip"
                      class="block text-sm font-medium text-slate-300"
                    >
                      IP 地址
                    </label>
                    <input
                      id="device-ip"
                      v-model="form.ip"
                      type="text"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                      placeholder="例如 192.168.1.100"
                    />
                  </div>

                  <!-- Bound Account -->
                  <div>
                    <label
                      for="device-bound-account"
                      class="flex items-center gap-1.5 text-sm font-medium text-slate-300"
                    >
                      绑定账号
                      <TipIcon text="绑定后该设备只执行该账号的任务，留空为通用设备" />
                    </label>
                    <select
                      id="device-bound-account"
                      v-model="form.bound_account_id"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
                    >
                      <option value="">不绑定（通用设备）</option>
                      <option v-for="acct in accounts" :key="acct.id" :value="acct.id">
                        {{ acct.nickname || acct.douyin_id || acct.id }}
                      </option>
                    </select>
                  </div>

                  <!-- Proxy Config -->
                  <div>
                    <label
                      for="device-proxy"
                      class="flex items-center gap-1.5 text-sm font-medium text-slate-300"
                    >
                      代理配置
                      <TipIcon text="JSON 格式代理配置，如 {&quot;server&quot;: &quot;socks5://host:port&quot;, &quot;username&quot;: &quot;user&quot;, &quot;password&quot;: &quot;pass&quot;}" width="w-96" />
                    </label>
                    <textarea
                      id="device-proxy"
                      v-model="form.proxy_config"
                      rows="3"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 font-mono"
                      placeholder='{"server": "socks5://user:pass@host:port"}'
                    ></textarea>
                  </div>

                  <!-- Buttons -->
                  <div class="flex justify-end gap-3 pt-2">
                    <button
                      type="button"
                      class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors"
                      @click="showFormDialog = false"
                    >
                      取消
                    </button>
                    <button
                      type="submit"
                      :disabled="saving"
                      class="btn-aurora rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <span class="relative z-10">{{ saving ? '保存中...' : '保存' }}</span>
                    </button>
                  </div>
                </form>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>

    <!-- Delete Confirmation Dialog -->
    <ConfirmDialog
      :open="showDeleteDialog"
      title="删除设备"
      :message="`确定要删除设备「${deletingDevice?.name || ''}」吗？此操作不可撤销。`"
      confirm-text="删除"
      :danger="true"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>
```

## src/views/DictManagePage.vue

```html
<template>
  <div class="dict-manage">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-white tracking-tight">系统字典管理</h1>
      <p class="text-sm text-slate-400 mt-1.5">管理字典分类和下拉选项值，创建、编辑、删除分类及选项</p>
    </div>

    <!-- Category Tabs -->
    <div class="flex gap-2 mb-8 flex-wrap items-center">
      <button
        v-for="cat in categories" :key="cat.id"
        @click="currentCat = cat.key"
        class="cat-tab group"
        :class="currentCat === cat.key ? 'cat-tab--active' : ''"
      >
        <span class="cat-tab-label">{{ cat.label }}</span>
        <span class="cat-tab-count">{{ cat.item_count ?? 0 }}</span>
        <!-- Edit/Delete controls -->
        <span class="cat-tab-actions">
          <button @click.stop="startEditCat(cat)" class="cat-tab-action" title="编辑分类">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
          </button>
          <button @click.stop="confirmDeleteCat(cat)" class="cat-tab-action cat-tab-action--danger" title="删除分类">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
          </button>
        </span>
      </button>

      <!-- Inline add category form -->
      <div v-if="addingCat" class="cat-add-form">
        <input v-model="newCatLabel" @keyup.enter="addCategory" placeholder="分类名称"
               class="cat-add-input" ref="catLabelInput" />
        <input v-model="newCatKey" placeholder="key (可选)"
               class="cat-add-input cat-add-input--key" @keyup.enter="addCategory" />
        <button @click="addCategory" class="cat-add-btn cat-add-btn--confirm" title="确认">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/></svg>
        </button>
        <button @click="cancelAddCat" class="cat-add-btn cat-add-btn--cancel" title="取消">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
      </div>
      <button v-else @click="startAddCat" class="cat-add-trigger">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
        新增分类
      </button>
    </div>

    <!-- Edit Category Modal -->
    <Teleport to="body">
      <transition name="modal">
        <div v-if="editingCat" class="modal-overlay" @click.self="cancelEditCat">
          <div class="modal-card">
            <div class="modal-header">
              <h3 class="modal-title">编辑分类</h3>
              <button @click="cancelEditCat" class="modal-close" title="关闭">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
              </button>
            </div>
            <div class="modal-body">
              <div class="form-group">
                <label class="form-label">Key <span class="form-hint">唯一标识，不可与其他分类重复</span></label>
                <input v-model="editCatKey" class="form-input" placeholder="e.g. series_genre" />
              </div>
              <div class="form-group">
                <label class="form-label">显示名称</label>
                <input v-model="editCatLabel" class="form-input" placeholder="e.g. 系列类型" @keyup.enter="saveCategory" />
              </div>
            </div>
            <div class="modal-footer">
              <button @click="cancelEditCat" class="btn btn--secondary">取消</button>
              <button @click="saveCategory" class="btn btn--primary">保存修改</button>
            </div>
          </div>
        </div>
      </transition>
    </Teleport>

    <!-- Delete Confirmation Modal -->
    <Teleport to="body">
      <transition name="modal">
        <div v-if="deletingCat" class="modal-overlay" @click.self="deletingCat = null">
          <div class="modal-card modal-card--sm">
            <div class="modal-header">
              <h3 class="modal-title text-red-400">删除分类</h3>
            </div>
            <div class="modal-body">
              <p class="text-slate-300 text-sm">确定要删除分类 <span class="text-white font-semibold">「{{ deletingCat.label }}」</span> 吗？</p>
              <p class="text-slate-500 text-xs mt-2">该分类下的所有选项将被级联删除，此操作不可撤销。</p>
            </div>
            <div class="modal-footer">
              <button @click="deletingCat = null" class="btn btn--secondary">取消</button>
              <button @click="doDeleteCat" class="btn btn--danger">确认删除</button>
            </div>
          </div>
        </div>
      </transition>
    </Teleport>

    <!-- Item List Card -->
    <div class="list-card">
      <!-- Add item row -->
      <div class="list-add-row">
        <input v-model="newLabel" @keyup.enter="addItem" placeholder="输入选项显示名称后回车添加"
               class="list-add-input list-add-input--label" />
        <input v-model="newValue" placeholder="value (可选)"
               class="list-add-input list-add-input--value" @keyup.enter="addItem" />
        <input v-model="newDesc" placeholder="描述 (可选)"
               class="list-add-input list-add-input--desc" @keyup.enter="addItem" />
        <button @click="addItem" class="btn btn--primary btn--sm" :disabled="!newLabel.trim()">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
          添加
        </button>
      </div>

      <!-- Empty state -->
      <div v-if="items.length === 0" class="list-empty">
        <svg class="w-10 h-10 text-slate-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>
        <p class="text-slate-500 text-sm">此分类暂无选项</p>
        <p class="text-slate-600 text-xs mt-1">在上方输入框中添加第一个选项</p>
      </div>

      <!-- Item list -->
      <div v-else class="list-body">
        <transition-group name="item">
          <div v-for="item in items" :key="item.id" class="list-item">
            <!-- Sort handle -->
            <span class="list-item-grip" title="拖拽排序">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8h16M4 16h16"/></svg>
            </span>

            <!-- Value + description -->
            <div class="list-item-meta">
              <code class="list-item-value">{{ item.value }}</code>
              <span v-if="item.description" class="list-item-desc">{{ item.description }}</span>
            </div>

            <!-- Editable label -->
            <input
              :value="item.label"
              @blur="e => saveLabel(item, e.target.value)"
              @keyup.enter="e => e.target.blur()"
              class="list-item-input"
            />

            <!-- Status toggle -->
            <button
              @click="toggleItem(item)"
              class="list-item-toggle"
              :class="item.enabled ? 'list-item-toggle--on' : 'list-item-toggle--off'"
              :title="item.enabled ? '已启用，点击禁用' : '已禁用，点击启用'"
            >
              <span class="list-item-toggle-dot"></span>
              <span class="list-item-toggle-label">{{ item.enabled ? '启用' : '禁用' }}</span>
            </button>

            <!-- Delete -->
            <button @click="removeItem(item)" class="list-item-delete" title="删除此选项">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
            </button>
          </div>
        </transition-group>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import {
  listCategories, createCategory, updateCategory, deleteCategory,
  listAllItems, createItem, updateItem, deleteItem,
} from '../api/referenceData.js'

const categories = ref([])
const currentCat = ref('')
const items = ref([])
const newLabel = ref('')
const newValue = ref('')
const newDesc = ref('')

const addingCat = ref(false)
const newCatKey = ref('')
const newCatLabel = ref('')
const catLabelInput = ref(null)
const editingCat = ref(null)
const editCatKey = ref('')
const editCatLabel = ref('')
const deletingCat = ref(null)

function startAddCat() {
  addingCat.value = true
  nextTick(() => catLabelInput.value?.focus())
}

async function loadCategories() {
  const { data } = await listCategories()
  if (data.ok) {
    categories.value = data.categories
    if (!currentCat.value && data.categories.length) {
      currentCat.value = data.categories[0].key
    }
  }
}

async function addCategory() {
  if (!newCatLabel.value.trim()) return
  const key = newCatKey.value.trim() || newCatLabel.value.trim()
  await createCategory({ key, label: newCatLabel.value.trim() })
  newCatKey.value = ''; newCatLabel.value = ''; addingCat.value = false
  await loadCategories()
}

function cancelAddCat() {
  newCatKey.value = ''; newCatLabel.value = ''; addingCat.value = false
}

function startEditCat(cat) {
  editingCat.value = cat
  editCatKey.value = cat.key
  editCatLabel.value = cat.label
}

function cancelEditCat() {
  editingCat.value = null
}

async function saveCategory() {
  if (!editingCat.value) return
  await updateCategory(editingCat.value.id, { key: editCatKey.value, label: editCatLabel.value })
  editingCat.value = null
  await loadCategories()
}

function confirmDeleteCat(cat) {
  deletingCat.value = cat
}

async function doDeleteCat() {
  if (!deletingCat.value) return
  const cat = deletingCat.value
  await deleteCategory(cat.id)
  if (currentCat.value === cat.key) currentCat.value = ''
  deletingCat.value = null
  await loadCategories()
  if (!currentCat.value && categories.value.length) {
    currentCat.value = categories.value[0].key
  }
}

async function load() {
  if (!currentCat.value) { items.value = []; return }
  const { data } = await listAllItems(currentCat.value)
  if (data.ok) items.value = data.items
}

async function addItem() {
  if (!newLabel.value.trim()) return
  await createItem({
    category: currentCat.value,
    value: newValue.value || newLabel.value,
    label: newLabel.value,
    description: newDesc.value,
  })
  newLabel.value = ''; newValue.value = ''; newDesc.value = ''
  await load()
}

async function saveLabel(item, newLabel) {
  if (newLabel !== item.label) { await updateItem(item.id, { label: newLabel }); item.label = newLabel }
}

async function toggleItem(item) {
  await updateItem(item.id, { enabled: !item.enabled }); await load()
}

async function removeItem(item) {
  await deleteItem(item.id); await load()
}

watch(currentCat, load)
onMounted(async () => { await loadCategories(); await load() })
</script>

<style scoped>
/* ===== Category Tabs ===== */
.cat-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 200ms ease;
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(71, 85, 105, 0.2);
  color: #cbd5e1;
  position: relative;
}
.cat-tab:hover {
  background: rgba(51, 65, 85, 0.6);
  border-color: rgba(71, 85, 105, 0.4);
  color: #e2e8f0;
}
.cat-tab--active {
  background: rgba(14, 165, 233, 0.12);
  border-color: rgba(14, 165, 233, 0.3);
  color: #38bdf8;
  box-shadow: 0 0 12px rgba(14, 165, 233, 0.08);
}
.cat-tab-count {
  font-size: 11px;
  opacity: 0.55;
  font-variant-numeric: tabular-nums;
  min-width: 8px;
}
.cat-tab-actions {
  display: none;
  gap: 2px;
  margin-left: 4px;
  align-items: center;
}
.cat-tab:hover .cat-tab-actions {
  display: inline-flex;
}
.cat-tab-action {
  padding: 2px 4px;
  border-radius: 4px;
  background: none;
  border: none;
  cursor: pointer;
  color: #94a3b8;
  transition: all 150ms;
  display: inline-flex;
  align-items: center;
}
.cat-tab-action:hover {
  color: #fbbf24;
  background: rgba(251, 191, 36, 0.1);
}
.cat-tab-action--danger:hover {
  color: #f87171;
  background: rgba(248, 113, 113, 0.1);
}

/* ===== Inline Add Category ===== */
.cat-add-form {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border-radius: 10px;
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid rgba(14, 165, 233, 0.25);
  box-shadow: 0 0 10px rgba(14, 165, 233, 0.06);
}
.cat-add-input {
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(71, 85, 105, 0.3);
  border-radius: 6px;
  padding: 5px 10px;
  font-size: 13px;
  color: #e2e8f0;
  outline: none;
  min-width: 130px;
  transition: border-color 150ms;
}
.cat-add-input::placeholder { color: #64748b; }
.cat-add-input:focus { border-color: rgba(14, 165, 233, 0.5); }
.cat-add-input--key { min-width: 110px; }
.cat-add-btn {
  padding: 2px 6px;
  border-radius: 5px;
  border: none;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  transition: all 150ms;
}
.cat-add-btn--confirm {
  background: rgba(14, 165, 233, 0.15);
  color: #38bdf8;
}
.cat-add-btn--confirm:hover { background: rgba(14, 165, 233, 0.3); }
.cat-add-btn--cancel {
  background: none;
  color: #64748b;
}
.cat-add-btn--cancel:hover { color: #94a3b8; }

.cat-add-trigger {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 200ms;
  background: none;
  border: 1px dashed rgba(100, 116, 139, 0.4);
  color: #64748b;
}
.cat-add-trigger:hover {
  border-color: rgba(148, 163, 184, 0.6);
  color: #94a3b8;
}

/* ===== Modal ===== */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(4px);
}
.modal-card {
  background: rgba(15, 23, 42, 0.95);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(71, 85, 105, 0.3);
  border-radius: 16px;
  width: 420px;
  max-width: calc(100vw - 32px);
  box-shadow: 0 25px 50px rgba(0, 0, 0, 0.5);
}
.modal-card--sm { width: 380px; }
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 0;
}
.modal-title {
  font-size: 16px;
  font-weight: 600;
  color: #f1f5f9;
}
.modal-close {
  padding: 4px;
  border-radius: 8px;
  border: none;
  background: none;
  color: #64748b;
  cursor: pointer;
  transition: all 150ms;
  display: flex;
}
.modal-close:hover { color: #e2e8f0; background: rgba(71, 85, 105, 0.2); }
.modal-body { padding: 20px 24px; }
.modal-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  padding: 0 24px 20px;
}

/* ===== Form ===== */
.form-group { margin-bottom: 16px; }
.form-group:last-child { margin-bottom: 0; }
.form-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #cbd5e1;
  margin-bottom: 6px;
}
.form-hint {
  font-weight: 400;
  color: #64748b;
  margin-left: 6px;
}
.form-input {
  width: 100%;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(30, 41, 59, 0.8);
  border: 1px solid rgba(71, 85, 105, 0.3);
  color: #e2e8f0;
  font-size: 14px;
  outline: none;
  transition: border-color 150ms;
  box-sizing: border-box;
}
.form-input::placeholder { color: #475569; }
.form-input:focus { border-color: rgba(14, 165, 233, 0.5); }

/* ===== Buttons ===== */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: all 150ms;
}
.btn--sm { padding: 6px 12px; font-size: 13px; }
.btn--primary { background: #0284c7; color: #fff; }
.btn--primary:hover { background: #0369a1; }
.btn--primary:disabled { opacity: 0.4; cursor: not-allowed; }
.btn--secondary { background: rgba(71, 85, 105, 0.3); color: #cbd5e1; }
.btn--secondary:hover { background: rgba(71, 85, 105, 0.5); }
.btn--danger { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.25); }
.btn--danger:hover { background: rgba(239, 68, 68, 0.3); }

/* ===== List Card ===== */
.list-card {
  border-radius: 16px;
  border: 1px solid rgba(71, 85, 105, 0.15);
  overflow: hidden;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(12px);
}
.list-add-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(71, 85, 105, 0.12);
}
.list-add-input {
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid rgba(71, 85, 105, 0.2);
  color: #e2e8f0;
  font-size: 13px;
  outline: none;
  transition: border-color 150ms;
}
.list-add-input::placeholder { color: #475569; }
.list-add-input:focus { border-color: rgba(14, 165, 233, 0.45); }
.list-add-input--label { flex: 1; }
.list-add-input--value { width: 140px; }
.list-add-input--desc { width: 180px; }

.list-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
}

.list-body {
  max-height: 480px;
  overflow-y: auto;
}
.list-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 20px;
  transition: background 150ms;
  border-bottom: 1px solid rgba(71, 85, 105, 0.06);
}
.list-item:last-child { border-bottom: none; }
.list-item:hover { background: rgba(30, 41, 59, 0.35); }

.list-item-grip {
  color: #475569;
  flex-shrink: 0;
  cursor: grab;
  display: flex;
  opacity: 0;
  transition: opacity 150ms;
}
.list-item:hover .list-item-grip { opacity: 1; }

.list-item-meta {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 90px;
  max-width: 110px;
  flex-shrink: 0;
}
.list-item-value {
  font-size: 11px;
  color: #64748b;
  font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  background: rgba(30, 41, 59, 0.4);
  padding: 1px 6px;
  border-radius: 4px;
}
.list-item-desc {
  font-size: 10px;
  color: #475569;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 2px;
}
.list-item-input {
  flex: 1;
  padding: 6px 10px;
  border-radius: 6px;
  background: transparent;
  border: 1px solid transparent;
  color: #e2e8f0;
  font-size: 13px;
  outline: none;
  transition: all 150ms;
}
.list-item-input:hover { background: rgba(30, 41, 59, 0.4); }
.list-item-input:focus {
  background: rgba(30, 41, 59, 0.7);
  border-color: rgba(14, 165, 233, 0.35);
}

/* Toggle switch */
.list-item-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 500;
  border: 1px solid;
  cursor: pointer;
  transition: all 200ms;
  background: none;
  flex-shrink: 0;
}
.list-item-toggle--on {
  color: #34d399;
  border-color: rgba(52, 211, 153, 0.25);
}
.list-item-toggle--on:hover { background: rgba(52, 211, 153, 0.08); }
.list-item-toggle--off {
  color: #475569;
  border-color: rgba(71, 85, 105, 0.2);
}
.list-item-toggle--off:hover { background: rgba(71, 85, 105, 0.1); color: #94a3b8; }
.list-item-toggle-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}
.list-item-toggle--on .list-item-toggle-dot {
  box-shadow: 0 0 6px currentColor;
}

.list-item-delete {
  padding: 5px;
  border-radius: 6px;
  border: none;
  background: none;
  color: #475569;
  cursor: pointer;
  transition: all 150ms;
  display: flex;
  opacity: 0;
  flex-shrink: 0;
}
.list-item:hover .list-item-delete { opacity: 1; }
.list-item-delete:hover { color: #f87171; background: rgba(239, 68, 68, 0.1); }

/* ===== Transitions ===== */
.modal-enter-active, .modal-leave-active {
  transition: opacity 200ms ease;
}
.modal-enter-active .modal-card, .modal-leave-active .modal-card {
  transition: transform 200ms ease, opacity 200ms ease;
}
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from .modal-card { transform: scale(0.95) translateY(8px); opacity: 0; }
.modal-leave-to .modal-card { transform: scale(0.95) translateY(8px); opacity: 0; }

.item-enter-active { transition: all 250ms ease; }
.item-leave-active { transition: all 200ms ease; }
.item-enter-from { opacity: 0; transform: translateX(-12px); }
.item-leave-to { opacity: 0; transform: translateX(12px); }
</style>
```

## src/views/DirectorPage.vue

```html
<template>
  <div class="p-6">
    <div class="flex items-center gap-4 mb-6">
      <button @click="$router.back()" class="text-sky-400 hover:text-sky-300 transition cursor-pointer">&larr; 返回</button>
      <h1 class="text-2xl font-bold text-slate-100">导演时间线</h1>
    </div>

    <div v-if="!plan" class="text-slate-500 text-center py-12">请先选择剧集，然后构建导演计划</div>
    <div v-else class="space-y-6">
      <div class="flex gap-4 text-sm text-slate-400">
        <span>{{ plan.frame_count }} 帧</span><span>{{ plan.total_duration?.toFixed(0) || 0 }}s 总时长</span>
        <span>BGM: {{ plan.bgm_path || '无' }}</span>
      </div>

      <div class="space-y-3">
        <div v-for="f in plan.frames" :key="f.index"
             class="rounded-xl border border-gray-700/50 p-4 flex gap-4 items-start hover:shadow-lg hover:shadow-sky-900/10 transition-all duration-200"
             style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);">
          <div class="w-12 h-12 rounded-lg flex items-center justify-center text-lg font-bold" :class="shotBg(f.shot_type)">{{ f.index + 1 }}</div>
          <div class="flex-1 min-w-0">
            <div class="flex gap-2 flex-wrap mb-2">
              <span class="px-2 py-0.5 rounded text-xs font-medium" :class="shotBg(f.shot_type)">{{ f.shot_type }}</span>
              <span class="px-2 py-0.5 rounded text-xs bg-gray-800 text-slate-400">{{ f.camera_angle }}</span>
              <span class="px-2 py-0.5 rounded text-xs bg-gray-800 text-slate-400">{{ f.camera_movement }}</span>
              <span class="px-2 py-0.5 rounded text-xs" :class="audioBg(f.audio_mode)">{{ f.audio_mode }}</span>
              <span class="px-2 py-0.5 rounded text-xs bg-gray-800 text-slate-400">{{ f.duration }}s</span>
            </div>
            <p class="text-sm text-slate-200 line-clamp-2 mb-1">{{ f.narration }}</p>
            <p class="text-xs text-slate-500 italic">{{ f.image_prompt }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const plan = ref(null)
function shotBg(t) { return { close_up: 'bg-red-900/40 text-red-400', medium: 'bg-sky-900/40 text-sky-400', wide: 'bg-emerald-900/40 text-emerald-400', aerial: 'bg-purple-900/40 text-purple-400', climax: 'bg-orange-900/40 text-orange-400' }[t] || 'bg-gray-800 text-slate-400' }
function audioBg(m) { return { tts: 'bg-sky-900/40 text-sky-400', seedance_native: 'bg-emerald-900/40 text-emerald-400', bgm_only: 'bg-yellow-900/40 text-yellow-400', silent: 'bg-gray-800 text-slate-400' }[m] || 'bg-gray-800 text-slate-400' }
</script>
```

## src/views/DMSequenceManagePage.vue

```html
<script setup>
import { ref, reactive, onMounted } from 'vue'
import { listDMSequences, createDMSequence, updateDMSequence, deleteDMSequence, getDMSequence } from '../api/dmSequences.js'
import { useToastStore } from '../stores/toast.js'

const toast = useToastStore()
const loading = ref(false)
const sequences = ref([])
const showEditor = ref(false)
const editingId = ref(null)

// AI generation
const aiDescription = ref('')
const aiLinkUrl = ref('')
const generating = ref(false)
const generateStatus = ref('')
const generatingVariants = ref(false)
const loadedVariants = ref(null)
const variantCount = ref(3)
const targetVariantCount = ref(0)
const partialGenMsg = ref('')
const editingVariantIdx = ref(-1)

function deleteVariant(idx) {
  if (!loadedVariants.value) return
  loadedVariants.value.splice(idx, 1)
  if (loadedVariants.value.length === 0) loadedVariants.value = null
  if (editingVariantIdx.value === idx) editingVariantIdx.value = -1
}

function startEditVariant(idx) {
  editingVariantIdx.value = idx
}

function doneEditVariant() {
  editingVariantIdx.value = -1
}

let _savedFocusEl = null

const form = reactive({
  name: '',
  industry: '',
  messages: [{ order: 1, content: '', delay_ms: 3000 }],
})

function closeEditor() {
  showEditor.value = false
  if (_savedFocusEl && typeof _savedFocusEl.focus === 'function') {
    _savedFocusEl.focus()
  }
  _savedFocusEl = null
}

function resetForm() {
  form.name = ''
  form.industry = ''
  form.messages = [{ order: 1, content: '', delay_ms: 3000 }]
  editingId.value = null
  aiDescription.value = ''
  aiLinkUrl.value = ''
  generateStatus.value = ''
  loadedVariants.value = null
  targetVariantCount.value = 0
  partialGenMsg.value = ''
}

function addMessage() {
  if (form.messages.length >= 10) { toast.error('最多 10 条消息'); return }
  form.messages.push({ order: form.messages.length + 1, content: '', delay_ms: 3000 })
}

function removeMessage(idx) {
  if (form.messages.length <= 1) { toast.error('至少保留 1 条消息'); return }
  form.messages.splice(idx, 1)
  // Re-number
  form.messages.forEach(function (m, i) { m.order = i + 1 })
}

function moveUp(idx) {
  if (idx === 0) return
  var tmp = form.messages[idx - 1]
  form.messages[idx - 1] = form.messages[idx]
  form.messages[idx] = tmp
  form.messages.forEach(function (m, i) { m.order = i + 1 })
}

function moveDown(idx) {
  if (idx >= form.messages.length - 1) return
  var tmp = form.messages[idx + 1]
  form.messages[idx + 1] = form.messages[idx]
  form.messages[idx] = tmp
  form.messages.forEach(function (m, i) { m.order = i + 1 })
}

function openCreate() {
  _savedFocusEl = document.activeElement
  resetForm()
  showEditor.value = true
}

function openEdit(seq) {
  _savedFocusEl = document.activeElement
  form.name = seq.name
  form.industry = seq.industry || ''
  form.messages = JSON.parse(JSON.stringify(seq.messages))
  loadedVariants.value = (seq.variants && seq.variants.length) ? seq.variants : null
  targetVariantCount.value = 0
  partialGenMsg.value = ''
  editingId.value = seq.id
  showEditor.value = true
}

async function handleSave() {
  var valid = form.messages.filter(function (m) { return m.content.trim() })
  if (!form.name.trim()) { toast.error('请输入模板名称'); return }
  if (valid.length === 0) { toast.error('请至少填写一条消息内容'); return }
  try {
    if (editingId.value) {
      var payload = { name: form.name, industry: form.industry, messages: form.messages }
      if (loadedVariants.value) { payload.variants = loadedVariants.value }
      await updateDMSequence(editingId.value, payload)
      toast.success('已更新')
    } else {
      await createDMSequence({
        name: form.name, industry: form.industry, messages: form.messages,
      })
      toast.success('已创建')
    }
    closeEditor()
    fetchData()
  } catch (e) {
    toast.error(e?.response?.data?.detail || '保存失败')
  }
}

async function handleDelete(seq) {
  if (!confirm('确认删除序列模板 "' + seq.name + '"？')) return
  try {
    await deleteDMSequence(seq.id)
    toast.success('已删除')
    fetchData()
  } catch (e) {
    toast.error('删除失败')
  }
}

async function fetchData() {
  loading.value = true
  try {
    var res = await listDMSequences()
    sequences.value = res.data.sequences || []
  } catch (e) {
    toast.error('加载失败')
  } finally {
    loading.value = false
  }
}


async function generateSequence() {
  if (!aiDescription.value || !aiLinkUrl.value) return
  generating.value = true
  generateStatus.value = '正在连接...';
  var token = localStorage.getItem('token') || '';

  try {
    var response = await fetch('/api/dm-sequences/generate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? 'Bearer ' + token : '',
      },
      body: JSON.stringify({
        industry: form.industry || 'general',
        description: aiDescription.value,
        link_url: aiLinkUrl.value,
      }),
    })

    if (!response.ok) {
      var errData = null
      try { errData = await response.json() } catch (_) { /* ignore */ }
      generateStatus.value = '错误: ' + (errData?.detail || 'HTTP ' + response.status)
      generating.value = false
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.trim()) continue
        const jsonStr = line.startsWith('data: ') ? line.slice(6) : line
        try {
          const data = JSON.parse(jsonStr)
          if (data.type === 'status') {
            generateStatus.value = data.text || data.content || '';
          } else if (data.type === 'done') {
            const messages = data.messages
            if (messages && Array.isArray(messages)) {
              form.messages = messages
            }
            generateStatus.value = '生成完成！请检查并调整消息内容';
            generating.value = false
            return
          } else if (data.type === 'error') {
            generateStatus.value = '错误: ' + (data.message || '未知错误')
            generating.value = false
            return
          }
        } catch (_) { /* 跳过非 JSON 行 */ }
      }
    }
  } catch (e) {
    generateStatus.value = '连接失败';
  }
  generating.value = false
}

async function generateVariants() {
  if (!editingId.value) return
  generatingVariants.value = true
  partialGenMsg.value = ''
  var token = localStorage.getItem('token') || '';

  // 首次点击记住目标总数，后续点击自动算剩余
  var existingCount = loadedVariants.value ? loadedVariants.value.length : 0
  var remaining;
  if (targetVariantCount.value > 0) {
    // 追量模式：上一次没生成完，这次生成剩余数
    remaining = targetVariantCount.value - existingCount
    if (remaining <= 0) {
      targetVariantCount.value = 0
      alert('已达到目标套数，无需继续生成')
      generatingVariants.value = false
      return
    }
  } else {
    targetVariantCount.value = variantCount.value
    remaining = variantCount.value
  }

  try {
    var res = await fetch('/api/dm-sequences/' + editingId.value + '/variants', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? 'Bearer ' + token : '',
      },
      body: JSON.stringify({ count: remaining }),
    })
    var data = await res.json()
    if (data.ok) {
      loadedVariants.value = data.variants
      var newTotal = loadedVariants.value.length
      if (newTotal < targetVariantCount.value) {
        partialGenMsg.value = '本次生成 ' + data.variants_count + ' 套，累计 ' + newTotal + '/' + targetVariantCount.value + ' 套，还差 ' + (targetVariantCount.value - newTotal) + ' 套，请再次点击生成'
      } else {
        partialGenMsg.value = '已生成 ' + newTotal + ' 套变体，目标完成'
        targetVariantCount.value = 0
      }
      fetchData()
    } else {
      alert('变体生成失败: ' + (data.detail || '未知错误'))
    }
  } catch (e) {
    alert('变体生成失败: ' + (e.message || ''))
  }
  generatingVariants.value = false
}

onMounted(fetchData)
</script>

<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-100">DM 序列模板</h1>
        <p class="text-sm text-slate-400 mt-1">预设私信发送序列，控制内容和发送间隔</p>
      </div>
      <button @click="openCreate" class="bg-sky-500 hover:bg-sky-400 text-white px-4 py-2 rounded-lg transition cursor-pointer">
        + 新建模板
      </button>
    </div>

    <div v-if="loading" class="text-slate-400 text-center py-12">加载中...</div>
    <div v-else-if="sequences.length === 0" class="text-slate-500 text-center py-12">
      暂无私信序列模板，点击"新建模板"创建
    </div>
    <div v-else class="grid grid-cols-1 gap-4">
      <div v-for="s in sequences" :key="s.id"
           class="rounded-xl border border-gray-700/50 p-5" style="background: rgba(15,23,42,0.5); backdrop-filter: blur(8px)">
        <div class="flex justify-between items-start">
          <div>
            <h3 class="text-lg font-semibold text-white">{{ s.name }}</h3>
            <p class="text-sm text-slate-400 mt-1">{{ s.message_count }} 条消息
              <span v-if="s.industry" class="ml-2 px-2 py-0.5 rounded text-xs bg-white/5 text-slate-300">{{ s.industry }}</span>
              <span v-if="s.variants_count" class="ml-2 px-2 py-0.5 rounded text-xs bg-emerald-500/15 text-emerald-400">{{ s.variants_count }} 套变体</span>
            </p>
            <div class="mt-3 space-y-1">
              <div v-for="m in (s.messages || []).slice(0, 3)" :key="m.order" class="text-xs text-slate-400">
                <span class="text-slate-500 mr-1">{{ m.order }}.</span>
                {{ (m.content || '').substring(0, 50) }}{{ (m.content || '').length > 50 ? '...' : '' }}
                <span class="text-slate-600 ml-1">({{ m.delay_ms || 0 }}ms)</span>
              </div>
            </div>
          </div>
          <div class="flex gap-2">
            <button @click="openEdit(s)" class="text-sm text-sky-400 hover:text-sky-300 cursor-pointer px-2 py-1 rounded hover:bg-white/5 transition">编辑</button>
            <button @click="handleDelete(s)" class="text-sm text-red-400 hover:text-red-300 cursor-pointer px-2 py-1 rounded hover:bg-white/5 transition">删除</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Editor Dialog -->
    <div v-if="showEditor" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="closeEditor()">
      <div class="bg-slate-800 rounded-xl shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto p-6 border border-slate-700">
        <h2 class="text-lg font-bold text-white mb-4">{{ editingId ? '编辑模板' : '新建模板' }}</h2>
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-1">模板名称</label>
            <input v-model="form.name" maxlength="100" class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-sky-500" placeholder="如：健康行业标准话术" />
          </div>
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-1">行业标签（可选）</label>
            <select v-model="form.industry"
              class="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:border-sky-500 focus:outline-none">
              <option value="">不选择</option>
              <option value="health">大健康</option>
              <option value="beauty">医美</option>
              <option value="education">教育</option>
              <option value="travel">旅游</option>
              <option value="secondhand">二手买卖</option>
              <option value="general">通用</option>
            </select>
          </div>

          <!-- AI 智能生成 -->
          <div v-if="!editingId" class="p-4 bg-slate-800/50 rounded-lg border border-slate-700">
            <h4 class="text-sm font-medium text-slate-300 mb-2">AI 智能生成序列</h4>
            <div class="mb-2">
              <input v-model="aiDescription" type="text" placeholder="大白话描述，如：推饮食指南软文，语气亲和可信"
                class="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:border-sky-500 focus:outline-none" />
            </div>
            <div class="mb-3">
              <input v-model="aiLinkUrl" type="text" placeholder="短链URL（作为消息2）"
                class="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm focus:border-sky-500 focus:outline-none" />
            </div>
            <button @click="generateSequence" :disabled="!aiDescription || !aiLinkUrl || generating"
              class="px-4 py-2 bg-gradient-to-r from-sky-600 to-purple-600 text-white rounded-lg text-sm font-medium disabled:opacity-50 hover:from-sky-500 hover:to-purple-500 transition-colors cursor-pointer">
              <span v-if="generating">AI 正在生成...</span>
              <span v-else>AI 生成序列</span>
            </button>
            <div v-if="generating" class="mt-2 text-xs text-slate-400">{{ generateStatus }}</div>
          </div>

          <div>
            <div class="flex justify-between items-center mb-2">
              <label class="text-sm font-medium text-slate-300">消息序列 ({{ form.messages.length }}/10)</label>
              <button @click="addMessage" v-if="form.messages.length < 10" class="text-xs text-sky-400 hover:text-sky-300 cursor-pointer">+ 添加消息</button>
            </div>
            <div class="space-y-3">
              <div v-for="(msg, idx) in form.messages" :key="idx" class="flex gap-2 items-start p-3 rounded-lg border border-white/5 bg-white/[0.03]">
                <div class="flex flex-col gap-1 text-slate-500 text-xs pt-2">
                  <button @click="moveUp(idx)" :disabled="idx === 0" class="hover:text-white disabled:opacity-30 disabled:cursor-default cursor-pointer">&#9650;</button>
                  <span class="text-center">{{ msg.order }}</span>
                  <button @click="moveDown(idx)" :disabled="idx >= form.messages.length - 1" class="hover:text-white disabled:opacity-30 disabled:cursor-default cursor-pointer">&#9660;</button>
                </div>
                <div class="flex-1">
                  <textarea v-model="msg.content" rows="2" maxlength="500" class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-sky-500" placeholder="私信内容，支持 {{keyword}} 变量"></textarea>
                </div>
                <div class="flex flex-col gap-1 items-end">
                  <input v-model.number="msg.delay_ms" type="number" min="0" max="60000" step="500" class="w-20 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-white text-xs text-center focus:outline-none focus:border-sky-500" title="本条发送后额外等待（毫秒）" />
                  <span class="text-xs text-slate-500">{{ msg.delay_ms || 0 }}ms</span>
                  <button @click="removeMessage(idx)" class="text-xs text-red-400 hover:text-red-300 cursor-pointer">删除</button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 变体预览 -->
        <div v-if="loadedVariants && loadedVariants.length" class="mt-4 p-4 bg-emerald-500/5 rounded-lg border border-emerald-500/20">
          <h4 class="text-sm font-medium text-emerald-400 mb-3">{{ loadedVariants.length }} 套变体</h4>
          <div class="space-y-3">
            <div v-for="(variant, vi) in loadedVariants" :key="vi" class="p-3 rounded bg-slate-800/50 border border-white/5">
              <div class="flex justify-between items-center mb-2">
                <span class="text-xs text-slate-500">变体 {{ vi + 1 }}</span>
                <div class="flex gap-1">
                  <button @click="editingVariantIdx === vi ? doneEditVariant() : startEditVariant(vi)"
                    class="text-xs px-2 py-0.5 rounded cursor-pointer transition"
                    :class="editingVariantIdx === vi ? 'bg-sky-500/20 text-sky-400' : 'text-slate-500 hover:text-slate-300 hover:bg-white/5'">
                    {{ editingVariantIdx === vi ? '完成' : '编辑' }}
                  </button>
                  <button @click="deleteVariant(vi)"
                    class="text-xs px-2 py-0.5 rounded text-red-400 hover:text-red-300 hover:bg-red-500/10 cursor-pointer transition">删除</button>
                </div>
              </div>
              <div class="space-y-1">
                <div v-for="vm in variant" :key="vm.order" class="text-xs flex gap-2 items-start">
                  <span class="text-slate-500 shrink-0 pt-0.5">{{ vm.order }}.</span>
                  <template v-if="editingVariantIdx === vi">
                    <textarea v-model="vm.content" rows="2"
                      class="flex-1 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-white text-xs focus:outline-none focus:border-sky-500"></textarea>
                    <input v-model.number="vm.delay_ms" type="number" min="0" max="60000" step="500"
                      class="w-16 bg-slate-700 border border-slate-600 rounded px-1 py-1 text-white text-xs text-center focus:outline-none focus:border-sky-500 shrink-0" />
                  </template>
                  <template v-else>
                    <span class="text-slate-300 flex-1">{{ vm.content }}</span>
                    <span class="text-slate-600 shrink-0">({{ vm.delay_ms || 0 }}ms)</span>
                  </template>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="flex justify-between gap-3 mt-6">
          <div>
            <div class="flex flex-col gap-2">
              <div class="flex items-center gap-2">
                <button v-if="editingId && form.messages && form.messages.length >= 3"
                  @click="generateVariants" :disabled="generatingVariants"
                  class="px-4 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-lg text-sm font-medium disabled:opacity-50 hover:from-emerald-500 hover:to-teal-500 transition-colors cursor-pointer">
                  <span v-if="generatingVariants">正在生成变体...</span>
                  <span v-else>
                    <template v-if="targetVariantCount > 0 && loadedVariants && loadedVariants.length < targetVariantCount">
                      继续生成 {{ targetVariantCount - loadedVariants.length }} 套
                    </template>
                    <template v-else>生成 {{ variantCount }} 套变体</template>
                  </span>
                </button>
                <input v-model.number="variantCount" type="number" min="1" max="10"
                  class="w-14 bg-slate-700 border border-slate-600 rounded px-2 py-2 text-white text-sm text-center focus:outline-none focus:border-emerald-500" />
              </div>
              <p v-if="partialGenMsg" class="text-xs text-amber-400">{{ partialGenMsg }}</p>
            </div>
          </div>
          <div class="flex gap-3">
            <button @click="closeEditor()" class="px-4 py-2 text-slate-400 hover:text-white transition cursor-pointer">取消</button>
            <button @click="handleSave" class="px-4 py-2 bg-sky-500 text-white rounded-lg hover:bg-sky-400 transition cursor-pointer">保存</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
```

## src/views/LoginPage.vue

```html
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const router = useRouter()
const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await authStore.login(username.value, password.value)
    router.push('/')
  } catch (e) {
    if (e.response && e.response.data && e.response.data.detail) {
      error.value = e.response.data.detail
    } else {
      error.value = '登录失败，请稍后重试'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center relative login-aurora">
    <div class="cinematic-bg"></div>
    <div class="dot-grid"></div>

    <div class="relative z-10 w-full max-w-sm">
      <!-- Brand -->
      <div class="text-center mb-8">
        <div class="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg" style="background: linear-gradient(135deg, var(--accent-600), var(--accent-500)); box-shadow: 0 0 40px var(--accent-glow);">
          <svg class="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <h1 class="text-2xl font-black tracking-tight gradient-text">抖音助手</h1>
        <p class="text-slate-500 text-sm mt-1 font-mono tracking-wide">COMMAND CENTER</p>
      </div>

      <!-- Card -->
      <div class="card-glass p-8 card-gradient">
        <form @submit.prevent="handleLogin" class="space-y-5">
          <div>
            <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5" for="username">用户名</label>
            <input id="username" v-model="username" type="text" required class="w-full px-3 py-2.5 rounded-lg text-sm" placeholder="请输入用户名" />
          </div>

          <div>
            <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5" for="password">密码</label>
            <input id="password" v-model="password" type="password" required class="w-full px-3 py-2.5 rounded-lg text-sm" placeholder="请输入密码" />
          </div>

          <div v-if="error" class="text-red-400 text-xs bg-red-500/8 border border-red-500/15 p-2.5 rounded-lg flex items-center gap-2">
            <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"/></svg>
            {{ error }}
          </div>

          <button type="submit" :disabled="loading" class="btn-primary w-full py-2.5 text-sm justify-center">
            {{ loading ? '验证中...' : '进入指挥中心' }}
          </button>
        </form>
      </div>

      <p class="text-center text-[11px] text-slate-600 mt-6 font-mono tracking-wider">DOUYIN AUTOMATION · HELIX COMMAND</p>
    </div>
  </div>
</template>
```

## src/views/PipelineMonitorPage.vue

```html
<template>
  <div class="p-6">
    <button @click="$router.back()" class="text-sky-400 hover:text-sky-300 mb-4 transition cursor-pointer">&larr; 返回</button>

    <div v-if="loading" class="text-slate-400 text-center py-12">加载中...</div>
    <div v-else-if="error" class="text-red-400 text-center py-12">{{ error }}</div>
    <template v-else-if="run">
      <div class="flex justify-between items-start mb-6">
        <div>
          <h1 class="text-2xl font-bold text-slate-100">流水线监控</h1>
          <p class="text-slate-500 text-sm font-mono mt-1">Run {{ run.id.slice(0, 8) }}</p>
        </div>
        <span :class="runStatusClass(run.status)" class="px-3 py-1 rounded-lg text-sm font-medium">{{ run.status }}</span>
      </div>

      <div class="space-y-2 mb-6">
        <div v-for="(layer, idx) in layers" :key="idx" class="flex items-center gap-4">
          <span class="w-8 text-center text-lg text-slate-300">{{ idx }}</span>
          <span class="w-24 text-sm text-slate-400">{{ layerNames[idx] }}</span>
          <div class="flex-1 rounded-full h-2.5" style="background: rgba(255,255,255,0.06);">
            <div :class="layerBarClass(layer.status)" class="h-2.5 rounded-full transition-all duration-500"
                 :style="{ width: layer.status === 'completed' ? '100%' : layer.status === 'running' ? '60%' : '0%' }"></div>
          </div>
          <span class="w-16 text-xs text-right" :class="layer.status === 'completed' ? 'text-emerald-400' : 'text-slate-500'">
            {{ layer.status === 'completed' ? '✓ 完成' : layer.status === 'running' ? '进行中' : '—' }}
          </span>
        </div>
      </div>

      <div class="grid grid-cols-3 gap-4 mb-6">
        <div v-for="stat in stats" :key="stat.label" class="rounded-xl border border-gray-700/50 p-4 text-center" style="background: rgba(15, 23, 42, 0.5);">
          <div class="text-2xl font-bold text-slate-100">{{ stat.value }}</div>
          <div class="text-xs text-slate-500 mt-1">{{ stat.label }}</div>
        </div>
      </div>

      <div v-if="run.error_log" class="rounded-xl border border-red-800/50 p-4 text-sm text-red-400" style="background: rgba(127, 29, 29, 0.1);">
        <strong>错误：</strong> {{ run.error_log }}
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { getRun } from '../api/pipeline.js'
const route = useRoute(); const run = ref(null); const loading = ref(true); const error = ref(''); let timer = null
const layerNames = ['资产生成', '资产工坊', '故事工坊', '导演工坊', '渲染引擎', '后期包装']
const layers = computed(() => { if (!run.value) return []; const json = run.value.layers_json || {}; return Array.from({ length: 6 }, (_, i) => ({ status: json[String(i)]?.status || (i === run.value.current_layer ? 'running' : 'pending') })) })
const stats = computed(() => { if (!run.value) return []; const diff = run.value.started_at ? Math.floor((Date.now() - new Date(run.value.started_at).getTime()) / 1000) : 0; return [{ label: '当前层', value: `${run.value.current_layer}/6` }, { label: '累计成本', value: `¥${(run.value.actual_cost_so_far || 0).toFixed(2)}` }, { label: '运行时间', value: `${Math.floor(diff/60)}m ${diff%60}s` }] })
async function load() { try { const { data } = await getRun('_', route.params.runId); if (data.ok) { run.value = data.run; if (run.value?.status === 'completed' || run.value?.status === 'failed') { if (timer) { clearInterval(timer); timer = null } } } else throw new Error('Not found') } catch (e) { error.value = e.message || '加载失败'; if (timer) clearInterval(timer) } finally { loading.value = false } }
function runStatusClass(s) { return { running: 'bg-sky-900/40 text-sky-400', completed: 'bg-emerald-900/40 text-emerald-400', failed: 'bg-red-900/40 text-red-400', pending: 'bg-gray-800 text-slate-400' }[s] || 'bg-gray-800 text-slate-400' }
function layerBarClass(s) { return s === 'completed' ? 'bg-emerald-500' : s === 'running' ? 'bg-sky-500 animate-pulse' : '' }
onMounted(() => { load(); timer = setInterval(load, 5000) })
onUnmounted(() => clearInterval(timer))
</script>
```

## src/views/PromptTemplatesPage.vue

```html
<script setup>
import { ref, onMounted, nextTick } from 'vue'
import {
  Dialog,
  DialogPanel,
  DialogTitle,
  TransitionRoot,
  TransitionChild,
  Switch,
  SwitchGroup,
  SwitchLabel,
} from '@headlessui/vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import EmptyState from '../components/EmptyState.vue'
import { useToastStore } from '../stores/toast.js'
import { useSavedPrompt } from '../composables/useSavedPrompt.js'
import { useWebSocket } from '../composables/useWebSocket.js'
import * as api from '../api/promptTemplates.js'

const toast = useToastStore()

// --- WebSocket ---
function wsUrl() {
  const token = localStorage.getItem('token') || ''
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/api/devices/ws/pair-events?token=${encodeURIComponent(token)}`
}
useWebSocket(wsUrl, {
  onMessage(msg) {
    if (msg.event === 'prompt_templates_changed') fetchTemplates()
  },
})

const generatingStatus = ref('')
const templates = ref([])
const loading = ref(false)
const saving = ref(false)
const generating = ref(false)
const dialogOpen = ref(false)
const isEditing = ref(false)
const aiDesc = useSavedPrompt('template_generator', '')
const form = ref({ name: '', industry: 'health', description: '', contentJson: '' })
const showDeleteDialog = ref(false)
const deletingName = ref(null)

// ---- helpers ----
function scenePreview(content) {
  if (!content) return []
  const parts = []
  if (content.videoComment) parts.push({ key: 'video', label: '视频评论', desc: '引流截流' })
  if (content.analysis) parts.push({ key: 'reply', label: '评论回复', desc: '评论区截流' })
  if (content.dmOpener || content.dmStages) parts.push({ key: 'dm', label: '私信转化', desc: '多阶段漏斗' })
  return parts
}

const industryLabels = { health: '大健康', travel: '旅游', education: '教育', finance: '金融', beauty: '美妆', realestate: '房产', auto: '汽车' }
function industryLabel(val) { return industryLabels[val] || val }

function formatDate(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  const now = new Date()
  const diff = now - d
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + ' 分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + ' 小时前'
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

// ---- data ----
async function fetchTemplates() {
  loading.value = true
  try {
    const res = await api.listTemplates(true)
    templates.value = res.data.templates || []
  } catch (e) {
    toast.error('加载模板列表失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  isEditing.value = false
  generatingStatus.value = ''
  form.value = { name: '', industry: 'health', description: '', contentJson: '' }
  dialogOpen.value = true
}

async function handleGenerate() {
  if (!aiDesc.value.trim()) { toast.error('请输入模板需求描述'); return }
  generating.value = true
  generatingStatus.value = '正在连接...'
  try {
    const token = localStorage.getItem('token') || ''
    const resp = await fetch('/api/prompt-templates/generate-stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
      body: JSON.stringify({ description: aiDesc.value, industry: form.value.industry }),
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }))
      throw new Error(err.detail || 'HTTP ' + resp.status)
    }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let receivedDone = false
    let lastRender = Date.now()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value, { stream: true })
      buffer += chunk
      while (buffer.includes('\n\n')) {
        const idx = buffer.indexOf('\n\n')
        const raw = buffer.slice(0, idx).trim()
        buffer = buffer.slice(idx + 2)
        if (!raw.startsWith('data: ')) continue
        try {
          const data = JSON.parse(raw.slice(6))
          if (data.type === 'token') {
            form.value.contentJson += data.text
            generatingStatus.value = 'AI 正在生成...'
          } else if (data.type === 'status') {
            generatingStatus.value = data.text
          } else if (data.type === 'done') {
            receivedDone = true
            form.value.contentJson = JSON.stringify(data.content, null, 2)
            generatingStatus.value = ''
            if (!form.value.name) {
              const words = aiDesc.value.split(/[\s,，]+/).filter(w => w.length > 1)
              form.value.name = form.value.industry + '-' + (words.slice(0, 3).join('-') || 'custom')
            }
            toast.success('模板已生成，请检查并保存')
          } else if (data.type === 'error') {
            receivedDone = true
            toast.error('生成失败: ' + data.message)
            generatingStatus.value = ''
          }
        } catch (e) { /* skip malformed line */ }
      }
      // Throttle: render at most every 50ms
      const now = Date.now()
      if (now - lastRender > 50) { await nextTick(); lastRender = now }
    }
    if (!receivedDone && generatingStatus.value) {
      generatingStatus.value = ''
      toast.error('生成连接中断')
    }
  } catch (e) {
    toast.error('生成失败: ' + e.message)
    generatingStatus.value = ''
  } finally { generating.value = false }
}

function openEdit(row) {
  isEditing.value = true
  generatingStatus.value = ''
  form.value = {
    name: row.name,
    industry: row.industry,
    description: row.description,
    contentJson: JSON.stringify(row.content, null, 2),
  }
  dialogOpen.value = true
}

async function handleSave() {
  let content
  try { content = JSON.parse(form.value.contentJson) }
  catch (e) { toast.error('JSON 格式无效: ' + e.message); return }
  saving.value = true
  try {
    if (isEditing.value) {
      await api.updateTemplate(form.value.name, { content, industry: form.value.industry, description: form.value.description })
      toast.success('模板已更新')
    } else {
      await api.createTemplate({ name: form.value.name, industry: form.value.industry, description: form.value.description, content })
      toast.success('模板已创建')
    }
    dialogOpen.value = false
    fetchTemplates()
  } catch (e) {
    toast.error('保存失败')
  } finally { saving.value = false }
}

async function handleToggle(row, enabled) {
  const prev = row.enabled
  row.enabled = enabled  // optimistic update
  try {
    await api.toggleTemplate(row.name, enabled)
    toast.success(enabled ? '已启用' : '已禁用')
  } catch (e) {
    row.enabled = prev  // rollback on failure
    toast.error('操作失败')
  }
}

function openDeleteConfirm(row) { deletingName.value = row.name; showDeleteDialog.value = true }

async function handleDelete() {
  try {
    await api.deleteTemplate(deletingName.value)
    toast.success('模板已删除')
    showDeleteDialog.value = false
    deletingName.value = null
    fetchTemplates()
  } catch (e) { toast.error('删除失败') }
}

onMounted(fetchTemplates)
</script>

<template>
  <div class="prompt-templates-page">
    <!-- === Header === -->
    <div class="flex flex-wrap items-center justify-between gap-4 mb-8">
      <div>
        <h2 class="text-2xl font-bold tracking-tight">
          <span class="gradient-text">提示词模板</span>
        </h2>
        <p class="mt-1.5 text-sm text-slate-400">
          配置 AI 提示词策略，覆盖视频评论、评论回复、私信转化三大场景。设备端自动同步
        </p>
      </div>
      <button class="btn-aurora inline-flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold" @click="openCreate">
        <!-- plus icon -->
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 4v16m8-8H4" />
        </svg>
        新建模板
      </button>
    </div>

    <!-- === Loading / Empty === -->
    <LoadingSpinner v-if="loading" />
    <EmptyState v-else-if="templates.length === 0" message="暂无提示词模板" />

    <!-- === Template Cards === -->
    <div v-else class="grid gap-5">
      <div
        v-for="tmpl in templates"
        :key="tmpl.name"
        :class="['glass-card p-6 transition-all duration-300', !tmpl.enabled && 'opacity-50']"
      >
        <div class="flex flex-col lg:flex-row lg:items-start gap-5">
          <!-- Left: core info -->
          <div class="flex-1 min-w-0 space-y-3">
            <!-- name row -->
            <div class="flex items-center gap-3 flex-wrap">
              <span class="font-mono text-lg font-bold text-white tracking-tight">{{ tmpl.name }}</span>
              <!-- industry badge -->
              <span class="badge-info">{{ industryLabel(tmpl.industry) }}</span>
              <!-- version -->
              <span class="inline-flex items-center rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20 px-2.5 py-0.5 text-[11px] font-semibold tracking-wide">
                v{{ tmpl.version }}
              </span>
              <!-- disabled -->
              <span v-if="!tmpl.enabled" class="badge-danger">已禁用</span>
            </div>

            <!-- description -->
            <p v-if="tmpl.description" class="text-sm text-slate-400 leading-relaxed">{{ tmpl.description }}</p>

            <!-- scenario badges -->
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-[11px] uppercase tracking-widest text-slate-500 font-semibold mr-1">场景覆盖</span>
              <span
                v-for="sc in scenePreview(tmpl.content)"
                :key="sc.key"
                class="inline-flex items-center gap-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] px-3 py-1 text-xs text-slate-300"
                :title="sc.desc"
              >
                <!-- video icon -->
                <svg v-if="sc.key === 'video'" class="w-3 h-3 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <!-- chat icon -->
                <svg v-if="sc.key === 'reply'" class="w-3 h-3 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                <!-- mail icon -->
                <svg v-if="sc.key === 'dm'" class="w-3 h-3 text-pink-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
                {{ sc.label }}
              </span>
              <span v-if="scenePreview(tmpl.content).length === 0" class="text-xs text-slate-500">未配置</span>
            </div>

            <!-- meta -->
            <div class="flex items-center gap-4 text-xs text-slate-500">
              <span>更新于 {{ formatDate(tmpl.updated_at) }}</span>
            </div>
          </div>

          <!-- Right: actions -->
          <div class="flex items-center gap-4 flex-shrink-0">
            <SwitchGroup>
              <div class="flex items-center gap-2.5">
                <SwitchLabel class="text-xs font-medium text-slate-400 cursor-pointer select-none uppercase tracking-wider">
                  {{ tmpl.enabled ? 'ON' : 'OFF' }}
                </SwitchLabel>
                <Switch
                  :model-value="tmpl.enabled"
                  :class="tmpl.enabled ? 'bg-indigo-500' : 'bg-slate-600'"
                  class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:ring-offset-0"
                  @update:model-value="(val) => handleToggle(tmpl, val)"
                >
                  <span
                    :class="tmpl.enabled ? 'translate-x-[18px]' : 'translate-x-[2px]'"
                    class="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow-sm transition-transform duration-200"
                  />
                </Switch>
              </div>
            </SwitchGroup>

            <button
              class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-cyan-400 hover:text-cyan-200 hover:bg-cyan-400/10 transition-all duration-200"
              @click="openEdit(tmpl)"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              编辑
            </button>
            <button
              class="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-red-400 hover:text-red-200 hover:bg-red-400/10 transition-all duration-200"
              @click="openDeleteConfirm(tmpl)"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- === Create / Edit Dialog === -->
    <TransitionRoot :show="dialogOpen" as="template">
      <Dialog as="div" class="relative z-50" @close="dialogOpen = false">
        <TransitionChild as="template" enter="ease-out duration-200" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-150" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/60 backdrop-blur-sm" />
        </TransitionChild>

        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-200" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-150" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="glass-card w-full max-w-2xl p-6">
                <DialogTitle as="h3" class="text-lg font-bold text-white mb-1">
                  {{ isEditing ? '编辑模板' : '新建模板' }}
                </DialogTitle>
                <p class="text-sm text-slate-400 mb-6">
                  提示词模板包含身份设定、语义分析指南、评分规则、场景提示词等完整配置
                </p>

                <div class="space-y-4">
                  <!-- name -->
                  <div>
                    <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                      模板名称 <span class="text-red-400">*</span>
                    </label>
                    <input
                      v-model="form.name"
                      :disabled="isEditing"
                      class="w-full rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 py-2.5 text-sm text-white placeholder-slate-500 transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed font-mono"
                      placeholder="health-default"
                    />
                  </div>

                  <!-- industry -->
                  <div>
                    <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                      行业 <span class="text-red-400">*</span>
                    </label>
                    <input
                      v-model="form.industry"
                      list="industry-presets"
                      class="w-full rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 py-2.5 text-sm text-white placeholder-slate-500 transition-all duration-200"
                      placeholder="输入行业标识，如 health / travel / education"
                    />
                    <datalist id="industry-presets">
                      <option value="health">大健康</option>
                      <option value="travel">旅游</option>
                      <option value="education">教育</option>
                      <option value="finance">金融</option>
                      <option value="beauty">美妆</option>
                      <option value="realestate">房产</option>
                      <option value="auto">汽车</option>
                    </datalist>
                  </div>

                  <!-- description -->
                  <div>
                    <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">描述</label>
                    <input
                      v-model="form.description"
                      class="w-full rounded-xl bg-white/[0.04] border border-white/[0.08] px-4 py-2.5 text-sm text-white placeholder-slate-500 transition-all duration-200"
                      placeholder="简要说明模板的用途和适用场景"
                    />
                  </div>

                  <!-- AI generate card -->
                  <div v-if="!isEditing" class="rounded-xl border border-purple-500/20 bg-purple-500/[0.03] p-4 space-y-3">
                    <div class="flex items-center gap-2">
                      <svg class="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      <span class="text-sm font-semibold text-purple-300">AI 智能生成</span>
                      <span class="text-xs text-slate-500">— 用自然语言描述需求，AI 自动生成完整模板</span>
                    </div>
                    <div class="flex gap-2">
                      <input
                        v-model="aiDesc"
                        class="flex-1 rounded-lg bg-slate-900/60 border border-white/[0.08] px-3.5 py-2 text-sm text-white placeholder-slate-500 transition-all duration-200"
                        placeholder="例如：大健康行业，针对糖尿病和高血压相关评论进行截流，语气温和专业，偏向中老年用户"
                        @keydown.enter="handleGenerate"
                      />
                      <button
                        class="btn-aurora rounded-lg px-4 py-2 text-sm font-semibold inline-flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
                        :disabled="generating || !aiDesc.trim()"
                        @click="handleGenerate"
                      >
                        <svg v-if="generating" class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        {{ generating ? '生成中...' : '生成模板' }}
                      </button>
                    </div>
                  </div>

                  <!-- content JSON -->
                  <div>
                    <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                      模板内容 JSON <span class="text-red-400">*</span>
                    </label>
                    <div v-if="generatingStatus" class="flex items-center gap-2 mb-2 px-3 py-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/20">
                      <svg class="animate-spin w-3.5 h-3.5 text-cyan-400" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      <span class="text-xs text-cyan-300">{{ generatingStatus }}</span>
                    </div>
                    <textarea
                      v-model="form.contentJson"
                      :rows="18"
                      spellcheck="false"
                      class="w-full rounded-xl bg-slate-950/60 border border-white/[0.06] px-4 py-3 text-sm text-slate-200 font-mono leading-relaxed placeholder-slate-600 transition-all duration-200 resize-y"
                      placeholder='{
  "identity": { "role": "...", "constraints": [...] },
  "semanticGuide": { "mission": "...", "highValueSignals": [...], ... },
  "analysis": { "intents": [...], "scoringRules": [...], ... },
  "videoComment": { ... },
  "dmOpener": { ... },
  "dmStages": { ... },
  "localFilter": { "exclude": [...], "include": [...] },
  "disabledWords": "..."
}'
                    />
                    <p class="mt-2 text-[11px] text-slate-500 leading-relaxed">
                      必填字段: <code class="text-slate-400">identity</code>, <code class="text-slate-400">semanticGuide</code>, <code class="text-slate-400">analysis</code>, <code class="text-slate-400">localFilter</code>, <code class="text-slate-400">disabledWords</code>
                      &nbsp;|&nbsp; 场景字段: <code class="text-slate-400">videoComment</code> (场景1), <code class="text-slate-400">analysis.replyRules</code> (场景2), <code class="text-slate-400">dmOpener</code> + <code class="text-slate-400">dmStages</code> (场景3)
                    </p>
                  </div>
                </div>

                <!-- footer -->
                <div class="mt-6 flex justify-end gap-3 pt-4 border-t border-white/[0.06]">
                  <button
                    class="rounded-xl px-5 py-2.5 text-sm font-semibold text-slate-400 hover:text-white hover:bg-white/[0.04] transition-all duration-200"
                    @click="dialogOpen = false"
                    :disabled="saving"
                  >
                    取消
                  </button>
                  <button
                    class="btn-aurora rounded-xl px-5 py-2.5 text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-2"
                    @click="handleSave"
                    :disabled="saving"
                  >
                    <svg v-if="saving" class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    {{ saving ? '保存中...' : (isEditing ? '更新模板' : '创建模板') }}
                  </button>
                </div>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>

    <!-- === Delete Confirm === -->
    <ConfirmDialog
      :open="showDeleteDialog"
      :message="deletingName ? `确定删除模板「${deletingName}」吗？此操作不可撤销，设备端将回退到本地默认配置。` : ''"
      confirm-text="确认删除"
      danger
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false; deletingName = null"
    />
  </div>
</template>
```

## src/views/ScenesPage.vue

```html
<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-100">场景资产库</h1>
        <p class="text-sm text-slate-400 mt-1">管理拍摄场景，配置光照氛围和参考图</p>
      </div>
      <div class="flex gap-2">
        <button @click="showAiGen = true" class="bg-purple-500 hover:bg-purple-400 text-white px-4 py-2 rounded-lg transition cursor-pointer text-sm" title="输入故事概要，AI 自动生成场景描述">
          AI 批量生成
        </button>
        <button @click="showCreate = true" class="bg-sky-500 hover:bg-sky-400 text-white px-4 py-2 rounded-lg transition cursor-pointer" title="创建新场景，描述后可生成多角度参考图">
          + 新建场景
        </button>
      </div>
    </div>

    <div v-if="loading" class="text-slate-400 text-center py-12">加载中...</div>
    <div v-else-if="error" class="text-red-400 text-center py-12">{{ error }}</div>
    <div v-else-if="scenes.length === 0" class="text-slate-500 text-center py-12">
      暂无场景<br><span class="text-xs text-slate-600 mt-1">提示：创建场景后可在系列详情中关联到具体剧集</span>
    </div>
    <div v-else class="grid grid-cols-3 gap-4">
      <div v-for="s in scenes" :key="s.id"
           class="rounded-xl border border-gray-700/50 p-4 hover:shadow-lg hover:shadow-sky-900/10 transition-all duration-200"
           style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);">
        <h3 class="font-semibold text-slate-100">{{ s.name }}</h3>
        <div class="flex gap-2 mt-2 text-xs">
          <span class="px-2 py-1 rounded bg-gray-800 text-slate-400">{{ sceneTypeLabel(s.scene_type) }}</span>
          <span class="px-2 py-1 rounded bg-gray-800 text-slate-400">{{ lightingLabel(s.lighting) || '-' }}</span>
          <span class="px-2 py-1 rounded bg-gray-800 text-slate-400">{{ moodLabel(s.mood) || '-' }}</span>
        </div>
        <p class="text-sm text-slate-400 mt-2">{{ s.location_desc || '(无地点描述)' }}</p>
        <div class="flex gap-1 mt-2">
          <span :class="s.reference_wideshot_url ? 'text-emerald-400' : 'text-slate-600'" class="text-xs">{{ s.reference_wideshot_url ? '广角 ✓' : '广角 —' }}</span>
          <span :class="s.reference_midshot_url ? 'text-emerald-400' : 'text-slate-600'" class="text-xs">{{ s.reference_midshot_url ? '中景 ✓' : '中景 —' }}</span>
          <span :class="s.reference_aerial_url ? 'text-emerald-400' : 'text-slate-600'" class="text-xs">{{ s.reference_aerial_url ? '俯拍 ✓' : '俯拍 —' }}</span>
        </div>
      </div>
    </div>

    <!-- AI 批量生成对话框 -->
    <div v-if="showAiGen" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50" @click.self="showAiGen = false">
      <div class="rounded-xl p-6 w-full max-w-lg shadow-2xl border border-gray-700/50 max-h-[85vh] overflow-y-auto" style="background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(20px);">
        <h2 class="text-lg font-semibold text-slate-100 mb-4">AI 批量生成场景</h2>
        <p class="text-xs text-slate-500 mb-4">输入故事概要，AI 自动分析并生成场景描述。确认后批量创建。</p>
        <div class="space-y-3">
          <div>
            <textarea v-model="aiForm.text" placeholder="输入故事概要/剧本片段..." rows="4" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500/50 transition" />
          </div>
          <div class="flex gap-3">
            <div class="flex-1">
              <select v-model="aiForm.genre" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 cursor-pointer">
                <option v-for="g in genreOptions" :key="g.value" :value="g.value">{{ g.label }}</option>
              </select>
            </div>
            <div class="w-24">
              <input v-model.number="aiForm.count" type="number" min="1" max="10" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 focus:outline-none focus:ring-2 focus:ring-purple-500/50 transition" />
            </div>
          </div>
        </div>

        <div v-if="aiGenerating" class="text-center py-8">
          <div class="animate-spin w-8 h-8 border-2 border-purple-400 border-t-transparent rounded-full mx-auto mb-3"></div>
          <p class="text-sm text-slate-400">AI 正在分析故事，生成场景...</p>
        </div>

        <div v-else-if="aiResult.length" class="mt-4 space-y-2 max-h-[300px] overflow-y-auto">
          <p class="text-xs text-slate-500 mb-2">AI 生成了 {{ aiResult.length }} 个场景，勾选需要创建的：</p>
          <div v-for="(s, i) in aiResult" :key="i" class="flex items-start gap-3 rounded-lg p-3 border border-gray-700/50 hover:border-purple-500/30 transition" style="background: rgba(255,255,255,0.03);">
            <input type="checkbox" v-model="s._selected" class="mt-1" />
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="font-semibold text-slate-100">{{ s.name }}</span>
                <span class="text-xs px-2 py-0.5 rounded bg-gray-800 text-slate-400">{{ sceneTypeLabel(s.scene_type) }}</span>
                <span class="text-xs text-slate-500">{{ lightingLabel(s.lighting) || '-' }}</span>
                <span class="text-xs text-slate-500">{{ moodLabel(s.mood) || '-' }}</span>
              </div>
              <p class="text-xs text-slate-400 mt-1">{{ s.location_desc }}</p>
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-3 mt-6">
          <button @click="showAiGen = false; aiResult = []" class="px-4 py-2 rounded-lg border border-gray-600 text-slate-300 hover:bg-gray-700 transition cursor-pointer">取消</button>
          <button v-if="!aiResult.length" @click="doAiGenerate" :disabled="!aiForm.text || aiGenerating" class="px-4 py-2 bg-purple-500 hover:bg-purple-400 disabled:opacity-50 text-white rounded-lg transition cursor-pointer">{{ aiGenerating ? '生成中...' : 'AI 生成' }}</button>
          <button v-else @click="doBatchCreate" :disabled="aiBatchCreating" class="px-4 py-2 bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-white rounded-lg transition cursor-pointer">{{ aiBatchCreating ? '创建中...' : `批量创建 (${aiResult.filter(s => s._selected).length})` }}</button>
        </div>
      </div>
    </div>

    <div v-if="showCreate" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50" @click.self="showCreate = false">
      <div class="rounded-xl p-6 w-full max-w-md shadow-2xl border border-gray-700/50" style="background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(20px);">
        <h2 class="text-lg font-semibold text-slate-100 mb-4">新建场景</h2>
        <div class="space-y-3">
          <div>
            <input v-model="form.name" placeholder="场景名称" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </div>
          <div>
            <select v-model="form.scene_type" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 cursor-pointer">
              <option v-for="t in typeOptions" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
            <p class="text-xs text-slate-500 mt-1 ml-1">可在"系统字典"中管理场景类型</p>
          </div>
          <div>
            <input v-model="form.location_desc" placeholder="地点描述 — 如 'CBD高层写字楼，落地窗俯瞰城市'" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
            <p class="text-xs text-slate-500 mt-1 ml-1">描述越详细，AI 生成的场景图越准确</p>
          </div>
          <div class="flex gap-3">
            <div class="flex-1">
              <select v-model="form.lighting" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 cursor-pointer">
                <option v-for="l in lightingOptions" :key="l.value" :value="l.value">{{ l.label }}</option>
              </select>
            </div>
            <div class="flex-1">
              <select v-model="form.mood" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 cursor-pointer">
                <option v-for="m in moodOptions" :key="m.value" :value="m.value">{{ m.label }}</option>
              </select>
            </div>
          </div>
        </div>
        <div class="flex justify-end gap-3 mt-6">
          <button @click="showCreate = false" class="px-4 py-2 rounded-lg border border-gray-600 text-slate-300 hover:bg-gray-700 transition cursor-pointer">取消</button>
          <button @click="doCreate" class="px-4 py-2 bg-sky-500 hover:bg-sky-400 text-white rounded-lg transition cursor-pointer">创建</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { listScenes, createScene, autoGenerateScenes } from '../api/scenes.js'
import { listItems } from '../api/referenceData.js'

const scenes = ref([]); const loading = ref(true); const showCreate = ref(false); const showAiGen = ref(false); const error = ref('')
const typeOptions = ref([]); const lightingOptions = ref([]); const moodOptions = ref([]); const genreOptions = ref([])
const aiGenerating = ref(false); const aiBatchCreating = ref(false); const aiResult = ref([])
const form = reactive({ name: '', scene_type: 'indoor', location_desc: '', lighting: '', mood: '' })
const aiForm = reactive({ text: '', genre: 'drama', count: 5 })

async function loadOpts() {
  try {
    const [t, l, m, g] = await Promise.all([
      listItems('scene_type'), listItems('scene_lighting'), listItems('scene_mood'), listItems('series_genre')
    ])
    if (t.data.ok) { typeOptions.value = t.data.items; form.scene_type = t.data.items[0]?.value || 'indoor' }
    if (l.data.ok) lightingOptions.value = l.data.items
    if (m.data.ok) moodOptions.value = m.data.items
    if (g.data.ok) genreOptions.value = g.data.items
  } catch (e) {}
}
async function load() { loading.value = true; error.value = ''; try { const { data } = await listScenes(); scenes.value = data.ok ? data.scenes : [] } catch (e) { error.value = e.message || '加载失败' } finally { loading.value = false } }
async function doCreate() { error.value = ''; try { await createScene({ ...form }); showCreate.value = false; await load() } catch (e) { error.value = e.message || '创建失败' } }
async function doAiGenerate() {
  aiGenerating.value = true; aiResult.value = []; error.value = ''
  try {
    const { data } = await autoGenerateScenes(aiForm.text, aiForm.genre, aiForm.count)
    if (data.ok) {
      aiResult.value = (data.scenes || []).map(s => ({ ...s, _selected: true }))
    } else throw new Error('生成失败')
  } catch (e) { error.value = e.response?.data?.detail || e.message || 'AI 生成失败' } finally { aiGenerating.value = false }
}
async function doBatchCreate() {
  const selected = aiResult.value.filter(s => s._selected)
  if (!selected.length) return
  aiBatchCreating.value = true; error.value = ''
  try {
    for (const s of selected) {
      await createScene({
        name: s.name, scene_type: s.scene_type, location_desc: s.location_desc,
        lighting: s.lighting, mood: s.mood,
      })
    }
    showAiGen.value = false; aiResult.value = []
    await load()
  } catch (e) { error.value = e.response?.data?.detail || e.message || '批量创建失败' } finally { aiBatchCreating.value = false }
}
function sceneTypeLabel(v) { const x = typeOptions.value.find(o => o.value === v); return x ? x.label : v }
function lightingLabel(v) { const x = lightingOptions.value.find(o => o.value === v); return x ? x.label : v }
function moodLabel(v) { const x = moodOptions.value.find(o => o.value === v); return x ? x.label : v }
onMounted(async () => { await loadOpts(); await load() })
</script>
```

## src/views/SelectorsPage.vue

```html
<script setup>
import { ref, reactive, onMounted, watch, computed } from 'vue'
import {
  Dialog,
  DialogPanel,
  DialogTitle,
  TransitionRoot,
  TransitionChild,
  Switch,
  SwitchGroup,
  SwitchLabel,
} from '@headlessui/vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import EmptyState from '../components/EmptyState.vue'
import StrategyCard from '../components/StrategyCard.vue'
import {
  listSelectors,
  createSelector,
  updateSelector,
  deleteSelector,
  toggleSelector,
  generateRegex,
  generateCleanPrompt,
} from '../api/selectors.js'
import { useToastStore } from '../stores/toast.js'
import { useSavedPrompt } from '../composables/useSavedPrompt.js'
import { useWebSocket } from '../composables/useWebSocket.js'

// 动作名称中文说明
const actionDescriptions = {
  back_btn: '返回按钮',
  open_app: '打开抖音 App',
  video_comment_btn: '视频评论入口按钮（点击打开评论面板）',
  video_comment_input: '视频评论输入框（需先点击弹出键盘）',
  search_tab: '搜索标签页入口',
  search_input: '搜索输入框',
  search_button: '搜索按钮',
  search_suggestion: '搜索建议词',
  search_suggestion_list: '搜索联想词列表容器',
  search_video_tab: '搜索结果-视频标签页',
  search_video_list: '搜索结果-视频列表容器',
  video_tab: '视频标签页',
  video_author_avatar: '视频作者头像（点击进入主页）',
  sort_button: '排序按钮',
  sort_latest: '最新排序选项',
  sort_most_liked: '最多点赞排序选项',
  sort_default: '默认排序选项',
  like_button: '点赞按钮',
  follow_button: '关注按钮',
  comment_input: '评论输入框',
  comment_submit: '评论提交按钮',
  comment_reply_button: '评论回复按钮',
  comment_reply_input: '评论回复输入框',
  comment_reply_submit: '评论回复提交按钮',
  comment_list: '评论列表容器',
  comment_text: '评论内容文本',
  comment_author: '评论作者昵称',
  comment_time: '评论发布时间',
  comment_like_count: '评论点赞数',
  comment_author_avatar: '评论作者头像',
  message_button: '私信按钮',
  dm_input: '私信输入框',
  dm_send: '私信发送按钮',
  profile_more: '个人主页更多菜单',
}

// Tooltip content for each field
const tooltips = {
  action_name: {
    title: '动作名称（必填）',
    desc: '选择器的唯一标识符，对应设备端要执行的操作名称。命名规则：小写字母+下划线，例如 like_video、comment_video、search_keyword。设备端任务执行时会根据此名称查找对应的选择器。',
    examples: '常用值：like_video（点赞）、comment_video（评论）、search_keyword（搜索）、follow_user（关注）、reply_comment（回复评论）、send_dm（私信）',
  },
  platform_version: {
    title: '平台版本（可选）',
    desc: '抖音 App 的版本号，用于多版本适配。不同版本的抖音界面布局可能不同，可以为同一动作创建多个选择器，每个针对不同版本。留空表示适用于所有版本。',
    examples: '例如：29.0.0、28.5.1。设备端会优先匹配精确版本，找不到则使用无版本号的通用选择器',
  },
  strategies: {
    title: '选择策略数组（必填）',
    desc: 'JSON 数组，定义如何在屏幕上定位目标 UI 元素。每个策略是一种查找方式，系统按 priority 顺序依次尝试，直到找到元素为止。支持单条件匹配、多条件 AND/OR 组合匹配。',
    types: [
      { type: 'text', value: '通过文本内容查找', fields: 'value: 要匹配的文本，match_mode: 匹配模式（exact 精确/contains 包含）' },
      { type: 'id', value: '通过资源 ID 查找', fields: 'value: Android 资源 ID，match_mode: 匹配模式（exact/contains）' },
      { type: 'desc', value: '通过内容描述查找', fields: 'value: contentDescription 属性值，match_mode: 匹配模式（exact/contains）' },
      { type: 'className', value: '通过类名查找', fields: 'value: Android 控件类名，match_mode: 匹配模式（exact/contains）' },
      { type: 'package', value: '通过包名查找', fields: 'value: 应用包名，如 com.ss.android.ugc.aweme' },
      { type: 'coordinate', value: '通过固定坐标点击', fields: 'x_percent: X 百分比(0-100)，y_percent: Y 百分比(0-100)' },
      { type: 'image', value: '通过图片模板匹配', fields: 'template: 模板图片路径，threshold: 匹配阈值(0-1，默认0.8)' },
      { type: 'chain', value: '链式查找（原生语法）', fields: 'steps: [{type,value}] 按顺序链式匹配，所有步骤必须匹配同一元素，比 AND 更快更精准' },
    ],
    commonFields: '通用字段：type、value、priority（数字越小越优先）、match_mode（exact/contains，默认 exact）。多条件模式：conditions（条件数组）+ logic（and/or），每个条件含 type/value/match_mode。',
  },
}

// --- Data state ---
const selectors = ref([])
const loading = ref(false)
const includeDisabled = ref(false)

// --- Version filter ---
const versionFilter = ref('default')

const availableVersions = computed(() => {
  const versions = new Set()
  for (const s of selectors.value) {
    versions.add(s.platform_version || 'default')
  }
  return Array.from(versions).sort()
})

// --- Category filter ---
const categoryFilter = ref('all')
const categoryTabs = [
  { key: 'all', label: '全部' },
  { key: 'page_detect', label: '页面检测' },
  { key: 'search', label: '搜索相关' },
  { key: 'comment', label: '评论相关' },
  { key: 'dm', label: '私信相关' },
  { key: 'video', label: '视频相关' },
  { key: 'sort', label: '排序相关' },
  { key: 'system', label: '系统相关' },
  { key: 'collect', label: '采集相关' },
  { key: '', label: '未分类' },
]

const categoryOptions = [
  { value: '', label: '未分类' },
  { value: 'page_detect', label: '页面检测' },
  { value: 'search', label: '搜索相关' },
  { value: 'comment', label: '评论相关' },
  { value: 'dm', label: '私信相关' },
  { value: 'video', label: '视频相关' },
  { value: 'sort', label: '排序相关' },
  { value: 'system', label: '系统相关' },
  { value: 'collect', label: '采集相关' },
]

function getCategoryLabel(cat) {
  const opt = categoryOptions.find(o => o.value === cat)
  return opt ? opt.label : '未分类'
}

const categoryColorMap = {
  page_detect: 'bg-amber-500/15 text-amber-300 border-amber-500/25',
  search: 'bg-blue-500/15 text-blue-300 border-blue-500/25',
  comment: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/25',
  dm: 'bg-pink-500/15 text-pink-300 border-pink-500/25',
  video: 'bg-amber-500/15 text-amber-300 border-amber-500/25',
  sort: 'bg-violet-500/15 text-violet-300 border-violet-500/25',
  system: 'bg-slate-500/15 text-slate-300 border-slate-500/25',
  collect: 'bg-orange-500/15 text-orange-300 border-orange-500/25',
}

function getCategoryClass(cat) {
  return categoryColorMap[cat] || 'bg-cyan-500/15 text-cyan-300 border-cyan-500/25'
}

function _matchVersion(s) {
  return (s.platform_version || 'default')
}

const filteredSelectors = computed(() => {
  let list = selectors.value
  if (versionFilter.value !== 'all') {
    list = list.filter(s => _matchVersion(s) === versionFilter.value)
  }
  if (categoryFilter.value !== 'all') {
    list = list.filter(s => (s.category || '') === categoryFilter.value)
  }
  return list
})

const categoryCounts = computed(() => {
  let base = versionFilter.value === 'all'
    ? selectors.value
    : selectors.value.filter(s => _matchVersion(s) === versionFilter.value)
  const counts = { all: base.length }
  for (const s of base) {
    const cat = s.category || ''
    counts[cat] = (counts[cat] || 0) + 1
  }
  return counts
})

// --- Form / Dialog state ---
const showFormDialog = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const formError = ref(null)

const defaultForm = {
  action_name: '',
  description: '',
  platform_version: '',
  resolution_profile: 'default',
  strategies: '[]',
  category: '',
}
// --- AI generation state ---
const generatingRegex = ref(false)
const generatingPrompt = ref(false)
const regexAiPrompt = useSavedPrompt('selector_regex', '')
const cleanAiPrompt = useSavedPrompt('selector_clean', '')

async function generateRegexAI() {
  if (!regexAiPrompt.value.trim()) {
    formError.value = '请输入正则需求描述'
    return
  }
  generatingRegex.value = true
  try {
    const res = await generateRegex(regexAiPrompt.value.trim())
    form.clean_pattern = res.data.regex || res.data.pattern || ''
  } catch (e) {
    formError.value = '正则生成失败: ' + (e.response?.data?.detail || e.message)
  } finally {
    generatingRegex.value = false
  }
}

async function generateCleanPromptAI() {
  if (!cleanAiPrompt.value.trim()) {
    formError.value = '请输入清洗需求描述'
    return
  }
  generatingPrompt.value = true
  try {
    const res = await generateCleanPrompt(cleanAiPrompt.value.trim())
    form.clean_prompt = res.data.prompt || ''
  } catch (e) {
    formError.value = '提示词生成失败: ' + (e.response?.data?.detail || e.message)
  } finally {
    generatingPrompt.value = false
  }
}

const form = reactive({ ...defaultForm })

// --- Strategy card builder state ---
const editMode = ref('form') // 'form' | 'json'
const strategyList = ref([])

// Normalize legacy condition types: classNameContains → type:className + match_mode:contains
// (Chain steps use their own type system — classNameContains is valid there, do NOT touch)
function _normalizeLegacyTypes(strategies) {
  const MAP = { classNameContains: 'className', idContains: 'id', textContains: 'text', descContains: 'desc' }
  for (const s of strategies) {
    if (s.conditions) {
      for (const c of s.conditions) {
        if (MAP[c.type]) { c.match_mode = 'contains'; c.type = MAP[c.type] }
      }
    }
  }
  return strategies
}

function syncStrategiesToList() {
  try {
    strategyList.value = _normalizeLegacyTypes(JSON.parse(form.strategies || '[]'))
  } catch {
    strategyList.value = []
  }
}

function syncListToStrategies() {
  form.strategies = JSON.stringify(_normalizeLegacyTypes(strategyList.value), null, 2)
}

function addStrategy() {
  strategyList.value.push({ type: 'text', value: '', priority: strategyList.value.length + 1 })
  syncListToStrategies()
}

function updateStrategy(index, newStrategy) {
  strategyList.value[index] = newStrategy
  syncListToStrategies()
}

function deleteStrategy(index) {
  strategyList.value.splice(index, 1)
  // Re-index priorities
  strategyList.value.forEach((s, i) => { s.priority = i + 1 })
  syncListToStrategies()
}

function moveStrategy(index, direction) {
  const target = index + direction
  if (target < 0 || target >= strategyList.value.length) return
  const tmp = strategyList.value[index]
  strategyList.value[index] = strategyList.value[target]
  strategyList.value[target] = tmp
  // Re-index priorities
  strategyList.value.forEach((s, i) => { s.priority = i + 1 })
  syncListToStrategies()
}

// --- Delete confirmation state ---
const showDeleteDialog = ref(false)
const deletingSelector = ref(null)
const deleting = ref(false)

// --- Page-level error ---
const pageError = ref(null)
const toast = useToastStore()

// --- WebSocket ---
function wsUrl() {
  const token = localStorage.getItem('token') || ''
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/api/devices/ws/pair-events?token=${encodeURIComponent(token)}`
}
useWebSocket(wsUrl, {
  onMessage(msg) {
    if (msg.event === 'selectors_changed') fetchSelectors()
  },
})

// --- Fetch selectors ---
async function fetchSelectors() {
  loading.value = true
  try {
    const res = await listSelectors(includeDisabled.value)
    selectors.value = res.data.selectors || []
  } catch (e) {
    toast.error('加载选择器列表失败')
    selectors.value = []
  } finally {
    loading.value = false
  }
}

// Re-fetch when includeDisabled changes
watch(includeDisabled, () => {
  fetchSelectors()
})

// --- Format strategy summary ---
function formatStrategies(strategies) {
  if (!strategies || strategies.length === 0) return '无策略'
  const parts = strategies.map((s) => {
    if (s.type === "chain" && s.steps) {
      const stepStrs = s.steps.map(st => (st.nav === "parent" ? "parent" : st.nav === "child" ? "child:" + st.type : st.type + ":" + (st.value || "").slice(0, 8)))
      return "chain[" + stepStrs.join(" -> ") + "]"
    }
    if (s.conditions && s.conditions.length > 0) {
      const logic = s.logic === 'or' ? ' OR ' : ' AND '
      const condStrs = s.conditions.map(c => `${c.type}:${(c.value || '').slice(0, 15)}`)
      return `[${condStrs.join(logic)}]`
    }
    const val = s.value && s.value.length > 20 ? s.value.slice(0, 20) + '...' : s.value
    const mode = s.match_mode === 'contains' ? '~' : ''
    return `${mode}${s.type}:${val}`
  })
  return `${strategies.length} 个策略: ${parts.join(', ')}`
}

// --- Open create dialog ---
function openCreateDialog() {
  isEditing.value = false
  form.action_name = ''
  form.description = ''
  form.platform_version = ''
  form.resolution_profile = 'default'
  form.strategies = '[]'
  form.category = ''
  form.purpose = 'locate'
  form.strategy_logic = 'and'
  form.extract_field = 'text'
  form.clean_mode = 'raw'
  form.clean_pattern = ''
  form.clean_prompt = ''
  regexAiPrompt.value = ''
  cleanAiPrompt.value = ''
  editMode.value = 'form'
  strategyList.value = []
  formError.value = null
  showFormDialog.value = true
}

// --- Open edit dialog ---
function openEditDialog(sel) {
  isEditing.value = true
  form.action_name = sel.action_name
  form.description = sel.description || ''
  form.platform_version = sel.platform_version || ''
  form.resolution_profile = sel.resolution_profile || 'default'
  form.strategies = JSON.stringify(sel.strategies || [], null, 2)
  form.category = sel.category || ''
  form.purpose = sel.purpose || 'locate'
  form.strategy_logic = sel.strategy_logic || 'and'
  form.extract_field = sel.extract_field || 'text'
  form.clean_mode = sel.clean_mode || 'raw'
  form.clean_pattern = sel.clean_pattern || ''
  form.clean_prompt = sel.clean_prompt || ''
  editMode.value = 'form'
  syncStrategiesToList()
  formError.value = null
  showFormDialog.value = true
}

// --- Save (create or update) ---
async function handleSave() {
  if (!form.action_name.trim()) {
    formError.value = 'action_name 不能为空'
    return
  }

  let parsedStrategies
  try {
    parsedStrategies = JSON.parse(form.strategies)
    if (!Array.isArray(parsedStrategies)) {
      formError.value = 'strategies 必须是 JSON 数组'
      return
    }
  } catch {
    formError.value = 'strategies JSON 格式不正确'
    return
  }

  saving.value = true
  formError.value = null

  const payload = {
    strategies: parsedStrategies,
    platform_version: form.platform_version.trim() || undefined,
    resolution_profile: form.resolution_profile.trim() || 'default',
    description: form.description.trim() || '',
    category: form.category || '',
    purpose: form.purpose || 'locate',
    strategy_logic: form.purpose === 'page_detect' ? (form.strategy_logic || 'and') : undefined,
    extract_field: form.purpose === 'extract' ? (form.extract_field || 'text') : undefined,
    clean_mode: form.purpose === 'extract' ? (form.clean_mode || 'raw') : undefined,
    clean_pattern: form.purpose === 'extract' && form.clean_mode === 'regex' ? (form.clean_pattern || undefined) : undefined,
    clean_prompt: form.purpose === 'extract' && form.clean_mode === 'ai' ? (form.clean_prompt || undefined) : undefined,
  }

  try {
    if (isEditing.value) {
      await updateSelector(form.action_name, payload)
    } else {
      payload.action_name = form.action_name.trim()
      await createSelector(payload)
    }
    showFormDialog.value = false
    fetchSelectors()
  } catch (e) {
    formError.value =
      e.response?.data?.message ||
      e.response?.data?.detail ||
      '保存失败，请重试'
  } finally {
    saving.value = false
  }
}

// --- Delete ---
function openDeleteDialog(sel) {
  deletingSelector.value = sel
  showDeleteDialog.value = true
}

async function handleDelete() {
  if (!deletingSelector.value) return
  deleting.value = true
  try {
    await deleteSelector(deletingSelector.value.action_name)
    showDeleteDialog.value = false
    deletingSelector.value = null
    fetchSelectors()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '删除失败，请重试'
  } finally {
    deleting.value = false
  }
}

// --- Toggle enabled ---
async function handleToggle(sel, newValue) {
  const previous = sel.enabled
  sel.enabled = newValue
  try {
    await toggleSelector(sel.action_name, newValue)
  } catch (e) {
    sel.enabled = previous
    pageError.value = e.response?.data?.detail || '切换失败，请重试'
  }
}

// --- Init ---
onMounted(fetchSelectors)
</script>

<template>
  <div>
    <!-- Page error banner -->
    <div v-if="pageError" class="mb-4 glass-card border-red-500/30 text-red-400 px-4 py-3 rounded-xl flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-400 hover:text-red-300 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white">选择器管理</h1>
      <div class="flex items-center gap-4">
        <!-- Include disabled toggle -->
        <label class="flex items-center gap-2 text-sm text-slate-400 cursor-pointer select-none">
          <input
            v-model="includeDisabled"
            type="checkbox"
            class="h-4 w-4 rounded border-white/20 bg-white/5 text-purple-500 focus:ring-purple-500"
          />
          显示已禁用
        </label>
        <!-- Add button -->
        <button
          class="inline-flex items-center px-4 py-2 btn-aurora text-sm font-medium rounded-xl transition-colors"
          @click="openCreateDialog"
        >
          <svg
            class="-ml-1 mr-2 h-5 w-5"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"
            />
          </svg>
          <span class="relative z-10">添加选择器</span>
        </button>
      </div>
    </div>

    <!-- Version filter tabs -->
    <div class="flex items-center gap-2 mb-3 overflow-x-auto pb-1">
      <button
        v-for="ver in ['all', ...availableVersions]"
        :key="ver"
        :class="[
          'px-3 py-1.5 text-sm font-medium rounded-lg whitespace-nowrap transition-colors',
          versionFilter === ver
            ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
            : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent',
        ]"
        @click="versionFilter = ver"
      >
        {{ ver === 'all' ? '全部版本' : ver === 'default' ? '默认版本' : 'v' + ver }}
      </button>
    </div>

    <!-- Category tabs -->
    <div class="flex items-center gap-2 mb-4 overflow-x-auto pb-1">
      <button
        v-for="tab in categoryTabs"
        :key="tab.key"
        :class="[
          'px-3 py-1.5 text-sm font-medium rounded-lg whitespace-nowrap transition-colors',
          categoryFilter === tab.key
            ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
            : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent',
        ]"
        @click="categoryFilter = tab.key"
      >
        {{ tab.label }}
        <span v-if="categoryCounts[tab.key]" class="ml-1 text-xs opacity-60">
          ({{ categoryCounts[tab.key] || 0 }})
        </span>
      </button>
    </div>

    <!-- Loading -->
    <LoadingSpinner v-if="loading" />

    <!-- Empty state -->
    <EmptyState v-else-if="filteredSelectors.length === 0" :message="categoryFilter === 'all' ? '暂无选择器' : '当前分类暂无选择器'" />

    <!-- Selector cards -->
    <div v-else class="grid gap-4">
      <div
        v-for="sel in filteredSelectors"
        :key="sel.action_name + '_' + (sel.platform_version || 'default')"
        :class="[
          'glass-card p-5 transition-opacity',
          !sel.enabled && 'opacity-50',
        ]"
      >
        <div class="flex items-start justify-between">
          <!-- Left: info -->
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-3 flex-wrap">
              <span class="font-mono text-base font-semibold text-white" :title="'动作名称：' + sel.action_name">
                {{ sel.action_name }}
              </span>
              <span v-if="sel.description || actionDescriptions[sel.action_name]" class="text-sm text-slate-400">
                {{ sel.description || actionDescriptions[sel.action_name] }}
              </span>
              <span
                class="inline-flex items-center rounded-full bg-purple-500/15 text-purple-300 border border-purple-500/25 px-2.5 py-0.5 text-xs font-medium"
                :title="'选择器版本号，每次修改自动递增'"
              >
                v{{ sel.version }}
              </span>
              <span
                v-if="sel.platform_version"
                class="inline-flex items-center rounded-full bg-slate-500/15 text-slate-300 border border-slate-500/25 px-2.5 py-0.5 text-xs font-medium"
                :title="'适配的抖音版本：' + sel.platform_version"
              >
                平台 {{ sel.platform_version }}
              </span>
              <span
                v-if="sel.purpose === 'page_detect'"
                class="inline-flex items-center rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/25 px-2.5 py-0.5 text-xs font-medium"
                title="页面检测：多控件 AND 判定"
              >
                页面检测
              </span>
              <span
                v-if="sel.category"
                :class="[
                  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium',
                  getCategoryClass(sel.category),
                ]"
                :title="'操作分类：' + getCategoryLabel(sel.category)"
              >
                {{ getCategoryLabel(sel.category) }}
              </span>
              <span
                v-if="!sel.enabled"
                class="inline-flex items-center rounded-full bg-red-500/10 text-red-400 border border-red-500/20 px-2.5 py-0.5 text-xs font-medium"
                title="此选择器已禁用，设备端不会使用"
              >
                已禁用
              </span>
            </div>
            <p class="mt-2 text-sm text-slate-400" :title="'策略详情：' + JSON.stringify(sel.strategies)">
              {{ formatStrategies(sel.strategies) }}
            </p>
          </div>

          <!-- Right: toggle + actions -->
          <div class="ml-4 flex items-center gap-3 flex-shrink-0">
            <!-- Toggle switch -->
            <SwitchGroup>
              <div class="flex items-center gap-2">
                <SwitchLabel class="text-sm text-slate-400 cursor-pointer">
                  {{ sel.enabled ? '启用' : '禁用' }}
                </SwitchLabel>
                <Switch
                  :model-value="sel.enabled"
                  :class="sel.enabled ? 'bg-indigo-600' : 'bg-slate-600'"
                  class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-0"
                  @update:model-value="(val) => handleToggle(sel, val)"
                >
                  <span
                    :class="sel.enabled ? 'translate-x-6' : 'translate-x-1'"
                    class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                  />
                </Switch>
              </div>
            </SwitchGroup>

            <!-- Edit button -->
            <button
              class="inline-flex items-center px-3 py-1 text-sm font-medium text-cyan-400 hover:text-cyan-300 hover:bg-cyan-400/10 rounded transition-colors"
              @click="openEditDialog(sel)"
            >
              编辑
            </button>

            <!-- Delete button -->
            <button
              class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-400/10 rounded transition-colors"
              @click="openDeleteDialog(sel)"
            >
              删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Create / Edit Dialog -->
    <TransitionRoot :show="showFormDialog" as="template">
      <Dialog
        as="div"
        class="relative z-50"
        @close="showFormDialog = false"
      >
        <TransitionChild
          as="template"
          enter="ease-out duration-300"
          enter-from="opacity-0"
          enter-to="opacity-100"
          leave="ease-in duration-200"
          leave-from="opacity-100"
          leave-to="opacity-0"
        >
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>

        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild
              as="template"
              enter="ease-out duration-300"
              enter-from="opacity-0 scale-95"
              enter-to="opacity-100 scale-100"
              leave="ease-in duration-200"
              leave-from="opacity-100 scale-100"
              leave-to="opacity-0 scale-95"
            >
              <DialogPanel
                class="w-full max-w-2xl glass-card p-6 gradient-border"
              >
                <DialogTitle class="text-lg font-medium text-white">
                  {{ isEditing ? '编辑选择器' : '添加选择器' }}
                </DialogTitle>

                <!-- Error message -->
                <div
                  v-if="formError"
                  class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-3 py-2 rounded-lg"
                >
                  {{ formError }}
                </div>

                <form class="mt-4 space-y-4" @submit.prevent="handleSave">
                  <!-- action_name -->
                  <div>
                    <label
                      for="sel-action-name"
                      class="flex items-center gap-1.5 text-sm font-medium text-slate-300"
                    >
                      动作名称
                      <span class="text-red-400">*</span>
                      <span class="tooltip-trigger group relative inline-flex items-center">
                        <svg class="w-4 h-4 text-slate-500 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke-width="2"/><path stroke-linecap="round" d="M12 16v-4m0-4h.01" stroke-width="2"/></svg>
                        <span class="tooltip-content invisible group-hover:visible absolute z-50 left-6 top-0 w-80 p-3 text-xs font-normal text-slate-300 bg-slate-800 border border-white/10 rounded-lg shadow-xl leading-relaxed">
                          <span class="font-semibold text-white block mb-1">{{ tooltips.action_name.title }}</span>
                          {{ tooltips.action_name.desc }}<br><br>
                          <span class="text-cyan-400">{{ tooltips.action_name.examples }}</span>
                        </span>
                      </span>
                    </label>
                    <input
                      id="sel-action-name"
                      v-model="form.action_name"
                      type="text"
                      required
                      :disabled="isEditing"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 disabled:bg-white/5 disabled:text-slate-500 disabled:cursor-not-allowed font-mono"
                      placeholder="例如 like_video"
                    />
                    <p class="mt-1 text-xs text-slate-500">唯一标识符，对应设备端要执行的操作（如 like_video、comment_video）</p>
                  </div>

                  <!-- description -->
                  <div>
                    <label for="sel-description" class="flex items-center gap-1.5 text-sm font-medium text-slate-300">
                      说明
                    </label>
                    <input
                      id="sel-description"
                      v-model="form.description"
                      type="text"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                      placeholder="例如：视频评论入口按钮（点击打开评论面板）"
                    />
                    <p class="mt-1 text-xs text-slate-500">可选，描述此选择器的用途，方便后续管理</p>
                  </div>

                  <!-- platform_version -->
                  <div>
                    <label
                      for="sel-platform-version"
                      class="flex items-center gap-1.5 text-sm font-medium text-slate-300"
                    >
                      平台版本
                      <span class="tooltip-trigger group relative inline-flex items-center">
                        <svg class="w-4 h-4 text-slate-500 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke-width="2"/><path stroke-linecap="round" d="M12 16v-4m0-4h.01" stroke-width="2"/></svg>
                        <span class="tooltip-content invisible group-hover:visible absolute z-50 left-6 top-0 w-80 p-3 text-xs font-normal text-slate-300 bg-slate-800 border border-white/10 rounded-lg shadow-xl leading-relaxed">
                          <span class="font-semibold text-white block mb-1">{{ tooltips.platform_version.title }}</span>
                          {{ tooltips.platform_version.desc }}<br><br>
                          <span class="text-cyan-400">{{ tooltips.platform_version.examples }}</span>
                        </span>
                      </span>
                    </label>
                    <input
                      id="sel-platform-version"
                      v-model="form.platform_version"
                      type="text"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                      placeholder="例如 29.0.0（留空表示所有版本）"
                    />
                    <p class="mt-1 text-xs text-slate-500">抖音 App 版本号，用于多版本适配，留空表示通用</p>
                  </div>

                  <!-- resolution_profile -->
                  <div>
                    <label for="sel-resolution-profile" class="flex items-center gap-1.5 text-sm font-medium text-slate-300">
                      resolution_profile
                    </label>
                    <input
                      id="sel-resolution-profile"
                      v-model="form.resolution_profile"
                      type="text"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                      placeholder="default 或 1080x2340"
                    />
                    <p class="mt-1 text-xs text-slate-500">图片模板上传时会保存到 server/app/template_images/该目录</p>
                  </div>

                  <!-- category -->
                  <div>
                    <label for="sel-category" class="flex items-center gap-1.5 text-sm font-medium text-slate-300">
                      操作分类
                    </label>
                    <select
                      id="sel-category"
                      v-model="form.category"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
                    >
                      <option v-for="opt in categoryOptions" :key="opt.value" :value="opt.value">
                        {{ opt.label }}
                      </option>
                    </select>
                    <p class="mt-1 text-xs text-slate-500">选择此选择器所属的操作模块分类，方便筛选和维护</p>
                  </div>

                  <!-- purpose: locate / extract / page_detect -->
                  <div>
                    <label class="flex items-center gap-1.5 text-sm font-medium text-slate-300">
                      控件用途
                    </label>
                    <div class="mt-2 flex rounded-lg border border-white/10 overflow-hidden">
                      <button
                        type="button"
                        :class="form.purpose === 'locate' ? 'bg-indigo-500/20 text-indigo-300' : 'text-slate-500 hover:text-slate-300'"
                        class="flex-1 px-4 py-2 text-sm font-medium transition-colors"
                        @click="form.purpose = 'locate'"
                      >
                        定位（点击/操作控件）
                      </button>
                      <button
                        type="button"
                        :class="form.purpose === 'extract' ? 'bg-emerald-500/20 text-emerald-300' : 'text-slate-500 hover:text-slate-300'"
                        class="flex-1 px-4 py-2 text-sm font-medium transition-colors"
                        @click="form.purpose = 'extract'"
                      >
                        取值（读取控件内容）
                      </button>
                      <button
                        type="button"
                        :class="form.purpose === 'page_detect' ? 'bg-amber-500/20 text-amber-300' : 'text-slate-500 hover:text-slate-300'"
                        class="flex-1 px-4 py-2 text-sm font-medium transition-colors"
                        @click="form.purpose = 'page_detect'"
                      >
                        页面检测（多控件判定）
                      </button>
                    </div>
                    <!-- strategy_logic: only for page_detect -->
                    <div v-if="form.purpose === 'page_detect'" class="mt-3">
                      <label class="text-sm font-medium text-slate-300">策略间逻辑</label>
                      <div class="mt-2 flex gap-2">
                        <button
                          type="button"
                          :class="form.strategy_logic === 'and' ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' : 'text-slate-500 hover:text-slate-300 border-transparent'"
                          class="px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors"
                          @click="form.strategy_logic = 'and'"
                        >
                          AND（全部命中）
                        </button>
                        <button
                          type="button"
                          :class="form.strategy_logic === 'or' ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' : 'text-slate-500 hover:text-slate-300 border-transparent'"
                          class="px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors"
                          @click="form.strategy_logic = 'or'"
                        >
                          OR（任一命中）
                        </button>
                      </div>
                      <p class="mt-1 text-xs text-slate-500">AND：所有策略必须同时命中；OR：任意策略命中即判定页面存在</p>
                    </div>
                    <p class="mt-1 text-xs text-slate-500">定位：查找控件并点击/输入；取值：读取控件属性值；页面检测：多控件组合判定当前页面</p>
                  </div>

                  <!-- extract fields (shown when purpose=extract) -->
                  <div v-if="form.purpose === 'extract'" class="space-y-3">
                    <div>
                      <label class="text-sm font-medium text-slate-300">取值字段</label>
                      <select
                        v-model="form.extract_field"
                        class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
                      >
                        <option value="text">text（文本内容）</option>
                        <option value="desc">desc（描述内容）</option>
                        <option value="id">id（资源ID）</option>
                        <option value="className">className（类名）</option>
                      </select>
                      <p class="mt-1 text-xs text-slate-500">从找到的控件中读取此属性</p>
                    </div>

                    <div>
                      <label class="text-sm font-medium text-slate-300">清洗方式</label>
                      <div class="mt-2 flex gap-2">
                        <button
                          type="button"
                          :class="form.clean_mode === 'raw' ? 'bg-slate-500/20 text-slate-200 border-slate-500/30' : 'text-slate-500 hover:text-slate-300 border-transparent'"
                          class="px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors"
                          @click="form.clean_mode = 'raw'"
                        >
                          不处理（原始值）
                        </button>
                        <button
                          type="button"
                          :class="form.clean_mode === 'regex' ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30' : 'text-slate-500 hover:text-slate-300 border-transparent'"
                          class="px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors"
                          @click="form.clean_mode = 'regex'"
                        >
                          正则清洗
                        </button>
                        <button
                          type="button"
                          :class="form.clean_mode === 'ai' ? 'bg-purple-500/20 text-purple-300 border-purple-500/30' : 'text-slate-500 hover:text-slate-300 border-transparent'"
                          class="px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors"
                          @click="form.clean_mode = 'ai'"
                        >
                          AI 清洗
                        </button>
                      </div>
                    </div>

                    <!-- Regex mode -->
                    <div v-if="form.clean_mode === 'regex'" class="space-y-2">
                      <div>
                        <label class="text-xs text-slate-400 mb-1 block">AI 需求描述（用大白话告诉 AI 要提取什么，可粘贴原始数据）</label>
                        <div class="flex items-end gap-2">
                          <textarea
                            v-model="regexAiPrompt"
                            rows="3"
                            placeholder="描述要提取的内容，可粘贴多条原始数据示例"
                            class="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none"
                          />
                          <button
                            type="button"
                            class="btn-aurora rounded-lg px-3 py-2 text-xs font-medium whitespace-nowrap"
                            @click="generateRegexAI"
                            :disabled="generatingRegex"
                          >
                            <span class="relative z-10">{{ generatingRegex ? '生成中...' : 'AI 生成' }}</span>
                          </button>
                        </div>
                      </div>
                      <div>
                        <label class="text-xs text-slate-400 mb-1 block">正则表达式</label>
                        <input
                          v-model="form.clean_pattern"
                          type="text"
                          placeholder="AI 生成后自动填入，也可手动填写"
                          class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 font-mono focus:border-cyan-500/50 focus:outline-none"
                        />
                      </div>
                    </div>

                    <!-- AI mode -->
                    <div v-if="form.clean_mode === 'ai'" class="space-y-2">
                      <div>
                        <label class="text-xs text-slate-400 mb-1 block">AI 需求描述（用大白话告诉 AI 怎么清洗数据）</label>
                        <div class="flex items-end gap-2">
                          <textarea
                            v-model="cleanAiPrompt"
                            rows="3"
                            placeholder="例如：提取评论中的血糖数值，去掉单位和多余文字"
                            class="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none"
                          />
                          <button
                            type="button"
                            class="btn-aurora rounded-lg px-3 py-2 text-xs font-medium whitespace-nowrap"
                            @click="generateCleanPromptAI"
                            :disabled="generatingPrompt"
                          >
                            <span class="relative z-10">{{ generatingPrompt ? '生成中...' : 'AI 生成' }}</span>
                          </button>
                        </div>
                      </div>
                      <div>
                        <label class="text-xs text-slate-400 mb-1 block">清洗提示词</label>
                        <textarea
                          v-model="form.clean_prompt"
                          rows="3"
                          placeholder="AI 生成后自动填入，也可手动填写"
                          class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none"
                        />
                      </div>
                    </div>
                  </div>

                  <!-- strategies -->
                  <div>
                    <div class="flex items-center justify-between mb-2">
                      <label class="flex items-center gap-1.5 text-sm font-medium text-slate-300">
                        选择策略
                        <span class="text-red-400">*</span>
                      </label>
                      <!-- Mode toggle -->
                      <div class="flex items-center rounded-lg border border-white/10 overflow-hidden">
                        <button
                          type="button"
                          :class="editMode === 'form' ? 'bg-purple-500/20 text-purple-300' : 'text-slate-500 hover:text-slate-300'"
                          class="px-3 py-1 text-xs font-medium transition-colors"
                          @click="editMode = 'form'; syncStrategiesToList()"
                        >
                          可视化
                        </button>
                        <button
                          type="button"
                          :class="editMode === 'json' ? 'bg-purple-500/20 text-purple-300' : 'text-slate-500 hover:text-slate-300'"
                          class="px-3 py-1 text-xs font-medium transition-colors"
                          @click="editMode = 'json'; syncListToStrategies()"
                        >
                          JSON
                        </button>
                      </div>
                    </div>

                    <!-- Form mode: card builder -->
                    <div v-if="editMode === 'form'" class="space-y-3">
                      <div v-if="strategyList.length === 0" class="text-center py-6 text-slate-500 text-sm border border-dashed border-white/10 rounded-lg">
                        暂无策略，点击下方按钮添加
                      </div>
                      <StrategyCard
                        v-for="(s, i) in strategyList"
                        :key="i"
                        :strategy="s"
                        :index="i"
                        :total-count="strategyList.length"
                        :action-name="form.action_name"
                        :resolution-profile="form.resolution_profile"
                        :purpose="form.purpose"
                        @update="updateStrategy(i, $event)"
                        @delete="deleteStrategy(i)"
                        @move-up="moveStrategy(i, -1)"
                        @move-down="moveStrategy(i, 1)"
                      />
                      <button
                        type="button"
                        class="w-full py-2 border border-dashed border-white/20 rounded-lg text-sm text-slate-400 hover:text-purple-300 hover:border-purple-500/30 transition-colors"
                        @click="addStrategy"
                      >
                        + 添加策略
                      </button>
                    </div>

                    <!-- JSON mode: raw textarea -->
                    <div v-else>
                      <textarea
                        v-model="form.strategies"
                        rows="8"
                        class="block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 font-mono"
                        placeholder='[{"type":"text","value":"赞","priority":1}]'
                        @blur="syncStrategiesToList()"
                      />
                      <p class="mt-1 text-xs text-slate-500">
                        JSON 数组，每个策略含 type、value、priority 等字段
                      </p>
                    </div>
                  </div>

                  <!-- Buttons -->
                  <div class="flex justify-end gap-3 pt-2">
                    <button
                      type="button"
                      class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors"
                      @click="showFormDialog = false"
                    >
                      取消
                    </button>
                    <button
                      type="submit"
                      :disabled="saving"
                      class="btn-aurora rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <span class="relative z-10">{{ saving ? '保存中...' : '保存' }}</span>
                    </button>
                  </div>
                </form>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>

    <!-- Delete Confirmation Dialog -->
    <ConfirmDialog
      :open="showDeleteDialog"
      title="删除选择器"
      :message="`确定要删除选择器「${deletingSelector?.action_name || ''}」吗？此操作不可撤销。`"
      confirm-text="删除"
      :danger="true"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>
```

## src/views/SeriesDetailPage.vue

```html
<template>
  <div class="p-6">
    <button @click="$router.push('/series')" class="text-sky-400 hover:text-sky-300 mb-4 transition cursor-pointer">&larr; 返回系列列表</button>
    <div v-if="loading" class="text-slate-400 text-center py-12">加载中...</div>
    <div v-else-if="error" class="text-red-400 text-center py-12">{{ error }}</div>
    <template v-else-if="series">
      <div class="flex justify-between items-start mb-6">
        <div>
          <h1 class="text-2xl font-bold text-slate-100">{{ series.title }}</h1>
          <p class="text-slate-400 mt-1">{{ series.logline }}</p>
          <div class="flex gap-3 mt-2 text-sm text-slate-500">
            <span>{{ series.total_episodes }} 集</span><span>{{ series.genre }}</span>
            <span>{{ series.mode === 'fully_automatic' ? '全自动' : '逐步确认' }}</span>
          </div>
        </div>
        <div class="flex gap-2">
          <button v-if="!series.character_count && !series.scene_count && series.logline" @click="autoGenerate"
                  :disabled="autoGenerating" class="bg-purple-500 hover:bg-purple-400 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer"
                  title="根据故事概要，AI 自动生成角色和场景">
            {{ autoGenerating ? 'AI 生成中...' : 'AI 一键生成角色&场景' }}
          </button>
          <button @click="startPipelineRun" :disabled="pipelineStarting"
                  class="bg-sky-500 hover:bg-sky-400 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm transition cursor-pointer">
            {{ pipelineStarting ? '启动中...' : '▶ 启动流水线' }}
          </button>
        </div>
      </div>

      <div class="rounded-xl border border-gray-700/50 overflow-hidden" style="background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(12px);">
        <div class="px-5 py-3 border-b border-gray-700/50 font-medium text-slate-200">剧集列表</div>
        <div class="divide-y divide-gray-700/30 max-h-[600px] overflow-y-auto">
          <div v-for="ep in episodes" :key="ep.id" class="px-5 py-3 flex items-center gap-4 hover:bg-gray-800/40 transition cursor-pointer">
            <span class="text-slate-500 w-12 text-sm">E{{ String(ep.episode_number).padStart(2, '0') }}</span>
            <span class="flex-1 text-sm text-slate-200">{{ ep.title || '未命名' }}</span>
            <span class="text-xs text-slate-500 w-16 text-right">{{ ep.duration_seconds ? ep.duration_seconds + 's' : '-' }}</span>
            <span :class="epStatusClass(ep.status)" class="px-2 py-1 rounded text-xs">{{ ep.status }}</span>
          </div>
        </div>
      </div>

      <div v-if="runs.length" class="mt-8">
        <h2 class="text-lg font-semibold text-slate-100 mb-3">流水线运行历史</h2>
        <div class="space-y-2">
          <div v-for="r in runs" :key="r.id" @click="$router.push(`/pipeline/${r.id}`)"
               class="rounded-lg border border-gray-700/50 px-4 py-3 flex items-center gap-4 hover:shadow-lg hover:shadow-sky-900/10 transition cursor-pointer"
               style="background: rgba(15, 23, 42, 0.5);">
            <span class="text-xs text-slate-500 font-mono">{{ r.id.slice(0, 8) }}</span>
            <span :class="runStatusClass(r.status)" class="px-2 py-1 rounded text-xs">{{ r.status }}</span>
            <span class="text-xs text-slate-500">Layer {{ r.current_layer }}/6</span>
            <span class="text-xs text-slate-500 ml-auto">{{ r.created_at?.slice(0, 19) }}</span>
          </div>
        </div>
      </div>
    </template>

    <!-- AI 自动生成进度对话框 -->
    <div v-if="autoGenerating || autoGenResult" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50" @click.self="autoGenResult = null; load()">
      <div class="rounded-xl p-6 w-full max-w-lg shadow-2xl border border-gray-700/50 max-h-[85vh] overflow-y-auto" style="background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(20px);">
        <h2 class="text-lg font-semibold text-slate-100 mb-4">AI 自动生成</h2>
        <template v-if="autoGenerating">
          <div class="text-center py-8">
            <div class="animate-spin w-8 h-8 border-2 border-purple-400 border-t-transparent rounded-full mx-auto mb-3"></div>
            <p class="text-sm text-slate-400">{{ autoGenStep }}</p>
          </div>
        </template>
        <template v-else-if="autoGenResult">
          <p class="text-xs text-slate-500 mb-4">AI 已根据故事概要生成以下资产：</p>
          <div v-if="autoGenResult.characters?.length" class="mb-4">
            <h3 class="text-sm font-medium text-slate-200 mb-2">角色 ({{ autoGenResult.characters.length }})</h3>
            <div class="space-y-1">
              <div v-for="(c, i) in autoGenResult.characters" :key="'c'+i" class="text-xs text-slate-400 flex gap-2">
                <span class="text-slate-100">{{ c.name }}</span>
                <span class="text-slate-500">· {{ c.role_type }} · {{ c.gender === 'male' ? '男' : '女' }}</span>
              </div>
            </div>
          </div>
          <div v-if="autoGenResult.scenes?.length" class="mb-4">
            <h3 class="text-sm font-medium text-slate-200 mb-2">场景 ({{ autoGenResult.scenes.length }})</h3>
            <div class="space-y-1">
              <div v-for="(sc, i) in autoGenResult.scenes" :key="'s'+i" class="text-xs text-slate-400 flex gap-2">
                <span class="text-slate-100">{{ sc.name }}</span>
                <span class="text-slate-500">· {{ sc.scene_type }} · {{ sc.lighting }}</span>
              </div>
            </div>
          </div>
          <div class="flex justify-end mt-4">
            <button @click="autoGenResult = null; load()" class="px-4 py-2 bg-sky-500 hover:bg-sky-400 text-white rounded-lg transition cursor-pointer text-sm">完成</button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getSeries, autoGenerateAssets } from '../api/series.js'
import { startPipeline, listRuns } from '../api/pipeline.js'
const route = useRoute(); const series = ref(null); const episodes = ref([]); const runs = ref([]); const loading = ref(true); const pipelineStarting = ref(false); const error = ref('')
const autoGenerating = ref(false); const autoGenStep = ref(''); const autoGenResult = ref(null)
async function load() { loading.value = true; error.value = ''; try { const { data } = await getSeries(route.params.id); if (data.ok) { series.value = data.series; episodes.value = data.episodes || [] } else throw new Error('Series not found'); const r = await listRuns(route.params.id); runs.value = r.data.ok ? r.data.runs : [] } catch (e) { error.value = e.message || '加载失败' } finally { loading.value = false } }
async function startPipelineRun() { pipelineStarting.value = true; try { await startPipeline(route.params.id, null, series.value.mode) } catch (e) { error.value = e.message || '启动失败' } finally { pipelineStarting.value = false }; await load() }
async function autoGenerate() {
  autoGenerating.value = true; autoGenResult.value = null; error.value = ''
  try {
    autoGenStep.value = 'AI 正在分析故事，生成角色档案...'
    const { data } = await autoGenerateAssets(route.params.id)
    if (data.ok) {
      autoGenResult.value = data
      autoGenStep.value = ''
    } else throw new Error('生成失败')
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'AI 生成失败'
    autoGenerating.value = false
  } finally { autoGenerating.value = false }
}
function epStatusClass(s) { return { pending: 'bg-gray-800 text-slate-400', rendering: 'bg-yellow-900/40 text-yellow-400', done: 'bg-emerald-900/40 text-emerald-400', failed: 'bg-red-900/40 text-red-400' }[s] || 'bg-gray-800 text-slate-400' }
function runStatusClass(s) { return { running: 'bg-sky-900/40 text-sky-400', completed: 'bg-emerald-900/40 text-emerald-400', failed: 'bg-red-900/40 text-red-400', pending: 'bg-gray-800 text-slate-400' }[s] || 'bg-gray-800 text-slate-400' }
onMounted(load)
</script>
```

## src/views/SeriesListPage.vue

```html
<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-100">系列管理</h1>
        <p class="text-sm text-slate-400 mt-1">创建和管理连续短剧系列，配置剧集数和生成模式</p>
      </div>
      <button @click="showCreate = true" class="bg-sky-500 hover:bg-sky-400 text-white px-4 py-2 rounded-lg transition-colors duration-200 cursor-pointer" title="创建一个新的短剧系列">
        + 新建系列
      </button>
    </div>

    <!-- 新建 Dialog -->
    <div v-if="showCreate" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50" @click.self="showCreate = false">
      <div class="rounded-xl p-6 w-full max-w-lg shadow-2xl border border-gray-700/50" style="background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(20px);">
        <h2 class="text-lg font-semibold text-slate-100 mb-4">新建系列</h2>
        <div class="space-y-3">
          <div>
            <input v-model="form.title" placeholder="系列标题" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
            <p class="text-xs text-slate-500 mt-1 ml-1">输入系列名称，如"都市爱情故事"</p>
          </div>
          <div>
            <textarea v-model="form.logline" placeholder="一句话梗概 (logline)" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" rows="2" />
            <p class="text-xs text-slate-500 mt-1 ml-1">用一句话概括系列的核心剧情，AI 会根据梗概生成完整剧本</p>
          </div>
          <div class="flex gap-3">
            <div class="flex-1">
              <select v-model="form.genre" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500/50 cursor-pointer">
                <option v-for="g in genreOptions" :key="g.value" :value="g.value">{{ g.label }}</option>
              </select>
              <p class="text-xs text-slate-500 mt-1 ml-1">可在"系统字典"中管理类型选项</p>
            </div>
            <div>
              <select v-model="form.total_episodes" class="rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 cursor-pointer">
                <option v-for="n in [10,20,30,50]" :key="n" :value="n">{{ n }} 集</option>
              </select>
              <p class="text-xs text-slate-500 mt-1 ml-1">总剧集数</p>
            </div>
            <div>
              <input v-model.number="form.target_duration" type="number" placeholder="时长(s)" class="rounded-lg px-3 py-2 w-24 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50" />
              <p class="text-xs text-slate-500 mt-1 ml-1">每集目标时长</p>
            </div>
          </div>
          <div class="flex gap-3">
            <div class="flex-1">
              <select v-model="form.mode" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 cursor-pointer">
                <option value="step_by_step">逐步确认模式 — 每阶段需人工确认</option>
                <option value="fully_automatic">全自动一键生成 — 输入梗概直接出片</option>
              </select>
              <p class="text-xs text-slate-500 mt-1 ml-1">逐步确认：每层完成后需确认再继续 | 全自动：零人工干预</p>
            </div>
            <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer" title="开启后先生成第1集试点，确认无误后批量生成剩余剧集">
              <input type="checkbox" v-model="form.pilot_first" class="accent-sky-500" /> Pilot 试点
            </label>
          </div>
        </div>
        <div class="flex justify-end gap-3 mt-6">
          <button @click="showCreate = false" class="px-4 py-2 rounded-lg border border-gray-600 text-slate-300 hover:bg-gray-700 transition cursor-pointer">取消</button>
          <button @click="doCreate" class="px-4 py-2 bg-sky-500 hover:bg-sky-400 text-white rounded-lg transition disabled:opacity-50 cursor-pointer" :disabled="creating" :title="creating ? '正在创建...' : '创建系列并自动生成剧集占位'">
            {{ creating ? '创建中...' : '创建' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="text-slate-400 text-center py-12">加载中...</div>
    <div v-else-if="error" class="text-red-400 text-center py-12">{{ error }}</div>
    <div v-else-if="seriesList.length === 0" class="text-slate-500 text-center py-12">
      暂无系列，点击「新建系列」开始<br><span class="text-xs text-slate-600 mt-1">提示：创建系列后可在详情页关联角色和场景</span>
    </div>
    <div v-else class="grid gap-4">
      <div v-for="s in seriesList" :key="s.id"
           class="rounded-xl border border-gray-700/50 p-5 hover:shadow-lg hover:shadow-sky-900/10 transition-all duration-200 cursor-pointer"
           style="background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(12px);"
           @click="$router.push(`/series/${s.id}`)" :title="`点击查看 ${s.title} 的详情和剧集列表`">
        <div class="flex justify-between items-start">
          <div>
            <h3 class="text-lg font-semibold text-slate-100">{{ s.title }}</h3>
            <p class="text-sm text-slate-400 mt-1">{{ s.logline || '(无梗概)' }}</p>
            <div class="flex gap-3 mt-2 text-xs text-slate-500">
              <span>{{ s.total_episodes }} 集</span><span>{{ s.target_duration }}s/集</span>
              <span>{{ genreLabel(s.genre) }}</span>
              <span>{{ s.mode === 'fully_automatic' ? '全自动' : '逐步确认' }}</span>
            </div>
          </div>
          <span :class="statusClass(s.status)" class="px-2 py-1 rounded text-xs font-medium">{{ s.status }}</span>
        </div>
        <div class="mt-3 rounded-full h-1.5" style="background: rgba(255,255,255,0.06);">
          <div class="h-1.5 rounded-full transition-all duration-500" :class="progressColor(s.status)" :style="{ width: progressPercent(s) + '%' }"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { listSeries, createSeries } from '../api/series.js'
import { listItems } from '../api/referenceData.js'

const seriesList = ref([]); const loading = ref(true); const showCreate = ref(false); const creating = ref(false); const error = ref('')
const genreOptions = ref([])
const form = reactive({ title: '', logline: '', genre: 'drama', total_episodes: 30, target_duration: 90, mode: 'step_by_step', pilot_first: true })

async function loadGenres() { try { const { data } = await listItems('series_genre'); if (data.ok) { genreOptions.value = data.items; if (data.items.length && !genreOptions.value.find(g => g.value === form.genre)) form.genre = data.items[0].value } } catch (e) { /* fallback to hardcoded */ } }
async function loadSeries() { loading.value = true; error.value = ''; try { const { data } = await listSeries(); seriesList.value = data.ok ? data.series : [] } catch (e) { error.value = e.message || '加载失败' } finally { loading.value = false } }
async function doCreate() { creating.value = true; try { await createSeries({ ...form }); showCreate.value = false; await loadSeries() } catch (e) { error.value = e.message || '创建失败' } finally { creating.value = false } }

function statusClass(s) { return { draft: 'bg-gray-800 text-slate-400', rendering: 'bg-yellow-900/40 text-yellow-400', done: 'bg-emerald-900/40 text-emerald-400', failed: 'bg-red-900/40 text-red-400' }[s] || 'bg-gray-800 text-slate-400' }
function progressColor(s) { return s === 'done' ? 'bg-emerald-500' : s === 'rendering' ? 'bg-sky-500 animate-pulse' : 'bg-slate-600' }
function progressPercent(s) { if (s === 'done') return 100; if (s === 'draft') return 0; return s === 'rendering' ? 50 : 10 }
function genreLabel(v) { const g = genreOptions.value.find(x => x.value === v); return g ? g.label : v }

onMounted(async () => { await loadGenres(); await loadSeries() })
</script>
```

## src/views/SettingsPage.vue

```html
<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getSettings, updateSettings } from '../api/settings.js'
import { testConnection } from '../api/pixelle.js'
import { useToastStore } from '../stores/toast.js'
import LoadingSpinner from '../components/LoadingSpinner.vue'

const toast = useToastStore()
const loading = ref(false)
const saving = ref(false)

const form = reactive({
  ai_api_key: '',
  ai_base_url: 'https://api.deepseek.com',
  ai_model: 'deepseek-chat',
  ai_thinking: 'max',
  pixelle_video_url: 'http://localhost:8500',
  pixelle_video_timeout: 600,
})

const pixelleConnTest = ref(null)
const pixelleTesting = ref(false)

async function fetchSettings() {
  loading.value = true
  try {
    const res = await getSettings()
    const data = res.data
    // 服务端返回 "****" 表示该字段已配置但不暴露，前端显示空输入框
    form.ai_api_key = (data.ai_api_key && data.ai_api_key !== '****') ? data.ai_api_key : ''
    form.ai_base_url = data.ai_base_url || 'https://api.deepseek.com'
    form.ai_model = data.ai_model || 'deepseek-chat'
    form.ai_thinking = data.ai_thinking || 'max'
    form.pixelle_video_url = data.pixelle_video_url || 'http://localhost:8500'
    form.pixelle_video_timeout = parseInt(data.pixelle_video_timeout) || 600
  } catch {
    toast.error('加载设置失败')
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  saving.value = true
  try {
    const payload = {}
    // 仅提交用户真实输入的值（空=不更新，后端保留现有值）
    if (form.ai_api_key) payload.ai_api_key = form.ai_api_key
    if (form.ai_base_url) payload.ai_base_url = form.ai_base_url
    if (form.ai_model) payload.ai_model = form.ai_model
    if (form.ai_thinking) payload.ai_thinking = form.ai_thinking
    if (form.pixelle_video_url) payload.pixelle_video_url = form.pixelle_video_url
    if (form.pixelle_video_timeout) payload.pixelle_video_timeout = String(form.pixelle_video_timeout)
    await updateSettings(payload)
    toast.success('设置已保存')
  } catch {
    toast.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleTestConnection() {
  pixelleTesting.value = true
  pixelleConnTest.value = null
  try {
    const resp = await testConnection()
    pixelleConnTest.value = resp.data
  } catch {
    pixelleConnTest.value = { ok: false, error: '请求失败' }
  } finally {
    pixelleTesting.value = false
  }
}

onMounted(fetchSettings)
</script>

<template>
  <div class="max-w-2xl mx-auto">
    <h1 class="text-2xl font-bold gradient-text mb-6">AI 配置</h1>

    <LoadingSpinner v-if="loading" />

    <template v-else>
      <!-- AI Configuration -->
      <div class="glass-card p-6 mb-6">
        <div class="flex items-center gap-3 mb-6">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-purple-500 flex items-center justify-center">
            <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <div>
            <h2 class="text-lg font-semibold text-white">AI 配置</h2>
            <p class="text-sm text-slate-400">配置 AI 内容分析和生成功能（DeepSeek / OpenAI 兼容格式）</p>
          </div>
        </div>

        <div class="space-y-5">
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">API Key</label>
            <input
              v-model="form.ai_api_key"
              type="password"
              placeholder="sk-..."
              class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/30 transition-all"
            />
            <p class="mt-1 text-xs text-slate-500">留空则使用服务端环境变量 AI_API_KEY</p>
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">Base URL</label>
            <input
              v-model="form.ai_base_url"
              type="text"
              placeholder="https://api.deepseek.com"
              class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/30 transition-all"
            />
            <p class="mt-1 text-xs text-slate-500">API 基础地址，不含 /v1/chat/completions 后缀</p>
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">模型</label>
            <input
              v-model="form.ai_model"
              type="text"
              placeholder="deepseek-chat"
              class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/30 transition-all"
            />
            <p class="mt-1 text-xs text-slate-500">例如 deepseek-chat、gpt-4o-mini 等</p>
          </div>

          <!-- Thinking mode -->
          <div class="pt-2 border-t border-white/5">
            <label class="block text-sm font-medium text-slate-300 mb-3">思考等级</label>
            <select
              v-model="form.ai_thinking"
              class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/30 transition-all"
            >
              <option value="disabled">关闭思考</option>
              <option value="low">Low — 快速响应 (1024 tokens)</option>
              <option value="medium">Medium — 简短思考 (2048 tokens)</option>
              <option value="high">High — 深入思考 (4096 tokens)</option>
              <option value="xhigh">X-High — 深度思考 (8192 tokens)</option>
              <option value="max">Max — 极限思考 (16384 tokens)</option>
            </select>
            <p class="mt-1 text-xs text-slate-500">控制 AI 思考深度，等级越高回复质量越好但耗时更长</p>
          </div>
        </div>
      </div>

      <!-- Pixelle-Video Configuration -->
      <div class="glass-card p-6 mb-6">
        <div class="flex items-center gap-3 mb-6">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
            <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </div>
          <div>
            <h2 class="text-lg font-semibold text-white">Pixelle-Video 配置</h2>
            <p class="text-sm text-slate-400">AI 视频生成服务（LLM 脚本 → ComfyUI 配图 → TTS 配音 → FFmpeg 合成）</p>
          </div>
        </div>

        <div class="space-y-5">
          <!-- Connection -->
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">Pixelle-Video 服务地址</label>
            <div class="flex gap-2">
              <input
                v-model="form.pixelle_video_url"
                type="text"
                placeholder="http://localhost:8501"
                class="flex-1 px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/30 transition-all"
              />
              <button
                @click="handleTestConnection"
                :disabled="pixelleTesting"
                class="px-4 py-3 rounded-xl bg-purple-500/20 text-purple-300 text-sm hover:bg-purple-500/30 disabled:opacity-50 transition-colors whitespace-nowrap"
              >
                {{ pixelleTesting ? '测试中...' : '测试连接' }}
              </button>
            </div>
            <div v-if="pixelleConnTest" class="mt-2 text-sm flex items-center gap-2">
              <template v-if="pixelleConnTest.ok">
                <svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                </svg>
                <span class="text-emerald-400">连接成功 (v{{ pixelleConnTest.version }})</span>
              </template>
              <template v-else>
                <svg class="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
                <span class="text-red-400">连接失败: {{ pixelleConnTest.error }}</span>
              </template>
            </div>
            <p class="mt-1 text-xs text-slate-500">Pixelle-Video 的 FastAPI 服务地址（默认端口 8501）</p>
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">超时时间 (秒)</label>
            <input
              v-model.number="form.pixelle_video_timeout"
              type="number"
              min="60"
              max="3600"
              class="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/30 transition-all"
            />
            <p class="mt-1 text-xs text-slate-500">代理请求 Pixelle-Video 的最大等待时间</p>
          </div>
        </div>

        <div class="mt-6 flex justify-end">
          <button
            @click="handleSave"
            :disabled="saving"
            class="btn-aurora px-6 py-2.5 rounded-xl font-medium text-white disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span v-if="saving">保存中...</span>
            <span v-else>保存设置</span>
          </button>
        </div>
      </div>

      <!-- Info card -->
      <div class="glass-card p-5">
        <div class="flex items-start gap-3">
          <svg class="w-5 h-5 text-cyan-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div class="text-sm text-slate-400 leading-relaxed">
            <p class="mb-2">AI 配置用于以下功能：</p>
            <ul class="list-disc list-inside space-y-1 text-slate-500">
              <li>养号过程中的内容语义分析（判断是否与大健康相关）</li>
              <li>评论 / 私信内容 AI 生成</li>
              <li>Pixelle-Video 视频生成（LLM 脚本 → ComfyUI 配图 → TTS 配音 → 合成）</li>
            </ul>
            <p class="mt-3">配置保存后，设备端下次轮询任务时自动生效。</p>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
```

## src/views/StatsPage.vue

```html
<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { Chart, registerables } from 'chart.js'
import { getDailyStats } from '../api/stats.js'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import TipIcon from '../components/TipIcon.vue'
import { useToastStore } from '../stores/toast.js'

Chart.register(...registerables)

function formatDate(d) {
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

const today = formatDate(new Date())
const selectedDate = ref(today)
const loading = ref(false)
const statsData = ref(null)
const toast = useToastStore()
const barCanvas = ref(null)
const donutCanvas = ref(null)
let barChart = null
let donutChart = null

const METRICS = [
  { key: 'likes', label: '点赞', color: '#f472b6', glow: 'rgba(244,114,182,0.4)' },
  { key: 'comments', label: '评论', color: '#34d399', glow: 'rgba(52,211,153,0.4)' },
  { key: 'follows', label: '关注', color: '#fbbf24', glow: 'rgba(251,191,36,0.4)' },
  { key: 'dms', label: '私信', color: '#f87171', glow: 'rgba(248,113,113,0.4)' },
  { key: 'replies', label: '回复', color: '#a78bfa', glow: 'rgba(167,139,250,0.4)' },
]

const totals = computed(() => {
  const accounts = statsData.value?.accounts
  if (!accounts || accounts.length === 0) return null
  const result = {}
  for (const m of METRICS) {
    result[m.key] = { used: 0, limit: 0 }
  }
  for (const acc of accounts) {
    const limits = acc.daily_limits || {}
    for (const m of METRICS) {
      result[m.key].used += acc[m.key] || 0
      result[m.key].limit += limits[m.key] || 0
    }
  }
  return result
})

function pct(used, limit) {
  if (!limit || limit === 0) return 0
  return Math.min(Math.round((used / limit) * 100), 100)
}

function pctColor(pct) {
  if (pct >= 90) return '#f87171'
  if (pct >= 70) return '#fbbf24'
  if (pct >= 40) return '#34d399'
  return '#60a5fa'
}

function ringDash(val, r) {
  const circ = 2 * Math.PI * r
  const filled = (val / 100) * circ
  return `${filled} ${circ}`
}

function buildCharts() {
  const accounts = statsData.value?.accounts
  if (!accounts || accounts.length === 0) return

  nextTick(() => {
    // Donut chart — overall task completion
    if (donutCanvas.value) {
      if (donutChart) donutChart.destroy()
      const totalUsed = METRICS.reduce((s, m) => s + (totals.value?.[m.key]?.used || 0), 0)
      const totalLimit = METRICS.reduce((s, m) => s + (totals.value?.[m.key]?.limit || 0), 0)
      const remaining = Math.max(totalLimit - totalUsed, 0)
      donutChart = new Chart(donutCanvas.value, {
        type: 'doughnut',
        data: {
          labels: ['已完成', '剩余配额'],
          datasets: [{
            data: [totalUsed, remaining],
            backgroundColor: [
              'rgba(167,139,250,0.8)',
              'rgba(255,255,255,0.06)',
            ],
            borderColor: [
                'rgba(167,139,250,0.3)',
                'rgba(255,255,255,0.05)',
            ],
            borderWidth: 2,
            borderRadius: 4,
          }]
        },
        options: {
          cutout: '72%',
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: 'rgba(15,23,42,0.95)',
              titleColor: '#e2e8f0',
              bodyColor: '#94a3b8',
              borderColor: 'rgba(255,255,255,0.1)',
              borderWidth: 1,
            }
          }
        }
      })
    }

    // Bar chart — per account
    if (barCanvas.value) {
      if (barChart) barChart.destroy()
      const labels = accounts.map(a => (a.nickname || a.account_id).substring(0, 8))
      barChart = new Chart(barCanvas.value, {
        type: 'bar',
        data: {
          labels,
          datasets: METRICS.map(m => ({
            label: m.label,
            data: accounts.map(a => a[m.key] || 0),
            backgroundColor: m.color,
            borderRadius: 6,
            borderSkipped: false,
          }))
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'top',
              labels: { color: '#cbd5e1', usePointStyle: true, padding: 20, font: { size: 13 } }
            },
            tooltip: {
              backgroundColor: 'rgba(15,23,42,0.95)',
              titleColor: '#f1f5f9',
              bodyColor: '#cbd5e1',
              borderColor: 'rgba(255,255,255,0.15)',
              borderWidth: 1,
            }
          },
          scales: {
            x: {
              stacked: true,
              grid: { color: 'rgba(255,255,255,0.06)' },
              ticks: { color: '#94a3b8', font: { size: 12 } }
            },
            y: {
              stacked: true,
              beginAtZero: true,
              grid: { color: 'rgba(255,255,255,0.06)' },
              ticks: { color: '#94a3b8', font: { size: 12 } }
            }
          }
        }
      })
    }
  })
}

watch(() => statsData.value, () => {
  if (statsData.value?.accounts?.length) buildCharts()
})

async function fetchStats() {
  loading.value = true
  try {
    const res = await getDailyStats(selectedDate.value)
    statsData.value = res.data
  } catch (err) {
    toast.error('加载统计数据失败')
    statsData.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => fetchStats())

onUnmounted(() => {
  if (barChart) barChart.destroy()
  if (donutChart) donutChart.destroy()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold text-white flex items-center gap-2">
        数据统计<TipIcon text="所有账号配额使用情况与任务完成度" />
      </h1>
      <input
        v-model="selectedDate"
        type="date"
        class="border border-white/10 bg-white/5 rounded-lg px-3 py-2 text-sm text-slate-200"
        @change="fetchStats"
      />
    </div>

    <LoadingSpinner v-if="loading" />

    <div
      v-else-if="!statsData || !statsData.accounts || statsData.accounts.length === 0"
      class="flex items-center justify-center py-20"
    >
      <p class="text-slate-300 text-lg">{{ selectedDate }} 暂无数据</p>
    </div>

    <template v-else>
      <!-- ========== 顶部 KPI 卡片 ========== -->
      <div class="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div
          v-for="m in METRICS"
          :key="m.key"
          class="relative overflow-hidden rounded-xl p-5 cursor-default group"
          style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1)"
        >
          <div class="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500"
            :style="{ background: `radial-gradient(circle at 50% 0%, ${m.glow}, transparent 70%)` }" />
          <div class="relative z-10">
            <p class="text-sm font-semibold mb-1.5" :style="{ color: m.color }">{{ m.label }}</p>
            <p class="text-3xl font-bold text-white tabular-nums">{{ totals[m.key].used }}</p>
            <div class="flex items-center gap-2 mt-2">
              <div class="flex-1 h-1.5 rounded-full" style="background: rgba(255,255,255,0.1)">
                <div class="h-full rounded-full transition-all duration-700"
                  :style="{ width: pct(totals[m.key].used, totals[m.key].limit) + '%', background: m.color }" />
              </div>
              <span class="text-sm font-semibold tabular-nums" :style="{ color: m.color }">
                {{ pct(totals[m.key].used, totals[m.key].limit) }}%
              </span>
            </div>
            <p class="text-sm text-slate-400 mt-1.5">/ {{ totals[m.key].limit }}</p>
          </div>
        </div>
      </div>

      <!-- ========== 环形图 + 环形图总览 ========== -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- 环形进度 -->
        <div class="rounded-xl p-6" style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1)">
          <h2 class="text-base font-semibold text-slate-200 uppercase tracking-wider mb-6">配额完成率</h2>
          <div class="flex flex-wrap justify-center gap-6">
            <div v-for="m in METRICS" :key="m.key" class="flex flex-col items-center gap-2.5">
              <div class="relative w-24 h-24">
                <svg class="w-full h-full -rotate-90" viewBox="0 0 100 100">
                  <defs>
                    <filter :id="'glow-' + m.key">
                      <feGaussianBlur stdDeviation="2" result="blur" />
                      <feComposite in="SourceGraphic" in2="blur" operator="over" />
                    </filter>
                  </defs>
                  <circle cx="50" cy="50" r="38" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="7" />
                  <circle
                    cx="50" cy="50" r="38" fill="none"
                    :stroke="m.color"
                    stroke-width="7" stroke-linecap="round"
                    :stroke-dasharray="ringDash(pct(totals[m.key].used, totals[m.key].limit), 38)"
                    :filter="'url(#glow-' + m.key + ')'"
                    class="ring-animate"
                  />
                </svg>
                <div class="absolute inset-0 flex flex-col items-center justify-center">
                  <span class="text-base font-bold text-white">{{ pct(totals[m.key].used, totals[m.key].limit) }}%</span>
                </div>
              </div>
              <span class="text-sm font-medium" :style="{ color: m.color }">{{ m.label }}</span>
            </div>
          </div>
        </div>

        <!-- 环形总结 -->
        <div class="rounded-xl p-6" style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1)">
          <h2 class="text-base font-semibold text-slate-200 uppercase tracking-wider mb-4">任务完成总进度</h2>
          <div class="relative" style="height: 240px">
            <canvas ref="donutCanvas"></canvas>
            <div class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <span class="text-4xl font-bold text-white">
                {{ (() => { const t = totals; if (!t) return 0; const u = METRICS.reduce((s,m) => s + (t[m.key]?.used||0), 0); const l = METRICS.reduce((s,m) => s + (t[m.key]?.limit||0), 0); return pct(u,l); })() }}%
              </span>
              <span class="text-sm text-slate-400 mt-1.5">完成率</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ========== 柱状图 ========== -->
      <div class="rounded-xl p-6" style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1)">
        <h2 class="text-base font-semibold text-slate-200 uppercase tracking-wider mb-4">各账号操作分布</h2>
        <div style="height: 340px">
          <canvas ref="barCanvas"></canvas>
        </div>
      </div>

      <!-- ========== 各账号详情 ========== -->
      <div class="rounded-xl p-6" style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1)">
        <h2 class="text-base font-semibold text-slate-200 uppercase tracking-wider mb-5">
          账号详情 ({{ statsData.accounts.length }})
        </h2>
        <div class="space-y-4">
          <div
            v-for="acc in statsData.accounts"
            :key="acc.account_id"
            class="p-5 rounded-xl border border-white/10 hover:border-white/20 transition-all duration-300"
            style="background: rgba(255,255,255,0.03)"
          >
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold text-white"
                  style="background: linear-gradient(135deg, #667eea, #764ba2); box-shadow: 0 0 16px rgba(102,126,234,0.35)">
                  {{ (acc.nickname || acc.account_id).charAt(0) }}
                </div>
                <span class="text-base font-medium text-slate-100">{{ acc.nickname || acc.account_id }}</span>
              </div>
            </div>
            <div class="space-y-2.5">
              <div v-for="m in METRICS" :key="m.key" class="flex items-center gap-3">
                <span class="text-sm w-12 text-right flex-shrink-0 font-medium" :style="{ color: m.color }">{{ m.label }}</span>
                <div class="flex-1 h-2.5 rounded-full overflow-hidden" style="background: rgba(255,255,255,0.08)">
                  <div class="h-full rounded-full transition-all duration-700"
                    :style="{
                      width: pct(acc[m.key], (acc.daily_limits || {})[m.key]) + '%',
                      background: `linear-gradient(90deg, ${m.color}, ${m.color}66)`,
                      boxShadow: pct(acc[m.key], (acc.daily_limits || {})[m.key]) > 0 ? `0 0 10px ${m.glow}` : 'none'
                    }"
                  />
                </div>
                <span class="text-sm w-16 text-right tabular-nums flex-shrink-0 font-semibold"
                  :style="{ color: pctColor(pct(acc[m.key], (acc.daily_limits || {})[m.key])) }">
                  {{ acc[m.key] || 0 }}/{{ (acc.daily_limits || {})[m.key] || 0 }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.ring-animate {
  transition: stroke-dasharray 1.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}
</style>
```

## src/views/TasksPage.vue

```html
<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import DataTable from '../components/DataTable.vue'
import StatusBadge from '../components/StatusBadge.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import ChannelDetail from '../components/ChannelDetail.vue'
import TaskCreateDialog from '../components/business/TaskCreateDialog.vue'
import KeywordSearchDialog from '../components/business/KeywordSearchDialog.vue'
import ChannelList from '../components/business/ChannelList.vue'
import { listTasks, cancelTask, deleteTask, batchDeleteTasks } from '../api/tasks.js'
import { listChannels } from '../api/channels.js'
import { listAccounts } from '../api/accounts.js'
import { listGroups } from '../api/accountGroups.js'
import { listDevices } from '../api/devices.js'
import { listTemplates } from '../api/content.js'
import { listTemplates as listPromptTemplates } from '../api/promptTemplates.js'
import { formatDate } from '../utils/format.js'
import { useToastStore } from '../stores/toast.js'
import { useWebSocket } from '../composables/useWebSocket.js'
import { TASK_TYPE_LABEL_MAP, TASK_TYPE_OPTIONS, STATUS_FILTER_OPTIONS, TASK_TABLE_COLUMNS } from '../constants/tasks.js'
import { CHANNEL_TASK_TYPE_LABEL, CHANNEL_STATUS_LABEL, CHANNEL_STATUS_CLASS } from '../constants/channels.js'

const toast = useToastStore()

// --- Task state ---
const tasks = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const statusFilter = ref('')
const searchQuery = ref('')
const typeFilter = ref('')
const sortBy = ref('created_at')
const sortOrder = ref('desc')
const selectedTaskIds = ref([])
const batchDeleting = ref(false)
const pageError = ref(null)
const taskProgress = reactive({})

// --- Ref data ---
const accounts = ref([])
const groups = ref([])
const devices = ref([])
const templates = ref([])
const promptTemplates = ref([])

// --- Channel state ---
const channels = ref([])
const channelsLoading = ref(false)
const detailChannel = ref(null)
const channelsExpanded = ref(false)

// --- Dialogs ---
const showCreateDialog = ref(false)
const showKeywordDialog = ref(false)
const showCancelDialog = ref(false)
const cancellingTask = ref(null)
const cancelling = ref(false)

// --- WebSocket ---
function wsUrl() {
  const token = localStorage.getItem('token') || ''
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/api/devices/ws/pair-events?token=${encodeURIComponent(token)}`
}
useWebSocket(wsUrl, {
  onMessage(msg) {
    if (msg.event === 'task_updated' || msg.event === 'tasks_changed') fetchTasks(true)
    else if (msg.event === 'task_progress') taskProgress[msg.task_id] = { step: msg.step, detail: msg.detail, progress: msg.progress }
  },
})

// --- Tasks ---
async function fetchTasks(silent) {
  if (!silent) loading.value = true
  try {
    const skip = (page.value - 1) * pageSize
    const params = { skip, limit: pageSize, sort_by: sortBy.value, sort_order: sortOrder.value }
    if (statusFilter.value) params.status = statusFilter.value
    if (typeFilter.value) params.type = typeFilter.value
    if (searchQuery.value) params.search = searchQuery.value
    const res = await listTasks(params)
    tasks.value = res.data.tasks || []
    total.value = res.data.total || 0
    if (!silent) selectedTaskIds.value = []
    const currentIds = {}
    for (const t of tasks.value) currentIds[t.id] = true
    for (const key in taskProgress) { if (!currentIds[key]) delete taskProgress[key] }
  } catch (e) {
    if (!silent) toast.error('加载任务列表失败')
    tasks.value = []; total.value = 0
  } finally { loading.value = false }
}

async function handleDeleteTask(row) {
  try { await deleteTask(row.id); toast.success('已删除'); fetchTasks() } catch { toast.error('删除失败') }
}
async function handleBatchDelete() {
  if (!selectedTaskIds.value.length) { toast.error('请先选择任务'); return }
  batchDeleting.value = true
  try { const res = await batchDeleteTasks(selectedTaskIds.value); toast.success(`已删除 ${res.data.deleted} 个任务`); fetchTasks() }
  catch { toast.error('批量删除失败') }
  finally { batchDeleting.value = false }
}
function handleSort(col) {
  if (sortBy.value === col) sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  else { sortBy.value = col; sortOrder.value = 'desc' }
  fetchTasks()
}
function toggleSelectAll() {
  if (selectedTaskIds.value.length === tasks.value.length) selectedTaskIds.value = []
  else selectedTaskIds.value = tasks.value.map(t => t.id)
}
function handlePageChange(p) { page.value = p; fetchTasks() }
function openCancelDialog(task) { cancellingTask.value = task; showCancelDialog.value = true }
async function handleCancel() {
  if (!cancellingTask.value) return
  cancelling.value = true
  try { await cancelTask(cancellingTask.value.id); showCancelDialog.value = false; cancellingTask.value = null; fetchTasks() }
  catch (e) { pageError.value = e.response?.data?.detail || '取消失败，请重试' }
  finally { cancelling.value = false }
}

// --- Channels ---
async function fetchChannels() {
  channelsLoading.value = true
  try { const resp = await listChannels(); channels.value = resp.data.channels || [] }
  catch {}
  finally { channelsLoading.value = false }
}
const activeChannelCount = () => channels.value.filter(c => c.status === 'active').length
const pausedChannelCount = () => channels.value.filter(c => c.status === 'paused').length

// --- Ref data ---
async function loadRefData() {
  try {
    const [acctRes, grpRes, devRes, tplRes, ptRes] = await Promise.all([
      listAccounts({ limit: 100 }), listGroups({ limit: 100 }), listDevices({ limit: 100 }),
      listTemplates({ limit: 100 }), listPromptTemplates(false),
    ])
    accounts.value = acctRes.data.accounts || []
    groups.value = grpRes.data.groups || grpRes.data || []
    devices.value = devRes.data.devices || []
    templates.value = tplRes.data.templates || []
    promptTemplates.value = (ptRes.data.templates || []).filter(t => t.enabled)
  } catch {}
}

function onCreated() {
  showCreateDialog.value = false; showKeywordDialog.value = false
  page.value = 1; fetchTasks(); fetchChannels()
}
function onChannelRefresh() { fetchChannels(); fetchTasks(true) }

watch(statusFilter, () => { page.value = 1; fetchTasks() })
onMounted(() => { fetchTasks(); fetchChannels(); loadRefData() })
</script>

<template>
  <div>
    <!-- Page error -->
    <div v-if="pageError" class="mb-4 card border-red-500/30 text-red-400 px-4 py-3 flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-400 hover:text-red-300 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- ====== 通道区 ====== -->
    <div class="mb-5">
      <div
        class="flex items-center justify-between px-4 py-2.5 rounded-xl cursor-pointer select-none transition-all duration-200"
        :class="channelsExpanded ? 'card' : 'card hover:border-accent'"
        style="border-color: var(--border-default);"
        @click="channelsExpanded = !channelsExpanded"
      >
        <div class="flex items-center gap-3 min-w-0 flex-1">
          <div class="flex items-center gap-2 shrink-0">
            <svg class="w-4 h-4" :class="channelsExpanded ? 'text-sky-400' : 'text-slate-500'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            <span class="text-sm font-semibold text-slate-300">通道</span>
            <span class="text-xs font-mono text-slate-500">({{ channels.length }})</span>
          </div>

          <!-- 摘要：每个通道 pill + hover 详情浮层 -->
          <div v-if="!channelsExpanded && channels.length > 0" class="hidden md:flex items-center gap-2 min-w-0 flex-1 overflow-visible">
            <template v-for="ch in channels.slice(0, 4)" :key="ch.id">
              <div class="relative group shrink-0">
                <!-- Pill -->
                <div class="flex items-center gap-2 px-2.5 py-1 rounded-lg cursor-default transition-colors duration-150" style="background: var(--bg-surface); border: 1px solid var(--border-subtle);"
                  :class="{
                    'hover:border-emerald-500/30': ch.status === 'active',
                    'hover:border-amber-500/30': ch.status === 'paused',
                    'hover:border-blue-500/30': ch.status === 'completed',
                  }">
                  <span class="w-1.5 h-1.5 rounded-full shrink-0" :class="{
                    'bg-emerald-400': ch.status === 'active',
                    'bg-amber-400': ch.status === 'paused',
                    'bg-blue-400': ch.status === 'completed',
                    'bg-slate-500': ch.status === 'cancelled',
                  }"></span>
                  <span class="text-xs font-medium text-slate-300 truncate max-w-[70px]">{{ ch.group_name || '-' }}</span>
                  <span class="text-[10px] font-mono tabular-nums" style="color: var(--accent-400);">{{ ch.completed }}/{{ ch.total }}</span>
                </div>

                <!-- Hover 详情浮层 -->
                <div class="absolute top-full mt-2 left-0 z-50 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-150 pointer-events-none" style="min-width: 220px;">
                  <div class="card p-4 space-y-2.5" style="box-shadow: var(--shadow-xl); border-color: var(--border-strong);">
                    <!-- 头部 -->
                    <div class="flex items-center justify-between">
                      <span class="text-sm font-semibold text-white truncate max-w-[120px]">{{ ch.group_name || '未命名' }}</span>
                      <span :class="CHANNEL_STATUS_CLASS[ch.status] || 'bg-slate-600/50 text-slate-400'" class="px-2 py-0.5 text-[10px] rounded-full font-medium">
                        {{ CHANNEL_STATUS_LABEL[ch.status] || ch.status }}
                      </span>
                    </div>
                    <!-- 分隔线 -->
                    <div style="border-top: 1px solid var(--border-subtle);"></div>
                    <!-- 任务信息 -->
                    <div class="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <span class="text-slate-500">任务类型</span>
                        <p class="text-slate-200 font-medium">{{ CHANNEL_TASK_TYPE_LABEL[ch.task_type] || ch.task_type }}</p>
                      </div>
                      <div>
                        <span class="text-slate-500">账号模式</span>
                        <p class="text-slate-200 font-medium">{{ ch.account_mode === 'single_account' ? '单账号' : '轮转' }}</p>
                      </div>
                      <div>
                        <span class="text-slate-500">已分发</span>
                        <p class="text-slate-200 font-mono font-semibold tabular-nums">{{ ch.assigned || 0 }}</p>
                      </div>
                      <div>
                        <span class="text-slate-500">待处理</span>
                        <p class="text-amber-300 font-mono font-semibold tabular-nums">{{ ch.pending || 0 }}</p>
                      </div>
                    </div>
                    <!-- 进度条 -->
                    <div>
                      <div class="flex justify-between text-[10px] mb-1">
                        <span class="text-slate-500">完成进度</span>
                        <span class="font-mono tabular-nums" style="color: var(--accent-400);">{{ ch.total ? Math.round(ch.completed / ch.total * 100) : 0 }}%</span>
                      </div>
                      <div class="w-full h-1.5 rounded-full bg-white/5">
                        <div class="h-full rounded-full transition-all duration-500" :style="{ width: ch.total ? (ch.completed / ch.total * 100) + '%' : '0%', background: ch.status === 'active' ? 'linear-gradient(90deg, #34d399, #22d3ee)' : 'linear-gradient(90deg, #fbbf24, #f59e0b)' }"></div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
            <span v-if="channels.length > 4" class="text-xs text-slate-600 shrink-0">+{{ channels.length - 4 }}</span>
          </div>
        </div>

        <div class="flex items-center gap-3 shrink-0">
          <span v-if="activeChannelCount()" class="hidden sm:flex items-center gap-1 text-xs"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span><span class="text-emerald-400 font-semibold">{{ activeChannelCount() }}</span></span>
          <span v-if="pausedChannelCount()" class="hidden sm:flex items-center gap-1 text-xs"><span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span><span class="text-amber-400 font-semibold">{{ pausedChannelCount() }}</span></span>
          <svg class="w-4 h-4 text-slate-500 transition-transform duration-200" :class="channelsExpanded ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      <!-- 展开的通道卡片网格 -->
      <div v-if="channelsExpanded" class="mt-3 animate-in">
        <ChannelList
          :channels="channels"
          :loading="channelsLoading"
          @refresh="onChannelRefresh"
          @detail="detailChannel = $event"
        />
      </div>
    </div>

    <!-- ====== 任务区 ====== -->
    <div class="flex items-center justify-between mb-5">
      <h1 class="text-xl font-bold text-white">任务列表</h1>
      <div class="flex items-center gap-2 flex-wrap">
        <input v-model="searchQuery" @keyup.enter="page=1;fetchTasks()" placeholder="搜索..." class="w-36 rounded-lg border px-3 py-2 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);" />
        <select v-model="typeFilter" @change="page=1;fetchTasks()" class="rounded-lg border px-3 py-2 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);">
          <option value="">全部类型</option>
          <option v-for="opt in TASK_TYPE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
        <select v-model="statusFilter" class="rounded-lg border px-3 py-2 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);">
          <option v-for="opt in STATUS_FILTER_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
        <button v-if="selectedTaskIds.length" class="btn-danger text-xs" @click="handleBatchDelete" :disabled="batchDeleting">
          {{ batchDeleting ? '...' : `删除(${selectedTaskIds.length})` }}
        </button>
        <button class="btn-ghost text-xs" style="border-color: var(--border-accent); color: var(--accent-400);" @click="showKeywordDialog = true">
          <svg class="-ml-0.5 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
          AI 关键词搜索
        </button>
        <button class="btn-primary text-xs" @click="showCreateDialog = true">
          <svg class="-ml-0.5 w-4 h-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"/></svg>
          创建任务
        </button>
      </div>
    </div>

    <!-- Task Table -->
    <DataTable :columns="TASK_TABLE_COLUMNS" :data="tasks" :loading="loading" :total="total" :page="page" :page-size="pageSize" @page-change="handlePageChange">
      <template #header-select>
        <input type="checkbox" :checked="tasks.length > 0 && selectedTaskIds.length === tasks.length" @change="toggleSelectAll" class="rounded" />
      </template>
      <template #cell-select="{ row }">
        <input type="checkbox" :value="row.id" v-model="selectedTaskIds" class="rounded" />
      </template>
      <template #cell-type="{ value }">{{ TASK_TYPE_LABEL_MAP[value] || value }}</template>
      <template #cell-keyword="{ row }">
        <span class="text-sm" style="color: var(--text-secondary);">{{ row.params?.keyword || row.params?.keywords?.[0] || '-' }}</span>
      </template>
      <template #cell-account_id="{ value }">
        <span style="color: var(--text-secondary);">{{ accounts.find(a => a.id === value)?.nickname || value }}</span>
      </template>
      <template #cell-device_id="{ value }">
        <span v-if="value" style="color: var(--text-secondary);">{{ devices.find(d => d.id === value)?.name || value }}</span>
        <span v-else class="text-slate-500">自动分配</span>
      </template>
      <template #cell-progress="{ row }">
        <!-- 已完成任务：显示结果统计 -->
        <div v-if="row.status === 'completed' && row.result?.result" class="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs min-w-[180px]">
          <span class="font-mono tabular-nums" style="color: var(--accent-400);">{{ row.result.result.success_count || 0 }}</span>
          <span class="text-slate-500">回复</span>
          <span v-if="row.result.result.skipped" class="font-mono tabular-nums text-slate-400">{{ row.result.result.skipped }}</span>
          <span v-if="row.result.result.skipped" class="text-slate-600">跳过</span>
          <span v-if="row.result.result.follow_count" class="font-mono tabular-nums text-amber-400">{{ row.result.result.follow_count }}</span>
          <span v-if="row.result.result.follow_count" class="text-slate-600">关注</span>
          <span v-if="row.result.result.dm_count" class="font-mono tabular-nums text-emerald-400">{{ row.result.result.dm_count }}</span>
          <span v-if="row.result.result.dm_count" class="text-slate-600">私信</span>
        </div>
        <!-- 运行中任务：显示进度 -->
        <div v-else-if="taskProgress[row.id]" class="flex flex-col gap-0.5 min-w-[140px]">
          <span class="text-xs" style="color: var(--accent-400);">{{ taskProgress[row.id].step }}</span>
          <span class="text-[11px] text-slate-500">{{ taskProgress[row.id].detail }}</span>
        </div>
        <!-- 失败任务：显示失败原因 -->
        <div v-else-if="row.status === 'failed' && row.result" class="flex flex-col gap-0.5 min-w-[140px]">
          <span class="text-xs text-red-400">{{ row.result.error || '执行失败' }}</span>
          <span v-if="row.result.result" class="text-[11px] text-slate-500">
            {{ row.result.result.success_count || 0 }} 回复 · {{ row.result.result.skipped || 0 }} 跳过
          </span>
        </div>
        <span v-else class="text-xs text-slate-500">-</span>
      </template>
      <template #cell-status="{ value }"><StatusBadge :status="value" /></template>
      <template #cell-created_at="{ value }">{{ formatDate(value) }}</template>
      <template #cell-actions="{ row }">
        <div class="flex justify-end gap-2">
          <button v-if="row.status === 'pending' || row.status === 'running'" class="btn-danger text-xs" @click="openCancelDialog(row)">取消</button>
          <button v-if="row.status === 'failed' || row.status === 'cancelled'" class="px-3 py-1 text-xs font-medium text-orange-400 hover:text-orange-300 hover:bg-orange-400/10 rounded-lg transition-colors" @click="handleDeleteTask(row)">删除</button>
        </div>
      </template>
    </DataTable>

    <!-- Dialogs -->
    <TaskCreateDialog :open="showCreateDialog" :accounts="accounts" :groups="groups" :devices="devices" :templates="templates" :prompt-templates="promptTemplates" @close="showCreateDialog = false" @created="onCreated" />
    <KeywordSearchDialog :open="showKeywordDialog" :accounts="accounts" :groups="groups" :devices="devices" :templates="templates" :prompt-templates="promptTemplates" @close="showKeywordDialog = false" @created="onCreated" />
    <ConfirmDialog :open="showCancelDialog" title="取消任务" message="确定要取消该任务吗？" confirm-text="取消任务" :danger="true" @confirm="handleCancel" @cancel="showCancelDialog = false" />
    <ChannelDetail v-if="detailChannel" :channel="detailChannel" @close="detailChannel = null" @refresh="onChannelRefresh" />
  </div>
</template>
```

## src/views/UsersPage.vue

```html
<script setup>
import { ref, onMounted } from 'vue'
import { listUsers, registerUser } from '../api/auth.js'
import { useToastStore } from '../stores/toast.js'

const toast = useToastStore()
const users = ref([])
const loading = ref(false)
const showCreate = ref(false)
const newUser = ref({ username: '', password: '', role: 'operator', nickname: '' })
const creating = ref(false)

async function fetchUsers() {
  loading.value = true
  try { const resp = await listUsers(); users.value = resp.data.users || [] }
  catch { toast.error('加载用户列表失败') }
  finally { loading.value = false }
}

async function handleCreate() {
  if (!newUser.value.username || !newUser.value.password) { toast.error('用户名和密码必填'); return }
  creating.value = true
  try {
    await registerUser(newUser.value)
    toast.success('用户创建成功')
    showCreate.value = false
    newUser.value = { username: '', password: '', role: 'operator', nickname: '' }
    fetchUsers()
  } catch (e) { toast.error(e.response?.data?.detail || '创建失败') }
  finally { creating.value = false }
}

onMounted(fetchUsers)
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-5">
      <h1 class="text-xl font-bold text-white">用户管理</h1>
      <button @click="showCreate = true" class="btn-primary text-sm">新增用户</button>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-16">
      <svg class="animate-spin h-7 w-7 text-cyan-400/60" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
    </div>

    <div v-else class="card overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr>
            <th class="px-4 py-3 text-left">用户名</th>
            <th class="px-4 py-3 text-left">昵称</th>
            <th class="px-4 py-3 text-left">角色</th>
            <th class="px-4 py-3 text-left">状态</th>
            <th class="px-4 py-3 text-right">创建时间</th>
          </tr>
        </thead>
        <tbody class="divide-y" style="border-color: var(--border-subtle);">
          <tr v-for="u in users" :key="u.id" class="hover:bg-white/5 transition-colors">
            <td class="px-4 py-3 text-slate-200 font-medium">{{ u.username }}</td>
            <td class="px-4 py-3 text-slate-400">{{ u.nickname || '-' }}</td>
            <td class="px-4 py-3">
              <span class="text-xs px-2 py-0.5 rounded font-medium" :class="u.role === 'admin' ? 'bg-amber-500/15 text-amber-400' : 'bg-sky-500/10 text-sky-400'">{{ u.role === 'admin' ? '管理员' : '操作员' }}</span>
            </td>
            <td class="px-4 py-3">
              <span class="text-xs px-2 py-0.5 rounded" :class="u.status === 'active' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-500/10 text-slate-500'">{{ u.status === 'active' ? '启用' : '禁用' }}</span>
            </td>
            <td class="px-4 py-3 text-right text-xs text-slate-500">{{ u.created_at?.slice(0, 10) || '-' }}</td>
          </tr>
          <tr v-if="users.length === 0">
            <td colspan="5" class="px-4 py-12 text-center text-slate-500">暂无用户</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="showCreate" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" @click.self="showCreate = false">
      <div class="card p-5 w-full max-w-sm">
        <h2 class="text-lg font-bold text-white mb-4">新增用户</h2>
        <div class="space-y-3">
          <input v-model="newUser.username" placeholder="用户名" class="w-full rounded-lg border px-3 py-2 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);" />
          <input v-model="newUser.password" type="password" placeholder="密码" class="w-full rounded-lg border px-3 py-2 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);" />
          <input v-model="newUser.nickname" placeholder="昵称（可选）" class="w-full rounded-lg border px-3 py-2 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);" />
          <select v-model="newUser.role" class="w-full rounded-lg border px-3 py-2 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);">
            <option value="operator">操作员</option>
            <option value="admin">管理员</option>
          </select>
        </div>
        <div class="flex justify-end gap-3 mt-4">
          <button @click="showCreate = false" class="btn-ghost text-sm">取消</button>
          <button @click="handleCreate" :disabled="creating" class="btn-primary text-sm">{{ creating ? '创建中...' : '创建' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>
```

## src/views/VideosPage.vue

```html
<script setup>
import { ref, computed, onMounted } from 'vue'
import { listVideos, deleteVideo, getVideoDownloadUrl } from '../api/videos.js'
import { useToastStore } from '../stores/toast.js'
import { useWebSocket } from '../composables/useWebSocket.js'
import { formatDate } from '../utils/format.js'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'

const toast = useToastStore()

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 12

const searchKeyword = ref('')
const filterStatus = ref('')

const previewVideo = ref(null)
const showPreview = ref(false)

const deleteTarget = ref(null)
const showDeleteConfirm = ref(false)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

function wsUrl() {
  const token = localStorage.getItem('token') || ''
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/api/devices/ws/pair-events?token=${encodeURIComponent(token)}`
}
const { connect: wsConnect } = useWebSocket(wsUrl, {
  onMessage(msg) {
    if (msg.event === 'task_updated' || msg.event === 'tasks_changed') {
      fetchData()
    }
  },
})

async function fetchData() {
  loading.value = true
  try {
    const params = { skip: (page.value - 1) * pageSize, limit: pageSize }
    if (searchKeyword.value) params.keyword = searchKeyword.value
    if (filterStatus.value) params.status = filterStatus.value
    const resp = await listVideos(params)
    items.value = resp.data.items || []
    total.value = resp.data.total || 0
  } catch {
    toast.error('加载视频列表失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  fetchData()
}

function goPage(p) {
  page.value = p
  fetchData()
}

function openPreview(video) {
  previewVideo.value = video
  showPreview.value = true
}

function closePreview() {
  showPreview.value = false
  previewVideo.value = null
}

function confirmDelete(video) {
  deleteTarget.value = video
  showDeleteConfirm.value = true
}

async function handleDelete() {
  if (!deleteTarget.value) return
  try {
    await deleteVideo(deleteTarget.value.id)
    toast.success('视频已删除')
    showDeleteConfirm.value = false
    deleteTarget.value = null
    fetchData()
  } catch {
    toast.error('删除失败')
  }
}

function statusVariant(status) {
  const map = { completed: 'success', failed: 'danger', processing: 'warning', pending: 'info' }
  return map[status] || 'info'
}

function statusLabel(status) {
  const map = { completed: '已完成', failed: '失败', processing: '生成中', pending: '待处理' }
  return map[status] || status
}

function formatDuration(seconds) {
  if (!seconds) return '-'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

onMounted(() => {
  wsConnect()
  fetchData()
})
</script>

<template>
  <div class="max-w-6xl mx-auto">
    <h1 class="text-2xl font-bold gradient-text mb-6">视频管理</h1>

    <!-- Filters -->
    <div class="glass-card p-4 mb-6">
      <div class="flex flex-wrap items-end gap-3">
        <div class="flex-1 min-w-[180px]">
          <label class="block text-xs text-slate-400 mb-1">关键词搜索</label>
          <input
            v-model="searchKeyword"
            type="text"
            placeholder="搜索视频关键词..."
            class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
            @keyup.enter="handleSearch"
          />
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">状态</label>
          <select
            v-model="filterStatus"
            class="px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-cyan-500/50"
            @change="handleSearch"
          >
            <option value="">全部</option>
            <option value="pending">待处理</option>
            <option value="processing">生成中</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
          </select>
        </div>
        <button
          @click="handleSearch"
          class="px-4 py-2 rounded-lg bg-cyan-500/20 text-cyan-300 text-sm hover:bg-cyan-500/30 transition-colors"
        >
          搜索
        </button>
      </div>
    </div>

    <LoadingSpinner v-if="loading" />

    <template v-else>
      <!-- Empty state -->
      <div v-if="items.length === 0" class="glass-card p-12 text-center">
        <svg class="w-16 h-16 mx-auto text-slate-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
        <p class="text-slate-400 text-lg mb-2">暂无视频</p>
        <p class="text-slate-500 text-sm">在任务中心创建「AI 生成视频」任务，生成完成后会出现在这里</p>
      </div>

      <!-- Video grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-6">
        <div
          v-for="video in items"
          :key="video.id"
          class="glass-card overflow-hidden group cursor-pointer hover:border-cyan-500/30 transition-all"
        >
          <!-- Thumbnail area -->
          <div
            class="relative bg-gradient-to-br from-slate-800 to-slate-900 h-40 flex items-center justify-center"
            @click="openPreview(video)"
          >
            <svg v-if="video.status === 'processing'" class="w-12 h-12 text-cyan-400 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="10" stroke-width="3" class="opacity-25" />
              <path stroke-linecap="round" stroke-width="3" d="M12 2a10 10 0 019.95 9" />
            </svg>
            <svg v-else-if="video.status === 'failed'" class="w-12 h-12 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <svg v-else class="w-12 h-12 text-slate-600 group-hover:text-white transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span
              class="absolute top-2 right-2 text-xs px-2 py-0.5 rounded-full"
              :class="{
                'bg-emerald-500/20 text-emerald-300': video.status === 'completed',
                'bg-red-500/20 text-red-300': video.status === 'failed',
                'bg-cyan-500/20 text-cyan-300': video.status === 'processing',
                'bg-slate-500/20 text-slate-400': video.status === 'pending',
              }"
            >{{ statusLabel(video.status) }}</span>
          </div>

          <!-- Info -->
          <div class="p-3 space-y-1.5">
            <p class="text-sm font-medium text-white truncate" :title="video.title || video.keyword">
              {{ video.title || video.keyword }}
            </p>
            <p class="text-xs text-slate-400">{{ video.keyword }}</p>
            <div class="flex items-center justify-between text-xs text-slate-500">
              <span v-if="video.duration">{{ formatDuration(video.duration) }}</span>
              <span v-else>-</span>
              <span>{{ formatDate(video.created_at) }}</span>
            </div>
            <!-- Actions -->
            <div class="flex items-center gap-2 pt-1 border-t border-white/5">
              <button
                v-if="video.status === 'completed'"
                @click="openPreview(video)"
                class="flex-1 text-xs px-2 py-1 rounded bg-cyan-500/15 text-cyan-300 hover:bg-cyan-500/25 transition-colors"
              >
                预览
              </button>
              <a
                v-if="video.video_path"
                :href="getVideoDownloadUrl(video.id)"
                class="flex-1 text-xs px-2 py-1 rounded bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 transition-colors text-center"
              >
                下载
              </a>
              <button
                @click="confirmDelete(video)"
                class="flex-1 text-xs px-2 py-1 rounded bg-red-500/15 text-red-300 hover:bg-red-500/25 transition-colors"
              >
                删除
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Pagination -->
      <div v-if="totalPages > 1" class="flex items-center justify-center gap-2">
        <button
          :disabled="page <= 1"
          @click="goPage(page - 1)"
          class="px-3 py-1.5 rounded-lg text-sm border border-white/10 text-slate-300 hover:border-white/20 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          上一页
        </button>
        <span class="text-sm text-slate-400">{{ page }} / {{ totalPages }}</span>
        <button
          :disabled="page >= totalPages"
          @click="goPage(page + 1)"
          class="px-3 py-1.5 rounded-lg text-sm border border-white/10 text-slate-300 hover:border-white/20 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          下一页
        </button>
      </div>
    </template>

    <!-- Preview dialog -->
    <Teleport to="body">
      <div
        v-if="showPreview"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
        @click.self="closePreview"
      >
        <div class="max-w-3xl w-full mx-4">
          <div class="glass-card p-4">
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-white font-medium truncate">{{ previewVideo?.title || previewVideo?.keyword }}</h3>
              <button @click="closePreview" class="text-slate-400 hover:text-white transition-colors">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <video
              v-if="previewVideo?.video_path"
              :src="getVideoDownloadUrl(previewVideo.id)"
              controls
              autoplay
              class="w-full rounded-lg max-h-[70vh]"
            />
            <p v-else class="text-slate-400 text-center py-12">视频文件不存在</p>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Delete confirm -->
    <ConfirmDialog
      :open="showDeleteConfirm"
      title="删除视频"
      :message="`确定要删除「${deleteTarget?.title || deleteTarget?.keyword || ''}」吗？视频文件也将被删除，此操作不可撤销。`"
      @confirm="handleDelete"
      @cancel="showDeleteConfirm = false; deleteTarget = null"
    />
  </div>
</template>
```

## src/views/VideoStudio.vue

```html
<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import SystemConfigPanel from '../components/video-studio/SystemConfigPanel.vue'
import ContentPanel from '../components/video-studio/ContentPanel.vue'
import VoiceVisualPanel from '../components/video-studio/VoiceVisualPanel.vue'
import GeneratePanel from '../components/video-studio/GeneratePanel.vue'
import CustomMediaPanel from '../components/video-studio/CustomMediaPanel.vue'
import DigitalHumanPanel from '../components/video-studio/DigitalHumanPanel.vue'
import ImageToVideoPanel from '../components/video-studio/ImageToVideoPanel.vue'
import ActionTransferPanel from '../components/video-studio/ActionTransferPanel.vue'
import SeedancePanel from '../components/video-studio/SeedancePanel.vue'
import {
  generateVideoAsync, getTask, listTemplates, getOpenAPISpec,
  listMediaWorkflows, listTTSWorkflows, listBGMs, getVideoFileUrl,
} from '../api/pixelle-client.js'
import { getPixelleConfig, updatePixelleConfig } from '../api/pixelle.js'
import { listCharacters } from '../api/characters.js'
import { listScenes } from '../api/scenes.js'
import PipelineLayerConfig from '../components/video-studio/PipelineLayerConfig.vue'
import { useToastStore } from '../stores/toast.js'

const toast = useToastStore()

// ==================== Pipeline tabs ====================

const pipelines = [
  { key: 'quick_create', label: '快速创作', icon: 'M13 10V3L4 14h7v7l9-11h-7z', desc: 'AI 自动生成脚本→配图→配音→合成' },
  { key: 'custom_media', label: '自定义素材', icon: 'M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z', desc: '上传图片/视频/音频素材，AI 生成视频' },
  { key: 'digital_human', label: '数字人口播', icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z', desc: '数字人形象+配音，生成口播视频' },
  { key: 'image_to_video', label: '图生视频', icon: 'M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z', desc: '上传图片，AI 生成动态视频' },
  { key: 'action_transfer', label: '动作迁移', icon: 'M8 5v14l11-7z', desc: '上传视频，提取动作并迁移' },
  { key: 'seedance', label: 'Seedance 2.0', icon: 'M13 10V3L4 14h7v7l9-11h-7z', desc: '字节跳动 Seedance 2.0 原生视频生成 (1080P 声画同步)' },
]
const activePipeline = ref('quick_create')

// ==================== Layer Model Config ====================

const layerModels = ref({
  scriptLLM: 'qwen-max',
  imageModel: 'flux',
  videoModel: 'auto',
  ttsModel: 'edge-tts',
  auditModel: 'auto',
})

// ==================== Character & Scene Selection ====================

const characterList = ref([])
const sceneList = ref([])
const selectedCharacterIds = ref([])
const selectedSceneIds = ref([])

async function loadAssets() {
  try {
    const [cRes, sRes] = await Promise.all([
      listCharacters().catch(() => ({ data: { ok: false, characters: [] } })),
      listScenes().catch(() => ({ data: { ok: false, scenes: [] } })),
    ])
    characterList.value = cRes.data.ok ? cRes.data.characters : []
    sceneList.value = sRes.data.ok ? sRes.data.scenes : []
  } catch {}
}

function toggleCharacter(id) {
  const idx = selectedCharacterIds.value.indexOf(id)
  if (idx >= 0) selectedCharacterIds.value.splice(idx, 1)
  else selectedCharacterIds.value.push(id)
}

function toggleScene(id) {
  const idx = selectedSceneIds.value.indexOf(id)
  if (idx >= 0) selectedSceneIds.value.splice(idx, 1)
  else selectedSceneIds.value.push(id)
}

// ==================== System Config ====================

const systemConfig = ref({
  llmApiKey: '',
  llmBaseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  llmModel: 'qwen-max',
  comfyuiUrl: 'http://127.0.0.1:8188',
  comfyuiApiKey: '',
  runninghubApiKey: '',
  runninghubConcurrent: 1,
  defaultTtsWorkflow: 'selfhost/tts_edge.json',
  defaultImageWorkflow: 'runninghub/image_flux.json',
  defaultVideoWorkflow: 'runninghub/video_wan2.1_fusionx.json',
  templateFontSize: '28px',
  templateTextColor: '#ffffff',
  templateBgColor: '#000000',
})

async function loadSystemConfig() {
  try {
    const resp = await getPixelleConfig()
    const data = resp.data
    const cfg = systemConfig.value
    if (data.llm) {
      cfg.llmBaseUrl = data.llm.base_url || cfg.llmBaseUrl
      cfg.llmModel = data.llm.model || cfg.llmModel
    }
    if (data.comfyui) {
      cfg.comfyuiUrl = data.comfyui.comfyui_url || cfg.comfyuiUrl
      cfg.runninghubConcurrent = data.comfyui.runninghub_concurrent_limit || cfg.runninghubConcurrent
    }
    if (data.template) {
      const tpl = data.template.custom_params || {}
      if (tpl.font_size) cfg.templateFontSize = tpl.font_size
      if (tpl.text_color) cfg.templateTextColor = tpl.text_color
      if (tpl.background_color) cfg.templateBgColor = tpl.background_color
    }
  } catch { /* config.yaml may not exist yet */ }
}

function buildPixelleConfigUpdates() {
  const cfg = systemConfig.value
  const updates = {
    llm: { base_url: cfg.llmBaseUrl, model: cfg.llmModel },
    comfyui: {
      comfyui_url: cfg.comfyuiUrl,
      runninghub_concurrent_limit: cfg.runninghubConcurrent,
    },
    template: {
      custom_params: {
        font_size: cfg.templateFontSize,
        text_color: cfg.templateTextColor,
        background_color: cfg.templateBgColor,
      },
    },
  }
  if (cfg.llmApiKey) updates.llm.api_key = cfg.llmApiKey
  if (cfg.comfyuiApiKey) updates.comfyui.comfyui_api_key = cfg.comfyuiApiKey
  if (cfg.runninghubApiKey) updates.comfyui.runninghub_api_key = cfg.runninghubApiKey
  return updates
}

let saveTimer = null
watch(systemConfig, () => {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    try { await updatePixelleConfig(buildPixelleConfigUpdates()) } catch {}
  }, 1000)
}, { deep: true })

// ==================== Content Form ====================

const contentForm = ref({
  text: '',
  title: '',
  mode: 'generate',
  splitMode: 'paragraph',
  nScenes: 5,
  bgmMode: 'none',
  bgmId: 'calm_01',
  bgmVolume: 0.2,
  customBgmFile: null,
})

// ==================== Voice & Visual Form ====================

const voiceVisualForm = ref({
  ttsEngine: 'edge-tts',
  ttsVoice: 'zh-CN-XiaoxiaoNeural',
  ttsSpeed: 1.0,
  ttsWorkflow: 'selfhost/tts_edge.json',
  refAudioFile: null,
  mediaWorkflow: '',
  promptPrefix: '',
  frameTemplate: '',
})

// ==================== Templates / Workflows / BGM ====================

const templates = ref([])
const mediaWorkflows = ref([])
const ttsWorkflows = ref([])
const bgmList = ref([])
const resourcesLoading = ref(false)

async function fetchResources() {
  resourcesLoading.value = true
  try {
    const [tRes, mRes, ttsRes, bgmRes] = await Promise.all([
      listTemplates().catch(() => ({ data: { templates: [] } })),
      listMediaWorkflows().catch(() => ({ data: { workflows: [] } })),
      listTTSWorkflows().catch(() => ({ data: { workflows: [] } })),
      listBGMs().catch(() => ({ data: { bgm_files: [] } })),
    ])
    templates.value = Array.isArray(tRes.data) ? tRes.data : (tRes.data.templates || [])
    mediaWorkflows.value = mRes.data?.workflows || []
    ttsWorkflows.value = ttsRes.data?.workflows || []
    bgmList.value = bgmRes.data?.bgm_files || []
  } catch {
    templates.value = [
      { key: '1080x1920/image_default.html', name: 'image_default.html', size: '1080x1920' },
      { key: '1920x1080/image_default.html', name: 'image_default.html', size: '1920x1080' },
      { key: '1080x1080/image_default.html', name: 'image_default.html', size: '1080x1080' },
    ]
  } finally {
    resourcesLoading.value = false
  }
}

// ==================== Generation State ====================

const generating = ref(false)
const progress = ref({ percent: 0, message: '', status: '' })
const result = ref(null)
const videoUrl = ref('')
const history = ref([])

let pollTimer = null

// ==================== Actions ====================

async function handleTestConnection() {
  try {
    const resp = await getOpenAPISpec()
    toast.success(`Pixelle-Video 连接成功 (v${resp.data?.info?.version || '?'})`)
  } catch {
    toast.error('Pixelle-Video 连接失败，请检查服务是否启动')
  }
}

function handleBgmUpload(event) {
  contentForm.value.customBgmFile = event.target.files?.[0] || null
}

function handleRefAudioUpload(event) {
  voiceVisualForm.value.refAudioFile = event.target.files?.[0] || null
}

async function handleGenerate() {
  const cf = contentForm.value
  if (!cf.text.trim()) { toast.error('请输入视频主题或脚本'); return }

  generating.value = true
  result.value = null
  videoUrl.value = ''
  progress.value = { percent: 0, message: '正在连接 Pixelle-Video...', status: '' }

  try {
    const vf = voiceVisualForm.value
    const payload = {
      text: cf.text,
      mode: cf.mode,
      n_scenes: cf.nScenes,
    }
    if (cf.title) payload.title = cf.title
    if (cf.mode === 'fixed') payload.split_mode = cf.splitMode
    if (vf.frameTemplate) payload.frame_template = vf.frameTemplate

    if (vf.ttsEngine === 'edge-tts') {
      payload.tts_voice = vf.ttsVoice
      if (vf.ttsSpeed !== 1.0) payload.tts_speed = vf.ttsSpeed
    } else if (vf.ttsEngine === 'custom') {
      payload.tts_workflow = vf.ttsWorkflow
    }
    if (vf.ttsWorkflow && vf.ttsEngine !== 'custom') payload.tts_workflow = vf.ttsWorkflow
    if (vf.mediaWorkflow) payload.media_workflow = vf.mediaWorkflow
    if (vf.promptPrefix) payload.prompt_prefix = vf.promptPrefix

    if (cf.bgmMode === 'builtin') {
      payload.bgm_path = cf.bgmId  // full path e.g. bgm/default.mp3
    } else if (cf.bgmMode === 'custom' && cf.customBgmFile) {
      payload.bgm_path = cf.customBgmFile.name
    }
    if (cf.bgmMode !== 'none') payload.bgm_volume = cf.bgmVolume

    // Character & scene references
    if (selectedCharacterIds.value.length) payload.character_ids = selectedCharacterIds.value
    if (selectedSceneIds.value.length) payload.scene_ids = selectedSceneIds.value

    // Per-layer model overrides
    const lm = layerModels.value
    if (lm.scriptLLM && lm.scriptLLM !== 'qwen-max') payload.script_llm = lm.scriptLLM
    if (lm.imageModel && lm.imageModel !== 'auto') payload.image_model = lm.imageModel
    if (lm.videoModel && lm.videoModel !== 'auto') payload.video_model = lm.videoModel
    if (lm.ttsModel && lm.ttsModel !== 'edge-tts') payload.tts_model = lm.ttsModel
    if (lm.auditModel && lm.auditModel !== 'auto') payload.audit_model = lm.auditModel

    const sc = systemConfig.value
    if (sc.templateFontSize || sc.templateTextColor || sc.templateBgColor) {
      payload.template_params = {}
      if (sc.templateFontSize) payload.template_params.font_size = sc.templateFontSize
      if (sc.templateTextColor) payload.template_params.text_color = sc.templateTextColor
      if (sc.templateBgColor) payload.template_params.background_color = sc.templateBgColor
    }

    progress.value.message = '正在提交任务...'
    const resp = await generateVideoAsync(payload)
    const taskId = resp.data?.task_id
    if (!taskId) throw new Error('未获取到 Pixelle 任务 ID')

    progress.value.message = 'AI 正在生成脚本...'
    progress.value.percent = 5
    await pollTask(taskId, payload.video_model)

  } catch (e) {
    const errMsg = e.response?.data?.detail || e.message || '视频生成失败'
    result.value = { success: false, error: errMsg }
    history.value.unshift({ text: cf.text, success: false })
    toast.error(errMsg)
  } finally {
    generating.value = false
    clearPoll()
  }
}

function pollTask(taskId, videoModel = 'auto') {
  const maxAttempts = videoModel === 'seedance' ? 180 : videoModel === 'kling' ? 120 : 120
  return new Promise((resolve, reject) => {
    let attempts = 0
    pollTimer = setInterval(async () => {
      attempts++
      if (attempts > maxAttempts) { reject(new Error(`视频生成超时 (${(maxAttempts * 5 / 60).toFixed(0)}min)`)); return }
      try {
        const resp = await getTask(taskId)
        const data = resp.data
        if (data.status === 'completed') {
          clearPoll()
          videoUrl.value = getVideoFileUrl(data.video_path)
          result.value = { success: true, taskId, duration: data.duration, fileSize: data.file_size, frames: data.frames, videoPath: data.video_path }
          history.value.unshift({ text: contentForm.value.text, success: true })
          toast.success('视频生成完成！')
          resolve()
        } else if (data.status === 'failed') {
          reject(new Error(data.error || 'Pixelle-Video 返回失败'))
        } else {
          const stageMap = {
            narrating: '分镜脚本生成中...',
            generating_images: '画面渲染中...',
            generating_video: '视频画面生成中...',
            tts: 'TTS 配音合成中...',
            composing: 'FFmpeg 最终合成中...',
          }
          const pct = data.progress != null ? Math.min(95, data.progress) : Math.min(95, progress.value.percent + 0.3)
          const stage = data.stage || ''
          const stageMsg = stageMap[stage] || `处理中 (${data.status})`

          // Show frame progress: "分镜 3/5 — 步骤 2/4: 生成插图"
          const frame = data.current_frame
          const total = data.total_frames
          if (frame && total) {
            progress.value.message = `分镜 ${frame}/${total} — ${stageMsg}`
          } else {
            progress.value.message = stageMsg
          }
          progress.value.percent = pct
        }
      } catch {
        if (attempts % 6 === 0) progress.value.message = `网络波动，重试中... (${attempts}/120)`
      }
    }, 5000)
  })
}

function clearPoll() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

function handleClearResult() {
  result.value = null
  videoUrl.value = ''
  progress.value = { percent: 0, message: '', status: '' }
}

// ==================== Lifecycle ====================

// Two-way sync: layerModels ↔ voiceVisualForm
watch(() => layerModels.value.ttsModel, (val) => {
  if (voiceVisualForm.value.ttsEngine !== val) {
    voiceVisualForm.value = { ...voiceVisualForm.value, ttsEngine: val }
  }
})
watch(() => voiceVisualForm.value.ttsEngine, (val) => {
  if (layerModels.value.ttsModel !== val) {
    layerModels.value = { ...layerModels.value, ttsModel: val }
  }
})
watch(() => layerModels.value.imageModel, (val) => {
  const wf = val === 'flux' ? 'runninghub/image_flux.json' : val === 'sdxl' ? 'comfyui/sdxl.json' : ''
  if (voiceVisualForm.value.mediaWorkflow !== wf) {
    voiceVisualForm.value = { ...voiceVisualForm.value, mediaWorkflow: wf }
  }
})

onMounted(() => { loadSystemConfig(); fetchResources(); loadAssets() })
onUnmounted(() => { clearPoll() })
</script>

<template>
  <div class="max-w-[1440px] mx-auto px-4">
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-2xl font-bold gradient-text">AI 视频工坊</h1>
      <span class="text-xs text-slate-500">Pixelle-Video</span>
    </div>

    <!-- Pipeline tabs -->
    <div class="flex flex-wrap gap-1.5 mb-4">
      <button v-for="p in pipelines" :key="p.key" @click="activePipeline = p.key"
        class="flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all"
        :class="activePipeline === p.key ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/30' : 'bg-white/5 text-slate-400 border border-white/10 hover:border-white/20'"
        :title="p.desc">
        <svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="p.icon"/></svg>
        {{ p.label }}
      </button>
    </div>

    <SystemConfigPanel
      v-model="systemConfig"
      @test-connection="handleTestConnection"
    />

    <!-- Standard pipeline (quick_create) -->
    <div v-if="activePipeline === 'quick_create'" class="space-y-4" style="min-height: calc(100vh - 330px);">
      <!-- Per-layer model config -->
      <PipelineLayerConfig v-model="layerModels" />
      <!-- Character & scene selection chips -->
      <div v-if="characterList.length || sceneList.length" class="flex gap-4 flex-wrap">
        <div v-if="characterList.length" class="flex-1 min-w-0">
          <label class="block text-xs text-slate-400 mb-1.5">选择角色 (可多选)</label>
          <div class="flex flex-wrap gap-1.5">
            <button v-for="c in characterList" :key="c.id" @click="toggleCharacter(c.id)"
              class="px-2.5 py-1 rounded-lg text-xs transition-all cursor-pointer"
              :class="selectedCharacterIds.includes(c.id) ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30' : 'bg-white/5 text-slate-400 border border-white/10 hover:border-white/20'">
              {{ c.name }}
            </button>
          </div>
        </div>
        <div v-if="sceneList.length" class="flex-1 min-w-0">
          <label class="block text-xs text-slate-400 mb-1.5">选择场景 (可多选)</label>
          <div class="flex flex-wrap gap-1.5">
            <button v-for="s in sceneList" :key="s.id" @click="toggleScene(s.id)"
              class="px-2.5 py-1 rounded-lg text-xs transition-all cursor-pointer"
              :class="selectedSceneIds.includes(s.id) ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30' : 'bg-white/5 text-slate-400 border border-white/10 hover:border-white/20'">
              {{ s.name }}
            </button>
          </div>
        </div>
      </div>
      <!-- Three-column layout -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <ContentPanel v-model="contentForm" :bgm-list="bgmList" @bgm-upload="handleBgmUpload"/>
        <VoiceVisualPanel v-model="voiceVisualForm" :templates="templates" :media-workflows="mediaWorkflows" :tts-workflows="ttsWorkflows" :resources-loading="resourcesLoading" @ref-audio-upload="handleRefAudioUpload"/>
        <GeneratePanel :generating="generating" :progress="progress" :result="result" :history="history" :video-url="videoUrl" :config-valid="!!(systemConfig.llmApiKey || systemConfig.runninghubApiKey)" @generate="handleGenerate" @clear-result="handleClearResult"/>
      </div>
    </div>

    <!-- Custom Media -->
    <CustomMediaPanel v-else-if="activePipeline === 'custom_media'" />

    <!-- Digital Human -->
    <DigitalHumanPanel v-else-if="activePipeline === 'digital_human'" />

    <!-- Image to Video -->
    <ImageToVideoPanel v-else-if="activePipeline === 'image_to_video'" />

    <!-- Action Transfer -->
    <ActionTransferPanel v-else-if="activePipeline === 'action_transfer'" />

    <!-- Seedance 2.0 -->
    <SeedancePanel v-else-if="activePipeline === 'seedance'" />
  </div>
</template>
```

## src/App.vue

```html
<script setup>
import ToastNotification from './components/ToastNotification.vue'
</script>

<template>
  <div class="cinematic-bg"></div>
  <div class="dot-grid"></div>
  <RouterView />
  <ToastNotification />
</template>
```
