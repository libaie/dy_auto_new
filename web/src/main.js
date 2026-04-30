import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import { setupAuthInterceptor } from './api/client.js'
import { useAuthStore } from './stores/auth.js'
import './style.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

// Set up 401 interceptor after pinia and router are ready
const authStore = useAuthStore(pinia)
setupAuthInterceptor(authStore, router)

app.mount('#app')
