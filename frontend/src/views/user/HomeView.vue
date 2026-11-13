<script setup lang="ts">
import { computed } from 'vue'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const displayName = computed(
  () => auth.user?.nickname || auth.user?.username || '',
)
</script>

<template>
  <div class="page home-page">
    <header class="home-header">
      <div class="brand">
        <div class="brand-logo" aria-hidden="true">AI</div>
        <div>
          <h1 class="brand-title">AI 找货</h1>
          <div class="brand-sub">对话式导购助手</div>
        </div>
      </div>
    </header>
    <div class="home-body">
      <div class="empty-card">
        <div class="empty-avatar" aria-hidden="true">AI</div>
        <h2>你好，{{ displayName }}</h2>
        <p>AI 导购对话将在 M4 上线</p>
        <p class="empty-sub">当前为 M0 项目骨架，登录与双 Tab 已就绪</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home-page {
  min-height: calc(100vh - 56px);
  min-height: calc(100vh - 56px - env(safe-area-inset-bottom));
  min-height: calc(100dvh - 56px - env(safe-area-inset-bottom));
  background: var(--color-bg);
}

.home-header {
  height: 58px;
  background: var(--color-card);
  display: flex;
  align-items: center;
  padding: 0 16px;
  border-bottom: 1px solid var(--color-border);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-logo {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: var(--color-primary-gradient);
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-title {
  font-size: 15px;
  font-weight: 700;
  line-height: 1.1;
  margin: 0;
}

.brand-sub {
  font-size: 10px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}

.home-body {
  padding: 16px;
}

.empty-card {
  background: var(--color-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: 36px 20px;
  text-align: center;
}

.empty-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  margin: 0 auto 14px;
  background: var(--color-primary-gradient);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-card h2 {
  font-size: 16px;
  margin: 0 0 6px;
}

.empty-card p {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 0;
}

.empty-sub {
  margin-top: 4px;
  color: var(--color-text-tertiary);
}
</style>
