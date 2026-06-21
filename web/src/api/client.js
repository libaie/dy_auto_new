// 前端 API 客户端：封装 client 相关后端接口，统一给页面和组件调用。
import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// Request interceptor: attach JWT token
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: handle 401 + global toast
// Handlers are set up lazily by setupAuthInterceptor() in main.js
// to avoid circular dependency with router/store
let _authHandler = null
let _toastHandler = null

// 前端业务函数：协调 handleUnauthorizedResponse 对应的页面流程、接口调用或状态转换。
export function handleUnauthorizedResponse() {
  if (_authHandler) {
    _authHandler()
  } else {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    window.location.href = '/login'
  }
}

client.interceptors.response.use(
  (response) => response,
  (error) => {
    const config = error.config || {}
    const silent = config.silent === true
    // 401 → redirect to login
    if (error.response && error.response.status === 401) {
      if (!silent && config.skipAuthRedirect !== true) {
        handleUnauthorizedResponse()
      }
      return Promise.reject(error)
    }

    // All other errors → show toast
    if (_toastHandler && !silent && config.skipGlobalErrorToast !== true) {
      const data = error.response?.data
      const message = data?.detail || data?.message || (error.response ? `请求失败 (${error.response.status})` : '网络连接失败，请检查网络')
      _toastHandler(message)
    }

    return Promise.reject(error)
  }
)

/**
 * Call this after router and pinia are initialized.
 * Sets up the 401 handler to properly log out via the store and redirect via the router.
 */
// 前端业务函数：协调 setupAuthInterceptor 对应的页面流程、接口调用或状态转换。
export function setupAuthInterceptor(authStore, router) {
  _authHandler = () => {
    authStore.logout()
    router.push('/login')
  }
}

/**
 * Call this after pinia is initialized.
 * Sets up the global toast handler for all non-401 errors.
 */
// 前端业务函数：协调 setupToastInterceptor 对应的页面流程、接口调用或状态转换。
export function setupToastInterceptor(toastStore) {
  _toastHandler = (message) => {
    toastStore.error(message)
  }
}

export default client
