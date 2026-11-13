<script setup lang="ts">
import { computed } from 'vue'
import { showToast } from 'vant'

import ProductDiscoveryPanel from '@/components/catalog/ProductDiscoveryPanel.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const displayName = computed(
  () => auth.user?.nickname || auth.user?.username || '',
)

const examples = ['找一件蓝色薄衬衫', '200 元以内的运动鞋', '通勤双肩包']

function handleExample(): void {
  showToast('AI 导购将在 M4 上线')
}
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
      <section class="greeting-card">
        <div class="greeting-avatar" aria-hidden="true">AI</div>
        <div class="greeting-text">
          <h2>你好，{{ displayName }}</h2>
          <p>说出你想找的，AI 帮你挑合适的款。</p>
        </div>
      </section>

      <div class="example-chips">
        <button
          v-for="example in examples"
          :key="example"
          type="button"
          class="example-chip"
          @click="handleExample"
        >
          {{ example }}
        </button>
      </div>

      <ProductDiscoveryPanel />
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
  padding: 14px;
}

.greeting-card {
  background: var(--color-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: 16px;
  display: flex;
  gap: 12px;
  align-items: center;
}

.greeting-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--color-primary-gradient);
  color: #fff;
  font-size: 14px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}

.greeting-text h2 {
  margin: 0;
  font-size: 15px;
}

.greeting-text p {
  margin: 4px 0 0;
  font-size: 11px;
  color: var(--color-text-secondary);
}

.example-chips {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 10px 0 2px;
  scrollbar-width: none;
}

.example-chips::-webkit-scrollbar {
  display: none;
}

.example-chip {
  flex: 0 0 auto;
  border: 1px solid var(--color-primary-border);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border-radius: 999px;
  padding: 7px 11px;
  font-size: 11px;
  line-height: 1.2;
}

.example-chip:active {
  opacity: 0.8;
}
</style>
