import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

import { AUTH_EXPIRED_EVENT } from '@/utils/auth-events'
import { clearToken, getToken } from '@/utils/token'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 15000,
})

http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig | undefined
    const isLoginRequest = original?.url?.split('?')[0] === '/auth/login'

    // 登录接口本身返回 401 时只提示，不触发全局退出
    if (error.response?.status === 401 && !isLoginRequest) {
      clearToken()
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT))
      }
    }
    return Promise.reject(error)
  },
)

export default http
