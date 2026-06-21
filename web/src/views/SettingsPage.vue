<!-- 管理端业务页面：承载 SettingsPage 页面流程，协调接口数据、用户操作和业务状态展示。 -->
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
