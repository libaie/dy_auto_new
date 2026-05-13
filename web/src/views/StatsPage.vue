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
