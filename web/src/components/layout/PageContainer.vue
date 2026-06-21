<!-- 管理端布局组件：提供导航、侧栏和页面容器等业务后台基础框架。 -->
<script setup>
defineProps({
  title: { type: String, required: true },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})
</script>

<template>
  <div>
    <div v-if="error" class="mb-4 glass-card border-red-500/30 text-red-400 px-4 py-3 rounded-xl flex items-center justify-between">
      <span>{{ error }}</span>
      <button class="text-red-400 hover:text-red-300 font-bold" @click="$emit('dismissError')">&times;</button>
    </div>

    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-white">{{ title }}</h1>
      <slot name="actions" />
    </div>

    <slot />
  </div>
</template>
