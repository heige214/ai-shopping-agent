<script setup lang="ts">
import ProductImage from '@/components/catalog/ProductImage.vue'
import type { ProductSummary } from '@/types/catalog'
import { formatPrice } from '@/utils/format'

defineProps<{
  product: ProductSummary
}>()
</script>

<template>
  <router-link
    :to="{ name: 'product-detail', params: { id: product.id } }"
    class="product-card"
  >
    <ProductImage :src="product.main_image" :alt="product.title" />
    <div class="product-card-body">
      <div class="product-card-title">{{ product.title }}</div>
      <div class="product-card-meta">
        <span class="product-card-price">
          <small>¥</small>{{ formatPrice(product.price) }}
        </span>
        <span class="product-card-sales">已售 {{ product.sales_count }}</span>
      </div>
    </div>
  </router-link>
</template>

<style scoped>
.product-card {
  display: block;
  background: var(--color-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  overflow: hidden;
  color: inherit;
  text-decoration: none;
}

.product-card-body {
  padding: 8px 9px 10px;
}

.product-card-title {
  font-size: 12px;
  line-height: 1.35;
  font-weight: 600;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  min-height: 32px;
}

.product-card-meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 6px;
  margin-top: 6px;
}

.product-card-price {
  color: var(--color-price);
  font-size: 15px;
  font-weight: 800;
}

.product-card-price small {
  font-size: 9px;
  margin-right: 1px;
}

.product-card-sales {
  font-size: 9px;
  color: var(--color-text-secondary);
  white-space: nowrap;
}
</style>
