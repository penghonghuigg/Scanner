export interface Product {
  id: number
  carton_code: string
  pack_code: string | null
  brand: string
  standard_name: string
  carton_retail_price: string | null
  pack_retail_price: string | null
  sticks_per_pack: number
  packs_per_carton: number
  sticks_per_carton: number
  is_pack_ambiguous: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ProductInput {
  carton_code: string
  pack_code: string | null
  brand: string
  standard_name: string
  carton_retail_price: string | null
  sticks_per_pack: number
  packs_per_carton: number
  is_active: boolean
}

export type ProductPatch = Partial<ProductInput>

export interface ProductSummary {
  total_count: number
  active_count: number
  inactive_count: number
  ambiguous_count: number
}

export interface ProductListPayload {
  items: Product[]
  total: number
  page: number
  page_size: number
  summary: ProductSummary
}

export interface ProductQuery {
  query?: string
  is_active?: boolean
  ambiguous?: boolean
  page?: number
  page_size?: number
}

export interface ImportIssue {
  row_number: number
  level: 'ERROR' | 'WARNING'
  field: string
  code: string
  message: string
  carton_code: string
  standard_name: string
}

export interface ProductImportResult {
  total_rows: number
  created_count: number
  updated_count: number
  skipped_count: number
  warning_count: number
  issues: ImportIssue[]
}
