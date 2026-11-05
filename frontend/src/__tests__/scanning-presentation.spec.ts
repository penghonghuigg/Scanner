import {
  effectiveCartonCount,
  equivalentCartonCount,
  formatChinaDateTime,
  groupInventoryItems,
  referenceAmount,
} from '../utils/scanningPresentation'
import type { ScanSessionItem } from '../types/scanning'

function item(overrides: Partial<ScanSessionItem> = {}): ScanSessionItem {
  return {
    id: 1,
    product_id: 42,
    carton_count: 2,
    pack_count: 1,
    manual_delta_sticks: 200,
    total_sticks: 620,
    product_snapshot: {
      product_id: 42,
      carton_code: '6901028126427',
      pack_code: '6901028126428',
      brand: '黄山',
      standard_name: '黄山(七星皖烟)',
      carton_retail_price: '350.00',
      sticks_per_pack: 20,
      packs_per_carton: 10,
      sticks_per_carton: 200,
    },
    updated_at: '2026-08-31T07:47:22Z',
    ...overrides,
  }
}

test('计算人工调整后的整条数量、折合条数和参考金额', () => {
  const target = item()

  expect(effectiveCartonCount(target)).toBe(3)
  expect(equivalentCartonCount(target)).toBe(3.1)
  expect(referenceAmount(target)).toBe(1085)
})

test('同名不同条码版本分组并分别计算价格', () => {
  const second = item({
    id: 2,
    product_id: 43,
    carton_count: 1,
    pack_count: 0,
    manual_delta_sticks: 0,
    total_sticks: 200,
    product_snapshot: {
      ...item().product_snapshot,
      product_id: 43,
      carton_code: '6901028129999',
      pack_code: null,
      carton_retail_price: '400.00',
    },
  })

  const groups = groupInventoryItems([item(), second])

  expect(groups).toHaveLength(1)
  expect(groups[0]).toEqual(expect.objectContaining({
    standardName: '黄山(七星皖烟)',
    versionCount: 2,
    totalEquivalentCartons: 4.1,
    totalAmount: 1485,
  }))
  expect(groups[0]?.versions).toHaveLength(2)
})

test('中国标准时间显示完整日期和秒', () => {
  expect(formatChinaDateTime('2026-08-31T07:47:22Z')).toBe('2026/08/31 15:47:22')
})
