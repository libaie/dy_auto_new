<script setup>
import { ref, reactive, onMounted, watch, computed } from 'vue'
import {
  Dialog,
  DialogPanel,
  DialogTitle,
  TransitionRoot,
  TransitionChild,
  Switch,
  SwitchGroup,
  SwitchLabel,
} from '@headlessui/vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import EmptyState from '../components/EmptyState.vue'
import StrategyCard from '../components/StrategyCard.vue'
import {
  listSelectors,
  createSelector,
  updateSelector,
  deleteSelector,
  toggleSelector,
  generateRegex,
  generateCleanPrompt,
} from '../api/selectors.js'
import { useToastStore } from '../stores/toast.js'

// 动作名称中文说明
const actionDescriptions = {
  back_btn: '返回按钮',
  open_app: '打开抖音 App',
  video_comment_btn: '视频评论入口按钮（点击打开评论面板）',
  video_comment_input: '视频评论输入框（需先点击弹出键盘）',
  search_tab: '搜索标签页入口',
  search_input: '搜索输入框',
  search_button: '搜索按钮',
  search_suggestion: '搜索建议词',
  search_suggestion_list: '搜索联想词列表容器',
  search_video_tab: '搜索结果-视频标签页',
  search_video_list: '搜索结果-视频列表容器',
  video_tab: '视频标签页',
  video_author_avatar: '视频作者头像（点击进入主页）',
  sort_button: '排序按钮',
  sort_latest: '最新排序选项',
  sort_most_liked: '最多点赞排序选项',
  sort_default: '默认排序选项',
  like_button: '点赞按钮',
  follow_button: '关注按钮',
  comment_input: '评论输入框',
  comment_submit: '评论提交按钮',
  comment_reply_button: '评论回复按钮',
  comment_reply_input: '评论回复输入框',
  comment_reply_submit: '评论回复提交按钮',
  comment_list: '评论列表容器',
  comment_text: '评论内容文本',
  comment_author: '评论作者昵称',
  comment_time: '评论发布时间',
  comment_like_count: '评论点赞数',
  comment_author_avatar: '评论作者头像',
  message_button: '私信按钮',
  dm_input: '私信输入框',
  dm_send: '私信发送按钮',
  profile_more: '个人主页更多菜单',
}

// Tooltip content for each field
const tooltips = {
  action_name: {
    title: '动作名称（必填）',
    desc: '选择器的唯一标识符，对应设备端要执行的操作名称。命名规则：小写字母+下划线，例如 like_video、comment_video、search_keyword。设备端任务执行时会根据此名称查找对应的选择器。',
    examples: '常用值：like_video（点赞）、comment_video（评论）、search_keyword（搜索）、follow_user（关注）、reply_comment（回复评论）、send_dm（私信）',
  },
  platform_version: {
    title: '平台版本（可选）',
    desc: '抖音 App 的版本号，用于多版本适配。不同版本的抖音界面布局可能不同，可以为同一动作创建多个选择器，每个针对不同版本。留空表示适用于所有版本。',
    examples: '例如：29.0.0、28.5.1。设备端会优先匹配精确版本，找不到则使用无版本号的通用选择器',
  },
  strategies: {
    title: '选择策略数组（必填）',
    desc: 'JSON 数组，定义如何在屏幕上定位目标 UI 元素。每个策略是一种查找方式，系统按 priority 顺序依次尝试，直到找到元素为止。支持单条件匹配、多条件 AND/OR 组合匹配。',
    types: [
      { type: 'text', value: '通过文本内容查找', fields: 'value: 要匹配的文本，match_mode: 匹配模式（exact 精确/contains 包含）' },
      { type: 'id', value: '通过资源 ID 查找', fields: 'value: Android 资源 ID，match_mode: 匹配模式（exact/contains）' },
      { type: 'desc', value: '通过内容描述查找', fields: 'value: contentDescription 属性值，match_mode: 匹配模式（exact/contains）' },
      { type: 'className', value: '通过类名查找', fields: 'value: Android 控件类名，match_mode: 匹配模式（exact/contains）' },
      { type: 'package', value: '通过包名查找', fields: 'value: 应用包名，如 com.ss.android.ugc.aweme' },
      { type: 'coordinate', value: '通过固定坐标点击', fields: 'x_percent: X 百分比(0-100)，y_percent: Y 百分比(0-100)' },
      { type: 'image', value: '通过图片模板匹配', fields: 'template: 模板图片路径，threshold: 匹配阈值(0-1，默认0.8)' },
    ],
    commonFields: '通用字段：type、value、priority（数字越小越优先）、match_mode（exact/contains，默认 exact）。多条件模式：conditions（条件数组）+ logic（and/or），每个条件含 type/value/match_mode。',
  },
}

// --- Data state ---
const selectors = ref([])
const loading = ref(false)
const includeDisabled = ref(false)

// --- Version filter ---
const versionFilter = ref('default')

const availableVersions = computed(() => {
  const versions = new Set()
  for (const s of selectors.value) {
    versions.add(s.platform_version || 'default')
  }
  return Array.from(versions).sort()
})

// --- Category filter ---
const categoryFilter = ref('all')
const categoryTabs = [
  { key: 'all', label: '全部' },
  { key: 'search', label: '搜索相关' },
  { key: 'comment', label: '评论相关' },
  { key: 'dm', label: '私信相关' },
  { key: 'video', label: '视频相关' },
  { key: 'sort', label: '排序相关' },
  { key: 'system', label: '系统相关' },
  { key: 'collect', label: '采集相关' },
  { key: '', label: '未分类' },
]

const categoryOptions = [
  { value: '', label: '未分类' },
  { value: 'search', label: '搜索相关' },
  { value: 'comment', label: '评论相关' },
  { value: 'dm', label: '私信相关' },
  { value: 'video', label: '视频相关' },
  { value: 'sort', label: '排序相关' },
  { value: 'system', label: '系统相关' },
  { value: 'collect', label: '采集相关' },
]

function getCategoryLabel(cat) {
  const opt = categoryOptions.find(o => o.value === cat)
  return opt ? opt.label : '未分类'
}

const categoryColorMap = {
  search: 'bg-blue-500/15 text-blue-300 border-blue-500/25',
  comment: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/25',
  dm: 'bg-pink-500/15 text-pink-300 border-pink-500/25',
  video: 'bg-amber-500/15 text-amber-300 border-amber-500/25',
  sort: 'bg-violet-500/15 text-violet-300 border-violet-500/25',
  system: 'bg-slate-500/15 text-slate-300 border-slate-500/25',
  collect: 'bg-orange-500/15 text-orange-300 border-orange-500/25',
}

function getCategoryClass(cat) {
  return categoryColorMap[cat] || 'bg-cyan-500/15 text-cyan-300 border-cyan-500/25'
}

function _matchVersion(s) {
  return (s.platform_version || 'default')
}

const filteredSelectors = computed(() => {
  let list = selectors.value
  if (versionFilter.value !== 'all') {
    list = list.filter(s => _matchVersion(s) === versionFilter.value)
  }
  if (categoryFilter.value !== 'all') {
    list = list.filter(s => (s.category || '') === categoryFilter.value)
  }
  return list
})

const categoryCounts = computed(() => {
  let base = versionFilter.value === 'all'
    ? selectors.value
    : selectors.value.filter(s => _matchVersion(s) === versionFilter.value)
  const counts = { all: base.length }
  for (const s of base) {
    const cat = s.category || ''
    counts[cat] = (counts[cat] || 0) + 1
  }
  return counts
})

// --- Form / Dialog state ---
const showFormDialog = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const formError = ref(null)

const defaultForm = {
  action_name: '',
  description: '',
  platform_version: '',
  strategies: '[]',
  category: '',
}
// --- AI generation state ---
const generatingRegex = ref(false)
const generatingPrompt = ref(false)
const regexAiPrompt = ref('')
const cleanAiPrompt = ref('')

async function generateRegexAI() {
  if (!regexAiPrompt.value.trim()) {
    formError.value = '请输入正则需求描述'
    return
  }
  generatingRegex.value = true
  try {
    const res = await generateRegex(regexAiPrompt.value.trim())
    form.clean_pattern = res.data.regex || res.data.pattern || ''
  } catch (e) {
    formError.value = '正则生成失败: ' + (e.response?.data?.detail || e.message)
  } finally {
    generatingRegex.value = false
  }
}

async function generateCleanPromptAI() {
  if (!cleanAiPrompt.value.trim()) {
    formError.value = '请输入清洗需求描述'
    return
  }
  generatingPrompt.value = true
  try {
    const res = await generateCleanPrompt(cleanAiPrompt.value.trim())
    form.clean_prompt = res.data.prompt || ''
  } catch (e) {
    formError.value = '提示词生成失败: ' + (e.response?.data?.detail || e.message)
  } finally {
    generatingPrompt.value = false
  }
}

const form = reactive({ ...defaultForm })

// --- Strategy card builder state ---
const editMode = ref('form') // 'form' | 'json'
const strategyList = ref([])

function syncStrategiesToList() {
  try {
    strategyList.value = JSON.parse(form.strategies || '[]')
  } catch {
    strategyList.value = []
  }
}

function syncListToStrategies() {
  form.strategies = JSON.stringify(strategyList.value, null, 2)
}

function addStrategy() {
  strategyList.value.push({ type: 'text', value: '', priority: strategyList.value.length + 1 })
  syncListToStrategies()
}

function updateStrategy(index, newStrategy) {
  strategyList.value[index] = newStrategy
  syncListToStrategies()
}

function deleteStrategy(index) {
  strategyList.value.splice(index, 1)
  // Re-index priorities
  strategyList.value.forEach((s, i) => { s.priority = i + 1 })
  syncListToStrategies()
}

function moveStrategy(index, direction) {
  const target = index + direction
  if (target < 0 || target >= strategyList.value.length) return
  const tmp = strategyList.value[index]
  strategyList.value[index] = strategyList.value[target]
  strategyList.value[target] = tmp
  // Re-index priorities
  strategyList.value.forEach((s, i) => { s.priority = i + 1 })
  syncListToStrategies()
}

// --- Delete confirmation state ---
const showDeleteDialog = ref(false)
const deletingSelector = ref(null)
const deleting = ref(false)

// --- Page-level error ---
const pageError = ref(null)
const toast = useToastStore()

// --- Fetch selectors ---
async function fetchSelectors() {
  loading.value = true
  try {
    const res = await listSelectors(includeDisabled.value)
    selectors.value = res.data.selectors || []
  } catch (e) {
    toast.error('加载选择器列表失败')
    selectors.value = []
  } finally {
    loading.value = false
  }
}

// Re-fetch when includeDisabled changes
watch(includeDisabled, () => {
  fetchSelectors()
})

// --- Format strategy summary ---
function formatStrategies(strategies) {
  if (!strategies || strategies.length === 0) return '无策略'
  const parts = strategies.map((s) => {
    if (s.conditions && s.conditions.length > 0) {
      const logic = s.logic === 'or' ? ' OR ' : ' AND '
      const condStrs = s.conditions.map(c => `${c.type}:${(c.value || '').slice(0, 15)}`)
      return `[${condStrs.join(logic)}]`
    }
    const val = s.value && s.value.length > 20 ? s.value.slice(0, 20) + '...' : s.value
    const mode = s.match_mode === 'contains' ? '~' : ''
    return `${mode}${s.type}:${val}`
  })
  return `${strategies.length} 个策略: ${parts.join(', ')}`
}

// --- Open create dialog ---
function openCreateDialog() {
  isEditing.value = false
  form.action_name = ''
  form.description = ''
  form.platform_version = ''
  form.strategies = '[]'
  form.category = ''
  form.purpose = 'locate'
  form.extract_field = 'text'
  form.clean_mode = 'raw'
  form.clean_pattern = ''
  form.clean_prompt = ''
  regexAiPrompt.value = ''
  cleanAiPrompt.value = ''
  editMode.value = 'form'
  strategyList.value = []
  formError.value = null
  showFormDialog.value = true
}

// --- Open edit dialog ---
function openEditDialog(sel) {
  isEditing.value = true
  form.action_name = sel.action_name
  form.description = sel.description || ''
  form.platform_version = sel.platform_version || ''
  form.strategies = JSON.stringify(sel.strategies || [], null, 2)
  form.category = sel.category || ''
  form.purpose = sel.purpose || 'locate'
  form.extract_field = sel.extract_field || 'text'
  form.clean_mode = sel.clean_mode || 'raw'
  form.clean_pattern = sel.clean_pattern || ''
  form.clean_prompt = sel.clean_prompt || ''
  editMode.value = 'form'
  syncStrategiesToList()
  formError.value = null
  showFormDialog.value = true
}

// --- Save (create or update) ---
async function handleSave() {
  if (!form.action_name.trim()) {
    formError.value = 'action_name 不能为空'
    return
  }

  let parsedStrategies
  try {
    parsedStrategies = JSON.parse(form.strategies)
    if (!Array.isArray(parsedStrategies)) {
      formError.value = 'strategies 必须是 JSON 数组'
      return
    }
  } catch {
    formError.value = 'strategies JSON 格式不正确'
    return
  }

  saving.value = true
  formError.value = null

  const payload = {
    strategies: parsedStrategies,
    platform_version: form.platform_version.trim() || undefined,
    description: form.description.trim() || '',
    category: form.category || '',
    purpose: form.purpose || 'locate',
    extract_field: form.purpose === 'extract' ? (form.extract_field || 'text') : undefined,
    clean_mode: form.purpose === 'extract' ? (form.clean_mode || 'raw') : undefined,
    clean_pattern: form.purpose === 'extract' && form.clean_mode === 'regex' ? (form.clean_pattern || undefined) : undefined,
    clean_prompt: form.purpose === 'extract' && form.clean_mode === 'ai' ? (form.clean_prompt || undefined) : undefined,
  }

  try {
    if (isEditing.value) {
      await updateSelector(form.action_name, payload)
    } else {
      payload.action_name = form.action_name.trim()
      await createSelector(payload)
    }
    showFormDialog.value = false
    fetchSelectors()
  } catch (e) {
    formError.value =
      e.response?.data?.message ||
      e.response?.data?.detail ||
      '保存失败，请重试'
  } finally {
    saving.value = false
  }
}

// --- Delete ---
function openDeleteDialog(sel) {
  deletingSelector.value = sel
  showDeleteDialog.value = true
}

async function handleDelete() {
  if (!deletingSelector.value) return
  deleting.value = true
  try {
    await deleteSelector(deletingSelector.value.action_name)
    showDeleteDialog.value = false
    deletingSelector.value = null
    fetchSelectors()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '删除失败，请重试'
  } finally {
    deleting.value = false
  }
}

// --- Toggle enabled ---
async function handleToggle(sel, newValue) {
  const previous = sel.enabled
  sel.enabled = newValue
  try {
    await toggleSelector(sel.action_name, newValue)
  } catch (e) {
    sel.enabled = previous
    pageError.value = e.response?.data?.detail || '切换失败，请重试'
  }
}

// --- Init ---
onMounted(fetchSelectors)
</script>

<template>
  <div>
    <!-- Page error banner -->
    <div v-if="pageError" class="mb-4 glass-card border-red-500/30 text-red-400 px-4 py-3 rounded-xl flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-400 hover:text-red-300 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white">选择器管理</h1>
      <div class="flex items-center gap-4">
        <!-- Include disabled toggle -->
        <label class="flex items-center gap-2 text-sm text-slate-400 cursor-pointer select-none">
          <input
            v-model="includeDisabled"
            type="checkbox"
            class="h-4 w-4 rounded border-white/20 bg-white/5 text-purple-500 focus:ring-purple-500"
          />
          显示已禁用
        </label>
        <!-- Add button -->
        <button
          class="inline-flex items-center px-4 py-2 btn-aurora text-sm font-medium rounded-xl transition-colors"
          @click="openCreateDialog"
        >
          <svg
            class="-ml-1 mr-2 h-5 w-5"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"
            />
          </svg>
          <span class="relative z-10">添加选择器</span>
        </button>
      </div>
    </div>

    <!-- Version filter tabs -->
    <div class="flex items-center gap-2 mb-3 overflow-x-auto pb-1">
      <button
        v-for="ver in ['all', ...availableVersions]"
        :key="ver"
        :class="[
          'px-3 py-1.5 text-sm font-medium rounded-lg whitespace-nowrap transition-colors',
          versionFilter === ver
            ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
            : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent',
        ]"
        @click="versionFilter = ver"
      >
        {{ ver === 'all' ? '全部版本' : ver === 'default' ? '默认版本' : 'v' + ver }}
      </button>
    </div>

    <!-- Category tabs -->
    <div class="flex items-center gap-2 mb-4 overflow-x-auto pb-1">
      <button
        v-for="tab in categoryTabs"
        :key="tab.key"
        :class="[
          'px-3 py-1.5 text-sm font-medium rounded-lg whitespace-nowrap transition-colors',
          categoryFilter === tab.key
            ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
            : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent',
        ]"
        @click="categoryFilter = tab.key"
      >
        {{ tab.label }}
        <span v-if="categoryCounts[tab.key]" class="ml-1 text-xs opacity-60">
          ({{ categoryCounts[tab.key] || 0 }})
        </span>
      </button>
    </div>

    <!-- Loading -->
    <LoadingSpinner v-if="loading" />

    <!-- Empty state -->
    <EmptyState v-else-if="filteredSelectors.length === 0" :message="categoryFilter === 'all' ? '暂无选择器' : '当前分类暂无选择器'" />

    <!-- Selector cards -->
    <div v-else class="grid gap-4">
      <div
        v-for="sel in filteredSelectors"
        :key="sel.action_name + '_' + (sel.platform_version || 'default')"
        :class="[
          'glass-card p-5 transition-opacity',
          !sel.enabled && 'opacity-50',
        ]"
      >
        <div class="flex items-start justify-between">
          <!-- Left: info -->
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-3 flex-wrap">
              <span class="font-mono text-base font-semibold text-white" :title="'动作名称：' + sel.action_name">
                {{ sel.action_name }}
              </span>
              <span v-if="sel.description || actionDescriptions[sel.action_name]" class="text-sm text-slate-400">
                {{ sel.description || actionDescriptions[sel.action_name] }}
              </span>
              <span
                class="inline-flex items-center rounded-full bg-purple-500/15 text-purple-300 border border-purple-500/25 px-2.5 py-0.5 text-xs font-medium"
                :title="'选择器版本号，每次修改自动递增'"
              >
                v{{ sel.version }}
              </span>
              <span
                v-if="sel.platform_version"
                class="inline-flex items-center rounded-full bg-slate-500/15 text-slate-300 border border-slate-500/25 px-2.5 py-0.5 text-xs font-medium"
                :title="'适配的抖音版本：' + sel.platform_version"
              >
                平台 {{ sel.platform_version }}
              </span>
              <span
                v-if="sel.category"
                :class="[
                  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium',
                  getCategoryClass(sel.category),
                ]"
                :title="'操作分类：' + getCategoryLabel(sel.category)"
              >
                {{ getCategoryLabel(sel.category) }}
              </span>
              <span
                v-if="!sel.enabled"
                class="inline-flex items-center rounded-full bg-red-500/10 text-red-400 border border-red-500/20 px-2.5 py-0.5 text-xs font-medium"
                title="此选择器已禁用，设备端不会使用"
              >
                已禁用
              </span>
            </div>
            <p class="mt-2 text-sm text-slate-400" :title="'策略详情：' + JSON.stringify(sel.strategies)">
              {{ formatStrategies(sel.strategies) }}
            </p>
          </div>

          <!-- Right: toggle + actions -->
          <div class="ml-4 flex items-center gap-3 flex-shrink-0">
            <!-- Toggle switch -->
            <SwitchGroup>
              <div class="flex items-center gap-2">
                <SwitchLabel class="text-sm text-slate-400 cursor-pointer">
                  {{ sel.enabled ? '启用' : '禁用' }}
                </SwitchLabel>
                <Switch
                  :model-value="sel.enabled"
                  :class="sel.enabled ? 'bg-indigo-600' : 'bg-slate-600'"
                  class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-0"
                  @update:model-value="(val) => handleToggle(sel, val)"
                >
                  <span
                    :class="sel.enabled ? 'translate-x-6' : 'translate-x-1'"
                    class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                  />
                </Switch>
              </div>
            </SwitchGroup>

            <!-- Edit button -->
            <button
              class="inline-flex items-center px-3 py-1 text-sm font-medium text-cyan-400 hover:text-cyan-300 hover:bg-cyan-400/10 rounded transition-colors"
              @click="openEditDialog(sel)"
            >
              编辑
            </button>

            <!-- Delete button -->
            <button
              class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-400/10 rounded transition-colors"
              @click="openDeleteDialog(sel)"
            >
              删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Create / Edit Dialog -->
    <TransitionRoot :show="showFormDialog" as="template">
      <Dialog
        as="div"
        class="relative z-50"
        @close="showFormDialog = false"
      >
        <TransitionChild
          as="template"
          enter="ease-out duration-300"
          enter-from="opacity-0"
          enter-to="opacity-100"
          leave="ease-in duration-200"
          leave-from="opacity-100"
          leave-to="opacity-0"
        >
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>

        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild
              as="template"
              enter="ease-out duration-300"
              enter-from="opacity-0 scale-95"
              enter-to="opacity-100 scale-100"
              leave="ease-in duration-200"
              leave-from="opacity-100 scale-100"
              leave-to="opacity-0 scale-95"
            >
              <DialogPanel
                class="w-full max-w-lg glass-card p-6 gradient-border"
              >
                <DialogTitle class="text-lg font-medium text-white">
                  {{ isEditing ? '编辑选择器' : '添加选择器' }}
                </DialogTitle>

                <!-- Error message -->
                <div
                  v-if="formError"
                  class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-3 py-2 rounded-lg"
                >
                  {{ formError }}
                </div>

                <form class="mt-4 space-y-4" @submit.prevent="handleSave">
                  <!-- action_name -->
                  <div>
                    <label
                      for="sel-action-name"
                      class="flex items-center gap-1.5 text-sm font-medium text-slate-300"
                    >
                      动作名称
                      <span class="text-red-400">*</span>
                      <span class="tooltip-trigger group relative inline-flex items-center">
                        <svg class="w-4 h-4 text-slate-500 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke-width="2"/><path stroke-linecap="round" d="M12 16v-4m0-4h.01" stroke-width="2"/></svg>
                        <span class="tooltip-content invisible group-hover:visible absolute z-50 left-6 top-0 w-80 p-3 text-xs font-normal text-slate-300 bg-slate-800 border border-white/10 rounded-lg shadow-xl leading-relaxed">
                          <span class="font-semibold text-white block mb-1">{{ tooltips.action_name.title }}</span>
                          {{ tooltips.action_name.desc }}<br><br>
                          <span class="text-cyan-400">{{ tooltips.action_name.examples }}</span>
                        </span>
                      </span>
                    </label>
                    <input
                      id="sel-action-name"
                      v-model="form.action_name"
                      type="text"
                      required
                      :disabled="isEditing"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 disabled:bg-white/5 disabled:text-slate-500 disabled:cursor-not-allowed font-mono"
                      placeholder="例如 like_video"
                    />
                    <p class="mt-1 text-xs text-slate-500">唯一标识符，对应设备端要执行的操作（如 like_video、comment_video）</p>
                  </div>

                  <!-- description -->
                  <div>
                    <label for="sel-description" class="flex items-center gap-1.5 text-sm font-medium text-slate-300">
                      说明
                    </label>
                    <input
                      id="sel-description"
                      v-model="form.description"
                      type="text"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                      placeholder="例如：视频评论入口按钮（点击打开评论面板）"
                    />
                    <p class="mt-1 text-xs text-slate-500">可选，描述此选择器的用途，方便后续管理</p>
                  </div>

                  <!-- platform_version -->
                  <div>
                    <label
                      for="sel-platform-version"
                      class="flex items-center gap-1.5 text-sm font-medium text-slate-300"
                    >
                      平台版本
                      <span class="tooltip-trigger group relative inline-flex items-center">
                        <svg class="w-4 h-4 text-slate-500 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke-width="2"/><path stroke-linecap="round" d="M12 16v-4m0-4h.01" stroke-width="2"/></svg>
                        <span class="tooltip-content invisible group-hover:visible absolute z-50 left-6 top-0 w-80 p-3 text-xs font-normal text-slate-300 bg-slate-800 border border-white/10 rounded-lg shadow-xl leading-relaxed">
                          <span class="font-semibold text-white block mb-1">{{ tooltips.platform_version.title }}</span>
                          {{ tooltips.platform_version.desc }}<br><br>
                          <span class="text-cyan-400">{{ tooltips.platform_version.examples }}</span>
                        </span>
                      </span>
                    </label>
                    <input
                      id="sel-platform-version"
                      v-model="form.platform_version"
                      type="text"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                      placeholder="例如 29.0.0（留空表示所有版本）"
                    />
                    <p class="mt-1 text-xs text-slate-500">抖音 App 版本号，用于多版本适配，留空表示通用</p>
                  </div>

                  <!-- category -->
                  <div>
                    <label for="sel-category" class="flex items-center gap-1.5 text-sm font-medium text-slate-300">
                      操作分类
                    </label>
                    <select
                      id="sel-category"
                      v-model="form.category"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
                    >
                      <option v-for="opt in categoryOptions" :key="opt.value" :value="opt.value">
                        {{ opt.label }}
                      </option>
                    </select>
                    <p class="mt-1 text-xs text-slate-500">选择此选择器所属的操作模块分类，方便筛选和维护</p>
                  </div>

                  <!-- purpose: locate vs extract -->
                  <div>
                    <label class="flex items-center gap-1.5 text-sm font-medium text-slate-300">
                      控件用途
                    </label>
                    <div class="mt-2 flex rounded-lg border border-white/10 overflow-hidden">
                      <button
                        type="button"
                        :class="form.purpose === 'locate' ? 'bg-indigo-500/20 text-indigo-300' : 'text-slate-500 hover:text-slate-300'"
                        class="flex-1 px-4 py-2 text-sm font-medium transition-colors"
                        @click="form.purpose = 'locate'"
                      >
                        定位（点击/操作控件）
                      </button>
                      <button
                        type="button"
                        :class="form.purpose === 'extract' ? 'bg-emerald-500/20 text-emerald-300' : 'text-slate-500 hover:text-slate-300'"
                        class="flex-1 px-4 py-2 text-sm font-medium transition-colors"
                        @click="form.purpose = 'extract'"
                      >
                        取值（读取控件内容）
                      </button>
                    </div>
                    <p class="mt-1 text-xs text-slate-500">定位：查找控件并点击/输入；取值：查找控件并读取其属性值</p>
                  </div>

                  <!-- extract fields (shown when purpose=extract) -->
                  <div v-if="form.purpose === 'extract'" class="space-y-3">
                    <div>
                      <label class="text-sm font-medium text-slate-300">取值字段</label>
                      <select
                        v-model="form.extract_field"
                        class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
                      >
                        <option value="text">text（文本内容）</option>
                        <option value="desc">desc（描述内容）</option>
                        <option value="id">id（资源ID）</option>
                        <option value="className">className（类名）</option>
                      </select>
                      <p class="mt-1 text-xs text-slate-500">从找到的控件中读取此属性</p>
                    </div>

                    <div>
                      <label class="text-sm font-medium text-slate-300">清洗方式</label>
                      <div class="mt-2 flex gap-2">
                        <button
                          type="button"
                          :class="form.clean_mode === 'raw' ? 'bg-slate-500/20 text-slate-200 border-slate-500/30' : 'text-slate-500 hover:text-slate-300 border-transparent'"
                          class="px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors"
                          @click="form.clean_mode = 'raw'"
                        >
                          不处理（原始值）
                        </button>
                        <button
                          type="button"
                          :class="form.clean_mode === 'regex' ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30' : 'text-slate-500 hover:text-slate-300 border-transparent'"
                          class="px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors"
                          @click="form.clean_mode = 'regex'"
                        >
                          正则清洗
                        </button>
                        <button
                          type="button"
                          :class="form.clean_mode === 'ai' ? 'bg-purple-500/20 text-purple-300 border-purple-500/30' : 'text-slate-500 hover:text-slate-300 border-transparent'"
                          class="px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors"
                          @click="form.clean_mode = 'ai'"
                        >
                          AI 清洗
                        </button>
                      </div>
                    </div>

                    <!-- Regex mode -->
                    <div v-if="form.clean_mode === 'regex'" class="space-y-2">
                      <div>
                        <label class="text-xs text-slate-400 mb-1 block">AI 需求描述（用大白话告诉 AI 要提取什么，可粘贴原始数据）</label>
                        <div class="flex items-end gap-2">
                          <textarea
                            v-model="regexAiPrompt"
                            rows="3"
                            placeholder="描述要提取的内容，可粘贴多条原始数据示例"
                            class="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none"
                          />
                          <button
                            type="button"
                            class="btn-aurora rounded-lg px-3 py-2 text-xs font-medium whitespace-nowrap"
                            @click="generateRegexAI"
                            :disabled="generatingRegex"
                          >
                            <span class="relative z-10">{{ generatingRegex ? '生成中...' : 'AI 生成' }}</span>
                          </button>
                        </div>
                      </div>
                      <div>
                        <label class="text-xs text-slate-400 mb-1 block">正则表达式</label>
                        <input
                          v-model="form.clean_pattern"
                          type="text"
                          placeholder="AI 生成后自动填入，也可手动填写"
                          class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 font-mono focus:border-cyan-500/50 focus:outline-none"
                        />
                      </div>
                    </div>

                    <!-- AI mode -->
                    <div v-if="form.clean_mode === 'ai'" class="space-y-2">
                      <div>
                        <label class="text-xs text-slate-400 mb-1 block">AI 需求描述（用大白话告诉 AI 怎么清洗数据）</label>
                        <div class="flex items-end gap-2">
                          <textarea
                            v-model="cleanAiPrompt"
                            rows="3"
                            placeholder="例如：提取评论中的血糖数值，去掉单位和多余文字"
                            class="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none"
                          />
                          <button
                            type="button"
                            class="btn-aurora rounded-lg px-3 py-2 text-xs font-medium whitespace-nowrap"
                            @click="generateCleanPromptAI"
                            :disabled="generatingPrompt"
                          >
                            <span class="relative z-10">{{ generatingPrompt ? '生成中...' : 'AI 生成' }}</span>
                          </button>
                        </div>
                      </div>
                      <div>
                        <label class="text-xs text-slate-400 mb-1 block">清洗提示词</label>
                        <textarea
                          v-model="form.clean_prompt"
                          rows="3"
                          placeholder="AI 生成后自动填入，也可手动填写"
                          class="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:border-purple-500/50 focus:outline-none"
                        />
                      </div>
                    </div>
                  </div>

                  <!-- strategies -->
                  <div>
                    <div class="flex items-center justify-between mb-2">
                      <label class="flex items-center gap-1.5 text-sm font-medium text-slate-300">
                        选择策略
                        <span class="text-red-400">*</span>
                      </label>
                      <!-- Mode toggle -->
                      <div class="flex items-center rounded-lg border border-white/10 overflow-hidden">
                        <button
                          type="button"
                          :class="editMode === 'form' ? 'bg-purple-500/20 text-purple-300' : 'text-slate-500 hover:text-slate-300'"
                          class="px-3 py-1 text-xs font-medium transition-colors"
                          @click="editMode = 'form'; syncStrategiesToList()"
                        >
                          可视化
                        </button>
                        <button
                          type="button"
                          :class="editMode === 'json' ? 'bg-purple-500/20 text-purple-300' : 'text-slate-500 hover:text-slate-300'"
                          class="px-3 py-1 text-xs font-medium transition-colors"
                          @click="editMode = 'json'; syncListToStrategies()"
                        >
                          JSON
                        </button>
                      </div>
                    </div>

                    <!-- Form mode: card builder -->
                    <div v-if="editMode === 'form'" class="space-y-3">
                      <div v-if="strategyList.length === 0" class="text-center py-6 text-slate-500 text-sm border border-dashed border-white/10 rounded-lg">
                        暂无策略，点击下方按钮添加
                      </div>
                      <StrategyCard
                        v-for="(s, i) in strategyList"
                        :key="i"
                        :strategy="s"
                        :index="i"
                        :total-count="strategyList.length"
                        :action-name="form.action_name"
                        @update="updateStrategy(i, $event)"
                        @delete="deleteStrategy(i)"
                        @move-up="moveStrategy(i, -1)"
                        @move-down="moveStrategy(i, 1)"
                      />
                      <button
                        type="button"
                        class="w-full py-2 border border-dashed border-white/20 rounded-lg text-sm text-slate-400 hover:text-purple-300 hover:border-purple-500/30 transition-colors"
                        @click="addStrategy"
                      >
                        + 添加策略
                      </button>
                    </div>

                    <!-- JSON mode: raw textarea -->
                    <div v-else>
                      <textarea
                        v-model="form.strategies"
                        rows="8"
                        class="block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 font-mono"
                        placeholder='[{"type":"text","value":"赞","priority":1}]'
                        @blur="syncStrategiesToList()"
                      />
                      <p class="mt-1 text-xs text-slate-500">
                        JSON 数组，每个策略含 type、value、priority 等字段
                      </p>
                    </div>
                  </div>

                  <!-- Buttons -->
                  <div class="flex justify-end gap-3 pt-2">
                    <button
                      type="button"
                      class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors"
                      @click="showFormDialog = false"
                    >
                      取消
                    </button>
                    <button
                      type="submit"
                      :disabled="saving"
                      class="btn-aurora rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <span class="relative z-10">{{ saving ? '保存中...' : '保存' }}</span>
                    </button>
                  </div>
                </form>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>

    <!-- Delete Confirmation Dialog -->
    <ConfirmDialog
      :open="showDeleteDialog"
      title="删除选择器"
      :message="`确定要删除选择器「${deletingSelector?.action_name || ''}」吗？此操作不可撤销。`"
      confirm-text="删除"
      :danger="true"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>
