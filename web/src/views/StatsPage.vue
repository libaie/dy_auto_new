<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
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
const chartCanvas = ref(null)
let chartInstance = null
const toast = useToastStore()

const summaryCards = [
  { key: 'likes', label: '点赞', color: 'bg-blue-500' },
  { key: 'comments', label: '评论', color: 'bg-green-500' },
  { key: 'follows', label: '关注', color: 'bg-yellow-500' },
  { key: 'dms', label: '私信', color: 'bg-red-500' },
  { key: 'replies', label: '回复', color: 'bg-purple-500' }
]

const totals = computed(() => {
  const accounts = statsData.value?.accounts
  if (!accounts || accounts.length === 0) return { likes: 0, comments: 0, follows: 0, dms: 0, replies: 0 }
  const result = { likes: 0, comments: 0, follows: 0, dms: 0, replies: 0 }
  for (const acc of accounts) {
    result.likes += acc.likes || 0
    result.comments += acc.comments || 0
    result.follows += acc.follows || 0
    result.dms += acc.dms || 0
    result.replies += acc.replies || 0
  }
  return result
})

function buildChart(accounts) {
  if (chartInstance) {
    chartInstance.destroy()
    chartInstance = null
  }

  nextTick(() => {
    if (!chartCanvas.value) return

    const labels = accounts.map(a => a.nickname || a.account_id)
    chartInstance = new Chart(chartCanvas.value, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: '点赞',
            data: accounts.map(a => a.likes || 0),
            backgroundColor: 'rgba(59, 130, 246, 0.7)'
          },
          {
            label: '评论',
            data: accounts.map(a => a.comments || 0),
            backgroundColor: 'rgba(34, 197, 94, 0.7)'
          },
          {
            label: '关注',
            data: accounts.map(a => a.follows || 0),
            backgroundColor: 'rgba(234, 179, 8, 0.7)'
          },
          {
            label: '私信',
            data: accounts.map(a => a.dms || 0),
            backgroundColor: 'rgba(239, 68, 68, 0.7)'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'top' }
        },
        scales: {
          x: { stacked: true },
          y: { stacked: true, beginAtZero: true }
        }
      }
    })
  })
}

async function fetchStats() {
  loading.value = true
  try {
    const res = await getDailyStats(selectedDate.value)
    statsData.value = res.data
    if (statsData.value?.accounts?.length) {
      await nextTick()
      buildChart(statsData.value.accounts)
    }
  } catch (err) {
    toast.error('加载统计数据失败')
    statsData.value = null
  } finally {
    loading.value = false
  }
}

watch(selectedDate, () => {
  fetchStats()
})

onMounted(() => {
  fetchStats()
})

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.destroy()
    chartInstance = null
  }
})
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white flex items-center gap-1.5">数据统计<TipIcon text="查看各账号的操作统计数据，支持按日期筛选" /></h1>
      <div class="flex items-center gap-1.5">
        <input
          v-model="selectedDate"
          type="date"
          class="border border-white/10 bg-white/5 rounded-lg px-3 py-2 text-sm text-slate-200"
        />
        <TipIcon text="选择查看统计数据的日期，默认为今天" />
      </div>
    </div>

    <!-- Loading -->
    <LoadingSpinner v-if="loading" />

    <!-- No data -->
    <div
      v-else-if="!statsData || !statsData.accounts || statsData.accounts.length === 0"
      class="flex items-center justify-center py-20"
    >
      <p class="text-slate-400 text-lg">暂无数据</p>
    </div>

    <!-- Data content -->
    <template v-else>
      <!-- Summary cards -->
      <div class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <div
          v-for="card in summaryCards"
          :key="card.key"
          class="glass-card stat-shimmer p-4 text-center cursor-pointer"
        >
          <div
            class="w-10 h-10 rounded-full mx-auto mb-2 flex items-center justify-center text-white text-sm"
            :class="card.color"
          >
            {{ card.label.charAt(0) }}
          </div>
          <p class="text-2xl font-bold gradient-text animate-count">
            {{ totals[card.key] }}
          </p>
          <p class="text-sm text-slate-400">{{ card.label }}</p>
        </div>
      </div>

      <!-- Chart -->
      <div class="glass-card p-6">
        <h2 class="text-lg font-semibold text-slate-300 mb-4 flex items-center gap-1.5">各账号操作统计<TipIcon text="选定日期内所有账号的操作统计总计" /></h2>
        <div class="relative" style="height: 400px">
          <canvas ref="chartCanvas"></canvas>
        </div>
      </div>
    </template>
  </div>
</template>
