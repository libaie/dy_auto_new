<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { getDashboard, getRealtimeStats } from '../api/stats.js'
import LoadingSpinner from '../components/LoadingSpinner.vue'

const loading = ref(true)
const error = ref(null)

const accounts = ref({ total: 0, active: 0, risk_controlled: 0 })
const devices = ref({ total: 0, online: 0 })
const tasks = ref({ total: 0, pending: 0, running: 0, completed: 0, failed: 0 })

const realtime = ref({ online_devices: 0, running_tasks: 0, pending_tasks: 0 })

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
    <h1 class="text-2xl font-bold text-gray-800 mb-6">仪表盘</h1>

    <LoadingSpinner v-if="loading" />

    <div v-else-if="error" class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
      {{ error }}
      <button
        class="ml-2 underline text-red-800 hover:text-red-900"
        @click="loading = true; fetchDashboardData()"
      >
        重试
      </button>
    </div>

    <template v-else>
      <!-- Summary Cards -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <!-- Accounts Card -->
        <div class="bg-white rounded-lg shadow p-6">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-gray-700">账号</h2>
            <router-link
              to="/accounts"
              class="text-sm text-indigo-600 hover:text-indigo-800"
            >
              查看全部
            </router-link>
          </div>
          <div class="text-3xl font-bold text-indigo-600 mb-2">{{ accounts.total }}</div>
          <div class="flex gap-4 text-sm text-gray-500">
            <span>活跃: <strong class="text-green-600">{{ accounts.active }}</strong></span>
            <span>风控中: <strong class="text-red-600">{{ accounts.risk_controlled }}</strong></span>
          </div>
        </div>

        <!-- Devices Card -->
        <div class="bg-white rounded-lg shadow p-6">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-gray-700">设备</h2>
            <router-link
              to="/devices"
              class="text-sm text-indigo-600 hover:text-indigo-800"
            >
              查看全部
            </router-link>
          </div>
          <div class="text-3xl font-bold text-indigo-600 mb-2">{{ devices.total }}</div>
          <div class="flex gap-4 text-sm text-gray-500">
            <span>在线: <strong class="text-green-600">{{ realtime.online_devices }}</strong></span>
            <span>总计在线: <strong class="text-gray-700">{{ devices.online }}</strong></span>
          </div>
        </div>

        <!-- Tasks Card -->
        <div class="bg-white rounded-lg shadow p-6">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-semibold text-gray-700">任务</h2>
            <router-link
              to="/tasks"
              class="text-sm text-indigo-600 hover:text-indigo-800"
            >
              查看全部
            </router-link>
          </div>
          <div class="text-3xl font-bold text-indigo-600 mb-2">{{ tasks.total }}</div>
          <div class="flex flex-wrap gap-3 text-sm text-gray-500">
            <span>待执行: <strong class="text-yellow-600">{{ realtime.pending_tasks }}</strong></span>
            <span>运行中: <strong class="text-blue-600">{{ realtime.running_tasks }}</strong></span>
            <span>已完成: <strong class="text-green-600">{{ tasks.completed }}</strong></span>
            <span>失败: <strong class="text-red-600">{{ tasks.failed }}</strong></span>
          </div>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="bg-white rounded-lg shadow p-6">
        <h2 class="text-lg font-semibold text-gray-700 mb-4">快捷操作</h2>
        <div class="flex flex-wrap gap-4">
          <router-link
            to="/tasks"
            class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 transition-colors"
          >
            任务管理
          </router-link>
          <router-link
            to="/accounts"
            class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 transition-colors"
          >
            账号管理
          </router-link>
          <router-link
            to="/devices"
            class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 transition-colors"
          >
            设备管理
          </router-link>
        </div>
      </div>
    </template>
  </div>
</template>
