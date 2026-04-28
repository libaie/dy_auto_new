<script setup>
import { ref, reactive, onMounted } from 'vue'
import {
  Dialog, DialogPanel, DialogTitle, TransitionRoot, TransitionChild,
} from '@headlessui/vue'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import EmptyState from '../components/EmptyState.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import {
  listTemplates, createTemplate, updateTemplate, deleteTemplate,
  listSensitiveWords, addSensitiveWord, deleteSensitiveWord,
  generateContent,
} from '../api/content.js'
import { formatDate } from '../utils/format.js'

// --- Templates state ---
const templates = ref([])
const loading = ref(false)
const pageError = ref(null)

// --- Template form dialog ---
const showFormDialog = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const formError = ref(null)
const defaultForm = { name: '', category: 'comment', body: '', variables: '' }
const form = reactive({ ...defaultForm })
const editingId = ref(null)

// --- Delete confirmation ---
const showDeleteDialog = ref(false)
const deletingTemplate = ref(null)
const deleting = ref(false)

// --- Sensitive words ---
const words = ref([])
const wordsLoading = ref(false)
const newWord = ref('')
const addingWord = ref(false)
const showWords = ref(false)

// --- AI Generate dialog ---
const showGenerateDialog = ref(false)
const generatingTemplate = ref(null)
const generateForm = reactive({ keyword: '', username: '', video_title: '' })
const generating = ref(false)
const generateResult = ref(null)
const generateError = ref(null)

const categoryLabels = { comment: '评论', dm: '私信', reply: '回复' }
const categoryColors = {
  comment: 'bg-blue-100 text-blue-800',
  dm: 'bg-green-100 text-green-800',
  reply: 'bg-purple-100 text-purple-800',
}

// --- Fetch templates ---
async function fetchTemplates() {
  loading.value = true
  try {
    const res = await listTemplates()
    templates.value = res.data.templates || []
  } catch (e) {
    pageError.value = e.response?.data?.detail || '加载模板失败'
    templates.value = []
  } finally {
    loading.value = false
  }
}

// --- Template CRUD ---
function openCreateDialog() {
  isEditing.value = false
  editingId.value = null
  Object.assign(form, defaultForm)
  formError.value = null
  showFormDialog.value = true
}

function openEditDialog(tpl) {
  isEditing.value = true
  editingId.value = tpl.id
  form.name = tpl.name
  form.category = tpl.category
  form.body = tpl.body
  form.variables = (tpl.variables || []).join(', ')
  formError.value = null
  showFormDialog.value = true
}

async function handleSave() {
  if (!form.name.trim()) { formError.value = '名称不能为空'; return }
  if (!form.body.trim()) { formError.value = '模板内容不能为空'; return }

  saving.value = true
  formError.value = null

  const vars = form.variables.split(',').map(v => v.trim()).filter(Boolean)
  const payload = {
    name: form.name.trim(),
    category: form.category,
    body: form.body.trim(),
    variables: vars,
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
    formError.value = e.response?.data?.detail || '保存失败'
  } finally {
    saving.value = false
  }
}

function openDeleteDialog(tpl) {
  deletingTemplate.value = tpl
  showDeleteDialog.value = true
}

async function handleDelete() {
  if (!deletingTemplate.value) return
  deleting.value = true
  try {
    await deleteTemplate(deletingTemplate.value.id)
    showDeleteDialog.value = false
    deletingTemplate.value = null
    fetchTemplates()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '删除失败'
  } finally {
    deleting.value = false
  }
}

// --- Sensitive words ---
async function fetchWords() {
  wordsLoading.value = true
  try {
    const res = await listSensitiveWords()
    words.value = res.data.words || []
  } catch (e) {
    console.error('Failed to fetch words:', e)
  } finally {
    wordsLoading.value = false
  }
}

async function handleAddWord() {
  const w = newWord.value.trim()
  if (!w) return
  addingWord.value = true
  try {
    await addSensitiveWord(w)
    newWord.value = ''
    fetchWords()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '添加失败'
  } finally {
    addingWord.value = false
  }
}

async function handleDeleteWord(word) {
  try {
    await deleteSensitiveWord(word.id)
    fetchWords()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '删除失败'
  }
}

// --- AI Generate ---
function openGenerateDialog(tpl) {
  generatingTemplate.value = tpl
  generateForm.keyword = ''
  generateForm.username = ''
  generateForm.video_title = ''
  generateResult.value = null
  generateError.value = null
  showGenerateDialog.value = true
}

async function handleGenerate() {
  generating.value = true
  generateError.value = null
  generateResult.value = null
  try {
    const res = await generateContent(generatingTemplate.value.id, {
      keyword: generateForm.keyword,
      username: generateForm.username,
      video_title: generateForm.video_title,
    })
    generateResult.value = res.data.content
  } catch (e) {
    generateError.value = e.response?.data?.detail || '生成失败'
  } finally {
    generating.value = false
  }
}

function copyResult() {
  if (generateResult.value) {
    navigator.clipboard.writeText(generateResult.value)
  }
}

// --- Init ---
onMounted(() => {
  fetchTemplates()
  fetchWords()
})
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
      <h1 class="text-2xl font-bold text-gray-800">内容管理</h1>
      <button
        class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 transition-colors"
        @click="openCreateDialog"
      >
        <svg class="-ml-1 mr-2 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
          <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" />
        </svg>
        添加模板
      </button>
    </div>

    <!-- Loading -->
    <LoadingSpinner v-if="loading" />

    <!-- Empty -->
    <EmptyState v-else-if="templates.length === 0" message="暂无内容模板" />

    <!-- Template cards -->
    <div v-else class="grid gap-4 mb-8">
      <div
        v-for="tpl in templates"
        :key="tpl.id"
        class="rounded-lg border border-gray-200 bg-white p-5 shadow-sm"
      >
        <div class="flex items-start justify-between">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-3 flex-wrap">
              <span class="font-semibold text-gray-900">{{ tpl.name }}</span>
              <span :class="[categoryColors[tpl.category] || 'bg-gray-100 text-gray-800']"
                class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium">
                {{ categoryLabels[tpl.category] || tpl.category }}
              </span>
              <span v-if="tpl.variables && tpl.variables.length > 0"
                class="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700">
                {{ tpl.variables.length }} 个变量
              </span>
            </div>
            <p class="mt-2 text-sm text-gray-600 whitespace-pre-wrap">{{ tpl.body }}</p>
            <p v-if="tpl.variables && tpl.variables.length > 0" class="mt-1 text-xs text-gray-400">
              变量: {{ tpl.variables.map(v => '{' + v + '}').join(', ') }}
            </p>
          </div>
          <div class="ml-4 flex items-center gap-2 flex-shrink-0">
            <button
              class="inline-flex items-center px-3 py-1 text-sm font-medium text-green-600 hover:text-green-800 hover:bg-green-50 rounded transition-colors"
              @click="openGenerateDialog(tpl)"
            >
              AI 生成
            </button>
            <button
              class="inline-flex items-center px-3 py-1 text-sm font-medium text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50 rounded transition-colors"
              @click="openEditDialog(tpl)"
            >
              编辑
            </button>
            <button
              class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-600 hover:text-red-800 hover:bg-red-50 rounded transition-colors"
              @click="openDeleteDialog(tpl)"
            >
              删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Sensitive Words Section -->
    <div class="bg-white rounded-lg shadow">
      <button
        class="w-full flex items-center justify-between px-6 py-4 text-left"
        @click="showWords = !showWords"
      >
        <h2 class="text-lg font-semibold text-gray-700">敏感词库 ({{ words.length }})</h2>
        <svg :class="showWords ? 'rotate-180' : ''" class="w-5 h-5 text-gray-400 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      <div v-if="showWords" class="px-6 pb-4 border-t border-gray-100">
        <!-- Add word input -->
        <div class="flex gap-2 mt-4 mb-4">
          <input
            v-model="newWord"
            type="text"
            class="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            placeholder="输入敏感词"
            @keyup.enter="handleAddWord"
          />
          <button
            :disabled="addingWord || !newWord.trim()"
            class="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
            @click="handleAddWord"
          >
            添加
          </button>
        </div>
        <!-- Word list -->
        <LoadingSpinner v-if="wordsLoading" />
        <div v-else-if="words.length === 0" class="text-sm text-gray-400 py-2">暂无敏感词</div>
        <div v-else class="flex flex-wrap gap-2">
          <span
            v-for="word in words"
            :key="word.id"
            class="inline-flex items-center gap-1 rounded-full bg-red-50 px-3 py-1 text-sm text-red-700"
          >
            {{ word.word }}
            <button class="text-red-400 hover:text-red-600" @click="handleDeleteWord(word)">&times;</button>
          </span>
        </div>
      </div>
    </div>

    <!-- Template Create/Edit Dialog -->
    <TransitionRoot :show="showFormDialog" as="template">
      <Dialog as="div" class="relative z-50" @close="showFormDialog = false">
        <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/30" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
                <DialogTitle class="text-lg font-medium text-gray-900">
                  {{ isEditing ? '编辑模板' : '添加模板' }}
                </DialogTitle>
                <div v-if="formError" class="mt-3 bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded">
                  {{ formError }}
                </div>
                <form class="mt-4 space-y-4" @submit.prevent="handleSave">
                  <div>
                    <label for="tpl-name" class="block text-sm font-medium text-gray-700">名称 <span class="text-red-500">*</span></label>
                    <input id="tpl-name" v-model="form.name" type="text" required class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="例如：美食评论模板" />
                  </div>
                  <div>
                    <label for="tpl-category" class="block text-sm font-medium text-gray-700">分类</label>
                    <select id="tpl-category" v-model="form.category" class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500">
                      <option value="comment">评论</option>
                      <option value="dm">私信</option>
                      <option value="reply">回复</option>
                    </select>
                  </div>
                  <div>
                    <label for="tpl-body" class="block text-sm font-medium text-gray-700">模板内容 <span class="text-red-500">*</span></label>
                    <textarea id="tpl-body" v-model="form.body" rows="4" required class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="支持 {keyword}、{username}、{video_title} 变量" />
                  </div>
                  <div>
                    <label for="tpl-vars" class="block text-sm font-medium text-gray-700">变量 (逗号分隔)</label>
                    <input id="tpl-vars" v-model="form.variables" type="text" class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="keyword, username, video_title" />
                    <p class="mt-1 text-xs text-gray-400">在模板中使用 {变量名} 引用</p>
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

    <!-- Delete Confirmation -->
    <ConfirmDialog
      :open="showDeleteDialog"
      title="删除模板"
      :message="`确定要删除模板「${deletingTemplate?.name || ''}」吗？`"
      confirm-text="删除"
      :danger="true"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />

    <!-- AI Generate Dialog -->
    <TransitionRoot :show="showGenerateDialog" as="template">
      <Dialog as="div" class="relative z-50" @close="showGenerateDialog = false">
        <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/30" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
                <DialogTitle class="text-lg font-medium text-gray-900">AI 内容生成</DialogTitle>
                <p class="mt-1 text-sm text-gray-500">模板: {{ generatingTemplate?.name }}</p>
                <div class="mt-3 bg-gray-50 rounded p-3 text-sm text-gray-600 whitespace-pre-wrap">{{ generatingTemplate?.body }}</div>

                <div v-if="generateError" class="mt-3 bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded">
                  {{ generateError }}
                </div>

                <form class="mt-4 space-y-3" @submit.prevent="handleGenerate">
                  <div>
                    <label class="block text-sm font-medium text-gray-700">搜索关键词</label>
                    <input v-model="generateForm.keyword" type="text" class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="例如：美食探店" />
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-700">目标用户名</label>
                    <input v-model="generateForm.username" type="text" class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="例如：美食家小明" />
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-700">视频标题</label>
                    <input v-model="generateForm.video_title" type="text" class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="例如：今天去了一家超好吃的火锅店" />
                  </div>

                  <!-- Result -->
                  <div v-if="generateResult" class="bg-green-50 border border-green-200 rounded p-3">
                    <div class="flex items-start justify-between">
                      <p class="text-sm text-green-800 flex-1">{{ generateResult }}</p>
                      <button type="button" class="ml-2 text-green-600 hover:text-green-800 text-xs" @click="copyResult">复制</button>
                    </div>
                  </div>

                  <div class="flex justify-end gap-3 pt-2">
                    <button type="button" class="rounded-md bg-white px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50" @click="showGenerateDialog = false">关闭</button>
                    <button type="submit" :disabled="generating" class="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed">
                      {{ generating ? '生成中...' : 'AI 生成' }}
                    </button>
                  </div>
                </form>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>
  </div>
</template>
