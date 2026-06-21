<!-- 管理端业务页面：承载 LoginPage 页面流程，协调接口数据、用户操作和业务状态展示。 -->
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const router = useRouter()
const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

// 前端业务函数：协调 handleLogin 对应的页面流程、接口调用或状态转换。
async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await authStore.login(username.value, password.value)
    router.push('/')
  } catch (e) {
    if (e.response && e.response.data && e.response.data.detail) {
      error.value = e.response.data.detail
    } else {
      error.value = '登录失败，请稍后重试'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center relative login-aurora">
    <div class="cinematic-bg"></div>
    <div class="dot-grid"></div>

    <div class="relative z-10 w-full max-w-sm">
      <!-- Brand -->
      <div class="text-center mb-8">
        <div class="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg" style="background: linear-gradient(135deg, var(--accent-600), var(--accent-500)); box-shadow: 0 0 40px var(--accent-glow);">
          <svg class="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <h1 class="text-2xl font-black tracking-tight gradient-text">抖音助手</h1>
        <p class="text-slate-500 text-sm mt-1 font-mono tracking-wide">COMMAND CENTER</p>
      </div>

      <!-- Card -->
      <div class="card-glass p-8 card-gradient">
        <form @submit.prevent="handleLogin" class="space-y-5">
          <div>
            <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5" for="username">用户名</label>
            <input id="username" v-model="username" type="text" required class="w-full px-3 py-2.5 rounded-lg text-sm" placeholder="请输入用户名" />
          </div>

          <div>
            <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5" for="password">密码</label>
            <input id="password" v-model="password" type="password" required class="w-full px-3 py-2.5 rounded-lg text-sm" placeholder="请输入密码" />
          </div>

          <div v-if="error" class="text-red-400 text-xs bg-red-500/8 border border-red-500/15 p-2.5 rounded-lg flex items-center gap-2">
            <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"/></svg>
            {{ error }}
          </div>

          <button type="submit" :disabled="loading" class="btn-primary w-full py-2.5 text-sm justify-center">
            {{ loading ? '验证中...' : '进入指挥中心' }}
          </button>
        </form>
      </div>

      <p class="text-center text-[11px] text-slate-600 mt-6 font-mono tracking-wider">DOUYIN AUTOMATION · HELIX COMMAND</p>
    </div>
  </div>
</template>
