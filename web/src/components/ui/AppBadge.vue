<script setup>
defineProps({
  variant: {
    type: String,
    default: 'info',
    validator: (v) => ['success', 'warning', 'danger', 'info', 'neutral'].includes(v),
  },
  size: {
    type: String,
    default: 'sm',
    validator: (v) => ['xs', 'sm'].includes(v),
  },
})

const variantClasses = {
  success: 'badge-success',
  warning: 'badge-warning',
  danger: 'badge-danger',
  info: 'badge-info',
  neutral: 'bg-slate-600/50 text-slate-400 border border-slate-600/50 rounded-lg px-2 py-0.5 text-xs',
}

const sizeClasses = {
  xs: 'text-[11px] px-2 py-0.5',
  sm: 'text-xs px-2.5 py-0.5',
}
</script>

<template>
  <span :class="[variantClasses[variant], sizeClasses[size], 'inline-flex items-center rounded-full font-medium']">
    <slot />
  </span>
</template>
