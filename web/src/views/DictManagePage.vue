<template>
  <div class="p-6">
    <h1 class="text-2xl font-bold text-slate-100 mb-1">系统字典管理</h1>
    <p class="text-sm text-slate-400 mb-6">管理所有下拉选项：系列类型、角色类型、场景属性等</p>

    <!-- 分类 tabs -->
    <div class="flex gap-2 mb-6 flex-wrap">
      <button v-for="cat in categories" :key="cat.key" @click="currentCat = cat.key"
              class="px-3 py-1.5 rounded-lg text-sm transition cursor-pointer"
              :class="currentCat === cat.key ? 'bg-sky-600 text-white' : 'bg-gray-800 text-slate-300 hover:bg-gray-700'">
        {{ cat.label }}
        <span class="ml-1 text-xs opacity-60">({{ cat.count }})</span>
      </button>
    </div>

    <!-- 列表 -->
    <div class="rounded-xl border border-gray-700/50 overflow-hidden" style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);">
      <div class="px-4 py-2 border-b border-gray-700/50 flex items-center gap-3">
        <input v-model="newLabel" @keyup.enter="addItem" placeholder="+ 新增选项 (回车添加)" class="flex-1 rounded-lg px-3 py-1.5 bg-gray-800 border border-gray-600 text-slate-100 text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
        <input v-model="newValue" placeholder="value" class="w-32 rounded-lg px-3 py-1.5 bg-gray-800 border border-gray-600 text-slate-100 text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
        <button @click="addItem" class="px-3 py-1.5 bg-sky-500 hover:bg-sky-400 text-white rounded-lg text-sm transition cursor-pointer">添加</button>
      </div>
      <div class="divide-y divide-gray-700/30 max-h-[500px] overflow-y-auto">
        <div v-for="item in items" :key="item.id" class="px-4 py-2.5 flex items-center gap-3 hover:bg-gray-800/30 transition">
          <span class="text-xs text-slate-500 font-mono w-20">{{ item.value }}</span>
          <input :value="item.label" @blur="e => saveLabel(item, e.target.value)" class="flex-1 rounded px-2 py-1 bg-transparent text-slate-200 text-sm focus:outline-none focus:bg-gray-800 focus:ring-1 focus:ring-sky-500/30 transition" />
          <button :class="item.enabled ? 'text-emerald-400' : 'text-slate-600'" @click="toggleItem(item)" class="text-xs hover:underline cursor-pointer" :title="item.enabled ? '点击禁用' : '点击启用'">
            {{ item.enabled ? '启用' : '禁用' }}
          </button>
          <button @click="removeItem(item)" class="text-red-400 hover:text-red-300 text-xs cursor-pointer" title="删除">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { listAllItems, createItem, updateItem, deleteItem } from '../api/referenceData.js'

const categories = [
  { key: 'series_genre', label: '系列类型', count: 0 },
  { key: 'character_role', label: '角色类型', count: 0 },
  { key: 'scene_type', label: '场景类型', count: 0 },
  { key: 'scene_lighting', label: '场景光照', count: 0 },
  { key: 'scene_mood', label: '场景氛围', count: 0 },
]

const currentCat = ref('series_genre')
const items = ref([])
const newLabel = ref('')
const newValue = ref('')

async function load() {
  const { data } = await listAllItems(currentCat.value)
  if (data.ok) {
    items.value = data.items
    const cat = categories.find(c => c.key === currentCat.value)
    if (cat) cat.count = items.value.filter(i => i.enabled).length
  }
}

async function addItem() {
  if (!newLabel.value.trim()) return
  await createItem({ category: currentCat.value, value: newValue.value || newLabel.value, label: newLabel.value })
  newLabel.value = ''; newValue.value = ''
  await load()
}

async function saveLabel(item, newLabel) {
  if (newLabel !== item.label) { await updateItem(item.id, { label: newLabel }); item.label = newLabel }
}

async function toggleItem(item) {
  await updateItem(item.id, { enabled: !item.enabled }); await load()
}

async function removeItem(item) {
  await deleteItem(item.id); await load()
}

watch(currentCat, load)
onMounted(load)
</script>
