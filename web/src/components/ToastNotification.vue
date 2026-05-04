<script setup>
import { useToastStore } from '../stores/toast.js'

const toast = useToastStore()

const typeStyles = {
  error: {
    bg: 'bg-red-500/15 border-red-500/30',
    icon: 'text-red-400',
    iconPath: 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  },
  warning: {
    bg: 'bg-amber-500/15 border-amber-500/30',
    icon: 'text-amber-400',
    iconPath: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z',
  },
  success: {
    bg: 'bg-emerald-500/15 border-emerald-500/30',
    icon: 'text-emerald-400',
    iconPath: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
  },
  info: {
    bg: 'bg-cyan-500/15 border-cyan-500/30',
    icon: 'text-cyan-400',
    iconPath: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  },
}
</script>

<template>
  <div class="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
    <TransitionGroup
      enter-active-class="transition-all duration-300 ease-out"
      enter-from-class="translate-x-full opacity-0"
      enter-to-class="translate-x-0 opacity-100"
      leave-active-class="transition-all duration-200 ease-in"
      leave-from-class="translate-x-0 opacity-100"
      leave-to-class="translate-x-full opacity-0"
    >
      <div
        v-for="t in toast.toasts"
        :key="t.id"
        :class="[
          typeStyles[t.type]?.bg || typeStyles.error.bg,
          'pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl border backdrop-blur-xl shadow-lg max-w-sm',
        ]"
      >
        <svg
          class="w-5 h-5 flex-shrink-0 mt-0.5"
          :class="typeStyles[t.type]?.icon || typeStyles.error.icon"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            :d="typeStyles[t.type]?.iconPath || typeStyles.error.iconPath"
          />
        </svg>
        <p class="text-sm text-slate-200 flex-1">{{ t.message }}</p>
        <button
          class="text-slate-500 hover:text-slate-300 transition-colors flex-shrink-0"
          @click="toast.removeToast(t.id)"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>
