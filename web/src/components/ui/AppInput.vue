<!-- 管理端通用 UI 组件：提供业务页面复用的按钮、输入、选择和弹窗基础能力。 -->
<script setup>
defineProps({
  modelValue: { type: [String, Number], default: '' },
  type: { type: String, default: 'text' },
  placeholder: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  error: { type: String, default: '' },
  inputClass: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <input
    :type="type"
    :value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    :class="[
      'w-full rounded-lg border bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder-slate-500 transition-colors',
      error ? 'border-red-500/50 focus:border-red-500' : 'border-white/10',
      disabled ? 'opacity-50 cursor-not-allowed' : '',
      inputClass,
    ]"
    @input="emit('update:modelValue', $event.target.value)"
  />
</template>
