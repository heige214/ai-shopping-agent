import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Vant from 'vant'
import 'vant/lib/index.css'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { AUTH_EXPIRED_EVENT } from './utils/auth-events'
import './styles/main.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(Vant)

const auth = useAuthStore(pinia)

// HTTP 拦截器发现 401 时广播事件，这里清理登录态并回到登录页
window.addEventListener(AUTH_EXPIRED_EVENT, () => {
  auth.clear()
  const current = router.currentRoute.value
  if (current.name !== 'login') {
    router.push({ name: 'login', query: { redirect: current.fullPath } })
  }
})

app.mount('#app')
