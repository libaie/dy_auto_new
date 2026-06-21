// 前端状态仓库：维护 auth 相关登录态、消息提示或跨页面状态。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi } from '../api/auth.js'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const username = ref(localStorage.getItem('username') || '')
  const userId = ref(localStorage.getItem('userId') || '')
  const role = ref(localStorage.getItem('role') || '')

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => role.value === 'admin')

  async function login(user, password) {
    const response = await loginApi(user, password)
    const data = response.data
    token.value = data.token
    username.value = user
    userId.value = data.user_id || ''
    role.value = data.role || 'operator'
    localStorage.setItem('token', data.token)
    localStorage.setItem('username', user)
    localStorage.setItem('userId', data.user_id || '')
    localStorage.setItem('role', data.role || 'operator')
  }

  function logout() {
    token.value = ''
    username.value = ''
    userId.value = ''
    role.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    localStorage.removeItem('userId')
    localStorage.removeItem('role')
  }

  return { token, username, userId, role, isLoggedIn, isAdmin, login, logout }
})
