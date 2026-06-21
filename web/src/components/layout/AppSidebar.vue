<!-- 管理端布局组件：提供导航、侧栏和页面容器等业务后台基础框架。 -->
<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { NAV_CATEGORIES } from '../../constants/navigation.js'

const props = defineProps({
  activeCategory: { type: String, required: true },
})

const route = useRoute()
const expanded = ref(false)

const visibleItems = computed(() => {
  const cat = NAV_CATEGORIES.find(c => c.key === props.activeCategory)
  return cat ? cat.items : []
})
</script>

<template>
  <nav
    class="flex flex-col shrink-0 border-r transition-all duration-300 relative z-10"
    :class="expanded ? 'w-52' : 'w-[56px]'"
    style="background: rgba(10, 15, 30, 0.5); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border-color: var(--border-subtle);"
    @mouseenter="expanded = true"
    @mouseleave="expanded = false"
  >
    <div class="flex-1 py-3 space-y-0.5 overflow-y-auto overflow-x-hidden">
      <!-- Category label -->
      <div
        class="px-4 pt-1 pb-2 text-[10px] uppercase tracking-widest font-semibold whitespace-nowrap transition-all duration-200"
        :class="expanded ? 'opacity-100' : 'opacity-0'"
        style="color: var(--accent-400);"
      >
        {{ NAV_CATEGORIES.find(c => c.key === props.activeCategory)?.label || '' }}
      </div>

      <router-link
        v-for="item in visibleItems"
        :key="item.path"
        :to="item.path"
        class="flex items-center h-10 mx-2 rounded-lg transition-all duration-200 group relative no-underline"
        :class="route.path === item.path
          ? 'text-sky-300'
          : 'text-slate-300 hover:text-slate-100'"
        :aria-label="item.name"
      >
        <!-- Active indicator bar -->
        <div
          v-if="route.path === item.path"
          class="absolute left-0 top-2 bottom-2 w-0.5 rounded-r-full"
          style="background: linear-gradient(180deg, var(--accent-500), var(--accent-400));"
        ></div>

        <!-- Icon -->
        <div class="w-[56px] flex items-center justify-center shrink-0">
          <svg class="w-5 h-5 transition-transform duration-200 group-hover:scale-110" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" :d="item.icon" />
          </svg>
        </div>

        <!-- Label -->
        <span
          class="text-[13px] font-medium whitespace-nowrap transition-all duration-200"
          :class="expanded ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-2 w-0 overflow-hidden'"
        >{{ item.name }}</span>

        <!-- Hover glow -->
        <div
          v-if="route.path === item.path"
          class="absolute inset-0 rounded-lg opacity-20 pointer-events-none"
          style="background: linear-gradient(90deg, rgba(14,165,233,0.3), transparent);"
        ></div>
      </router-link>
    </div>

    <!-- Bottom decoration -->
    <div class="p-3 border-t" style="border-color: var(--border-subtle);">
      <div class="flex items-center justify-center">
        <div class="w-6 h-6 rounded-full flex items-center justify-center opacity-30" style="background: var(--accent-glow-soft);">
          <svg class="w-3 h-3" style="color: var(--accent-400);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
      </div>
    </div>
  </nav>
</template>
