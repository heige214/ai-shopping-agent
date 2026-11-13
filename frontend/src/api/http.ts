import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

import { clearToken, getToken } from '@/utils/token'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api',
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
    const isLoginRequest = original?.url?.includes('/auth/login')

    // 登录接口本身返回 401 时只提示，不触发全局退出
    if (error.response?.status === 401 && !isLoginRequest) {
      clearToken()
      window.dispatchEvent(new CustomEvent('auth:expired'))
    }
    return Promise.reject(error)
  },
)

export default http
