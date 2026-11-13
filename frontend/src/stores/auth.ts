import axios from 'axios'
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import * as authApi from '@/api/auth'
import type {
  LoginPayload,
  RegisterPayload,
  TokenResponse,
  User,
} from '@/types'
import { clearToken, getToken, setToken } from '@/utils/token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getToken())
  const user = ref<User | null>(null)
  const initialized = ref(false)
  let pending: Promise<void> | null = null

  const isAuthenticated = computed(() => Boolean(token.value))

  function applyLogin(data: TokenResponse): void {
    token.value = data.access_token
    user.value = data.user
    setToken(data.access_token)
    initialized.value = true
  }

  function clear(): void {
    token.value = null
    user.value = null
    initialized.value = true
    clearToken()
  }

  async function login(payload: LoginPayload): Promise<void> {
    applyLogin(await authApi.login(payload))
  }

  async function registerAndLogin(payload: RegisterPayload): Promise<void> {
    await authApi.register(payload)
    await login({ username: payload.username, password: payload.password })
  }

  async function loadUser(): Promise<void> {
    try {
      user.value = await authApi.fetchMe()
      initialized.value = true
    } catch (error) {
      // 只有明确的 401 才清登录态；网络错误/5xx 保留 token，下次导航再重试
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        clear()
      }
    }
  }

  function ensureUserLoaded(): Promise<void> {
    if (initialized.value) {
      return Promise.resolve()
    }
    if (!token.value) {
      initialized.value = true
      return Promise.resolve()
    }
    // 并发导航只发一次 /auth/me
    pending ??= loadUser().finally(() => {
      pending = null
    })
    return pending
  }

  function logout(): void {
    clear()
  }

  return {
    token,
    user,
    initialized,
    isAuthenticated,
    login,
    registerAndLogin,
    ensureUserLoaded,
    logout,
    clear,
  }
})
