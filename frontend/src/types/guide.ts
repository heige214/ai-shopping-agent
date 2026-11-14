export interface GuidePrice {
  min: number | null
  max: number | null
}

export interface GuideSizeProfile {
  height_cm: number | null
  weight_kg: number | null
  usual_size: string | null
}

export interface GuideCartQuery {
  reference: 'ordinal' | 'name' | 'deictic' | 'none'
  ordinal: number | null
  product_name: string | null
  size: string | null
  quantity: number
}

export interface GuideQuery {
  intent: 'search' | 'refine' | 'chitchat' | 'add_to_cart'
  semantic: string | null
  category_path: string[]
  filters: Record<string, string[]>
  price: GuidePrice
  size_profile: GuideSizeProfile
  cart?: GuideCartQuery | null
}

export interface GuideProductCard {
  id: number
  title: string
  price: number
  original_price: number | null
  main_image: string | null
  brand: string | null
  attributes: Record<string, string | string[] | number>
  reason: string
  recommended_size: string | null
  size_reason: string | null
  sales_count: number
}

export interface GuideProductsPayload {
  items: GuideProductCard[]
  relaxed: string[]
  query: GuideQuery
}

export interface VisionPayload {
  category_path: string[]
  attributes: Record<string, string[]>
  description: string
  confidence: number
}

export interface GuideStreamMeta {
  intent: string
  query: GuideQuery
  need_clarify: boolean
  relaxed: string[]
  quick_replies: string[]
  degraded?: boolean
  vision?: VisionPayload | null
  image_failed?: boolean
  action_id?: number
  payload?: ActionPayload
  available_sizes?: string[]
}

export type ActionStatus =
  | 'pending'
  | 'confirmed'
  | 'cancelled'
  | 'executed'
  | 'failed'

export interface ActionPayload {
  product_id: number
  sku_id: number
  title: string
  color: string
  size: string
  quantity: number
  price: number
  image: string | null
}

export interface ActionResult {
  reason?: string
  available_sizes?: string[]
  cart_item_id?: number
  quantity?: number
  sku_id?: number
  price?: number
  color?: string
  size?: string
  [key: string]: unknown
}

export interface ActionCardContent {
  action_id: number
  action_type: 'add_to_cart'
  status: ActionStatus
  payload: ActionPayload
  result?: ActionResult
}

export interface ChatActionResponse {
  action_id: number
  status: ActionStatus
  result: ActionResult
  quantity: number | null
  cart_item_id: number | null
  available_sizes: string[]
}

export interface ImageUploadResult {
  url: string
}

export interface VoiceUploadResult {
  url: string
  transcript: string
}

export interface SizeRecommendation {
  product_id: number
  recommended_size: string | null
  size_reason: string | null
  source: string | null
  height_cm: number | null
  weight_kg: number | null
  usual_size: string | null
}
