<!-- 管理端业务页面：承载 VideosPage 页面流程，协调接口数据、用户操作和业务状态展示。 -->
<script setup>
import { ref, computed, onMounted } from 'vue'
import { listVideos, deleteVideo, getVideoDownloadUrl } from '../api/videos.js'
import { useToastStore } from '../stores/toast.js'
import { useWebSocket } from '../composables/useWebSocket.js'
import { formatDate } from '../utils/format.js'
import LoadingSpinner from '../components/LoadingSpinner.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'

const toast = useToastStore()

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 12

const searchKeyword = ref('')
const filterStatus = ref('')

const previewVideo = ref(null)
const showPreview = ref(false)

const deleteTarget = ref(null)
const showDeleteConfirm = ref(false)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

// 前端业务函数：协调 wsUrl 对应的页面流程、接口调用或状态转换。
function wsUrl() {
  const token = localStorage.getItem('token') || ''
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/api/devices/ws/pair-events?token=${encodeURIComponent(token)}`
}
const { connect: wsConnect } = useWebSocket(wsUrl, {
  onMessage(msg) {
    if (msg.event === 'task_updated' || msg.event === 'tasks_changed') {
      fetchData()
    }
  },
})

// 前端业务函数：协调 fetchData 对应的页面流程、接口调用或状态转换。
async function fetchData() {
  loading.value = true
  try {
    const params = { skip: (page.value - 1) * pageSize, limit: pageSize }
    if (searchKeyword.value) params.keyword = searchKeyword.value
    if (filterStatus.value) params.status = filterStatus.value
    const resp = await listVideos(params)
    items.value = resp.data.items || []
    total.value = resp.data.total || 0
  } catch {
    toast.error('加载视频列表失败')
  } finally {
    loading.value = false
  }
}

// 前端业务函数：协调 handleSearch 对应的页面流程、接口调用或状态转换。
function handleSearch() {
  page.value = 1
  fetchData()
}

// 前端业务函数：协调 goPage 对应的页面流程、接口调用或状态转换。
function goPage(p) {
  page.value = p
  fetchData()
}

// 前端业务函数：协调 openPreview 对应的页面流程、接口调用或状态转换。
function openPreview(video) {
  previewVideo.value = video
  showPreview.value = true
}

// 前端业务函数：协调 closePreview 对应的页面流程、接口调用或状态转换。
function closePreview() {
  showPreview.value = false
  previewVideo.value = null
}

// 前端业务函数：协调 confirmDelete 对应的页面流程、接口调用或状态转换。
function confirmDelete(video) {
  deleteTarget.value = video
  showDeleteConfirm.value = true
}

// 前端业务函数：协调 handleDelete 对应的页面流程、接口调用或状态转换。
async function handleDelete() {
  if (!deleteTarget.value) return
  try {
    await deleteVideo(deleteTarget.value.id)
    toast.success('视频已删除')
    showDeleteConfirm.value = false
    deleteTarget.value = null
    fetchData()
  } catch {
    toast.error('删除失败')
  }
}

function statusVariant(status) {
  const map = { completed: 'success', failed: 'danger', processing: 'warning', pending: 'info' }
  return map[status] || 'info'
}

// 前端业务函数：协调 statusLabel 对应的页面流程、接口调用或状态转换。
function statusLabel(status) {
  const map = { completed: '已完成', failed: '失败', processing: '生成中', pending: '待处理' }
  return map[status] || status
}

function formatDuration(seconds) {
  if (!seconds) return '-'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

onMounted(() => {
  wsConnect()
  fetchData()
})
</script>

<template>
  <div class="max-w-6xl mx-auto">
    <h1 class="text-2xl font-bold gradient-text mb-6">视频管理</h1>

    <!-- Filters -->
    <div class="glass-card p-4 mb-6">
      <div class="flex flex-wrap items-end gap-3">
        <div class="flex-1 min-w-[180px]">
          <label class="block text-xs text-slate-400 mb-1">关键词搜索</label>
          <input
            v-model="searchKeyword"
            type="text"
            placeholder="搜索视频关键词..."
            class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"
            @keyup.enter="handleSearch"
          />
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">状态</label>
          <select
            v-model="filterStatus"
            class="px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-cyan-500/50"
            @change="handleSearch"
          >
            <option value="">全部</option>
            <option value="pending">待处理</option>
            <option value="processing">生成中</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
          </select>
        </div>
        <button
          @click="handleSearch"
          class="px-4 py-2 rounded-lg bg-cyan-500/20 text-cyan-300 text-sm hover:bg-cyan-500/30 transition-colors"
        >
          搜索
        </button>
      </div>
    </div>

    <LoadingSpinner v-if="loading" />

    <template v-else>
      <!-- Empty state -->
      <div v-if="items.length === 0" class="glass-card p-12 text-center">
        <svg class="w-16 h-16 mx-auto text-slate-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
        <p class="text-slate-400 text-lg mb-2">暂无视频</p>
        <p class="text-slate-500 text-sm">在任务中心创建「AI 生成视频」任务，生成完成后会出现在这里</p>
      </div>

      <!-- Video grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mb-6">
        <div
          v-for="video in items"
          :key="video.id"
          class="glass-card overflow-hidden group cursor-pointer hover:border-cyan-500/30 transition-all"
        >
          <!-- Thumbnail area -->
          <div
            class="relative bg-gradient-to-br from-slate-800 to-slate-900 h-40 flex items-center justify-center"
            @click="openPreview(video)"
          >
            <svg v-if="video.status === 'processing'" class="w-12 h-12 text-cyan-400 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="10" stroke-width="3" class="opacity-25" />
              <path stroke-linecap="round" stroke-width="3" d="M12 2a10 10 0 019.95 9" />
            </svg>
            <svg v-else-if="video.status === 'failed'" class="w-12 h-12 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <svg v-else class="w-12 h-12 text-slate-600 group-hover:text-white transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span
              class="absolute top-2 right-2 text-xs px-2 py-0.5 rounded-full"
              :class="{
                'bg-emerald-500/20 text-emerald-300': video.status === 'completed',
                'bg-red-500/20 text-red-300': video.status === 'failed',
                'bg-cyan-500/20 text-cyan-300': video.status === 'processing',
                'bg-slate-500/20 text-slate-400': video.status === 'pending',
              }"
            >{{ statusLabel(video.status) }}</span>
          </div>

          <!-- Info -->
          <div class="p-3 space-y-1.5">
            <p class="text-sm font-medium text-white truncate" :title="video.title || video.keyword">
              {{ video.title || video.keyword }}
            </p>
            <p class="text-xs text-slate-400">{{ video.keyword }}</p>
            <div class="flex items-center justify-between text-xs text-slate-500">
              <span v-if="video.duration">{{ formatDuration(video.duration) }}</span>
              <span v-else>-</span>
              <span>{{ formatDate(video.created_at) }}</span>
            </div>
            <!-- Actions -->
            <div class="flex items-center gap-2 pt-1 border-t border-white/5">
              <button
                v-if="video.status === 'completed'"
                @click="openPreview(video)"
                class="flex-1 text-xs px-2 py-1 rounded bg-cyan-500/15 text-cyan-300 hover:bg-cyan-500/25 transition-colors"
              >
                预览
              </button>
              <a
                v-if="video.video_path"
                :href="getVideoDownloadUrl(video.id)"
                class="flex-1 text-xs px-2 py-1 rounded bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 transition-colors text-center"
              >
                下载
              </a>
              <button
                @click="confirmDelete(video)"
                class="flex-1 text-xs px-2 py-1 rounded bg-red-500/15 text-red-300 hover:bg-red-500/25 transition-colors"
              >
                删除
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Pagination -->
      <div v-if="totalPages > 1" class="flex items-center justify-center gap-2">
        <button
          :disabled="page <= 1"
          @click="goPage(page - 1)"
          class="px-3 py-1.5 rounded-lg text-sm border border-white/10 text-slate-300 hover:border-white/20 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          上一页
        </button>
        <span class="text-sm text-slate-400">{{ page }} / {{ totalPages }}</span>
        <button
          :disabled="page >= totalPages"
          @click="goPage(page + 1)"
          class="px-3 py-1.5 rounded-lg text-sm border border-white/10 text-slate-300 hover:border-white/20 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          下一页
        </button>
      </div>
    </template>

    <!-- Preview dialog -->
    <Teleport to="body">
      <div
        v-if="showPreview"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
        @click.self="closePreview"
      >
        <div class="max-w-3xl w-full mx-4">
          <div class="glass-card p-4">
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-white font-medium truncate">{{ previewVideo?.title || previewVideo?.keyword }}</h3>
              <button @click="closePreview" class="text-slate-400 hover:text-white transition-colors">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <video
              v-if="previewVideo?.video_path"
              :src="getVideoDownloadUrl(previewVideo.id)"
              controls
              autoplay
              class="w-full rounded-lg max-h-[70vh]"
            />
            <p v-else class="text-slate-400 text-center py-12">视频文件不存在</p>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Delete confirm -->
    <ConfirmDialog
      :open="showDeleteConfirm"
      title="删除视频"
      :message="`确定要删除「${deleteTarget?.title || deleteTarget?.keyword || ''}」吗？视频文件也将被删除，此操作不可撤销。`"
      @confirm="handleDelete"
      @cancel="showDeleteConfirm = false; deleteTarget = null"
    />
  </div>
</template>
