import http from '@/api/http'
import type {
  LoginPayload,
  RegisterPayload,
  TokenResponse,
  User,
} from '@/types'

export async function register(payload: RegisterPayload): Promise<User> {
  const { data } = await http.post<User>('/auth/register', payload)
  return data
}

export async function login(payload: LoginPayload): Promise<TokenResponse> {
  const { data } = await http.post<TokenResponse>('/auth/login', payload)
  return data
}

export async function fetchMe(): Promise<User> {
  const { data } = await http.get<User>('/auth/me')
  return data
}
