import { createRouter, createWebHistory } from 'vue-router'
import { showToast } from 'vant'

import { useAuthStore } from '@/stores/auth'
import type { UserRole } from '@/types'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/user/LoginView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/user/RegisterView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/category/:id',
      name: 'category',
      component: () => import('@/views/user/CategoryView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/product/:id',
      name: 'product-detail',
      component: () => import('@/views/user/ProductDetailView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/product/:id/support',
      name: 'product-support',
      component: () => import('@/views/user/SupportView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/favorites',
      name: 'favorites',
      component: () => import('@/views/user/FavoritesView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/cart',
      name: 'cart',
      component: () => import('@/views/user/CartView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/checkout',
      name: 'checkout',
      component: () => import('@/views/user/CheckoutView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/orders',
      name: 'orders',
      component: () => import('@/views/user/OrdersView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/orders/:id',
      name: 'order-detail',
      component: () => import('@/views/user/OrderDetailView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/addresses',
      name: 'addresses',
      component: () => import('@/views/user/AddressesView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/agent/orders',
      name: 'agent-orders',
      component: () => import('@/views/agent/AgentOrdersView.vue'),
      meta: { requiresAuth: true, roles: ['agent', 'admin'] },
    },
    {
      path: '/',
      component: () => import('@/layouts/TabbarLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'home',
          component: () => import('@/views/user/HomeView.vue'),
        },
        {
          path: 'me',
          name: 'me',
          component: () => import('@/views/user/MeView.vue'),
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.ensureUserLoaded()

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && auth.isAuthenticated) {
    return { name: 'home' }
  }

  const roles = to.meta.roles as UserRole[] | undefined
  if (roles && (!auth.user || !roles.includes(auth.user.role))) {
    showToast('无权访问客服工作台')
    return { name: 'home' }
  }
  return true
})

export default router
