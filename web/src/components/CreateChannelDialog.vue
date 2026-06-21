<!-- 管理端通用组件：提供业务页面复用的展示、反馈或交互能力。 -->
<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="bg-slate-800 rounded-xl shadow-xl w-full max-w-lg mx-4 p-6 border border-slate-700">
      <h2 class="text-lg font-bold text-white mb-4">创建通道</h2>
      <form @submit.prevent="submit">
        <!-- Group select -->
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-300 mb-1">账号分组</label>
          <select v-model="form.group_id" class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500">
            <option value="" disabled>选择分组</option>
            <option v-for="g in groups" :key="g.id" :value="g.id">{{ g.name }}</option>
          </select>
        </div>

        <!-- Task type -->
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-300 mb-1">任务类型</label>
          <select v-model="form.task_type" class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500">
            <option value="search_comment">评论搜索</option>
            <option value="search_like">点赞搜索</option>
            <option value="search_dm">私信搜索</option>
            <option value="reply_comment">回复评论</option>
          </select>
        </div>

        <!-- Account mode -->
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-300 mb-1">账号模式</label>
          <select v-model="form.account_mode" class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500">
            <option value="round_robin">分摊（轮转）</option>
            <option value="single_account">单账号</option>
          </select>
        </div>

        <!-- Single account select -->
        <div v-if="form.account_mode === 'single_account'" class="mb-4">
          <label class="block text-sm font-medium text-slate-300 mb-1">指定账号</label>
          <select v-model="form.account_id" class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500">
            <option value="" disabled>选择账号</option>
            <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.nickname }}</option>
          </select>
        </div>

        <!-- Keywords -->
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-300 mb-1">种子关键词（每行一个）</label>
          <div class="flex gap-2 mb-2">
            <input
              v-model="seedKeyword"
              class="flex-1 bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-blue-500"
              placeholder="输入主题词，如：美食探店"
              @keydown.enter.prevent="expandKeywords"
            />
            <button
              type="button"
              @click="expandKeywords"
              :disabled="keywordGenerating"
              class="px-3 py-2 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-500 disabled:opacity-50 transition-colors whitespace-nowrap"
            >
              {{ keywordGenerating ? '生成中...' : 'AI 扩展' }}
            </button>
          </div>
          <textarea
            v-model="keywordsText"
            rows="4"
            class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            placeholder="种子关键词 + AI 扩展词&#10;每行一个关键词&#10;也可手动编辑"
          />
        </div>

        <!-- Common params -->
        <div class="grid grid-cols-2 gap-3 mb-4">
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-1">处理数量</label>
            <input
              v-model.number="formParams.count"
              type="number"
              min="-1"
              class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
            />
          </div>
          <div v-if="['reply_comment', 'search_comment', 'collect'].includes(form.task_type)">
            <label class="block text-sm font-medium text-slate-300 mb-1">处理视频数 <span class="text-slate-500 text-xs">-1=全量</span></label>
            <input
              v-model.number="formParams.video_count"
              type="number"
              min="-1"
              class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        <!-- 评论最大天数（reply_comment / search_comment / collect 共用） -->
        <template v-if="['reply_comment', 'search_comment', 'collect'].includes(form.task_type)">
          <div class="grid grid-cols-2 gap-3 mb-4">
            <div>
              <label class="block text-sm font-medium text-slate-300 mb-1">评论最大时间 <span class="text-slate-500 text-xs">-1=不限</span></label>
              <div class="flex gap-2">
                <input
                  v-model.number="formParams.max_age_days"
                  type="number"
                  min="-1"
                  class="flex-1 bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
                />
                <select v-model="formParams.max_age_unit" class="w-20 bg-slate-700 border border-slate-600 rounded-lg px-2 py-2 text-white text-sm focus:outline-none focus:border-blue-500">
                  <option value="days">天</option>
                  <option value="hours">时</option>
                  <option value="minutes">分</option>
                  <option value="seconds">秒</option>
                </select>
              </div>
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-300 mb-1">排序方式</label>
              <select v-model="formParams.sort_by" class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500">
                <option value="">默认</option>
                <option value="latest">最新发布</option>
                <option value="most_liked">最多点赞</option>
              </select>
            </div>
          </div>
        </template>

        <!-- DM sequence -->
        <div v-if="['search_dm', 'reply_comment'].includes(form.task_type) && dmSequences.length > 0" class="mb-4">
          <label class="block text-sm font-medium text-slate-300 mb-1">DM 序列模板（可选）</label>
          <select v-model="dmSequenceId" class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500">
            <option value="">不使用序列</option>
            <option v-for="seq in dmSequences" :key="seq.id" :value="seq.id">{{ seq.name }} ({{ seq.message_count }}条)</option>
          </select>
        </div>

        <!-- DM / comment content -->
        <div v-if="['search_comment', 'search_dm', 'reply_comment'].includes(form.task_type)" class="mb-4">
          <label class="block text-sm font-medium text-slate-300 mb-1">
            {{ form.task_type === 'search_dm' ? '私信' : '评论/私信' }}内容（可选）
          </label>
          <textarea
            v-model="formParams.content"
            rows="2"
            maxlength="500"
            :disabled="!!dmSequenceId"
            class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 text-sm focus:outline-none focus:border-blue-500 disabled:opacity-50"
            :placeholder="dmSequenceId ? '已选择DM序列模板，此处内容将被忽略' : (form.task_type === 'reply_comment' ? '留空则 AI 生成回复和私信' : '留空则 AI 自动生成')"
          />
        </div>

        <!-- Params template (JSON) for advanced -->
        <details class="mb-4">
          <summary class="text-sm text-slate-400 cursor-pointer hover:text-slate-300">高级参数 (JSON)</summary>
          <textarea
            v-model="paramsText"
            rows="2"
            class="mt-2 w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 font-mono text-sm focus:outline-none focus:border-blue-500"
            placeholder='{"count": 5}'
          />
        </details>

        <!-- Error -->
        <p v-if="error" class="text-red-400 text-sm mb-4">{{ error }}</p>

        <!-- Actions -->
        <div class="flex justify-end gap-3">
          <button type="button" @click="$emit('close')" class="px-4 py-2 text-slate-400 hover:text-white transition-colors">取消</button>
          <button type="submit" :disabled="submitting" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
            {{ submitting ? '创建中...' : '创建' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { createChannel } from '../api/channels.js'
import { listGroups, listMembers } from '../api/accountGroups.js'
import { generateKeywords } from '../api/content.js'
import { listDMSequences } from '../api/dmSequences.js'

const emit = defineEmits(['close', 'created'])

const groups = ref([])
const accounts = ref([])
const form = ref({
  group_id: '',
  task_type: 'search_comment',
  account_mode: 'round_robin',
  account_id: '',
})
const keywordsText = ref('')
const seedKeyword = ref('')
const keywordGenerating = ref(false)
const paramsText = ref('{}')
const formParams = ref({
  count: 10,
  video_count: 5,
  max_age_days: 5,
  max_age_unit: 'days',
  sort_by: '',
  content: '',
})
const dmSequenceId = ref('')
const dmSequences = ref([])
const error = ref('')
const submitting = ref(false)

onMounted(async () => {
  try {
    const resp = await listGroups()
    groups.value = resp.data.groups || resp.data || []
  } catch (e) {
    console.error('Failed to load groups:', e)
  }
  try { var sr = await listDMSequences(); dmSequences.value = sr.data.sequences || [] } catch (e) {}
})

// Load group members when group changes
watch(() => form.value.group_id, async (gid) => {
  if (!gid) return
  try {
    const resp = await listMembers(gid, { status: 'active' })
    accounts.value = resp.data.members || resp.data || []
  } catch (e) {
    console.error('Failed to load group members:', e)
  }
})

async function expandKeywords() {
  var seed = seedKeyword.value.trim()
  if (!seed) return
  keywordGenerating.value = true
  try {
    var resp = await generateKeywords(seed, 10)
    var newKeywords = resp.data.keywords || []
    // 合并种子关键词和 AI 扩展词，去重
    var existing = keywordsText.value.split('\n').map(function (k) { return k.trim() }).filter(Boolean)
    var seedWords = seed.split(/[,，\s]+/).filter(Boolean)
    var all = seedWords.slice()
    for (var i = 0; i < newKeywords.length; i++) {
      var kw = newKeywords[i].trim()
      if (all.indexOf(kw) === -1) all.push(kw)
    }
    // 追加已有手动输入的关键词（不在种子词和扩展词中的）
    for (var j = 0; j < existing.length; j++) {
      if (all.indexOf(existing[j]) === -1) all.push(existing[j])
    }
    keywordsText.value = all.join('\n')
    seedKeyword.value = ''
  } catch (e) {
    console.error('AI keyword expansion failed:', e)
  } finally {
    keywordGenerating.value = false
  }
}

async function submit() {
  error.value = ''
  const keywords = keywordsText.value.split('\n').map(k => k.trim()).filter(Boolean)
  if (keywords.length === 0) {
    error.value = '请至少输入一个关键词'
    return
  }

  let params = {}
  try {
    params = JSON.parse(paramsText.value || '{}')
  } catch {
    error.value = '参数模板 JSON 格式错误'
    return
  }

  // 合并表单参数（JSON 优先级更高）
  var fp = formParams.value
  var merged = {
    count: params.count !== undefined ? params.count : fp.count,
    content: params.content !== undefined ? params.content : (fp.content || undefined),
    dm_sequence_id: dmSequenceId.value || undefined,
  }
  if (['reply_comment', 'search_comment', 'collect'].includes(form.value.task_type)) {
    merged.video_count = params.video_count !== undefined ? params.video_count : fp.video_count
  }
  if (['reply_comment', 'search_comment', 'collect'].includes(form.value.task_type)) {
    merged.max_age_days = params.max_age_days !== undefined ? params.max_age_days : fp.max_age_days
    merged.max_age_unit = params.max_age_unit !== undefined ? params.max_age_unit : fp.max_age_unit
    if (fp.sort_by) merged.sort_by = params.sort_by || fp.sort_by
  }
  // 其他 JSON 参数
  Object.keys(params).forEach(function (k) {
    if (merged[k] === undefined) merged[k] = params[k]
  })

  submitting.value = true
  try {
    await createChannel({
      ...form.value,
      keywords,
      params_template: merged,
    })
    emit('created')
  } catch (e) {
    error.value = e.response?.data?.detail || '创建失败'
  } finally {
    submitting.value = false
  }
}
</script>
