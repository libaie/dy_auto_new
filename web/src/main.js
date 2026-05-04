import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import { setupAuthInterceptor, setupToastInterceptor } from './api/client.js'
import { useAuthStore } from './stores/auth.js'
import { useToastStore } from './stores/toast.js'
import './style.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

// Set up interceptors after pinia and router are ready
const authStore = useAuthStore(pinia)
setupAuthInterceptor(authStore, router)

const toastStore = useToastStore(pinia)
setupToastInterceptor(toastStore)

app.mount('#app')
