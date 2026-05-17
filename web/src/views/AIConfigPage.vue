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
