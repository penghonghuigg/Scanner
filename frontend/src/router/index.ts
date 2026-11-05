import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '../stores/auth'
import HomeView from '../views/HomeView.vue'
import LoginView from '../views/LoginView.vue'
import ProductManagementView from '../views/ProductManagementView.vue'
import ScanSessionCreateView from '../views/ScanSessionCreateView.vue'
import ScanSessionListView from '../views/ScanSessionListView.vue'
import ScanWorkspaceView from '../views/ScanWorkspaceView.vue'
import UserRegisterView from '../views/UserRegisterView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: HomeView, meta: { requiresAuth: true } },
    { path: '/login', name: 'login', component: LoginView },
    {
      path: '/users/register',
      name: 'user-register',
      component: UserRegisterView,
      meta: { requiresAuth: true, adminOnly: true },
    },
    {
      path: '/products',
      name: 'products',
      component: ProductManagementView,
      meta: { requiresAuth: true, adminOnly: true },
    },
    {
      path: '/scan-sessions/new',
      name: 'scan-session-create',
      component: ScanSessionCreateView,
      meta: { requiresAuth: true, creatorOnly: true },
    },
    {
      path: '/scan-sessions',
      name: 'scan-session-list',
      component: ScanSessionListView,
      meta: { requiresAuth: true, sessionStatus: 'DRAFT' },
    },
    {
      path: '/scan-sessions/:id/scan',
      name: 'scan-workspace',
      component: ScanWorkspaceView,
      meta: { requiresAuth: true },
    },
    {
      path: '/scan-results',
      name: 'scan-result-list',
      component: ScanSessionListView,
      meta: { requiresAuth: true, sessionStatus: 'COMPLETED' },
    },
    {
      path: '/scan-results/:id',
      name: 'scan-result-detail',
      component: ScanWorkspaceView,
      meta: { requiresAuth: true, sessionStatus: 'COMPLETED' },
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.ensureInitialized()
  if (to.meta.requiresAuth && !auth.user) return { name: 'login' }
  if (to.name === 'login' && auth.user) return { name: 'home' }
  if (to.meta.adminOnly && auth.user?.role !== 'ADMIN') {
    return { name: 'home', query: { denied: '1' } }
  }
  if (to.meta.creatorOnly && auth.user?.role === 'VIEWER') {
    return { name: 'home', query: { denied: '1' } }
  }
  return true
})
