<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog } from 'vant'

import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'
import { useFavoritesStore } from '@/stores/favorites'

const auth = useAuthStore()
const favorites = useFavoritesStore()
const cart = useCartStore()
const router = useRouter()

const orderShortcuts = [
  { status: 'pending_payment', label: '待付款', icon: 'clock-o' },
  { status: 'paid', label: '待发货', icon: 'logistics' },
  { status: 'shipped', label: '待收货', icon: 'passed' },
  { status: 'completed', label: '已完成', icon: 'success' },
]

const profileSummary = computed(() => {
  const parts: string[] = []
  if (auth.user?.height_cm) parts.push(`${auth.user.height_cm}cm`)
  if (auth.user?.weight_kg) parts.push(`${auth.user.weight_kg}kg`)
  if (auth.user?.usual_size) parts.push(`常穿 ${auth.user.usual_size} 码`)
  return parts.join(' · ') || `账号：${auth.user?.username ?? ''}`
})

async function handleLogout(): Promise<void> {
  try {
    await showConfirmDialog({
      title: '退出登录',
      message: '确定要退出当前账号吗？',
    })
  } catch {
    return
  }
  favorites.clear()
  cart.clear()
  auth.logout()
  await router.replace('/login')
}

onMounted(async () => {
  try {
    await favorites.load()
  } catch {
    // 401 由全局拦截器处理；其他错误不阻塞「我的」页
  }
})
</script>

<template>
  <div class="page me-page">
    <header class="me-header">
      <h1>我的</h1>
    </header>
    <div class="me-body">
      <section class="me-card">
        <div class="me-avatar" aria-hidden="true">
          {{ (auth.user?.nickname || auth.user?.username || '?').slice(0, 1) }}
        </div>
        <div class="me-info">
          <div class="me-name">
            {{ auth.user?.nickname || auth.user?.username }}
          </div>
          <div class="me-sub">{{ profileSummary }}</div>
        </div>
      </section>

      <div class="order-shortcuts">
        <button
          v-for="entry in orderShortcuts"
          :key="entry.status"
          type="button"
          class="order-shortcut"
          @click="
            router.push({ path: '/orders', query: { status: entry.status } })
          "
        >
          <van-icon :name="entry.icon" size="19" />
          <span>{{ entry.label }}</span>
        </button>
      </div>

      <van-cell-group inset class="me-menu">
        <van-cell
          title="我的收藏"
          is-link
          :value="favorites.items.length ? String(favorites.items.length) : ''"
          @click="router.push('/favorites')"
        />
        <van-cell
          title="我的订单"
          is-link
          @click="router.push('/orders')"
        />
        <van-cell
          title="收货地址"
          is-link
          @click="router.push('/addresses')"
        />
        <van-cell title="导购会话" value="M4 上线" />
      </van-cell-group>

      <van-button block class="logout-button" @click="handleLogout">
        退出登录
      </van-button>
    </div>
  </div>
</template>

<style scoped>
.me-page {
  min-height: calc(100vh - 56px);
  min-height: calc(100vh - 56px - env(safe-area-inset-bottom));
  min-height: calc(100dvh - 56px - env(safe-area-inset-bottom));
  background: var(--color-bg);
}

.me-header {
  height: 58px;
  background: var(--color-card);
  display: flex;
  align-items: center;
  padding: 0 16px;
  border-bottom: 1px solid var(--color-border);
}

.me-header h1 {
  font-size: 16px;
  margin: 0;
}

.me-body {
  padding: 14px;
}

.me-card {
  background: var(--color-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: 16px 14px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.me-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: linear-gradient(135deg, #ffb08a, #ff5a1f);
  color: #fff;
  font-size: 17px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}

.me-name {
  font-size: 15px;
  font-weight: 700;
}

.me-sub {
  font-size: 10px;
  color: var(--color-text-secondary);
  margin-top: 3px;
}

.order-shortcuts {
  background: var(--color-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  margin-top: 10px;
  padding: 14px 6px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.order-shortcut {
  border: 0;
  background: transparent;
  color: var(--color-text-secondary);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  font-size: 10.5px;
}

.me-menu {
  margin-top: 10px;
  overflow: hidden;
  border-radius: var(--radius-card);
}

.logout-button {
  margin-top: 18px;
  height: 44px;
  border-radius: 9px;
  color: var(--color-price);
  border: 1px solid var(--color-primary-border);
  background: var(--color-card);
  font-size: 13px;
}
</style>
