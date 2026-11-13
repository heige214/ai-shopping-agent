<script setup lang="ts">
import { computed } from 'vue'

import { useCartStore } from '@/stores/cart'

const cart = useCartStore()
const count = computed(() => cart.totalQuantity)
</script>

<template>
  <router-link to="/cart" class="cart-badge" aria-label="购物车">
    <van-badge
      :content="count"
      :max="99"
      :show="count > 0"
      color="#FF5A1F"
    >
      <van-icon name="cart-o" size="19" />
    </van-badge>
  </router-link>
</template>

<style scoped>
.cart-badge {
  width: 44px;
  height: 44px;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text);
  text-decoration: none;
}

.cart-badge :deep(.van-badge) {
  border: 0;
}
</style>
