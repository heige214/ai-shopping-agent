<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'

import {
  cancelOrder,
  confirmOrder,
  fetchOrders,
  payOrder,
} from '@/api/commerce'
import ProductImage from '@/components/catalog/ProductImage.vue'
import type { Order, OrderStatus } from '@/types/commerce'
import {
  ORDER_STATUS_LABEL,
  ORDER_STATUS_TAG,
  formatDateTime,
} from '@/utils/commerce'
import { getErrorMessage } from '@/utils/error'
import { formatPrice } from '@/utils/format'

type TabName = 'all' | 'pending_payment' | 'paid' | 'shipped' | 'completed'

const route = useRoute()
const router = useRouter()

const tabs: Array<{ name: TabName; title: string }> = [
  { name: 'all', title: '全部' },
  { name: 'pending_payment', title: '待付款' },
  { name: 'paid', title: '待发货' },
  { name: 'shipped', title: '待收货' },
  { name: 'completed', title: '已完成' },
]

const validTabs = new Set<string>(tabs.map((tab) => tab.name))
const active = ref<TabName>('all')
const orders = ref<Order[]>([])
const loading = ref(false)
const actingId = ref<number | null>(null)

function goBack(): void {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.replace('/me')
  }
}

function goDetail(order: Order): void {
  router.push(`/orders/${order.id}`)
}

async function loadOrders(): Promise<void> {
  loading.value = true
  try {
    orders.value = await fetchOrders(
      active.value === 'all'
        ? undefined
        : (active.value as OrderStatus),
    )
  } catch (error) {
    showToast(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function handleTabChange(): void {
  router.replace({
    path: '/orders',
    query: active.value === 'all' ? {} : { status: active.value },
  })
  void loadOrders()
}

async function pay(order: Order): Promise<void> {
  if (actingId.value !== null) {
    return
  }
  actingId.value = order.id
  try {
    await payOrder(order.id)
    showToast('支付成功')
    await loadOrders()
  } catch (error) {
    showToast(getErrorMessage(error))
  } finally {
    actingId.value = null
  }
}

async function cancel(order: Order): Promise<void> {
  try {
    await showConfirmDialog({
      title: '取消订单',
      message: '确定取消这笔订单吗？库存将恢复。',
    })
  } catch {
    return
  }
  actingId.value = order.id
  try {
    await cancelOrder(order.id)
    showToast('订单已取消')
    await loadOrders()
  } catch (error) {
    showToast(getErrorMessage(error))
  } finally {
    actingId.value = null
  }
}

async function confirmReceipt(order: Order): Promise<void> {
  try {
    await showConfirmDialog({
      title: '确认收货',
      message: '确认已经收到商品吗？',
    })
  } catch {
    return
  }
  actingId.value = order.id
  try {
    await confirmOrder(order.id)
    showToast('已确认收货')
    await loadOrders()
  } catch (error) {
    showToast(getErrorMessage(error))
  } finally {
    actingId.value = null
  }
}

onMounted(async () => {
  const queryStatus = route.query.status
  if (typeof queryStatus === 'string' && validTabs.has(queryStatus)) {
    active.value = queryStatus as TabName
  }
  await loadOrders()
})
</script>

<template>
  <div class="page orders-page">
    <header class="page-header">
      <button type="button" class="icon-button" aria-label="返回" @click="goBack">
        <van-icon name="arrow-left" size="18" />
      </button>
      <span class="header-title">我的订单</span>
      <span class="header-spacer" />
    </header>

    <van-tabs
      v-model:active="active"
      class="order-tabs"
      sticky
      @change="handleTabChange"
    >
      <van-tab
        v-for="tab in tabs"
        :key="tab.name"
        :name="tab.name"
        :title="tab.title"
      />
    </van-tabs>

    <div v-if="loading && !orders.length" class="state-panel">
      <van-loading size="22">加载中...</van-loading>
    </div>

    <div v-else-if="orders.length" class="order-list">
      <article
        v-for="order in orders"
        :key="order.id"
        class="order-card"
        :data-order-no="order.order_no"
        @click="goDetail(order)"
      >
        <div class="order-head">
          <span class="order-no">{{ order.order_no }}</span>
          <van-tag :type="ORDER_STATUS_TAG[order.status]" plain>
            {{ ORDER_STATUS_LABEL[order.status] }}
          </van-tag>
        </div>

        <div class="order-goods">
          <div v-for="item in order.items" :key="item.id" class="order-goods-row">
            <div class="order-goods-image">
              <ProductImage :src="item.image" :alt="item.title" />
            </div>
            <div class="order-goods-info">
              <div class="order-goods-title">{{ item.title }}</div>
              <div class="order-goods-spec">
                {{ item.color }} / {{ item.size }} ×{{ item.quantity }}
              </div>
            </div>
            <span class="order-goods-price">
              ¥{{ formatPrice(item.price) }}
            </span>
          </div>
        </div>

        <div class="order-time">
          下单时间 {{ formatDateTime(order.created_at) }}
        </div>

        <div class="order-foot">
          <span>
            实付
            <strong>¥{{ formatPrice(order.total_amount) }}</strong>
          </span>
          <div class="order-actions" @click.stop>
            <template v-if="order.status === 'pending_payment'">
              <van-button
                size="small"
                plain
                class="order-button"
                :disabled="actingId === order.id"
                @click="cancel(order)"
              >
                取消订单
              </van-button>
              <van-button
                size="small"
                type="primary"
                class="order-button"
                :loading="actingId === order.id"
                @click="pay(order)"
              >
                去支付
              </van-button>
            </template>
            <van-button
              v-else-if="order.status === 'shipped'"
              size="small"
              type="primary"
              class="order-button"
              :loading="actingId === order.id"
              @click="confirmReceipt(order)"
            >
              确认收货
            </van-button>
            <van-button
              v-else
              size="small"
              plain
              class="order-button"
              @click="goDetail(order)"
            >
              查看详情
            </van-button>
          </div>
        </div>
      </article>
    </div>

    <van-empty v-else description="暂无订单" />
  </div>
</template>

<style scoped>
.orders-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: var(--color-bg);
  padding-bottom: 20px;
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

.order-tabs {
  --van-tabs-line-height: 40px;
}

.state-panel {
  padding: 80px 0;
  display: flex;
  justify-content: center;
}

.order-list {
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.order-card {
  background: var(--color-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: 12px;
}

.order-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-bottom: 9px;
  border-bottom: 1px solid var(--color-border);
}

.order-no {
  font-size: 10.5px;
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.order-goods {
  padding: 10px 0 4px;
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.order-goods-row {
  display: flex;
  align-items: center;
  gap: 9px;
}

.order-goods-image {
  width: 50px;
  flex: 0 0 50px;
  border-radius: 8px;
  overflow: hidden;
}

.order-goods-info {
  flex: 1;
  min-width: 0;
}

.order-goods-title {
  font-size: 11.5px;
  font-weight: 600;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.order-goods-spec {
  margin-top: 3px;
  font-size: 9.5px;
  color: var(--color-text-secondary);
}

.order-goods-price {
  font-size: 11px;
  color: var(--color-text-secondary);
}

.order-time {
  font-size: 9.5px;
  color: var(--color-text-tertiary);
  padding: 4px 0 9px;
}

.order-foot {
  border-top: 1px solid var(--color-border);
  padding-top: 9px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.order-foot > span {
  font-size: 10.5px;
  color: var(--color-text-secondary);
}

.order-foot strong {
  color: var(--color-price);
  font-size: 15px;
  margin-left: 3px;
}

.order-actions {
  display: flex;
  gap: 7px;
}

.order-button {
  height: 30px;
  border-radius: 999px;
  font-size: 11px;
  padding: 0 12px;
}
</style>
