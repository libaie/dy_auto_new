<!-- 视频工作台组件：承载 Pixelle、Seedance、媒体面板和生成参数相关业务配置。 -->
<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  modelValue: { type: Object, required: true },
  bgmList: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue', 'bgm-upload'])

// 前端业务函数：协调 updateField 对应的页面流程、接口调用或状态转换。
function updateField(key, value) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

const isFixedMode = computed(() => props.modelValue.mode === 'fixed')

// BGM preview
const bgmPreviewUrl = ref('')
// 前端业务函数：协调 previewBGM 对应的页面流程、接口调用或状态转换。
function previewBGM() {
  const bgm = props.modelValue.bgmId
  if (bgm) bgmPreviewUrl.value = `/api/pixelle-proxy/api/files/${encodeURIComponent(bgm)}`
  else bgmPreviewUrl.value = ''
}
</script>

<template>
  <div class="glass-card p-5 h-full flex flex-col">
    <div class="flex items-center gap-2 mb-5">
      <div class="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center">
        <svg class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
        </svg>
      </div>
      <h3 class="text-sm font-semibold text-white">内容创作</h3>
    </div>

    <div class="flex-1 overflow-y-auto space-y-4">
      <!-- Mode toggle -->
      <div>
        <div class="flex gap-2">
          <button @click="updateField('mode', 'generate')" class="flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all"
            :class="modelValue.mode === 'generate' ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' : 'bg-white/5 text-slate-400 border border-white/10 hover:border-white/20'">
            <div class="text-sm mb-0.5">AI 生成脚本</div><div class="text-[11px] opacity-60">LLM 自动编撰</div>
          </button>
          <button @click="updateField('mode', 'fixed')" class="flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-all"
            :class="modelValue.mode === 'fixed' ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30' : 'bg-white/5 text-slate-400 border border-white/10 hover:border-white/20'">
            <div class="text-sm mb-0.5">固定文本</div><div class="text-[11px] opacity-60">使用自定义脚本</div>
          </button>
        </div>
      </div>

      <!-- Text input -->
      <div>
        <label class="block text-xs text-slate-400 mb-1.5">
          {{ isFixedMode ? '视频脚本文本' : '视频主题 / 话题' }}
        </label>
        <textarea
          :value="modelValue.text"
          @input="updateField('text', $event.target.value)"
          :rows="isFixedMode ? 7 : 4"
          maxlength="5000"
          :placeholder="isFixedMode ? '输入完整的视频脚本...' : '输入一个话题或关键词，AI 将自动生成视频脚本。例如：养生茶的5大功效'"
          class="w-full px-3 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-blue-500/50 resize-none"
        />
        <p class="text-[11px] text-slate-500 mt-1">{{ (modelValue.text || '').length }} / 5000</p>
      </div>

      <!-- Title input -->
      <div>
        <label class="block text-xs text-slate-400 mb-1.5">视频标题 <span class="text-slate-500">(可选)</span></label>
        <input
          :value="modelValue.title"
          @input="updateField('title', $event.target.value)"
          type="text" maxlength="200"
          placeholder="留空则自动生成标题"
          class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-blue-500/50"
        />
      </div>

      <!-- Split mode (fixed only) -->
      <div v-if="isFixedMode">
        <label class="block text-xs text-slate-400 mb-1.5">文本拆分方式</label>
        <select :value="modelValue.splitMode" @change="updateField('splitMode', $event.target.value)"
          class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-purple-500/50">
          <option value="paragraph">按段落拆分</option>
          <option value="line">按行拆分</option>
          <option value="sentence">按句子拆分</option>
        </select>
      </div>

      <!-- Scene count -->
      <div>
        <label class="block text-xs text-slate-400 mb-1.5">场景数量: <span class="text-white font-semibold">{{ modelValue.nScenes }}</span></label>
        <input type="range" min="1" max="30" :value="modelValue.nScenes" @input="updateField('nScenes', Number($event.target.value))" class="w-full accent-blue-500"/>
        <div class="flex justify-between text-[11px] text-slate-500 mt-0.5"><span>1</span><span>30</span></div>
      </div>

      <!-- BGM Section -->
      <div class="border-t border-white/5 pt-4">
        <label class="block text-xs text-slate-400 mb-2">背景音乐 (BGM)</label>
        <div class="flex gap-2 mb-3">
          <button v-for="opt in [{v:'none',l:'无'},{v:'builtin',l:'内置'},{v:'custom',l:'自定义'}]" :key="opt.v"
            @click="updateField('bgmMode', opt.v)"
            class="px-3 py-1.5 rounded-lg text-xs transition-all"
            :class="modelValue.bgmMode === opt.v ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' : 'bg-white/5 text-slate-400 border border-white/10'"
          >{{ opt.l }}</button>
        </div>

        <!-- Built-in BGM -->
        <div v-if="modelValue.bgmMode === 'builtin'" class="mb-3">
          <div class="flex gap-2">
            <select :value="modelValue.bgmId" @change="updateField('bgmId', $event.target.value)"
              class="flex-1 px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-blue-500/50">
              <option v-for="bgm in bgmList" :key="bgm.path || bgm.name" :value="bgm.path || bgm.name">{{ bgm.name }}</option>
            </select>
            <button @click="previewBGM" class="px-3 py-2 rounded-lg bg-purple-500/20 text-purple-300 text-xs hover:bg-purple-500/30 transition-colors whitespace-nowrap">试听</button>
          </div>
          <audio v-if="bgmPreviewUrl" :src="bgmPreviewUrl" controls class="mt-2 w-full h-7" controlslist="nodownload"/>
        </div>

        <!-- Custom BGM upload -->
        <div v-if="modelValue.bgmMode === 'custom'" class="mb-3">
          <input type="file" accept=".mp3,.wav" @change="$emit('bgm-upload', $event)"
            class="w-full text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:text-xs file:bg-white/10 file:text-white file:border-0 hover:file:bg-white/20"/>
        </div>

        <!-- Volume -->
        <div v-if="modelValue.bgmMode !== 'none'">
          <label class="block text-xs text-slate-400 mb-1">音量: <span class="text-white font-semibold">{{ modelValue.bgmVolume.toFixed(2) }}</span></label>
          <input type="range" min="0" max="0.5" step="0.01" :value="modelValue.bgmVolume" @input="updateField('bgmVolume', Number($event.target.value))" class="w-full accent-blue-500"/>
        </div>
      </div>
    </div>
  </div>
</template>
