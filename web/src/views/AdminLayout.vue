<!-- 管理端业务页面：承载 AdminLayout 页面流程，协调接口数据、用户操作和业务状态展示。 -->
<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppTopNav from '../components/layout/AppTopNav.vue'
import AppSidebar from '../components/layout/AppSidebar.vue'
import { getCategoryByRoute } from '../constants/navigation.js'

const route = useRoute()
const activeCategory = computed(() => getCategoryByRoute(route))
</script>

<template>
  <div class="h-screen flex flex-col overflow-hidden" style="background: var(--bg-void);">
    <AppTopNav :activeCategory="activeCategory" />
    <div class="flex flex-1 overflow-hidden">
      <AppSidebar :activeCategory="activeCategory" />
      <main class="min-w-0 flex-1 overflow-auto">
        <div class="min-w-0 p-6 animate-in">
          <RouterView />
        </div>
      </main>
    </div>
  </div>
</template>
