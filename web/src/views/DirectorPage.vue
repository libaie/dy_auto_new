<template>
  <div class="p-6">
    <div class="flex items-center gap-4 mb-6">
      <button @click="$router.back()" class="text-blue-600 hover:underline">&larr; 返回</button>
      <h1 class="text-2xl font-bold text-gray-900">导演时间线</h1>
    </div>

    <div v-if="!plan" class="text-gray-400 text-center py-12">请先选择剧集，然后构建导演计划</div>
    <div v-else class="space-y-6">
      <div class="flex gap-4 text-sm text-gray-500">
        <span>{{ plan.frame_count }} 帧</span>
        <span>{{ plan.total_duration.toFixed(0) }}s 总时长</span>
        <span>BGM: {{ plan.bgm_path || '无' }}</span>
      </div>

      <!-- 分镜时间线 -->
      <div class="space-y-3">
        <div v-for="f in plan.frames" :key="f.index"
             class="bg-white rounded-xl border p-4 flex gap-4 items-start hover:shadow-sm transition">
          <div class="w-12 h-12 rounded-lg flex items-center justify-center text-lg font-bold"
               :class="shotBg(f.shot_type)">{{ f.index + 1 }}</div>
          <div class="flex-1 min-w-0">
            <div class="flex gap-2 flex-wrap mb-2">
              <span class="px-2 py-0.5 rounded text-xs font-medium" :class="shotBadge(f.shot_type)">{{ f.shot_type }}</span>
              <span class="px-2 py-0.5 rounded text-xs bg-gray-100">{{ f.camera_angle }}</span>
              <span class="px-2 py-0.5 rounded text-xs bg-gray-100">{{ f.camera_movement }}</span>
              <span class="px-2 py-0.5 rounded text-xs" :class="audioBadge(f.audio_mode)">{{ f.audio_mode }}</span>
              <span class="px-2 py-0.5 rounded text-xs bg-gray-100">{{ f.duration }}s</span>
            </div>
            <p class="text-sm text-gray-700 line-clamp-2 mb-1">{{ f.narration }}</p>
            <p class="text-xs text-gray-400 italic">{{ f.image_prompt }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const plan = ref(null)

function shotBg(t) {
  return { close_up: 'bg-red-100 text-red-700', medium: 'bg-blue-100 text-blue-700',
           wide: 'bg-green-100 text-green-700', aerial: 'bg-purple-100 text-purple-700',
           climax: 'bg-orange-100 text-orange-700' }[t] || 'bg-gray-100'
}
function shotBadge(t) { return shotBg(t) }
function audioBadge(m) {
  return { tts: 'bg-blue-100 text-blue-700', seedance_native: 'bg-green-100 text-green-700',
           bgm_only: 'bg-yellow-100 text-yellow-700', silent: 'bg-gray-100' }[m] || 'bg-gray-100'
}
</script>
