export type ChatSessionStatus =
  | 'active'
  | 'waiting_human'
  | 'human'
  | 'closed'

export type ChatSenderType = 'user' | 'ai' | 'agent' | 'system'

export interface SupportProduct {
  id: number
  title: string
  main_image: string | null
  price: number
}

export interface ChatSession {
  id: number
  type: 'support' | 'guide'
  product_id: number | null
  title: string | null
  status: ChatSessionStatus
  created_at: string
  updated_at: string
  product: SupportProduct | null
}

export interface Citation {
  doc_type: string
  title: string | null
  chunk_id?: number
}

export interface AnswerMeta {
  intent: string
  can_answer: boolean
  confidence: number
  partial: boolean
  handoff_required: boolean
  degraded?: boolean
}

export interface ChatMessageMeta {
  intent?: string
  can_answer?: boolean
  confidence?: number
  partial?: boolean
  handoff_required?: boolean
  degraded?: boolean
  citations?: Citation[]
  feedback?: { helpful: boolean; comment?: string | null }
  [key: string]: unknown
}

export interface ChatMessage {
  id: number
  session_id: number
  sender_type: ChatSenderType
  content_type: string
  content: { text?: string; [key: string]: unknown }
  meta: ChatMessageMeta
  created_at: string
}

export interface MessagePage {
  items: ChatMessage[]
  has_more: boolean
}

export interface EscalateResult {
  ticket_id: number
  ticket_status: string
  session_status: ChatSessionStatus
}

export interface DonePayload {
  message_id: number
  latency_ms: number
}

export interface ErrorPayload {
  code: string
  message: string
}
