<!-- 运营业务组件：展示账号、频道、关键词或任务创建相关业务交互。 -->
<script setup>
import { CHANNEL_TASK_TYPE_LABEL, CHANNEL_STATUS_LABEL, CHANNEL_STATUS_CLASS } from '../../constants/channels.js'

defineProps({
  channel: { type: Object, required: true },
})

defineEmits(['pause', 'resume', 'cancel', 'delete', 'click'])
</script>

<template>
  <div
    class="bg-slate-800/50 backdrop-blur rounded-lg shadow p-4 border border-slate-700 hover:border-slate-500 transition-all cursor-pointer"
    @click="$emit('click', channel)"
  >
    <div class="flex items-center justify-between mb-2">
      <span class="text-sm font-medium text-white">
        {{ channel.group_name }} · {{ CHANNEL_TASK_TYPE_LABEL[channel.task_type] || channel.task_type }}
      </span>
      <span :class="CHANNEL_STATUS_CLASS[channel.status] || 'bg-slate-600/50 text-slate-400'" class="px-2 py-0.5 text-xs rounded-full">
        {{ CHANNEL_STATUS_LABEL[channel.status] || channel.status }}
      </span>
    </div>
    <div class="mb-2">
      <div class="flex justify-between text-xs text-slate-400 mb-1">
        <span>{{ channel.completed }}/{{ channel.total }} 完成</span>
        <span>{{ channel.pending }} 待处理</span>
      </div>
      <div class="w-full bg-slate-700 rounded-full h-2">
        <div class="bg-green-500 h-2 rounded-full transition-all" :style="{ width: channel.total ? (channel.completed / channel.total * 100) + '%' : '0%' }" />
      </div>
    </div>
    <div class="flex items-center justify-between text-xs text-slate-500">
      <span>{{ channel.account_mode === 'single_account' ? '单账号' : '轮转' }}</span>
      <span>{{ channel.assigned }} 执行中</span>
    </div>
    <div class="flex gap-2 mt-3">
      <button v-if="channel.status === 'active'" @click.stop="$emit('pause', channel)" class="px-3 py-1 text-xs bg-yellow-500/20 text-yellow-400 rounded hover:bg-yellow-500/30 transition-colors">暂停</button>
      <button v-if="channel.status === 'paused'" @click.stop="$emit('resume', channel)" class="px-3 py-1 text-xs bg-green-500/20 text-green-400 rounded hover:bg-green-500/30 transition-colors">恢复</button>
      <button v-if="channel.status !== 'cancelled' && channel.status !== 'completed'" @click.stop="$emit('cancel', channel)" class="px-3 py-1 text-xs bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 transition-colors">取消</button>
      <button @click.stop="$emit('delete', channel)" class="px-3 py-1 text-xs bg-slate-600/50 text-slate-300 rounded hover:bg-slate-600 transition-colors">删除</button>
    </div>
  </div>
</template>
