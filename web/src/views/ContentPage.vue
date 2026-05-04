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
import { useToastStore } from '../stores/toast.js'
import TipIcon from '../components/TipIcon.vue'

// --- Templates state ---
const templates = ref([])
const loading = ref(false)
const pageError = ref(null)
const toast = useToastStore()

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
    toast.error('加载模板失败')
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
    toast.error('加载敏感词库失败')
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
    <div v-if="pageError" class="mb-4 glass-card border-red-500/30 text-red-400 px-4 py-3 rounded-xl flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-400 hover:text-red-300 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white inline-flex items-center gap-1.5">内容管理 <TipIcon text="管理评论/私信内容模板和敏感词库" /></h1>
      <button
        class="inline-flex items-center btn-aurora text-sm font-medium rounded-xl"
        @click="openCreateDialog"
      >
        <svg class="-ml-1 mr-2 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
          <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" />
        </svg>
        <span class="relative z-10">添加模板</span>
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
        class="glass-card p-5"
      >
        <div class="flex items-start justify-between">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-3 flex-wrap">
              <span class="font-semibold text-white">{{ tpl.name }}</span>
              <span :class="[categoryColors[tpl.category] || 'bg-gray-100 text-gray-800']"
                class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium">
                {{ categoryLabels[tpl.category] || tpl.category }}
              </span>
              <span v-if="tpl.variables && tpl.variables.length > 0"
                class="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700">
                {{ tpl.variables.length }} 个变量
              </span>
            </div>
            <p class="mt-2 text-sm text-slate-400 whitespace-pre-wrap">{{ tpl.body }}</p>
            <p v-if="tpl.variables && tpl.variables.length > 0" class="mt-1 text-xs text-slate-500">
              变量: {{ tpl.variables.map(v => '{' + v + '}').join(', ') }}
            </p>
          </div>
          <div class="ml-4 flex items-center gap-2 flex-shrink-0">
            <button
              class="inline-flex items-center px-3 py-1 text-sm font-medium text-emerald-400 hover:text-emerald-300 hover:bg-emerald-400/10 rounded transition-colors"
              @click="openGenerateDialog(tpl)"
            >
              AI 生成
            </button>
            <button
              class="inline-flex items-center px-3 py-1 text-sm font-medium text-cyan-400 hover:text-cyan-300 hover:bg-cyan-400/10 rounded transition-colors"
              @click="openEditDialog(tpl)"
            >
              编辑
            </button>
            <button
              class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-400/10 rounded transition-colors"
              @click="openDeleteDialog(tpl)"
            >
              删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Sensitive Words Section -->
    <div class="glass-card">
      <button
        class="w-full flex items-center justify-between px-6 py-4 text-left"
        @click="showWords = !showWords"
      >
        <h2 class="text-lg font-semibold text-slate-300 inline-flex items-center gap-1.5">敏感词库 ({{ words.length }}) <TipIcon text="包含敏感词的内容会被自动过滤不会发布，用于避免触发平台审核" /></h2>
        <svg :class="showWords ? 'rotate-180' : ''" class="w-5 h-5 text-slate-400 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      <div v-if="showWords" class="px-6 pb-4 border-t border-white/5">
        <!-- Add word input -->
        <div class="flex gap-2 mt-4 mb-4">
          <input
            v-model="newWord"
            type="text"
            class="flex-1 border border-white/10 bg-white/5 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
            placeholder="输入敏感词"
            @keyup.enter="handleAddWord"
          />
          <button
            :disabled="addingWord || !newWord.trim()"
            class="btn-aurora text-sm font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
            @click="handleAddWord"
          >
            <span class="relative z-10">添加</span>
          </button>
        </div>
        <!-- Word list -->
        <LoadingSpinner v-if="wordsLoading" />
        <div v-else-if="words.length === 0" class="text-sm text-slate-400 py-2">暂无敏感词</div>
        <div v-else class="flex flex-wrap gap-2">
          <span
            v-for="word in words"
            :key="word.id"
            class="inline-flex items-center gap-1 rounded-full bg-red-500/10 px-3 py-1 text-sm text-red-400 border border-red-500/20"
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
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-lg glass-card p-6 gradient-border">
                <DialogTitle class="text-lg font-medium text-white">
                  {{ isEditing ? '编辑模板' : '添加模板' }}
                </DialogTitle>
                <div v-if="formError" class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-sm px-3 py-2">
                  {{ formError }}
                </div>
                <form class="mt-4 space-y-4" @submit.prevent="handleSave">
                  <div>
                    <label for="tpl-name" class="block text-sm font-medium text-slate-300">名称 <span class="text-red-400">*</span></label>
                    <input id="tpl-name" v-model="form.name" type="text" required class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="例如：美食评论模板" />
                  </div>
                  <div>
                    <label for="tpl-category" class="flex items-center gap-1.5 text-sm font-medium text-slate-300">分类 <TipIcon text="评论=视频下方评论模板；私信=用户私信模板；回复=回复已有评论的模板" /></label>
                    <select id="tpl-category" v-model="form.category" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500">
                      <option value="comment">评论</option>
                      <option value="dm">私信</option>
                      <option value="reply">回复</option>
                    </select>
                  </div>
                  <div>
                    <label for="tpl-body" class="block text-sm font-medium text-slate-300">模板内容 <span class="text-red-400">*</span></label>
                    <textarea id="tpl-body" v-model="form.body" rows="4" required class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="支持 {keyword}、{username}、{video_title} 变量" />
                  </div>
                  <div>
                    <label for="tpl-vars" class="flex items-center gap-1.5 text-sm font-medium text-slate-300">变量 (逗号分隔) <TipIcon text="定义模板中的动态占位符。常用：keyword（搜索关键词）、username（目标用户名）、video_title（视频标题）" width="w-80" /></label>
                    <input id="tpl-vars" v-model="form.variables" type="text" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="keyword, username, video_title" />
                    <p class="mt-1 text-xs text-slate-400">在模板中使用 {变量名} 引用</p>
                  </div>
                  <div class="flex justify-end gap-3 pt-2">
                    <button type="button" class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors" @click="showFormDialog = false">取消</button>
                    <button type="submit" :disabled="saving" class="btn-aurora rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed">
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
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-lg glass-card p-6 gradient-border">
                <DialogTitle class="text-lg font-medium text-white">AI 内容生成</DialogTitle>
                <p class="mt-1 text-sm text-slate-400">模板: {{ generatingTemplate?.name }}</p>
                <div class="mt-3 bg-white/5 border border-white/5 rounded-lg p-3 text-sm text-slate-400 whitespace-pre-wrap">{{ generatingTemplate?.body }}</div>

                <div v-if="generateError" class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-sm px-3 py-2">
                  {{ generateError }}
                </div>

                <form class="mt-4 space-y-3" @submit.prevent="handleGenerate">
                  <div>
                    <label class="flex items-center gap-1.5 text-sm font-medium text-slate-300">搜索关键词 <TipIcon text="AI 生成内容时的上下文关键词，帮助生成更相关的内容" /></label>
                    <input v-model="generateForm.keyword" type="text" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="例如：美食探店" />
                  </div>
                  <div>
                    <label class="flex items-center gap-1.5 text-sm font-medium text-slate-300">目标用户名 <TipIcon text="要互动的目标用户昵称，AI 会在生成内容中引用" /></label>
                    <input v-model="generateForm.username" type="text" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="例如：美食家小明" />
                  </div>
                  <div>
                    <label class="flex items-center gap-1.5 text-sm font-medium text-slate-300">视频标题 <TipIcon text="目标视频的标题，AI 会基于此生成相关评论内容" /></label>
                    <input v-model="generateForm.video_title" type="text" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="例如：今天去了一家超好吃的火锅店" />
                  </div>

                  <!-- Result -->
                  <div v-if="generateResult" class="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-3">
                    <div class="flex items-start justify-between">
                      <p class="text-sm text-emerald-300 flex-1">{{ generateResult }}</p>
                      <button type="button" class="ml-2 text-emerald-400 hover:text-emerald-300 text-xs" @click="copyResult">复制</button>
                    </div>
                  </div>

                  <div class="flex justify-end gap-3 pt-2">
                    <button type="button" class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors" @click="showGenerateDialog = false">关闭</button>
                    <button type="submit" :disabled="generating" class="rounded-lg bg-gradient-to-r from-emerald-600 to-emerald-500 px-4 py-2 text-sm font-medium text-white hover:from-emerald-500 hover:to-emerald-400 shadow-lg shadow-emerald-500/25 disabled:opacity-50 disabled:cursor-not-allowed">
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
