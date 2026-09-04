import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  { path: '/register', name: 'register', component: () => import('../views/RegisterView.vue'), meta: { public: true } },
  { path: '/', name: 'chat', component: () => import('../views/ChatView.vue') },
  { path: '/profile', name: 'profile', component: () => import('../views/ProfileView.vue') },
  {
    path: '/admin',
    component: () => import('../views/admin/AdminLayout.vue'),
    meta: { admin: true },
    children: [
      { path: '', redirect: '/admin/kbs' },
      { path: 'kbs', name: 'admin-kbs', component: () => import('../views/admin/KnowledgeBaseView.vue') },
      { path: 'documents', name: 'admin-documents', component: () => import('../views/admin/DocumentView.vue') },
      { path: 'stats', name: 'admin-stats', component: () => import('../views/admin/StatsView.vue') },
    ],
  },
  { path: '/forbidden', name: 'forbidden', component: () => import('../views/ForbiddenView.vue'), meta: { public: true } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()

  if (to.meta.public) return true
  if (!auth.isLoggedIn) return { path: '/login', query: { redirect: to.fullPath } }
  // 管理端双重校验（后端 require_admin 为最终防线）
  if (to.meta.admin && !auth.isAdmin) return { path: '/forbidden' }
  return true
})

export default router
