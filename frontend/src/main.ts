import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Vant from 'vant'
import 'vant/lib/index.css'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { useCartStore } from './stores/cart'
import { useFavoritesStore } from './stores/favorites'
import { AUTH_EXPIRED_EVENT } from './utils/auth-events'
import './styles/main.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(Vant)

const auth = useAuthStore(pinia)
const favorites = useFavoritesStore(pinia)
const cart = useCartStore(pinia)

// HTTP 拦截器发现 401 时广播事件，这里清理登录态并回到登录页
window.addEventListener(AUTH_EXPIRED_EVENT, () => {
  auth.clear()
  favorites.clear()
  cart.clear()
  const current = router.currentRoute.value
  // 首屏导航期间 currentRoute 仍是 START_LOCATION，此时由路由守卫负责 redirect
  if (current.matched.length > 0 && current.name !== 'login') {
    router.push({ name: 'login', query: { redirect: current.fullPath } })
  }
})

app.mount('#app')
