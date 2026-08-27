function productFixture() {
  return {
    id: 1,
    carton_code: '6901028000011',
    pack_code: '6901028000028',
    brand: '测试品牌',
    standard_name: '测试品牌（经典）',
    carton_retail_price: '100.00',
    pack_retail_price: '10.00',
    sticks_per_pack: 20,
    packs_per_carton: 10,
    sticks_per_carton: 200,
    is_pack_ambiguous: false,
    is_active: true,
    created_at: '2026-08-27T08:00:00',
    updated_at: '2026-08-27T08:00:00',
  }
}

beforeEach(() => {
  vi.restoreAllMocks()
})

test('品规查询和新增使用同源 API 与 Cookie', async () => {
  const products = await import('../api/products')
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({
      success: true,
      data: {
        items: [productFixture()],
        total: 1,
        page: 1,
        page_size: 20,
        summary: { total_count: 1, active_count: 1, inactive_count: 0, ambiguous_count: 0 },
      },
      trace_id: 'trace-1',
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    .mockResolvedValueOnce(new Response(JSON.stringify({
      success: true,
      data: { product: productFixture() },
      trace_id: 'trace-2',
    }), { status: 201, headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetchMock)

  await products.listProducts({ query: '经典', page: 1, page_size: 20 })
  await products.createProduct({
    carton_code: '6901028000011',
    pack_code: '6901028000028',
    brand: '测试品牌',
    standard_name: '测试品牌（经典）',
    carton_retail_price: '100.00',
    sticks_per_pack: 20,
    packs_per_carton: 10,
    is_active: true,
  })

  expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/products?query=%E7%BB%8F%E5%85%B8&page=1&page_size=20')
  expect((fetchMock.mock.calls[0]?.[1] as RequestInit).credentials).toBe('include')
  expect(fetchMock.mock.calls[1]?.[0]).toBe('/api/v1/products')
  expect(JSON.parse((fetchMock.mock.calls[1]?.[1] as RequestInit).body as string).carton_code)
    .toBe('6901028000011')
})

test('Excel 导入使用 FormData 且不手工设置 Content-Type', async () => {
  const products = await import('../api/products')
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
    success: true,
    data: {
      total_rows: 1,
      created_count: 1,
      updated_count: 0,
      skipped_count: 0,
      warning_count: 0,
      issues: [],
    },
    trace_id: 'trace-import',
  }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  vi.stubGlobal('fetch', fetchMock)

  await products.importProducts(new File(['xlsx'], 'products.xlsx'))

  const request = fetchMock.mock.calls[0]?.[1] as RequestInit
  expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/products/import')
  expect(request.body).toBeInstanceOf(FormData)
  expect(request.headers).toBeUndefined()
  expect(request.credentials).toBe('include')
})

test('Excel 模板下载地址与 SPEC 及后端路由一致', async () => {
  const products = await import('../api/products')
  const fetchMock = vi.fn().mockResolvedValue(new Response('xlsx', { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)

  await products.fetchImportTemplate()

  expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/products/import-template.xlsx')
  expect((fetchMock.mock.calls[0]?.[1] as RequestInit).credentials).toBe('include')
})

test('问题 CSV 防止来源单元格触发公式', async () => {
  const products = await import('../api/products')

  const csv = products.buildImportIssuesCsv([{
    row_number: 2,
    level: 'ERROR',
    field: '品规名称',
    code: 'PRODUCT_REQUIRED_FIELD_MISSING',
    message: '字段不能为空',
    carton_code: '6901028000011',
    standard_name: '=HYPERLINK("bad")',
  }])

  expect(csv).toContain("'=HYPERLINK")
})
