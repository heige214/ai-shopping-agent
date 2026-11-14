import http from '@/api/http'
import type {
  ChatActionResponse,
  SizeRecommendation,
} from '@/types/guide'
import type { ChatSession, MessagePage } from '@/types/support'
import { streamPost, type SSEHandler } from '@/utils/sse'

export interface GuideMessagePayload {
  content_type: 'text' | 'image' | 'voice'
  content: Record<string, unknown>
}

export async function createGuideSession(
  newSession = false,
): Promise<ChatSession> {
  const { data } = await http.post<ChatSession>('/chat/sessions', {
    type: 'guide',
    new: newSession,
  })
  return data
}

export async function fetchGuideSessions(): Promise<ChatSession[]> {
  const { data } = await http.get<ChatSession[]>('/chat/sessions', {
    params: { type: 'guide' },
  })
  return data
}

export async function fetchGuideMessages(
  sessionId: number,
  limit = 50,
): Promise<MessagePage> {
  const { data } = await http.get<MessagePage>(
    `/chat/sessions/${sessionId}/messages`,
    { params: { limit } },
  )
  return data
}

export async function sendGuideMessage(
  sessionId: number,
  payload: GuideMessagePayload,
  onEvent: SSEHandler,
  signal?: AbortSignal,
): Promise<void> {
  await streamPost(
    `/chat/sessions/${sessionId}/messages`,
    payload,
    onEvent,
    signal,
  )
}

export async function confirmChatAction(
  actionId: number,
): Promise<ChatActionResponse> {
  const { data } = await http.post<ChatActionResponse>(
    `/chat/actions/${actionId}/confirm`,
  )
  return data
}

export async function cancelChatAction(
  actionId: number,
): Promise<ChatActionResponse> {
  const { data } = await http.post<ChatActionResponse>(
    `/chat/actions/${actionId}/cancel`,
  )
  return data
}

export async function fetchSizeRecommendation(
  productId: number,
): Promise<SizeRecommendation> {
  const { data } = await http.get<SizeRecommendation>(
    `/products/${productId}/size-recommendation`,
  )
  return data
}
