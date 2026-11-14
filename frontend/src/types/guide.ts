export interface GuidePrice {
  min: number | null
  max: number | null
}

export interface GuideSizeProfile {
  height_cm: number | null
  weight_kg: number | null
  usual_size: string | null
}

export interface GuideQuery {
  intent: 'search' | 'refine' | 'chitchat'
  semantic: string | null
  category_path: string[]
  filters: Record<string, string[]>
  price: GuidePrice
  size_profile: GuideSizeProfile
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

export interface GuideStreamMeta {
  intent: string
  query: GuideQuery
  need_clarify: boolean
  relaxed: string[]
  quick_replies: string[]
  degraded?: boolean
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
