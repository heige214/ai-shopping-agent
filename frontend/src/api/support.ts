import http from '@/api/http'
import type {
  ChatSession,
  EscalateResult,
  MessagePage,
} from '@/types/support'
import { streamPost, type SSEHandler } from '@/utils/sse'

export async function createSupportSession(
  productId: number,
): Promise<ChatSession> {
  const { data } = await http.post<ChatSession>('/chat/sessions', {
    type: 'support',
    product_id: productId,
  })
  return data
}

export async function fetchSupportSessions(): Promise<ChatSession[]> {
  const { data } = await http.get<ChatSession[]>('/chat/sessions', {
    params: { type: 'support' },
  })
  return data
}

export async function fetchSupportMessages(
  sessionId: number,
  beforeId?: number,
  limit = 20,
): Promise<MessagePage> {
  const { data } = await http.get<MessagePage>(
    `/chat/sessions/${sessionId}/messages`,
    { params: { before_id: beforeId, limit } },
  )
  return data
}

export async function sendSupportMessage(
  sessionId: number,
  text: string,
  onEvent: SSEHandler,
  signal?: AbortSignal,
): Promise<void> {
  await streamPost(
    `/chat/sessions/${sessionId}/messages`,
    { content_type: 'text', content: { text } },
    onEvent,
    signal,
  )
}

export async function escalateSupportSession(
  sessionId: number,
): Promise<EscalateResult> {
  const { data } = await http.post<EscalateResult>(
    `/chat/sessions/${sessionId}/escalate`,
  )
  return data
}

export async function sendSupportFeedback(
  messageId: number,
  helpful: boolean,
  comment?: string,
): Promise<{ message_id: number; helpful: boolean }> {
  const { data } = await http.post<{ message_id: number; helpful: boolean }>(
    `/chat/messages/${messageId}/feedback`,
    { helpful, comment: comment ?? null },
  )
  return data
}
