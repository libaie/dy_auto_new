<script setup>
import AppTopNav from '../components/layout/AppTopNav.vue'
import AppSidebar from '../components/layout/AppSidebar.vue'
</script>

<template>
  <div class="h-screen flex flex-col overflow-hidden" style="background: var(--bg-void);">
    <AppTopNav />
    <div class="flex flex-1 overflow-hidden">
      <AppSidebar />
      <main class="flex-1 overflow-auto">
        <div class="p-6 animate-in">
          <RouterView />
        </div>
      </main>
    </div>
  </div>
</template>
