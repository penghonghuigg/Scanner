import type { ScanSessionItem } from '../types/scanning'

export interface InventoryGroup {
  standardName: string
  versionCount: number
  versions: ScanSessionItem[]
  totalEquivalentCartons: number
  totalAmount: number
  hasMissingPrice: boolean
}

function rounded(value: number): number {
  return Math.round((value + Number.EPSILON) * 10000) / 10000
}

export function effectiveCartonCount(item: ScanSessionItem): number {
  return rounded(
    item.carton_count
    + item.manual_delta_sticks / item.product_snapshot.sticks_per_carton,
  )
}

export function equivalentCartonCount(item: ScanSessionItem): number {
  return rounded(item.total_sticks / item.product_snapshot.sticks_per_carton)
}

export function referenceAmount(item: ScanSessionItem): number | null {
  if (item.product_snapshot.carton_retail_price === null) return null
  return rounded(
    equivalentCartonCount(item) * Number(item.product_snapshot.carton_retail_price),
  )
}

export function groupInventoryItems(items: ScanSessionItem[]): InventoryGroup[] {
  const groups = new Map<string, ScanSessionItem[]>()
  for (const item of items) {
    const name = item.product_snapshot.standard_name
    const versions = groups.get(name) ?? []
    versions.push(item)
    groups.set(name, versions)
  }
  return [...groups.entries()].map(([standardName, versions]) => {
    const amounts = versions.map(referenceAmount)
    return {
      standardName,
      versionCount: versions.length,
      versions,
      totalEquivalentCartons: rounded(
        versions.reduce((total, item) => total + equivalentCartonCount(item), 0),
      ),
      totalAmount: rounded(
        amounts.reduce((total: number, amount) => total + (amount ?? 0), 0),
      ),
      hasMissingPrice: amounts.some((amount) => amount === null),
    }
  })
}

export function formatChinaDateTime(value: string): string {
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(new Date(value))
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${values.year}/${values.month}/${values.day} ${values.hour}:${values.minute}:${values.second}`
}

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}
