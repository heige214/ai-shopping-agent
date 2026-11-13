import http from '@/api/http'
import type {
  Address,
  AddressPayload,
  AgentOrder,
  Cart,
  CartItem,
  CreateOrderPayload,
  Order,
  OrderStatus,
} from '@/types/commerce'

export async function fetchCart(): Promise<Cart> {
  const { data } = await http.get<Cart>('/cart')
  return data
}

export async function addCartItem(
  skuId: number,
  quantity = 1,
): Promise<CartItem> {
  const { data } = await http.post<CartItem>('/cart/items', {
    sku_id: skuId,
    quantity,
  })
  return data
}

export async function updateCartItem(
  itemId: number,
  payload: { quantity?: number; selected?: boolean },
): Promise<CartItem> {
  const { data } = await http.patch<CartItem>(
    `/cart/items/${itemId}`,
    payload,
  )
  return data
}

export async function removeCartItem(itemId: number): Promise<void> {
  await http.delete(`/cart/items/${itemId}`)
}

export async function fetchAddresses(): Promise<Address[]> {
  const { data } = await http.get<Address[]>('/addresses')
  return data
}

export async function createAddress(
  payload: AddressPayload,
): Promise<Address> {
  const { data } = await http.post<Address>('/addresses', payload)
  return data
}

export async function updateAddress(
  addressId: number,
  payload: Partial<AddressPayload>,
): Promise<Address> {
  const { data } = await http.patch<Address>(
    `/addresses/${addressId}`,
    payload,
  )
  return data
}

export async function deleteAddress(addressId: number): Promise<void> {
  await http.delete(`/addresses/${addressId}`)
}

export async function createOrder(
  payload: CreateOrderPayload,
): Promise<Order> {
  const { data } = await http.post<Order>('/orders', payload)
  return data
}

export async function fetchOrders(status?: OrderStatus): Promise<Order[]> {
  const { data } = await http.get<Order[]>('/orders', {
    params: status ? { status } : {},
  })
  return data
}

export async function fetchOrder(orderId: number): Promise<Order> {
  const { data } = await http.get<Order>(`/orders/${orderId}`)
  return data
}

export async function payOrder(orderId: number): Promise<Order> {
  const { data } = await http.post<Order>(`/orders/${orderId}/pay`)
  return data
}

export async function cancelOrder(orderId: number): Promise<Order> {
  const { data } = await http.post<Order>(`/orders/${orderId}/cancel`)
  return data
}

export async function confirmOrder(orderId: number): Promise<Order> {
  const { data } = await http.post<Order>(`/orders/${orderId}/confirm`)
  return data
}

export type AgentOrderFilter = OrderStatus | 'all'

export async function fetchAgentOrders(
  status: AgentOrderFilter = 'paid',
): Promise<AgentOrder[]> {
  const { data } = await http.get<AgentOrder[]>('/agent/orders', {
    params: { status },
  })
  return data
}

export async function shipOrder(orderId: number): Promise<Order> {
  const { data } = await http.post<Order>(
    `/agent/orders/${orderId}/ship`,
  )
  return data
}
