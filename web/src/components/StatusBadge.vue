<script setup>
defineProps({
  status: {
    type: String,
    required: true,
  },
})

const colorMap = {
  active: 'bg-green-100 text-green-800',
  online: 'bg-green-100 text-green-800',
  offline: 'bg-gray-100 text-gray-800',
  pending: 'bg-yellow-100 text-yellow-800',
  running: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-800',
  risk_controlled: 'bg-red-100 text-red-800',
  disabled: 'bg-gray-100 text-gray-800',
}

const labelMap = {
  active: '正常',
  online: '在线',
  offline: '离线',
  pending: '待执行',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
  risk_controlled: '风控中',
  disabled: '已禁用',
}
</script>

<template>
  <span
    :class="[colorMap[status] || 'bg-gray-100 text-gray-800']"
    class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
  >
    {{ labelMap[status] || status }}
  </span>
</template>
