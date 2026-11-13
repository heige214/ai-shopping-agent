export type UserRole = 'user' | 'agent' | 'admin'

export interface User {
  id: number
  username: string
  nickname: string | null
  avatar_url: string | null
  role: UserRole
  height_cm: number | null
  weight_kg: number | null
  usual_size: string | null
  created_at: string
}

export interface LoginPayload {
  username: string
  password: string
}

export interface RegisterPayload {
  username: string
  password: string
  nickname?: string | null
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}
