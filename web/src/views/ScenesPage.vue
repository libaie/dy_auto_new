<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-100">场景资产库</h1>
        <p class="text-sm text-slate-400 mt-1">管理拍摄场景，配置光照氛围和参考图</p>
      </div>
      <button @click="showCreate = true" class="bg-sky-500 hover:bg-sky-400 text-white px-4 py-2 rounded-lg transition cursor-pointer" title="创建新场景，描述后可生成多角度参考图">
        + 新建场景
      </button>
    </div>

    <div v-if="loading" class="text-slate-400 text-center py-12">加载中...</div>
    <div v-else-if="scenes.length === 0" class="text-slate-500 text-center py-12">
      暂无场景<br><span class="text-xs text-slate-600 mt-1">提示：创建场景后可在系列详情中关联到具体剧集</span>
    </div>
    <div v-else class="grid grid-cols-3 gap-4">
      <div v-for="s in scenes" :key="s.id"
           class="rounded-xl border border-gray-700/50 p-4 hover:shadow-lg hover:shadow-sky-900/10 transition-all duration-200"
           style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);">
        <h3 class="font-semibold text-slate-100">{{ s.name }}</h3>
        <div class="flex gap-2 mt-2 text-xs">
          <span class="px-2 py-1 rounded bg-gray-800 text-slate-400">{{ sceneTypeLabel(s.scene_type) }}</span>
          <span class="px-2 py-1 rounded bg-gray-800 text-slate-400">{{ lightingLabel(s.lighting) || '-' }}</span>
          <span class="px-2 py-1 rounded bg-gray-800 text-slate-400">{{ moodLabel(s.mood) || '-' }}</span>
        </div>
        <p class="text-sm text-slate-400 mt-2">{{ s.location_desc || '(无地点描述)' }}</p>
        <div class="flex gap-1 mt-2">
          <span :class="s.reference_wideshot_url ? 'text-emerald-400' : 'text-slate-600'" class="text-xs">{{ s.reference_wideshot_url ? '广角 ✓' : '广角 —' }}</span>
          <span :class="s.reference_midshot_url ? 'text-emerald-400' : 'text-slate-600'" class="text-xs">{{ s.reference_midshot_url ? '中景 ✓' : '中景 —' }}</span>
          <span :class="s.reference_aerial_url ? 'text-emerald-400' : 'text-slate-600'" class="text-xs">{{ s.reference_aerial_url ? '俯拍 ✓' : '俯拍 —' }}</span>
        </div>
      </div>
    </div>

    <div v-if="showCreate" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50" @click.self="showCreate = false">
      <div class="rounded-xl p-6 w-full max-w-md shadow-2xl border border-gray-700/50" style="background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(20px);">
        <h2 class="text-lg font-semibold text-slate-100 mb-4">新建场景</h2>
        <div class="space-y-3">
          <div>
            <input v-model="form.name" placeholder="场景名称" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </div>
          <div>
            <select v-model="form.scene_type" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 cursor-pointer">
              <option v-for="t in typeOptions" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
            <p class="text-xs text-slate-500 mt-1 ml-1">可在"系统字典"中管理场景类型</p>
          </div>
          <div>
            <input v-model="form.location_desc" placeholder="地点描述 — 如 'CBD高层写字楼，落地窗俯瞰城市'" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
            <p class="text-xs text-slate-500 mt-1 ml-1">描述越详细，AI 生成的场景图越准确</p>
          </div>
          <div class="flex gap-3">
            <div class="flex-1">
              <select v-model="form.lighting" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 cursor-pointer">
                <option v-for="l in lightingOptions" :key="l.value" :value="l.value">{{ l.label }}</option>
              </select>
            </div>
            <div class="flex-1">
              <select v-model="form.mood" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 cursor-pointer">
                <option v-for="m in moodOptions" :key="m.value" :value="m.value">{{ m.label }}</option>
              </select>
            </div>
          </div>
        </div>
        <div class="flex justify-end gap-3 mt-6">
          <button @click="showCreate = false" class="px-4 py-2 rounded-lg border border-gray-600 text-slate-300 hover:bg-gray-700 transition cursor-pointer">取消</button>
          <button @click="doCreate" class="px-4 py-2 bg-sky-500 hover:bg-sky-400 text-white rounded-lg transition cursor-pointer">创建</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { listScenes, createScene } from '../api/scenes.js'
import { listItems } from '../api/referenceData.js'

const scenes = ref([]); const loading = ref(true); const showCreate = ref(false)
const typeOptions = ref([]); const lightingOptions = ref([]); const moodOptions = ref([])
const form = reactive({ name: '', scene_type: 'indoor', location_desc: '', lighting: '', mood: '' })

async function loadOpts() {
  try { const [t, l, m] = await Promise.all([listItems('scene_type'), listItems('scene_lighting'), listItems('scene_mood')]); if (t.data.ok) { typeOptions.value = t.data.items; form.scene_type = t.data.items[0]?.value || 'indoor' }; if (l.data.ok) lightingOptions.value = l.data.items; if (m.data.ok) moodOptions.value = m.data.items } catch (e) {}
}
async function load() { const { data } = await listScenes(); scenes.value = data.ok ? data.scenes : []; loading.value = false }
async function doCreate() { await createScene({ ...form }); showCreate.value = false; await load() }
function sceneTypeLabel(v) { const x = typeOptions.value.find(o => o.value === v); return x ? x.label : v }
function lightingLabel(v) { const x = lightingOptions.value.find(o => o.value === v); return x ? x.label : v }
function moodLabel(v) { const x = moodOptions.value.find(o => o.value === v); return x ? x.label : v }
onMounted(async () => { await loadOpts(); await load() })
</script>
