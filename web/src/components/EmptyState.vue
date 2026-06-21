<!-- 管理端通用组件：提供业务页面复用的展示、反馈或交互能力。 -->
<script setup>
defineProps({
  message: {
    type: String,
    default: '暂无数据',
  },
})
</script>

<template>
  <div class="flex flex-col items-center justify-center py-16 text-slate-400">
    <div class="relative mb-4">
      <div class="absolute inset-0 rounded-full blur-xl opacity-20" style="background: var(--accent-glow-soft);"></div>
      <svg
        class="h-14 w-14 relative opacity-40"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="1.2"
          d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
        />
      </svg>
    </div>
    <p class="text-sm text-slate-500">{{ message }}</p>
  </div>
</template>
