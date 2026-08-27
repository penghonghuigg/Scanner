import type { ErrorEnvelope, SuccessEnvelope } from '../types/auth'

export class ApiRequestError extends Error {
  constructor(message: string, public readonly code: string) {
    super(message)
  }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  const payload = (await response.json()) as SuccessEnvelope<T> | ErrorEnvelope
  if (!response.ok || !payload.success) {
    const error = payload as ErrorEnvelope
    throw new ApiRequestError(error.error?.message ?? '请求失败，请稍后重试', error.error?.code ?? 'REQUEST_FAILED')
  }
  return payload.data
}
