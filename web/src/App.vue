<!-- 管理端应用根组件：承载全局布局、路由出口和登录态下的页面框架。 -->
<script setup>
import ToastNotification from './components/ToastNotification.vue'
</script>

<template>
  <div class="cinematic-bg"></div>
  <div class="dot-grid"></div>
  <RouterView />
  <ToastNotification />
</template>
