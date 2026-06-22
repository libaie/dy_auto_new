<!-- 视频工作台组件：承载 Pixelle、Seedance、媒体面板和生成参数相关业务配置。 -->
<script setup>
import { computed } from 'vue'

const props = defineProps({
  generating: { type: Boolean, default: false },
  progress: { type: Object, default: () => ({}) },
  result: { type: Object, default: null },
  history: { type: Array, default: () => [] },
  videoUrl: { type: String, default: '' },
  configValid: { type: Boolean, default: false },
})

const emit = defineEmits(['generate', 'download', 'clear-result'])

const progressPercent = computed(() => {
  if (!props.progress) return 0
  return props.progress.percent || 0
})

const progressLabel = computed(() => {
  if (!props.progress) return '准备中...'
  return props.progress.message || props.progress.status || '处理中...'
})

// 入参：seconds 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 formatDuration 对应业务流程的处理结果。
function formatDuration(seconds) {
  if (!seconds) return '-'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

// 前端业务函数：协调 formatFileSize 对应的页面流程、接口调用或状态转换。
// 入参：bytes 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 formatFileSize 对应业务流程的处理结果。
function formatFileSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<template>
  <div class="glass-card p-5 h-full flex flex-col">
    <div class="flex items-center gap-2 mb-5">
      <div class="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
        <svg class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <h3 class="text-sm font-semibold text-white">生成 & 预览</h3>
    </div>

    <!-- Config validation warning -->
    <div v-if="!configValid" class="mb-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300">
      <div class="flex items-start gap-2">
        <svg class="w-4 h-4 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
        <span>请先在「系统配置」中填入 LLM API Key 和 RunningHub API Key 后再生成视频</span>
      </div>
    </div>

    <!-- Generate button -->
    <button
      @click="$emit('generate')"
      :disabled="generating"
      class="w-full py-3 rounded-xl font-medium text-white text-sm transition-all mb-4"
      :class="generating
        ? 'bg-slate-700 cursor-not-allowed'
        : 'bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 shadow-lg shadow-emerald-500/20'"
    >
      <span v-if="generating" class="flex items-center justify-center gap-2">
        <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" class="opacity-25" />
          <path stroke-linecap="round" stroke-width="3" d="M12 2a10 10 0 019.95 9" fill="currentColor" />
        </svg>
        生成中...
      </span>
      <span v-else>生成视频</span>
    </button>

    <!-- Progress -->
    <div v-if="generating" class="mb-4">
      <div class="flex justify-between text-xs text-slate-400 mb-1">
        <span>{{ progressLabel }}</span>
        <span>{{ progressPercent }}%</span>
      </div>
      <div class="h-2 rounded-full bg-white/10 overflow-hidden">
        <div
          class="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-all duration-500"
          :style="{ width: progressPercent + '%' }"
        />
      </div>
    </div>

    <!-- Result: Video Preview -->
    <div v-if="result && result.success" class="flex-1 flex flex-col">
      <div class="relative bg-black rounded-lg overflow-hidden mb-3 flex-1 min-h-[200px] flex items-center justify-center">
        <video
          v-if="videoUrl"
          :src="videoUrl"
          controls
          aria-label="视频预览"
          class="w-full max-h-[360px]"
        />
        <div v-else class="text-slate-500 text-sm">视频加载中...</div>
      </div>

      <!-- Info -->
      <div class="space-y-1.5 text-xs">
        <div class="flex justify-between">
          <span class="text-slate-400">时长</span>
          <span class="text-white">{{ formatDuration(result.duration) }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-slate-400">文件大小</span>
          <span class="text-white">{{ formatFileSize(result.fileSize) }}</span>
        </div>
        <div v-if="result.frames" class="flex justify-between">
          <span class="text-slate-400">帧数</span>
          <span class="text-white">{{ result.frames }}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-slate-400">任务 ID</span>
          <span class="text-white text-[11px] font-mono">{{ result.taskId }}</span>
        </div>
      </div>

      <!-- Actions -->
      <div class="flex gap-2 mt-3">
        <a
          v-if="videoUrl"
          :href="videoUrl"
          download
          class="flex-1 text-center px-3 py-2 rounded-lg bg-emerald-500/20 text-emerald-300 text-xs hover:bg-emerald-500/30 transition-colors"
        >
          下载视频
        </a>
        <button
          @click="$emit('clear-result')"
          class="px-3 py-2 rounded-lg bg-white/5 text-slate-400 text-xs hover:bg-white/10 transition-colors"
        >
          清除
        </button>
      </div>
    </div>

    <!-- Result: Error -->
    <div v-if="result && !result.success" class="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
      <p class="text-sm text-red-400 font-medium mb-1">生成失败</p>
      <p class="text-xs text-red-300/70">{{ result.error || '未知错误' }}</p>
      <button
        @click="$emit('clear-result')"
        class="mt-2 text-xs text-red-400 hover:text-red-300"
      >清除</button>
    </div>

    <!-- Idle state -->
    <div v-if="!generating && !result" class="flex-1 flex items-center justify-center">
      <div class="text-center">
        <svg class="w-12 h-12 mx-auto text-slate-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
        <p class="text-slate-500 text-sm">在左侧填入话题关键词</p>
        <p class="text-slate-600 text-xs mt-1">然后点击「生成视频」</p>
      </div>
    </div>

    <!-- History -->
    <div v-if="history.length > 0" class="border-t border-white/5 pt-3 mt-auto">
      <p class="text-xs text-slate-400 mb-2">生成历史</p>
      <div class="space-y-1.5 max-h-36 overflow-y-auto">
        <div
          v-for="(item, idx) in history" :key="idx"
          class="flex items-center justify-between text-xs px-2 py-1.5 rounded bg-white/[0.02]"
        >
          <span class="text-slate-300 truncate flex-1">{{ item.text || '未命名' }}</span>
          <span
            class="ml-2 px-1.5 py-0.5 rounded text-[11px]"
            :class="item.success
              ? 'bg-emerald-500/15 text-emerald-400'
              : 'bg-red-500/15 text-red-400'"
          >{{ item.success ? '完成' : '失败' }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
