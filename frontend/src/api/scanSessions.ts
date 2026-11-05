import { ApiRequestError, apiRequest } from './http'
import type {
  AdjustCartonQuantityInput,
  AddResultItemInput,
  CompleteScanSessionInput,
  CompletionSummary,
  CreateScanSessionInput,
  DownloadedFile,
  IntegrationSnapshotPayload,
  ProductSourceAllocationState,
  ProductOptionListPayload,
  RegionCatalog,
  ResultItemInput,
  ResultItemOperation,
  ResolveAmbiguityInput,
  RemoveScanSessionItemInput,
  ScanCodeInput,
  ScanEventPage,
  ScanEventQuery,
  ScanOperation,
  ScanSession,
  ScanSessionListPayload,
  ScanSessionQuery,
  ScanState,
  SourceAllocationInput,
  SourceAllocationListPayload,
} from '../types/scanning'

export function searchProductOptions(query: string, page = 1, pageSize = 20) {
  const params = new URLSearchParams({
    query,
    page: String(page),
    page_size: String(pageSize),
  })
  return apiRequest<ProductOptionListPayload>(`/api/v1/product-options?${params.toString()}`)
}

export function addResultItem(id: number, input: AddResultItemInput) {
  return apiRequest<ResultItemOperation>(`/api/v1/scan-sessions/${id}/result-items`, {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function replaceResultItem(id: number, productId: number, input: ResultItemInput) {
  return apiRequest<ResultItemOperation>(
    `/api/v1/scan-sessions/${id}/result-items/${productId}`,
    { method: 'PUT', body: JSON.stringify(input) },
  )
}

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

export function getIntegrationSnapshot(id: number) {
  return apiRequest<IntegrationSnapshotPayload>(
    `/api/v1/scan-sessions/${id}/integration-snapshot`,
  )
}

export function importToJianDaoYun(id: number) {
  return apiRequest<IntegrationSnapshotPayload>(
    `/api/v1/scan-sessions/${id}/jiandaoyun-import`,
    { method: 'POST' },
  )
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

export function adjustCartonQuantity(
  id: number,
  productId: number,
  input: AdjustCartonQuantityInput,
) {
  return apiRequest<ScanOperation>(
    `/api/v1/scan-sessions/${id}/items/${productId}/carton-quantity`,
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
  )
}

export function removeScanSessionItem(
  id: number,
  productId: number,
  input: RemoveScanSessionItemInput,
) {
  return apiRequest<ScanOperation>(
    `/api/v1/scan-sessions/${id}/items/${productId}/remove`,
    {
      method: 'POST',
      body: JSON.stringify(input),
    },
  )
}

export function listScanEvents(id: number, query: ScanEventQuery) {
  const params = new URLSearchParams({
    page: String(query.page),
    page_size: String(query.page_size),
  })
  return apiRequest<ScanEventPage>(`/api/v1/scan-sessions/${id}/events?${params.toString()}`)
}

export function getRegionCatalog() {
  return apiRequest<RegionCatalog>('/api/v1/regions')
}

export function getSourceAllocations(id: number) {
  return apiRequest<SourceAllocationListPayload>(
    `/api/v1/scan-sessions/${id}/source-allocations`,
  )
}

export function replaceSourceAllocations(
  id: number,
  productId: number,
  input: { items: SourceAllocationInput[] },
) {
  return apiRequest<ProductSourceAllocationState>(
    `/api/v1/scan-sessions/${id}/items/${productId}/source-allocations`,
    { method: 'PUT', body: JSON.stringify(input) },
  )
}

export function completeScanSession(id: number, input: CompleteScanSessionInput) {
  return apiRequest<CompletionSummary>(`/api/v1/scan-sessions/${id}/complete`, {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

function contentDispositionFilename(value: string | null): string {
  if (!value) return '涉案卷烟统计.xlsx'
  const utf8 = value.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  if (utf8) return decodeURIComponent(utf8)
  return value.match(/filename="?([^";]+)"?/i)?.[1] ?? '涉案卷烟统计.xlsx'
}

export async function downloadScanSessionExport(id: number): Promise<DownloadedFile> {
  const response = await fetch(`/api/v1/scan-sessions/${id}/export.xlsx`, {
    credentials: 'include',
  })
  if (!response.ok) {
    let message = 'Excel 导出失败，请稍后重试'
    let code = 'EXPORT_FAILED'
    try {
      const payload = await response.json() as {
        error?: { message?: string; code?: string }
      }
      message = payload.error?.message ?? message
      code = payload.error?.code ?? code
    } catch {
      // 非 JSON 错误响应使用统一提示。
    }
    throw new ApiRequestError(message, code)
  }
  return {
    blob: await response.blob(),
    filename: contentDispositionFilename(response.headers.get('Content-Disposition')),
  }
}
