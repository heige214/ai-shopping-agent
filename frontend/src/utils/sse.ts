import { getToken } from '@/utils/token'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

export type SSEHandler = (event: string, data: unknown) => void

function parseBlock(block: string, onEvent: SSEHandler): void {
  let event = 'message'
  const dataLines: string[] = []
  for (const rawLine of block.split('\n')) {
    const line = rawLine.replace(/\r$/, '')
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart())
    }
  }
  if (dataLines.length === 0) {
    return
  }
  try {
    onEvent(event, JSON.parse(dataLines.join('\n')))
  } catch {
    // 忽略无法解析的心跳/注释块
  }
}

async function responseError(response: Response): Promise<Error> {
  let message = '请求失败，请稍后重试'
  try {
    const data = (await response.json()) as { detail?: unknown }
    if (typeof data.detail === 'string') {
      message = data.detail
    }
  } catch {
    // 保持默认提示
  }
  return new Error(message)
}

/** fetch + ReadableStream 解析 POST SSE，避免 EventSource 无法带 Bearer 的问题。 */
export async function streamPost(
  path: string,
  body: unknown,
  onEvent: SSEHandler,
  signal?: AbortSignal,
): Promise<void> {
  const token = getToken()
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok) {
    throw await responseError(response)
  }
  if (!response.body) {
    throw new Error('当前浏览器不支持流式响应')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        break
      }
      buffer += decoder.decode(value, { stream: true })
      buffer = buffer.replace(/\r\n/g, '\n')
      let boundary = buffer.indexOf('\n\n')
      while (boundary >= 0) {
        const block = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        if (block.trim()) {
          parseBlock(block, onEvent)
        }
        boundary = buffer.indexOf('\n\n')
      }
    }
    buffer += decoder.decode()
    buffer = buffer.replace(/\r\n/g, '\n')
    if (buffer.trim()) {
      parseBlock(buffer, onEvent)
    }
  } finally {
    reader.releaseLock()
  }
}
