<script setup>
import { ref, reactive, onMounted } from 'vue'
import {
  Dialog,
  DialogPanel,
  DialogTitle,
  TransitionRoot,
  TransitionChild,
} from '@headlessui/vue'
import DataTable from '../components/DataTable.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import TipIcon from '../components/TipIcon.vue'
import {
  listGroups,
  createGroup,
  updateGroup,
  deleteGroup,
  listMembers,
  addMembers,
  removeMembers,
} from '../api/accountGroups.js'
import { listAccounts } from '../api/accounts.js'
import { formatDate } from '../utils/format.js'
import { useToastStore } from '../stores/toast.js'
import { useWebSocket } from '../composables/useWebSocket.js'

// --- Data state ---
const groups = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)

// --- Form / Dialog state ---
const showFormDialog = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const formError = ref(null)

const defaultForm = {
  name: '',
  description: '',
}
const form = reactive({ ...defaultForm })
const editingId = ref(null)

// --- Delete confirmation state ---
const showDeleteDialog = ref(false)
const deletingGroup = ref(false)
const deleting = ref(false)

// --- Member management state ---
const showMembersDialog = ref(false)
const managingGroupId = ref(null)
const managingGroupName = ref('')
const members = ref([])
const membersLoading = ref(false)
const allAccounts = ref([])
const selectedAccountIds = ref([])

// --- Page-level error ---
const pageError = ref(null)
const toast = useToastStore()

// --- WebSocket ---
function wsUrl() {
  const token = localStorage.getItem('token') || ''
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/api/devices/ws/pair-events?token=${encodeURIComponent(token)}`
}
useWebSocket(wsUrl, {
  onMessage(msg) {
    if (msg.event === 'account_groups_changed') fetchGroups()
  },
})

// --- Table columns ---
const columns = [
  { key: 'name', label: '分组名称' },
  { key: 'description', label: '描述' },
  { key: 'member_count', label: '成员数' },
  { key: 'created_at', label: '创建时间' },
  { key: 'actions', label: '操作', headerClass: 'text-right', cellClass: 'text-right' },
]

// --- Fetch groups ---
async function fetchGroups() {
  loading.value = true
  try {
    const skip = (page.value - 1) * pageSize
    const res = await listGroups({ skip, limit: pageSize })
    groups.value = res.data.groups || []
    total.value = res.data.total || 0
  } catch (e) {
    toast.error('加载分组列表失败')
    groups.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handlePageChange(p) {
  page.value = p
  fetchGroups()
}

// --- Open create dialog ---
function openCreateDialog() {
  isEditing.value = false
  editingId.value = null
  Object.assign(form, defaultForm)
  formError.value = null
  showFormDialog.value = true
}

// --- Open edit dialog ---
function openEditDialog(group) {
  isEditing.value = true
  editingId.value = group.id
  form.name = group.name || ''
  form.description = group.description || ''
  formError.value = null
  showFormDialog.value = true
}

// --- Save (create or update) ---
async function handleSave() {
  if (!form.name.trim()) {
    formError.value = '分组名称不能为空'
    return
  }

  saving.value = true
  formError.value = null

  const payload = {
    name: form.name.trim(),
    description: form.description.trim(),
  }

  try {
    if (isEditing.value) {
      await updateGroup(editingId.value, payload)
    } else {
      await createGroup(payload)
    }
    showFormDialog.value = false
    fetchGroups()
  } catch (e) {
    formError.value =
      e.response?.data?.message ||
      e.response?.data?.detail ||
      '保存失败，请重试'
  } finally {
    saving.value = false
  }
}

// --- Delete ---
function openDeleteDialog(group) {
  deletingGroup.value = group
  showDeleteDialog.value = true
}

async function handleDelete() {
  if (!deletingGroup.value) return
  deleting.value = true
  try {
    await deleteGroup(deletingGroup.value.id)
    showDeleteDialog.value = false
    deletingGroup.value = null
    if (groups.value.length === 1 && page.value > 1) {
      page.value--
    }
    fetchGroups()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '删除失败，请重试'
  } finally {
    deleting.value = false
  }
}

// --- Member management ---
async function openMembersDialog(group) {
  managingGroupId.value = group.id
  managingGroupName.value = group.name
  showMembersDialog.value = true
  selectedAccountIds.value = []
  await Promise.all([fetchMembers(group.id), fetchAllAccounts()])
}

async function fetchMembers(groupId) {
  membersLoading.value = true
  try {
    const res = await listMembers(groupId)
    members.value = res.data.members || []
  } catch (e) {
    toast.error('加载成员列表失败')
    members.value = []
  } finally {
    membersLoading.value = false
  }
}

async function fetchAllAccounts() {
  try {
    const res = await listAccounts({ limit: 200 })
    allAccounts.value = res.data.accounts || []
  } catch (e) {
    toast.error('加载账号列表失败')
    allAccounts.value = []
  }
}

// Available accounts = all active accounts not already in the group
const availableAccounts = ref([])

function updateAvailableAccounts() {
  const memberIds = new Set(members.value.map(m => m.id))
  availableAccounts.value = allAccounts.value.filter(
    a => a.status === 'active' && !memberIds.has(a.id)
  )
}

async function handleAddMembers() {
  if (selectedAccountIds.value.length === 0) return
  try {
    await addMembers(managingGroupId.value, selectedAccountIds.value)
    selectedAccountIds.value = []
    await fetchMembers(managingGroupId.value)
    fetchGroups() // refresh member count
  } catch (e) {
    pageError.value = e.response?.data?.detail || '添加成员失败'
  }
}

async function handleRemoveMember(accountId) {
  try {
    await removeMembers(managingGroupId.value, [accountId])
    await fetchMembers(managingGroupId.value)
    fetchGroups() // refresh member count
  } catch (e) {
    pageError.value = e.response?.data?.detail || '移除成员失败'
  }
}

// Watch members change to update available accounts
import { watch } from 'vue'
watch(members, updateAvailableAccounts, { immediate: true })

// --- Init ---
onMounted(fetchGroups)
</script>

<template>
  <div>
    <!-- Page error banner -->
    <div v-if="pageError" class="mb-4 glass-card border-red-500/30 text-red-400 rounded-xl px-4 py-3 flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-400 hover:text-red-300 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white flex items-center gap-1.5">账号分组<TipIcon text="将账号分组管理，方便批量创建链实例和统计" /></h1>
      <button
        class="btn-aurora inline-flex items-center px-4 py-2 text-sm font-medium rounded-xl"
        @click="openCreateDialog"
      >
        <span class="relative z-10 inline-flex items-center">
          <svg class="-ml-1 mr-2 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" />
          </svg>
          创建分组
        </span>
      </button>
    </div>

    <!-- Data Table -->
    <DataTable
      :columns="columns"
      :data="groups"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      @page-change="handlePageChange"
    >
      <template #cell-member_count="{ value }">
        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium badge-info">
          {{ value }} 人
        </span>
      </template>

      <template #cell-created_at="{ value }">
        {{ formatDate(value) }}
      </template>

      <template #cell-actions="{ row }">
        <div class="flex justify-end gap-2">
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-emerald-400 hover:text-emerald-300 hover:bg-emerald-400/10 rounded transition-colors"
            @click="openMembersDialog(row)"
          >
            成员管理
          </button>
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-cyan-400 hover:text-cyan-300 hover:bg-cyan-400/10 rounded transition-colors"
            @click="openEditDialog(row)"
          >
            编辑
          </button>
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-400/10 rounded transition-colors"
            @click="openDeleteDialog(row)"
          >
            删除
          </button>
        </div>
      </template>
    </DataTable>

    <!-- Create / Edit Dialog -->
    <TransitionRoot :show="showFormDialog" as="template">
      <Dialog as="div" class="relative z-50" @close="showFormDialog = false">
        <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-lg glass-card p-6 gradient-border">
                <DialogTitle class="text-lg font-medium text-white">
                  {{ isEditing ? '编辑分组' : '创建分组' }}
                </DialogTitle>
                <div v-if="formError" class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-3 py-2 rounded-lg">
                  {{ formError }}
                </div>
                <form class="mt-4 space-y-4" @submit.prevent="handleSave">
                  <div>
                    <label class="block text-sm font-medium text-slate-300">分组名称 <span class="text-red-400">*</span></label>
                    <input v-model="form.name" type="text" required class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="请输入分组名称" />
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-slate-300">描述</label>
                    <textarea v-model="form.description" rows="3" class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500" placeholder="请输入分组描述"></textarea>
                  </div>
                  <div class="flex justify-end gap-3 pt-2">
                    <button type="button" class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors" @click="showFormDialog = false">取消</button>
                    <button type="submit" :disabled="saving" class="btn-aurora rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed">
                      <span class="relative z-10">{{ saving ? '保存中...' : '保存' }}</span>
                    </button>
                  </div>
                </form>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>

    <!-- Members Management Dialog -->
    <TransitionRoot :show="showMembersDialog" as="template">
      <Dialog as="div" class="relative z-50" @close="showMembersDialog = false">
        <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0" enter-to="opacity-100" leave="ease-in duration-200" leave-from="opacity-100" leave-to="opacity-0">
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-2xl glass-card p-6 gradient-border">
                <DialogTitle class="text-lg font-medium text-white">
                  成员管理 — {{ managingGroupName }}
                </DialogTitle>

                <div class="mt-4 grid grid-cols-2 gap-4">
                  <!-- Left: Available accounts -->
                  <div>
                    <h3 class="text-sm font-medium text-slate-300 mb-2 flex items-center gap-1.5">可选账号<TipIcon text="状态为'正常'且尚未加入此分组的账号，勾选后点击添加选中加入分组" /></h3>
                    <div class="border border-white/10 rounded-lg p-3 h-64 overflow-y-auto">
                      <div v-if="availableAccounts.length === 0" class="text-sm text-slate-500 text-center py-4">
                        暂无可选账号
                      </div>
                      <label
                        v-for="account in availableAccounts"
                        :key="account.id"
                        class="flex items-center gap-2 py-1 px-2 hover:bg-white/5 rounded cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          :value="account.id"
                          v-model="selectedAccountIds"
                          class="rounded border-white/10 text-cyan-400 focus:ring-cyan-500"
                        />
                        <span class="text-sm text-slate-300">{{ account.nickname || account.douyin_id || account.id }}</span>
                      </label>
                    </div>
                    <button
                      v-if="selectedAccountIds.length > 0"
                      class="btn-aurora mt-2 w-full inline-flex items-center justify-center px-3 py-2 text-sm font-medium rounded-lg"
                      @click="handleAddMembers"
                    >
                      <span class="relative z-10">添加选中 ({{ selectedAccountIds.length }})</span>
                    </button>
                  </div>

                  <!-- Right: Current members -->
                  <div>
                    <h3 class="text-sm font-medium text-slate-300 mb-2 flex items-center gap-1.5">当前成员 ({{ members.length }})<TipIcon text="已加入此分组的账号。非活跃状态的账号在创建链实例时会被自动跳过" /></h3>
                    <div class="border border-white/10 rounded-lg p-3 h-64 overflow-y-auto">
                      <div v-if="membersLoading" class="text-sm text-slate-500 text-center py-4">加载中...</div>
                      <div v-else-if="members.length === 0" class="text-sm text-slate-500 text-center py-4">暂无成员</div>
                      <div
                        v-for="member in members"
                        :key="member.id"
                        class="flex items-center justify-between py-1 px-2 hover:bg-white/5 rounded"
                      >
                        <div>
                          <span class="text-sm text-slate-300">{{ member.nickname || member.douyin_id || member.id }}</span>
                          <span v-if="member.status !== 'active'" class="ml-1 text-xs text-red-400">({{ member.status }})</span>
                        </div>
                        <button
                          class="text-xs text-red-400 hover:text-red-300 px-2 py-1 hover:bg-red-400/10 rounded"
                          @click="handleRemoveMember(member.id)"
                        >
                          移除
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                <div class="flex justify-end mt-4">
                  <button
                    class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors"
                    @click="showMembersDialog = false"
                  >
                    关闭
                  </button>
                </div>
              </DialogPanel>
            </TransitionChild>
          </div>
        </div>
      </Dialog>
    </TransitionRoot>

    <!-- Delete Confirmation Dialog -->
    <ConfirmDialog
      :open="showDeleteDialog"
      title="删除分组"
      :message="`确定要删除分组「${deletingGroup?.name || ''}」吗？此操作不可撤销。`"
      confirm-text="删除"
      :danger="true"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>
