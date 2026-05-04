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
  <div class="min-h-screen flex items-center justify-center login-aurora">
    <div class="w-full max-w-sm glass-card p-8 gradient-border">
      <h1 class="text-2xl font-bold text-center gradient-text mb-2">抖音助手</h1>
      <p class="text-center text-slate-400 text-sm mb-8">管理后台登录</p>

      <form @submit.prevent="handleLogin" class="space-y-5">
        <div>
          <label class="block text-sm font-medium text-slate-300 mb-1.5" for="username">用户名</label>
          <input
            id="username"
            v-model="username"
            type="text"
            required
            class="w-full px-3 py-2.5 bg-white/5 border border-white/10 rounded-lg text-slate-200 placeholder-slate-500"
            placeholder="请输入用户名"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-slate-300 mb-1.5" for="password">密码</label>
          <input
            id="password"
            v-model="password"
            type="password"
            required
            class="w-full px-3 py-2.5 bg-white/5 border border-white/10 rounded-lg text-slate-200 placeholder-slate-500"
            placeholder="请输入密码"
          />
        </div>

        <div v-if="error" class="text-red-400 text-sm bg-red-500/10 border border-red-500/20 p-2.5 rounded-lg">
          {{ error }}
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="btn-aurora w-full py-2.5 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span class="relative z-10">{{ loading ? '登录中...' : '登录' }}</span>
        </button>
      </form>
    </div>
  </div>
</template>
