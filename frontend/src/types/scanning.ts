import type { BranchCode } from './auth'

export const BUSINESS_TYPES = [
  { value: 'MARKET_INSPECTION', label: '市场检查', description: '市场日常检查及现场查获' },
  { value: 'DELIVERY_CHANNEL', label: '寄递渠道', description: '快递、物流等寄递环节' },
  { value: 'SPECIAL_TRANSPORT', label: '专车运输', description: '车辆运输及路面查缉' },
  { value: 'OTHER', label: '其他', description: '不属于以上类型的业务' },
] as const

export type BusinessType = (typeof BUSINESS_TYPES)[number]['value']
export type ScanSessionStatus = 'DRAFT' | 'COMPLETED'
export type IntegrationStatus = 'PENDING' | 'SUCCEEDED' | 'FAILED' | 'UNCERTAIN'

export interface IntegrationSnapshot {
  status: IntegrationStatus
  external_data_id: string | null
  attempt_count: number
  last_error_code: string | null
  last_error_message: string | null
  created_at: string
  updated_at: string
  succeeded_at: string | null
}

export interface IntegrationSnapshotPayload {
  snapshot: IntegrationSnapshot | null
}

export interface ScanSession {
  id: number
  session_no: string
  business_type: BusinessType
  business_type_name: string
  filing_case_no: string | null
  location: string | null
  notes: string | null
  branch_code: BranchCode
  branch_name: string
  operator_id: number
  operator_name: string
  status: ScanSessionStatus
  status_name: string
  product_count: number
  total_sticks: number
  display_label: string
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface CreateScanSessionInput {
  business_type: BusinessType
  filing_case_no?: string
  location?: string
  notes?: string
  branch_code?: BranchCode
}

export interface ScanSessionQuery {
  query?: string
  status?: ScanSessionStatus
  page?: number
  page_size?: number
}

export interface ScanSessionListPayload {
  items: ScanSession[]
  total: number
  page: number
  page_size: number
}

export type ScanResult = 'SUCCESS' | 'UNKNOWN' | 'AMBIGUOUS'
export type ScanEventType = 'SCAN' | 'RESOLVE' | 'ADJUST'
export type ScanUnitType = 'CARTON' | 'PACK' | 'STICK'

export interface ProductSnapshot {
  product_id: number
  carton_code: string
  pack_code: string | null
  brand: string
  standard_name: string
  carton_retail_price: string | null
  sticks_per_pack: number
  packs_per_carton: number
  sticks_per_carton: number
}

export interface ScanSessionItem {
  id: number
  product_id: number
  carton_count: number
  pack_count: number
  manual_delta_sticks: number
  total_sticks: number
  product_snapshot: ProductSnapshot
  updated_at: string
}

export interface ScanEvent {
  id: number
  request_id: string
  event_type: ScanEventType
  result: ScanResult
  raw_code: string
  product_id: number | null
  unit_type: ScanUnitType | null
  delta_sticks: number
  reason: string | null
  source_event_id: number | null
  candidate_snapshot: ProductSnapshot[] | null
  product_snapshot: ProductSnapshot | null
  operator_id: number
  operator_name: string
  resolved: boolean
  created_at: string
}

export interface ScanSummary {
  product_count: number
  carton_count: number
  pack_count: number
  total_sticks: number
  unknown_count: number
  ambiguous_count: number
}

export interface ScanState {
  summary: ScanSummary
  items: ScanSessionItem[]
  recent_events: ScanEvent[]
  pending_ambiguities: ScanEvent[]
  catalog_summary: CatalogSummary
  latest_successful_event: ScanEvent | null
}

export interface CatalogSummary {
  active_code_count: number
  active_standard_product_count: number
}

export interface ScanCodeInput {
  request_id: string
  code: string
}

export interface ResolveAmbiguityInput {
  request_id: string
  event_id: number
  product_id: number
}

export interface AdjustCartonQuantityInput {
  request_id: string
  operation: 'DELTA' | 'SET'
  quantity: number
  reason_type: AdjustmentReasonType
  reason_note?: string
}

export type AdjustmentReasonType =
  | 'ONSITE_VERIFICATION'
  | 'SCAN_CORRECTION'
  | 'LOOSE_PACK_VERIFICATION'
  | 'OTHER'

export type SourceType =
  | 'OUTSIDE_PROVINCE'
  | 'UNKNOWN'
  | 'LOCAL_HUAINAN'
  | 'ANHUI_OTHER_CITY'

export interface SourceTypeOption {
  value: SourceType
  label: string
}

export interface RegionProvince {
  name: string
  cities: Array<{ name: string }>
}

export interface RegionCatalog {
  source_types: SourceTypeOption[]
  provinces: RegionProvince[]
}

export interface SourceAllocationInput {
  source_type: SourceType
  province_name: string | null
  city_name: string | null
  pack_count: number
}

export interface SourceAllocation extends SourceAllocationInput {
  id: number
  source_type_name: string
  equivalent_cartons: string
  quantity_sticks: number
}

export interface ProductSourceAllocationState {
  product_id: number
  product_snapshot: ProductSnapshot
  required_pack_count: number
  allocated_pack_count: number
  remaining_pack_count: number
  allocations: SourceAllocation[]
}

export interface ProductOption {
  id: number
  carton_code: string
  brand: string
  standard_name: string
  carton_retail_price: string | null
  sticks_per_pack: number
  packs_per_carton: number
}

export interface ProductOptionListPayload {
  items: ProductOption[]
  total: number
  page: number
  page_size: number
}

export interface ResultItemInput {
  request_id: string
  quantity_cartons: number
  source_allocations: SourceAllocationInput[]
}

export interface AddResultItemInput extends ResultItemInput {
  product_id: number
}

export interface ResultItemOperation {
  item: ScanSessionItem
  source_state: ProductSourceAllocationState
  event: ScanEvent
  idempotent_replay: boolean
}

export interface SourceAllocationListPayload {
  items: ProductSourceAllocationState[]
}

export interface CompleteScanSessionInput {
  confirm_exceptions: boolean
}

export interface CompletionSummary {
  scan_session: ScanSession
  summary: ScanSummary
  source_product_count: number
  source_allocated_product_count: number
  unknown_count: number
  unresolved_ambiguity_count: number
}

export interface DownloadedFile {
  blob: Blob
  filename: string
}

export interface RemoveScanSessionItemInput {
  request_id: string
}

export interface ScanEventQuery {
  page: number
  page_size: number
}

export interface ScanEventPage {
  items: ScanEvent[]
  total: number
  page: number
  page_size: number
}

export interface ScanOperation {
  event: ScanEvent
  state: ScanState
  idempotent_replay: boolean
}
