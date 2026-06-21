<!-- 管理端业务页面：承载 DirectorPage 页面流程，协调接口数据、用户操作和业务状态展示。 -->
<template>
  <div class="p-6">
    <div class="flex items-center gap-4 mb-6">
      <button @click="$router.back()" class="text-sky-400 hover:text-sky-300 transition cursor-pointer">&larr; 返回</button>
      <h1 class="text-2xl font-bold text-slate-100">导演时间线</h1>
    </div>

    <div v-if="!plan" class="text-slate-500 text-center py-12">请先选择剧集，然后构建导演计划</div>
    <div v-else class="space-y-6">
      <div class="flex gap-4 text-sm text-slate-400">
        <span>{{ plan.frame_count }} 帧</span><span>{{ plan.total_duration?.toFixed(0) || 0 }}s 总时长</span>
        <span>BGM: {{ plan.bgm_path || '无' }}</span>
      </div>

      <div class="space-y-3">
        <div v-for="f in plan.frames" :key="f.index"
             class="rounded-xl border border-gray-700/50 p-4 flex gap-4 items-start hover:shadow-lg hover:shadow-sky-900/10 transition-all duration-200"
             style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);">
          <div class="w-12 h-12 rounded-lg flex items-center justify-center text-lg font-bold" :class="shotBg(f.shot_type)">{{ f.index + 1 }}</div>
          <div class="flex-1 min-w-0">
            <div class="flex gap-2 flex-wrap mb-2">
              <span class="px-2 py-0.5 rounded text-xs font-medium" :class="shotBg(f.shot_type)">{{ f.shot_type }}</span>
              <span class="px-2 py-0.5 rounded text-xs bg-gray-800 text-slate-400">{{ f.camera_angle }}</span>
              <span class="px-2 py-0.5 rounded text-xs bg-gray-800 text-slate-400">{{ f.camera_movement }}</span>
              <span class="px-2 py-0.5 rounded text-xs" :class="audioBg(f.audio_mode)">{{ f.audio_mode }}</span>
              <span class="px-2 py-0.5 rounded text-xs bg-gray-800 text-slate-400">{{ f.duration }}s</span>
            </div>
            <p class="text-sm text-slate-200 line-clamp-2 mb-1">{{ f.narration }}</p>
            <p class="text-xs text-slate-500 italic">{{ f.image_prompt }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const plan = ref(null)
function shotBg(t) { return { close_up: 'bg-red-900/40 text-red-400', medium: 'bg-sky-900/40 text-sky-400', wide: 'bg-emerald-900/40 text-emerald-400', aerial: 'bg-purple-900/40 text-purple-400', climax: 'bg-orange-900/40 text-orange-400' }[t] || 'bg-gray-800 text-slate-400' }
function audioBg(m) { return { tts: 'bg-sky-900/40 text-sky-400', seedance_native: 'bg-emerald-900/40 text-emerald-400', bgm_only: 'bg-yellow-900/40 text-yellow-400', silent: 'bg-gray-800 text-slate-400' }[m] || 'bg-gray-800 text-slate-400' }
</script>
