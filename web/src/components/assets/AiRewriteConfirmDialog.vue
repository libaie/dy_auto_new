<!-- 素材业务组件：展示或处理素材详情、参考图、AI 改写和危险操作确认。 -->
<script setup>
import { reactive, watch } from 'vue'

import AppDialog from '../ui/AppDialog.vue'
import AppButton from '../ui/AppButton.vue'

const props = defineProps({
  open: { type: Boolean, required: true },
  title: { type: String, default: '确认 AI 改写' },
  before: { type: Object, default: () => ({}) },
  candidate: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['confirm', 'cancel'])
const draft = reactive({})

watch(
  () => [props.open, props.candidate],
  () => {
    Object.keys(draft).forEach((key) => delete draft[key])
    Object.assign(draft, props.candidate || {})
  },
  { immediate: true, deep: true },
)

// 前端业务函数：协调 cancel 对应的页面流程、接口调用或状态转换。
function cancel() {
  emit('cancel')
}
</script>

<template>
  <AppDialog :open="open" :title="title" max-width="max-w-3xl" @close="cancel">
    <div class="mt-4 space-y-4">
      <p class="text-sm text-slate-400">请先核对改写结果，再保存到资产。</p>

      <div class="grid gap-3 md:grid-cols-2">
        <section class="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
          <h3 class="mb-3 text-sm font-semibold text-slate-100">改写前</h3>
          <dl class="space-y-2 text-sm">
            <div v-for="(value, key) in before" :key="key" class="space-y-1">
              <dt class="text-xs text-slate-500">{{ key }}</dt>
              <dd class="whitespace-pre-wrap text-slate-300">{{ value || '未填写' }}</dd>
            </div>
          </dl>
        </section>

        <section class="rounded-lg border border-cyan-500/30 bg-slate-950/70 p-3">
          <h3 class="mb-3 text-sm font-semibold text-slate-100">改写后</h3>
          <div class="space-y-3">
            <label v-for="(_, key) in draft" :key="key" class="block space-y-1">
              <span class="text-xs text-slate-400">{{ key }}</span>
              <textarea
                v-model="draft[key]"
                rows="3"
                class="w-full rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100"
              />
            </label>
          </div>
        </section>
      </div>

      <div class="flex justify-end gap-2">
        <AppButton type="button" variant="secondary" @click="cancel">取消</AppButton>
        <AppButton type="button" variant="success" @click="emit('confirm', { ...draft })">确认应用</AppButton>
      </div>
    </div>
  </AppDialog>
</template>
