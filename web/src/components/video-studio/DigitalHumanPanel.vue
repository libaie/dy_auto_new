<!-- 视频工作台组件：承载 Pixelle、Seedance、媒体面板和生成参数相关业务配置。 -->
<script setup>
import { ref } from 'vue'
import { runPixelleVideoGeneration, uploadPixelleFiles } from './pixelleGeneration.js'

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
const videoUrl = ref('')

// 前端业务函数：协调 handleCharacters 对应的页面流程、接口调用或状态转换。
function handleCharacters(e) { characterFiles.value = Array.from(e.target.files || []) }
// 前端业务函数：协调 handleGoods 对应的页面流程、接口调用或状态转换。
function handleGoods(e) { goodsFiles.value = Array.from(e.target.files || []) }

// 前端业务函数：协调 handleGenerate 对应的页面流程、接口调用或状态转换。
async function handleGenerate() {
  if (characterFiles.value.length === 0) return
  generating.value = true; result.value = null; videoUrl.value = ''
  progress.value = { percent: 0, message: '正在上传数字人素材...' }
  try {
    const characterPaths = await uploadPixelleFiles(characterFiles.value)
    const goodsPaths = await uploadPixelleFiles(goodsFiles.value)
    const payload = {
      text: goodsText.value || goodsTitle.value || 'digital human video',
      mode: 'generate',
      n_scenes: 1,
      tts_voice: ttsVoice.value,
      tts_speed: ttsSpeed.value,
      character_paths: characterPaths,
      goods_paths: goodsPaths,
    }
    if (goodsTitle.value) payload.title = goodsTitle.value
    progress.value = { percent: 2, message: '正在提交任务...' }
    const done = await runPixelleVideoGeneration(payload, {
      onProgress: (p) => {
        progress.value.percent = p.percent ?? Math.min(95, progress.value.percent + 0.5)
        progress.value.message = p.message
      },
    })
    result.value = done
    videoUrl.value = done.videoUrl
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
      <div v-if="result?.success" class="mb-4">
        <div class="text-xs text-emerald-400 mb-2">生成完成!</div>
        <video v-if="videoUrl" :src="videoUrl" controls class="w-full rounded-lg" style="max-height:260px"/>
        <a v-if="videoUrl" :href="videoUrl" download class="mt-2 inline-flex text-xs text-cyan-300 hover:text-cyan-200">下载视频</a>
        <div v-else class="text-xs text-amber-300">任务已完成，但未返回视频路径</div>
      </div>
      <div v-if="result && !result.success" class="text-xs text-red-400">{{ result.error }}</div>
    </div>
  </div>
</template>
