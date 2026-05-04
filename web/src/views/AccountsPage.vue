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
import { useToastStore } from '../stores/toast.js'
import TipIcon from '../components/TipIcon.vue'

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
const dailyLimitsError = ref(null)
const form = reactive({ ...defaultForm })
const editingId = ref(null)

// --- Delete confirmation state ---
const showDeleteDialog = ref(false)
const deletingAccount = ref(null)
const deleting = ref(false)

// --- Page-level error ---
const pageError = ref(null)

const toast = useToastStore()

// --- Status options for the dropdown ---
const statusOptions = [
  { value: 'active', label: '正常' },
  { value: 'risk_controlled', label: '风控中' },
  { value: 'banned', label: '已禁用' },
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
    toast.error('加载账号列表失败')
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
  dailyLimitsError.value = null
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
    account.daily_limits != null ? JSON.stringify(account.daily_limits) : ''
  formError.value = null
  dailyLimitsError.value = null
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
    try {
      const parsed = JSON.parse(form.daily_limits)
      if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
        payload.daily_limits = parsed
        dailyLimitsError.value = null
      } else {
        dailyLimitsError.value = '每日限额需为 JSON 对象格式，如 {"like": 50, "comment": 20}'
        saving.value = false
        return
      }
    } catch {
      dailyLimitsError.value = 'JSON 格式不正确，请检查'
      saving.value = false
      return
    }
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
    <div v-if="pageError" class="mb-4 glass-card border-red-500/30 text-red-400 px-4 py-3 rounded-xl flex items-center justify-between">
      <span>{{ pageError }}</span>
      <button class="text-red-400 hover:text-red-300 font-bold" @click="pageError = null">&times;</button>
    </div>

    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white inline-flex items-center gap-1.5">账号管理 <TipIcon text="管理抖音账号，配置状态、分组和每日操作限额" /></h1>
      <button
        class="btn-aurora inline-flex items-center px-4 py-2 text-sm font-medium rounded-xl"
        @click="openCreateDialog"
      >
        <svg
          class="-ml-1 mr-2 h-5 w-5 relative z-10"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"
          />
        </svg>
        <span class="relative z-10">添加账号</span>
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
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-cyan-400 hover:text-cyan-300 hover:bg-cyan-400/10 rounded-lg transition-colors"
            @click="openEditDialog(row)"
          >
            编辑
          </button>
          <button
            class="inline-flex items-center px-3 py-1 text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-400/10 rounded-lg transition-colors"
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
          <div class="fixed inset-0 bg-black/50 backdrop-blur-sm" />
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
                class="glass-card w-full max-w-lg p-6 gradient-border"
              >
                <DialogTitle class="text-lg font-medium text-white">
                  {{ isEditing ? '编辑账号' : '添加账号' }}
                </DialogTitle>

                <!-- Error message -->
                <div
                  v-if="formError"
                  class="mt-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-3 py-2 rounded-lg"
                >
                  {{ formError }}
                </div>
                <div
                  v-if="dailyLimitsError"
                  class="mt-3 bg-amber-500/10 border border-amber-500/20 text-amber-400 text-sm px-3 py-2 rounded-lg"
                >
                  {{ dailyLimitsError }}
                </div>

                <form class="mt-4 space-y-4" @submit.prevent="handleSave">
                  <!-- Nickname -->
                  <div>
                    <label
                      for="nickname"
                      class="block text-sm font-medium text-slate-300"
                    >
                      昵称 <span class="text-red-400">*</span>
                    </label>
                    <input
                      id="nickname"
                      v-model="form.nickname"
                      type="text"
                      required
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                      placeholder="请输入昵称"
                    />
                  </div>

                  <!-- Douyin ID -->
                  <div>
                    <label
                      for="douyin_id"
                      class="block text-sm font-medium text-slate-300"
                    >
                      抖音号
                    </label>
                    <input
                      id="douyin_id"
                      v-model="form.douyin_id"
                      type="text"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                      placeholder="请输入抖音号"
                    />
                  </div>

                  <!-- Group -->
                  <div>
                    <label
                      for="group"
                      class="flex items-center gap-1.5 text-sm font-medium text-slate-300"
                    >
                      分组
                      <TipIcon text="为账号分配分组标签，方便批量管理和创建链实例" />
                    </label>
                    <input
                      id="group"
                      v-model="form.group"
                      type="text"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500"
                      placeholder="请输入分组"
                    />
                  </div>

                  <!-- Status -->
                  <div>
                    <label
                      for="status"
                      class="flex items-center gap-1.5 text-sm font-medium text-slate-300"
                    >
                      状态
                      <TipIcon text="正常=可执行任务；风控中=触发抖音风控，暂停任务；已禁用=手动禁用，不分配任务" width="w-80" />
                    </label>
                    <select
                      id="status"
                      v-model="form.status"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200"
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
                      class="flex items-center gap-1.5 text-sm font-medium text-slate-300"
                    >
                      每日限额
                      <TipIcon text="按操作类型设置每日上限，JSON 格式。如 {&quot;like&quot;: 50, &quot;comment&quot;: 20}，留空不限制" width="w-96" />
                    </label>
                    <textarea
                      id="daily_limits"
                      v-model="form.daily_limits"
                      rows="3"
                      class="mt-1 block w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 font-mono"
                      placeholder='{"like": 50, "comment": 20}'
                    ></textarea>
                  </div>

                  <!-- Buttons -->
                  <div class="flex justify-end gap-3 pt-2">
                    <button
                      type="button"
                      class="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 transition-colors"
                      @click="showFormDialog = false"
                    >
                      取消
                    </button>
                    <button
                      type="submit"
                      :disabled="saving"
                      class="btn-aurora rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                    >
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
