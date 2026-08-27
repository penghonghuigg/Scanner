import { apiRequest } from './http'
import type {
  CreateScanSessionInput,
  ResolveAmbiguityInput,
  ScanCodeInput,
  ScanOperation,
  ScanSession,
  ScanSessionListPayload,
  ScanSessionQuery,
  ScanState,
} from '../types/scanning'

export function createScanSession(input: CreateScanSessionInput) {
  return apiRequest<{ scan_session: ScanSession }>('/api/v1/scan-sessions', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function listScanSessions(query: ScanSessionQuery = {}) {
  const params = new URLSearchParams()
  if (query.query) params.set('query', query.query)
  if (query.status) params.set('status', query.status)
  if (query.page) params.set('page', String(query.page))
  if (query.page_size) params.set('page_size', String(query.page_size))
  const suffix = params.size ? `?${params.toString()}` : ''
  return apiRequest<ScanSessionListPayload>(`/api/v1/scan-sessions${suffix}`)
}

export function getScanSession(id: number) {
  return apiRequest<{ scan_session: ScanSession }>(`/api/v1/scan-sessions/${id}`)
}

export function scanCode(id: number, input: ScanCodeInput) {
  return apiRequest<ScanOperation>(`/api/v1/scan-sessions/${id}/scan`, {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function resolveAmbiguity(id: number, input: ResolveAmbiguityInput) {
  return apiRequest<ScanOperation>(`/api/v1/scan-sessions/${id}/resolve`, {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function getScanState(id: number) {
  return apiRequest<ScanState>(`/api/v1/scan-sessions/${id}/scan-state`)
}
