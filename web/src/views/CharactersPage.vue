<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-100">角色资产库</h1>
        <p class="text-sm text-slate-400 mt-1">管理剧中角色，配置外观描述和参考图</p>
      </div>
      <button @click="showCreate = true" class="bg-sky-500 hover:bg-sky-400 text-white px-4 py-2 rounded-lg transition cursor-pointer" title="创建新角色，填写描述后可通过 FLUX 自动生成角色参考图">
        + 新建角色
      </button>
    </div>

    <div v-if="loading" class="text-slate-400 text-center py-12">加载中...</div>
    <div v-else-if="error" class="text-red-400 text-center py-12">{{ error }}</div>
    <div v-else-if="characters.length === 0" class="text-slate-500 text-center py-12">
      暂无角色<br><span class="text-xs text-slate-600 mt-1">提示：创建角色后可在系列详情中关联到具体剧集</span>
    </div>
    <div v-else class="grid grid-cols-4 gap-4">
      <div v-for="c in characters" :key="c.id"
           class="rounded-xl border border-gray-700/50 p-4 text-center hover:shadow-lg hover:shadow-sky-900/10 transition-all duration-200 cursor-pointer"
           style="background: rgba(15, 23, 42, 0.5); backdrop-filter: blur(8px);"
           :title="`${c.name} — ${c.personality || '未设置性格'}`">
        <div class="w-20 h-20 mx-auto rounded-full flex items-center justify-center text-2xl mb-3" style="background: rgba(255,255,255,0.06);">
          {{ c.name[0] }}
        </div>
        <h3 class="font-semibold text-slate-100">{{ c.name }}</h3>
        <span class="text-xs px-2 py-1 rounded mt-1 inline-block" :class="roleClass(c.role_type)">{{ roleLabel(c.role_type) }}</span>
        <div class="mt-2 text-xs text-slate-500">{{ c.gender === 'male' ? '男' : '女' }}</div>
        <div v-if="c.avatar_front_url" class="mt-2 text-xs text-emerald-400">参考图已就绪</div>
        <div v-else class="mt-2 text-xs text-yellow-400">待生成参考图</div>
      </div>
    </div>

    <div v-if="showCreate" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50" @click.self="showCreate = false">
      <div class="rounded-xl p-6 w-full max-w-md shadow-2xl border border-gray-700/50" style="background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(20px);">
        <h2 class="text-lg font-semibold text-slate-100 mb-4">新建角色</h2>
        <div class="space-y-3">
          <div>
            <input v-model="form.name" placeholder="角色名称" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
            <p class="text-xs text-slate-500 mt-1 ml-1">角色的显示名称</p>
          </div>
          <div class="flex gap-3">
            <div class="flex-1">
              <select v-model="form.role_type" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 cursor-pointer">
                <option v-for="r in roleOptions" :key="r.value" :value="r.value">{{ r.label }}</option>
              </select>
              <p class="text-xs text-slate-500 mt-1 ml-1">可在"系统字典"中管理角色类型</p>
            </div>
            <div>
              <select v-model="form.gender" class="rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 cursor-pointer">
                <option value="male">男</option><option value="female">女</option>
              </select>
              <p class="text-xs text-slate-500 mt-1 ml-1">性别</p>
            </div>
          </div>
          <div>
            <textarea v-model="form.appearance_desc" placeholder="外观描述 — 用于 FLUX 生成角色参考图" rows="2" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
            <p class="text-xs text-slate-500 mt-1 ml-1">描述越详细，FLUX 生成的参考图越准确</p>
          </div>
          <div>
            <textarea v-model="form.outfit_desc" placeholder="服装描述" rows="2" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
          </div>
          <div>
            <textarea v-model="form.personality" placeholder="性格描述 — 影响剧本中角色的对话和行为" rows="2" class="w-full rounded-lg px-3 py-2 bg-gray-800 border border-gray-600 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500/50 transition" />
            <p class="text-xs text-slate-500 mt-1 ml-1">性格描述会被注入 LLM prompt，影响 AI 剧本生成</p>
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
import { listCharacters, createCharacter } from '../api/characters.js'
import { listItems } from '../api/referenceData.js'

const characters = ref([]); const loading = ref(true); const showCreate = ref(false); const error = ref('')
const roleOptions = ref([])
const form = reactive({ name: '', role_type: 'protagonist', gender: 'male', appearance_desc: '', outfit_desc: '', personality: '' })

async function loadRoles() { try { const { data } = await listItems('character_role'); if (data.ok) { roleOptions.value = data.items; if (data.items.length) form.role_type = data.items[0].value } } catch (e) {} }
async function load() { loading.value = true; error.value = ''; try { const { data } = await listCharacters(); characters.value = data.ok ? data.characters : [] } catch (e) { error.value = e.message || '加载失败' } finally { loading.value = false } }
async function doCreate() { try { await createCharacter({ ...form }); showCreate.value = false; await load() } catch (e) { error.value = e.message || '创建失败' } }
function roleClass(r) { return { protagonist: 'bg-sky-900/40 text-sky-400', antagonist: 'bg-red-900/40 text-red-400', supporting: 'bg-emerald-900/40 text-emerald-400', cameo: 'bg-gray-800 text-slate-400' }[r] || 'bg-gray-800 text-slate-400' }
function roleLabel(v) { const r = roleOptions.value.find(x => x.value === v); return r ? r.label : v }
onMounted(async () => { await loadRoles(); await load() })
</script>
