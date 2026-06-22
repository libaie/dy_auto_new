<!-- 管理端布局组件：提供导航、侧栏和页面容器等业务后台基础框架。 -->
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

// 前端业务函数：协调 updateClock 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 updateClock 对应业务流程的处理结果。
function updateClock() {
  currentTime.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
}

// 前端业务函数：协调 fetchStats 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 fetchStats 对应业务流程的处理结果。
async function fetchStats() {
  try { const res = await getRealtimeStats(); stats.value = res.data || stats.value } catch {}
}

onMounted(() => {
  updateClock(); clockTimer = setInterval(updateClock, 1000)
  fetchStats(); statsTimer = setInterval(fetchStats, 15000)
})
onUnmounted(() => { clearInterval(clockTimer); clearInterval(statsTimer) })

// 前端业务函数：协调 handleLogout 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 handleLogout 对应业务流程的处理结果。
function handleLogout() { auth.logout(); router.push('/login') }

const categories = [
  { key: 'ops', label: '运营', to: '/' },
  { key: 'tasks', label: '任务', to: '/tasks' },
  { key: 'data', label: '数据', to: '/data' },
  { key: 'ai-video', label: 'AI 视频', to: '/video-studio' },
  { key: 'system', label: '系统', to: '/settings' },
]

// 入参：cat 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 handleCategoryClick 对应业务流程的处理结果。
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

      <div class="hidden lg:flex items-center gap-1 tab-bar top-category-tabs">
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

<style scoped>
@media (max-width: 1023px) {
  .top-category-tabs {
    display: none;
  }
}
</style>
