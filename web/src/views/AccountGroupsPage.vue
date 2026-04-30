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
    console.error('Failed to fetch groups:', e)
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
    console.error('Failed to fetch members:', e)
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
    console.error('Failed to fetch accounts:', e)
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
    <div v-if="pageError" class="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-500 hover:text-red-700 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">账号分组</h1>
      <button
        class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 transition-colors"
        @click="openCreateDialog"
      >
        <svg class="-ml-1 mr-2 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
          <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" />
        </svg>
        创建分组
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
        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
          {{ value }} 人
        </span>
      </template>

      <template #cell-created_at="{ value }">
        {{ formatDate(value) }}
      </template>

      <template #cell-actions="{ row }">
        <div class="flex justify-end gap-2">
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-green-600 hover:text-green-800 hover:bg-green-50 rounded transition-colors"
            @click="openMembersDialog(row)"
          >
            成员管理
          </button>
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50 rounded transition-colors"
            @click="openEditDialog(row)"
          >
            编辑
          </button>
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-600 hover:text-red-800 hover:bg-red-50 rounded transition-colors"
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
          <div class="fixed inset-0 bg-black/30" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
                <DialogTitle class="text-lg font-medium text-gray-900">
                  {{ isEditing ? '编辑分组' : '创建分组' }}
                </DialogTitle>
                <div v-if="formError" class="mt-3 bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded">
                  {{ formError }}
                </div>
                <form class="mt-4 space-y-4" @submit.prevent="handleSave">
                  <div>
                    <label class="block text-sm font-medium text-gray-700">分组名称 <span class="text-red-500">*</span></label>
                    <input v-model="form.name" type="text" required class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="请输入分组名称" />
                  </div>
                  <div>
                    <label class="block text-sm font-medium text-gray-700">描述</label>
                    <textarea v-model="form.description" rows="3" class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="请输入分组描述"></textarea>
                  </div>
                  <div class="flex justify-end gap-3 pt-2">
                    <button type="button" class="rounded-md bg-white px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50" @click="showFormDialog = false">取消</button>
                    <button type="submit" :disabled="saving" class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed">
                      {{ saving ? '保存中...' : '保存' }}
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
          <div class="fixed inset-0 bg-black/30" />
        </TransitionChild>
        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild as="template" enter="ease-out duration-300" enter-from="opacity-0 scale-95" enter-to="opacity-100 scale-100" leave="ease-in duration-200" leave-from="opacity-100 scale-100" leave-to="opacity-0 scale-95">
              <DialogPanel class="w-full max-w-2xl rounded-xl bg-white p-6 shadow-xl">
                <DialogTitle class="text-lg font-medium text-gray-900">
                  成员管理 — {{ managingGroupName }}
                </DialogTitle>

                <div class="mt-4 grid grid-cols-2 gap-4">
                  <!-- Left: Available accounts -->
                  <div>
                    <h3 class="text-sm font-medium text-gray-700 mb-2">可选账号</h3>
                    <div class="border rounded-lg p-3 h-64 overflow-y-auto">
                      <div v-if="availableAccounts.length === 0" class="text-sm text-gray-400 text-center py-4">
                        暂无可选账号
                      </div>
                      <label
                        v-for="account in availableAccounts"
                        :key="account.id"
                        class="flex items-center gap-2 py-1 px-2 hover:bg-gray-50 rounded cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          :value="account.id"
                          v-model="selectedAccountIds"
                          class="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        <span class="text-sm">{{ account.nickname || account.douyin_id || account.id }}</span>
                      </label>
                    </div>
                    <button
                      v-if="selectedAccountIds.length > 0"
                      class="mt-2 w-full inline-flex items-center justify-center px-3 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700"
                      @click="handleAddMembers"
                    >
                      添加选中 ({{ selectedAccountIds.length }})
                    </button>
                  </div>

                  <!-- Right: Current members -->
                  <div>
                    <h3 class="text-sm font-medium text-gray-700 mb-2">当前成员 ({{ members.length }})</h3>
                    <div class="border rounded-lg p-3 h-64 overflow-y-auto">
                      <div v-if="membersLoading" class="text-sm text-gray-400 text-center py-4">加载中...</div>
                      <div v-else-if="members.length === 0" class="text-sm text-gray-400 text-center py-4">暂无成员</div>
                      <div
                        v-for="member in members"
                        :key="member.id"
                        class="flex items-center justify-between py-1 px-2 hover:bg-gray-50 rounded"
                      >
                        <div>
                          <span class="text-sm">{{ member.nickname || member.douyin_id || member.id }}</span>
                          <span v-if="member.status !== 'active'" class="ml-1 text-xs text-red-500">({{ member.status }})</span>
                        </div>
                        <button
                          class="text-xs text-red-500 hover:text-red-700 px-2 py-1 hover:bg-red-50 rounded"
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
                    class="rounded-md bg-white px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50"
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
