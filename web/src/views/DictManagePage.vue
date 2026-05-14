<template>
  <div class="p-6">
    <h1 class="text-2xl font-bold text-slate-100 mb-1">系统字典管理</h1>
    <p class="text-sm text-slate-400 mb-6">管理字典分类和下拉选项：添加、修改、删除分类及选项值</p>

    <!-- 分类管理区 -->
    <div class="flex gap-2 mb-6 flex-wrap items-center">
      <button v-for="cat in categories" :key="cat.id" @click="currentCat = cat.key"
              class="px-3 py-1.5 rounded-lg text-sm transition cursor-pointer relative group"
              :class="currentCat === cat.key ? 'bg-sky-600 text-white' : 'bg-gray-800 text-slate-300 hover:bg-gray-700'">
        {{ cat.label }}
        <span class="ml-1 text-xs opacity-60">({{ cat.item_count ?? 0 }})</span>
        <span class="hidden group-hover:inline-flex ml-2 gap-1">
          <button @click.stop="startEditCat(cat)" class="text-yellow-400 hover:text-yellow-300 text-xs" title="编辑">✎</button>
          <button @click.stop="removeCategory(cat)" class="text-red-400 hover:text-red-300 text-xs" title="删除">✕</button>
        </span>
      </button>
      <!-- 新增分类 -->
      <div v-if="addingCat" class="flex items-center gap-1 bg-gray-800 rounded-lg px-2 py-1">
        <input v-model="newCatLabel" @keyup.enter="addCategory" placeholder="分类名" class="w-20 rounded px-2 py-0.5 bg-gray-700 border border-gray-600 text-slate-100 text-sm placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-sky-500/50" />
        <input v-model="newCatKey" placeholder="key" class="w-16 rounded px-2 py-0.5 bg-gray-700 border border-gray-600 text-slate-100 text-sm placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-sky-500/50" />
        <button @click="addCategory" class="px-2 py-0.5 bg-sky-500 hover:bg-sky-400 text-white rounded text-xs cursor-pointer">✓</button>
        <button @click="cancelAddCat" class="px-2 py-0.5 text-slate-400 hover:text-slate-200 text-xs cursor-pointer">✕</button>
      </div>
      <button v-else @click="addingCat = true" class="px-3 py-1.5 border border-dashed border-gray-500 text-gray-400 hover:text-slate-200 hover:border-gray-300 rounded-lg text-sm transition cursor-pointer">+ 新增分类</button>
    </div>

    <!-- 编辑分类弹窗 -->
    <div v-if="editingCat" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div class="bg-gray-800 rounded-xl p-6 w-96 border border-gray-600">
        <h3 class="text-lg font-semibold text-slate-100 mb-4">编辑分类</h3>
        <label class="block text-sm text-slate-300 mb-1">Key (唯一标识)</label>
        <input v-model="editCatKey" class="w-full rounded-lg px-3 py-2 bg-gray-700 border border-gray-600 text-slate-100 mb-3 focus:outline-none focus:ring-2 focus:ring-sky-500/50" />
        <label class="block text-sm text-slate-300 mb-1">Label (显示名)</label>
        <input v-model="editCatLabel" class="w-full rounded-lg px-3 py-2 bg-gray-700 border border-gray-600 text-slate-100 mb-4 focus:outline-none focus:ring-2 focus:ring-sky-500/50" />
        <div class="flex gap-2 justify-end">
          <button @click="cancelEditCat" class="px-4 py-2 rounded-lg bg-gray-600 hover:bg-gray-500 text-white text-sm cursor-pointer">取消</button>
          <button @click="saveCategory" class="px-4 py-2 rounded-lg bg-sky-500 hover:bg-sky-400 text-white text-sm cursor-pointer">保存</button>
        </div>
      </div>
    </div>

    <!-- 选项列表 -->
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
import {
  listCategories, createCategory, updateCategory, deleteCategory,
  listAllItems, createItem, updateItem, deleteItem,
} from '../api/referenceData.js'

const categories = ref([])
const currentCat = ref('')
const items = ref([])
const newLabel = ref('')
const newValue = ref('')

const addingCat = ref(false)
const newCatKey = ref('')
const newCatLabel = ref('')
const editingCat = ref(null)
const editCatKey = ref('')
const editCatLabel = ref('')

async function loadCategories() {
  const { data } = await listCategories()
  if (data.ok) {
    categories.value = data.categories
    if (!currentCat.value && data.categories.length) {
      currentCat.value = data.categories[0].key
    }
  }
}

async function addCategory() {
  if (!newCatLabel.value.trim()) return
  const key = newCatKey.value.trim() || newCatLabel.value.trim()
  await createCategory({ key, label: newCatLabel.value.trim() })
  newCatKey.value = ''; newCatLabel.value = ''; addingCat.value = false
  await loadCategories()
}

function cancelAddCat() {
  newCatKey.value = ''; newCatLabel.value = ''; addingCat.value = false
}

function startEditCat(cat) {
  editingCat.value = cat
  editCatKey.value = cat.key
  editCatLabel.value = cat.label
}

function cancelEditCat() {
  editingCat.value = null
}

async function saveCategory() {
  if (!editingCat.value) return
  await updateCategory(editingCat.value.id, { key: editCatKey.value, label: editCatLabel.value })
  editingCat.value = null
  await loadCategories()
}

async function removeCategory(cat) {
  await deleteCategory(cat.id)
  if (currentCat.value === cat.key) currentCat.value = ''
  await loadCategories()
  if (!currentCat.value && categories.value.length) {
    currentCat.value = categories.value[0].key
  }
}

async function load() {
  if (!currentCat.value) { items.value = []; return }
  const { data } = await listAllItems(currentCat.value)
  if (data.ok) items.value = data.items
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
onMounted(async () => { await loadCategories(); await load() })
</script>
