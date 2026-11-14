<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { showToast } from 'vant'

import {
  cancelChatAction,
  confirmChatAction,
} from '@/api/guide'
import ProductImage from '@/components/catalog/ProductImage.vue'
import { useCartStore } from '@/stores/cart'
import type {
  ActionCardContent,
  ActionResult,
  ActionStatus,
  ChatActionResponse,
} from '@/types/guide'
import { getErrorMessage } from '@/utils/error'
import { formatPrice } from '@/utils/format'

const props = defineProps<{
  card: ActionCardContent
}>()

const emit = defineEmits<{
  (event: 'updated', payload: ChatActionResponse): void
}>()

const cart = useCartStore()
const status = ref<ActionStatus>(props.card.status)
const result = ref<ActionResult>(props.card.result || {})
const busy = ref(false)

watch(
  () => props.card,
  (card) => {
    status.value = card.status
    result.value = card.result || {}
  },
  { deep: true },
)

const availableSizes = computed(
  () => result.value.available_sizes || [],
)
const pending = computed(() => status.value === 'pending')

function apply(response: ChatActionResponse): void {
  status.value = response.status
  result.value = response.result || {}
  emit('updated', response)
}

async function confirm(): Promise<void> {
  if (!pending.value || busy.value) {
    return
  }
  busy.value = true
  try {
    const response = await confirmChatAction(props.card.action_id)
    apply(response)
    if (response.status === 'executed') {
      await cart.load(true)
      showToast('已加入购物车')
    } else if (response.status === 'failed') {
      showToast(response.result.reason || '加购失败')
    }
  } catch (error) {
    showToast(getErrorMessage(error))
  } finally {
    busy.value = false
  }
}

async function cancel(): Promise<void> {
  if (!pending.value || busy.value) {
    return
  }
  busy.value = true
  try {
    apply(await cancelChatAction(props.card.action_id))
    showToast('已取消加购')
  } catch (error) {
    showToast(getErrorMessage(error))
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div
    class="guide-action-card"
    :data-action-status="status"
    :data-action-id="card.action_id"
  >
    <div class="action-head">
      <span class="action-title">加购确认</span>
      <span class="action-status" :class="status">
        {{
          status === 'pending'
            ? '待确认'
            : status === 'executed'
              ? '已加入'
              : status === 'failed'
                ? '加购失败'
                : '已取消'
        }}
      </span>
    </div>

    <div class="action-product">
      <div class="action-image">
        <ProductImage :src="card.payload.image" :alt="card.payload.title" />
      </div>
      <div class="action-main">
        <div class="action-name">{{ card.payload.title }}</div>
        <div class="action-spec">
          {{ card.payload.color }} · {{ card.payload.size }} 码 ·
          ×{{ card.payload.quantity }}
        </div>
        <div class="action-price">
          <small>¥</small>{{ formatPrice(card.payload.price) }}
        </div>
      </div>
    </div>

    <div v-if="status === 'executed'" class="action-success">
      <div class="action-success-text">
        <van-icon name="success" />
        已加入购物车
      </div>
      <router-link to="/cart" class="action-cart-link">
        去购物车
      </router-link>
    </div>

    <div v-else-if="status === 'failed'" class="action-failed">
      <div class="action-failed-reason">
        {{ result.reason || '商品暂时无法加入购物车' }}
      </div>
      <div v-if="availableSizes.length" class="action-size-list">
        可换尺码：{{ availableSizes.join('、') }}
      </div>
    </div>

    <div v-else-if="status === 'cancelled'" class="action-cancelled">
      已取消，本次不会加入购物车
    </div>

    <div v-else class="action-buttons">
      <button
        type="button"
        class="action-cancel"
        :disabled="busy"
        @click="cancel"
      >
        取消
      </button>
      <button
        type="button"
        class="action-confirm"
        :disabled="busy"
        @click="confirm"
      >
        {{ busy ? '处理中…' : '确认加入' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.guide-action-card {
  background: var(--color-card);
  border: 1px solid var(--color-primary-border);
  border-radius: 12px;
  box-shadow: var(--shadow-card);
  padding: 10px;
  color: var(--color-text);
  min-width: 230px;
}

.action-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.action-title {
  font-size: 12px;
  font-weight: 700;
}

.action-status {
  font-size: 9px;
  font-weight: 600;
  border-radius: 5px;
  padding: 1px 5px;
  background: var(--color-field-bg);
  color: var(--color-text-secondary);
}

.action-status.pending {
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.action-status.executed {
  color: #1a9c62;
  background: #e8f8ef;
}

.action-status.failed {
  color: var(--color-price);
  background: #fff1eb;
}

.action-product {
  margin-top: 9px;
  display: flex;
  gap: 9px;
}

.action-image {
  width: 62px;
  flex: 0 0 auto;
  border-radius: 8px;
  overflow: hidden;
}

.action-main {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.action-name {
  font-size: 11.5px;
  font-weight: 600;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

.action-spec {
  font-size: 10px;
  color: var(--color-text-secondary);
}

.action-price {
  color: var(--color-price);
  font-size: 15px;
  font-weight: 800;
}

.action-price small {
  font-size: 9px;
}

.action-buttons {
  margin-top: 10px;
  display: flex;
  gap: 8px;
}

.action-cancel,
.action-confirm {
  flex: 1;
  height: 34px;
  border-radius: 17px;
  font-size: 11.5px;
  font-weight: 700;
}

.action-cancel {
  border: 1px solid var(--color-border);
  background: var(--color-field-bg);
  color: var(--color-text-secondary);
}

.action-confirm {
  border: 0;
  background: var(--color-primary-gradient);
  color: #fff;
}

.action-cancel:disabled,
.action-confirm:disabled {
  opacity: 0.55;
}

.action-success {
  margin-top: 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  background: #e8f8ef;
  border-radius: 9px;
  padding: 8px 10px;
}

.action-success-text {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #1a9c62;
  font-size: 11.5px;
  font-weight: 700;
}

.action-cart-link {
  color: var(--color-primary);
  font-size: 11px;
  font-weight: 700;
  text-decoration: none;
}

.action-failed {
  margin-top: 10px;
  background: #fff1eb;
  border-radius: 9px;
  padding: 8px 10px;
}

.action-failed-reason {
  color: var(--color-price);
  font-size: 11px;
  font-weight: 600;
}

.action-size-list {
  margin-top: 4px;
  color: var(--color-text-secondary);
  font-size: 10px;
}

.action-cancelled {
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: 9px;
  background: var(--color-field-bg);
  color: var(--color-text-secondary);
  font-size: 11px;
}
</style>
