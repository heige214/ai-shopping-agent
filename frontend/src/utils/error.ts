import axios from 'axios'

interface ValidationErrorItem {
  msg?: string
}

export function getErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) {
    return '操作失败，请稍后重试'
  }

  const detail: unknown = error.response?.data?.detail
  if (typeof detail === 'string') {
    return detail
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as ValidationErrorItem
    if (typeof first?.msg === 'string') {
      return first.msg.replace(/^Value error, /, '')
    }
  }

  if (!error.response) {
    return '网络异常，请稍后重试'
  }
  return '操作失败，请稍后重试'
}
