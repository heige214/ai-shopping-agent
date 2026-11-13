export type OrderStatus =
  | 'pending_payment'
  | 'paid'
  | 'shipped'
  | 'completed'
  | 'cancelled'

export interface Address {
  id: number
  receiver_name: string
  phone: string
  province: string
  city: string
  district: string
  detail: string
  is_default: boolean
  created_at: string
}

export interface AddressPayload {
  receiver_name: string
  phone: string
  province: string
  city: string
  district: string
  detail: string
  is_default?: boolean
}

export interface AddressSnapshot {
  receiver_name: string
  phone: string
  province: string
  city: string
  district: string
  detail: string
}

export interface CartItem {
  id: number
  sku_id: number
  product_id: number
  title: string
  main_image: string | null
  color: string
  size: string
  price: number
  quantity: number
  stock: number
  selected: boolean
  available: boolean
}

export interface Cart {
  items: CartItem[]
  total_quantity: number
  selected_count: number
  selected_amount: number
  all_selected: boolean
}

export interface OrderItem {
  id: number
  sku_id: number
  product_id: number
  title: string
  image: string | null
  price: number
  color: string
  size: string
  quantity: number
}

export interface Order {
  id: number
  order_no: string
  status: OrderStatus
  total_amount: number
  payment_method: string
  payment_no: string | null
  address_snapshot: AddressSnapshot
  items: OrderItem[]
  created_at: string
  expires_at: string
  paid_at: string | null
  shipped_at: string | null
  completed_at: string | null
  cancelled_at: string | null
}

export interface AgentOrder extends Order {
  buyer_id: number
  buyer_username: string
  buyer_nickname: string | null
}

export interface CreateOrderPayload {
  address_id: number
  cart_item_ids: number[]
}
