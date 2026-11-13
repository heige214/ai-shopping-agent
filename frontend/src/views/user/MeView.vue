<script setup lang="ts">
import { useRouter } from 'vue-router'
import { showConfirmDialog } from 'vant'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

async function handleLogout(): Promise<void> {
  try {
    await showConfirmDialog({
      title: '退出登录',
      message: '确定要退出当前账号吗？',
    })
  } catch {
    return
  }
  auth.logout()
  await router.replace('/login')
}
</script>

<template>
  <div class="page me-page">
    <header class="me-header">
      <h1>我的</h1>
    </header>
    <main class="me-body">
      <section class="me-card">
        <div class="me-avatar" aria-hidden="true">
          {{ (auth.user?.nickname || auth.user?.username || '?').slice(0, 1) }}
        </div>
        <div class="me-info">
          <div class="me-name">
            {{ auth.user?.nickname || auth.user?.username }}
          </div>
          <div class="me-sub">
            <template v-if="auth.user?.height_cm || auth.user?.weight_kg">
              <span v-if="auth.user?.height_cm">{{ auth.user?.height_cm }}cm</span>
              <span v-if="auth.user?.weight_kg"> / {{ auth.user?.weight_kg }}kg</span>
              <span v-if="auth.user?.usual_size">
                · 常穿 {{ auth.user?.usual_size }} 码
              </span>
            </template>
            <template v-else>账号：{{ auth.user?.username }}</template>
          </div>
        </div>
      </section>

      <section class="me-placeholder">
        <div class="placeholder-title">更多功能将在后续模块上线</div>
        <p class="placeholder-text">收藏、地址、订单、导购会话</p>
      </section>

      <van-button block class="logout-button" @click="handleLogout">
        退出登录
      </van-button>
    </main>
  </div>
</template>

<style scoped>
.me-page {
  min-height: calc(100vh - 56px);
  min-height: calc(100dvh - 56px);
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

.me-placeholder {
  background: var(--color-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  margin-top: 10px;
  padding: 20px 14px;
  text-align: center;
}

.placeholder-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--color-text);
}

.placeholder-text {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin: 6px 0 0;
}

.logout-button {
  margin-top: 18px;
  height: 42px;
  border-radius: 9px;
  color: var(--color-price);
  border: 1px solid var(--color-primary-border);
  background: var(--color-card);
  font-size: 13px;
}
</style>
