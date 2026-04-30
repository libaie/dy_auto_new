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
import StatusBadge from '../components/StatusBadge.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import {
  listAccounts,
  createAccount,
  updateAccount,
  deleteAccount,
} from '../api/accounts.js'
import { formatDate } from '../utils/format.js'

// --- Data state ---
const accounts = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)

// --- Form / Dialog state ---
const showFormDialog = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const formError = ref(null)

const defaultForm = {
  nickname: '',
  douyin_id: '',
  group: '',
  status: 'active',
  daily_limits: '',
}
const form = reactive({ ...defaultForm })
const editingId = ref(null)

// --- Delete confirmation state ---
const showDeleteDialog = ref(false)
const deletingAccount = ref(null)
const deleting = ref(false)

// --- Page-level error ---
const pageError = ref(null)

// --- Status options for the dropdown ---
const statusOptions = [
  { value: 'active', label: '正常' },
  { value: 'risk_controlled', label: '风控中' },
  { value: 'disabled', label: '已禁用' },
]

// --- Table columns ---
const columns = [
  { key: 'nickname', label: '昵称' },
  { key: 'douyin_id', label: '抖音号' },
  { key: 'group', label: '分组' },
  { key: 'status', label: '状态' },
  { key: 'created_at', label: '创建时间' },
  { key: 'actions', label: '操作', headerClass: 'text-right', cellClass: 'text-right' },
]

// --- Fetch accounts ---
async function fetchAccounts() {
  loading.value = true
  try {
    const skip = (page.value - 1) * pageSize
    const res = await listAccounts({ skip, limit: pageSize })
    accounts.value = res.data.accounts || []
    total.value = res.data.total || 0
  } catch (e) {
    console.error('Failed to fetch accounts:', e)
    accounts.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handlePageChange(p) {
  page.value = p
  fetchAccounts()
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
function openEditDialog(account) {
  isEditing.value = true
  editingId.value = account.id
  form.nickname = account.nickname || ''
  form.douyin_id = account.douyin_id || ''
  form.group = account.group || ''
  form.status = account.status || 'active'
  form.daily_limits =
    account.daily_limits != null ? String(account.daily_limits) : ''
  formError.value = null
  showFormDialog.value = true
}

// --- Save (create or update) ---
async function handleSave() {
  if (!form.nickname.trim()) {
    formError.value = '昵称不能为空'
    return
  }

  saving.value = true
  formError.value = null

  const payload = {
    nickname: form.nickname.trim(),
    douyin_id: form.douyin_id.trim() || undefined,
    group: form.group.trim() || undefined,
    status: form.status,
  }

  if (form.daily_limits === '' || form.daily_limits == null) {
    payload.daily_limits = null
  } else {
    const n = Number(form.daily_limits)
    if (!isNaN(n)) payload.daily_limits = n
  }

  try {
    if (isEditing.value) {
      await updateAccount(editingId.value, payload)
    } else {
      await createAccount(payload)
    }
    showFormDialog.value = false
    fetchAccounts()
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
function openDeleteDialog(account) {
  deletingAccount.value = account
  showDeleteDialog.value = true
}

async function handleDelete() {
  if (!deletingAccount.value) return
  deleting.value = true
  try {
    await deleteAccount(deletingAccount.value.id)
    showDeleteDialog.value = false
    deletingAccount.value = null
    // If we deleted the last item on the current page, go back one page
    if (accounts.value.length === 1 && page.value > 1) {
      page.value--
    }
    fetchAccounts()
  } catch (e) {
    pageError.value = e.response?.data?.detail || '删除失败，请重试'
  } finally {
    deleting.value = false
  }
}

// --- Init ---
onMounted(fetchAccounts)
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
      <h1 class="text-2xl font-bold text-gray-800">账号管理</h1>
      <button
        class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-md hover:bg-indigo-700 transition-colors"
        @click="openCreateDialog"
      >
        <svg
          class="-ml-1 mr-2 h-5 w-5"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"
          />
        </svg>
        添加账号
      </button>
    </div>

    <!-- Data Table -->
    <DataTable
      :columns="columns"
      :data="accounts"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      @page-change="handlePageChange"
    >
      <!-- Status column -->
      <template #cell-status="{ value }">
        <StatusBadge :status="value" />
      </template>

      <!-- Created at column -->
      <template #cell-created_at="{ value }">
        {{ formatDate(value) }}
      </template>

      <!-- Actions column -->
      <template #cell-actions="{ row }">
        <div class="flex justify-end gap-2">
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
      <Dialog
        as="div"
        class="relative z-50"
        @close="showFormDialog = false"
      >
        <TransitionChild
          as="template"
          enter="ease-out duration-300"
          enter-from="opacity-0"
          enter-to="opacity-100"
          leave="ease-in duration-200"
          leave-from="opacity-100"
          leave-to="opacity-0"
        >
          <div class="fixed inset-0 bg-black/30" />
        </TransitionChild>

        <div class="fixed inset-0 overflow-y-auto">
          <div class="flex min-h-full items-center justify-center p-4">
            <TransitionChild
              as="template"
              enter="ease-out duration-300"
              enter-from="opacity-0 scale-95"
              enter-to="opacity-100 scale-100"
              leave="ease-in duration-200"
              leave-from="opacity-100 scale-100"
              leave-to="opacity-0 scale-95"
            >
              <DialogPanel
                class="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl"
              >
                <DialogTitle class="text-lg font-medium text-gray-900">
                  {{ isEditing ? '编辑账号' : '添加账号' }}
                </DialogTitle>

                <!-- Error message -->
                <div
                  v-if="formError"
                  class="mt-3 bg-red-50 border border-red-200 text-red-700 text-sm px-3 py-2 rounded"
                >
                  {{ formError }}
                </div>

                <form class="mt-4 space-y-4" @submit.prevent="handleSave">
                  <!-- Nickname -->
                  <div>
                    <label
                      for="nickname"
                      class="block text-sm font-medium text-gray-700"
                    >
                      昵称 <span class="text-red-500">*</span>
                    </label>
                    <input
                      id="nickname"
                      v-model="form.nickname"
                      type="text"
                      required
                      class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      placeholder="请输入昵称"
                    />
                  </div>

                  <!-- Douyin ID -->
                  <div>
                    <label
                      for="douyin_id"
                      class="block text-sm font-medium text-gray-700"
                    >
                      抖音号
                    </label>
                    <input
                      id="douyin_id"
                      v-model="form.douyin_id"
                      type="text"
                      class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      placeholder="请输入抖音号"
                    />
                  </div>

                  <!-- Group -->
                  <div>
                    <label
                      for="group"
                      class="block text-sm font-medium text-gray-700"
                    >
                      分组
                    </label>
                    <input
                      id="group"
                      v-model="form.group"
                      type="text"
                      class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      placeholder="请输入分组"
                    />
                  </div>

                  <!-- Status -->
                  <div>
                    <label
                      for="status"
                      class="block text-sm font-medium text-gray-700"
                    >
                      状态
                    </label>
                    <select
                      id="status"
                      v-model="form.status"
                      class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    >
                      <option
                        v-for="opt in statusOptions"
                        :key="opt.value"
                        :value="opt.value"
                      >
                        {{ opt.label }}
                      </option>
                    </select>
                  </div>

                  <!-- Daily Limits -->
                  <div>
                    <label
                      for="daily_limits"
                      class="block text-sm font-medium text-gray-700"
                    >
                      每日限额
                    </label>
                    <input
                      id="daily_limits"
                      v-model="form.daily_limits"
                      type="number"
                      min="0"
                      class="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      placeholder="请输入每日限额"
                    />
                  </div>

                  <!-- Buttons -->
                  <div class="flex justify-end gap-3 pt-2">
                    <button
                      type="button"
                      class="rounded-md bg-white px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                      @click="showFormDialog = false"
                    >
                      取消
                    </button>
                    <button
                      type="submit"
                      :disabled="saving"
                      class="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
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

    <!-- Delete Confirmation Dialog -->
    <ConfirmDialog
      :open="showDeleteDialog"
      title="删除账号"
      :message="`确定要删除账号「${deletingAccount?.nickname || ''}」吗？此操作不可撤销。`"
      confirm-text="删除"
      :danger="true"
      @confirm="handleDelete"
      @cancel="showDeleteDialog = false"
    />
  </div>
</template>
