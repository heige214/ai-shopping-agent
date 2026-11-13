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

  async function ensureUserLoaded(): Promise<void> {
    if (initialized.value) {
      return
    }
    if (!token.value) {
      initialized.value = true
      return
    }
    try {
      user.value = await authApi.fetchMe()
    } catch {
      clear()
    } finally {
      initialized.value = true
    }
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
