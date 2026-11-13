export interface AttributeDef {
  key: string
  label: string
  type: 'enum' | 'multi_enum' | 'tags' | 'string' | 'number'
  options?: string[] | null
  filterable: boolean
}

export interface AttributeSchema {
  attributes: AttributeDef[]
}

export interface SizeChartRow {
  size: string
  height?: number[]
  weight?: number[]
  chest?: number[]
  waist?: number[]
  foot_length?: number[]
}

export interface SizeChart {
  type: 'clothing' | 'shoes'
  unit: string
  rows: SizeChartRow[]
}

export interface Category {
  id: number
  parent_id: number | null
  name: string
  slug: string
  level: number
  sort_order: number
  attribute_schema: AttributeSchema
  size_chart_template: SizeChart | null
  children: Category[]
}

export interface ProductSummary {
  id: number
  product_code: string
  category_id: number
  title: string
  price: number
  original_price: number | null
  main_image: string | null
  brand: string | null
  sales_count: number
}

export interface ProductSku {
  id: number
  color: string
  size: string
  stock: number
  price: number
  status: string
}

export interface ProductDetail extends ProductSummary {
  description: string | null
  images: string[]
  attributes: Record<string, string | string[] | number>
  attribute_schema: AttributeSchema
  size_chart: SizeChart | null
  category_name: string
  parent_category_name: string | null
  skus: ProductSku[]
  is_favorited: boolean
}

export interface ProductPage {
  items: ProductSummary[]
  total: number
  page: number
  page_size: number
}

export interface FavoriteState {
  favorited: boolean
}

export type ProductSort = 'recommended' | 'price_asc' | 'price_desc'
