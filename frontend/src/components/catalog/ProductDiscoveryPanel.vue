<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchProducts } from '@/api/catalog'
import ProductCard from '@/components/catalog/ProductCard.vue'
import { useCatalogStore } from '@/stores/catalog'
import type { ProductSummary } from '@/types/catalog'

const catalog = useCatalogStore()
const products = ref<ProductSummary[]>([])
const loading = ref(true)

const categories = computed(() => catalog.roots.slice(0, 4))

onMounted(async () => {
  try {
    await catalog.load()
    const page = await fetchProducts({ page_size: 8, sort: 'recommended' })
    products.value = page.items
  } catch {
    products.value = []
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section class="discovery-panel">
    <div class="section-head">
      <h2>按品类逛逛</h2>
    </div>
    <div class="category-grid">
      <router-link
        v-for="category in categories"
        :key="category.id"
        :to="{ name: 'category', params: { id: category.id } }"
        class="category-tile"
      >
        <span class="category-icon">{{ category.name.slice(0, 1) }}</span>
        <span class="category-name">{{ category.name }}</span>
      </router-link>
    </div>

    <div class="section-head">
      <h2>大家都在看</h2>
      <span class="section-sub">按热度推荐</span>
    </div>
    <div v-if="loading" class="product-grid">
      <div v-for="index in 4" :key="index" class="product-skeleton" />
    </div>
    <div v-else-if="products.length" class="product-grid">
      <ProductCard
        v-for="product in products"
        :key="product.id"
        :product="product"
      />
    </div>
    <div v-else class="empty-panel">商品即将上架，敬请期待</div>
  </section>
</template>

<style scoped>
.discovery-panel {
  margin-top: 14px;
}

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin: 0 2px 8px;
}

.section-head h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
}

.section-sub {
  font-size: 10px;
  color: var(--color-text-secondary);
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 18px;
}

.category-tile {
  background: var(--color-card);
  border-radius: 12px;
  box-shadow: var(--shadow-card);
  padding: 12px 4px 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  color: inherit;
  text-decoration: none;
}

.category-icon {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: var(--color-primary-soft);
  color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 800;
}

.category-name {
  font-size: 11px;
  font-weight: 600;
}

.product-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.product-skeleton {
  aspect-ratio: 0.72;
  border-radius: var(--radius-card);
  background: linear-gradient(90deg, #f0f1f3, #f7f8fa, #f0f1f3);
}

.empty-panel {
  background: var(--color-card);
  border-radius: var(--radius-card);
  padding: 28px 16px;
  text-align: center;
  font-size: 12px;
  color: var(--color-text-secondary);
}
</style>
