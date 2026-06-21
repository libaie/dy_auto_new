<!-- 运营业务组件：展示账号、频道、关键词或任务创建相关业务交互。 -->
<script setup>
import { ref } from 'vue'
import ChannelCard from './ChannelCard.vue'
import ConfirmDialog from '../ConfirmDialog.vue'
import { updateChannel, deleteChannel as deleteChannelApi } from '../../api/channels.js'

const props = defineProps({
  channels: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['refresh', 'detail'])

const confirmOpen = ref(false)
const confirmTitle = ref('')
const confirmMessage = ref('')
const confirmAction = ref(null)
const confirmDanger = ref(false)

function openConfirm(title, message, action, danger) {
  confirmTitle.value = title
  confirmMessage.value = message
  confirmAction.value = action
  confirmDanger.value = danger
  confirmOpen.value = true
}

async function handleConfirm() {
  if (confirmAction.value) await confirmAction.value()
  confirmOpen.value = false
  emit('refresh')
}

async function pauseChannel(ch) {
  openConfirm('暂停通道', '确定暂停此通道？',
    () => updateChannel(ch.id, { status: 'paused' }), false)
}

async function resumeChannel(ch) {
  await updateChannel(ch.id, { status: 'active' })
  emit('refresh')
}

async function cancelChannel(ch) {
  openConfirm('取消通道', '确定取消此通道？已分发的任务将继续执行，未分发的关键词将被跳过。',
    () => updateChannel(ch.id, { status: 'cancelled' }), false)
}

async function deleteChannel(ch) {
  openConfirm('删除通道', `确定要删除此通道吗？此操作不可撤销。`,
    () => deleteChannelApi(ch.id), true)
}
</script>

<template>
  <div v-if="loading" class="text-center py-12 text-slate-400">加载中...</div>
  <div v-else-if="channels.length === 0" class="text-center py-12 text-slate-400">暂无通道，点击上方按钮创建</div>
  <div v-else class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
    <ChannelCard
      v-for="ch in channels"
      :key="ch.id"
      :channel="ch"
      @click="emit('detail', ch)"
      @pause="pauseChannel"
      @resume="resumeChannel"
      @cancel="cancelChannel"
      @delete="deleteChannel"
    />
  </div>

  <ConfirmDialog
    :open="confirmOpen"
    :title="confirmTitle"
    :message="confirmMessage"
    :danger="confirmDanger"
    @confirm="handleConfirm"
    @cancel="confirmOpen = false"
  />
</template>
