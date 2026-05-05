<template>
  <div class="p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white">任务通道</h1>
      <button
        @click="showCreateDialog = true"
        class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
      >
        创建通道
      </button>
    </div>

    <!-- Channel cards -->
    <div v-if="loading" class="text-center py-12 text-slate-400">加载中...</div>
    <div v-else-if="channels.length === 0" class="text-center py-12 text-slate-400">
      暂无通道，点击上方按钮创建
    </div>
    <div v-else class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      <div
        v-for="ch in channels"
        :key="ch.id"
        class="bg-slate-800/50 backdrop-blur rounded-lg shadow p-4 border border-slate-700 hover:border-slate-500 transition-all cursor-pointer"
        @click="openDetail(ch)"
      >
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm font-medium text-white">
            {{ ch.group_name }} · {{ taskTypeLabel(ch.task_type) }}
          </span>
          <span :class="statusClass(ch.status)" class="px-2 py-0.5 text-xs rounded-full">
            {{ statusLabel(ch.status) }}
          </span>
        </div>
        <div class="mb-2">
          <div class="flex justify-between text-xs text-slate-400 mb-1">
            <span>{{ ch.completed }}/{{ ch.total }} 完成</span>
            <span>{{ ch.pending }} 待处理</span>
          </div>
          <div class="w-full bg-slate-700 rounded-full h-2">
            <div
              class="bg-green-500 h-2 rounded-full transition-all"
              :style="{ width: ch.total ? (ch.completed / ch.total * 100) + '%' : '0%' }"
            />
          </div>
        </div>
        <div class="flex items-center justify-between text-xs text-slate-500">
          <span>{{ ch.account_mode === 'single_account' ? '单账号' : '轮转' }}</span>
          <span>{{ ch.assigned }} 执行中</span>
        </div>
        <div class="flex gap-2 mt-3">
          <button
            v-if="ch.status === 'active'"
            @click.stop="pauseChannel(ch)"
            class="px-3 py-1 text-xs bg-yellow-500/20 text-yellow-400 rounded hover:bg-yellow-500/30 transition-colors"
          >暂停</button>
          <button
            v-if="ch.status === 'paused'"
            @click.stop="resumeChannel(ch)"
            class="px-3 py-1 text-xs bg-green-500/20 text-green-400 rounded hover:bg-green-500/30 transition-colors"
          >恢复</button>
          <button
            v-if="ch.status !== 'cancelled' && ch.status !== 'completed'"
            @click.stop="cancelChannel(ch)"
            class="px-3 py-1 text-xs bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 transition-colors"
          >取消</button>
          <button
            @click.stop="deleteChannel(ch)"
            class="px-3 py-1 text-xs bg-slate-600/50 text-slate-300 rounded hover:bg-slate-600 transition-colors"
          >删除</button>
        </div>
      </div>
    </div>

    <!-- Create dialog -->
    <CreateChannelDialog
      v-if="showCreateDialog"
      @close="showCreateDialog = false"
      @created="onChannelCreated"
    />

    <!-- Detail dialog -->
    <ChannelDetail
      v-if="detailChannel"
      :channel="detailChannel"
      @close="detailChannel = null"
      @refresh="fetchChannels"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listChannels, updateChannel, deleteChannel as deleteChannelApi } from '../api/channels.js'
import CreateChannelDialog from '../components/CreateChannelDialog.vue'
import ChannelDetail from '../components/ChannelDetail.vue'

const channels = ref([])
const loading = ref(true)
const showCreateDialog = ref(false)
const detailChannel = ref(null)

const taskTypeLabel = (type) => ({
  search_comment: '评论搜索',
  search_like: '点赞搜索',
  search_dm: '私信搜索',
  reply_comment: '回复评论',
  nurture: '养号',
}[type] || type)

const statusLabel = (s) => ({
  active: '运行中',
  paused: '已暂停',
  completed: '已完成',
  cancelled: '已取消',
}[s] || s)

const statusClass = (s) => ({
  active: 'bg-green-500/20 text-green-400',
  paused: 'bg-yellow-500/20 text-yellow-400',
  completed: 'bg-blue-500/20 text-blue-400',
  cancelled: 'bg-slate-600/50 text-slate-400',
}[s] || 'bg-slate-600/50 text-slate-400')

async function fetchChannels() {
  loading.value = true
  try {
    const resp = await listChannels()
    channels.value = resp.data.channels || []
  } catch (e) {
    console.error('Failed to fetch channels:', e)
  } finally {
    loading.value = false
  }
}

async function pauseChannel(ch) {
  await updateChannel(ch.id, { status: 'paused' })
  await fetchChannels()
}

async function resumeChannel(ch) {
  await updateChannel(ch.id, { status: 'active' })
  await fetchChannels()
}

async function cancelChannel(ch) {
  if (!confirm('确定取消此通道？')) return
  await updateChannel(ch.id, { status: 'cancelled' })
  await fetchChannels()
}

async function deleteChannel(ch) {
  if (!confirm('确定删除此通道？')) return
  await deleteChannelApi(ch.id)
  await fetchChannels()
}

function openDetail(ch) {
  detailChannel.value = ch
}

function onChannelCreated() {
  showCreateDialog.value = false
  fetchChannels()
}

onMounted(fetchChannels)
</script>
