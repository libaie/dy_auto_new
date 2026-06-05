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
        path: 'one-sentence-video',
        name: 'OneSentenceVideo',
        component: () => import('../views/OneSentenceVideoPage.vue'),
      },
      {
        path: 'image-creation',
        name: 'ImageCreation',
        component: () => import('../views/ImageCreationPage.vue'),
      },
      {
        path: 'image-production/strategies',
        name: 'ImageProductionStrategies',
        component: () => import('../views/ImageProductionStrategiesPage.vue'),
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
        path: 'scenes',
        name: 'Scenes',
        component: () => import('../views/ScenesPage.vue'),
      },
      {
        path: 'dict-manage',
        name: 'DictManage',
        component: () => import('../views/DictManagePage.vue'),
      },
      {
        path: 'dm-sequences',
        name: 'DMSequences',
        component: () => import('../views/DMSequenceManagePage.vue'),
      },
      {
        path: 'director/:seriesId/:episodeId',
        name: 'Director',
        component: () => import('../views/DirectorPage.vue'),
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
        path: 'series/:seriesId/agency-console',
        name: 'AgencyConsole',
        component: () => import('../views/AgencyConsolePage.vue'),
      },
      {
        path: 'series/:seriesId/collection-builder',
        name: 'CollectionBuilder',
        component: () => import('../views/CollectionBuilderPage.vue'),
      },
      {
        path: 'pipeline/:runId',
        name: 'PipelineMonitor',
        component: () => import('../views/PipelineMonitorPage.vue'),
      },
      {
        path: 'ai-video-review',
        name: 'AIVideoReview',
        component: () => import('../views/AIVideoReviewPage.vue'),
      },
      {
        path: 'video-production/:runId',
        name: 'VideoProductionMonitor',
        component: () => import('../views/VideoProductionMonitorPage.vue'),
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('../views/UsersPage.vue'),
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

const ADMIN_ONLY_PATHS = [
  '/accounts', '/account-groups', '/devices', '/chain-templates', '/chain-instances',
  '/selectors', '/settings', '/prompt-templates', '/ai-config', '/dict-manage',
  '/characters', '/scenes', '/series', '/director', '/pipeline', '/ai-video-review', '/one-sentence-video', '/image-creation', '/image-production/strategies', '/stats',
  '/users',
]

router.beforeEach((to, from, next) => {
  if (!router._authStore) {
    router._authStore = useAuthStore()
  }
  const authStore = router._authStore

  if (to.matched.some((record) => record.meta.requiresAuth) && !authStore.isLoggedIn) {
    next('/login')
    return
  }

  if (authStore.isLoggedIn && !authStore.isAdmin && ADMIN_ONLY_PATHS.some(p => to.path.startsWith(p))) {
    next('/')
    return
  }

  if (to.path === '/login' && authStore.isLoggedIn) {
    next('/')
    return
  }

  next()
})

export default router
