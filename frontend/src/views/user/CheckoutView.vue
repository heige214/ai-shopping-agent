<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'

import { createOrder, fetchAddresses } from '@/api/commerce'
import ProductImage from '@/components/catalog/ProductImage.vue'
import AddressFormPopup from '@/components/commerce/AddressFormPopup.vue'
import { useCartStore } from '@/stores/cart'
import type { Address } from '@/types/commerce'
import { formatFullAddress } from '@/utils/commerce'
import { getErrorMessage } from '@/utils/error'
import { formatPrice } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const cart = useCartStore()

const addresses = ref<Address[]>([])
const addressId = ref<number | null>(null)
const showAddressForm = ref(false)
const loading = ref(true)
const submitting = ref(false)

const requestedIds = computed(() => {
  const raw = route.query.items
  if (typeof raw !== 'string' || !raw) {
    return []
  }
  return raw
    .split(',')
    .map((value) => Number(value))
    .filter((value) => Number.isInteger(value) && value > 0)
})

const checkoutItems = computed(() =>
  requestedIds.value.length
    ? cart.data.items.filter((item) => requestedIds.value.includes(item.id))
    : cart.data.items.filter((item) => item.selected),
)

const totalAmount = computed(() => {
  const amount = checkoutItems.value.reduce(
    (sum, item) => sum + item.price * item.quantity,
    0,
  )
  return Math.round(amount * 100) / 100
})

function goBack(): void {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.replace('/cart')
  }
}

async function loadAddresses(): Promise<void> {
  addresses.value = await fetchAddresses()
  if (
    addressId.value === null ||
    !addresses.value.some((item) => item.id === addressId.value)
  ) {
    addressId.value =
      addresses.value.find((item) => item.is_default)?.id ??
      addresses.value[0]?.id ??
      null
  }
}

function handleAddressSaved(address: Address): void {
  showAddressForm.value = false
  void loadAddresses()
    .then(() => {
      addressId.value = address.id
    })
    .catch((error) => showToast(getErrorMessage(error)))
}

async function submitOrder(): Promise<void> {
  if (submitting.value) {
    return
  }
  if (!checkoutItems.value.length) {
    showToast('请选择要结算的商品')
    return
  }
  if (!addressId.value) {
    showToast('请选择收货地址')
    return
  }

  submitting.value = true
  try {
    const order = await createOrder({
      address_id: addressId.value,
      cart_item_ids: checkoutItems.value.map((item) => item.id),
    })
    await cart.load(true).catch(() => undefined)
    showToast('下单成功')
    await router.replace(`/orders/${order.id}`)
  } catch (error) {
    showToast(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    await Promise.all([cart.load(true), loadAddresses()])
    if (
      requestedIds.value.length &&
      checkoutItems.value.length !== requestedIds.value.length
    ) {
      showToast('部分商品已失效，请重新选择')
      await router.replace('/cart')
    }
  } catch (error) {
    showToast(getErrorMessage(error))
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page checkout-page">
    <header class="page-header">
      <button type="button" class="icon-button" aria-label="返回" @click="goBack">
        <van-icon name="arrow-left" size="18" />
      </button>
      <span class="header-title">确认订单</span>
      <span class="header-spacer" />
    </header>

    <div v-if="loading" class="state-panel">
      <van-loading size="22">加载中...</van-loading>
    </div>

    <template v-else>
      <section class="panel">
        <div class="panel-head">
          <h2>收货地址</h2>
          <button
            type="button"
            class="text-button"
            @click="showAddressForm = true"
          >
            新增地址
          </button>
        </div>

        <van-radio-group v-if="addresses.length" v-model="addressId">
          <label
            v-for="address in addresses"
            :key="address.id"
            class="address-row"
          >
            <van-radio :name="address.id" />
            <div class="address-body">
              <div class="address-person">
                <span>{{ address.receiver_name }}</span>
                <span class="address-phone">{{ address.phone }}</span>
                <van-tag v-if="address.is_default" type="primary">
                  默认
                </van-tag>
              </div>
              <div class="address-detail">{{ formatFullAddress(address) }}</div>
            </div>
          </label>
        </van-radio-group>
        <button
          v-else
          type="button"
          class="empty-address"
          @click="showAddressForm = true"
        >
          <van-icon name="add-o" size="18" />
          <span>还没有收货地址，点击新增</span>
        </button>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>商品清单</h2>
          <span class="panel-sub">共 {{ checkoutItems.length }} 种</span>
        </div>
        <div class="goods-list">
          <div
            v-for="item in checkoutItems"
            :key="item.id"
            class="goods-row"
          >
            <div class="goods-image">
              <ProductImage :src="item.main_image" :alt="item.title" />
            </div>
            <div class="goods-info">
              <div class="goods-title">{{ item.title }}</div>
              <div class="goods-spec">{{ item.color }} / {{ item.size }}</div>
            </div>
            <div class="goods-price">
              <span>¥{{ formatPrice(item.price) }}</span>
              <small>×{{ item.quantity }}</small>
            </div>
          </div>
        </div>
      </section>

      <section class="panel amount-panel">
        <div class="amount-row">
          <span>商品金额</span>
          <span>¥{{ formatPrice(totalAmount) }}</span>
        </div>
        <div class="amount-row">
          <span>运费</span>
          <span>¥0.00</span>
        </div>
        <div class="amount-row total">
          <span>应付合计</span>
          <strong>¥{{ formatPrice(totalAmount) }}</strong>
        </div>
      </section>

      <section class="panel pay-panel">
        <div>
          <h2>模拟支付</h2>
          <p>演示环境，不产生真实扣款</p>
        </div>
        <van-tag type="success" plain>模拟</van-tag>
      </section>

      <footer class="checkout-footer">
        <div class="footer-total">
          合计
          <strong>¥{{ formatPrice(totalAmount) }}</strong>
        </div>
        <van-button
          type="primary"
          class="submit-button"
          :loading="submitting"
          :disabled="!checkoutItems.length"
          @click="submitOrder"
        >
          提交订单
        </van-button>
      </footer>
    </template>

    <AddressFormPopup
      v-model:show="showAddressForm"
      @saved="handleAddressSaved"
    />
  </div>
</template>

<style scoped>
.checkout-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: var(--color-bg);
  padding-bottom: 84px;
  padding-bottom: calc(84px + env(safe-area-inset-bottom));
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

.panel {
  background: var(--color-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  margin: 12px 14px 0;
  padding: 14px;
}

.panel-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 10px;
}

.panel-head h2,
.pay-panel h2 {
  margin: 0;
  font-size: 13px;
}

.panel-sub {
  font-size: 10px;
  color: var(--color-text-secondary);
}

.text-button {
  border: 0;
  background: transparent;
  color: var(--color-primary);
  font-size: 11px;
  padding: 4px 0;
}

.address-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 0;
  border-top: 1px solid var(--color-border);
}

.address-row:first-child {
  border-top: 0;
}

.address-row :deep(.van-radio) {
  flex: 0 0 auto;
  margin-top: 2px;
}

.address-body {
  flex: 1;
  min-width: 0;
}

.address-person {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  font-weight: 600;
}

.address-phone {
  font-weight: 400;
  color: var(--color-text-secondary);
}

.address-detail {
  margin-top: 4px;
  font-size: 10.5px;
  line-height: 1.45;
  color: var(--color-text-secondary);
}

.empty-address {
  width: 100%;
  border: 1px dashed var(--color-primary-border);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border-radius: 10px;
  padding: 16px 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 12px;
}

.goods-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.goods-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.goods-image {
  width: 56px;
  flex: 0 0 56px;
  border-radius: 8px;
  overflow: hidden;
}

.goods-info {
  flex: 1;
  min-width: 0;
}

.goods-title {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

.goods-spec {
  margin-top: 4px;
  font-size: 10px;
  color: var(--color-text-secondary);
}

.goods-price {
  text-align: right;
  font-size: 12px;
  color: var(--color-price);
  font-weight: 600;
}

.goods-price small {
  display: block;
  margin-top: 4px;
  color: var(--color-text-secondary);
  font-weight: 400;
}

.amount-panel {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.amount-row {
  display: flex;
  justify-content: space-between;
  font-size: 11.5px;
  color: var(--color-text-secondary);
}

.amount-row.total {
  padding-top: 8px;
  border-top: 1px solid var(--color-border);
  color: var(--color-text);
  font-weight: 600;
}

.amount-row.total strong {
  color: var(--color-price);
  font-size: 16px;
}

.pay-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.pay-panel p {
  margin: 4px 0 0;
  font-size: 10px;
  color: var(--color-text-secondary);
}

.checkout-footer {
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
  justify-content: space-between;
  gap: 12px;
  z-index: 20;
}

.footer-total {
  font-size: 11px;
  color: var(--color-text-secondary);
}

.footer-total strong {
  color: var(--color-price);
  font-size: 18px;
  margin-left: 4px;
}

.submit-button {
  width: 128px;
  height: 40px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
}
</style>
