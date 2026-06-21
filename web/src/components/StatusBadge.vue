<!-- 管理端通用组件：提供业务页面复用的展示、反馈或交互能力。 -->
<script setup>
defineProps({
  status: {
    type: String,
    required: true,
  },
})

const badgeClassMap = {
  active: 'badge-success',
  online: 'badge-success',
  offline: 'badge-info',
  pending: 'badge-warning',
  running: 'badge-info',
  completed: 'badge-success',
  failed: 'badge-danger',
  cancelled: 'badge-info',
  risk_controlled: 'badge-danger',
  disabled: 'badge-info',
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

const titleMap = {
  active: '账号状态正常，可执行任务',
  online: '设备当前在线，可执行任务',
  offline: '设备当前离线，无法执行任务',
  pending: '排队中等待设备执行的任务',
  running: '正在设备上执行的任务',
  completed: '已成功完成的任务',
  failed: '执行出错的任务，可查看详情或重试',
  cancelled: '被手动取消的任务',
  risk_controlled: '账号触发抖音平台风控，暂停任务执行',
  disabled: '手动禁用的账号，不会分配任何任务',
}
</script>

<template>
  <span
    :class="badgeClassMap[status] || 'badge-info'"
    :title="titleMap[status] || ''"
    class="inline-flex items-center"
  >
    {{ labelMap[status] || status }}
  </span>
</template>
