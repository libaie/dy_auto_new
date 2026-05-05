<template>
  <div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" @click.self="$emit('close')">
    <div class="bg-slate-800 rounded-xl shadow-xl w-full max-w-2xl mx-4 p-6 max-h-[80vh] overflow-y-auto border border-slate-700">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-bold text-white">通道详情</h2>
        <button @click="$emit('close')" class="text-slate-400 hover:text-white text-2xl leading-none">&times;</button>
      </div>

      <!-- Stats -->
      <div class="grid grid-cols-5 gap-2 mb-4">
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
      </div>

      <!-- Items table -->
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-slate-700">
              <th class="text-left py-2 px-2 text-slate-400 font-medium">关键词</th>
              <th class="text-left py-2 px-2 text-slate-400 font-medium">账号</th>
              <th class="text-left py-2 px-2 text-slate-400 font-medium">状态</th>
              <th class="text-left py-2 px-2 text-slate-400 font-medium">设备</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in detail.items" :key="item.id" class="border-b border-slate-700/50 hover:bg-slate-700/30">
              <td class="py-2 px-2 text-white">{{ item.keyword }}</td>
              <td class="py-2 px-2 text-slate-300">{{ item.account_nickname || item.account_id }}</td>
              <td class="py-2 px-2">
                <span :class="itemStatusClass(item.status)" class="px-2 py-0.5 text-xs rounded-full">
                  {{ itemStatusLabel(item.status) }}
                </span>
              </td>
              <td class="py-2 px-2 text-slate-500">{{ item.device_name || '-' }}</td>
            </tr>
            <tr v-if="!detail.items || detail.items.length === 0">
              <td colspan="4" class="py-4 text-center text-slate-500">暂无子项</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getChannel } from '../api/channels.js'

const props = defineProps({ channel: Object })
const emit = defineEmits(['close', 'refresh'])

const detail = ref({ items: [], total: 0, pending: 0, assigned: 0, completed: 0, failed: 0, skipped: 0 })

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

onMounted(async () => {
  try {
    const resp = await getChannel(props.channel.id)
    detail.value = resp.data
  } catch (e) {
    console.error('Failed to load channel detail:', e)
  }
})
</script>
