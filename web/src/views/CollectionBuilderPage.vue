<!-- 管理端业务页面：承载 CollectionBuilderPage 页面流程，协调接口数据、用户操作和业务状态展示。 -->
<template>
  <div class="p-6">
    <div class="mb-6 flex items-start justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-slate-100">Collection Builder</h1>
        <p class="mt-1 text-sm text-slate-500">Package approved episodes without blocking episode delivery.</p>
      </div>
      <button
        data-test="create-collection"
        @click="create"
        :disabled="acting"
        class="rounded-lg bg-cyan-600 px-4 py-2 text-sm text-white hover:bg-cyan-500 disabled:opacity-50"
      >
        Create Collection
      </button>
    </div>

    <div v-if="error" class="py-6 text-red-400">{{ error }}</div>
    <div v-if="collection" class="rounded-lg border border-gray-700/50 bg-slate-900/50 p-4">
      <div class="font-medium text-slate-100">Collection {{ collection.id }}</div>
      <div class="mt-2 text-sm text-slate-400">Status: {{ collection.status }}</div>
      <div class="mt-1 text-sm text-slate-400">Included episodes: {{ collection.included_episode_ids?.length || 0 }}</div>
      <div class="mt-1 text-sm text-slate-400">Duration: {{ collection.duration_seconds }}s</div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { createVideoCollection } from '../api/videoProduction.js'

const route = useRoute()
const collection = ref(null)
const acting = ref(false)
const error = ref('')

// 前端业务函数：协调 create 对应的页面流程、接口调用或状态转换。
// 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
// 出参：返回 create 对应业务流程的处理结果。
async function create() {
  acting.value = true
  error.value = ''
  try {
    const { data } = await createVideoCollection(route.params.seriesId)
    collection.value = data.collection
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || 'Failed to create collection'
  } finally {
    acting.value = false
  }
}
</script>
