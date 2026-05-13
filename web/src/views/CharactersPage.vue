<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold text-gray-900">角色资产库</h1>
      <button @click="showCreate = true" class="bg-blue-600 text-white px-4 py-2 rounded-lg">+ 新建角色</button>
    </div>

    <div v-if="loading" class="text-gray-500 text-center py-12">加载中...</div>
    <div v-else-if="error" class="text-red-500 text-center py-12">{{ error }}</div>
    <div v-else-if="characters.length === 0" class="text-gray-400 text-center py-12">暂无角色</div>
    <div v-else class="grid grid-cols-4 gap-4">
      <div v-for="c in characters" :key="c.id" class="bg-white rounded-xl border p-4 text-center hover:shadow-md transition">
        <div class="w-20 h-20 mx-auto bg-gray-100 rounded-full flex items-center justify-center text-2xl mb-3">
          {{ c.name[0] }}
        </div>
        <h3 class="font-semibold text-gray-900">{{ c.name }}</h3>
        <span class="text-xs px-2 py-1 rounded mt-1 inline-block"
              :class="roleClass(c.role_type)">{{ c.role_type }}</span>
        <div class="mt-2 text-xs text-gray-400">{{ c.gender }}</div>
      </div>
    </div>

    <!-- 新建角色 Dialog -->
    <div v-if="showCreate" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-xl p-6 w-full max-w-md shadow-xl">
        <h2 class="text-lg font-semibold mb-4">新建角色</h2>
        <div class="space-y-3">
          <input v-model="form.name" placeholder="角色名称" class="w-full border rounded-lg px-3 py-2" />
          <div class="flex gap-3">
            <select v-model="form.role_type" class="border rounded-lg px-3 py-2 flex-1">
              <option value="protagonist">主角</option><option value="antagonist">反派</option>
              <option value="supporting">配角</option><option value="cameo">客串</option>
            </select>
            <select v-model="form.gender" class="border rounded-lg px-3 py-2">
              <option value="male">男</option><option value="female">女</option>
            </select>
          </div>
          <textarea v-model="form.appearance_desc" placeholder="外观描述" class="w-full border rounded-lg px-3 py-2" rows="2" />
          <textarea v-model="form.outfit_desc" placeholder="服装描述" class="w-full border rounded-lg px-3 py-2" rows="2" />
          <textarea v-model="form.personality" placeholder="性格描述" class="w-full border rounded-lg px-3 py-2" rows="2" />
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
import { listCharacters, createCharacter } from '../api/characters.js'

const characters = ref([])
const loading = ref(true)
const showCreate = ref(false)
const error = ref('')
const form = reactive({ name: '', role_type: 'protagonist', gender: 'male', appearance_desc: '', outfit_desc: '', personality: '' })

async function load() {
  loading.value = true; error.value = ''
  try { const { data } = await listCharacters(); characters.value = data.ok ? data.characters : [] }
  catch (e) { error.value = e.message || '加载失败' }
  finally { loading.value = false }
}

async function doCreate() {
  try { await createCharacter({ ...form }); showCreate.value = false; await load() }
  catch (e) { error.value = e.message || '创建失败' }
}

function roleClass(r) {
  return { protagonist: 'bg-blue-100 text-blue-700', antagonist: 'bg-red-100 text-red-700',
           supporting: 'bg-green-100 text-green-700', cameo: 'bg-gray-100 text-gray-600' }[r] || ''
}

onMounted(load)
</script>
