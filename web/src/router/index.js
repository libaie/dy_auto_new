import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginPage.vue'),
  },
  {
    path: '/',
    component: () => import('../views/AdminLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('../views/DashboardPage.vue'),
      },
      {
        path: 'accounts',
        name: 'Accounts',
        component: () => import('../views/AccountsPage.vue'),
      },
      {
        path: 'account-groups',
        name: 'AccountGroups',
        component: () => import('../views/AccountGroupsPage.vue'),
      },
      {
        path: 'devices',
        name: 'Devices',
        component: () => import('../views/DevicesPage.vue'),
      },
      {
        path: 'tasks',
        name: 'Tasks',
        component: () => import('../views/TasksPage.vue'),
      },
      {
        path: 'chain-templates',
        name: 'ChainTemplates',
        component: () => import('../views/ChainTemplatesPage.vue'),
      },
      {
        path: 'chain-instances',
        name: 'ChainInstances',
        component: () => import('../views/ChainInstancesPage.vue'),
      },
      {
        path: 'selectors',
        name: 'Selectors',
        component: () => import('../views/SelectorsPage.vue'),
      },
      {
        path: 'channels',
        redirect: '/tasks',
      },
      {
        path: 'stats',
        name: 'Stats',
        component: () => import('../views/StatsPage.vue'),
      },
      {
        path: 'content',
        name: 'Content',
        component: () => import('../views/ContentPage.vue'),
      },
      {
        path: 'prompt-templates',
        name: 'PromptTemplates',
        component: () => import('../views/PromptTemplatesPage.vue'),
      },
      {
        path: 'data',
        name: 'DataCenter',
        component: () => import('../views/DataCenterPage.vue'),
      },
      {
        path: 'video-studio',
        name: 'VideoStudio',
        component: () => import('../views/VideoStudio.vue'),
      },
      {
        path: 'videos',
        name: 'Videos',
        component: () => import('../views/VideosPage.vue'),
      },
      {
        path: 'ai-config',
        name: 'AIConfig',
        component: () => import('../views/AIConfigPage.vue'),
      },
      {
        path: 'characters',
        name: 'Characters',
        component: () => import('../views/CharactersPage.vue'),
      },
      {
        path: 'series',
        name: 'SeriesList',
        component: () => import('../views/SeriesListPage.vue'),
      },
      {
        path: 'series/:id',
        name: 'SeriesDetail',
        component: () => import('../views/SeriesDetailPage.vue'),
      },
      {
        path: 'pipeline/:runId',
        name: 'PipelineMonitor',
        component: () => import('../views/PipelineMonitorPage.vue'),
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('../views/SettingsPage.vue'),
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  // Lazy-init store once; Pinia must be installed before first navigation
  if (!router._authStore) {
    router._authStore = useAuthStore()
  }
  const authStore = router._authStore

  if (to.matched.some((record) => record.meta.requiresAuth) && !authStore.isLoggedIn) {
    next('/login')
    return
  }

  if (to.path === '/login' && authStore.isLoggedIn) {
    next('/')
    return
  }

  next()
})

export default router
