<script setup>
import ToastNotification from './components/ToastNotification.vue'
</script>

<template>
  <div class="cinematic-bg"></div>
  <div class="dot-grid"></div>
  <RouterView />
  <ToastNotification />
</template>
