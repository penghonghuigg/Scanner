import {
  createScanSession,
  getScanSession,
  getScanState,
  listScanSessions,
  resolveAmbiguity,
  scanCode,
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
