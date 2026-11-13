<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'

import ProductImage from '@/components/catalog/ProductImage.vue'
import { useCartStore } from '@/stores/cart'
import type { CartItem } from '@/types/commerce'
import { getErrorMessage } from '@/utils/error'
import { formatPrice } from '@/utils/format'

const router = useRouter()
const cart = useCartStore()

const items = computed(() => cart.data.items)

function goBack(): void {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.replace('/')
  }
}

async function toggleItem(item: CartItem, value: unknown): Promise<void> {
  try {
    await cart.update(item.id, { selected: value === true })
  } catch (error) {
    showToast(getErrorMessage(error))
  }
}

async function changeQuantity(
  item: CartItem,
  value: number | string,
): Promise<void> {
  const quantity = Number(value)
  if (!Number.isInteger(quantity) || quantity < 1 || quantity === item.quantity) {
    return
  }
  try {
    await cart.update(item.id, { quantity })
  } catch (error) {
    showToast(getErrorMessage(error))
    await cart.load(true).catch(() => undefined)
  }
}

async function toggleAll(value: unknown): Promise<void> {
  const target = value === true
  const targets = items.value.filter(
    (item) => item.selected !== target && (target ? item.available : true),
  )
  try {
    for (const item of targets) {
      await cart.update(item.id, { selected: target })
    }
  } catch (error) {
    showToast(getErrorMessage(error))
  }
}

async function removeItem(item: CartItem): Promise<void> {
  try {
    await showConfirmDialog({
      title: '删除商品',
      message: `确定从购物车删除「${item.title}」吗？`,
    })
  } catch {
    return
  }
  try {
    await cart.remove(item.id)
    showToast('已删除')
  } catch (error) {
    showToast(getErrorMessage(error))
  }
}

function checkout(): void {
  if (!cart.data.selected_count) {
    showToast('请选择要结算的商品')
    return
  }
  router.push('/checkout')
}

onMounted(async () => {
  try {
    await cart.load(true)
  } catch (error) {
    showToast(getErrorMessage(error))
  }
})
</script>

<template>
  <div class="page cart-page">
    <header class="page-header">
      <button type="button" class="icon-button" aria-label="返回" @click="goBack">
        <van-icon name="arrow-left" size="18" />
      </button>
      <span class="header-title">
        购物车<template v-if="items.length">（{{ items.length }} 件）</template>
      </span>
      <span class="header-spacer" />
    </header>

    <div v-if="cart.loading && !items.length" class="state-panel">
      <van-loading size="22">加载中...</van-loading>
    </div>

    <template v-else-if="items.length">
      <div class="cart-list">
        <div v-for="item in items" :key="item.id" class="cart-row">
          <van-checkbox
            :model-value="item.selected"
            :disabled="!item.available && !item.selected"
            class="cart-check"
            @update:model-value="toggleItem(item, $event)"
          />
          <router-link :to="`/product/${item.product_id}`" class="cart-image">
            <ProductImage :src="item.main_image" :alt="item.title" />
          </router-link>
          <div class="cart-info">
            <div class="cart-title">{{ item.title }}</div>
            <div class="cart-spec">{{ item.color }} / {{ item.size }}</div>
            <div class="cart-price-row">
              <span class="cart-price">
                <small>¥</small>{{ formatPrice(item.price) }}
              </span>
              <span v-if="!item.available" class="cart-stock-warn">
                库存不足（剩余 {{ item.stock }} 件）
              </span>
            </div>
            <div class="cart-actions">
              <van-stepper
                :model-value="item.quantity"
                :min="1"
                :max="Math.max(item.stock, 1)"
                :disabled="item.stock <= 0"
                integer
                @change="changeQuantity(item, $event)"
              />
              <button
                type="button"
                class="cart-delete"
                aria-label="删除"
                @click="removeItem(item)"
              >
                <van-icon name="delete-o" size="17" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <footer class="cart-footer">
        <van-checkbox
          :model-value="cart.data.all_selected"
          class="select-all"
          @update:model-value="toggleAll"
        >
          全选
        </van-checkbox>
        <div class="cart-total">
          <span>合计</span>
          <strong>¥{{ formatPrice(cart.data.selected_amount) }}</strong>
        </div>
        <van-button
          type="primary"
          class="checkout-button"
          :disabled="!cart.data.selected_count"
          @click="checkout"
        >
          结算 ({{ cart.data.selected_count }})
        </van-button>
      </footer>
    </template>

    <div v-else class="empty-wrap">
      <van-empty description="购物车还是空的">
        <van-button
          round
          type="primary"
          class="empty-button"
          @click="router.push('/')"
        >
          去逛逛
        </van-button>
      </van-empty>
    </div>
  </div>
</template>

<style scoped>
.cart-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: var(--color-bg);
  padding-bottom: 90px;
  padding-bottom: calc(90px + env(safe-area-inset-bottom));
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

.cart-list {
  padding: 12px 14px 6px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cart-row {
  background: var(--color-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: 12px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.cart-check {
  flex: 0 0 auto;
  margin-top: 30px;
}

.cart-image {
  width: 74px;
  flex: 0 0 74px;
  border-radius: 10px;
  overflow: hidden;
}

.cart-info {
  flex: 1;
  min-width: 0;
}

.cart-title {
  font-size: 12.5px;
  font-weight: 600;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

.cart-spec {
  margin-top: 4px;
  font-size: 10.5px;
  color: var(--color-text-secondary);
}

.cart-price-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-top: 6px;
}

.cart-price {
  color: var(--color-price);
  font-size: 15px;
  font-weight: 800;
}

.cart-price small {
  font-size: 9px;
  margin-right: 1px;
}

.cart-stock-warn {
  font-size: 9.5px;
  color: var(--color-price);
}

.cart-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.cart-actions :deep(.van-stepper__input) {
  height: 26px;
  font-size: 12px;
}

.cart-actions :deep(.van-stepper__minus),
.cart-actions :deep(.van-stepper__plus) {
  width: 26px;
  height: 26px;
}

.cart-delete {
  width: 32px;
  height: 32px;
  border: 0;
  background: transparent;
  color: var(--color-text-secondary);
}

.cart-footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--color-card);
  border-top: 1px solid var(--color-border);
  padding: 10px 14px;
  padding-bottom: calc(10px + env(safe-area-inset-bottom));
  display: flex;
  align-items: center;
  gap: 10px;
  z-index: 20;
}

.select-all {
  flex: 0 0 auto;
  font-size: 12px;
}

.cart-total {
  flex: 1;
  text-align: right;
  font-size: 11px;
  color: var(--color-text-secondary);
}

.cart-total strong {
  color: var(--color-price);
  font-size: 17px;
  margin-left: 3px;
}

.checkout-button {
  width: 108px;
  height: 38px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
}

.empty-wrap {
  padding-top: 70px;
}

.empty-button {
  width: 120px;
  height: 38px;
  font-size: 13px;
}
</style>
