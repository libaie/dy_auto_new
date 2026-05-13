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
