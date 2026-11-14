<script setup lang="ts">
import { computed } from 'vue'

import ProductImage from '@/components/catalog/ProductImage.vue'
import type { GuideProductCard } from '@/types/guide'
import { formatAttributeValue, formatPrice } from '@/utils/format'

const props = defineProps<{
  card: GuideProductCard
}>()

const tags = computed(() =>
  ['color', 'material', 'thickness']
    .map((key) => formatAttributeValue(props.card.attributes[key]))
    .filter((value) => value.length > 0)
    .slice(0, 3),
)
</script>

<template>
  <router-link
    :to="{ name: 'product-detail', params: { id: card.id } }"
    class="guide-product-card"
  >
    <div class="guide-card-image">
      <ProductImage :src="card.main_image" :alt="card.title" />
    </div>
    <div class="guide-card-body">
      <div class="guide-card-title">{{ card.title }}</div>
      <div v-if="tags.length" class="guide-card-tags">
        <span v-for="tag in tags" :key="tag">{{ tag }}</span>
      </div>
      <div class="guide-card-price">
        <small>¥</small>{{ formatPrice(card.price) }}
      </div>
      <div v-if="card.recommended_size" class="guide-size">
        <span class="guide-size-badge">推荐 {{ card.recommended_size }} 码</span>
        <span v-if="card.size_reason" class="guide-size-reason">
          {{ card.size_reason }}
        </span>
      </div>
      <div v-if="card.reason" class="guide-card-reason">{{ card.reason }}</div>
    </div>
  </router-link>
</template>

<style scoped>
.guide-product-card {
  display: flex;
  flex-direction: column;
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  overflow: hidden;
  color: inherit;
  text-decoration: none;
}

.guide-card-image {
  width: 100%;
}

.guide-card-body {
  padding: 7px 8px 9px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.guide-card-title {
  font-size: 11.5px;
  line-height: 1.35;
  font-weight: 600;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  min-height: 31px;
}

.guide-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
}

.guide-card-tags span {
  font-size: 8.5px;
  line-height: 1.4;
  color: var(--color-text-secondary);
  background: var(--color-field-bg);
  border-radius: 5px;
  padding: 1px 4px;
}

.guide-card-price {
  color: var(--color-price);
  font-size: 14px;
  font-weight: 800;
  line-height: 1.2;
}

.guide-card-price small {
  font-size: 9px;
  margin-right: 1px;
}

.guide-size {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.guide-size-badge {
  align-self: flex-start;
  font-size: 9px;
  font-weight: 700;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border: 1px solid var(--color-primary-border);
  border-radius: 6px;
  padding: 1px 5px;
}

.guide-size-reason {
  font-size: 8.5px;
  line-height: 1.35;
  color: var(--color-text-secondary);
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

.guide-card-reason {
  font-size: 9px;
  line-height: 1.35;
  color: var(--color-text-secondary);
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}
</style>
