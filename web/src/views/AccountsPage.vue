<!-- 管理端业务页面：承载 AccountsPage 页面流程，协调接口数据、用户操作和业务状态展示。 -->
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
import { useWebSocket } from '../composables/useWebSocket.js'

const DAILY_LIMIT_FIELDS = [
  { key: 'likes', label: '点赞', max: 200 },
  { key: 'comments', label: '评论', max: 100 },
  { key: 'follows', label: '关注', max: 100 },
  { key: 'dms', label: '私信', max: 100 },
  { key: 'replies', label: '回复', max: 500 },
]

const DEFAULT_LIMITS = { likes: 50, comments: 20, follows: 20, dms: 10, replies: 15 }

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
  unlimited: false,
  limits: { ...DEFAULT_LIMITS },
}
const form = reactive({ ...defaultForm })
const editingId = ref(null)

// --- Delete confirmation state ---
const showDeleteDialog = ref(false)
const deletingAccount = ref(null)
const deleting = ref(false)

// --- Page-level error ---
const pageError = ref(null)

const toast = useToastStore()

// --- WebSocket ---
// 前端业务函数：协调 wsUrl 对应的页面流程、接口调用或状态转换。
function wsUrl() {
  const token = localStorage.getItem('token') || ''
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/api/devices/ws/pair-events?token=${encodeURIComponent(token)}`
}
useWebSocket(wsUrl, {
  onMessage(msg) {
    if (msg.event === 'accounts_changed') fetchAccounts()
  },
})

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

// 前端业务函数：协调 handlePageChange 对应的页面流程、接口调用或状态转换。
function handlePageChange(p) {
  page.value = p
  fetchAccounts()
}

// --- Open create dialog ---
// 前端业务函数：协调 openCreateDialog 对应的页面流程、接口调用或状态转换。
function openCreateDialog() {
  isEditing.value = false
  editingId.value = null
  Object.assign(form, defaultForm)
  form.limits = { ...DEFAULT_LIMITS }
  form.unlimited = false
  formError.value = null
  showFormDialog.value = true
}

// --- Open edit dialog ---
// 前端业务函数：协调 openEditDialog 对应的页面流程、接口调用或状态转换。
function openEditDialog(account) {
  isEditing.value = true
  editingId.value = account.id
  form.nickname = account.nickname || ''
  form.douyin_id = account.douyin_id || ''
  form.group = account.group || ''
  form.status = account.status || 'active'
  const dl = account.daily_limits
  if (dl && typeof dl === 'object' && Object.keys(dl).length > 0) {
    form.unlimited = false
    form.limits = {
      likes: dl.likes ?? DEFAULT_LIMITS.likes,
      comments: dl.comments ?? DEFAULT_LIMITS.comments,
      follows: dl.follows ?? DEFAULT_LIMITS.follows,
      dms: dl.dms ?? DEFAULT_LIMITS.dms,
      replies: dl.replies ?? DEFAULT_LIMITS.replies,
    }
  } else {
    form.unlimited = true
    form.limits = { ...DEFAULT_LIMITS }
  }
  formError.value = null
  showFormDialog.value = true
}

// --- Save (create or update) ---
// 前端业务函数：协调 handleSave 对应的页面流程、接口调用或状态转换。
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
    daily_limits: form.unlimited ? {} : { ...form.limits },
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
// 前端业务函数：协调 openDeleteDialog 对应的页面流程、接口调用或状态转换。
function openDeleteDialog(account) {
  deletingAccount.value = account
  showDeleteDialog.value = true
}

// 前端业务函数：协调 handleDelete 对应的页面流程、接口调用或状态转换。
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
                    <div class="flex items-center justify-between mb-4">
                      <label class="flex items-center gap-1.5 text-sm font-semibold text-slate-200">
                        <svg class="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        每日限额
                        <TipIcon :text="'每种操作类型每日执行上限，超出后自动跳过该操作\n\n点赞 (search_like)\n  搜索结果页对视频点赞\n\n评论 (search_comment)\n  搜索结果页对视频发表评论\n\n关注 (follow)\n  评论回复流程中关注评论者\n\n私信 (search_dm)\n  搜索视频作者或评论者发送私信，一个用户计 1 次\n\n回复 (reply_comment)\n  对视频评论区留言进行 AI 回复'" width="w-72" />
                      </label>
                      <label class="flex items-center gap-2 text-xs text-slate-400 cursor-pointer select-none hover:text-slate-300 transition-colors">
                        <input type="checkbox" v-model="form.unlimited" class="accent-indigo-600 rounded" />
                        不限制
                      </label>
                    </div>
                    <div v-if="!form.unlimited" class="space-y-2">
                      <div v-for="f in DAILY_LIMIT_FIELDS" :key="f.key"
                           class="flex items-center gap-3 rounded-lg px-3 py-2"
                           :style="{ background: 'rgba(255,255,255,0.02)' }">
                        <span class="w-10 text-xs font-medium shrink-0"
                          :class="[
                            f.key === 'likes' ? 'text-pink-400' :
                            f.key === 'comments' ? 'text-emerald-400' :
                            f.key === 'follows' ? 'text-amber-400' :
                            f.key === 'dms' ? 'text-sky-400' :
                            'text-violet-400'
                          ]">{{ f.label }}</span>
                        <input
                          :id="'limit-' + f.key"
                          v-model.number="form.limits[f.key]"
                          type="number"
                          min="-1"
                          :max="f.max"
                          title="-1 表示不限制"
                          class="w-16 rounded-lg border border-white/10 bg-white/[0.06] px-2 py-1.5 text-sm font-semibold text-white text-center focus:outline-none focus:ring-2 focus:ring-indigo-500/30 focus:border-transparent transition-shadow shrink-0"
                        />
                        <div class="flex-1 h-1.5 rounded-full bg-white/5 overflow-hidden">
                          <div class="h-full rounded-full transition-all duration-300"
                            :style="{ width: Math.min(100, Math.max(0, (form.limits[f.key] || 0)) / f.max * 100) + '%' }"
                            :class="[
                              f.key === 'likes' ? 'bg-gradient-to-r from-pink-500 to-pink-300' :
                              f.key === 'comments' ? 'bg-gradient-to-r from-emerald-500 to-emerald-300' :
                              f.key === 'follows' ? 'bg-gradient-to-r from-amber-500 to-amber-300' :
                              f.key === 'dms' ? 'bg-gradient-to-r from-sky-500 to-sky-300' :
                              'bg-gradient-to-r from-violet-500 to-violet-300'
                            ]"></div>
                        </div>
                        <span class="text-[11px] text-slate-500 w-9 text-right shrink-0">/{{ f.max }}</span>
                      </div>
                    </div>
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
