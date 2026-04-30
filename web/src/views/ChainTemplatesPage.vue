<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import {
  Dialog,
  DialogPanel,
  DialogTitle,
  TransitionRoot,
  TransitionChild,
} from '@headlessui/vue'
import DataTable from '../components/DataTable.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { listTemplates, createTemplate, updateTemplate, deleteTemplate } from '../api/chains.js'
import { formatDate } from '../utils/format.js'

const typeOptions = [
  { value: 'nurture', label: '养号' },
  { value: 'search_comment', label: '搜索评论' },
  { value: 'search_like', label: '搜索点赞' },
  { value: 'search_dm', label: '搜索私信' },
  { value: 'reply_comment', label: '评论回复' },
]

const typeParamDefaults = {
  nurture: { duration: 30 },
  search_comment: { keyword: '', count: 5 },
  search_like: { keyword: '', count: 5 },
  search_dm: { keyword: '', count: 5 },
  reply_comment: { keyword: '', count: 5, video_count: 3 },
}

// --- Data state ---
const templates = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

// --- Form / Dialog state ---
const showFormDialog = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const formError = ref(null)
const editingId = ref(null)

const defaultForm = {
  name: '',
  description: '',
  steps: [],
}
const form = reactive({ ...defaultForm })

// --- Delete confirmation state ---
const showDeleteDialog = ref(false)
const deletingTemplate = ref(null)
const deleting = ref(false)

// --- Page-level error ---
const pageError = ref(null)

// --- Table columns ---
const columns = [
  { key: 'name', label: '模板名称' },
  { key: 'description', label: '描述' },
  { key: 'steps_count', label: '步骤数' },
  { key: 'created_at', label: '创建时间' },
  { key: 'actions', label: '操作', headerClass: 'text-right', cellClass: 'text-right' },
]

// --- Fetch templates ---
async function fetchTemplates() {
  loading.value = true
  try {
    const skip = (page.value - 1) * pageSize
    const res = await listTemplates({ skip, limit: pageSize })
    templates.value = (res.data.templates || []).map(t => ({
      ...t,
      steps_count: t.steps?.length || 0,
    }))
    total.value = res.data.total || 0
  } catch (e) {
    console.error('Failed to fetch templates:', e)
    templates.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handlePageChange(p) {
  page.value = p
  fetchTemplates()
}

// --- Open create dialog ---
function openCreateDialog() {
  isEditing.value = false
  editingId.value = null
  form.name = ''
  form.description = ''
  form.steps = []
  formError.value = null
  showFormDialog.value = true
}

// --- Open edit dialog ---
function openEditDialog(template) {
  isEditing.value = true
  editingId.value = template.id
  form.name = template.name || ''
  form.description = template.description || ''
  form.steps = (template.steps || []).map(s => ({ ...s }))
  formError.value = null
  showFormDialog.value = true
}

// --- Step management ---
function addStep() {
  const nextOrder = form.steps.length + 1
  form.steps.push({
    step_order: nextOrder,
    type: 'nurture',
    label: '步骤 ' + nextOrder,
    params: { duration: 30 },
  })
}

function removeStep(index) {
  form.steps.splice(index, 1)
  // Re-number steps
  form.steps.forEach((s, i) => { s.step_order = i + 1 })
}

function moveStepUp(index) {
  if (index === 0) return
  const temp = form.steps[index]
  form.steps[index] = form.steps[index - 1]
  form.steps[index - 1] = temp
  form.steps.forEach((s, i) => { s.step_order = i + 1 })
}

function moveStepDown(index) {
  if (index === form.steps.length - 1) return
  const temp = form.steps[index]
  form.steps[index] = form.steps[index + 1]
  form.steps[index + 1] = temp
  form.steps.forEach((s, i) => { s.step_order = i + 1 })
}

function onStepTypeChange(step) {
  step.params = { ...typeParamDefaults[step.type] || {} }
  step.label = typeOptions.find(o => o.value === step.type)?.label || step.type
}

// --- Save ---
async function handleSave() {
  if (!form.name.trim()) {
    formError.value = '模板名称不能为空'
    return
  }
  if (form.steps.length === 0) {
    formError.value = '至少添加一个步骤'
    return
  }

  saving.value = true
  formError.value = null

  const payload = {
    name: form.name.trim(),
    description: form.description.trim(),
    steps: form.steps,
  }

  try {
    if (isEditing.value) {
      await updateTemplate(editingId.value, payload)
    } else {
      await createTemplate(payload)
    }
    showFormDialog.value = false
    fetchTemplates()
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
function openDeleteDialog(template) {
  deletingTemplate.value = template
  showDeleteDialog.value = true
}

async function handleDelete() {
  if (!deletingTemplate.value) return
  deleting.value = true
  try {
    await deleteTemplate(deletingTemplate.value.id)
    showDeleteDialog.value = false
    deletingTemplate.value = null
    if (templates.value.length === 1 && page.value > 1) {
      page.value--
    }
    fetchTemplates()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '删除失败，请重试'
  } finally {
    deleting.value = false
  }
}

onMounted(fetchTemplates)
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
      <h1 class="text-2xl font-bold text-gray-800">任务链模板</h1>
      <button
        class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 transition-colors"
        @click="openCreateDialog"
      >
        <svg class="-ml-1 mr-2 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
          <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" />
        </svg>
        创建模板
      </button>
    </div>

    <!-- Data Table -->
    <DataTable
      :columns="columns"
      :data="templates"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      @page-change="handlePageChange"
    >
      <template #cell-created_at="{ value }">
        {{ formatDate(value) }}
      </template>

      <template #cell-actions="{ row }">
        <div class="flex justify-end gap-2">
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50 rounded transition-colors"
            @click="openEditDialog(row)"
          >
            编辑
          </button>
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-600 hover:text-red-800 hover:bg-red-50 rounded transition-colors"
            @click="openDeleteDialog(row)"
          >
            删除
          </button>
        </div>
      </template>
    </DataTable>

    <!-- Create / Edit Dialog -->
    <TransitionRoot :show="showFormDialog" as="template">
      <Dialog as="div" class="relative z-50" @close="showFormDialog = false">
        <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/30" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-2xl rounded-xl bg-white p-6 shadow-xl">
                <DialogTitle class="text-lg font-medium text-gray-900">
                  {{ isEditing ? '编辑模板' : '创建模板' }}
                </DialogTitle>
                <div v-if="formError" class="mt-3 bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded">
                  {{ formError }}
                </div>
                <form class="mt-4 space-y-4" @submit.prevent="handleSave">
                  <div>
                    <label class="block text-sm font-medium text-gray-700">模板名称 <span class="text-red-500">*</span></label>
                    <input v-model="form.name" type="text" required class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="请输入模板名称" />
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-700">描述</label>
                    <textarea v-model="form.description" rows="2" class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="请输入模板描述"></textarea>
                  </div>

                  <!-- Steps editor -->
                  <div>
                    <div class="flex items-center justify-between mb-2">
                      <label class="block text-sm font-medium text-gray-700">步骤配置</label>
                      <button type="button" class="text-sm text-indigo-600 hover:text-indigo-800" @click="addStep">+ 添加步骤</button>
                    </div>
                    <div v-if="form.steps.length === 0" class="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center text-sm text-gray-400">
                      点击「添加步骤」开始配置任务链
                    </div>
                    <div v-else class="space-y-3">
                      <div v-for="(step, index) in form.steps" :key="index" class="border rounded-lg p-3 bg-gray-50">
                        <div class="flex items-center justify-between mb-2">
                          <span class="text-sm font-medium text-gray-600">步骤 {{ step.step_order }}</span>
                          <div class="flex gap-1">
                            <button type="button" class="text-gray-400 hover:text-gray-600 px-1" :disabled="index === 0" @click="moveStepUp(index)">
                              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7"/></svg>
                            </button>
                            <button type="button" class="text-gray-400 hover:text-gray-600 px-1" :disabled="index === form.steps.length - 1" @click="moveStepDown(index)">
                              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
                            </button>
                            <button type="button" class="text-red-400 hover:text-red-600 px-1" @click="removeStep(index)">
                              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                            </button>
                          </div>
                        </div>
                        <div class="grid grid-cols-2 gap-2">
                          <div>
                            <label class="block text-xs text-gray-500">任务类型</label>
                            <select v-model="step.type" @change="onStepTypeChange(step)" class="mt-1 block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500">
                              <option v-for="opt in typeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                            </select>
                          </div>
                          <div>
                            <label class="block text-xs text-gray-500">步骤标签</label>
                            <input v-model="step.label" type="text" class="mt-1 block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
                          </div>
                        </div>
                        <!-- Params for the step -->
                        <div class="mt-2 grid grid-cols-2 gap-2">
                          <template v-if="step.type === 'nurture'">
                            <div>
                              <label class="block text-xs text-gray-500">时长(分钟)</label>
                              <input v-model.number="step.params.duration" type="number" min="1" max="120" class="mt-1 block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm shadow-sm" />
                            </div>
                          </template>
                          <template v-else>
                            <div>
                              <label class="block text-xs text-gray-500">关键词</label>
                              <input v-model="step.params.keyword" type="text" class="mt-1 block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm shadow-sm" />
                            </div>
                            <div>
                              <label class="block text-xs text-gray-500">数量</label>
                              <input v-model.number="step.params.count" type="number" min="1" max="20" class="mt-1 block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm shadow-sm" />
                            </div>
                            <div v-if="step.type === 'reply_comment'">
                              <label class="block text-xs text-gray-500">视频数</label>
                              <input v-model.number="step.params.video_count" type="number" min="1" max="10" class="mt-1 block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm shadow-sm" />
                            </div>
                            <div v-if="['search_comment', 'search_dm', 'reply_comment'].includes(step.type)">
                              <label class="block text-xs text-gray-500">内容</label>
                              <input v-model="step.params.content" type="text" class="mt-1 block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm shadow-sm" />
                            </div>
                          </template>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class="flex justify-end gap-3 pt-2">
                    <button type="button" class="rounded-md bg-white px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50" @click="showFormDialog = false">取消</button>
                    <button type="submit" :disabled="saving" class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed">
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
      title="删除模板"
      :message="`确定要删除模板「${deletingTemplate?.name || ''}」吗？此操作不可撤销。`"
      confirm-text="删除"
      :danger="true"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>
