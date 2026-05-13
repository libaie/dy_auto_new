<template>
  <div class="p-6">
    <h1 class="text-2xl font-bold text-gray-900 mb-6">AI 模型配置中心</h1>

    <div v-if="loading" class="text-gray-500 text-center py-12">加载中...</div>
    <div v-else class="max-w-3xl space-y-6">
      <!-- LLM -->
      <section class="bg-white rounded-xl border p-5">
        <h2 class="font-semibold text-gray-700 mb-3">LLM 模型</h2>
        <div class="grid grid-cols-2 gap-3">
          <label class="text-xs text-gray-500">Provider <input v-model="models.llm_provider" class="w-full border rounded px-3 py-2 mt-1" /></label>
          <label class="text-xs text-gray-500">API Key <input v-model="models.llm_api_key" type="password" class="w-full border rounded px-3 py-2 mt-1" /></label>
          <label class="text-xs text-gray-500">Base URL <input v-model="models.llm_base_url" class="w-full border rounded px-3 py-2 mt-1" /></label>
          <label class="text-xs text-gray-500">Model <input v-model="models.llm_model" class="w-full border rounded px-3 py-2 mt-1" /></label>
        </div>
      </section>

      <!-- Video Models -->
      <section class="bg-white rounded-xl border p-5">
        <h2 class="font-semibold text-gray-700 mb-3">视频模型</h2>
        <div class="grid grid-cols-2 gap-3">
          <label class="text-xs text-gray-500">Seedance API Key <input v-model="models.seedance_api_key" type="password" class="w-full border rounded px-3 py-2 mt-1" /></label>
          <label class="text-xs text-gray-500">Kling Access Key <input v-model="models.kling_access_key" type="password" class="w-full border rounded px-3 py-2 mt-1" /></label>
          <label class="text-xs text-gray-500">Kling Secret Key <input v-model="models.kling_secret_key" type="password" class="w-full border rounded px-3 py-2 mt-1" /></label>
          <label class="text-xs text-gray-500">RunningHub API Key <input v-model="models.runninghub_api_key" type="password" class="w-full border rounded px-3 py-2 mt-1" /></label>
        </div>
      </section>

      <!-- ComfyUI -->
      <section class="bg-white rounded-xl border p-5">
        <h2 class="font-semibold text-gray-700 mb-3">ComfyUI</h2>
        <div class="grid grid-cols-2 gap-3">
          <label class="text-xs text-gray-500">ComfyUI URL <input v-model="models.comfyui_url" class="w-full border rounded px-3 py-2 mt-1" /></label>
          <label class="text-xs text-gray-500">ComfyUI API Key <input v-model="models.comfyui_api_key" type="password" class="w-full border rounded px-3 py-2 mt-1" /></label>
        </div>
      </section>

      <!-- OSS -->
      <section class="bg-white rounded-xl border p-5">
        <h2 class="font-semibold text-gray-700 mb-3">OSS 存储</h2>
        <div class="grid grid-cols-2 gap-3">
          <label class="text-xs text-gray-500">Provider <input v-model="models.oss_provider" class="w-full border rounded px-3 py-2 mt-1" /></label>
          <label class="text-xs text-gray-500">Endpoint <input v-model="models.oss_endpoint" class="w-full border rounded px-3 py-2 mt-1" /></label>
          <label class="text-xs text-gray-500">Bucket <input v-model="models.oss_bucket" class="w-full border rounded px-3 py-2 mt-1" /></label>
          <label class="text-xs text-gray-500">Access Key <input v-model="models.oss_access_key" type="password" class="w-full border rounded px-3 py-2 mt-1" /></label>
          <label class="text-xs text-gray-500">Secret Key <input v-model="models.oss_secret_key" type="password" class="w-full border rounded px-3 py-2 mt-1" /></label>
        </div>
      </section>

      <button @click="save" class="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700" :disabled="saving">
        {{ saving ? '保存中...' : '保存全部配置' }}
      </button>
      <span v-if="saved" class="text-green-600 text-sm ml-3">已保存</span>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getModels, updateModels } from '../api/aiConfig.js'

const models = reactive({})
const loading = ref(true)
const saving = ref(false)
const saved = ref(false)

onMounted(async () => {
  const { data } = await getModels()
  if (data.ok) Object.assign(models, data.models)
  loading.value = false
})

async function save() {
  saving.value = true
  saved.value = false
  await updateModels({ ...models })
  saving.value = false
  saved.value = true
  setTimeout(() => saved.value = false, 3000)
}
</script>
