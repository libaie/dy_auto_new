<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-slate-100">场景资产库</h1>
      <button @click="showCreate = true" class="bg-sky-500 hover:bg-sky-400 text-white px-4 py-2 rounded-lg transition cursor-pointer">+ 新建场景</button>
    </div>
    <div v-if="loading" class="text-slate-400 text-center py-12">加载中...</div>
    <div v-else-if="scenes.length === 0" class="text-slate-500 text-center py-12">暂无场景</div>
    <div v-else class="grid grid-cols-3 gap-4">
      <div v-for="s in scenes" :key="s.id"
           class="rounded-xl border border-gray-700/50 p-4 hover:shadow-lg hover:shadow-sky-900/10 transition-all duration-200"
           style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);">
        <h3 class="font-semibold text-slate-100">{{ s.name }}</h3>
        <div class="flex gap-2 mt-2 text-xs">
          <span class="px-2 py-1 rounded bg-gray-800 text-slate-400">{{ s.scene_type }}</span>
          <span class="px-2 py-1 rounded bg-gray-800 text-slate-400">{{ s.lighting || '-' }}</span>
          <span class="px-2 py-1 rounded bg-gray-800 text-slate-400">{{ s.mood || '-' }}</span>
        </div>
        <p class="text-sm text-slate-400 mt-2">{{ s.location_desc || '(无地点描述)' }}</p>
        <div class="flex gap-1 mt-2">
          <span :class="s.reference_wideshot_url ? 'text-emerald-400' : 'text-slate-600'" class="text-xs">{{ s.reference_wideshot_url ? '广角 ✓' : '广角 —' }}</span>
          <span :class="s.reference_midshot_url ? 'text-emerald-400' : 'text-slate-600'" class="text-xs">{{ s.reference_midshot_url ? '中景 ✓' : '中景 —' }}</span>
          <span :class="s.reference_aerial_url ? 'text-emerald-400' : 'text-slate-600'" class="text-xs">{{ s.reference_aerial_url ? '俯拍 ✓' : '俯拍 —' }}</span>
        </div>
      </div>
    </div>

    <div v-if="showCreate" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50" @click.self="showCreate = false">
      <div class="rounded-xl p-6 w-full max-w-md shadow-2xl border border-gray-700/50" style="background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(20px);">
        <h2 class="text-lg font-semibold text-slate-100 mb-4">新建场景</h2>
        <div class="space-y-3">
          <input v-model="form.name" placeholder="场景名称" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          <select v-model="form.scene_type" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 cursor-pointer"><option value="indoor">室内</option><option value="outdoor">室外</option><option value="transition">转场</option><option value="special">特殊</option></select>
          <input v-model="form.location_desc" placeholder="地点描述" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          <div class="flex gap-3">
            <select v-model="form.lighting" class="rounded-lg px-3 py-2 flex-1 bg-gray-800 border border-gray-600 text-slate-100 cursor-pointer"><option value="">光照</option><option value="白天">白天</option><option value="黄昏">黄昏</option><option value="夜晚">夜晚</option><option value="室内暖光">室内暖光</option></select>
            <select v-model="form.mood" class="rounded-lg px-3 py-2 flex-1 bg-gray-800 border border-gray-600 text-slate-100 cursor-pointer"><option value="">氛围</option><option value="温馨">温馨</option><option value="紧张">紧张</option><option value="浪漫">浪漫</option><option value="悬疑">悬疑</option></select>
          </div>
        </div>
        <div class="flex justify-end gap-3 mt-6">
          <button @click="showCreate = false" class="px-4 py-2 rounded-lg border border-gray-600 text-slate-300 hover:bg-gray-700 transition cursor-pointer">取消</button>
          <button @click="doCreate" class="px-4 py-2 bg-sky-500 hover:bg-sky-400 text-white rounded-lg transition cursor-pointer">创建</button>
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
