import type {
  Address,
  AddressSnapshot,
  OrderStatus,
} from '@/types/commerce'

export const ORDER_STATUS_LABEL: Record<OrderStatus, string> = {
  pending_payment: '待付款',
  paid: '待发货',
  shipped: '待收货',
  completed: '已完成',
  cancelled: '已取消',
}

export const ORDER_STATUS_TAG: Record<
  OrderStatus,
  'primary' | 'success' | 'warning' | 'danger' | 'default'
> = {
  pending_payment: 'warning',
  paid: 'primary',
  shipped: 'primary',
  completed: 'success',
  cancelled: 'default',
}

export function formatFullAddress(
  address: Address | AddressSnapshot,
): string {
  return `${address.province}${address.city}${address.district}${address.detail}`
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return ''
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return ''
  }
  const pad = (part: number): string => String(part).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
    date.getDate(),
  )} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
