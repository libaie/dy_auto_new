<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Object, required: true },
})

const emit = defineEmits(['update:modelValue'])

function setLayer(layer, value) {
  emit('update:modelValue', { ...props.modelValue, [layer]: value })
}

const layers = [
  {
    key: 'scriptLLM', label: '脚本生成', icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
    color: 'sky', options: [
      { value: 'qwen-max', label: 'Qwen Max', desc: '通义千问 · 阿里云' },
      { value: 'gpt-4o', label: 'GPT-4o', desc: 'OpenAI 旗舰' },
      { value: 'deepseek-v3', label: 'DeepSeek V3', desc: '高性价比' },
      { value: 'claude-opus', label: 'Claude Opus', desc: '创意写作' },
      { value: 'ollama-local', label: 'Ollama 本地', desc: '开源本地部署' },
    ],
  },
  {
    key: 'imageModel', label: '画面生成', icon: 'M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z',
    color: 'emerald', options: [
      { value: 'flux', label: 'FLUX', desc: 'RunningHub · 高质量静态图' },
      { value: 'sdxl', label: 'SDXL', desc: 'ComfyUI · 灵活可控' },
      { value: 'auto', label: '自动选择', desc: '根据场景自动匹配' },
    ],
  },
  {
    key: 'videoModel', label: '视频渲染', icon: 'M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    color: 'purple', options: [
      { value: 'auto', label: '自动选择', desc: '根据镜头类型智能切换' },
      { value: 'seedance', label: 'Seedance 2.0', desc: '字节跳动 · 人脸最优' },
      { value: 'kling', label: 'Kling 3.0', desc: '快手 · 4K AI导演' },
      { value: 'wan', label: 'Wan 2.7', desc: '阿里 · 开源 RunningHub' },
      { value: 'flux', label: 'FLUX 静态图', desc: '仅静态画面，无动态视频' },
    ],
  },
  {
    key: 'ttsModel', label: '语音合成', icon: 'M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z',
    color: 'amber', options: [
      { value: 'edge-tts', label: 'Edge-TTS', desc: '微软免费 · 40+语言' },
      { value: 'index-tts', label: 'Index-TTS', desc: '声音克隆 · 上传参考音频' },
      { value: 'spark-tts', label: 'Spark-TTS', desc: '火山引擎 · 高级合成' },
      { value: 'custom', label: '自定义 ComfyUI', desc: '自托管 TTS 工作流' },
    ],
  },
  {
    key: 'auditModel', label: '质量审计', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
    color: 'rose', options: [
      { value: 'auto', label: '自动选择', desc: '根据内容类型自动' },
      { value: 'gemini', label: 'Gemini', desc: 'Google 多模态审计' },
      { value: 'gpt-4o', label: 'GPT-4o', desc: 'OpenAI 视觉审计' },
      { value: 'local', label: '本地 vLLM', desc: '自托管审计模型' },
      { value: 'none', label: '跳过审计', desc: '不进行质量检查' },
    ],
  },
]

const colorMap = {
  sky: { active: 'bg-sky-500/15 text-sky-300 border-sky-500/30', dot: 'bg-sky-400' },
  emerald: { active: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30', dot: 'bg-emerald-400' },
  purple: { active: 'bg-purple-500/15 text-purple-300 border-purple-500/30', dot: 'bg-purple-400' },
  amber: { active: 'bg-amber-500/15 text-amber-300 border-amber-500/30', dot: 'bg-amber-400' },
  rose: { active: 'bg-rose-500/15 text-rose-300 border-rose-500/30', dot: 'bg-rose-400' },
}

const selectedLabels = computed(() => {
  const result = {}
  for (const layer of layers) {
    const val = props.modelValue[layer.key]
    const opt = layer.options.find(o => o.value === val)
    result[layer.key] = opt ? opt.label : val
  }
  return result
})
</script>

<template>
  <div class="rounded-xl border border-gray-700/50 p-4" style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);">
    <h3 class="text-xs font-medium text-slate-400 mb-3 flex items-center gap-2">
      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"/></svg>
      各环节模型配置
    </h3>
    <div class="grid grid-cols-5 gap-3">
      <div v-for="layer in layers" :key="layer.key" class="relative">
        <!-- Layer header -->
        <div class="flex items-center gap-1.5 mb-2">
          <div class="w-5 h-5 rounded flex items-center justify-center" :class="colorMap[layer.color].dot" style="--tw-bg-opacity: 0.2;">
            <svg class="w-3 h-3" :class="colorMap[layer.color].dot.replace('bg-', 'text-')" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="layer.icon"/>
            </svg>
          </div>
          <span class="text-xs font-medium text-slate-300">{{ layer.label }}</span>
        </div>

        <!-- Model selector dropdown -->
        <select
          :value="modelValue[layer.key]"
          @change="setLayer(layer.key, $event.target.value)"
          class="layer-select w-full rounded-lg px-2.5 py-2 text-xs bg-gray-800/80 border border-gray-600 text-slate-100 cursor-pointer focus:outline-none focus:ring-2 transition appearance-none"
          :class="`focus:ring-${layer.color}-500/50`"
        >
          <option v-for="opt in layer.options" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>

        <!-- Selected model description -->
        <p class="text-[10px] text-slate-500 mt-1 leading-tight truncate">
          {{ layer.options.find(o => o.value === modelValue[layer.key])?.desc || '' }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.layer-select {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3E%3Cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3E%3C/svg%3E");
  background-position: right 0.25rem center;
  background-repeat: no-repeat;
  background-size: 1.25em;
}
</style>
