<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'

import {
  cancelOrder,
  confirmOrder,
  fetchOrder,
  payOrder,
} from '@/api/commerce'
import ProductImage from '@/components/catalog/ProductImage.vue'
import type { Order, OrderStatus } from '@/types/commerce'
import {
  ORDER_STATUS_LABEL,
  ORDER_STATUS_TAG,
  formatDateTime,
  formatFullAddress,
} from '@/utils/commerce'
import { getErrorMessage } from '@/utils/error'
import { formatPrice } from '@/utils/format'

const STATUS_HINT: Record<OrderStatus, string> = {
  pending_payment: '请尽快完成支付，超时订单将自动取消',
  paid: '支付成功，等待客服发货',
  shipped: '商品已发出，收到后请确认收货',
  completed: '订单已完成，感谢你的购买',
  cancelled: '订单已取消，库存已恢复',
}

const route = useRoute()
const router = useRouter()

const order = ref<Order | null>(null)
const loading = ref(true)
const acting = ref(false)

const orderId = computed(() => Number(route.params.id))

const timeline = computed(() => {
  const current = order.value
  if (!current) {
    return []
  }
  return [
    { label: '提交订单', time: current.created_at },
    { label: '完成支付', time: current.paid_at },
    { label: '客服发货', time: current.shipped_at },
    { label: '确认收货', time: current.completed_at },
    { label: '取消订单', time: current.cancelled_at },
  ].filter((item) => Boolean(item.time))
})

function goBack(): void {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.replace('/orders')
  }
}

async function loadOrder(): Promise<void> {
  loading.value = true
  try {
    order.value = await fetchOrder(orderId.value)
  } catch (error) {
    showToast(getErrorMessage(error))
    await router.replace('/orders')
  } finally {
    loading.value = false
  }
}

async function pay(): Promise<void> {
  if (!order.value || acting.value) {
    return
  }
  acting.value = true
  try {
    order.value = await payOrder(order.value.id)
    showToast('支付成功')
  } catch (error) {
    showToast(getErrorMessage(error))
    await loadOrder()
  } finally {
    acting.value = false
  }
}

async function cancel(): Promise<void> {
  if (!order.value || acting.value) {
    return
  }
  try {
    await showConfirmDialog({
      title: '取消订单',
      message: '确定取消这笔订单吗？库存将恢复。',
    })
  } catch {
    return
  }
  acting.value = true
  try {
    order.value = await cancelOrder(order.value.id)
    showToast('订单已取消')
  } catch (error) {
    showToast(getErrorMessage(error))
    await loadOrder()
  } finally {
    acting.value = false
  }
}

async function confirmReceipt(): Promise<void> {
  if (!order.value || acting.value) {
    return
  }
  try {
    await showConfirmDialog({
      title: '确认收货',
      message: '确认已经收到商品吗？',
    })
  } catch {
    return
  }
  acting.value = true
  try {
    order.value = await confirmOrder(order.value.id)
    showToast('已确认收货')
  } catch (error) {
    showToast(getErrorMessage(error))
    await loadOrder()
  } finally {
    acting.value = false
  }
}

onMounted(() => {
  if (!Number.isInteger(orderId.value) || orderId.value <= 0) {
    void router.replace('/orders')
    return
  }
  void loadOrder()
})
</script>

<template>
  <div class="page order-detail-page">
    <header class="page-header">
      <button type="button" class="icon-button" aria-label="返回" @click="goBack">
        <van-icon name="arrow-left" size="18" />
      </button>
      <span class="header-title">订单详情</span>
      <span class="header-spacer" />
    </header>

    <div v-if="loading" class="state-panel">
      <van-loading size="22">加载中...</van-loading>
    </div>

    <template v-else-if="order">
      <section class="status-panel">
        <div class="status-line">
          <h2>{{ ORDER_STATUS_LABEL[order.status] }}</h2>
          <van-tag :type="ORDER_STATUS_TAG[order.status]" plain>
            订单状态
          </van-tag>
        </div>
        <p>{{ STATUS_HINT[order.status] }}</p>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>收货信息</h2>
        </div>
        <div class="receiver-line">
          <span>{{ order.address_snapshot.receiver_name }}</span>
          <span class="receiver-phone">{{ order.address_snapshot.phone }}</span>
        </div>
        <div class="receiver-address">
          {{ formatFullAddress(order.address_snapshot) }}
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>商品清单</h2>
          <span class="panel-sub">共 {{ order.items.length }} 种</span>
        </div>
        <div class="goods-list">
          <div v-for="item in order.items" :key="item.id" class="goods-row">
            <div class="goods-image">
              <ProductImage :src="item.image" :alt="item.title" />
            </div>
            <div class="goods-info">
              <div class="goods-title">{{ item.title }}</div>
              <div class="goods-spec">
                {{ item.color }} / {{ item.size }} ×{{ item.quantity }}
              </div>
            </div>
            <span class="goods-price">
              ¥{{ formatPrice(item.price) }}
            </span>
          </div>
        </div>
      </section>

      <section class="panel amount-panel">
        <div class="amount-row">
          <span>商品金额</span>
          <span>¥{{ formatPrice(order.total_amount) }}</span>
        </div>
        <div class="amount-row">
          <span>运费</span>
          <span>¥0.00</span>
        </div>
        <div class="amount-row total">
          <span>实付金额</span>
          <strong>¥{{ formatPrice(order.total_amount) }}</strong>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>订单信息</h2>
        </div>
        <div class="info-row">
          <span>订单编号</span>
          <span class="order-no">{{ order.order_no }}</span>
        </div>
        <div class="info-row">
          <span>支付方式</span>
          <span>模拟支付</span>
        </div>
        <div v-if="order.payment_no" class="info-row">
          <span>支付流水</span>
          <span>{{ order.payment_no }}</span>
        </div>
        <div class="info-row">
          <span>下单时间</span>
          <span>{{ formatDateTime(order.created_at) }}</span>
        </div>
      </section>

      <section v-if="timeline.length" class="panel">
        <div class="panel-head">
          <h2>订单时间线</h2>
        </div>
        <div class="timeline">
          <div
            v-for="event in timeline"
            :key="event.label"
            class="timeline-item"
          >
            <span class="timeline-dot" />
            <span class="timeline-label">{{ event.label }}</span>
            <span class="timeline-time">
              {{ formatDateTime(event.time) }}
            </span>
          </div>
        </div>
      </section>
    </template>

    <footer
      v-if="
        order &&
        (order.status === 'pending_payment' || order.status === 'shipped')
      "
      class="detail-footer"
    >
      <template v-if="order.status === 'pending_payment'">
        <van-button
          plain
          class="footer-button"
          :disabled="acting"
          @click="cancel"
        >
          取消订单
        </van-button>
        <van-button
          type="primary"
          class="footer-button primary"
          :loading="acting"
          @click="pay"
        >
          模拟支付
        </van-button>
      </template>
      <van-button
        v-else
        type="primary"
        class="footer-button primary full"
        :loading="acting"
        @click="confirmReceipt"
      >
        确认收货
      </van-button>
    </footer>
  </div>
</template>

<style scoped>
.order-detail-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: var(--color-bg);
  padding-bottom: 80px;
  padding-bottom: calc(80px + env(safe-area-inset-bottom));
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

.status-panel {
  background: linear-gradient(135deg, #fff4ec, #ffe6d8);
  margin: 12px 14px 0;
  border-radius: var(--radius-card);
  padding: 16px 14px;
}

.status-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.status-line h2 {
  margin: 0;
  font-size: 19px;
  color: var(--color-text);
}

.status-panel p {
  margin: 6px 0 0;
  font-size: 11px;
  color: var(--color-text-secondary);
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
  margin-bottom: 9px;
}

.panel-head h2 {
  margin: 0;
  font-size: 13px;
}

.panel-sub {
  font-size: 10px;
  color: var(--color-text-secondary);
}

.receiver-line {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  font-weight: 600;
}

.receiver-phone {
  font-weight: 400;
  color: var(--color-text-secondary);
}

.receiver-address {
  margin-top: 5px;
  font-size: 10.5px;
  line-height: 1.5;
  color: var(--color-text-secondary);
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
  width: 54px;
  flex: 0 0 54px;
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
  font-size: 12px;
  color: var(--color-price);
  font-weight: 600;
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

.info-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
  font-size: 11px;
  color: var(--color-text-secondary);
}

.info-row span:last-child {
  color: var(--color-text);
  text-align: right;
  word-break: break-all;
}

.order-no {
  font-size: 10.5px;
}

.timeline {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.timeline-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
}

.timeline-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--color-primary);
  flex: 0 0 auto;
}

.timeline-label {
  color: var(--color-text);
}

.timeline-time {
  margin-left: auto;
  font-size: 10px;
  color: var(--color-text-secondary);
}

.detail-footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--color-card);
  border-top: 1px solid var(--color-border);
  padding: 10px 14px;
  padding-bottom: calc(10px + env(safe-area-inset-bottom));
  display: flex;
  gap: 10px;
  z-index: 20;
}

.footer-button {
  flex: 1;
  height: 40px;
  border-radius: 999px;
  font-size: 13px;
}

.footer-button.primary {
  font-weight: 700;
}

.footer-button.full {
  flex: 1;
}
</style>
