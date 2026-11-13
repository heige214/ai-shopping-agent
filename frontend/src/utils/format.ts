export function formatPrice(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}

export function formatRange(value?: number[] | null): string {
  if (!value || value.length === 0) {
    return '-'
  }
  return value.length === 1 ? String(value[0]) : `${value[0]}-${value[value.length - 1]}`
}

export function formatAttributeValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.join('、')
  }
  if (typeof value === 'string') {
    return value
  }
  if (typeof value === 'number') {
    return String(value)
  }
  return ''
}
