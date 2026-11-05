import {
  addResultItem,
  adjustCartonQuantity,
  completeScanSession,
  createScanSession,
  downloadScanSessionExport,
  getRegionCatalog,
  getIntegrationSnapshot,
  getScanSession,
  getScanState,
  getSourceAllocations,
  listScanEvents,
  listScanSessions,
  importToJianDaoYun,
  removeScanSessionItem,
  replaceResultItem,
  replaceSourceAllocations,
  resolveAmbiguity,
  scanCode,
  searchProductOptions,
} from '../api/scanSessions'

function success(data: unknown) {
  return Promise.resolve(new Response(JSON.stringify({ success: true, data, trace_id: 'trace-1' }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  }))
}

beforeEach(() => {
  vi.restoreAllMocks()
})

test('新建批次按 SPEC 字段提交', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => success({ scan_session: {} }))

  await createScanSession({
    business_type: 'MARKET_INSPECTION',
    filing_case_no: '凤烟立〔2026〕001号',
    location: '凤台县城关镇',
    notes: '现场登记',
    branch_code: 'FENGTAI',
  })

  expect(fetchMock).toHaveBeenCalledWith('/api/v1/scan-sessions', expect.objectContaining({
    method: 'POST',
    credentials: 'include',
    body: JSON.stringify({
      business_type: 'MARKET_INSPECTION',
      filing_case_no: '凤烟立〔2026〕001号',
      location: '凤台县城关镇',
      notes: '现场登记',
      branch_code: 'FENGTAI',
    }),
  }))
})

test('批次列表和详情使用统一资源路径', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => success({ items: [], total: 0 }))

  await listScanSessions({ status: 'DRAFT', page: 2, page_size: 20 })
  await getScanSession(18)

  expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/scan-sessions?status=DRAFT&page=2&page_size=20')
  expect(fetchMock.mock.calls[1]?.[0]).toBe('/api/v1/scan-sessions/18')
})

test('批次列表关键词经过 URL 编码后提交', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => success({ items: [], total: 0 }))

  await listScanSessions({ query: '凤烟立〔2026〕 001号', status: 'DRAFT', page: 1, page_size: 20 })

  expect(fetchMock.mock.calls[0]?.[0]).toBe(
    '/api/v1/scan-sessions?query=%E5%87%A4%E7%83%9F%E7%AB%8B%E3%80%942026%E3%80%95+001%E5%8F%B7&status=DRAFT&page=1&page_size=20',
  )
})

test('扫码、歧义解决和状态查询使用阶段五契约', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => success({}))

  await scanCode(18, {
    request_id: '00000000-0000-4000-8000-000000000201',
    code: '6900000000101',
  })
  await resolveAmbiguity(18, {
    request_id: '00000000-0000-4000-8000-000000000202',
    event_id: 31,
    product_id: 42,
  })
  await getScanState(18)

  expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/scan-sessions/18/scan')
  expect(fetchMock.mock.calls[0]?.[1]).toEqual(expect.objectContaining({
    method: 'POST',
    body: JSON.stringify({
      request_id: '00000000-0000-4000-8000-000000000201',
      code: '6900000000101',
    }),
  }))
  expect(fetchMock.mock.calls[1]?.[0]).toBe('/api/v1/scan-sessions/18/resolve')
  expect(fetchMock.mock.calls[1]?.[1]).toEqual(expect.objectContaining({
    method: 'POST',
    body: JSON.stringify({
      request_id: '00000000-0000-4000-8000-000000000202',
      event_id: 31,
      product_id: 42,
    }),
  }))
  expect(fetchMock.mock.calls[2]?.[0]).toBe('/api/v1/scan-sessions/18/scan-state')
})

test('人工调整和流水分页使用阶段 5B 契约', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => success({}))

  await adjustCartonQuantity(18, 42, {
    request_id: '00000000-0000-4000-8000-000000000203',
    operation: 'DELTA',
    quantity: 1,
    reason_type: 'ONSITE_VERIFICATION',
    reason_note: '',
  })
  await removeScanSessionItem(18, 42, {
    request_id: '00000000-0000-4000-8000-000000000204',
  })
  await listScanEvents(18, { page: 2, page_size: 10 })

  expect(fetchMock.mock.calls[0]?.[0]).toBe(
    '/api/v1/scan-sessions/18/items/42/carton-quantity',
  )
  expect(fetchMock.mock.calls[0]?.[1]).toEqual(expect.objectContaining({
    method: 'POST',
    body: JSON.stringify({
      request_id: '00000000-0000-4000-8000-000000000203',
      operation: 'DELTA',
      quantity: 1,
      reason_type: 'ONSITE_VERIFICATION',
      reason_note: '',
    }),
  }))
  expect(fetchMock.mock.calls[1]?.[0]).toBe(
    '/api/v1/scan-sessions/18/items/42/remove',
  )
  expect(fetchMock.mock.calls[1]?.[1]).toEqual(expect.objectContaining({
    method: 'POST',
    body: JSON.stringify({
      request_id: '00000000-0000-4000-8000-000000000204',
    }),
  }))
  expect(fetchMock.mock.calls[2]?.[0]).toBe(
    '/api/v1/scan-sessions/18/events?page=2&page_size=10',
  )
})

test('来源拆分、完成批次和 Excel 下载使用阶段 6+7 契约', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch')
    .mockImplementationOnce(() => success({ source_types: [], provinces: [] }))
    .mockImplementationOnce(() => success({ items: [] }))
    .mockImplementationOnce(() => success({ product_id: 42 }))
    .mockImplementationOnce(() => success({ scan_session: { status: 'COMPLETED' } }))
    .mockResolvedValueOnce(new Response(new Blob(['xlsx']), {
      status: 200,
      headers: {
        'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'Content-Disposition': "attachment; filename*=UTF-8''%E6%B6%89%E6%A1%88.xlsx",
      },
    }))

  await getRegionCatalog()
  await getSourceAllocations(18)
  await replaceSourceAllocations(18, 42, {
    items: [{ source_type: 'UNKNOWN', province_name: null, city_name: null, pack_count: 10 }],
  })
  await completeScanSession(18, { confirm_exceptions: true })
  const downloaded = await downloadScanSessionExport(18)

  expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
    '/api/v1/regions',
    '/api/v1/scan-sessions/18/source-allocations',
    '/api/v1/scan-sessions/18/items/42/source-allocations',
    '/api/v1/scan-sessions/18/complete',
    '/api/v1/scan-sessions/18/export.xlsx',
  ])
  expect(fetchMock.mock.calls[2]?.[1]).toEqual(expect.objectContaining({
    method: 'PUT',
    body: JSON.stringify({
      items: [{ source_type: 'UNKNOWN', province_name: null, city_name: null, pack_count: 10 }],
    }),
  }))
  expect(fetchMock.mock.calls[3]?.[1]).toEqual(expect.objectContaining({
    method: 'POST',
    body: JSON.stringify({ confirm_exceptions: true }),
  }))
  expect(downloaded.filename).toBe('涉案.xlsx')
  expect(downloaded.blob).toBeInstanceOf(Blob)
  expect(downloaded.blob.size).toBeGreaterThan(0)
})

test('已完成结果品规查询、新增和替换使用修订契约', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => success({}))

  await searchProductOptions('129756', 1, 20)
  await addResultItem(18, {
    request_id: '00000000-0000-4000-8000-000000000205',
    product_id: 42,
    quantity_cartons: 1.2,
    source_allocations: [
      { source_type: 'OUTSIDE_PROVINCE', province_name: '天津市', city_name: '不详', pack_count: 12 },
    ],
  })
  await replaceResultItem(18, 42, {
    request_id: '00000000-0000-4000-8000-000000000206',
    quantity_cartons: 0.5,
    source_allocations: [
      { source_type: 'UNKNOWN', province_name: null, city_name: null, pack_count: 5 },
    ],
  })

  expect(fetchMock.mock.calls[0]?.[0]).toBe(
    '/api/v1/product-options?query=129756&page=1&page_size=20',
  )
  expect(fetchMock.mock.calls[1]).toEqual([
    '/api/v1/scan-sessions/18/result-items',
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({
        request_id: '00000000-0000-4000-8000-000000000205',
        product_id: 42,
        quantity_cartons: 1.2,
        source_allocations: [
          { source_type: 'OUTSIDE_PROVINCE', province_name: '天津市', city_name: '不详', pack_count: 12 },
        ],
      }),
    }),
  ])
  expect(fetchMock.mock.calls[2]).toEqual([
    '/api/v1/scan-sessions/18/result-items/42',
    expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({
        request_id: '00000000-0000-4000-8000-000000000206',
        quantity_cartons: 0.5,
        source_allocations: [
          { source_type: 'UNKNOWN', province_name: null, city_name: null, pack_count: 5 },
        ],
      }),
    }),
  ])
})

test('简道云快照查询和一键导入使用阶段 8 契约', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => success({ snapshot: null }))

  await getIntegrationSnapshot(18)
  await importToJianDaoYun(18)

  expect(fetchMock.mock.calls[0]?.[0]).toBe(
    '/api/v1/scan-sessions/18/integration-snapshot',
  )
  expect(fetchMock.mock.calls[1]).toEqual([
    '/api/v1/scan-sessions/18/jiandaoyun-import',
    expect.objectContaining({ method: 'POST', credentials: 'include' }),
  ])
})
