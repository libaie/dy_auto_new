<template>
  <div class="bg-white rounded-xl border p-4">
    <h3 class="text-sm font-semibold text-gray-700 mb-3">模型路由配置</h3>
    <div class="space-y-2">
      <div v-for="m in models" :key="m.id"
           class="flex items-center gap-3 p-2 rounded-lg cursor-pointer hover:bg-gray-50 transition"
           :class="{ 'ring-2 ring-blue-500 bg-blue-50': props.selected === m.id }"
           @click="$emit('select', m.id)">
        <div class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
             :class="providerColor(m.provider)">{{ m.name[0] }}</div>
        <div class="flex-1">
          <div class="text-sm font-medium text-gray-800">{{ m.name }}</div>
          <div class="text-xs text-gray-400">{{ m.provider }}</div>
        </div>
        <div v-if="props.selected === m.id" class="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center">
          <svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" /></svg>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  models: { type: Array, default: () => [] },
  selected: { type: String, default: '' },
})
defineEmits(['select'])

function providerColor(p) {
  return { volcengine: 'bg-purple-100 text-purple-700', kuaishou: 'bg-green-100 text-green-700',
           runninghub: 'bg-orange-100 text-orange-700' }[p] || 'bg-gray-100'
}
</script>
