<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

import ProductCard from '@/components/catalog/ProductCard.vue'
import { useFavoritesStore } from '@/stores/favorites'

const router = useRouter()
const favorites = useFavoritesStore()

function goBack(): void {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.replace('/me')
  }
}

onMounted(async () => {
  try {
    await favorites.load(true)
  } catch {
    // 401 由全局拦截器处理；其他错误保持空态
  }
})
</script>

<template>
  <div class="page favorites-page">
    <header class="page-header">
      <button type="button" class="icon-button" aria-label="返回" @click="goBack">
        <van-icon name="arrow-left" size="18" />
      </button>
      <span class="header-title">我的收藏</span>
      <span class="header-spacer" />
    </header>

    <div v-if="favorites.loading && !favorites.items.length" class="state-panel">
      <van-loading size="22">加载中...</van-loading>
    </div>
    <div v-else-if="favorites.items.length" class="favorites-body">
      <div class="product-grid">
        <ProductCard
          v-for="product in favorites.items"
          :key="product.id"
          :product="product"
        />
      </div>
    </div>
    <van-empty v-else description="还没有收藏的商品" />
  </div>
</template>

<style scoped>
.favorites-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: var(--color-bg);
}

.page-header {
  height: 58px;
  background: var(--color-card);
  display: flex;
  align-items: center;
  padding: 0 8px;
  border-bottom: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  z-index: 10;
}

.icon-button {
  width: 44px;
  height: 44px;
  border: 0;
  background: transparent;
  color: var(--color-text);
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-title {
  flex: 1;
  text-align: center;
  font-size: 15px;
  font-weight: 700;
}

.header-spacer {
  width: 44px;
}

.state-panel {
  padding: 80px 0;
  display: flex;
  justify-content: center;
}

.favorites-body {
  padding: 12px 14px 20px;
}

.product-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
</style>
