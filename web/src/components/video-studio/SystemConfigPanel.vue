<!-- 视频工作台组件：承载 Pixelle、Seedance、媒体面板和生成参数相关业务配置。 -->
<script setup>
import { ref } from 'vue'

const props = defineProps({
  modelValue: { type: Object, required: true },
})

const emit = defineEmits(['update:modelValue', 'test-connection'])

const expanded = ref(false)

const llmPresets = [
  { name: 'Qwen Max', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-max' },
  { name: 'GPT-4o', baseUrl: 'https://api.openai.com/v1', model: 'gpt-4o' },
  { name: 'DeepSeek', baseUrl: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  { name: 'Ollama', baseUrl: 'http://localhost:11434/v1', model: 'llama3.2' },
]

// 前端业务函数：协调 applyLLMPreset 对应的页面流程、接口调用或状态转换。
// 入参：preset 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 applyLLMPreset 对应业务流程的处理结果。
function applyLLMPreset(preset) {
  emit('update:modelValue', {
    ...props.modelValue,
    llmBaseUrl: preset.baseUrl,
    llmModel: preset.model,
  })
}

// 前端业务函数：协调 updateField 对应的页面流程、接口调用或状态转换。
// 入参：key、value 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 updateField 对应业务流程的处理结果。
function updateField(key, value) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}
</script>

<template>
  <div class="glass-card mb-4 overflow-hidden">
    <button
      @click="expanded = !expanded"
      :aria-expanded="expanded"
      class="w-full flex items-center justify-between p-4 hover:bg-white/[0.02] transition-colors"
    >
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center">
          <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
        </div>
        <div class="text-left">
          <h3 class="text-sm font-semibold text-white">系统配置</h3>
          <p class="text-xs text-slate-400">LLM · ComfyUI · RunningHub · 默认工作流</p>
        </div>
        <!-- Config status -->
        <div class="flex items-center gap-1.5 ml-auto">
          <span class="w-2 h-2 rounded-full" :class="modelValue.llmApiKey ? 'bg-emerald-400' : 'bg-red-400'" title="LLM 配置状态"/>
          <span class="w-2 h-2 rounded-full" :class="modelValue.runninghubApiKey ? 'bg-emerald-400' : 'bg-amber-400'" title="RunningHub 配置状态"/>
          <span class="text-[10px] text-slate-500 ml-1">{{ (modelValue.llmApiKey && modelValue.runninghubApiKey) ? '已配置' : '未完成' }}</span>
        </div>
      </div>
      <svg class="w-5 h-5 text-slate-400 transition-transform" :class="expanded ? 'rotate-180' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
    </button>

    <div v-show="expanded" class="px-4 pb-4 space-y-5 border-t border-white/5 pt-4">
      <!-- LLM Section -->
      <div>
        <h4 class="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">LLM 配置（脚本生成）</h4>
        <div class="flex flex-wrap gap-2 mb-3">
          <button v-for="p in llmPresets" :key="p.name" @click="applyLLMPreset(p)" class="px-3 py-1.5 rounded-lg text-xs border transition-colors" :class="modelValue.llmModel === p.model ? 'border-cyan-500/50 bg-cyan-500/15 text-cyan-300' : 'border-white/10 bg-white/5 text-slate-400 hover:border-white/20'">{{ p.name }}</button>
        </div>
        <div class="grid grid-cols-3 gap-3">
          <div><label for="sc-llm-apikey" class="block text-[11px] text-slate-400 mb-1">API Key</label><input id="sc-llm-apikey" type="password" :value="modelValue.llmApiKey" @input="updateField('llmApiKey', $event.target.value)" placeholder="sk-..." class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"/></div>
          <div><label for="sc-llm-baseurl" class="block text-[11px] text-slate-400 mb-1">Base URL</label><input id="sc-llm-baseurl" type="text" :value="modelValue.llmBaseUrl" @input="updateField('llmBaseUrl', $event.target.value)" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"/></div>
          <div><label for="sc-llm-model" class="block text-[11px] text-slate-400 mb-1">Model</label><input id="sc-llm-model" type="text" :value="modelValue.llmModel" @input="updateField('llmModel', $event.target.value)" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"/></div>
        </div>
      </div>

      <!-- ComfyUI Section -->
      <div class="border-t border-white/5 pt-4">
        <h4 class="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">ComfyUI & RunningHub</h4>
        <div class="grid grid-cols-2 gap-3">
          <div><label for="sc-comfyui-url" class="block text-[11px] text-slate-400 mb-1">ComfyUI URL</label><input id="sc-comfyui-url" type="text" :value="modelValue.comfyuiUrl" @input="updateField('comfyuiUrl', $event.target.value)" placeholder="http://127.0.0.1:8188" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-purple-500/50"/></div>
          <div><label for="sc-comfyui-key" class="block text-[11px] text-slate-400 mb-1">ComfyUI API Key</label><input id="sc-comfyui-key" type="password" :value="modelValue.comfyuiApiKey" @input="updateField('comfyuiApiKey', $event.target.value)" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-purple-500/50"/></div>
          <div><label for="sc-rh-key" class="block text-[11px] text-slate-400 mb-1">RunningHub API Key</label><input id="sc-rh-key" type="password" :value="modelValue.runninghubApiKey" @input="updateField('runninghubApiKey', $event.target.value)" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-purple-500/50"/></div>
          <div><label for="sc-rh-concurrent" class="block text-[11px] text-slate-400 mb-1">并发限制</label><input id="sc-rh-concurrent" type="number" min="1" max="10" :value="modelValue.runninghubConcurrent" @input="updateField('runninghubConcurrent', Number($event.target.value))" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-purple-500/50"/></div>
        </div>
      </div>

      <!-- Default Workflows -->
      <div class="border-t border-white/5 pt-4">
        <h4 class="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">默认工作流</h4>
        <div class="grid grid-cols-3 gap-3">
          <div><label for="sc-tts-wf" class="block text-[11px] text-slate-400 mb-1">TTS Workflow</label><input id="sc-tts-wf" type="text" :value="modelValue.defaultTtsWorkflow" @input="updateField('defaultTtsWorkflow', $event.target.value)" placeholder="selfhost/tts_edge.json" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"/></div>
          <div><label for="sc-img-wf" class="block text-[11px] text-slate-400 mb-1">Image Workflow</label><input id="sc-img-wf" type="text" :value="modelValue.defaultImageWorkflow" @input="updateField('defaultImageWorkflow', $event.target.value)" placeholder="runninghub/image_flux.json" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"/></div>
          <div><label for="sc-video-wf" class="block text-[11px] text-slate-400 mb-1">Video Workflow</label><input id="sc-video-wf" type="text" :value="modelValue.defaultVideoWorkflow" @input="updateField('defaultVideoWorkflow', $event.target.value)" placeholder="runninghub/video_wan2.1_fusionx.json" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"/></div>
        </div>
      </div>

      <!-- Template custom params -->
      <div class="border-t border-white/5 pt-4">
        <h4 class="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3">模板自定义参数</h4>
        <div class="grid grid-cols-3 gap-3">
          <div><label for="sc-tpl-fontsize" class="block text-[11px] text-slate-400 mb-1">Font Size</label><input id="sc-tpl-fontsize" type="text" :value="modelValue.templateFontSize" @input="updateField('templateFontSize', $event.target.value)" placeholder="28px" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"/></div>
          <div><label for="sc-tpl-txtcolor" class="block text-[11px] text-slate-400 mb-1">Text Color</label><input id="sc-tpl-txtcolor" type="text" :value="modelValue.templateTextColor" @input="updateField('templateTextColor', $event.target.value)" placeholder="#ffffff" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"/></div>
          <div><label for="sc-tpl-bgcolor" class="block text-[11px] text-slate-400 mb-1">Background</label><input id="sc-tpl-bgcolor" type="text" :value="modelValue.templateBgColor" @input="updateField('templateBgColor', $event.target.value)" placeholder="#000000" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-cyan-500/50"/></div>
        </div>
      </div>

      <div class="flex items-center gap-3 pt-2">
        <button @click="$emit('test-connection')" class="px-4 py-2 rounded-lg bg-purple-500/20 text-purple-300 text-xs hover:bg-purple-500/30 transition-colors">测试连接</button>
        <span class="text-xs text-slate-500">配置自动保存到本地浏览器</span>
      </div>
    </div>
  </div>
</template>
