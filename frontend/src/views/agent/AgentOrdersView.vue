<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'

import {
  fetchAgentOrders,
  shipOrder,
  type AgentOrderFilter,
} from '@/api/commerce'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'
import type { AgentOrder } from '@/types/commerce'
import {
  ORDER_STATUS_LABEL,
  ORDER_STATUS_TAG,
  formatDateTime,
} from '@/utils/commerce'
import { getErrorMessage } from '@/utils/error'
import { formatPrice } from '@/utils/format'

const router = useRouter()
const auth = useAuthStore()
const cart = useCartStore()

const tabs: Array<{ name: AgentOrderFilter; title: string }> = [
  { name: 'paid', title: '待发货' },
  { name: 'shipped', title: '已发货' },
  { name: 'all', title: '全部订单' },
]

const active = ref<AgentOrderFilter>('paid')
const orders = ref<AgentOrder[]>([])
const loading = ref(false)
const shippingId = ref<number | null>(null)

const agentName = computed(
  () => auth.user?.nickname || auth.user?.username || '客服',
)

function itemSummary(order: AgentOrder): string {
  return order.items
    .map((item) => `${item.title}（${item.color}/${item.size}）×${item.quantity}`)
    .join('；')
}

function buyerName(order: AgentOrder): string {
  return order.buyer_nickname || order.buyer_username
}

async function loadOrders(): Promise<void> {
  loading.value = true
  try {
    orders.value = await fetchAgentOrders(active.value)
  } catch (error) {
    showToast(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function handleTabChange(): void {
  void loadOrders()
}

async function ship(order: AgentOrder): Promise<void> {
  try {
    await showConfirmDialog({
      title: '模拟发货',
      message: `确认对订单 ${order.order_no} 执行模拟发货吗？`,
    })
  } catch {
    return
  }
  shippingId.value = order.id
  try {
    await shipOrder(order.id)
    showToast('已发货')
    await loadOrders()
  } catch (error) {
    showToast(getErrorMessage(error))
  } finally {
    shippingId.value = null
  }
}

async function logout(): Promise<void> {
  cart.clear()
  auth.logout()
  await router.replace('/login')
}

onMounted(loadOrders)
</script>

<template>
  <div class="agent-page">
    <header class="agent-header">
      <div class="agent-brand">
        <span class="brand-logo">AI</span>
        <div>
          <h1>客服工作台</h1>
          <p>订单发货管理</p>
        </div>
      </div>
      <div class="agent-user">
        <span class="agent-role">客服</span>
        <span class="agent-name">{{ agentName }}</span>
        <button type="button" class="logout-button" @click="logout">
          退出登录
        </button>
      </div>
    </header>

    <main class="agent-main">
      <div class="page-title-row">
        <div>
          <h2>订单管理</h2>
          <p>仅展示模拟支付成功的订单，发货为演示操作。</p>
        </div>
        <span class="order-count">共 {{ orders.length }} 笔</span>
      </div>

      <div class="filter-tabs">
        <button
          v-for="tab in tabs"
          :key="tab.name"
          type="button"
          class="filter-tab"
          :class="{ active: active === tab.name }"
          @click="
            active = tab.name;
            handleTabChange()
          "
        >
          {{ tab.title }}
        </button>
      </div>

      <div v-if="loading && !orders.length" class="state-panel">
        <van-loading size="22">加载中...</van-loading>
      </div>

      <div v-else-if="orders.length" class="table-wrap">
        <table class="order-table">
          <thead>
            <tr>
              <th>订单号</th>
              <th>买家</th>
              <th>商品</th>
              <th>金额</th>
              <th>支付时间</th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="order in orders"
              :key="order.id"
              :data-order-no="order.order_no"
            >
              <td class="order-no">{{ order.order_no }}</td>
              <td>
                <div class="buyer-name">{{ buyerName(order) }}</div>
                <div class="buyer-username">@{{ order.buyer_username }}</div>
              </td>
              <td class="goods-cell">{{ itemSummary(order) }}</td>
              <td class="amount">¥{{ formatPrice(order.total_amount) }}</td>
              <td>{{ formatDateTime(order.paid_at) }}</td>
              <td>
                <van-tag :type="ORDER_STATUS_TAG[order.status]" plain>
                  {{ ORDER_STATUS_LABEL[order.status] }}
                </van-tag>
              </td>
              <td>
                <van-button
                  v-if="order.status === 'paid'"
                  size="small"
                  type="primary"
                  class="ship-button"
                  :loading="shippingId === order.id"
                  @click="ship(order)"
                >
                  模拟发货
                </van-button>
                <span v-else class="muted">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <van-empty v-else description="暂无订单" />
    </main>
  </div>
</template>

<style scoped>
.agent-page {
  min-height: 100vh;
  background: #f3f5f8;
}

.agent-header {
  height: 64px;
  background: #ffffff;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  position: sticky;
  top: 0;
  z-index: 10;
}

.agent-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-logo {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--color-primary-gradient);
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
}

.agent-brand h1 {
  margin: 0;
  font-size: 16px;
  line-height: 1.2;
}

.agent-brand p {
  margin: 2px 0 0;
  font-size: 10px;
  color: var(--color-text-secondary);
}

.agent-user {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}

.agent-role {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border: 1px solid var(--color-primary-border);
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 10px;
}

.agent-name {
  font-weight: 600;
}

.logout-button {
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-text-secondary);
  border-radius: 8px;
  padding: 7px 12px;
  font-size: 11px;
  cursor: pointer;
}

.agent-main {
  max-width: 1180px;
  margin: 0 auto;
  padding: 28px 24px 48px;
}

.page-title-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-title-row h2 {
  margin: 0;
  font-size: 21px;
}

.page-title-row p {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.order-count {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.filter-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}

.filter-tab {
  border: 1px solid var(--color-border);
  background: #fff;
  color: var(--color-text-secondary);
  border-radius: 999px;
  padding: 7px 16px;
  font-size: 12px;
  cursor: pointer;
}

.filter-tab.active {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  font-weight: 600;
}

.state-panel {
  padding: 70px 0;
  display: flex;
  justify-content: center;
}

.table-wrap {
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 2px 10px rgba(24, 36, 55, 0.05);
  overflow-x: auto;
}

.order-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.order-table th {
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
  background: #f8f9fb;
  padding: 12px 16px;
  white-space: nowrap;
}

.order-table td {
  padding: 14px 16px;
  border-top: 1px solid var(--color-border);
  vertical-align: middle;
}

.order-no {
  font-size: 11px;
  white-space: nowrap;
}

.buyer-name {
  font-weight: 600;
}

.buyer-username {
  margin-top: 2px;
  font-size: 10px;
  color: var(--color-text-secondary);
}

.goods-cell {
  max-width: 320px;
  line-height: 1.5;
}

.amount {
  color: var(--color-price);
  font-weight: 700;
  white-space: nowrap;
}

.ship-button {
  height: 30px;
  border-radius: 999px;
  font-size: 11px;
  padding: 0 14px;
  white-space: nowrap;
}

.muted {
  color: var(--color-text-tertiary);
}

@media (max-width: 720px) {
  .agent-header {
    padding: 0 14px;
  }

  .agent-main {
    padding: 18px 14px 40px;
  }

  .agent-brand p {
    display: none;
  }
}
</style>
