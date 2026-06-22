<!-- 运营业务组件：展示账号、频道、关键词或任务创建相关业务交互。 -->
<script setup>
import { computed, ref, watch } from 'vue'
import { Dialog, DialogPanel, DialogTitle, TransitionRoot, TransitionChild } from '@headlessui/vue'
import TipIcon from '../TipIcon.vue'
import { batchCreateTasks } from '../../api/tasks.js'
import { generateKeywords } from '../../api/content.js'
import { listDMSequences } from '../../api/dmSequences.js'
import { useToastStore } from '../../stores/toast.js'
import { KEYWORD_ACTION_TYPE_OPTIONS, SORT_BY_OPTIONS } from '../../constants/tasks.js'

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

const keywordSeed = ref('')
const keywordList = ref([])
const keywordGenerating = ref(false)
const keywordError = ref(null)
const keywordActionType = ref('search_comment')
const keywordSelectionMode = ref('single')
const keywordSelectedGroupIds = ref([])
const keywordSingleAccountId = ref('')
const keywordDeviceId = ref('')
const keywordSortBy = ref('')
const keywordTemplateId = ref('')
const keywordPromptTemplateId = ref('')
const keywordContent = ref('')
const keywordDMSequenceId = ref('')
const dmSequences = ref([])
const keywordMaxAgeDays = ref(5)
const keywordMaxAgeUnit = ref('days')
const keywordGenerateCount = ref(10)
const keywordProcessingCount = ref(5)
const keywordVideoCount = ref(3)
const keywordShareLinks = ref('')  // 分享链接（collect 类型专用）
const keywordSkipReply = ref(false)  // reply_comment: 跳过回复，仅关注+私信
const creating = ref(false)

const keywordProcessingCountMeta = computed(() => {
  if (keywordActionType.value === 'search_dm') {
    return {
      label: '私信数量',
      tip: '要发送私信的目标数量，范围 1-50；私信任务不支持 -1 全量。',
      min: 1,
      max: 50,
    }
  }
  if (keywordActionType.value === 'search_like') {
    return {
      label: '点赞数',
      tip: '要点赞的数量，范围 1-30。',
      min: 1,
      max: 30,
    }
  }
  return {
    label: '每视频评论数',
    tip: '每个视频要处理的评论数量，-1=全量。',
    min: -1,
    max: null,
  }
})

// 前端业务函数：协调 validateKeywordProcessingCount 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 validateKeywordProcessingCount 对应业务流程的处理结果。
function validateKeywordProcessingCount() {
  if (keywordActionType.value === 'search_dm' && (keywordProcessingCount.value < 1 || keywordProcessingCount.value > 50)) {
    keywordError.value = '搜索私信数量需在 1-50 之间'
    return false
  }
  return true
}

// 前端业务函数：协调 resetForm 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 resetForm 对应业务流程的处理结果。
function resetForm() {
  keywordSeed.value = ''
  keywordList.value = []
  keywordError.value = null
  creating.value = false
  keywordActionType.value = 'search_comment'
  keywordSelectionMode.value = 'single'
  keywordSelectedGroupIds.value = []
  keywordSingleAccountId.value = ''
  keywordDeviceId.value = ''
  keywordSortBy.value = ''
  keywordTemplateId.value = ''
  keywordPromptTemplateId.value = ''
  keywordContent.value = ''
  keywordMaxAgeDays.value = 5
  keywordMaxAgeUnit.value = 'days'
  keywordGenerateCount.value = 10
  keywordProcessingCount.value = 5
  keywordVideoCount.value = 3
  keywordSkipReply.value = false
}

watch(() => props.open, async (val) => {
  if (val) {
    resetForm()
    try { const res = await listDMSequences(); dmSequences.value = res.data.sequences || [] } catch (e) {}
  }
})

watch(keywordActionType, (newType) => {
  if (newType === 'search_dm' && keywordProcessingCount.value < 1) {
    keywordProcessingCount.value = 5
  }
})

// 前端业务函数：协调 handleGenerateKeywords 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 handleGenerateKeywords 对应业务流程的处理结果。
async function handleGenerateKeywords() {
  if (!keywordSeed.value.trim()) { keywordError.value = '请输入种子关键词'; return }
  keywordGenerating.value = true
  keywordError.value = null
  try {
    const res = await generateKeywords(keywordSeed.value.trim(), keywordGenerateCount.value)
    const expanded = res.data.keywords || []
    const seen = new Set([keywordSeed.value.trim()])
    const merged = [keywordSeed.value.trim()]
    for (const kw of expanded) { if (!seen.has(kw)) { seen.add(kw); merged.push(kw) } }
    keywordList.value = merged
  } catch (e) {
    keywordError.value = e.response?.data?.detail || '生成失败，请重试'
  } finally {
    keywordGenerating.value = false
  }
}

// 前端业务函数：协调 removeKeyword 对应的页面流程、接口调用或状态转换。
// 入参：idx 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 removeKeyword 对应业务流程的处理结果。
function removeKeyword(idx) { keywordList.value.splice(idx, 1) }

// 前端业务函数：协调 handleBatchCreateKeywordTasks 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 handleBatchCreateKeywordTasks 对应业务流程的处理结果。
async function handleBatchCreateKeywordTasks() {
  if (keywordList.value.length === 0) { keywordError.value = '请先生成关键词'; return }
  if (keywordSelectionMode.value === 'single' && !keywordSingleAccountId.value) { keywordError.value = '请选择账号'; return }
  if (keywordSelectionMode.value === 'group' && keywordSelectedGroupIds.value.length === 0) { keywordError.value = '请至少选择一个分组'; return }
  if (keywordActionType.value === 'reply_comment' && keywordProcessingCount.value === 0 && !keywordSkipReply.value) { keywordError.value = '每视频评论数为 0 时请开启"跳过回复"开关，或设置 -1(全量)/>0(指定数量)'; return }

  if (!validateKeywordProcessingCount()) return

  creating.value = true
  keywordError.value = null

  try {
    const kwList = keywordList.value.map(k => typeof k === 'string' ? k.trim() : k).filter(Boolean)
    if (kwList.length === 0) { keywordError.value = '关键词列表为空'; return }

    const params = { keyword: kwList[0] || '', keywords: kwList, count: keywordProcessingCount.value }
    if (keywordSortBy.value) params.sort_by = keywordSortBy.value
    params.max_age_days = keywordMaxAgeDays.value || 30
    if (keywordMaxAgeUnit.value) params.max_age_unit = keywordMaxAgeUnit.value
    if (keywordDMSequenceId.value) { params.dm_sequence_id = keywordDMSequenceId.value }
    else if (keywordTemplateId.value) { params.content_template_id = keywordTemplateId.value }
    else if (keywordContent.value) { params.content = keywordContent.value }
    if (keywordPromptTemplateId.value) params.prompt_template_id = keywordPromptTemplateId.value
    if (['reply_comment', 'search_comment', 'collect'].includes(keywordActionType.value)) {
      params.video_count = keywordVideoCount.value
    }
    if (keywordActionType.value === 'reply_comment' && keywordSkipReply.value) {
      params.skip_reply = true
    }
    if (keywordActionType.value === 'collect' && keywordShareLinks.value.trim()) {
      params.share_links = (keywordShareLinks.value.match(/https?:\/\/v\.douyin\.com\/[A-Za-z0-9_?=&%]+\/?/g) || [])
    }

    const payload = {
      type: keywordActionType.value,
      params,
      ...(keywordDeviceId.value ? { device_id: keywordDeviceId.value } : {}),
    }

    if (keywordSelectionMode.value === 'group') {
      payload.group_ids = keywordSelectedGroupIds.value
    } else {
      payload.account_ids = [keywordSingleAccountId.value]
    }

    const resp = await batchCreateTasks(payload)
    const created = resp.data?.created || 0
    const mode = resp.data?.mode || ''
    toast.success(mode === 'channel' ? `通道已创建，${created} 个关键词任务将自动分发` : `成功创建 ${created} 个任务`)
    emit('created')
  } catch (e) {
    keywordError.value = e.response?.data?.detail || '创建失败'
  } finally {
    creating.value = false
  }
}
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
            <DialogPanel class="glass-card w-full max-w-2xl p-6 gradient-border">
              <DialogTitle class="text-lg font-medium text-white">关键词搜索</DialogTitle>

              <div v-if="keywordError" class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-3 py-2 rounded-lg">{{ keywordError }}</div>

              <div class="mt-4 space-y-4 max-h-[70vh] overflow-y-auto pr-1">
                <!-- Seed keyword -->
                <div class="flex gap-2 items-end">
                  <div class="flex-1">
                    <label class="block text-sm font-medium text-slate-300 mb-1">种子关键词 <TipIcon text="输入一个基础关键词，AI 会自动扩展出多个相关搜索词" /></label>
                    <input v-model="keywordSeed" type="text" maxlength="50" class="block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="输入种子关键词，如：美食" @keyup.enter="handleGenerateKeywords" />
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-slate-300 mb-1">生成数量</label>
                    <input v-model.number="keywordGenerateCount" type="number" min="1" max="30" class="w-20 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                  </div>
                  <button type="button" :disabled="keywordGenerating" class="px-4 py-2 bg-gradient-to-r from-emerald-600 to-emerald-500 text-white text-sm font-medium rounded-lg hover:from-emerald-500 hover:to-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-emerald-500/25" @click="handleGenerateKeywords">
                    {{ keywordGenerating ? '生成中...' : 'AI 扩展' }}
                  </button>
                </div>

                <!-- Keyword matrix -->
                <div v-if="keywordList.length > 0">
                  <label class="block text-sm font-medium text-slate-300 mb-1">关键词矩阵 <TipIcon text="AI 生成的关键词列表，点击 X 可删除不需要的，最终保留的将各创建一个任务" /></label>
                  <div class="flex flex-wrap gap-2 p-3 border border-white/10 rounded-lg max-h-32 overflow-y-auto">
                    <span v-for="(kw, idx) in keywordList" :key="idx" class="inline-flex items-center gap-1 px-2.5 py-1 bg-purple-500/15 text-purple-300 text-sm rounded-full border border-purple-500/25">
                      {{ kw }}
                      <button type="button" @click="removeKeyword(idx)" class="text-purple-400 hover:text-purple-300">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                      </button>
                    </span>
                  </div>
                </div>

                <!-- 分享链接（collect 专用） -->
                <div v-if="keywordActionType === 'collect'">
                  <label class="block text-sm font-medium text-slate-300 mb-1">分享链接 <TipIcon text="粘贴抖音分享链接，每行一个。通过链接直接打开视频采集，无需关键词" width="w-72" /></label>
                  <textarea v-model="keywordShareLinks" rows="3" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="直接粘贴抖音分享口令，自动提取链接"></textarea>
                </div>

                <!-- Action type + count + video_count -->
                <div class="grid grid-cols-3 gap-3">
                  <div>
                    <label class="block text-sm font-medium text-slate-300">操作类型 <TipIcon text="批量创建任务时使用的操作类型" /></label>
                    <select v-model="keywordActionType" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                      <option v-for="opt in KEYWORD_ACTION_TYPE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                    </select>
                  </div>
                  <div v-if="['reply_comment', 'search_comment', 'collect'].includes(keywordActionType)">
                    <label class="block text-sm font-medium text-slate-300">处理视频数 <TipIcon text="每个关键词要处理的视频数量，-1=全量" /></label>
                    <input v-model.number="keywordVideoCount" type="number" min="-1" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-slate-300">{{ keywordProcessingCountMeta.label }} <TipIcon :text="keywordProcessingCountMeta.tip" /></label>
                    <input v-model.number="keywordProcessingCount" type="number" :min="keywordProcessingCountMeta.min" :max="keywordProcessingCountMeta.max || undefined" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                  </div>
                </div>

                <!-- skip_reply 开关（仅 reply_comment） -->
                <div v-if="keywordActionType === 'reply_comment'" class="flex items-center justify-between p-3 rounded-lg border"
                  :class="keywordSkipReply ? 'border-amber-500/30 bg-amber-500/5' : 'border-white/10 bg-white/[0.02]'">
                  <div>
                    <span class="text-sm font-medium" :class="keywordSkipReply ? 'text-amber-300' : 'text-slate-300'">跳过回复</span>
                    <p class="text-xs text-slate-500 mt-0.5">
                      {{ keywordSkipReply ? '仅关注+私信，不回复评论。每视频评论数=-1 直接跳过，每视频评论数>0 先完成指定回复' : '正常回复+关注+私信' }}
                    </p>
                  </div>
                  <button type="button"
                    @click="keywordSkipReply = !keywordSkipReply"
                    class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors flex-shrink-0"
                    :class="keywordSkipReply ? 'bg-amber-500' : 'bg-white/10'">
                    <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
                      :class="keywordSkipReply ? 'translate-x-6' : 'translate-x-1'" />
                  </button>
                </div>

                <!-- Selection mode -->
                <div>
                  <label class="block text-sm font-medium text-slate-300 mb-2">选择方式</label>
                  <div class="flex gap-4">
                    <label class="flex items-center gap-2 cursor-pointer"><input type="radio" v-model="keywordSelectionMode" value="single" class="text-purple-500 focus:ring-purple-500" /><span class="text-sm text-slate-300">单账号</span></label>
                    <label class="flex items-center gap-2 cursor-pointer"><input type="radio" v-model="keywordSelectionMode" value="group" class="text-purple-500 focus:ring-purple-500" /><span class="text-sm text-slate-300">按分组批量</span></label>
                  </div>
                </div>

                <div v-if="keywordSelectionMode === 'single'">
                  <label class="block text-sm font-medium text-slate-300">选择账号 <span class="text-red-400">*</span></label>
                  <select v-model="keywordSingleAccountId" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                    <option value="" disabled>请选择账号</option>
                    <option v-for="acct in accounts" :key="acct.id" :value="acct.id">{{ acct.nickname || acct.douyin_id || acct.id }}</option>
                  </select>
                </div>

                <div v-if="keywordSelectionMode === 'group'">
                  <label class="block text-sm font-medium text-slate-300 mb-1">选择分组 <span class="text-red-400">*</span></label>
                  <div class="max-h-32 overflow-y-auto rounded-lg border border-white/10 bg-white/5 p-2 space-y-1">
                    <label v-for="grp in groups" :key="grp.id" class="flex items-center gap-2 px-2 py-1 rounded hover:bg-white/5 cursor-pointer">
                      <input type="checkbox" :value="grp.id" v-model="keywordSelectedGroupIds" class="rounded border-white/20 bg-white/5 text-purple-500 focus:ring-purple-500" />
                      <span class="text-sm text-slate-300">{{ grp.name }} <span class="text-slate-500">({{ grp.member_count || 0 }})</span></span>
                    </label>
                    <p v-if="groups.length === 0" class="text-sm text-slate-500 px-2 py-1">暂无分组</p>
                  </div>
                </div>

                <!-- Sort by -->
                <div>
                  <label class="block text-sm font-medium text-slate-300">排序方式</label>
                  <select v-model="keywordSortBy" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                    <option v-for="opt in SORT_BY_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                  </select>
                </div>

                <div v-if="['search_comment', 'reply_comment', 'collect'].includes(keywordActionType)">
                  <label class="block text-sm font-medium text-slate-300">评论最大时间 <TipIcon text="只处理在此时间内发布的评论，-1=不限" /></label>
                  <div class="mt-1 flex gap-2">
                    <input v-model.number="keywordMaxAgeDays" type="number" min="-1" class="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200" />
                    <select v-model="keywordMaxAgeUnit" class="w-24 rounded-lg border border-white/10 bg-white/5 px-2 py-2 text-sm text-slate-200">
                      <option value="days">天</option>
                      <option value="hours">时</option>
                      <option value="minutes">分</option>
                      <option value="seconds">秒</option>
                    </select>
                  </div>
                </div>

                <template v-if="['search_comment', 'search_dm', 'reply_comment'].includes(keywordActionType)">
                  <div v-if="dmSequences.length > 0 && ['search_dm', 'reply_comment'].includes(keywordActionType)">
                    <label class="block text-sm font-medium text-slate-300">DM 序列模板</label>
                    <select v-model="keywordDMSequenceId" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                      <option value="">不使用序列</option>
                      <option v-for="seq in dmSequences" :key="seq.id" :value="seq.id">{{ seq.name }} ({{ seq.message_count }}条)</option>
                    </select>
                  </div>
                  <div v-if="!keywordDMSequenceId && templates.length > 0">
                    <label class="block text-sm font-medium text-slate-300">内容模板</label>
                    <select v-model="keywordTemplateId" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                      <option value="">不使用模板</option>
                      <option v-for="tpl in templates" :key="tpl.id" :value="tpl.id">{{ tpl.name }} ({{ tpl.category }})</option>
                    </select>
                  </div>
                  <div v-if="!keywordDMSequenceId">
                    <label class="block text-sm font-medium text-slate-300">评论/私信内容 <TipIcon text="留空则使用模板或 AI 生成" /></label>
                    <textarea v-model="keywordContent" rows="2" maxlength="500" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="输入内容...（留空用模板）" />
                  </div>
                </template>

                <div v-if="promptTemplates.length > 0">
                  <label class="block text-sm font-medium text-slate-300">提示词模版 <TipIcon text="选择 AI 提示词模版，留空则使用设备端默认模版" /></label>
                  <select v-model="keywordPromptTemplateId" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                    <option value="">设备默认模版</option>
                    <option v-for="tpl in promptTemplates" :key="tpl.id" :value="tpl.id">{{ tpl.name }} ({{ tpl.industry }})</option>
                  </select>
                </div>

                <div>
                  <label class="block text-sm font-medium text-slate-300">执行设备</label>
                  <select v-model="keywordDeviceId" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200">
                    <option value="">自动分配</option>
                    <option v-for="dev in devices" :key="dev.id" :value="dev.id">{{ dev.name }} {{ dev.status === 'online' ? '(在线)' : '(离线)' }}</option>
                  </select>
                </div>
              </div>

              <div class="flex justify-end gap-3 pt-4">
                <button type="button" class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors" @click="emit('close')">取消</button>
                <button type="button" :disabled="creating || keywordList.length === 0" class="btn-aurora rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed" @click="handleBatchCreateKeywordTasks">
                  <span class="relative z-10">{{ creating ? '创建中...' : `批量创建 ${keywordList.length} 个任务` }}</span>
                </button>
              </div>
            </DialogPanel>
          </TransitionChild>
        </div>
      </div>
    </Dialog>
  </TransitionRoot>
</template>
