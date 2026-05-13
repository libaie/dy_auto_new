<template>
  <div class="p-6">
    <h1 class="text-2xl font-bold text-slate-100 mb-6">AI 模型配置中心</h1>
    <div v-if="loading" class="text-slate-400 text-center py-12">加载中...</div>
    <div v-else class="max-w-3xl space-y-5">
      <section v-for="section in sections" :key="section.title"
               class="rounded-xl border border-gray-700/50 p-5" style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);">
        <h2 class="font-semibold text-slate-200 mb-3">{{ section.title }}</h2>
        <div class="grid grid-cols-2 gap-3">
          <label v-for="field in section.fields" :key="field.key" class="text-xs text-slate-400">
            {{ field.label }}
            <input :type="field.secret ? 'password' : 'text'" v-model="models[field.key]"
                   class="w-full rounded-lg px-3 py-2 mt-1 bg-gray-800 border border-gray-600 text-slate-100
                          placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </label>
        </div>
      </section>

      <div class="flex items-center gap-3">
        <button @click="save" class="bg-sky-500 hover:bg-sky-400 text-white px-6 py-3 rounded-lg transition disabled:opacity-50 cursor-pointer" :disabled="saving">
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

const sections = [
  { title: 'LLM 模型', fields: [{ key: 'llm_provider', label: 'Provider' }, { key: 'llm_api_key', label: 'API Key', secret: true }, { key: 'llm_base_url', label: 'Base URL' }, { key: 'llm_model', label: 'Model' }] },
  { title: '视频模型', fields: [{ key: 'seedance_api_key', label: 'Seedance API Key', secret: true }, { key: 'kling_access_key', label: 'Kling Access Key', secret: true }, { key: 'kling_secret_key', label: 'Kling Secret Key', secret: true }, { key: 'runninghub_api_key', label: 'RunningHub API Key', secret: true }] },
  { title: 'ComfyUI', fields: [{ key: 'comfyui_url', label: 'ComfyUI URL' }, { key: 'comfyui_api_key', label: 'ComfyUI API Key', secret: true }] },
  { title: 'OSS 存储', fields: [{ key: 'oss_provider', label: 'Provider' }, { key: 'oss_endpoint', label: 'Endpoint' }, { key: 'oss_bucket', label: 'Bucket' }, { key: 'oss_access_key', label: 'Access Key', secret: true }, { key: 'oss_secret_key', label: 'Secret Key', secret: true }] },
]

onMounted(async () => { try { const { data } = await getModels(); if (data.ok) { Object.assign(models, data.models); Object.assign(_originals, data.models) } } catch (e) { error.value = e.message || '加载失败' } finally { loading.value = false } })

async function save() { saving.value = true; saved.value = false; error.value = ''; const changed = {}; for (const [k, v] of Object.entries(models)) { if (v !== _originals[k]) changed[k] = v }; try { await updateModels(changed); Object.assign(_originals, changed); saved.value = true; setTimeout(() => saved.value = false, 3000) } catch (e) { error.value = e.message || '保存失败' } finally { saving.value = false } }
</script>
