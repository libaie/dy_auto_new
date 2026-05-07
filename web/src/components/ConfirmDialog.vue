<script setup>
import {
  Dialog,
  DialogPanel,
  DialogTitle,
  TransitionRoot,
  TransitionChild,
} from '@headlessui/vue'

defineProps({
  open: { type: Boolean, required: true },
  title: { type: String, default: '确认操作' },
  message: { type: String, default: '确定要执行此操作吗？' },
  confirmText: { type: String, default: '确认' },
  danger: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['confirm', 'cancel'])
</script>

<template>
  <TransitionRoot :show="open" as="template">
    <Dialog as="div" class="relative z-50" @close="loading ? null : emit('cancel')">
      <!-- Backdrop -->
      <TransitionChild
        as="template"
        enter="ease-out duration-200"
        enter-from="opacity-0"
        enter-to="opacity-100"
        leave="ease-in duration-150"
        leave-from="opacity-100"
        leave-to="opacity-0"
      >
        <div class="fixed inset-0 bg-black/60 backdrop-blur-md" />
      </TransitionChild>

      <!-- Panel -->
      <div class="fixed inset-0 overflow-y-auto">
        <div class="flex min-h-full items-center justify-center p-4">
          <TransitionChild
            as="template"
            enter="ease-out duration-300"
            enter-from="opacity-0 scale-90 -translate-y-4"
            enter-to="opacity-100 scale-100 translate-y-0"
            leave="ease-in duration-200"
            leave-from="opacity-100 scale-100 translate-y-0"
            leave-to="opacity-0 scale-90 -translate-y-4"
          >
            <DialogPanel
              :class="[
                'relative overflow-hidden w-full max-w-md p-6 rounded-2xl border backdrop-blur-xl',
                danger
                  ? 'bg-slate-900/95 border-red-500/20 shadow-2xl shadow-red-500/10'
                  : 'bg-slate-900/95 border-white/10 shadow-2xl shadow-purple-500/10',
              ]"
            >
              <!-- Background glow orb -->
              <div
                :class="[
                  'absolute -top-12 -right-12 w-40 h-40 rounded-full blur-3xl pointer-events-none transition-colors duration-500',
                  danger ? 'bg-red-500/15' : 'bg-purple-500/15',
                ]"
              />
              <div
                :class="[
                  'absolute -bottom-12 -left-12 w-32 h-32 rounded-full blur-3xl pointer-events-none transition-colors duration-500',
                  danger ? 'bg-orange-500/10' : 'bg-cyan-500/10',
                ]"
              />

              <div class="relative">
                <!-- Icon + Title -->
                <div class="flex items-center gap-4">
                  <!-- Animated icon ring -->
                  <div
                    :class="[
                      'relative flex-shrink-0 w-12 h-12 rounded-2xl flex items-center justify-center',
                      danger
                        ? 'bg-red-500/10 border border-red-500/20'
                        : 'bg-purple-500/10 border border-purple-500/20',
                    ]"
                  >
                    <!-- Outer pulse ring -->
                    <span
                      :class="[
                        'absolute inset-0 rounded-2xl animate-ping opacity-30',
                        danger ? 'bg-red-500/20' : 'bg-purple-500/20',
                      ]"
                      style="animation-duration: 2s"
                    />
                    <!-- Danger: exclamation triangle -->
                    <svg v-if="danger" class="relative w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                    </svg>
                    <!-- Normal: question mark -->
                    <svg v-else class="relative w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>

                  <DialogTitle class="text-lg font-semibold text-white leading-tight">
                    {{ title }}
                  </DialogTitle>
                </div>

                <!-- Message -->
                <p class="mt-4 pl-[56px] text-sm text-slate-400 leading-relaxed">
                  {{ message }}
                </p>

                <!-- Divider -->
                <div class="mt-5 mb-5 border-t border-white/5" />

                <!-- Buttons -->
                <div class="flex justify-end gap-3">
                  <button
                    type="button"
                    :disabled="loading"
                    class="px-5 py-2.5 text-sm font-medium text-slate-400 hover:text-slate-200 hover:bg-white/5 rounded-xl transition-all duration-200 disabled:opacity-50"
                    @click="emit('cancel')"
                  >
                    取消
                  </button>
                  <button
                    type="button"
                    :disabled="loading"
                    :class="[
                      'relative px-5 py-2.5 text-sm font-semibold text-white rounded-xl transition-all duration-200',
                      'hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98]',
                      'disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0',
                      danger
                        ? 'bg-gradient-to-r from-red-600 to-rose-500 hover:from-red-500 hover:to-rose-400 shadow-lg shadow-red-500/30 hover:shadow-red-500/40'
                        : 'bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 shadow-lg shadow-purple-500/30 hover:shadow-purple-500/40',
                    ]"
                    @click="emit('confirm')"
                  >
                    <!-- Loading spinner -->
                    <span v-if="loading" class="flex items-center gap-2">
                      <svg class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      处理中...
                    </span>
                    <span v-else>{{ confirmText }}</span>
                  </button>
                </div>
              </div>
            </DialogPanel>
          </TransitionChild>
        </div>
      </div>
    </Dialog>
  </TransitionRoot>
</template>
