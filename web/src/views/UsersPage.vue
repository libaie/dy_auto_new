<script setup>
import { ref, onMounted } from 'vue'
import { listUsers, registerUser } from '../api/auth.js'
import { useToastStore } from '../stores/toast.js'

const toast = useToastStore()
const users = ref([])
const loading = ref(false)
const showCreate = ref(false)
const newUser = ref({ username: '', password: '', role: 'operator', nickname: '' })
const creating = ref(false)

async function fetchUsers() {
  loading.value = true
  try { const resp = await listUsers(); users.value = resp.data.users || [] }
  catch { toast.error('加载用户列表失败') }
  finally { loading.value = false }
}

async function handleCreate() {
  if (!newUser.value.username || !newUser.value.password) { toast.error('用户名和密码必填'); return }
  creating.value = true
  try {
    await registerUser(newUser.value)
    toast.success('用户创建成功')
    showCreate.value = false
    newUser.value = { username: '', password: '', role: 'operator', nickname: '' }
    fetchUsers()
  } catch (e) { toast.error(e.response?.data?.detail || '创建失败') }
  finally { creating.value = false }
}

onMounted(fetchUsers)
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-5">
      <h1 class="text-xl font-bold text-white">用户管理</h1>
      <button @click="showCreate = true" class="btn-primary text-sm">新增用户</button>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-16">
      <svg class="animate-spin h-7 w-7 text-cyan-400/60" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
    </div>

    <div v-else class="card overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr>
            <th class="px-4 py-3 text-left">用户名</th>
            <th class="px-4 py-3 text-left">昵称</th>
            <th class="px-4 py-3 text-left">角色</th>
            <th class="px-4 py-3 text-left">状态</th>
            <th class="px-4 py-3 text-right">创建时间</th>
          </tr>
        </thead>
        <tbody class="divide-y" style="border-color: var(--border-subtle);">
          <tr v-for="u in users" :key="u.id" class="hover:bg-white/5 transition-colors">
            <td class="px-4 py-3 text-slate-200 font-medium">{{ u.username }}</td>
            <td class="px-4 py-3 text-slate-400">{{ u.nickname || '-' }}</td>
            <td class="px-4 py-3">
              <span class="text-xs px-2 py-0.5 rounded font-medium" :class="u.role === 'admin' ? 'bg-amber-500/15 text-amber-400' : 'bg-sky-500/10 text-sky-400'">{{ u.role === 'admin' ? '管理员' : '操作员' }}</span>
            </td>
            <td class="px-4 py-3">
              <span class="text-xs px-2 py-0.5 rounded" :class="u.status === 'active' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-500/10 text-slate-500'">{{ u.status === 'active' ? '启用' : '禁用' }}</span>
            </td>
            <td class="px-4 py-3 text-right text-xs text-slate-500">{{ u.created_at?.slice(0, 10) || '-' }}</td>
          </tr>
          <tr v-if="users.length === 0">
            <td colspan="5" class="px-4 py-12 text-center text-slate-500">暂无用户</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="showCreate" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" @click.self="showCreate = false">
      <div class="card p-5 w-full max-w-sm">
        <h2 class="text-lg font-bold text-white mb-4">新增用户</h2>
        <div class="space-y-3">
          <input v-model="newUser.username" placeholder="用户名" class="w-full rounded-lg border px-3 py-2 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);" />
          <input v-model="newUser.password" type="password" placeholder="密码" class="w-full rounded-lg border px-3 py-2 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);" />
          <input v-model="newUser.nickname" placeholder="昵称（可选）" class="w-full rounded-lg border px-3 py-2 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);" />
          <select v-model="newUser.role" class="w-full rounded-lg border px-3 py-2 text-sm" style="border-color: var(--border-default); background: var(--bg-surface); color: var(--text-primary);">
            <option value="operator">操作员</option>
            <option value="admin">管理员</option>
          </select>
        </div>
        <div class="flex justify-end gap-3 mt-4">
          <button @click="showCreate = false" class="btn-ghost text-sm">取消</button>
          <button @click="handleCreate" :disabled="creating" class="btn-primary text-sm">{{ creating ? '创建中...' : '创建' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>
