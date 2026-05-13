<script setup>
import { ref, onMounted } from 'vue'
import { listChannels } from '../api/channels.js'
import ChannelList from '../components/business/ChannelList.vue'
import CreateChannelDialog from '../components/CreateChannelDialog.vue'
import ChannelDetail from '../components/ChannelDetail.vue'
import PageContainer from '../components/layout/PageContainer.vue'
import { useWebSocket } from '../composables/useWebSocket.js'

const channels = ref([])
const loading = ref(true)
const showCreateDialog = ref(false)
const detailChannel = ref(null)

async function fetchChannels() {
  loading.value = true
  try {
    const resp = await listChannels()
    channels.value = resp.data.channels || []
  } catch (e) {
    console.error('Failed to fetch channels:', e)
  } finally {
    loading.value = false
  }
}

function onChannelCreated() {
  showCreateDialog.value = false
  fetchChannels()
}

function wsUrl() {
  const token = localStorage.getItem('token') || ''
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${location.host}/api/devices/ws/pair-events?token=${encodeURIComponent(token)}`
}
useWebSocket(wsUrl, {
  onMessage(msg) {
    if (msg.event === 'channels_changed') fetchChannels()
  },
})

onMounted(fetchChannels)
</script>

<template>
  <PageContainer title="任务通道">
    <template #actions>
      <button @click="showCreateDialog = true" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
        创建通道
      </button>
    </template>

    <ChannelList :channels="channels" :loading="loading" @refresh="fetchChannels" @detail="detailChannel = $event" />

    <CreateChannelDialog v-if="showCreateDialog" @close="showCreateDialog = false" @created="onChannelCreated" />

    <ChannelDetail v-if="detailChannel" :channel="detailChannel" @close="detailChannel = null" @refresh="fetchChannels" />
  </PageContainer>
</template>
