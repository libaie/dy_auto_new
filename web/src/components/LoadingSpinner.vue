<!-- 管理端通用组件：提供业务页面复用的展示、反馈或交互能力。 -->
<script setup>
</script>

<template>
  <div class="flex items-center justify-center py-12">
    <svg
      class="animate-spin h-8 w-8 text-cyan-400"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        class="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        stroke-width="4"
      />
      <path
        class="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  </div>
</template>
