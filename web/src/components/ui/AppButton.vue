<script setup>
defineProps({
  variant: {
    type: String,
    default: 'primary',
    validator: (v) => ['primary', 'secondary', 'danger', 'ghost', 'success'].includes(v),
  },
  size: {
    type: String,
    default: 'md',
    validator: (v) => ['sm', 'md', 'lg'].includes(v),
  },
  disabled: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
})

const variantClasses = {
  primary: 'btn-aurora text-white',
  secondary: 'border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10',
  danger: 'bg-red-500/20 text-red-400 hover:bg-red-500/30 border border-red-500/25',
  ghost: 'text-slate-400 hover:text-white hover:bg-white/5',
  success: 'bg-gradient-to-r from-emerald-600 to-emerald-500 text-white hover:from-emerald-500 hover:to-emerald-400 shadow-lg shadow-emerald-500/25',
}

const sizeClasses = {
  sm: 'px-3 py-1 text-xs rounded-lg',
  md: 'px-4 py-2 text-sm font-medium rounded-xl',
  lg: 'px-6 py-2.5 text-base font-medium rounded-xl',
}
</script>

<template>
  <button
    :disabled="disabled || loading"
    :class="[variantClasses[variant], sizeClasses[size], { 'opacity-50 cursor-not-allowed': disabled || loading }]"
    class="inline-flex items-center transition-colors"
  >
    <span v-if="variant === 'primary' || variant === 'success'" class="relative z-10">
      <slot />
    </span>
    <template v-else>
      <slot />
    </template>
  </button>
</template>
