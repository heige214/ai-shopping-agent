<script setup lang="ts">
import axios from 'axios'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { showToast } from 'vant'

import { fetchProducts } from '@/api/catalog'
import {
  createGuideSession,
  fetchGuideMessages,
  fetchGuideSessions,
  sendGuideMessage,
} from '@/api/guide'
import CartBadge from '@/components/commerce/CartBadge.vue'
import GuideEmptyState from '@/components/guide/GuideEmptyState.vue'
import GuideProductCardView from '@/components/guide/GuideProductCard.vue'
import { useAuthStore } from '@/stores/auth'
import { useCartStore } from '@/stores/cart'
import { useCatalogStore } from '@/stores/catalog'
import type { Category, ProductSummary } from '@/types/catalog'
import type {
  GuideProductCard,
  GuideProductsPayload,
  GuideStreamMeta,
} from '@/types/guide'
import type { ChatMessage, ChatSession } from '@/types/support'
import { getErrorMessage } from '@/utils/error'

const auth = useAuthStore()
const cart = useCartStore()
const catalog = useCatalogStore()

const session = ref<ChatSession | null>(null)
const messages = ref<ChatMessage[]>([])
const input = ref('')
const sending = ref(false)
const booting = ref(true)
const hotProducts = ref<ProductSummary[]>([])
const hotLoading = ref(true)
const messageList = ref<HTMLElement | null>(null)

const streaming = ref(false)
const streamingText = ref('')
const streamingProducts = ref<GuideProductCard[]>([])
const quickReplies = ref<string[]>([])

const examples = ['推荐几件衬衫', '通勤双肩包', '跑步运动鞋']

const displayName = computed(
  () => auth.user?.nickname || auth.user?.username || '',
)
const categories = computed(() => catalog.roots.slice(0, 4))
const profileComplete = computed(
  () => Boolean(auth.user?.height_cm && auth.user?.weight_kg),
)
const profileSummary = computed(() => {
  const parts: string[] = []
  if (auth.user?.height_cm) parts.push(`${auth.user.height_cm}cm`)
  if (auth.user?.weight_kg) parts.push(`${auth.user.weight_kg}kg`)
  if (auth.user?.usual_size) parts.push(`常穿 ${auth.user.usual_size} 码`)
  return parts.length
    ? parts.join(' · ')
    : '完善身材档案后，商品卡会标注推荐尺码'
})
const showEmptyState = computed(
  () => messages.value.length === 0 && !streaming.value,
)

function messageText(message: ChatMessage): string {
  return typeof message.content.text === 'string' ? message.content.text : ''
}

function productsOf(message: ChatMessage): GuideProductCard[] {
  const value = message.meta.products
  return Array.isArray(value) ? (value as GuideProductCard[]) : []
}

function friendlyError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    return getErrorMessage(error)
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return '操作失败，请稍后重试'
}

function scrollToBottom(): void {
  void nextTick(() => {
    const element = messageList.value
    if (element) {
      element.scrollTop = element.scrollHeight
    }
  })
}

watch(streamingText, scrollToBottom)

async function loadDiscover(): Promise<void> {
  try {
    await catalog.load()
    const page = await fetchProducts({ page_size: 8, sort: 'recommended' })
    hotProducts.value = page.items
  } catch {
    hotProducts.value = []
  } finally {
    hotLoading.value = false
  }
}

async function loadSession(): Promise<void> {
  try {
    const sessions = await fetchGuideSessions()
    const active = sessions.find((item) => item.status === 'active')
    if (!active) {
      return
    }
    session.value = active
    const page = await fetchGuideMessages(active.id, 50)
    messages.value = page.items
    scrollToBottom()
  } catch {
    // 会话加载失败时仍展示空状态，首次发送会重新创建会话
  } finally {
    booting.value = false
  }
}

async function ensureSession(): Promise<ChatSession> {
  if (session.value) {
    return session.value
  }
  session.value = await createGuideSession()
  return session.value
}

async function send(text: string): Promise<void> {
  const content = text.trim()
  if (!content || sending.value) {
    return
  }
  let chatSession: ChatSession
  try {
    chatSession = await ensureSession()
  } catch (error) {
    showToast(friendlyError(error))
    return
  }

  input.value = ''
  quickReplies.value = []
  messages.value.push({
    id: -Date.now(),
    session_id: chatSession.id,
    sender_type: 'user',
    content_type: 'text',
    content: { text: content },
    meta: {},
    created_at: new Date().toISOString(),
  })

  sending.value = true
  streaming.value = true
  streamingText.value = ''
  streamingProducts.value = []
  const metaRef = ref<GuideStreamMeta | null>(null)
  let products: GuideProductCard[] = []
  let relaxed: string[] = []
  let doneId = 0
  scrollToBottom()

  try {
    await sendGuideMessage(chatSession.id, content, (event, data) => {
      if (event === 'meta') {
        metaRef.value = data as GuideStreamMeta
        quickReplies.value = metaRef.value.quick_replies ?? []
        scrollToBottom()
      } else if (event === 'token') {
        streamingText.value += (data as { text: string }).text
        scrollToBottom()
      } else if (event === 'products') {
        const payload = data as GuideProductsPayload
        products = payload.items ?? []
        relaxed = payload.relaxed ?? []
        streamingProducts.value = products
        scrollToBottom()
      } else if (event === 'done') {
        doneId = (data as { message_id: number }).message_id
      } else if (event === 'error') {
        const message = (data as { message?: string }).message
        if (message) {
          showToast(message)
        }
      }
    })

    const meta = metaRef.value
    const answerText =
      streamingText.value || '暂时没有找到合适的商品，换个条件再试试。'
    messages.value.push({
      id: doneId || -Date.now(),
      session_id: chatSession.id,
      sender_type: 'ai',
      content_type: 'text',
      content: { text: answerText },
      meta: {
        intent: meta?.intent,
        query: meta?.query,
        need_clarify: meta?.need_clarify,
        quick_replies: meta?.quick_replies ?? [],
        degraded: meta?.degraded,
        products,
        relaxed,
      },
      created_at: new Date().toISOString(),
    })
    quickReplies.value = meta?.quick_replies ?? []
  } catch (error) {
    showToast(friendlyError(error))
    messages.value.push({
      id: -Date.now(),
      session_id: chatSession.id,
      sender_type: 'ai',
      content_type: 'text',
      content: {
        text: '服务繁忙，暂时无法完成推荐，请稍后重试。',
      },
      meta: {},
      created_at: new Date().toISOString(),
    })
  } finally {
    sending.value = false
    streaming.value = false
    streamingText.value = ''
    streamingProducts.value = []
    scrollToBottom()
  }
}

async function newConversation(): Promise<void> {
  if (sending.value) {
    return
  }
  try {
    session.value = await createGuideSession(true)
    messages.value = []
    quickReplies.value = []
    streamingProducts.value = []
    input.value = ''
    scrollToBottom()
  } catch (error) {
    showToast(friendlyError(error))
  }
}

function handleCategory(category: Category): void {
  void send(`我想看看${category.name}`)
}

onMounted(() => {
  cart.load().catch(() => undefined)
  void loadDiscover()
  void loadSession()
})
</script>

<template>
  <div class="page home-page">
    <header class="home-header">
      <div class="brand">
        <div class="brand-logo" aria-hidden="true">AI</div>
        <div>
          <h1 class="brand-title">AI 找货</h1>
          <div class="brand-sub">对话式导购助手</div>
        </div>
      </div>
      <div class="header-actions">
        <button
          type="button"
          class="new-chat-button"
          :disabled="sending"
          @click="newConversation"
        >
          新对话
        </button>
        <CartBadge />
      </div>
    </header>

    <main ref="messageList" class="home-main">
      <div v-if="booting" class="state-panel">
        <van-loading size="22">加载中...</van-loading>
      </div>
      <GuideEmptyState
        v-else-if="showEmptyState"
        :user-name="displayName"
        :profile-summary="profileSummary"
        :profile-complete="profileComplete"
        :examples="examples"
        :categories="categories"
        :products="hotProducts"
        :loading="hotLoading"
        @example="send"
        @category="handleCategory"
      />
      <template v-else>
        <template v-for="message in messages" :key="message.id">
          <div
            v-if="message.sender_type === 'user'"
            class="message-row user"
          >
            <div class="bubble user-bubble">{{ messageText(message) }}</div>
          </div>
          <div v-else class="message-row ai">
            <div class="ai-avatar">AI</div>
            <div class="ai-content">
              <div class="bubble ai-bubble">
                <span class="bubble-text">{{ messageText(message) }}</span>
                <div
                  v-if="productsOf(message).length"
                  class="guide-card-grid"
                >
                  <GuideProductCardView
                    v-for="card in productsOf(message)"
                    :key="card.id"
                    :card="card"
                  />
                </div>
              </div>
            </div>
          </div>
        </template>

        <div v-if="streaming" class="message-row ai">
          <div class="ai-avatar">AI</div>
          <div class="ai-content">
            <div class="bubble ai-bubble">
              <span class="bubble-text">
                {{ streamingText || '正在检索商品…' }}
              </span>
              <div
                v-if="streamingProducts.length"
                class="guide-card-grid"
              >
                <GuideProductCardView
                  v-for="card in streamingProducts"
                  :key="card.id"
                  :card="card"
                />
              </div>
            </div>
          </div>
        </div>

        <div v-if="quickReplies.length && !sending" class="quick-reply-row">
          <button
            v-for="reply in quickReplies"
            :key="reply"
            type="button"
            class="quick-reply-chip"
            @click="send(reply)"
          >
            {{ reply }}
          </button>
        </div>
        <div class="ai-note">AI 推荐基于商品库与你的身材档案，仅供参考</div>
      </template>
    </main>

    <form class="input-bar" @submit.prevent="send(input)">
      <input
        v-model="input"
        class="guide-input"
        :disabled="sending"
        placeholder="说说你想找什么，例如：蓝色薄衬衫"
        maxlength="500"
      />
      <button
        type="submit"
        class="send-button"
        :disabled="!input.trim() || sending"
        aria-label="发送"
      >
        <van-icon name="guide-o" size="20" />
      </button>
    </form>
  </div>
</template>

<style scoped>
.home-page {
  height: calc(100dvh - 56px - env(safe-area-inset-bottom));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-bg);
}

.home-header {
  height: 58px;
  flex: 0 0 auto;
  background: var(--color-card);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 8px 0 16px;
  border-bottom: 1px solid var(--color-border);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-logo {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: var(--color-primary-gradient);
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-title {
  font-size: 15px;
  font-weight: 700;
  line-height: 1.1;
  margin: 0;
}

.brand-sub {
  font-size: 10px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.new-chat-button {
  border: 1px solid var(--color-primary-border);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 11px;
  font-weight: 600;
}

.new-chat-button:disabled {
  opacity: 0.5;
}

.home-main {
  flex: 1;
  overflow-y: auto;
  padding: 12px 12px 16px;
}

.state-panel {
  padding: 80px 0;
  display: flex;
  justify-content: center;
}

.message-row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.message-row.user {
  justify-content: flex-end;
}

.ai-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-primary-gradient);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}

.ai-content {
  max-width: 86%;
  min-width: 0;
}

.bubble {
  border-radius: 12px;
  padding: 9px 11px;
  font-size: 12px;
  line-height: 1.55;
  word-break: break-word;
}

.ai-bubble {
  background: var(--color-card);
  box-shadow: var(--shadow-card);
  border-top-left-radius: 4px;
}

.user-bubble {
  background: var(--color-primary-gradient);
  color: #fff;
  border-top-right-radius: 4px;
}

.guide-card-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 9px;
}

.quick-reply-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 0 0 12px 36px;
}

.quick-reply-chip {
  border: 1px solid var(--color-primary-border);
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 10.5px;
}

.ai-note {
  text-align: center;
  font-size: 9.5px;
  color: var(--color-text-tertiary);
  margin: 14px 0 4px;
}

.input-bar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  padding-bottom: calc(8px + env(safe-area-inset-bottom));
  background: var(--color-card);
  border-top: 1px solid var(--color-border);
}

.guide-input {
  flex: 1;
  min-width: 0;
  height: 38px;
  border: 0;
  outline: none;
  border-radius: 19px;
  background: var(--color-field-bg);
  padding: 0 14px;
  font-size: 12px;
  color: var(--color-text);
}

.guide-input:disabled {
  color: var(--color-text-tertiary);
}

.send-button {
  width: 38px;
  height: 38px;
  flex: 0 0 auto;
  border: 0;
  border-radius: 50%;
  background: var(--color-primary-gradient);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.send-button:disabled {
  opacity: 0.45;
}
</style>
