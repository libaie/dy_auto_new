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

// Response interceptor: handle 401
// Auth handler is set up lazily by setupAuthInterceptor() in main.js
// to avoid circular dependency with router/store
let _authHandler = null

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      if (_authHandler) {
        _authHandler()
      } else {
        // Fallback if interceptor fires before setup
        localStorage.removeItem('token')
        localStorage.removeItem('username')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

/**
 * Call this after router and pinia are initialized.
 * Sets up the 401 handler to properly log out via the store and redirect via the router.
 */
export function setupAuthInterceptor(authStore, router) {
  _authHandler = () => {
    authStore.logout()
    router.push('/login')
  }
}

export default client
