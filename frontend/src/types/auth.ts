export const ROLE_VALUES = ['ADMIN', 'OPERATOR', 'VIEWER'] as const

export type Role = (typeof ROLE_VALUES)[number]

export const BRANCH_VALUES = ['TIANDA', 'XIEBA', 'PANJI', 'SHOUXIAN', 'FENGTAI'] as const

export type BranchCode = (typeof BRANCH_VALUES)[number]

export const BRANCH_NAMES: Record<BranchCode, string> = {
  TIANDA: '田大分局',
  XIEBA: '谢八分局',
  PANJI: '潘集分局',
  SHOUXIAN: '寿县局',
  FENGTAI: '凤台县局',
}

export interface AuthUser {
  id: number
  username: string
  display_name: string
  role: Role
  branch_code: BranchCode | null
  branch_name: string | null
}

export interface ApiError {
  code: string
  message: string
}

export interface SuccessEnvelope<T> {
  success: true
  data: T
  trace_id: string
}

export interface ErrorEnvelope {
  success: false
  error: ApiError
  trace_id: string
}
