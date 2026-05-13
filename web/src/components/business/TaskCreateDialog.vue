<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { Dialog, DialogPanel, DialogTitle, TransitionRoot, TransitionChild } from '@headlessui/vue'
import TipIcon from '../TipIcon.vue'
import { createTask, batchCreateTasks } from '../../api/tasks.js'
import { generateKeywords } from '../../api/content.js'
import { useToastStore } from '../../stores/toast.js'
import { TASK_TYPE_OPTIONS, SUB_TASK_TYPE_OPTIONS, NURTURE_DEFAULT_FORM } from '../../constants/tasks.js'

const props = defineProps({
  open: { type: Boolean, required: true },
  accounts: { type: Array, default: () => [] },
  groups: { type: Array, default: () => [] },
  devices: { type: Array, default: () => [] },
  templates: { type: Array, default: () => [] },
  promptTemplates: { type: Array, default: () => [] },
})

const emit = defineEmits(['close', 'created'])

const toast = useToastStore()

const creating = ref(false)
const createError = ref(null)
const selectionMode = ref('single')
const selectedGroupIds = ref([])
const selectedTemplateId = ref('')
const selectedPromptTemplateId = ref('')
const keywordExpandCount = ref(8)
const keywordGenerating = ref(false)

const form = reactive({ ...NURTURE_DEFAULT_FORM })

const nurtureMode = ref('simple')
const subTasks = ref([{ type: 'browse', count: 10, content_template_id: '' }])
const completionMode = ref('all')
const maxDuration = ref(60)
const nurtureKeywords = ref('')
const nurtureKeywordMatrix = ref([])
const nurtureKeywordGenerating = ref(false)
const nurtureKeywordExpandCount = ref(8)

function addSubTask() {
  subTasks.value.push({ type: 'browse', count: 5, content_template_id: '' })
}

function removeSubTask(index) {
  if (subTasks.value.length <= 1) return
  subTasks.value.splice(index, 1)
}

const filteredDevices = computed(() => {
  if (!form.account_id) return props.devices
  return props.devices.filter(d => !d.bound_account_id || d.bound_account_id === form.account_id)
})

const filteredTemplates = computed(() => {
  if (form.type === 'nurture') return []
  return props.templates
})

const isSearchType = computed(() =>
  ['search_comment', 'search_like', 'search_dm', 'reply_comment', 'collect'].includes(form.type)
)

watch(() => form.type, (newType) => {
  if (newType === 'nurture') selectedTemplateId.value = ''
})

watch(() => form.account_id, () => {
  form.device_id = ''
})

function buildParams() {
  if (form.type === 'nurture') {
    if (nurtureMode.value === 'advanced') {
      if (subTasks.value.length === 0) throw new Error('高级模式下至少需要一个子任务')
      const params = {
        sub_tasks: subTasks.value.map(st => ({
          type: st.type, count: st.count,
          ...(st.type === 'comment' && st.content_template_id ? { content_template_id: st.content_template_id } : {}),
        })),
        completion_mode: completionMode.value,
        duration: maxDuration.value,
      }
      const seeds = nurtureKeywords.value.split(/[,，\s]+/).map(s => s.trim()).filter(Boolean)
      if (seeds.length > 0) { params.keywords = seeds; params.expand_count = nurtureKeywordExpandCount.value }
      return params
    }
    return { duration: form.duration }
  }

  const params = { keyword: form.keyword, count: form.count }
  if (form.sort_by) params.sort_by = form.sort_by

  if (['search_comment', 'search_dm', 'reply_comment', 'collect'].includes(form.type)) {
    if (form.content) params.content = form.content
    if (selectedTemplateId.value) params.content_template_id = selectedTemplateId.value
  }

  if (['search_comment', 'search_dm', 'reply_comment', 'nurture'].includes(form.type)) {
    if (selectedPromptTemplateId.value) params.prompt_template_id = selectedPromptTemplateId.value
  }

  if (['reply_comment', 'search_comment', 'collect'].includes(form.type)) {
    params.video_count = form.video_count
    params.max_age_days = form.max_age_days
  }

  return params
}

async function handleCreate() {
  if (!form.type) { createError.value = '请选择任务类型'; return }
  if (selectionMode.value === 'single' && !form.account_id) { createError.value = '请选择账号'; return }
  if (selectionMode.value === 'group' && selectedGroupIds.value.length === 0) { createError.value = '请至少选择一个分组'; return }
  if (isSearchType.value && !form.keyword) { createError.value = '请输入搜索关键词'; return }

  creating.value = true
  createError.value = null

  try {
    const params = buildParams()
    if (selectionMode.value === 'group') {
      const payload = { type: form.type, group_ids: selectedGroupIds.value, params }
      if (form.device_id) payload.device_id = form.device_id
      const res = await batchCreateTasks(payload)
      toast.success(`批量创建成功：${res.data?.created || 0} 个任务`)
    } else {
      const payload = { type: form.type, account_id: form.account_id, params }
      if (form.device_id) payload.device_id = form.device_id
      await createTask(payload)
    }
    emit('created')
  } catch (e) {
    createError.value = e.response?.data?.message || e.response?.data?.detail || '创建失败，请重试'
  } finally {
    creating.value = false
  }
}

async function expandNurtureKeywords() {
  const seeds = nurtureKeywords.value.split(/[,，\s]+/).map(s => s.trim()).filter(Boolean)
  if (seeds.length === 0) return
  nurtureKeywordGenerating.value = true
  try {
    const allExpanded = []
    for (const seed of seeds) {
      const res = await generateKeywords(seed, nurtureKeywordExpandCount.value)
      allExpanded.push(...(res.data.keywords || []))
    }
    nurtureKeywordMatrix.value = [...new Set(allExpanded)]
    toast.success(`已扩展 ${nurtureKeywordMatrix.value.length} 个关键词`)
  } catch (e) {
    toast.error('关键词扩展失败，请重试')
  } finally {
    nurtureKeywordGenerating.value = false
  }
}

async function expandCreateKeyword() {
  const seed = form.keyword.trim()
  if (!seed) return
  keywordGenerating.value = true
  try {
    const seeds = seed.split(/[,，]/).map(s => s.trim()).filter(Boolean)
    const allExpanded = []
    for (const s of seeds) {
      const res = await generateKeywords(s, keywordExpandCount.value)
      allExpanded.push(...(res.data.keywords || []))
    }
    const seen = {}
    const merged = []
    for (const s of seeds) { if (!seen[s]) { seen[s] = true; merged.push(s) } }
    for (const kw of allExpanded) { if (!seen[kw]) { seen[kw] = true; merged.push(kw) } }
    form.keyword = merged.join('，')
  } catch (e) {
    toast.error('关键词扩展失败')
  } finally {
    keywordGenerating.value = false
  }
}

function openDialog() {
  Object.assign(form, NURTURE_DEFAULT_FORM)
  selectedTemplateId.value = ''
  selectedPromptTemplateId.value = ''
  selectionMode.value = 'single'
  selectedGroupIds.value = []
  createError.value = null
  nurtureKeywords.value = ''
  nurtureKeywordMatrix.value = []
  nurtureKeywordExpandCount.value = 8
}

watch(() => props.open, (val) => {
  if (val) openDialog()
})
</script>

<template>
  <TransitionRoot :show="open" as="template">
    <Dialog as="div" class="relative z-50" @close="emit('close')">
      <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
        <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
      </TransitionChild>
      <div class="fixed inset-0 overflow-y-auto">
        <div class="flex min-h-full items-center justify-center p-4">
          <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
            <DialogPanel class="glass-card w-full max-w-lg p-6 gradient-border">
              <DialogTitle class="text-lg font-medium text-white">创建任务</DialogTitle>

              <div v-if="createError" class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-3 py-2 rounded-lg">
                {{ createError }}
              </div>

              <form class="mt-4 space-y-4" @submit.prevent="handleCreate">
                <!-- Task Type -->
                <div>
                  <label class="block text-sm font-medium text-slate-300">
                    任务类型 <TipIcon text="选择要执行的任务类型。养号=模拟真实用户行为提升权重；搜索评论/点赞/私信=按关键词搜索视频后自动操作；评论回复=回复已有评论引流" /> <span class="text-red-400">*</span>
                  </label>
                  <select v-model="form.type" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                    <option v-for="opt in TASK_TYPE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                  </select>
                </div>

                <!-- Selection mode -->
                <div>
                  <label class="block text-sm font-medium text-slate-300 mb-2">选择方式 <TipIcon text="单账号=为一个账号创建任务；按分组=为分组内所有活跃账号批量创建任务" /></label>
                  <div class="flex gap-4">
                    <label class="flex items-center gap-2 cursor-pointer">
                      <input type="radio" v-model="selectionMode" value="single" class="text-purple-500 focus:ring-purple-500" />
                      <span class="text-sm text-slate-300">单账号</span>
                    </label>
                    <label class="flex items-center gap-2 cursor-pointer">
                      <input type="radio" v-model="selectionMode" value="group" class="text-purple-500 focus:ring-purple-500" />
                      <span class="text-sm text-slate-300">按分组批量</span>
                    </label>
                  </div>
                </div>

                <!-- Account (single) -->
                <div v-if="selectionMode === 'single'">
                  <label class="block text-sm font-medium text-slate-300">账号 <TipIcon text="选择执行此任务的抖音账号" /> <span class="text-red-400">*</span></label>
                  <select v-model="form.account_id" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                    <option value="" disabled>请选择账号</option>
                    <option v-for="acct in accounts" :key="acct.id" :value="acct.id">{{ acct.nickname || acct.douyin_id || acct.id }}</option>
                  </select>
                </div>

                <!-- Groups (batch) -->
                <div v-if="selectionMode === 'group'">
                  <label class="block text-sm font-medium text-slate-300 mb-1">选择分组 <TipIcon text="选中的分组内所有活跃账号都会创建相同任务" /> <span class="text-red-400">*</span></label>
                  <div class="max-h-40 overflow-y-auto rounded-lg border border-white/10 bg-white/5 p-2 space-y-1">
                    <label v-for="grp in groups" :key="grp.id" class="flex items-center gap-2 px-2 py-1 rounded hover:bg-white/5 cursor-pointer">
                      <input type="checkbox" :value="grp.id" v-model="selectedGroupIds" class="rounded border-white/20 bg-white/5 text-purple-500 focus:ring-purple-500" />
                      <span class="text-sm text-slate-300">{{ grp.name }} <span class="text-slate-500">({{ grp.member_count || 0 }} 个账号)</span></span>
                    </label>
                    <p v-if="groups.length === 0" class="text-sm text-slate-500 px-2 py-1">暂无分组，请先创建账号分组</p>
                  </div>
                </div>

                <!-- Device -->
                <div>
                  <label class="block text-sm font-medium text-slate-300">执行设备 <TipIcon text="选择运行任务的设备。留空则自动分配给该账号绑定的在线设备" /></label>
                  <select v-model="form.device_id" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                    <option value="">自动分配（绑定设备领取）</option>
                    <option v-for="dev in filteredDevices" :key="dev.id" :value="dev.id">{{ dev.name }} {{ dev.status === 'online' ? '(在线)' : '(离线)' }}</option>
                  </select>
                </div>

                <!-- Nurture params -->
                <template v-if="form.type === 'nurture'">
                  <div>
                    <label class="block text-sm font-medium text-slate-300 mb-2">养号模式 <TipIcon text="简单模式=设定总时长，系统自动随机操作；高级模式=自定义多个子任务按顺序执行" width="w-80" /></label>
                    <div class="flex gap-4">
                      <label class="flex items-center gap-2 cursor-pointer"><input type="radio" v-model="nurtureMode" value="simple" class="text-purple-500 focus:ring-purple-500" /><span class="text-sm text-slate-300">简单模式</span></label>
                      <label class="flex items-center gap-2 cursor-pointer"><input type="radio" v-model="nurtureMode" value="advanced" class="text-purple-500 focus:ring-purple-500" /><span class="text-sm text-slate-300">高级模式（子任务）</span></label>
                    </div>
                  </div>

                  <div v-if="nurtureMode === 'simple'">
                    <label class="block text-sm font-medium text-slate-300">养号时长（分钟） <TipIcon text="简单模式下养号操作的总持续时间，建议 15-60 分钟" /></label>
                    <input v-model.number="form.duration" type="number" min="1" max="120" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                  </div>

                  <div v-else class="space-y-3">
                    <div>
                      <label class="block text-sm font-medium text-slate-300 mb-1">子任务列表 <TipIcon text="按顺序配置多个操作步骤。每个子任务指定类型和执行次数" /></label>
                      <p class="mt-1 text-xs text-slate-500">浏览/观看=刷视频，点赞/评论/关注=互动操作</p>
                      <div class="space-y-2">
                        <div v-for="(st, idx) in subTasks" :key="idx" class="flex items-center gap-2">
                          <select v-model="st.type" class="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-slate-200">
                            <option v-for="opt in SUB_TASK_TYPE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                          </select>
                          <input v-model.number="st.count" type="number" min="1" max="100" class="w-20 rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-slate-200" placeholder="次数" />
                          <select v-if="st.type === 'comment'" v-model="st.content_template_id" class="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5 text-sm text-slate-200">
                            <option value="">选择模板</option>
                            <option v-for="tpl in templates" :key="tpl.id" :value="tpl.id">{{ tpl.name }}</option>
                          </select>
                          <button type="button" @click="removeSubTask(idx)" class="text-red-400 hover:text-red-300">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                          </button>
                        </div>
                      </div>
                      <button type="button" @click="addSubTask" class="mt-2 text-sm text-cyan-400 hover:text-cyan-300">+ 添加子任务</button>
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                      <div>
                        <label class="block text-sm font-medium text-slate-300">完成模式 <TipIcon text="全部完成=所有子任务都必须完成才算成功；任一完成=任意一个子任务完成即可" /></label>
                        <select v-model="completionMode" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                          <option value="all">全部完成</option><option value="any">任一完成</option>
                        </select>
                      </div>
                      <div>
                        <label class="block text-sm font-medium text-slate-300">最大时长（分钟） <TipIcon text="高级模式下整个养号任务的最大执行时间，超时自动停止" /></label>
                        <input v-model.number="maxDuration" type="number" min="1" max="240" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                      </div>
                    </div>
                  </div>

                  <!-- Nurture keyword filter -->
                  <div>
                    <label class="block text-sm font-medium text-slate-300 mb-1">关键词过滤 <TipIcon text="输入种子关键词，AI 扩展为关键词矩阵。养号时只对匹配关键词的内容进行点赞/评论/关注，不匹配的内容直接跳过。留空则不限制" /></label>
                    <div class="flex gap-2">
                      <input v-model="nurtureKeywords" type="text" class="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="输入种子关键词，逗号分隔，如：养生,中医,食疗" />
                      <input v-model.number="nurtureKeywordExpandCount" type="number" min="3" max="30" class="w-16 rounded-lg border border-white/10 bg-white/5 px-2 py-2 text-sm text-slate-200 text-center" title="扩展数量" />
                      <button type="button" @click="expandNurtureKeywords" :disabled="nurtureKeywordGenerating || !nurtureKeywords.trim()" class="px-3 py-2 rounded-lg text-sm font-medium bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30 disabled:opacity-50">
                        {{ nurtureKeywordGenerating ? '扩展中...' : 'AI 扩展' }}
                      </button>
                    </div>
                    <div v-if="nurtureKeywordMatrix.length > 0" class="mt-2 flex flex-wrap gap-1.5">
                      <span v-for="(kw, idx) in nurtureKeywordMatrix" :key="idx" class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-purple-500/20 text-purple-300">
                        {{ kw }}<button type="button" @click="nurtureKeywordMatrix.splice(idx, 1)" class="hover:text-purple-100">&times;</button>
                      </span>
                    </div>
                  </div>
                </template>

                <!-- Search type params -->
                <template v-if="isSearchType">
                  <div>
                    <label class="block text-sm font-medium text-slate-300">搜索关键词 <TipIcon text="输入种子词，点击 AI 扩展自动生成相关关键词" /> <span class="text-red-400">*</span></label>
                    <div class="flex gap-2 mt-1">
                      <input v-model="form.keyword" type="text" maxlength="200" class="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="例：美食、养生" />
                      <input v-model.number="keywordExpandCount" type="number" min="3" max="30" class="w-16 rounded-lg border border-white/10 bg-white/5 px-2 py-2 text-sm text-slate-200 text-center" title="扩展数量" />
                      <button type="button" @click="expandCreateKeyword" :disabled="keywordGenerating" class="px-3 py-2 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-500 disabled:opacity-50 transition-colors whitespace-nowrap">{{ keywordGenerating ? '...' : 'AI 扩展' }}</button>
                    </div>
                  </div>

                  <div>
                    <label class="block text-sm font-medium text-slate-300">排序方式 <TipIcon text="控制搜索结果排序，影响目标视频选择优先级" /></label>
                    <select v-model="form.sort_by" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                      <option value="">默认排序</option>
                      <option value="latest">最新发布</option>
                      <option value="most_liked">最多点赞</option>
                    </select>
                  </div>

                  <div>
                    <label class="block text-sm font-medium text-slate-300">{{ form.type === 'reply_comment' ? '每视频评论数' : form.type === 'collect' ? '每视频采集数' : form.type === 'search_like' ? '点赞数' : '处理数量' }} <TipIcon :text="form.type === 'search_like' ? '要处理的点赞总数' : '每个视频中要处理的数量'" /></label>
                    <input v-model.number="form.count" type="number" min="1" :max="50" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                  </div>

                  <!-- 视频数（reply_comment / search_comment / collect 共用） -->
                  <div v-if="['reply_comment', 'search_comment', 'collect'].includes(form.type)">
                    <label class="block text-sm font-medium text-slate-300">处理视频数 <TipIcon text="每个关键词要处理的视频数量" /></label>
                    <input v-model.number="form.video_count" type="number" min="1" max="50" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                  </div>
                </template>

                <!-- 评论最大天数（reply_comment / collect 共用） -->
                <div v-if="['reply_comment', 'collect'].includes(form.type)">
                  <label class="block text-sm font-medium text-slate-300">评论最大天数 <TipIcon text="只处理在此天数内发布的评论，超过的将被忽略" /></label>
                  <input v-model.number="form.max_age_days" type="number" min="1" max="90" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                </div>

                <!-- Content template + text -->
                <template v-if="['search_comment', 'search_dm', 'reply_comment', 'collect'].includes(form.type)">
                  <div v-if="filteredTemplates.length > 0">
                    <label class="block text-sm font-medium text-slate-300">内容模板 <TipIcon text="选择预设的评论/私信模板，模板中的变量会自动替换为实际值" /></label>
                    <select v-model="selectedTemplateId" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                      <option value="">不使用模板</option>
                      <option v-for="tpl in filteredTemplates" :key="tpl.id" :value="tpl.id">{{ tpl.name }} ({{ tpl.category }})</option>
                    </select>
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-slate-300">{{ form.type === 'search_dm' ? '私信内容' : '评论/私信内容' }} <TipIcon text="发送的内容文本。支持 {keyword}、{username}、{video_title} 变量。留空则使用模板或 AI 生成" width="w-80" /></label>
                    <textarea v-model="form.content" rows="3" maxlength="500" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" :placeholder="form.type === 'reply_comment' ? '留空则使用 AI 生成招呼语' : '输入内容...'" />
                  </div>
                </template>

                <!-- Prompt template -->
                <div v-if="promptTemplates.length > 0">
                  <label class="block text-sm font-medium text-slate-300">提示词模版 <TipIcon text="选择 AI 提示词模版，控制 AI 分析评论、生成回复的风格策略。留空则使用设备端默认模版" /></label>
                  <select v-model="selectedPromptTemplateId" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                    <option value="">设备默认模版</option>
                    <option v-for="tpl in promptTemplates" :key="tpl.id" :value="tpl.id">{{ tpl.name }} ({{ tpl.industry }})</option>
                  </select>
                </div>

                <div class="flex justify-end gap-3 pt-2">
                  <button type="button" class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors" @click="emit('close')">取消</button>
                  <button type="submit" :disabled="creating" class="btn-aurora rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed">
                    <span class="relative z-10">{{ creating ? '创建中...' : '创建' }}</span>
                  </button>
                </div>
              </form>
            </DialogPanel>
          </TransitionChild>
        </div>
      </div>
    </Dialog>
  </TransitionRoot>
</template>
