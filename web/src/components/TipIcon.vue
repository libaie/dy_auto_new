<script setup>
defineProps({
  text: { type: String, default: '' },
  width: { type: String, default: 'w-72' },
})
</script>

<template>
  <span class="group relative inline-flex items-center">
    <svg
      class="w-4 h-4 text-slate-500 cursor-help hover:text-slate-400 transition-colors"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <circle cx="12" cy="12" r="10" stroke-width="2" />
      <path stroke-linecap="round" d="M12 16v-4m0-4h.01" stroke-width="2" />
    </svg>
    <span
      :class="[
        width,
        'invisible group-hover:visible absolute z-50 left-6 top-0 p-3 text-xs font-normal text-slate-300 bg-slate-800/95 backdrop-blur-sm border border-white/10 rounded-lg shadow-xl leading-relaxed',
      ]"
    >
      <slot>{{ text }}</slot>
    </span>
  </span>
</template>
