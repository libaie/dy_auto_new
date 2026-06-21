<!-- 管理端业务页面：承载 DashboardPage 页面流程，协调接口数据、用户操作和业务状态展示。 -->
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

// 前端业务函数：协调 fetchDashboardData 对应的页面流程、接口调用或状态转换。
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

// 前端业务函数：协调 createSparkline 对应的页面流程、接口调用或状态转换。
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

// 前端业务函数：协调 updateCharts 对应的页面流程、接口调用或状态转换。
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
