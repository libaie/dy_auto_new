<!-- 管理端通用组件：提供业务页面复用的展示、反馈或交互能力。 -->
<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="bg-slate-800 rounded-xl shadow-xl w-full max-w-3xl mx-4 p-6 max-h-[85vh] overflow-y-auto border border-slate-700">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-bold text-white">通道详情</h2>
        <button @click="$emit('close')" class="text-slate-400 hover:text-white text-2xl leading-none">&times;</button>
      </div>

      <!-- Channel Info Card -->
      <div class="bg-slate-700/30 rounded-lg p-4 mb-4 border border-slate-600/30">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-semibold text-slate-300">通道配置</h3>
          <button
            v-if="!editingChannel && canEditChannel"
            @click="startEditChannel"
            class="text-xs px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded transition-colors"
          >编辑</button>
        </div>

        <!-- Display mode -->
        <div v-if="!editingChannel" class="grid grid-cols-2 gap-2 text-sm">
          <div><span class="text-slate-500">分组：</span><span class="text-white">{{ detail.group_name || '-' }}</span></div>
          <div><span class="text-slate-500">模式：</span><span class="text-white">{{ detail.account_mode === 'single_account' ? '单账号' : '轮询' }}</span></div>
          <div><span class="text-slate-500">冷却：</span><span class="text-white">{{ detail.cooldown_seconds }}s</span></div>
          <div><span class="text-slate-500">任务类型：</span><span class="text-white">{{ detail.task_type }}</span></div>
          <div class="col-span-2"><span class="text-slate-500">参数模板：</span><span class="text-slate-400 text-xs">{{ JSON.stringify(detail.params_template) }}</span></div>
        </div>

        <!-- Edit mode -->
        <div v-else class="space-y-3">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="text-xs text-slate-400 block mb-1">分组</label>
              <select v-model="channelForm.group_id" class="w-full bg-slate-800 border border-slate-600 rounded px-3 py-2 text-white text-sm">
                <option value="">不变更</option>
                <option v-for="g in groups" :key="g.id" :value="g.id">{{ g.name }}</option>
              </select>
            </div>
            <div>
              <label class="text-xs text-slate-400 block mb-1">账号模式</label>
              <select v-model="channelForm.account_mode" class="w-full bg-slate-800 border border-slate-600 rounded px-3 py-2 text-white text-sm">
                <option value="">不变更</option>
                <option value="round_robin">轮询</option>
                <option value="single_account">单账号</option>
              </select>
            </div>
            <div>
              <label class="text-xs text-slate-400 block mb-1">账号</label>
              <select v-model="channelForm.account_id" class="w-full bg-slate-800 border border-slate-600 rounded px-3 py-2 text-white text-sm">
                <option value="">不变更</option>
                <option v-for="a in editableAccounts" :key="a.id" :value="a.id">{{ a.nickname || a.id }}</option>
              </select>
            </div>
            <div>
              <label class="text-xs text-slate-400 block mb-1">冷却时间(s)</label>
              <input v-model.number="channelForm.cooldown_seconds" type="number" min="30" max="3600" class="w-full bg-slate-800 border border-slate-600 rounded px-3 py-2 text-white text-sm" />
            </div>
          </div>
          <label class="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
            <input type="checkbox" v-model="channelForm.sync_to_items" class="accent-indigo-600" />
            同步应用到所有待处理和执行中的子项
          </label>
          <div class="flex gap-2">
            <button @click="saveChannel" :disabled="savingChannel" class="text-xs px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded transition-colors disabled:opacity-50">保存</button>
            <button @click="editingChannel = false" class="text-xs px-4 py-1.5 bg-slate-600 hover:bg-slate-500 text-white rounded transition-colors">取消</button>
          </div>
        </div>
      </div>

      <!-- Stats -->
      <div class="grid grid-cols-6 gap-2 mb-4">
        <div class="text-center p-2 bg-slate-700/50 rounded">
          <div class="text-lg font-bold text-white">{{ detail.total }}</div>
          <div class="text-xs text-slate-400">总计</div>
        </div>
        <div class="text-center p-2 bg-yellow-500/10 rounded">
          <div class="text-lg font-bold text-yellow-400">{{ detail.pending }}</div>
          <div class="text-xs text-slate-400">待处理</div>
        </div>
        <div class="text-center p-2 bg-blue-500/10 rounded">
          <div class="text-lg font-bold text-blue-400">{{ detail.assigned }}</div>
          <div class="text-xs text-slate-400">执行中</div>
        </div>
        <div class="text-center p-2 bg-green-500/10 rounded">
          <div class="text-lg font-bold text-green-400">{{ detail.completed }}</div>
          <div class="text-xs text-slate-400">完成</div>
        </div>
        <div class="text-center p-2 bg-red-500/10 rounded">
          <div class="text-lg font-bold text-red-400">{{ detail.failed }}</div>
          <div class="text-xs text-slate-400">失败</div>
        </div>
        <div class="text-center p-2 bg-slate-500/10 rounded">
          <div class="text-lg font-bold text-slate-400">{{ detail.skipped }}</div>
          <div class="text-xs text-slate-400">跳过</div>
        </div>
      </div>

      <!-- Items table -->
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-slate-700">
              <th class="text-left py-2 px-1 w-8">
                <input
                  type="checkbox"
                  :disabled="editableItems.length === 0"
                  :checked="allSelected"
                  @change="toggleSelectAll"
                  class="accent-indigo-600"
                />
              </th>
              <th class="text-left py-2 px-2 text-slate-400 font-medium">关键词</th>
              <th class="text-left py-2 px-2 text-slate-400 font-medium">账号</th>
              <th class="text-left py-2 px-2 text-slate-400 font-medium">状态</th>
              <th class="text-left py-2 px-2 text-slate-400 font-medium">设备</th>
              <th class="text-left py-2 px-2 text-slate-400 font-medium w-12"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in detail.items" :key="item.id" class="border-b border-slate-700/50 hover:bg-slate-700/30">
              <td class="py-2 px-1">
                <input
                  type="checkbox"
                  :disabled="!isItemEditable(item)"
                  :checked="selectedIds.has(item.id)"
                  @change="toggleItem(item.id)"
                  class="accent-indigo-600 disabled:opacity-30"
                />
              </td>
              <td class="py-2 px-2 text-white">{{ item.keyword }}</td>
              <td class="py-2 px-2 text-slate-300">{{ item.account_nickname || item.account_id }}</td>
              <td class="py-2 px-2">
                <span :class="itemStatusClass(item.status)" class="px-2 py-0.5 text-xs rounded-full">
                  {{ itemStatusLabel(item.status) }}
                </span>
              </td>
              <td class="py-2 px-2 text-slate-500">{{ item.device_name || '-' }}</td>
              <td class="py-2 px-1">
                <button
                  v-if="isItemEditable(item)"
                  @click="openItemEdit(item)"
                  class="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
                >编辑</button>
              </td>
            </tr>
            <tr v-if="!detail.items || detail.items.length === 0">
              <td colspan="6" class="py-4 text-center text-slate-500">暂无子项</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Batch toolbar -->
      <div v-if="selectedIds.size > 0" class="mt-4 p-3 bg-indigo-600/10 border border-indigo-500/30 rounded-lg flex items-center justify-between">
        <span class="text-sm text-indigo-300">已选 {{ selectedIds.size }} 项</span>
        <button @click="openBatchEdit" class="text-sm px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded transition-colors">批量编辑</button>
      </div>

      <!-- Item Edit Dialog -->
      <div v-if="editDialog.open" class="fixed inset-0 bg-black/60 flex items-center justify-center z-[60]" @click.self="editDialog.open = false">
        <div class="bg-slate-800 rounded-xl shadow-xl w-full max-w-md mx-4 p-6 border border-slate-700">
          <h3 class="text-base font-bold text-white mb-4">
            {{ editDialog.isBatch ? `批量编辑 (${selectedIds.size} 项)` : '编辑子项' }}
          </h3>
          <div class="space-y-3">
            <div v-if="!editDialog.isBatch">
              <label class="text-xs text-slate-400 block mb-1">关键词</label>
              <input v-model="editDialog.keyword" class="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white text-sm" :placeholder="editDialog.currentKeyword || '不变更'" />
            </div>
            <div>
              <label class="text-xs text-slate-400 block mb-1">账号</label>
              <select v-model="editDialog.account_id" class="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white text-sm">
                <option value="">不变更</option>
                <option v-for="a in editableAccounts" :key="a.id" :value="a.id">{{ a.nickname || a.id }}</option>
              </select>
            </div>
            <div>
              <label class="text-xs text-slate-400 block mb-1">设备</label>
              <select v-model="editDialog.assigned_device_id" class="w-full bg-slate-700 border border-slate-600 rounded px-3 py-2 text-white text-sm">
                <option value="">不变更</option>
                <option v-for="d in editableDevices" :key="d.id" :value="d.id">{{ d.name }}</option>
              </select>
            </div>
          </div>
          <div class="flex justify-end gap-2 mt-5">
            <button @click="editDialog.open = false" class="text-sm px-4 py-2 bg-slate-600 hover:bg-slate-500 text-white rounded transition-colors">取消</button>
            <button @click="saveItemEdit" :disabled="savingItem" class="text-sm px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded transition-colors disabled:opacity-50">保存</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { getChannel, editChannelMeta, editChannelItem, batchEditItems } from '../api/channels.js'
import { listAccounts } from '../api/accounts.js'
import { listDevices } from '../api/devices.js'
import { listGroups, listMembers } from '../api/accountGroups.js'

const props = defineProps({ channel: Object })
const emit = defineEmits(['close', 'refresh'])

const detail = ref({ items: [], total: 0, pending: 0, assigned: 0, completed: 0, failed: 0, skipped: 0 })

// Reference data for edit forms
const accounts = ref([])
const devices = ref([])
const groups = ref([])

// Channel edit state
const editingChannel = ref(false)
const savingChannel = ref(false)
const channelForm = ref({})

// Item selection state
const selectedIds = ref(new Set())
const editDialog = ref({ open: false, isBatch: false, itemId: '', currentKeyword: '', keyword: '', account_id: '', assigned_device_id: '' })
const savingItem = ref(false)

const itemStatusLabel = (s) => ({
  pending: '待处理', assigned: '执行中', completed: '已完成', failed: '失败', skipped: '已跳过',
}[s] || s)

const itemStatusClass = (s) => ({
  pending: 'bg-yellow-500/20 text-yellow-400',
  assigned: 'bg-blue-500/20 text-blue-400',
  completed: 'bg-green-500/20 text-green-400',
  failed: 'bg-red-500/20 text-red-400',
  skipped: 'bg-slate-600/50 text-slate-400',
}[s] || 'bg-slate-600/50 text-slate-400')

const canEditChannel = computed(() => {
  return detail.value.status === 'active' || detail.value.status === 'paused'
})

const editableItems = computed(() => {
  return (detail.value.items || []).filter(isItemEditable)
})

const allSelected = computed(() => {
  const items = editableItems.value
  return items.length > 0 && items.every(i => selectedIds.value.has(i.id))
})

const groupMemberIds = ref(new Set())
const membersLoaded = ref(false)

const editableAccounts = computed(() => {
  if (!membersLoaded.value) return accounts.value
  return accounts.value.filter(a => groupMemberIds.value.has(a.id))
})

async function loadMembersForGroup(gid) {
  if (!gid) return
  try {
    const resp = await listMembers(gid)
    const members = resp.data.members || []
    groupMemberIds.value = new Set(members.map(m => m.id))
    membersLoaded.value = true
  } catch (e) {
    console.error('Failed to load members for group:', gid, e)
    // On failure, clear — don't silently show all accounts
    groupMemberIds.value = new Set()
    membersLoaded.value = true
  }
}

// Watch group selector changes → re-fetch members
watch(() => channelForm.value.group_id, async (gid) => {
  if (!gid || !editingChannel.value) return
  await loadMembersForGroup(gid)
})

// Device filtering by bound account
const editableDevices = computed(() => {
  const aid = editDialog.value.account_id
  if (!aid) return devices.value
  return devices.value.filter(d => !d.bound_account_id || d.bound_account_id === aid)
})

function isItemEditable(item) {
  return item.status === 'pending'
}

function toggleItem(id) {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

function toggleSelectAll() {
  if (allSelected.value) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(editableItems.value.map(i => i.id))
  }
}

function startEditChannel() {
  channelForm.value = {
    group_id: '',
    account_mode: '',
    account_id: '',
    cooldown_seconds: detail.value.cooldown_seconds,
    sync_to_items: false,
  }
  editingChannel.value = true
}

async function saveChannel() {
  savingChannel.value = true
  try {
    const payload = {}
    for (const [k, v] of Object.entries(channelForm.value)) {
      if (v !== '' && v !== null && v !== undefined) payload[k] = v
    }
    await editChannelMeta(props.channel.id, payload)
    editingChannel.value = false
    await loadDetail()
    if (detail.value.group_id) await loadMembersForGroup(detail.value.group_id)
    emit('refresh')
  } catch (e) {
    alert('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    savingChannel.value = false
  }
}

function openItemEdit(item) {
  editDialog.value = {
    open: true,
    isBatch: false,
    itemId: item.id,
    currentKeyword: item.keyword,
    keyword: '',
    account_id: '',
    assigned_device_id: '',
  }
}

function openBatchEdit() {
  editDialog.value = {
    open: true,
    isBatch: true,
    itemId: '',
    currentKeyword: '',
    keyword: '',
    account_id: '',
    assigned_device_id: '',
  }
}

async function saveItemEdit() {
  savingItem.value = true
  try {
    if (editDialog.value.isBatch) {
      const payload = { item_ids: [...selectedIds.value] }
      if (editDialog.value.account_id) payload.account_id = editDialog.value.account_id
      if (editDialog.value.assigned_device_id) payload.assigned_device_id = editDialog.value.assigned_device_id
      const resp = await batchEditItems(payload)
      if (resp.data.errors && resp.data.errors.length > 0) {
        alert('部分失败: ' + resp.data.errors.join(', '))
      }
    } else {
      const payload = {}
      if (editDialog.value.keyword) payload.keyword = editDialog.value.keyword
      if (editDialog.value.account_id) payload.account_id = editDialog.value.account_id
      if (editDialog.value.assigned_device_id) payload.assigned_device_id = editDialog.value.assigned_device_id
      await editChannelItem(editDialog.value.itemId, payload)
    }
    editDialog.value.open = false
    selectedIds.value = new Set()
    await loadDetail()
    emit('refresh')
  } catch (e) {
    alert('保存失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    savingItem.value = false
  }
}

async function loadDetail() {
  try {
    const resp = await getChannel(props.channel.id)
    detail.value = resp.data
  } catch (e) {
    console.error('Failed to load channel detail:', e)
  }
}

onMounted(async () => {
  await loadDetail()
  const gid = detail.value.group_id
  try {
    const [accResp, devResp, grpResp] = await Promise.all([
      listAccounts(),
      listDevices(),
      listGroups(),
    ])
    accounts.value = accResp.data.accounts || accResp.data || []
    devices.value = devResp.data.devices || devResp.data || []
    groups.value = grpResp.data.groups || grpResp.data || []
    if (gid) await loadMembersForGroup(gid)
    else membersLoaded.value = true
  } catch (e) {
    console.error('Failed to load ref data:', e)
  }
})
</script>
