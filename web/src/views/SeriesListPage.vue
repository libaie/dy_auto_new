<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-gray-900">系列管理</h1>
      <button @click="showCreate = true" class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700">
        + 新建系列
      </button>
    </div>

    <!-- 新建系列 Dialog -->
    <div v-if="showCreate" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl p-6 w-full max-w-lg shadow-xl">
        <h2 class="text-lg font-semibold mb-4">新建系列</h2>
        <div class="space-y-3">
          <input v-model="form.title" placeholder="系列标题" class="w-full border rounded-lg px-3 py-2" />
          <textarea v-model="form.logline" placeholder="一句话梗概 (logline)" class="w-full border rounded-lg px-3 py-2" rows="2" />
          <div class="flex gap-3">
            <select v-model="form.genre" class="border rounded-lg px-3 py-2 flex-1">
              <option value="drama">都市爱情</option>
              <option value="romance">古装言情</option>
              <option value="fantasy">奇幻悬疑</option>
              <option value="suspense">悬疑推理</option>
              <option value="scifi">科幻</option>
            </select>
            <select v-model="form.total_episodes" class="border rounded-lg px-3 py-2">
              <option v-for="n in [10,20,30,50]" :key="n" :value="n">{{ n }} 集</option>
            </select>
            <input v-model.number="form.target_duration" type="number" placeholder="时长(s)" class="border rounded-lg px-3 py-2 w-24" />
          </div>
          <div class="flex gap-3">
            <select v-model="form.mode" class="border rounded-lg px-3 py-2 flex-1">
              <option value="step_by_step">逐步确认模式</option>
              <option value="fully_automatic">全自动一键生成</option>
            </select>
            <label class="flex items-center gap-2 text-sm">
              <input type="checkbox" v-model="form.pilot_first" /> Pilot 试点
            </label>
          </div>
        </div>
        <div class="flex justify-end gap-3 mt-6">
          <button @click="showCreate = false" class="px-4 py-2 border rounded-lg">取消</button>
          <button @click="doCreate" class="px-4 py-2 bg-blue-600 text-white rounded-lg" :disabled="creating">
            {{ creating ? '创建中...' : '创建' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 系列列表 -->
    <div v-if="loading" class="text-gray-500 text-center py-12">加载中...</div>
    <div v-else-if="seriesList.length === 0" class="text-gray-400 text-center py-12">暂无系列，点击「新建系列」开始</div>
    <div v-else class="grid gap-4">
      <div v-for="s in seriesList" :key="s.id"
           class="bg-white rounded-xl border p-5 hover:shadow-md transition cursor-pointer"
           @click="$router.push(`/series/${s.id}`)">
        <div class="flex justify-between items-start">
          <div>
            <h3 class="text-lg font-semibold text-gray-900">{{ s.title }}</h3>
            <p class="text-sm text-gray-500 mt-1">{{ s.logline || '(无梗概)' }}</p>
            <div class="flex gap-3 mt-2 text-xs text-gray-400">
              <span>{{ s.total_episodes }} 集</span>
              <span>{{ s.target_duration }}s/集</span>
              <span>{{ s.genre }}</span>
              <span>{{ s.mode === 'fully_automatic' ? '全自动' : '逐步确认' }}</span>
            </div>
          </div>
          <span :class="statusClass(s.status)" class="px-2 py-1 rounded text-xs font-medium">{{ s.status }}</span>
        </div>
        <div class="mt-3 bg-gray-100 rounded-full h-2">
          <div class="bg-blue-500 h-2 rounded-full" :style="{ width: progressPercent(s) + '%' }"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { listSeries, createSeries } from '../api/series.js'

const seriesList = ref([])
const loading = ref(true)
const showCreate = ref(false)
const creating = ref(false)

const form = reactive({
  title: '', logline: '', genre: 'drama', total_episodes: 30, target_duration: 90,
  mode: 'step_by_step', pilot_first: true,
})

async function loadSeries() {
  loading.value = true
  const { data } = await listSeries()
  seriesList.value = data.ok ? data.series : []
  loading.value = false
}

async function doCreate() {
  creating.value = true
  await createSeries({ ...form })
  showCreate.value = false
  await loadSeries()
  creating.value = false
}

function statusClass(s) {
  return { draft: 'bg-gray-100 text-gray-600', rendering: 'bg-yellow-100 text-yellow-700',
           done: 'bg-green-100 text-green-700', failed: 'bg-red-100 text-red-700' }[s] || 'bg-gray-100 text-gray-600'
}

function progressPercent(s) {
  if (s.status === 'done') return 100
  if (s.status === 'draft') return 0
  return s.status === 'rendering' ? 50 : 10
}

onMounted(loadSeries)
</script>
