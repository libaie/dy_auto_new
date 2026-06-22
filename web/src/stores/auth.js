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

  // 前端业务函数：协调 login 对应的页面流程、接口调用或状态转换。
  // 入参：user、password 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 login 对应业务流程的处理结果。
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

  // 前端业务函数：协调 logout 对应的页面流程、接口调用或状态转换。
  // 入参：无显式入参 为该业务流程需要的上下文、标识或载荷。
  // 出参：返回 logout 对应业务流程的处理结果。
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
