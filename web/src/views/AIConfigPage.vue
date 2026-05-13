<template>
  <div class="p-6">
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-slate-100">AI 模型配置中心</h1>
      <p class="text-sm text-slate-400 mt-1">管理所有 AI 模型的 API 密钥和端点配置，配置变更即时生效</p>
    </div>
    <div v-if="loading" class="text-slate-400 text-center py-12">加载中...</div>
    <div v-else class="max-w-3xl space-y-5">
      <!-- LLM -->
      <section class="rounded-xl border border-gray-700/50 p-5" style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);">
        <div class="flex items-center gap-2 mb-3">
          <h2 class="font-semibold text-slate-200">大语言模型 (LLM)</h2>
          <span class="text-xs text-slate-500">— 用于生成剧本、分镜和对话</span>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <label class="text-xs text-slate-400">
            服务商 (Provider) <span class="text-sky-400 cursor-help" title="LLM 服务提供商：deepseek / openai / google / custom">[?]</span>
            <input v-model="models.llm_provider" placeholder="如 deepseek" class="w-full rounded-lg px-3 py-2 mt-1 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </label>
          <label class="text-xs text-slate-400">
            API 密钥 <span class="text-sky-400 cursor-help" title="从 LLM 服务商后台获取，密钥加密存储不会明文展示">[?]</span>
            <input type="password" v-model="models.llm_api_key" placeholder="sk-xxx..." class="w-full rounded-lg px-3 py-2 mt-1 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </label>
          <label class="text-xs text-slate-400">
            接口地址 (Base URL) <span class="text-sky-400 cursor-help" title="API 端点地址，如 https://api.deepseek.com/v1">[?]</span>
            <input v-model="models.llm_base_url" placeholder="https://api.deepseek.com/v1" class="w-full rounded-lg px-3 py-2 mt-1 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </label>
          <label class="text-xs text-slate-400">
            模型名称 <span class="text-sky-400 cursor-help" title="具体模型 ID，如 deepseek-chat / gpt-4o / gemini-2.5-pro">[?]</span>
            <input v-model="models.llm_model" placeholder="deepseek-chat" class="w-full rounded-lg px-3 py-2 mt-1 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </label>
        </div>
      </section>

      <!-- 视频模型 -->
      <section class="rounded-xl border border-gray-700/50 p-5" style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);">
        <div class="flex items-center gap-2 mb-3">
          <h2 class="font-semibold text-slate-200">视频生成模型</h2>
          <span class="text-xs text-slate-500">— Seedance / Kling / Wan2.7</span>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <label class="text-xs text-slate-400">
            Seedance API 密钥 <span class="text-sky-400 cursor-help" title="火山方舟 Ark API Key，用于 Seedance 2.0 视频生成">[?]</span>
            <input type="password" v-model="models.seedance_api_key" placeholder="从火山方舟控制台获取" class="w-full rounded-lg px-3 py-2 mt-1 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </label>
          <label class="text-xs text-slate-400">
            Kling Access Key <span class="text-sky-400 cursor-help" title="快手可灵 API Access Key，用于 Kling 3.0 AI 导演运镜">[?]</span>
            <input type="password" v-model="models.kling_access_key" placeholder="从可灵开放平台获取" class="w-full rounded-lg px-3 py-2 mt-1 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </label>
          <label class="text-xs text-slate-400">
            Kling Secret Key <span class="text-sky-400 cursor-help" title="快手可灵 API Secret Key，配合 Access Key 进行签名认证">[?]</span>
            <input type="password" v-model="models.kling_secret_key" placeholder="从可灵开放平台获取" class="w-full rounded-lg px-3 py-2 mt-1 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </label>
          <label class="text-xs text-slate-400">
            RunningHub API 密钥 <span class="text-sky-400 cursor-help" title="RunningHub API Key，用于 ComfyUI workflow（FLUX/SDXL/Wan2.7）">[?]</span>
            <input type="password" v-model="models.runninghub_api_key" placeholder="从 RunningHub 控制台获取" class="w-full rounded-lg px-3 py-2 mt-1 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </label>
        </div>
      </section>

      <!-- ComfyUI -->
      <section class="rounded-xl border border-gray-700/50 p-5" style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);">
        <div class="flex items-center gap-2 mb-3">
          <h2 class="font-semibold text-slate-200">ComfyUI 服务</h2>
          <span class="text-xs text-slate-500">— 本地/远程 ComfyUI 实例</span>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <label class="text-xs text-slate-400">
            ComfyUI 服务地址 <span class="text-sky-400 cursor-help" title="ComfyUI 实例的完整 URL，如 http://127.0.0.1:8188">[?]</span>
            <input v-model="models.comfyui_url" placeholder="http://127.0.0.1:8188" class="w-full rounded-lg px-3 py-2 mt-1 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </label>
          <label class="text-xs text-slate-400">
            ComfyUI API 密钥 <span class="text-sky-400 cursor-help" title="ComfyUI v0.1.11+ 的 API Key，如未设置则留空">[?]</span>
            <input type="password" v-model="models.comfyui_api_key" placeholder="可选，ComfyUI v0.1.11+ 需要" class="w-full rounded-lg px-3 py-2 mt-1 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </label>
        </div>
      </section>

      <!-- OSS -->
      <section class="rounded-xl border border-gray-700/50 p-5" style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);">
        <div class="flex items-center gap-2 mb-3">
          <h2 class="font-semibold text-slate-200">OSS 对象存储</h2>
          <span class="text-xs text-slate-500">— 参考图上传 CDN，供 Seedance/Kling API 访问</span>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <label class="text-xs text-slate-400">
            存储类型 <span class="text-sky-400 cursor-help" title="local=本地文件, minio=MinIO S3, aliyun_oss=阿里云OSS">[?]</span>
            <input v-model="models.oss_provider" placeholder="local / minio / aliyun_oss" class="w-full rounded-lg px-3 py-2 mt-1 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </label>
          <label class="text-xs text-slate-400">
            端点地址 <span class="text-sky-400 cursor-help" title="OSS 服务端点，如 oss-cn-shanghai.aliyuncs.com">[?]</span>
            <input v-model="models.oss_endpoint" placeholder="oss-cn-shanghai.aliyuncs.com" class="w-full rounded-lg px-3 py-2 mt-1 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </label>
          <label class="text-xs text-slate-400">
            存储桶 <span class="text-sky-400 cursor-help" title="OSS Bucket 名称">[?]</span>
            <input v-model="models.oss_bucket" placeholder="dy-auto-assets" class="w-full rounded-lg px-3 py-2 mt-1 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </label>
          <label class="text-xs text-slate-400">
            Access Key <span class="text-sky-400 cursor-help" title="OSS 访问密钥 AccessKey">[?]</span>
            <input type="password" v-model="models.oss_access_key" placeholder="OSS Access Key" class="w-full rounded-lg px-3 py-2 mt-1 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </label>
          <label class="text-xs text-slate-400">
            Secret Key <span class="text-sky-400 cursor-help" title="OSS 访问密钥 SecretKey">[?]</span>
            <input type="password" v-model="models.oss_secret_key" placeholder="OSS Secret Key" class="w-full rounded-lg px-3 py-2 mt-1 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </label>
        </div>
      </section>

      <div class="flex items-center gap-3">
        <button @click="save" class="bg-sky-500 hover:bg-sky-400 text-white px-6 py-3 rounded-lg transition disabled:opacity-50 cursor-pointer" :disabled="saving" :title="saving ? '正在加密保存...' : '仅保存修改过的字段，密钥将 AES 加密存储'">
          {{ saving ? '保存中...' : '保存全部配置' }}
        </button>
        <span v-if="saved" class="text-emerald-400 text-sm">已保存 ✓</span>
        <span v-if="error" class="text-red-400 text-sm">{{ error }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getModels, updateModels } from '../api/aiConfig.js'
const models = reactive({}); const _originals = {}; const loading = ref(true); const saving = ref(false); const saved = ref(false); const error = ref('')
onMounted(async () => { try { const { data } = await getModels(); if (data.ok) { Object.assign(models, data.models); Object.assign(_originals, data.models) } } catch (e) { error.value = e.message || '加载失败' } finally { loading.value = false } })
async function save() { saving.value = true; saved.value = false; error.value = ''; const changed = {}; for (const [k, v] of Object.entries(models)) { if (v !== _originals[k]) changed[k] = v }; try { await updateModels(changed); Object.assign(_originals, changed); saved.value = true; setTimeout(() => saved.value = false, 3000) } catch (e) { error.value = e.message || '保存失败' } finally { saving.value = false } }
</script>
