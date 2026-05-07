<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getSettings, updateSettings } from '../api/settings.js'
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
})

async function fetchSettings() {
  loading.value = true
  try {
    const res = await getSettings()
    const data = res.data
    form.ai_api_key = data.ai_api_key || ''
    form.ai_base_url = data.ai_base_url || 'https://api.deepseek.com'
    form.ai_model = data.ai_model || 'deepseek-chat'
    form.ai_thinking = data.ai_thinking || 'max'
  } catch {
    toast.error('加载设置失败')
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  saving.value = true
  try {
    await updateSettings({
      ai_api_key: form.ai_api_key,
      ai_base_url: form.ai_base_url,
      ai_model: form.ai_model,
      ai_thinking: form.ai_thinking,
    })
    toast.success('设置已保存')
  } catch {
    toast.error('保存失败')
  } finally {
    saving.value = false
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
            </ul>
            <p class="mt-3">配置保存后，设备端下次轮询任务时自动生效。</p>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
