import type { AuthUser, BranchCode } from '../types/auth'
import { apiRequest } from './http'

export interface RegisterUserInput {
  username: string
  display_name: string
  branch_code: BranchCode
  password: string
  password_confirmation: string
}

export function registerUser(input: RegisterUserInput): Promise<{ user: AuthUser }> {
  return apiRequest<{ user: AuthUser }>('/api/v1/users', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}
