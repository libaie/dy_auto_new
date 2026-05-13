<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-gray-900">场景资产库</h1>
      <button @click="showCreate = true" class="bg-blue-600 text-white px-4 py-2 rounded-lg">+ 新建场景</button>
    </div>
    <div v-if="loading" class="text-gray-500 text-center py-12">加载中...</div>
    <div v-else-if="scenes.length === 0" class="text-gray-400 text-center py-12">暂无场景</div>
    <div v-else class="grid grid-cols-3 gap-4">
      <div v-for="s in scenes" :key="s.id" class="bg-white rounded-xl border p-4 hover:shadow-md transition">
        <h3 class="font-semibold text-gray-900">{{ s.name }}</h3>
        <div class="flex gap-2 mt-2 text-xs">
          <span class="px-2 py-1 rounded bg-gray-100">{{ s.scene_type }}</span>
          <span class="px-2 py-1 rounded bg-gray-100">{{ s.lighting || '-' }}</span>
          <span class="px-2 py-1 rounded bg-gray-100">{{ s.mood || '-' }}</span>
        </div>
        <p class="text-sm text-gray-500 mt-2">{{ s.location_desc || '(无地点描述)' }}</p>
        <div class="flex gap-1 mt-2">
          <span v-if="s.reference_wideshot_url" class="text-xs text-green-600">广角 ✓</span>
          <span v-else class="text-xs text-gray-400">广角 —</span>
          <span v-if="s.reference_midshot_url" class="text-xs text-green-600">中景 ✓</span>
          <span v-else class="text-xs text-gray-400">中景 —</span>
          <span v-if="s.reference_aerial_url" class="text-xs text-green-600">俯拍 ✓</span>
          <span v-else class="text-xs text-gray-400">俯拍 —</span>
        </div>
      </div>
    </div>

    <div v-if="showCreate" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl p-6 w-full max-w-md shadow-xl">
        <h2 class="text-lg font-semibold mb-4">新建场景</h2>
        <div class="space-y-3">
          <input v-model="form.name" placeholder="场景名称" class="w-full border rounded-lg px-3 py-2" />
          <select v-model="form.scene_type" class="w-full border rounded-lg px-3 py-2">
            <option value="indoor">室内</option><option value="outdoor">室外</option>
            <option value="transition">转场</option><option value="special">特殊</option>
          </select>
          <input v-model="form.location_desc" placeholder="地点描述" class="w-full border rounded-lg px-3 py-2" />
          <div class="flex gap-3">
            <select v-model="form.lighting" class="border rounded-lg px-3 py-2 flex-1">
              <option value="">光照</option>
              <option value="白天">白天</option><option value="黄昏">黄昏</option>
              <option value="夜晚">夜晚</option><option value="室内暖光">室内暖光</option>
            </select>
            <select v-model="form.mood" class="border rounded-lg px-3 py-2 flex-1">
              <option value="">氛围</option>
              <option value="温馨">温馨</option><option value="紧张">紧张</option>
              <option value="浪漫">浪漫</option><option value="悬疑">悬疑</option>
            </select>
          </div>
        </div>
        <div class="flex justify-end gap-3 mt-6">
          <button @click="showCreate = false" class="px-4 py-2 border rounded-lg">取消</button>
          <button @click="doCreate" class="px-4 py-2 bg-blue-600 text-white rounded-lg">创建</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { listScenes, createScene } from '../api/scenes.js'
const scenes = ref([]); const loading = ref(true); const showCreate = ref(false)
const form = reactive({ name: '', scene_type: 'indoor', location_desc: '', lighting: '', mood: '' })
async function load() { const { data } = await listScenes(); scenes.value = data.ok ? data.scenes : []; loading.value = false }
async function doCreate() { await createScene({ ...form }); showCreate.value = false; await load() }
onMounted(load)
</script>
