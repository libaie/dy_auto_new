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
import {
  listSelectors,
  createSelector,
  updateSelector,
  deleteSelector,
  toggleSelector,
} from '../api/selectors.js'

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

// --- Delete confirmation state ---
const showDeleteDialog = ref(false)
const deletingSelector = ref(null)
const deleting = ref(false)

// --- Page-level error ---
const pageError = ref(null)

// --- Fetch selectors ---
async function fetchSelectors() {
  loading.value = true
  try {
    const res = await listSelectors(includeDisabled.value)
    selectors.value = res.data.selectors || []
  } catch (e) {
    console.error('Failed to fetch selectors:', e)
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
  formError.value = null
  showFormDialog.value = true
}

// --- Open edit dialog ---
function openEditDialog(sel) {
  isEditing.value = true
  form.action_name = sel.action_name
  form.platform_version = sel.platform_version || ''
  form.strategies = JSON.stringify(sel.strategies || [], null, 2)
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
    <div v-if="pageError" class="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-500 hover:text-red-700 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">选择器管理</h1>
      <div class="flex items-center gap-4">
        <!-- Include disabled toggle -->
        <label class="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
          <input
            v-model="includeDisabled"
            type="checkbox"
            class="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
          />
          显示已禁用
        </label>
        <!-- Add button -->
        <button
          class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 transition-colors"
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
          添加选择器
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
          'rounded-lg border border-gray-200 bg-white p-5 shadow-sm transition-opacity',
          !sel.enabled && 'opacity-50',
        ]"
      >
        <div class="flex items-start justify-between">
          <!-- Left: info -->
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-3 flex-wrap">
              <span class="font-mono text-base font-semibold text-gray-900" :title="'动作名称：' + sel.action_name">
                {{ sel.action_name }}
              </span>
              <span
                class="inline-flex items-center rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-700"
                :title="'选择器版本号，每次修改自动递增'"
              >
                v{{ sel.version }}
              </span>
              <span
                v-if="sel.platform_version"
                class="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600"
                :title="'适配的抖音版本：' + sel.platform_version"
              >
                平台 {{ sel.platform_version }}
              </span>
              <span
                v-if="!sel.enabled"
                class="inline-flex items-center rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700"
                title="此选择器已禁用，设备端不会使用"
              >
                已禁用
              </span>
            </div>
            <p class="mt-2 text-sm text-gray-500" :title="'策略详情：' + JSON.stringify(sel.strategies)">
              {{ formatStrategies(sel.strategies) }}
            </p>
          </div>

          <!-- Right: toggle + actions -->
          <div class="ml-4 flex items-center gap-3 flex-shrink-0">
            <!-- Toggle switch -->
            <SwitchGroup>
              <div class="flex items-center gap-2">
                <SwitchLabel class="text-sm text-gray-500 cursor-pointer">
                  {{ sel.enabled ? '启用' : '禁用' }}
                </SwitchLabel>
                <Switch
                  :model-value="sel.enabled"
                  :class="sel.enabled ? 'bg-indigo-600' : 'bg-gray-200'"
                  class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
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
              class="inline-flex items-center px-3 py-1 text-sm font-medium text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50 rounded transition-colors"
              @click="openEditDialog(sel)"
            >
              编辑
            </button>

            <!-- Delete button -->
            <button
              class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-600 hover:text-red-800 hover:bg-red-50 rounded transition-colors"
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
          <div class="fixed inset-0 bg-black/30" />
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
                class="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl"
              >
                <DialogTitle class="text-lg font-medium text-gray-900">
                  {{ isEditing ? '编辑选择器' : '添加选择器' }}
                </DialogTitle>

                <!-- Error message -->
                <div
                  v-if="formError"
                  class="mt-3 bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded"
                >
                  {{ formError }}
                </div>

                <form class="mt-4 space-y-4" @submit.prevent="handleSave">
                  <!-- action_name -->
                  <div>
                    <label
                      for="sel-action-name"
                      class="flex items-center gap-1.5 text-sm font-medium text-gray-700"
                    >
                      动作名称
                      <span class="text-red-500">*</span>
                      <span class="tooltip-trigger group relative inline-flex items-center">
                        <svg class="w-4 h-4 text-gray-400 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke-width="2"/><path stroke-linecap="round" d="M12 16v-4m0-4h.01" stroke-width="2"/></svg>
                        <span class="tooltip-content invisible group-hover:visible absolute z-50 left-6 top-0 w-80 p-3 text-xs font-normal text-gray-600 bg-white border border-gray-200 rounded-lg shadow-lg leading-relaxed">
                          <span class="font-semibold text-gray-800 block mb-1">{{ tooltips.action_name.title }}</span>
                          {{ tooltips.action_name.desc }}<br><br>
                          <span class="text-indigo-600">{{ tooltips.action_name.examples }}</span>
                        </span>
                      </span>
                    </label>
                    <input
                      id="sel-action-name"
                      v-model="form.action_name"
                      type="text"
                      required
                      :disabled="isEditing"
                      class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-gray-100 disabled:text-gray-500 disabled:cursor-not-allowed font-mono"
                      placeholder="例如 like_video"
                    />
                    <p class="mt-1 text-xs text-gray-400">唯一标识符，对应设备端要执行的操作（如 like_video、comment_video）</p>
                  </div>

                  <!-- platform_version -->
                  <div>
                    <label
                      for="sel-platform-version"
                      class="flex items-center gap-1.5 text-sm font-medium text-gray-700"
                    >
                      平台版本
                      <span class="tooltip-trigger group relative inline-flex items-center">
                        <svg class="w-4 h-4 text-gray-400 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke-width="2"/><path stroke-linecap="round" d="M12 16v-4m0-4h.01" stroke-width="2"/></svg>
                        <span class="tooltip-content invisible group-hover:visible absolute z-50 left-6 top-0 w-80 p-3 text-xs font-normal text-gray-600 bg-white border border-gray-200 rounded-lg shadow-lg leading-relaxed">
                          <span class="font-semibold text-gray-800 block mb-1">{{ tooltips.platform_version.title }}</span>
                          {{ tooltips.platform_version.desc }}<br><br>
                          <span class="text-indigo-600">{{ tooltips.platform_version.examples }}</span>
                        </span>
                      </span>
                    </label>
                    <input
                      id="sel-platform-version"
                      v-model="form.platform_version"
                      type="text"
                      class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      placeholder="例如 29.0.0（留空表示所有版本）"
                    />
                    <p class="mt-1 text-xs text-gray-400">抖音 App 版本号，用于多版本适配，留空表示通用</p>
                  </div>

                  <!-- strategies -->
                  <div>
                    <label
                      for="sel-strategies"
                      class="flex items-center gap-1.5 text-sm font-medium text-gray-700"
                    >
                      选择策略 (JSON 数组)
                      <span class="text-red-500">*</span>
                      <span class="tooltip-trigger group relative inline-flex items-center">
                        <svg class="w-4 h-4 text-gray-400 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke-width="2"/><path stroke-linecap="round" d="M12 16v-4m0-4h.01" stroke-width="2"/></svg>
                        <span class="tooltip-content invisible group-hover:visible absolute z-50 left-6 top-0 w-96 p-3 text-xs font-normal text-gray-600 bg-white border border-gray-200 rounded-lg shadow-lg leading-relaxed">
                          <span class="font-semibold text-gray-800 block mb-1">{{ tooltips.strategies.title }}</span>
                          {{ tooltips.strategies.desc }}<br><br>
                          <span class="font-semibold text-gray-700">支持的策略类型：</span>
                          <span v-for="t in tooltips.strategies.types" :key="t.type" class="block ml-2 mt-1">
                            <code class="text-indigo-600 font-semibold">{{ t.type }}</code> — {{ t.value }}<br>
                            <span class="text-gray-400 ml-4">字段：{{ t.fields }}</span>
                          </span>
                          <br>
                          <span class="text-gray-500">{{ tooltips.strategies.commonFields }}</span>
                        </span>
                      </span>
                    </label>
                    <textarea
                      id="sel-strategies"
                      v-model="form.strategies"
                      rows="8"
                      required
                      class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      placeholder='[{"type":"text","value":"赞","priority":1}]'
                    />
                    <p class="mt-1 text-xs text-gray-400">
                      每个策略包含：type（类型）、value（查找值）、priority（优先级，越小越优先）、x_percent/y_percent（可选，坐标偏移）、template/threshold（可选，图片匹配）
                    </p>
                    <details class="mt-2">
                      <summary class="text-xs text-indigo-500 cursor-pointer hover:text-indigo-700">展开查看策略类型速查表</summary>
                      <div class="mt-2 p-3 bg-gray-50 rounded-md text-xs space-y-1.5">
                        <div v-for="t in tooltips.strategies.types" :key="t.type" class="flex">
                          <code class="w-20 flex-shrink-0 font-semibold text-indigo-600">{{ t.type }}</code>
                          <span class="text-gray-600">{{ t.value }} <span class="text-gray-400">（{{ t.fields }}）</span></span>
                        </div>
                      </div>
                    </details>
                  </div>

                  <!-- Buttons -->
                  <div class="flex justify-end gap-3 pt-2">
                    <button
                      type="button"
                      class="rounded-md bg-white px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                      @click="showFormDialog = false"
                    >
                      取消
                    </button>
                    <button
                      type="submit"
                      :disabled="saving"
                      class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {{ saving ? '保存中...' : '保存' }}
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
