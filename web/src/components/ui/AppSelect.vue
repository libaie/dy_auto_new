<script setup>
defineProps({
  modelValue: { type: [String, Number], default: '' },
  options: { type: Array, required: true },
  placeholder: { type: String, default: '请选择' },
  disabled: { type: Boolean, default: false },
  selectClass: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <select
    :value="modelValue"
    :disabled="disabled"
    :class="[
      'w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 transition-colors',
      disabled ? 'opacity-50 cursor-not-allowed' : '',
      selectClass,
    ]"
    @change="emit('update:modelValue', $event.target.value)"
  >
    <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
    <option
      v-for="opt in options"
      :key="opt.value"
      :value="opt.value"
    >
      {{ opt.label }}
    </option>
  </select>
</template>
