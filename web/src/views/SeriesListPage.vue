<!-- 管理端业务页面：承载 SeriesListPage 页面流程，协调接口数据、用户操作和业务状态展示。 -->
<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-100">系列管理</h1>
        <p class="text-sm text-slate-400 mt-1">创建和管理连续短剧系列，配置剧集数和生成模式</p>
      </div>
      <button data-test="open-create-series" @click="showCreate = true" class="bg-sky-500 hover:bg-sky-400 text-white px-4 py-2 rounded-lg transition-colors duration-200 cursor-pointer" title="创建一个新的短剧系列">
        + 新建系列
      </button>
    </div>

    <!-- 新建 Dialog -->
    <div v-if="showCreate" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50" @click.self="showCreate = false">
      <div class="rounded-xl p-6 w-full max-w-lg shadow-2xl border border-gray-700/50" style="background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(20px);">
        <h2 class="text-lg font-semibold text-slate-100 mb-4">新建系列</h2>
        <div class="space-y-3">
          <div>
            <input data-test="series-create-title" v-model="form.title" placeholder="系列标题" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
            <p class="text-xs text-slate-500 mt-1 ml-1">输入系列名称，如"都市爱情故事"</p>
          </div>
          <div>
            <textarea data-test="series-create-logline" v-model="form.logline" placeholder="一句话梗概 (logline)" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" rows="2" />
            <p class="text-xs text-slate-500 mt-1 ml-1">用一句话概括系列的核心剧情，AI 会根据梗概生成完整剧本</p>
          </div>
          <div class="flex gap-3">
            <div class="flex-1">
              <select v-model="form.genre" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500/50 cursor-pointer">
                <option v-for="g in genreOptions" :key="g.value" :value="g.value">{{ g.label }}</option>
              </select>
              <p class="text-xs text-slate-500 mt-1 ml-1">可在"系统字典"中管理类型选项</p>
            </div>
            <div>
              <select v-model="form.total_episodes" class="rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 cursor-pointer">
                <option v-for="n in [10,20,30,50]" :key="n" :value="n">{{ n }} 集</option>
              </select>
              <p class="text-xs text-slate-500 mt-1 ml-1">总剧集数</p>
            </div>
            <div>
              <input v-model.number="form.target_duration" type="number" placeholder="时长(s)" class="rounded-lg px-3 py-2 w-24 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50" />
              <p class="text-xs text-slate-500 mt-1 ml-1">每集目标时长</p>
            </div>
          </div>
          <div class="flex gap-3">
            <div class="flex-1">
              <select data-test="series-create-mode" v-model="form.mode" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 cursor-pointer">
                <option value="step_by_step">逐步确认模式 — 每阶段需人工确认</option>
                <option value="fully_automatic">全自动一键生成 — 输入梗概直接出片</option>
              </select>
              <p class="text-xs text-slate-500 mt-1 ml-1">逐步确认：每层完成后需确认再继续 | 全自动：零人工干预</p>
            </div>
            <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer" title="开启后先生成第1集试点，确认无误后批量生成剩余剧集">
              <input data-test="series-create-pilot" type="checkbox" v-model="form.pilot_first" class="accent-sky-500" /> Pilot 试点
            </label>
          </div>
        </div>
        <div class="flex justify-end gap-3 mt-6">
          <button @click="showCreate = false" class="px-4 py-2 rounded-lg border border-gray-600 text-slate-300 hover:bg-gray-700 transition cursor-pointer">取消</button>
          <button data-test="submit-create-series" @click="doCreate" class="px-4 py-2 bg-sky-500 hover:bg-sky-400 text-white rounded-lg transition disabled:opacity-50 cursor-pointer" :disabled="creating" :title="creating ? '正在创建...' : '创建系列并自动生成剧集占位'">
            {{ creating ? '创建中...' : '创建' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="text-slate-400 text-center py-12">加载中...</div>
    <div v-else-if="error" class="text-red-400 text-center py-12">{{ error }}</div>
    <div v-else-if="seriesList.length === 0" class="text-slate-500 text-center py-12">
      暂无系列，点击「新建系列」开始<br><span class="text-xs text-slate-600 mt-1">提示：创建系列后可在详情页关联角色和场景</span>
    </div>
    <div v-else class="grid gap-4">
      <div v-for="s in seriesList" :key="s.id"
           class="rounded-xl border border-gray-700/50 p-5 hover:shadow-lg hover:shadow-sky-900/10 transition-all duration-200 cursor-pointer"
           style="background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(12px);"
           @click="$router.push(`/series/${s.id}`)" :title="`点击查看 ${s.title} 的详情和剧集列表`">
        <div class="flex justify-between items-start">
          <div>
            <h3 class="text-lg font-semibold text-slate-100">{{ s.title }}</h3>
            <p class="text-sm text-slate-400 mt-1">{{ s.logline || '(无梗概)' }}</p>
            <div class="flex gap-3 mt-2 text-xs text-slate-500">
              <span>{{ s.total_episodes }} 集</span><span>{{ s.target_duration }}s/集</span>
              <span>{{ genreLabel(s.genre) }}</span>
              <span>{{ s.mode === 'fully_automatic' ? '全自动' : '逐步确认' }}</span>
            </div>
          </div>
          <span :class="statusClass(s.status)" class="px-2 py-1 rounded text-xs font-medium">{{ s.status }}</span>
        </div>
        <div class="mt-3 rounded-full h-1.5" style="background: rgba(255,255,255,0.06);">
          <div class="h-1.5 rounded-full transition-all duration-500" :class="progressColor(s.status)" :style="{ width: progressPercent(s) + '%' }"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { getCurrentInstance, ref, reactive, onMounted } from 'vue'
import { listSeries, createSeries } from '../api/series.js'
import { listItems } from '../api/referenceData.js'

const seriesList = ref([]); const loading = ref(true); const showCreate = ref(false); const creating = ref(false); const error = ref('')
const genreOptions = ref([])
const form = reactive({ title: '', logline: '', genre: 'drama', total_episodes: 30, target_duration: 90, mode: 'step_by_step', pilot_first: true })
const instance = getCurrentInstance()

// 前端业务函数：协调 loadGenres 对应的页面流程、接口调用或状态转换。
async function loadGenres() { try { const { data } = await listItems('series_genre'); if (data.ok) { genreOptions.value = data.items; if (data.items.length && !genreOptions.value.find(g => g.value === form.genre)) form.genre = data.items[0].value } } catch (e) { /* fallback to hardcoded */ } }
// 前端业务函数：协调 loadSeries 对应的页面流程、接口调用或状态转换。
async function loadSeries() { loading.value = true; error.value = ''; try { const { data } = await listSeries(); seriesList.value = data.ok ? data.series : [] } catch (e) { error.value = e.message || '加载失败' } finally { loading.value = false } }
async function doCreate() {
  creating.value = true
  try {
    const { data } = await createSeries({ ...form })
    showCreate.value = false
    const seriesId = data?.series?.id
    if (form.mode === 'fully_automatic' && seriesId) {
      await instance?.proxy?.$router?.push(`/series/${seriesId}?autostart=production`)
      return
    }
    if (seriesId) {
      await instance?.proxy?.$router?.push(`/series/${seriesId}`)
      return
    }
    await loadSeries()
  } catch (e) {
    error.value = e.message || '创建失败'
  } finally {
    creating.value = false
  }
}

// 前端业务函数：协调 statusClass 对应的页面流程、接口调用或状态转换。
function statusClass(s) { return { draft: 'bg-gray-800 text-slate-400', rendering: 'bg-yellow-900/40 text-yellow-400', done: 'bg-emerald-900/40 text-emerald-400', failed: 'bg-red-900/40 text-red-400' }[s] || 'bg-gray-800 text-slate-400' }
// 前端业务函数：协调 progressColor 对应的页面流程、接口调用或状态转换。
function progressColor(s) { return s === 'done' ? 'bg-emerald-500' : s === 'rendering' ? 'bg-sky-500 animate-pulse' : 'bg-slate-600' }
// 前端业务函数：协调 progressPercent 对应的页面流程、接口调用或状态转换。
function progressPercent(s) { if (s === 'done') return 100; if (s === 'draft') return 0; return s === 'rendering' ? 50 : 10 }
// 前端业务函数：协调 genreLabel 对应的页面流程、接口调用或状态转换。
function genreLabel(v) { const g = genreOptions.value.find(x => x.value === v); return g ? g.label : v }

onMounted(async () => { await loadGenres(); await loadSeries() })
</script>
