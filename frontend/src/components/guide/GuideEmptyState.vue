<script setup lang="ts">
import ProductCard from '@/components/catalog/ProductCard.vue'
import type { Category, ProductSummary } from '@/types/catalog'

defineProps<{
  userName: string
  profileSummary: string
  profileComplete: boolean
  examples: string[]
  categories: Category[]
  products: ProductSummary[]
  loading: boolean
}>()

const emit = defineEmits<{
  (event: 'example', text: string): void
  (event: 'category', category: Category): void
}>()
</script>

<template>
  <section class="guide-empty">
    <section class="greeting-card">
      <div class="greeting-avatar" aria-hidden="true">AI</div>
      <div class="greeting-text">
        <h2>你好，{{ userName }}</h2>
        <p>说出你想找的，AI 帮你挑合适的款。</p>
        <div class="profile-hint">
          <span>{{ profileSummary }}</span>
          <router-link v-if="!profileComplete" to="/me" class="profile-link">
            去完善
          </router-link>
        </div>
      </div>
    </section>

    <div class="section-head">
      <h2>试试这样问</h2>
      <span class="section-sub">点一下直接发送</span>
    </div>
    <div class="example-chips">
      <button
        v-for="example in examples"
        :key="example"
        type="button"
        class="guide-example-chip"
        @click="emit('example', example)"
      >
        {{ example }}
      </button>
    </div>

    <div class="section-head">
      <h2>按品类逛逛</h2>
      <span class="section-sub">点一下直接找</span>
    </div>
    <div class="category-grid">
      <button
        v-for="category in categories"
        :key="category.id"
        type="button"
        class="guide-category-tile"
        @click="emit('category', category)"
      >
        <span class="category-icon">{{ category.name.slice(0, 1) }}</span>
        <span class="category-name">{{ category.name }}</span>
      </button>
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
.guide-empty {
  display: flex;
  flex-direction: column;
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

.greeting-text {
  min-width: 0;
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

.profile-hint {
  margin-top: 7px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 9.5px;
  color: var(--color-text-secondary);
}

.profile-link {
  color: var(--color-primary);
  text-decoration: none;
  font-weight: 600;
}

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin: 16px 2px 8px;
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

.example-chips {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 2px 0;
  scrollbar-width: none;
}

.example-chips::-webkit-scrollbar {
  display: none;
}

.guide-example-chip {
  flex: 0 0 auto;
  border: 1px solid var(--color-primary-border);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border-radius: 999px;
  padding: 7px 11px;
  font-size: 11px;
  line-height: 1.2;
}

.guide-example-chip:active {
  opacity: 0.8;
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.guide-category-tile {
  border: 0;
  background: var(--color-card);
  border-radius: 12px;
  box-shadow: var(--shadow-card);
  padding: 12px 4px 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  color: inherit;
}

.guide-category-tile:active {
  opacity: 0.8;
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
