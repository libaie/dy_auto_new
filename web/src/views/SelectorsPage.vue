<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
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
    desc: 'JSON 数组，定义如何在屏幕上定位目标 UI 元素。每个策略是一种查找方式，系统按 priority 顺序依次尝试，直到找到元素为止。',
    types: [
      { type: 'text', value: '通过文本内容查找', fields: 'value: 要匹配的文本（支持部分匹配）' },
      { type: 'id', value: '通过资源 ID 查找', fields: 'value: Android 资源 ID，如 com.ss.android.ugc.aweme:id/like_btn' },
      { type: 'desc', value: '通过内容描述查找', fields: 'value: 元素的 contentDescription 属性值' },
      { type: 'className', value: '通过类名查找', fields: 'value: Android 控件类名，如 android.widget.TextView' },
      { type: 'package', value: '通过包名查找', fields: 'value: 应用包名，如 com.ss.android.ugc.aweme' },
      { type: 'coordinate', value: '通过固定坐标点击', fields: 'x_percent: X 坐标百分比(0-100)，y_percent: Y 坐标百分比(0-100)' },
      { type: 'image', value: '通过图片模板匹配', fields: 'template: 模板图片路径或 base64，threshold: 匹配阈值(0-1，默认0.8)' },
    ],
    commonFields: '通用字段：type（策略类型）、value（查找值）、priority（优先级，数字越小越优先）、x_percent/y_percent（可选，点击偏移百分比）',
  },
}

// --- Data state ---
const selectors = ref([])
const loading = ref(false)
const includeDisabled = ref(false)

// --- Form / Dialog state ---
const showFormDialog = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const formError = ref(null)

const defaultForm = {
  action_name: '',
  platform_version: '',
  strategies: '[]',
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
    const val = s.value && s.value.length > 20 ? s.value.slice(0, 20) + '...' : s.value
    return `${s.type}:${val}`
  })
  return `${strategies.length} 个策略: ${parts.join(', ')}`
}

// --- Open create dialog ---
function openCreateDialog() {
  isEditing.value = false
  form.action_name = ''
  form.platform_version = ''
  form.strategies = '[]'
  editMode.value = 'form'
  strategyList.value = []
  formError.value = null
  showFormDialog.value = true
}

// --- Open edit dialog ---
function openEditDialog(sel) {
  isEditing.value = true
  form.action_name = sel.action_name
  form.platform_version = sel.platform_version || ''
  form.strategies = JSON.stringify(sel.strategies || [], null, 2)
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

    <!-- Loading -->
    <LoadingSpinner v-if="loading" />

    <!-- Empty state -->
    <EmptyState v-else-if="selectors.length === 0" message="暂无选择器" />

    <!-- Selector cards -->
    <div v-else class="grid gap-4">
      <div
        v-for="sel in selectors"
        :key="sel.action_name"
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
              <span v-if="actionDescriptions[sel.action_name]" class="text-sm text-slate-400">
                {{ actionDescriptions[sel.action_name] }}
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
                          @click="editMode = 'form'"
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
