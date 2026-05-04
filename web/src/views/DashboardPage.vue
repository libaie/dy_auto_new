<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { getDashboard, getRealtimeStats } from '../api/stats.js'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import TipIcon from '../components/TipIcon.vue'
import { useToastStore } from '../stores/toast.js'

const loading = ref(true)
const error = ref(null)

const accounts = ref({ total: 0, active: 0, risk_controlled: 0 })
const devices = ref({ total: 0, online: 0 })
const tasks = ref({ total: 0, pending: 0, running: 0, completed: 0, failed: 0, cancelled: 0 })

const realtime = ref({ online_devices: 0, running_tasks: 0, pending_tasks: 0 })

const toast = useToastStore()

let refreshTimer = null

function startPolling() {
  stopPolling()
  refreshTimer = setInterval(fetchDashboardData, 10000)
}

function stopPolling() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

function handleVisibilityChange() {
  if (document.hidden) {
    stopPolling()
  } else {
    fetchDashboardData()
    startPolling()
  }
}

async function fetchDashboardData() {
  try {
    const [dashRes, rtRes] = await Promise.all([
      getDashboard(),
      getRealtimeStats(),
    ])

    const dash = dashRes.data
    accounts.value = dash.accounts || accounts.value
    devices.value = dash.devices || devices.value
    tasks.value = dash.tasks || tasks.value

    realtime.value = rtRes.data || realtime.value
    error.value = null
  } catch (e) {
    toast.error('加载仪表盘数据失败')
    error.value = e.response?.data?.message || '加载仪表盘数据失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchDashboardData()
  startPolling()
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onUnmounted(() => {
  stopPolling()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold text-white mb-6 inline-flex items-center gap-1.5">仪表盘 <TipIcon text="系统运行概览，展示账号、设备和任务的实时状态统计" /></h1>

    <LoadingSpinner v-if="loading" />

    <div v-else-if="error" class="glass-card border-red-500/30 text-red-400 px-4 py-3 rounded-xl mb-6">
      {{ error }}
      <button
        class="ml-2 underline text-red-300 hover:text-red-200"
        @click="loading = true; fetchDashboardData()"
      >
        重试
      </button>
    </div>

    <template v-else>
      <!-- Summary Cards -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <!-- Accounts Card -->
        <div class="glass-card stat-shimmer p-6 cursor-pointer">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-slate-300">账号</h2>
            <router-link
              to="/accounts"
              class="text-sm text-cyan-400 hover:text-cyan-300 transition-colors"
            >
              查看全部
            </router-link>
          </div>
          <div class="text-3xl font-bold gradient-text mb-2 animate-count">{{ accounts.total }}</div>
          <div class="flex gap-4 text-sm text-slate-400">
            <span>活跃: <strong class="text-emerald-400">{{ accounts.active }}</strong></span>
            <span class="inline-flex items-center gap-1.5">风控中: <strong class="text-red-400">{{ accounts.risk_controlled }}</strong><TipIcon text="账号因异常操作被抖音风控限制，暂时无法执行任务" /></span>
          </div>
        </div>

        <!-- Devices Card -->
        <div class="glass-card stat-shimmer p-6 cursor-pointer">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-slate-300">设备</h2>
            <router-link
              to="/devices"
              class="text-sm text-cyan-400 hover:text-cyan-300 transition-colors"
            >
              查看全部
            </router-link>
          </div>
          <div class="text-3xl font-bold gradient-text mb-2 animate-count">{{ devices.total }}</div>
          <div class="flex gap-4 text-sm text-slate-400">
            <span class="inline-flex items-center gap-1.5">在线: <strong class="text-emerald-400 relative inline-flex items-center">{{ realtime.online_devices }}<span class="ml-1 w-2 h-2 rounded-full bg-emerald-400 pulse-ring relative"></span></strong><TipIcon text="当前实时在线的设备数量（WebSocket 连接）" /></span>
            <span class="inline-flex items-center gap-1.5">总计在线: <strong class="text-slate-300">{{ devices.online }}</strong><TipIcon text="今日内曾经上线过的设备总数" /></span>
          </div>
        </div>

        <!-- Tasks Card -->
        <div class="glass-card stat-shimmer p-6 cursor-pointer">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-slate-300">任务</h2>
            <router-link
              to="/tasks"
              class="text-sm text-cyan-400 hover:text-cyan-300 transition-colors"
            >
              查看全部
            </router-link>
          </div>
          <div class="text-3xl font-bold gradient-text mb-2 animate-count">{{ tasks.total }}</div>
          <div class="flex flex-wrap gap-3 text-sm text-slate-400">
            <span>待执行: <strong class="text-amber-400">{{ realtime.pending_tasks }}</strong></span>
            <span>运行中: <strong class="text-blue-400">{{ realtime.running_tasks }}</strong></span>
            <span>已完成: <strong class="text-emerald-400">{{ tasks.completed }}</strong></span>
            <span>失败: <strong class="text-red-400">{{ tasks.failed }}</strong></span>
            <span>已取消: <strong class="text-slate-400">{{ tasks.cancelled }}</strong></span>
          </div>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="glass-card p-6">
        <h2 class="text-lg font-semibold text-slate-300 mb-4">快捷操作</h2>
        <div class="flex flex-wrap gap-4">
          <router-link
            to="/tasks"
            class="btn-aurora inline-flex items-center px-5 py-2.5 text-sm font-medium rounded-xl"
          >
            <span class="relative z-10">任务管理</span>
          </router-link>
          <router-link
            to="/accounts"
            class="btn-aurora inline-flex items-center px-5 py-2.5 text-sm font-medium rounded-xl"
          >
            <span class="relative z-10">账号管理</span>
          </router-link>
          <router-link
            to="/devices"
            class="btn-aurora inline-flex items-center px-5 py-2.5 text-sm font-medium rounded-xl"
          >
            <span class="relative z-10">设备管理</span>
          </router-link>
        </div>
      </div>
    </template>
  </div>
</template>
