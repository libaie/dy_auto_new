<script setup>
import { ref } from 'vue'
import { generateVideoAsync, getTask } from '../../api/pixelle-client.js'

const characterFiles = ref([])
const goodsFiles = ref([])
const goodsTitle = ref('')
const goodsText = ref('')
const ttsVoice = ref('zh-CN-YunjianNeural')
const ttsSpeed = ref(1.2)
const showAdvanced = ref(false)

const generating = ref(false)
const progress = ref({ percent: 0, message: '' })
const result = ref(null)

function handleCharacters(e) { characterFiles.value = Array.from(e.target.files || []) }
function handleGoods(e) { goodsFiles.value = Array.from(e.target.files || []) }

async function handleGenerate() {
  generating.value = true; result.value = null
  try {
    const payload = {
      text: goodsText.value || goodsTitle.value || 'digital human video',
      mode: 'generate',
      n_scenes: 1,
      tts_voice: ttsVoice.value,
      tts_speed: ttsSpeed.value,
    }
    const resp = await generateVideoAsync(payload)
    const taskId = resp.data?.task_id
    if (!taskId) throw new Error('No task ID')
    await new Promise((resolve, reject) => {
      let a = 0; const t = setInterval(async () => {
        a++; if (a > 120) { clearInterval(t); reject(new Error('Timeout')); return }
        try {
          const r = await getTask(taskId)
          if (r.data.status === 'completed') { clearInterval(t); result.value = { success: true, taskId }; resolve() }
          else if (r.data.status === 'failed') { clearInterval(t); reject(new Error(r.data.error)) }
          else { progress.value.percent = Math.min(95, r.data.progress || progress.value.percent + 0.5); progress.value.message = r.data.status }
        } catch {}
      }, 5000)
    })
  } catch (e) { result.value = { success: false, error: e.message } }
  finally { generating.value = false }
}
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
    <!-- Left: Character Assets -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">数字人角色素材</h3>
      <input type="file" multiple accept="image/*,video/*" @change="handleCharacters"
        class="w-full text-xs text-slate-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:text-xs file:bg-cyan-500/20 file:text-cyan-300 file:border-0"/>
      <p class="text-[11px] text-slate-500 mt-2">上传数字人角色图片或视频</p>
      <div v-if="characterFiles.length" class="mt-2 text-xs text-slate-400">已选 {{ characterFiles.length }} 个文件</div>

      <div class="border-t border-white/5 pt-4 mt-4">
        <h3 class="text-sm font-semibold text-white mb-3">商品素材 <span class="text-slate-500 text-xs">(可选)</span></h3>
        <input type="file" multiple accept="image/*" @change="handleGoods"
          class="w-full text-xs text-slate-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:text-xs file:bg-amber-500/20 file:text-amber-300 file:border-0"/>
        <div class="mt-3 space-y-2">
          <input v-model="goodsTitle" placeholder="商品标题" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm"/>
          <textarea v-model="goodsText" placeholder="商品描述" rows="2" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm resize-none"/>
        </div>
      </div>
    </div>

    <!-- Middle: TTS Config -->
    <div class="glass-card p-5">
      <h3 class="text-sm font-semibold text-white mb-4">配音设置</h3>
      <div class="space-y-3">
        <div>
          <label class="block text-xs text-slate-400 mb-1">语音角色</label>
          <select v-model="ttsVoice" class="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-white text-sm">
            <option value="zh-CN-YunjianNeural">云健 (男) — 推荐</option>
            <option value="zh-CN-YunxiNeural">云希 (男)</option>
            <option value="zh-CN-XiaoxiaoNeural">晓晓 (女)</option>
            <option value="zh-CN-XiaobeiNeural">晓北 (女)</option>
          </select>
        </div>
        <div>
          <label class="block text-xs text-slate-400 mb-1">语速: {{ ttsSpeed.toFixed(1) }}x</label>
          <input type="range" min="0.5" max="2.0" step="0.1" v-model.number="ttsSpeed" class="w-full accent-cyan-500"/>
        </div>
      </div>
    </div>

    <!-- Right: Generate -->
    <div class="glass-card p-5 flex flex-col">
      <h3 class="text-sm font-semibold text-white mb-4">生成数字人视频</h3>
      <button @click="handleGenerate" :disabled="generating || characterFiles.length === 0"
        class="w-full py-3 rounded-xl font-medium text-white text-sm transition-all mb-4"
        :class="generating ? 'bg-slate-700' : 'bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400'">
        {{ generating ? '生成中...' : '生成数字人视频' }}
      </button>
      <div v-if="generating" class="mb-4">
        <div class="h-2 rounded-full bg-white/10 overflow-hidden">
          <div class="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all" :style="{width: progress.percent+'%'}"/>
        </div>
        <p class="text-xs text-slate-400 mt-1">{{ progress.message }}</p>
      </div>
      <div v-if="result?.success" class="text-xs text-emerald-400">生成完成!</div>
      <div v-if="result && !result.success" class="text-xs text-red-400">{{ result.error }}</div>
    </div>
  </div>
</template>
