<!-- 管理端业务页面：承载 CharactersPage 页面流程，协调接口数据、用户操作和业务状态展示。 -->
<template>
  <div class="p-6">
    <div class="mb-6 flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 class="text-2xl font-bold text-slate-100">角色资产库</h1>
        <p class="mt-1 text-sm text-slate-400">管理剧中角色，维护设定、外观和参考图。</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <button type="button" class="rounded-lg bg-cyan-600 px-4 py-2 text-sm text-white transition hover:bg-cyan-500 disabled:opacity-50" @click="showAiGen = true">
          AI 批量生成
        </button>
        <button type="button" class="rounded-lg bg-sky-600 px-4 py-2 text-sm text-white transition hover:bg-sky-500" @click="showCreate = true">
          新建角色
        </button>
      </div>
    </div>

    <div v-if="loading" class="py-12 text-center text-slate-400">加载中...</div>
    <div v-else-if="error" class="py-12 text-center text-red-400">{{ error }}</div>
    <div v-else-if="characters.length === 0" class="py-12 text-center text-slate-500">
      暂无角色
      <div class="mt-1 text-xs text-slate-600">创建角色后可在系列详情中关联到具体剧集。</div>
    </div>

    <div v-else class="grid min-w-0 gap-4 md:grid-cols-2 xl:grid-cols-4">
      <button
        v-for="c in characters"
        :key="c.id"
        type="button"
        :data-test="`character-card-${c.id}`"
        class="min-w-0 rounded-lg border border-slate-800 bg-slate-900/60 p-4 text-left transition hover:border-sky-500/50 hover:bg-slate-900"
        @click="openCharacter(c)"
      >
        <div class="mx-auto mb-3 flex h-20 w-20 items-center justify-center rounded-full bg-slate-800 text-2xl text-slate-100">
          {{ c.name?.[0] || '?' }}
        </div>
        <div class="text-center">
          <h3 class="font-semibold text-slate-100">{{ c.name }}</h3>
          <span class="mt-2 inline-block rounded px-2 py-1 text-xs" :class="roleClass(c.role_type)">
            {{ roleLabel(c.role_type) }}
          </span>
          <div class="mt-2 text-xs text-slate-500">{{ genderLabel(c.gender) }}</div>
          <div class="mt-2 text-xs" :class="c.avatar_front_url ? 'text-emerald-400' : 'text-amber-400'">
            {{ c.avatar_front_url ? '参考图已配置' : '参考图待生成' }}
          </div>
        </div>
      </button>
    </div>

    <div v-if="showAiGen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" @click.self="showAiGen = false">
      <div class="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-lg border border-slate-700 bg-slate-950 p-6 shadow-2xl">
        <h2 class="mb-4 text-lg font-semibold text-slate-100">AI 批量生成角色</h2>
        <p class="mb-4 text-xs text-slate-500">输入故事概要，AI 会生成可勾选的角色档案。</p>
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

        <div v-if="aiGenerating" class="py-8 text-center text-sm text-slate-400">AI 正在生成角色...</div>
        <div v-else-if="aiResult.length" class="mt-4 max-h-[300px] space-y-2 overflow-y-auto">
          <p class="text-xs text-slate-500">AI 生成了 {{ aiResult.length }} 个角色，请勾选需要创建的项目。</p>
          <label v-for="(c, i) in aiResult" :key="i" class="flex items-start gap-3 rounded-lg border border-slate-800 bg-slate-900/70 p-3">
            <input v-model="c._selected" type="checkbox" class="mt-1">
            <span class="min-w-0 flex-1">
              <span class="block font-semibold text-slate-100">{{ c.name }}</span>
              <span class="mt-1 block text-xs text-slate-400">性格：{{ c.personality || '-' }}</span>
              <span class="mt-1 block text-xs text-slate-500">外观：{{ c.appearance_desc || '-' }}</span>
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
        <h2 class="mb-4 text-lg font-semibold text-slate-100">新建角色</h2>
        <div class="space-y-3">
          <label class="block space-y-1">
            <span class="text-xs text-slate-400">角色名称</span>
            <input v-model="form.name" class="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100">
          </label>
          <div class="flex gap-3">
            <label class="block flex-1 space-y-1">
              <span class="text-xs text-slate-400">角色类型</span>
              <select v-model="form.role_type" class="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100">
                <option v-for="r in roleOptions" :key="r.value" :value="r.value">{{ r.label }}</option>
              </select>
            </label>
            <label class="block w-28 space-y-1">
              <span class="text-xs text-slate-400">性别</span>
              <select v-model="form.gender" class="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100">
                <option value="male">男</option>
                <option value="female">女</option>
              </select>
            </label>
          </div>
          <label class="block space-y-1">
            <span class="text-xs text-slate-400">外观描述</span>
            <textarea v-model="form.appearance_desc" rows="2" class="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100" />
          </label>
          <label class="block space-y-1">
            <span class="text-xs text-slate-400">服装描述</span>
            <textarea v-model="form.outfit_desc" rows="2" class="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100" />
          </label>
          <label class="block space-y-1">
            <span class="text-xs text-slate-400">性格描述</span>
            <textarea v-model="form.personality" rows="2" class="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-100" />
          </label>
        </div>
        <div class="mt-6 flex justify-end gap-3">
          <button type="button" class="rounded-lg border border-slate-700 px-4 py-2 text-slate-300 hover:bg-slate-800" @click="showCreate = false">取消</button>
          <button type="button" class="rounded-lg bg-sky-600 px-4 py-2 text-white hover:bg-sky-500" @click="doCreate">创建</button>
        </div>
      </div>
    </div>

    <AssetDetailDrawer :open="Boolean(selectedCharacter)" title="角色详情" :subtitle="selectedCharacter?.name || ''" @close="closeCharacter">
      <div v-if="selectedCharacter" class="space-y-6">
        <div v-if="drawerError" data-test="character-drawer-error" class="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">
          {{ drawerError }}
        </div>

        <section class="space-y-3">
          <label class="block space-y-1">
            <span class="text-xs font-medium text-slate-300">角色名称</span>
            <input v-model="editingCharacter.name" data-test="character-name-input" class="w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100">
          </label>
          <div class="grid gap-3 sm:grid-cols-2">
            <label class="block space-y-1">
              <span class="text-xs font-medium text-slate-300">角色类型</span>
              <select v-model="editingCharacter.role_type" class="w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100">
                <option v-for="r in roleOptions" :key="r.value" :value="r.value">{{ r.label }}</option>
              </select>
            </label>
            <label class="block space-y-1">
              <span class="text-xs font-medium text-slate-300">性别</span>
              <select v-model="editingCharacter.gender" class="w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100">
                <option value="male">男</option>
                <option value="female">女</option>
              </select>
            </label>
          </div>
          <label class="block space-y-1">
            <span class="text-xs font-medium text-slate-300">性格</span>
            <textarea v-model="editingCharacter.personality" rows="3" class="w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100" />
          </label>
          <label class="block space-y-1">
            <span class="text-xs font-medium text-slate-300">外观描述</span>
            <textarea v-model="editingCharacter.appearance_desc" rows="3" class="w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100" />
          </label>
          <label class="block space-y-1">
            <span class="text-xs font-medium text-slate-300">服装描述</span>
            <textarea v-model="editingCharacter.outfit_desc" rows="3" class="w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100" />
          </label>
        </section>

        <section class="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
          <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 class="text-sm font-semibold text-slate-100">AI 改写</h3>
              <p class="mt-1 text-xs text-slate-500">生成候选内容，确认后才会应用到角色。</p>
            </div>
            <button data-test="request-character-rewrite" type="button" class="rounded border border-cyan-500/40 px-3 py-2 text-sm text-cyan-200 hover:bg-cyan-500/10" @click="requestCharacterRewrite">
              生成改写候选
            </button>
          </div>
          <label class="block space-y-1">
            <span class="text-xs text-slate-400">改写要求</span>
            <textarea v-model="rewriteInstruction" rows="2" class="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100" placeholder="例如：更冷静、更适合悬疑短剧" />
          </label>
        </section>

        <ReferenceImageGallery title="角色参考图" :slots="characterReferenceSlotsWithProgress" :loading-slot="referenceLoadingSlot" @regenerate="regenerateCharacterReference" @replace-url="replaceCharacterReference" />
      </div>

      <template #footer>
        <div class="flex flex-wrap justify-between gap-2">
          <button data-test="delete-character" type="button" class="rounded border border-red-500/40 px-4 py-2 text-sm text-red-200 hover:bg-red-500/10" @click="deleteDialogOpen = true">
            删除或归档
          </button>
          <button type="button" data-test="save-character" class="rounded bg-emerald-600 px-4 py-2 text-sm text-white hover:bg-emerald-500 disabled:opacity-50" :disabled="saving" @click="saveCharacter">
            {{ saving ? '保存中...' : '保存角色' }}
          </button>
        </div>
      </template>
    </AssetDetailDrawer>

    <AiRewriteConfirmDialog :open="rewriteDialogOpen" title="确认角色 AI 改写" :before="rewriteBefore" :candidate="rewriteCandidate" @cancel="rewriteDialogOpen = false" @confirm="applyCharacterRewrite" />

    <DangerConfirmDialog
      :open="deleteDialogOpen"
      title="删除或归档角色"
      message="此操作会根据生产引用情况删除或归档当前角色。"
      :impact="selectedCharacter ? `目标角色：${selectedCharacter.name}` : ''"
      confirm-text="确认删除或归档"
      @cancel="deleteDialogOpen = false"
      @confirm="confirmDeleteCharacter"
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
  listCharacters,
  createCharacter,
  updateCharacter,
  deleteCharacter,
  autoGenerateCharacters,
  aiRewriteCharacter,
  generateCharacterReferences,
} from '../api/characters.js'
import { listItems } from '../api/referenceData.js'

const CHARACTER_EDIT_FIELDS = ['name', 'role_type', 'gender', 'personality', 'appearance_desc', 'outfit_desc']

const characters = ref([])
const loading = ref(true)
const error = ref('')
const drawerError = ref('')
const showCreate = ref(false)
const showAiGen = ref(false)
const roleOptions = ref([])
const genreOptions = ref([])
const aiGenerating = ref(false)
const aiBatchCreating = ref(false)
const aiResult = ref([])
const selectedCharacter = ref(null)
const editingCharacter = reactive({})
const referenceLoadingSlot = ref('')
const deleteDialogOpen = ref(false)
const rewriteDialogOpen = ref(false)
const rewriteCandidate = ref({})
const rewriteInstruction = ref('')
const saving = ref(false)
const referencePollTimer = ref(null)

const form = reactive({ name: '', role_type: 'protagonist', gender: 'male', appearance_desc: '', outfit_desc: '', personality: '' })
const aiForm = reactive({ text: '', genre: 'drama', count: 4 })

const selectedAiCount = computed(() => aiResult.value.filter((c) => c._selected).length)

const characterReferenceSlots = computed(() => selectedCharacter.value ? [
  { key: 'avatar_front_url', label: '正面', url: selectedCharacter.value.avatar_front_url },
  { key: 'avatar_side_url', label: '侧面', url: selectedCharacter.value.avatar_side_url },
  { key: 'avatar_threequarter_url', label: '三分之四', url: selectedCharacter.value.avatar_threequarter_url },
  { key: 'avatar_fullbody_url', label: '全身', url: selectedCharacter.value.avatar_fullbody_url },
] : [])

const rewriteBefore = computed(() => pickAllowed(editingCharacter, CHARACTER_EDIT_FIELDS))

const characterReferenceSlotsWithProgress = computed(() => characterReferenceSlots.value.map((slot) => ({
  ...slot,
  progress: referenceProgress(selectedCharacter.value, slot.key),
})))

// 前端业务函数：协调 referenceProgress 对应的页面流程、接口调用或状态转换。
// 入参：character、slot 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 referenceProgress 对应业务流程的处理结果。
function referenceProgress(character, slot) {
  return character?.meta_json?.reference_generation?.[slot] || null
}

// 前端业务函数：协调 hasActiveReferenceProgress 对应的页面流程、接口调用或状态转换。
// 入参：items 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 hasActiveReferenceProgress 对应业务流程的处理结果。
function hasActiveReferenceProgress(items) {
  return items.some((character) => Object.values(character?.meta_json?.reference_generation || {}).some((progress) => (
    ['pending', 'generating'].includes(progress?.status)
  )))
}

// 前端业务函数：协调 scheduleReferencePoll 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 scheduleReferencePoll 对应业务流程的处理结果。
function scheduleReferencePoll() {
  if (referencePollTimer.value) {
    clearTimeout(referencePollTimer.value)
    referencePollTimer.value = null
  }
  if (hasActiveReferenceProgress(characters.value)) {
    referencePollTimer.value = setTimeout(load, 5000)
  }
}

// 前端业务函数：协调 messageFromError 对应的页面流程、接口调用或状态转换。
// 入参：errorValue、fallback 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 messageFromError 对应业务流程的处理结果。
function messageFromError(errorValue, fallback) {
  return errorValue?.response?.data?.detail || errorValue?.message || fallback
}

// 前端业务函数：协调 pickAllowed 对应的页面流程、接口调用或状态转换。
// 入参：source、fields 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 pickAllowed 对应业务流程的处理结果。
function pickAllowed(source, fields) {
  return fields.reduce((payload, field) => {
    payload[field] = source?.[field] ?? ''
    return payload
  }, {})
}

// 前端业务函数：协调 pickCandidateFields 对应的页面流程、接口调用或状态转换。
// 入参：candidate、fields 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 pickCandidateFields 对应业务流程的处理结果。
function pickCandidateFields(candidate, fields) {
  return fields.reduce((payload, field) => {
    if (Object.prototype.hasOwnProperty.call(candidate || {}, field) && candidate[field] !== undefined) {
      payload[field] = candidate[field]
    }
    return payload
  }, {})
}

// 前端业务函数：协调 mergeAllowedDraft 对应的页面流程、接口调用或状态转换。
// 入参：draft、candidate 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 mergeAllowedDraft 对应业务流程的处理结果。
function mergeAllowedDraft(draft, candidate) {
  return {
    ...pickAllowed(draft, CHARACTER_EDIT_FIELDS),
    ...pickCandidateFields(candidate, CHARACTER_EDIT_FIELDS),
  }
}

// 前端业务函数：协调 loadRoles 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 loadRoles 对应业务流程的处理结果。
async function loadRoles() {
  try {
    const { data } = await listItems('character_role')
    if (data.ok) {
      roleOptions.value = data.items
      if (data.items.length) form.role_type = data.items[0].value
    }
  } catch (e) {
    roleOptions.value = []
  }
}

// 前端业务函数：协调 loadGenres 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 loadGenres 对应业务流程的处理结果。
async function loadGenres() {
  try {
    const { data } = await listItems('series_genre')
    if (data.ok) genreOptions.value = data.items
  } catch (e) {
    genreOptions.value = []
  }
}

// 前端业务函数：协调 load 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 load 对应业务流程的处理结果。
async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await listCharacters()
    characters.value = data.ok ? data.characters : []
    if (selectedCharacter.value) syncSelected(selectedCharacter.value.id)
    scheduleReferencePoll()
  } catch (e) {
    error.value = messageFromError(e, '加载失败')
  } finally {
    loading.value = false
  }
}

// 前端业务函数：协调 syncSelected 对应的页面流程、接口调用或状态转换。
// 入参：id 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 syncSelected 对应业务流程的处理结果。
function syncSelected(id) {
  const fresh = characters.value.find((c) => c.id === id) || null
  selectedCharacter.value = fresh
  if (fresh) {
    Object.keys(editingCharacter).forEach((key) => delete editingCharacter[key])
    Object.assign(editingCharacter, { ...fresh })
  }
}

// 前端业务函数：协调 openCharacter 对应的页面流程、接口调用或状态转换。
// 入参：character 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 openCharacter 对应业务流程的处理结果。
function openCharacter(character) {
  drawerError.value = ''
  selectedCharacter.value = character
  Object.keys(editingCharacter).forEach((key) => delete editingCharacter[key])
  Object.assign(editingCharacter, { ...character })
}

// 前端业务函数：协调 closeCharacter 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 closeCharacter 对应业务流程的处理结果。
function closeCharacter() {
  selectedCharacter.value = null
  drawerError.value = ''
  deleteDialogOpen.value = false
  rewriteDialogOpen.value = false
}

// 前端业务函数：协调 saveCharacter 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 saveCharacter 对应业务流程的处理结果。
async function saveCharacter() {
  if (!selectedCharacter.value) return
  const id = selectedCharacter.value.id
  saving.value = true
  drawerError.value = ''
  try {
    await updateCharacter(id, mergeAllowedDraft(editingCharacter, {}))
    await load()
    syncSelected(id)
  } catch (e) {
    drawerError.value = messageFromError(e, '保存失败')
  } finally {
    saving.value = false
  }
}

// 前端业务函数：协调 regenerateCharacterReference 对应的页面流程、接口调用或状态转换。
// 入参：slot 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 regenerateCharacterReference 对应业务流程的处理结果。
async function regenerateCharacterReference(slot) {
  if (!selectedCharacter.value) return
  const id = selectedCharacter.value.id
  referenceLoadingSlot.value = slot
  drawerError.value = ''
  try {
    await generateCharacterReferences(id, { slot })
    await load()
    syncSelected(id)
  } catch (e) {
    drawerError.value = messageFromError(e, '参考图生成失败')
  } finally {
    referenceLoadingSlot.value = ''
  }
}

// 前端业务函数：协调 replaceCharacterReference 对应的页面流程、接口调用或状态转换。
// 入参：slot、url 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 replaceCharacterReference 对应业务流程的处理结果。
async function replaceCharacterReference(slot, url) {
  if (!selectedCharacter.value) return
  const id = selectedCharacter.value.id
  drawerError.value = ''
  try {
    await updateCharacter(id, { [slot]: url })
    await load()
    syncSelected(id)
  } catch (e) {
    drawerError.value = messageFromError(e, '参考图链接保存失败')
  }
}

// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 requestCharacterRewrite 对应业务流程的处理结果。
async function requestCharacterRewrite() {
  if (!selectedCharacter.value) return
  drawerError.value = ''
  try {
    const { data } = await aiRewriteCharacter(selectedCharacter.value.id, {
      instruction: rewriteInstruction.value,
      asset: mergeAllowedDraft(editingCharacter, {}),
    })
    rewriteCandidate.value = mergeAllowedDraft(editingCharacter, data.candidate || data.character || {})
    rewriteDialogOpen.value = true
  } catch (e) {
    drawerError.value = messageFromError(e, 'AI 改写失败')
  }
}

// 入参：candidate 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 applyCharacterRewrite 对应业务流程的处理结果。
async function applyCharacterRewrite(candidate) {
  if (!selectedCharacter.value) return
  const id = selectedCharacter.value.id
  drawerError.value = ''
  try {
    await updateCharacter(id, mergeAllowedDraft(editingCharacter, candidate))
    rewriteDialogOpen.value = false
    await load()
    syncSelected(id)
  } catch (e) {
    drawerError.value = messageFromError(e, '应用改写失败')
  }
}

// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 confirmDeleteCharacter 对应业务流程的处理结果。
async function confirmDeleteCharacter() {
  if (!selectedCharacter.value) return
  drawerError.value = ''
  try {
    await deleteCharacter(selectedCharacter.value.id)
    closeCharacter()
    await load()
  } catch (e) {
    drawerError.value = messageFromError(e, '删除或归档失败')
  }
}

// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 doCreate 对应业务流程的处理结果。
async function doCreate() {
  error.value = ''
  try {
    await createCharacter({ ...form })
    showCreate.value = false
    await load()
  } catch (e) {
    error.value = messageFromError(e, '创建失败')
  }
}

// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 doAiGenerate 对应业务流程的处理结果。
async function doAiGenerate() {
  aiGenerating.value = true
  aiResult.value = []
  error.value = ''
  try {
    const { data } = await autoGenerateCharacters(aiForm.text, aiForm.genre, aiForm.count)
    if (!data.ok) throw new Error('生成失败')
    aiResult.value = (data.characters || []).map((c) => ({ ...c, _selected: true }))
  } catch (e) {
    error.value = messageFromError(e, 'AI 生成失败')
  } finally {
    aiGenerating.value = false
  }
}

// 前端业务函数：协调 doBatchCreate 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 doBatchCreate 对应业务流程的处理结果。
async function doBatchCreate() {
  const selected = aiResult.value.filter((c) => c._selected)
  if (!selected.length) return
  aiBatchCreating.value = true
  error.value = ''
  try {
    for (const c of selected) {
      await createCharacter({
        name: c.name,
        role_type: c.role_type,
        gender: c.gender,
        age_range: c.age_range,
        personality: c.personality,
        appearance_desc: c.appearance_desc,
        outfit_desc: c.outfit_desc,
        default_voice_id: c.default_voice_id,
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

// 前端业务函数：协调 roleClass 对应的页面流程、接口调用或状态转换。
// 入参：role 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 roleClass 对应业务流程的处理结果。
function roleClass(role) {
  return {
    protagonist: 'bg-sky-900/40 text-sky-300',
    antagonist: 'bg-red-900/40 text-red-300',
    supporting: 'bg-emerald-900/40 text-emerald-300',
    cameo: 'bg-slate-800 text-slate-400',
  }[role] || 'bg-slate-800 text-slate-400'
}

// 前端业务函数：协调 roleLabel 对应的页面流程、接口调用或状态转换。
// 入参：value 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 roleLabel 对应业务流程的处理结果。
function roleLabel(value) {
  return roleOptions.value.find((item) => item.value === value)?.label || value || '未设置'
}

// 入参：value 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 genderLabel 对应业务流程的处理结果。
function genderLabel(value) {
  return value === 'male' ? '男' : value === 'female' ? '女' : value || '未设置'
}

onMounted(async () => {
  await Promise.all([loadRoles(), loadGenres()])
  await load()
})

onBeforeUnmount(() => {
  if (referencePollTimer.value) clearTimeout(referencePollTimer.value)
})
</script>
