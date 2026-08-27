import type { ErrorEnvelope, SuccessEnvelope } from '../types/auth'
import type {
  ImportIssue,
  Product,
  ProductImportResult,
  ProductInput,
  ProductListPayload,
  ProductPatch,
  ProductQuery,
} from '../types/catalog'
import { ApiRequestError, apiRequest } from './http'

export function listProducts(query: ProductQuery = {}): Promise<ProductListPayload> {
  const params = new URLSearchParams()
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value))
  })
  const suffix = params.size > 0 ? `?${params.toString()}` : ''
  return apiRequest<ProductListPayload>(`/api/v1/products${suffix}`)
}

export function createProduct(input: ProductInput): Promise<{ product: Product }> {
  return apiRequest<{ product: Product }>('/api/v1/products', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function updateProduct(id: number, input: ProductPatch): Promise<{ product: Product }> {
  return apiRequest<{ product: Product }>(`/api/v1/products/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(input),
  })
}

async function parseResponse<T>(response: Response): Promise<T> {
  const payload = (await response.json()) as SuccessEnvelope<T> | ErrorEnvelope
  if (!response.ok || !payload.success) {
    const failure = payload as ErrorEnvelope
    throw new ApiRequestError(
      failure.error?.message ?? '请求失败，请稍后重试',
      failure.error?.code ?? 'REQUEST_FAILED',
    )
  }
  return payload.data
}

export async function importProducts(file: File): Promise<ProductImportResult> {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch('/api/v1/products/import', {
    method: 'POST',
    body: form,
    credentials: 'include',
  })
  return parseResponse<ProductImportResult>(response)
}

export async function fetchImportTemplate(): Promise<Blob> {
  const response = await fetch('/api/v1/products/import-template.xlsx', {
    credentials: 'include',
  })
  if (!response.ok) throw new ApiRequestError('模板下载失败', 'PRODUCT_TEMPLATE_DOWNLOAD_FAILED')
  return response.blob()
}

function safeCsvCell(value: string | number): string {
  let text = String(value)
  if (/^[=+\-@]/.test(text)) text = `'${text}`
  return `"${text.replace(/"/g, '""')}"`
}

export function buildImportIssuesCsv(issues: ImportIssue[]): string {
  const headers = ['行号', '级别', '字段', '错误码', '说明', '条码', '品规名称']
  const rows = issues.map(issue => [
    issue.row_number,
    issue.level,
    issue.field,
    issue.code,
    issue.message,
    issue.carton_code,
    issue.standard_name,
  ])
  return `\uFEFF${[headers, ...rows].map(row => row.map(safeCsvCell).join(',')).join('\r\n')}`
}
