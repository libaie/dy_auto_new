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
          <label class="block text-sm font-medium text-slate-300 mb-1">关键词（每行一个）</label>
          <textarea
            v-model="keywordsText"
            rows="4"
            class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            placeholder="美食&#10;旅游&#10;健身"
          />
        </div>

        <!-- Params template (JSON) -->
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-300 mb-1">参数模板 (JSON)</label>
          <textarea
            v-model="paramsText"
            rows="2"
            class="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white placeholder-slate-500 font-mono text-sm focus:outline-none focus:border-blue-500"
            placeholder='{"content": "好棒！", "count": 5}'
          />
        </div>

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
const paramsText = ref('{}')
const error = ref('')
const submitting = ref(false)

onMounted(async () => {
  try {
    const resp = await listGroups()
    groups.value = resp.data || []
  } catch (e) {
    console.error('Failed to load groups:', e)
  }
})

// Load group members when group changes
watch(() => form.value.group_id, async (gid) => {
  if (!gid) return
  try {
    const resp = await listMembers(gid, { status: 'active' })
    accounts.value = resp.data || []
  } catch (e) {
    console.error('Failed to load group members:', e)
  }
})

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

  submitting.value = true
  try {
    await createChannel({
      ...form.value,
      keywords,
      params_template: params,
    })
    emit('created')
  } catch (e) {
    error.value = e.response?.data?.detail || '创建失败'
  } finally {
    submitting.value = false
  }
}
</script>
