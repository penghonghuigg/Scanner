import type { AuthUser } from '../types/auth'
import { apiRequest } from './http'

interface UserPayload { user: AuthUser }

export function login(username: string, password: string): Promise<UserPayload> {
  return apiRequest<UserPayload>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function getCurrentUser(): Promise<UserPayload> {
  return apiRequest<UserPayload>('/api/v1/auth/me')
}

export function logout(): Promise<Record<string, never>> {
  return apiRequest<Record<string, never>>('/api/v1/auth/logout', { method: 'POST' })
}
