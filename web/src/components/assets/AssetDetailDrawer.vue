<!-- 素材业务组件：展示或处理素材详情、参考图、AI 改写和危险操作确认。 -->
<script setup>
import {
  Dialog,
  DialogPanel,
  DialogTitle,
  TransitionChild,
  TransitionRoot,
} from '@headlessui/vue'

defineProps({
  open: { type: Boolean, required: true },
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
})

const emit = defineEmits(['close'])
</script>

<template>
  <TransitionRoot :show="open" as="template">
    <Dialog as="div" class="relative z-50" @close="emit('close')">
      <TransitionChild
        as="template"
        enter="ease-out duration-200"
        enter-from="opacity-0"
        enter-to="opacity-100"
        leave="ease-in duration-150"
        leave-from="opacity-100"
        leave-to="opacity-0"
      >
        <div
          data-test="drawer-backdrop"
          class="fixed inset-0 bg-black/60"
          @click="emit('close')"
        />
      </TransitionChild>

      <div class="fixed inset-0 flex justify-end overflow-hidden">
        <TransitionChild
          as="template"
          enter="transform transition ease-out duration-200"
          enter-from="translate-x-full"
          enter-to="translate-x-0"
          leave="transform transition ease-in duration-150"
          leave-from="translate-x-0"
          leave-to="translate-x-full"
        >
          <DialogPanel
            class="flex h-full w-full max-w-2xl flex-col border-l border-slate-700 bg-slate-950 shadow-2xl"
            :aria-label="title || '资产详情'"
          >
            <header class="flex items-start justify-between border-b border-slate-800 px-5 py-4">
              <div class="min-w-0">
                <DialogTitle class="text-lg font-semibold text-slate-100">
                  {{ title }}
                </DialogTitle>
                <p v-if="subtitle" class="mt-1 truncate text-sm text-slate-400">{{ subtitle }}</p>
              </div>
              <button
                data-test="close-drawer"
                data-autofocus
                type="button"
                class="rounded border border-slate-700 px-3 py-1 text-sm text-slate-300 hover:bg-slate-800"
                aria-label="关闭详情"
                @click="emit('close')"
              >
                关闭
              </button>
            </header>

            <main class="min-h-0 flex-1 overflow-y-auto p-5">
              <slot />
            </main>

            <footer v-if="$slots.footer" class="border-t border-slate-800 p-4">
              <slot name="footer" />
            </footer>
          </DialogPanel>
        </TransitionChild>
      </div>
    </Dialog>
  </TransitionRoot>
</template>
