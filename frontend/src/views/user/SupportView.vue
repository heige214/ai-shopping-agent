<script setup lang="ts">
import axios from 'axios'
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'

import { fetchProduct } from '@/api/catalog'
import {
  createSupportSession,
  escalateSupportSession,
  fetchSupportMessages,
  sendSupportFeedback,
  sendSupportMessage,
} from '@/api/support'
import ProductImage from '@/components/catalog/ProductImage.vue'
import type { ProductDetail } from '@/types/catalog'
import type {
  AnswerMeta,
  ChatMessage,
  ChatSession,
  Citation,
} from '@/types/support'
import { getErrorMessage } from '@/utils/error'
import { formatPrice } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const product = ref<ProductDetail | null>(null)
const session = ref<ChatSession | null>(null)
const messages = ref<ChatMessage[]>([])
const loading = ref(true)
const errorMessage = ref('')
const input = ref('')
const sending = ref(false)
const escalating = ref(false)
const messageList = ref<HTMLElement | null>(null)

const streaming = ref(false)
const streamingText = ref('')
const streamingCitations = ref<Citation[]>([])
const streamingHandoff = ref(false)
const feedbackState = reactive<Record<number, boolean>>({})

const DOC_LABELS: Record<string, string> = {
  detail: '商品详情',
  faq: '商品问答',
  size: '尺码指南',
  care: '洗护指南',
  policy: '平台规则',
}

const selectedSize = computed(() =>
  typeof route.query.size === 'string' ? route.query.size : '',
)

const waitingHuman = computed(
  () =>
    session.value?.status === 'waiting_human' ||
    session.value?.status === 'human',
)

const canSend = computed(
  () => input.value.trim().length > 0 && !sending.value && !waitingHuman.value,
)

const productSubtitle = computed(() => {
  if (!product.value) {
    return ''
  }
  const price = `¥${formatPrice(product.value.price)}`
  return selectedSize.value ? `${price} · 已选 ${selectedSize.value} 码` : price
})

function friendlyError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    return getErrorMessage(error)
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return '操作失败，请稍后重试'
}

function messageText(message: ChatMessage): string {
  return typeof message.content.text === 'string' ? message.content.text : ''
}

function citationsOf(message: ChatMessage): Citation[] {
  return Array.isArray(message.meta.citations) ? message.meta.citations : []
}

function citationLabel(citation: Citation): string {
  return DOC_LABELS[citation.doc_type] ?? '参考资料'
}

function isHandoff(message: ChatMessage): boolean {
  return Boolean(message.meta.handoff_required)
}

function showFeedback(message: ChatMessage): boolean {
  return (
    message.sender_type === 'ai' &&
    message.id > 0 &&
    Boolean(message.meta.intent)
  )
}

function goBack(): void {
  if (window.history.length > 1) {
    router.back()
  } else if (product.value) {
    router.replace(`/product/${product.value.id}`)
  } else {
    router.replace('/')
  }
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

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const productId = Number(route.params.id)
    product.value = await fetchProduct(productId)
    const chatSession = await createSupportSession(productId)
    session.value = chatSession
    const page = await fetchSupportMessages(chatSession.id, undefined, 50)
    messages.value = page.items
    for (const message of messages.value) {
      if (message.meta.feedback) {
        feedbackState[message.id] = Boolean(message.meta.feedback.helpful)
      }
    }
  } catch (error) {
    errorMessage.value = friendlyError(error)
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

async function submit(): Promise<void> {
  const text = input.value.trim()
  if (!text || !session.value || sending.value || waitingHuman.value) {
    return
  }
  input.value = ''
  messages.value.push({
    id: -Date.now(),
    session_id: session.value.id,
    sender_type: 'user',
    content_type: 'text',
    content: { text },
    meta: {},
    created_at: new Date().toISOString(),
  })

  sending.value = true
  streaming.value = true
  streamingText.value = ''
  streamingCitations.value = []
  streamingHandoff.value = false
  let doneId = 0
  let answerMeta: AnswerMeta | null = null
  scrollToBottom()

  try {
    await sendSupportMessage(session.value.id, text, (event, data) => {
      if (event === 'token') {
        streamingText.value += (data as { text: string }).text
        scrollToBottom()
      } else if (event === 'citations') {
        streamingCitations.value =
          (data as { items: Citation[] }).items ?? []
      } else if (event === 'answer_meta') {
        answerMeta = data as AnswerMeta
        streamingHandoff.value = Boolean(answerMeta.handoff_required)
      } else if (event === 'done') {
        doneId = (data as { message_id: number }).message_id
      } else if (event === 'error') {
        const message =
          (data as { message?: string }).message || '服务繁忙，请稍后再试'
        showToast(message)
      }
    })

    const answerText =
      streamingText.value || '服务繁忙，暂时无法完成回答，请稍后再试或转人工客服。'
    if (!streamingText.value) {
      streamingHandoff.value = true
    }
    messages.value.push({
      id: doneId || -Date.now(),
      session_id: session.value.id,
      sender_type: 'ai',
      content_type: 'text',
      content: { text: answerText },
      meta: {
        ...(answerMeta ?? {}),
        citations: streamingCitations.value,
        handoff_required: streamingHandoff.value,
      },
      created_at: new Date().toISOString(),
    })
    if (streamingHandoff.value) {
      showToast('建议转人工客服进一步确认')
    }
  } catch (error) {
    showToast(friendlyError(error))
    messages.value.push({
      id: -Date.now(),
      session_id: session.value.id,
      sender_type: 'ai',
      content_type: 'text',
      content: {
        text: '服务繁忙，暂时无法回答，请稍后重试或转人工客服。',
      },
      meta: { handoff_required: true },
      created_at: new Date().toISOString(),
    })
  } finally {
    sending.value = false
    streaming.value = false
    streamingText.value = ''
    streamingCitations.value = []
    streamingHandoff.value = false
    scrollToBottom()
  }
}

async function escalate(): Promise<void> {
  if (!session.value || escalating.value || waitingHuman.value) {
    return
  }
  escalating.value = true
  try {
    const result = await escalateSupportSession(session.value.id)
    session.value = { ...session.value, status: result.session_status }
    messages.value.push({
      id: -Date.now(),
      session_id: session.value.id,
      sender_type: 'system',
      content_type: 'system_event',
      content: { event: 'waiting_human', text: '已转人工，等待客服接入' },
      meta: {},
      created_at: new Date().toISOString(),
    })
    showToast('已转人工，等待客服接入')
    scrollToBottom()
  } catch (error) {
    showToast(friendlyError(error))
  } finally {
    escalating.value = false
  }
}

async function feedback(
  message: ChatMessage,
  helpful: boolean,
): Promise<void> {
  if (message.id <= 0 || feedbackState[message.id] !== undefined) {
    return
  }
  try {
    await sendSupportFeedback(message.id, helpful)
    feedbackState[message.id] = helpful
    showToast(helpful ? '感谢反馈' : '已记录，我们会改进')
  } catch (error) {
    showToast(friendlyError(error))
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="page support-page">
    <header class="support-header">
      <button type="button" class="icon-button" aria-label="返回" @click="goBack">
        <van-icon name="arrow-left" size="18" />
      </button>
      <div class="header-main">
        <div class="header-title">AI 客服</div>
        <div v-if="product" class="header-sub">{{ product.title }}</div>
      </div>
      <button
        v-if="!waitingHuman"
        type="button"
        class="handoff-link"
        :disabled="escalating"
        @click="escalate"
      >
        转人工
      </button>
      <span v-else class="handoff-pill">等待人工</span>
    </header>

    <div v-if="loading" class="state-panel">
      <van-loading size="22">加载中...</van-loading>
    </div>
    <van-empty v-else-if="errorMessage" :description="errorMessage" />
    <template v-else>
      <main ref="messageList" class="message-scroll">
        <div v-if="product" class="mini-product">
          <div class="mini-image">
            <ProductImage :src="product.main_image" :alt="product.title" />
          </div>
          <div class="mini-info">
            <div class="mini-title">{{ product.title }}</div>
            <div class="mini-sub">{{ productSubtitle }}</div>
          </div>
        </div>

        <template v-for="message in messages" :key="message.id">
          <div
            v-if="message.sender_type === 'system'"
            class="system-row"
          >
            {{ messageText(message) }}
          </div>
          <div
            v-else-if="message.sender_type === 'user'"
            class="message-row user"
          >
            <div class="bubble user-bubble">{{ messageText(message) }}</div>
          </div>
          <div v-else class="message-row ai">
            <div class="ai-avatar">AI</div>
            <div class="ai-content">
              <div
                class="bubble ai-bubble"
                :class="{ 'fallback-bubble': isHandoff(message) }"
              >
                <span class="bubble-text">{{ messageText(message) }}</span>
                <div
                  v-if="citationsOf(message).length"
                  class="citation-list"
                >
                  <span
                    v-for="(citation, index) in citationsOf(message)"
                    :key="index"
                    class="citation-chip"
                  >
                    <van-icon name="notes-o" size="11" />
                    {{ citationLabel(citation) }}
                  </span>
                </div>
                <button
                  v-if="isHandoff(message) && !waitingHuman"
                  type="button"
                  class="escalate-button"
                  :disabled="escalating"
                  @click="escalate"
                >
                  转人工客服
                </button>
              </div>
              <div v-if="showFeedback(message)" class="feedback-row">
                <button
                  type="button"
                  class="feedback-button"
                  :class="{ active: feedbackState[message.id] === true }"
                  :disabled="feedbackState[message.id] !== undefined"
                  @click="feedback(message, true)"
                >
                  有帮助
                </button>
                <button
                  type="button"
                  class="feedback-button"
                  :class="{ active: feedbackState[message.id] === false }"
                  :disabled="feedbackState[message.id] !== undefined"
                  @click="feedback(message, false)"
                >
                  没帮助
                </button>
              </div>
            </div>
          </div>
        </template>

        <div v-if="streaming" class="message-row ai">
          <div class="ai-avatar">AI</div>
          <div class="ai-content">
            <div class="bubble ai-bubble">
              <span class="bubble-text">
                {{ streamingText || '正在检索商品资料…' }}
              </span>
              <div
                v-if="streamingCitations.length"
                class="citation-list"
              >
                <span
                  v-for="(citation, index) in streamingCitations"
                  :key="index"
                  class="citation-chip"
                >
                  <van-icon name="notes-o" size="11" />
                  {{ citationLabel(citation) }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div v-if="waitingHuman" class="waiting-banner">
          <van-icon name="clock-o" size="14" />
          已转人工，等待客服接入
        </div>
        <div class="ai-note">AI 回答基于商品知识库，仅供参考</div>
      </main>

      <form class="input-bar" @submit.prevent="submit">
        <input
          v-model="input"
          class="support-input"
          :disabled="waitingHuman || sending"
          :placeholder="
            waitingHuman
              ? '等待客服接入…'
              : '问商品问题，例如材质、尺码、洗护'
          "
          maxlength="2000"
        />
        <button
          type="submit"
          class="send-button"
          :disabled="!canSend"
          aria-label="发送"
        >
          <van-icon name="guide-o" size="20" />
        </button>
      </form>
    </template>
  </div>
</template>

<style scoped>
.support-page {
  height: 100vh;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg);
}

.support-header {
  height: 58px;
  flex: 0 0 auto;
  background: var(--color-card);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 10px;
}

.icon-button {
  width: 40px;
  height: 44px;
  border: 0;
  background: transparent;
  color: var(--color-text);
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-main {
  flex: 1;
  min-width: 0;
}

.header-title {
  font-size: 15px;
  font-weight: 700;
}

.header-sub {
  margin-top: 1px;
  font-size: 10px;
  color: var(--color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.handoff-link {
  border: 0;
  background: transparent;
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 600;
  padding: 10px 4px;
}

.handoff-pill {
  font-size: 10px;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border: 1px solid var(--color-primary-border);
  border-radius: 10px;
  padding: 3px 8px;
}

.state-panel {
  padding: 80px 0;
  display: flex;
  justify-content: center;
}

.message-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 12px 12px 18px;
}

.mini-product {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  background: var(--color-card);
  border-radius: 12px;
  box-shadow: var(--shadow-card);
  margin-bottom: 14px;
}

.mini-image {
  width: 46px;
  height: 46px;
  border-radius: 8px;
  overflow: hidden;
  flex: 0 0 auto;
}

.mini-info {
  min-width: 0;
}

.mini-title {
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mini-sub {
  margin-top: 4px;
  font-size: 10px;
  color: var(--color-text-secondary);
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
  max-width: 82%;
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

.fallback-bubble {
  border: 1px solid #ffe3d5;
}

.citation-list {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 7px;
}

.citation-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 9.5px;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border: 1px solid var(--color-primary-border);
  border-radius: 8px;
  padding: 2px 6px;
}

.escalate-button {
  width: 100%;
  margin-top: 9px;
  padding: 8px 10px;
  border: 0;
  border-radius: 9px;
  background: var(--color-primary-gradient);
  color: #fff;
  font-size: 11.5px;
  font-weight: 600;
}

.feedback-row {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}

.feedback-button {
  border: 1px solid var(--color-border);
  background: var(--color-card);
  color: var(--color-text-secondary);
  border-radius: 9px;
  padding: 3px 9px;
  font-size: 10px;
}

.feedback-button.active {
  color: var(--color-primary);
  border-color: var(--color-primary-border);
  background: var(--color-primary-soft);
}

.feedback-button:disabled {
  opacity: 0.75;
}

.system-row {
  text-align: center;
  font-size: 10px;
  color: var(--color-text-secondary);
  margin: 10px 0;
}

.waiting-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  margin: 12px auto 0;
  padding: 7px 10px;
  border-radius: 10px;
  background: var(--color-primary-soft);
  border: 1px solid var(--color-primary-border);
  color: var(--color-primary);
  font-size: 11px;
  max-width: 280px;
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

.support-input {
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

.support-input:disabled {
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
