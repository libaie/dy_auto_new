<!-- 管理端业务页面：承载 ScenesPage 页面流程，协调接口数据、用户操作和业务状态展示。 -->
<template>
  <div class="p-6">
    <div class="mb-6 flex items-center justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-100">场景资产库</h1>
        <p class="mt-1 text-sm text-slate-400">管理拍摄场景，维护地点、光照、氛围和参考图。</p>
      </div>
      <div class="flex gap-2">
        <button type="button" class="rounded-lg bg-cyan-600 px-4 py-2 text-sm text-white transition hover:bg-cyan-500" @click="showAiGen = true">
          AI 批量生成
        </button>
        <button type="button" class="rounded-lg bg-sky-600 px-4 py-2 text-sm text-white transition hover:bg-sky-500" @click="showCreate = true">
          新建场景
        </button>
      </div>
    </div>

    <div v-if="loading" class="py-12 text-center text-slate-400">加载中...</div>
    <div v-else-if="error" class="py-12 text-center text-red-400">{{ error }}</div>
    <div v-else-if="scenes.length === 0" class="py-12 text-center text-slate-500">
      暂无场景
      <div class="mt-1 text-xs text-slate-600">创建场景后可在系列详情中关联到具体剧集。</div>
    </div>

    <div v-else class="grid gap-4 lg:grid-cols-3">
      <button
        v-for="s in scenes"
        :key="s.id"
        type="button"
        :data-test="`scene-card-${s.id}`"
        class="rounded-lg border border-slate-800 bg-slate-900/60 p-4 text-left transition hover:border-sky-500/50 hover:bg-slate-900"
        @click="openScene(s)"
      >
        <h3 class="font-semibold text-slate-100">{{ s.name }}</h3>
        <div class="mt-2 flex flex-wrap gap-2 text-xs">
          <span class="rounded bg-slate-800 px-2 py-1 text-slate-400">{{ sceneTypeLabel(s.scene_type) }}</span>
          <span class="rounded bg-slate-800 px-2 py-1 text-slate-400">{{ lightingLabel(s.lighting) || '-' }}</span>
          <span class="rounded bg-slate-800 px-2 py-1 text-slate-400">{{ moodLabel(s.mood) || '-' }}</span>
        </div>
        <p class="mt-3 line-clamp-2 text-sm text-slate-400">{{ s.location_desc || '无地点描述' }}</p>
        <div class="mt-3 flex flex-wrap gap-2 text-xs">
          <span :class="s.reference_wideshot_url ? 'text-emerald-400' : 'text-slate-600'">广角 {{ s.reference_wideshot_url ? '已配置' : '待生成' }}</span>
          <span :class="s.reference_midshot_url ? 'text-emerald-400' : 'text-slate-600'">中景 {{ s.reference_midshot_url ? '已配置' : '待生成' }}</span>
          <span :class="s.reference_aerial_url ? 'text-emerald-400' : 'text-slate-600'">俯拍 {{ s.reference_aerial_url ? '已配置' : '待生成' }}</span>
        </div>
      </button>
    </div>

    <div v-if="showAiGen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" @click.self="showAiGen = false">
      <div class="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-lg border border-slate-700 bg-slate-950 p-6 shadow-2xl">
        <h2 class="mb-4 text-lg font-semibold text-slate-100">AI 批量生成场景</h2>
        <p class="mb-4 text-xs text-slate-500">输入故事概要，AI 会生成可勾选的场景档案。</p>
        <div class="space-y-3">
          <label class="block space-y-1">
            <span class="text-xs text-slate-400">故事概要</span>
            <textarea v-model="aiForm.text" rows="4" class="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100" placeholder="输入故事概要或剧本片段" />
          </label>
          <div class="flex gap-3">
            <label class="block flex-1 space-y-1">
              <span class="text-xs text-slate-400">类型</span>
              <select v-model="aiForm.genre" class="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100">
                <option v-for="g in genreOptions" :key="g.value" :value="g.value">{{ g.label }}</option>
              </select>
            </label>
            <label class="block w-28 space-y-1">
              <span class="text-xs text-slate-400">数量</span>
              <input v-model.number="aiForm.count" type="number" min="1" max="10" class="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100">
            </label>
          </div>
        </div>

        <div v-if="aiGenerating" class="py-8 text-center text-sm text-slate-400">AI 正在生成场景...</div>
        <div v-else-if="aiResult.length" class="mt-4 max-h-[300px] space-y-2 overflow-y-auto">
          <p class="text-xs text-slate-500">AI 生成了 {{ aiResult.length }} 个场景，请勾选需要创建的项目。</p>
          <label v-for="(s, i) in aiResult" :key="i" class="flex items-start gap-3 rounded-lg border border-slate-800 bg-slate-900/70 p-3">
            <input v-model="s._selected" type="checkbox" class="mt-1">
            <span class="min-w-0 flex-1">
              <span class="block font-semibold text-slate-100">{{ s.name }}</span>
              <span class="mt-1 block text-xs text-slate-400">{{ s.location_desc || '-' }}</span>
            </span>
          </label>
        </div>

        <div class="mt-6 flex justify-end gap-3">
          <button type="button" class="rounded-lg border border-slate-700 px-4 py-2 text-slate-300 hover:bg-slate-800" @click="showAiGen = false; aiResult = []">取消</button>
          <button v-if="!aiResult.length" type="button" :disabled="!aiForm.text || aiGenerating" class="rounded-lg bg-cyan-600 px-4 py-2 text-white hover:bg-cyan-500 disabled:opacity-50" @click="doAiGenerate">
            {{ aiGenerating ? '生成中...' : 'AI 生成' }}
          </button>
          <button v-else type="button" :disabled="aiBatchCreating" class="rounded-lg bg-sky-600 px-4 py-2 text-white hover:bg-sky-500 disabled:opacity-50" @click="doBatchCreate">
            {{ aiBatchCreating ? '创建中...' : `批量创建 (${selectedAiCount})` }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="showCreate" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" @click.self="showCreate = false">
      <div class="w-full max-w-md rounded-lg border border-slate-700 bg-slate-950 p-6 shadow-2xl">
        <h2 class="mb-4 text-lg font-semibold text-slate-100">新建场景</h2>
        <div class="space-y-3">
          <label class="block space-y-1">
            <span class="text-xs text-slate-400">场景名称</span>
            <input v-model="form.name" class="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100">
          </label>
          <label class="block space-y-1">
            <span class="text-xs text-slate-400">场景类型</span>
            <select v-model="form.scene_type" class="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100">
              <option v-for="t in typeOptions" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
          </label>
          <label class="block space-y-1">
            <span class="text-xs text-slate-400">地点描述</span>
            <input v-model="form.location_desc" class="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100">
          </label>
          <div class="flex gap-3">
            <label class="block flex-1 space-y-1">
              <span class="text-xs text-slate-400">光照</span>
              <select v-model="form.lighting" class="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100">
                <option v-for="l in lightingOptions" :key="l.value" :value="l.value">{{ l.label }}</option>
              </select>
            </label>
            <label class="block flex-1 space-y-1">
              <span class="text-xs text-slate-400">氛围</span>
              <select v-model="form.mood" class="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100">
                <option v-for="m in moodOptions" :key="m.value" :value="m.value">{{ m.label }}</option>
              </select>
            </label>
          </div>
        </div>
        <div class="mt-6 flex justify-end gap-3">
          <button type="button" class="rounded-lg border border-slate-700 px-4 py-2 text-slate-300 hover:bg-slate-800" @click="showCreate = false">取消</button>
          <button type="button" class="rounded-lg bg-sky-600 px-4 py-2 text-white hover:bg-sky-500" @click="doCreate">创建</button>
        </div>
      </div>
    </div>

    <AssetDetailDrawer :open="Boolean(selectedScene)" title="场景详情" :subtitle="selectedScene?.name || ''" @close="closeScene">
      <div v-if="selectedScene" class="space-y-6">
        <div v-if="drawerError" data-test="scene-drawer-error" class="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">
          {{ drawerError }}
        </div>

        <section class="space-y-3">
          <label class="block space-y-1">
            <span class="text-xs font-medium text-slate-300">场景名称</span>
            <input v-model="editingScene.name" data-test="scene-name-input" class="w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100">
          </label>
          <label class="block space-y-1">
            <span class="text-xs font-medium text-slate-300">场景类型</span>
            <select v-model="editingScene.scene_type" class="w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100">
              <option v-for="t in typeOptions" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
          </label>
          <label class="block space-y-1">
            <span class="text-xs font-medium text-slate-300">地点描述</span>
            <textarea v-model="editingScene.location_desc" rows="3" class="w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100" />
          </label>
          <div class="grid gap-3 sm:grid-cols-2">
            <label class="block space-y-1">
              <span class="text-xs font-medium text-slate-300">光照</span>
              <select v-model="editingScene.lighting" class="w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100">
                <option v-for="l in lightingOptions" :key="l.value" :value="l.value">{{ l.label }}</option>
              </select>
            </label>
            <label class="block space-y-1">
              <span class="text-xs font-medium text-slate-300">氛围</span>
              <select v-model="editingScene.mood" class="w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100">
                <option v-for="m in moodOptions" :key="m.value" :value="m.value">{{ m.label }}</option>
              </select>
            </label>
          </div>
        </section>

        <section class="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
          <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 class="text-sm font-semibold text-slate-100">AI 改写</h3>
              <p class="mt-1 text-xs text-slate-500">生成候选内容，确认后才会应用到场景。</p>
            </div>
            <button data-test="request-scene-rewrite" type="button" class="rounded border border-cyan-500/40 px-3 py-2 text-sm text-cyan-200 hover:bg-cyan-500/10" @click="requestSceneRewrite">
              生成改写候选
            </button>
          </div>
          <label class="block space-y-1">
            <span class="text-xs text-slate-400">改写要求</span>
            <textarea v-model="rewriteInstruction" rows="2" class="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100" placeholder="例如：更紧张、更适合夜景" />
          </label>
        </section>

        <ReferenceImageGallery title="场景参考图" :slots="sceneReferenceSlotsWithProgress" :loading-slot="referenceLoadingSlot" @regenerate="regenerateSceneReference" @replace-url="replaceSceneReference" />
      </div>

      <template #footer>
        <div class="flex flex-wrap justify-between gap-2">
          <button data-test="delete-scene" type="button" class="rounded border border-red-500/40 px-4 py-2 text-sm text-red-200 hover:bg-red-500/10" @click="deleteDialogOpen = true">
            删除或归档
          </button>
          <button type="button" data-test="save-scene" class="rounded bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-500 disabled:opacity-50" :disabled="saving" @click="saveScene">
            {{ saving ? '保存中...' : '保存场景' }}
          </button>
        </div>
      </template>
    </AssetDetailDrawer>

    <AiRewriteConfirmDialog :open="rewriteDialogOpen" title="确认场景 AI 改写" :before="rewriteBefore" :candidate="rewriteCandidate" @cancel="rewriteDialogOpen = false" @confirm="applySceneRewrite" />

    <DangerConfirmDialog
      :open="deleteDialogOpen"
      title="删除或归档场景"
      message="此操作会根据生产引用情况删除或归档当前场景。"
      :impact="selectedScene ? `目标场景：${selectedScene.name}` : ''"
      confirm-text="确认删除或归档"
      @cancel="deleteDialogOpen = false"
      @confirm="confirmDeleteScene"
    />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import AssetDetailDrawer from '../components/assets/AssetDetailDrawer.vue'
import ReferenceImageGallery from '../components/assets/ReferenceImageGallery.vue'
import AiRewriteConfirmDialog from '../components/assets/AiRewriteConfirmDialog.vue'
import DangerConfirmDialog from '../components/assets/DangerConfirmDialog.vue'
import {
  listScenes,
  createScene,
  updateScene,
  deleteScene,
  autoGenerateScenes,
  aiRewriteScene,
  generateSceneReferences,
} from '../api/scenes.js'
import { listItems } from '../api/referenceData.js'

const SCENE_EDIT_FIELDS = ['name', 'scene_type', 'location_desc', 'lighting', 'mood']

const scenes = ref([])
const loading = ref(true)
const error = ref('')
const drawerError = ref('')
const showCreate = ref(false)
const showAiGen = ref(false)
const typeOptions = ref([])
const lightingOptions = ref([])
const moodOptions = ref([])
const genreOptions = ref([])
const aiGenerating = ref(false)
const aiBatchCreating = ref(false)
const aiResult = ref([])
const selectedScene = ref(null)
const editingScene = reactive({})
const referenceLoadingSlot = ref('')
const deleteDialogOpen = ref(false)
const rewriteDialogOpen = ref(false)
const rewriteCandidate = ref({})
const rewriteInstruction = ref('')
const saving = ref(false)
const referencePollTimer = ref(null)

const form = reactive({ name: '', scene_type: 'indoor', location_desc: '', lighting: '', mood: '' })
const aiForm = reactive({ text: '', genre: 'drama', count: 5 })

const selectedAiCount = computed(() => aiResult.value.filter((s) => s._selected).length)

const sceneReferenceSlots = computed(() => selectedScene.value ? [
  { key: 'reference_wideshot_url', label: '广角', url: selectedScene.value.reference_wideshot_url },
  { key: 'reference_midshot_url', label: '中景', url: selectedScene.value.reference_midshot_url },
  { key: 'reference_aerial_url', label: '俯拍', url: selectedScene.value.reference_aerial_url },
] : [])

const rewriteBefore = computed(() => pickAllowed(editingScene, SCENE_EDIT_FIELDS))

const sceneReferenceSlotsWithProgress = computed(() => sceneReferenceSlots.value.map((slot) => ({
  ...slot,
  progress: referenceProgress(selectedScene.value, slot.key),
})))

// 前端业务函数：协调 referenceProgress 对应的页面流程、接口调用或状态转换。
function referenceProgress(scene, slot) {
  return scene?.meta_json?.reference_generation?.[slot] || null
}

// 前端业务函数：协调 hasActiveReferenceProgress 对应的页面流程、接口调用或状态转换。
function hasActiveReferenceProgress(items) {
  return items.some((scene) => Object.values(scene?.meta_json?.reference_generation || {}).some((progress) => (
    ['pending', 'generating'].includes(progress?.status)
  )))
}

// 前端业务函数：协调 scheduleReferencePoll 对应的页面流程、接口调用或状态转换。
function scheduleReferencePoll() {
  if (referencePollTimer.value) {
    clearTimeout(referencePollTimer.value)
    referencePollTimer.value = null
  }
  if (hasActiveReferenceProgress(scenes.value)) {
    referencePollTimer.value = setTimeout(load, 5000)
  }
}

// 前端业务函数：协调 messageFromError 对应的页面流程、接口调用或状态转换。
function messageFromError(errorValue, fallback) {
  return errorValue?.response?.data?.detail || errorValue?.message || fallback
}

// 前端业务函数：协调 pickAllowed 对应的页面流程、接口调用或状态转换。
function pickAllowed(source, fields) {
  return fields.reduce((payload, field) => {
    payload[field] = source?.[field] ?? ''
    return payload
  }, {})
}

// 前端业务函数：协调 pickCandidateFields 对应的页面流程、接口调用或状态转换。
function pickCandidateFields(candidate, fields) {
  return fields.reduce((payload, field) => {
    if (Object.prototype.hasOwnProperty.call(candidate || {}, field) && candidate[field] !== undefined) {
      payload[field] = candidate[field]
    }
    return payload
  }, {})
}

// 前端业务函数：协调 mergeAllowedDraft 对应的页面流程、接口调用或状态转换。
function mergeAllowedDraft(draft, candidate) {
  return {
    ...pickAllowed(draft, SCENE_EDIT_FIELDS),
    ...pickCandidateFields(candidate, SCENE_EDIT_FIELDS),
  }
}

// 前端业务函数：协调 loadOpts 对应的页面流程、接口调用或状态转换。
async function loadOpts() {
  try {
    const [t, l, m, g] = await Promise.all([
      listItems('scene_type'),
      listItems('scene_lighting'),
      listItems('scene_mood'),
      listItems('series_genre'),
    ])
    if (t.data.ok) {
      typeOptions.value = t.data.items
      form.scene_type = t.data.items[0]?.value || 'indoor'
    }
    if (l.data.ok) lightingOptions.value = l.data.items
    if (m.data.ok) moodOptions.value = m.data.items
    if (g.data.ok) genreOptions.value = g.data.items
  } catch (e) {
    typeOptions.value = []
    lightingOptions.value = []
    moodOptions.value = []
    genreOptions.value = []
  }
}

// 前端业务函数：协调 load 对应的页面流程、接口调用或状态转换。
async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await listScenes()
    scenes.value = data.ok ? data.scenes : []
    if (selectedScene.value) syncSelected(selectedScene.value.id)
    scheduleReferencePoll()
  } catch (e) {
    error.value = messageFromError(e, '加载失败')
  } finally {
    loading.value = false
  }
}

// 前端业务函数：协调 syncSelected 对应的页面流程、接口调用或状态转换。
function syncSelected(id) {
  const fresh = scenes.value.find((s) => s.id === id) || null
  selectedScene.value = fresh
  if (fresh) {
    Object.keys(editingScene).forEach((key) => delete editingScene[key])
    Object.assign(editingScene, { ...fresh })
  }
}

// 前端业务函数：协调 openScene 对应的页面流程、接口调用或状态转换。
function openScene(scene) {
  drawerError.value = ''
  selectedScene.value = scene
  Object.keys(editingScene).forEach((key) => delete editingScene[key])
  Object.assign(editingScene, { ...scene })
}

// 前端业务函数：协调 closeScene 对应的页面流程、接口调用或状态转换。
function closeScene() {
  selectedScene.value = null
  drawerError.value = ''
  deleteDialogOpen.value = false
  rewriteDialogOpen.value = false
}

// 前端业务函数：协调 saveScene 对应的页面流程、接口调用或状态转换。
async function saveScene() {
  if (!selectedScene.value) return
  const id = selectedScene.value.id
  saving.value = true
  drawerError.value = ''
  try {
    await updateScene(id, mergeAllowedDraft(editingScene, {}))
    await load()
    syncSelected(id)
  } catch (e) {
    drawerError.value = messageFromError(e, '保存失败')
  } finally {
    saving.value = false
  }
}

// 前端业务函数：协调 regenerateSceneReference 对应的页面流程、接口调用或状态转换。
async function regenerateSceneReference(slot) {
  if (!selectedScene.value) return
  const id = selectedScene.value.id
  referenceLoadingSlot.value = slot
  drawerError.value = ''
  try {
    await generateSceneReferences(id, { slot })
    await load()
    syncSelected(id)
  } catch (e) {
    drawerError.value = messageFromError(e, '参考图生成失败')
  } finally {
    referenceLoadingSlot.value = ''
  }
}

// 前端业务函数：协调 replaceSceneReference 对应的页面流程、接口调用或状态转换。
async function replaceSceneReference(slot, url) {
  if (!selectedScene.value) return
  const id = selectedScene.value.id
  drawerError.value = ''
  try {
    await updateScene(id, { [slot]: url })
    await load()
    syncSelected(id)
  } catch (e) {
    drawerError.value = messageFromError(e, '参考图链接保存失败')
  }
}

async function requestSceneRewrite() {
  if (!selectedScene.value) return
  drawerError.value = ''
  try {
    const { data } = await aiRewriteScene(selectedScene.value.id, {
      instruction: rewriteInstruction.value,
      asset: mergeAllowedDraft(editingScene, {}),
    })
    rewriteCandidate.value = mergeAllowedDraft(editingScene, data.candidate || data.scene || {})
    rewriteDialogOpen.value = true
  } catch (e) {
    drawerError.value = messageFromError(e, 'AI 改写失败')
  }
}

async function applySceneRewrite(candidate) {
  if (!selectedScene.value) return
  const id = selectedScene.value.id
  drawerError.value = ''
  try {
    await updateScene(id, mergeAllowedDraft(editingScene, candidate))
    rewriteDialogOpen.value = false
    await load()
    syncSelected(id)
  } catch (e) {
    drawerError.value = messageFromError(e, '应用改写失败')
  }
}

async function confirmDeleteScene() {
  if (!selectedScene.value) return
  drawerError.value = ''
  try {
    await deleteScene(selectedScene.value.id)
    closeScene()
    await load()
  } catch (e) {
    drawerError.value = messageFromError(e, '删除或归档失败')
  }
}

async function doCreate() {
  error.value = ''
  try {
    await createScene({ ...form })
    showCreate.value = false
    await load()
  } catch (e) {
    error.value = messageFromError(e, '创建失败')
  }
}

async function doAiGenerate() {
  aiGenerating.value = true
  aiResult.value = []
  error.value = ''
  try {
    const { data } = await autoGenerateScenes(aiForm.text, aiForm.genre, aiForm.count)
    if (!data.ok) throw new Error('生成失败')
    aiResult.value = (data.scenes || []).map((s) => ({ ...s, _selected: true }))
  } catch (e) {
    error.value = messageFromError(e, 'AI 生成失败')
  } finally {
    aiGenerating.value = false
  }
}

// 前端业务函数：协调 doBatchCreate 对应的页面流程、接口调用或状态转换。
async function doBatchCreate() {
  const selected = aiResult.value.filter((s) => s._selected)
  if (!selected.length) return
  aiBatchCreating.value = true
  error.value = ''
  try {
    for (const s of selected) {
      await createScene({
        name: s.name,
        scene_type: s.scene_type,
        location_desc: s.location_desc,
        lighting: s.lighting,
        mood: s.mood,
      })
    }
    showAiGen.value = false
    aiResult.value = []
    await load()
  } catch (e) {
    error.value = messageFromError(e, '批量创建失败')
  } finally {
    aiBatchCreating.value = false
  }
}

// 前端业务函数：协调 sceneTypeLabel 对应的页面流程、接口调用或状态转换。
function sceneTypeLabel(value) {
  return typeOptions.value.find((item) => item.value === value)?.label || value || '未设置'
}

function lightingLabel(value) {
  return lightingOptions.value.find((item) => item.value === value)?.label || value || ''
}

// 前端业务函数：协调 moodLabel 对应的页面流程、接口调用或状态转换。
function moodLabel(value) {
  return moodOptions.value.find((item) => item.value === value)?.label || value || ''
}

onMounted(async () => {
  await loadOpts()
  await load()
})

onBeforeUnmount(() => {
  if (referencePollTimer.value) clearTimeout(referencePollTimer.value)
})
</script>
