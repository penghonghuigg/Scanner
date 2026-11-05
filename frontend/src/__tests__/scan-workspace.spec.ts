import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import SourceAllocationDialog from '../components/scanning/SourceAllocationDialog.vue'
import { useAuthStore } from '../stores/auth'

const apiMocks = vi.hoisted(() => ({
  addResultItem: vi.fn(),
  adjustCartonQuantity: vi.fn(),
  completeScanSession: vi.fn(),
  downloadScanSessionExport: vi.fn(),
  getRegionCatalog: vi.fn(),
  getIntegrationSnapshot: vi.fn(),
  getScanSession: vi.fn(),
  getScanState: vi.fn(),
  getSourceAllocations: vi.fn(),
  listScanEvents: vi.fn(),
  importToJianDaoYun: vi.fn(),
  removeScanSessionItem: vi.fn(),
  replaceResultItem: vi.fn(),
  replaceSourceAllocations: vi.fn(),
  scanCode: vi.fn(),
  searchProductOptions: vi.fn(),
  resolveAmbiguity: vi.fn(),
}))
vi.mock('../api/scanSessions', () => apiMocks)

const sessionFixture = {
  id: 8,
  session_no: 'PD20260827-163000-0001',
  business_type: 'MARKET_INSPECTION',
  business_type_name: '市场检查',
  filing_case_no: '凤烟立〔2026〕001号',
  location: '凤台县城关镇',
  notes: null,
  branch_code: 'FENGTAI',
  branch_name: '凤台县局',
  operator_id: 2,
  operator_name: '张三',
  status: 'DRAFT',
  status_name: '进行中',
  product_count: 0,
  total_sticks: 0,
  display_label: '2026-08-27 16:30—张三—0个品规—0支卷烟',
  completed_at: null,
  created_at: '2026-08-27T08:30:00Z',
  updated_at: '2026-08-27T08:30:00Z',
} as const

const product = {
  product_id: 42,
  carton_code: '6900000000101',
  pack_code: '6900000000102',
  brand: '测试品牌',
  standard_name: '测试卷烟',
  carton_retail_price: '100.00',
  sticks_per_pack: 20,
  packs_per_carton: 10,
  sticks_per_carton: 200,
}

const emptyState = {
  summary: {
    product_count: 0,
    carton_count: 0,
    pack_count: 0,
    total_sticks: 0,
    unknown_count: 0,
    ambiguous_count: 0,
  },
  items: [],
  recent_events: [],
  pending_ambiguities: [],
  catalog_summary: {
    active_code_count: 41,
    active_standard_product_count: 39,
  },
  latest_successful_event: null,
}

function successOperation(result: 'SUCCESS' | 'UNKNOWN' | 'AMBIGUOUS' = 'SUCCESS') {
  const event = {
    id: 31,
    request_id: '00000000-0000-4000-8000-000000000201',
    event_type: 'SCAN',
    result,
    raw_code: '6900000000101',
    product_id: result === 'SUCCESS' ? 42 : null,
    unit_type: result === 'SUCCESS' ? 'CARTON' : null,
    delta_sticks: result === 'SUCCESS' ? 200 : 0,
    reason: null,
    source_event_id: null,
    candidate_snapshot: result === 'AMBIGUOUS' ? [product] : null,
    product_snapshot: result === 'SUCCESS' ? product : null,
    operator_id: 2,
    operator_name: '张三',
    resolved: false,
    created_at: '2026-08-27T08:31:00Z',
  }
  const state = result === 'SUCCESS'
    ? {
        summary: { ...emptyState.summary, product_count: 1, carton_count: 1, total_sticks: 200 },
        items: [{
          id: 11, product_id: 42, carton_count: 1, pack_count: 0,
          manual_delta_sticks: 0, total_sticks: 200, product_snapshot: product,
          updated_at: '2026-08-27T08:31:00Z',
        }],
        recent_events: [event],
        pending_ambiguities: [],
        catalog_summary: emptyState.catalog_summary,
        latest_successful_event: event,
      }
    : {
        ...emptyState,
        summary: {
          ...emptyState.summary,
          unknown_count: result === 'UNKNOWN' ? 1 : 0,
          ambiguous_count: result === 'AMBIGUOUS' ? 1 : 0,
        },
        recent_events: [event],
        pending_ambiguities: result === 'AMBIGUOUS' ? [event] : [],
      }
  return { event, state, idempotent_replay: false }
}

function activateUser(role: 'OPERATOR' | 'VIEWER' = 'OPERATOR') {
  setActivePinia(createPinia())
  const auth = useAuthStore()
  auth.user = {
    id: 2,
    username: 'zhangsan',
    display_name: '张三',
    role,
    branch_code: 'FENGTAI',
    branch_name: '凤台县局',
  }
  auth.initialized = true
}

async function mountWorkspace(role: 'OPERATOR' | 'VIEWER' = 'OPERATOR') {
  activateUser(role)
  const { default: ScanWorkspaceView } = await import('../views/ScanWorkspaceView.vue')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/scan-sessions/:id/scan', component: ScanWorkspaceView }],
  })
  await router.push('/scan-sessions/8/scan')
  await router.isReady()
  const wrapper = mount(ScanWorkspaceView, {
    attachTo: document.body,
    global: { plugins: [router] },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  document.body.innerHTML = ''
  apiMocks.getScanSession.mockResolvedValue({ scan_session: sessionFixture })
  apiMocks.getScanState.mockResolvedValue(emptyState)
  apiMocks.getRegionCatalog.mockResolvedValue({
    source_types: [
      { value: 'OUTSIDE_PROVINCE', label: '外省流入' },
      { value: 'UNKNOWN', label: '来源不详' },
      { value: 'LOCAL_HUAINAN', label: '市内串码' },
      { value: 'ANHUI_OTHER_CITY', label: '省内市外' },
    ],
    provinces: [
      { name: '北京市', cities: [{ name: '北京市' }] },
      { name: '安徽省', cities: [{ name: '合肥市' }, { name: '淮南市' }] },
    ],
  })
  apiMocks.getSourceAllocations.mockResolvedValue({ items: [] })
  apiMocks.getIntegrationSnapshot.mockResolvedValue({ snapshot: null })
  apiMocks.listScanEvents.mockResolvedValue({
    items: [], total: 0, page: 1, page_size: 10,
  })
})

test('输入达到 13 位也不自动提交，按回车后才识别', async () => {
  apiMocks.scanCode.mockResolvedValue(successOperation())
  const wrapper = await mountWorkspace()
  const input = wrapper.get('input[name="scan_code"]')

  expect(document.activeElement).toBe(input.element)
  await input.setValue('690000000010')
  await flushPromises()
  expect(apiMocks.scanCode).not.toHaveBeenCalled()

  await input.setValue('6900000000101')
  await flushPromises()
  expect(apiMocks.scanCode).not.toHaveBeenCalled()
  await input.trigger('keydown.enter')
  await flushPromises()

  expect(apiMocks.scanCode).toHaveBeenCalledTimes(1)
  expect(apiMocks.scanCode).toHaveBeenCalledWith(8, expect.objectContaining({
    code: '6900000000101',
    request_id: expect.any(String),
  }))
  expect((input.element as HTMLInputElement).value).toBe('')
  expect(document.activeElement).toBe(input.element)
  expect(wrapper.text()).toContain('识别成功')
  expect(wrapper.text()).toContain('测试卷烟')
  expect(wrapper.text()).toContain('200')
})

test('不足 13 位的有效编码可点击确认识别', async () => {
  apiMocks.scanCode.mockResolvedValue(successOperation())
  const wrapper = await mountWorkspace()
  const input = wrapper.get('input[name="scan_code"]')

  await input.setValue('690001')
  await flushPromises()
  expect(apiMocks.scanCode).not.toHaveBeenCalled()

  await wrapper.get('button[type="submit"]').trigger('submit')
  await flushPromises()

  expect(apiMocks.scanCode).toHaveBeenCalledWith(8, expect.objectContaining({
    code: '690001',
  }))
})

test('网络失败保留输入并用同一 request_id 重试', async () => {
  apiMocks.scanCode
    .mockRejectedValueOnce(new Error('网络连接失败'))
    .mockResolvedValueOnce(successOperation())
  const wrapper = await mountWorkspace()
  const input = wrapper.get('input[name="scan_code"]')

  await input.setValue('6900000000101')
  await input.trigger('keydown.enter')
  await flushPromises()
  const firstRequest = apiMocks.scanCode.mock.calls[0]?.[1]
  expect((input.element as HTMLInputElement).value).toBe('6900000000101')
  expect(wrapper.text()).toContain('网络连接失败')

  await input.trigger('keydown.enter')
  await flushPromises()
  const secondRequest = apiMocks.scanCode.mock.calls[1]?.[1]
  expect(secondRequest.request_id).toBe(firstRequest.request_id)
  expect((input.element as HTMLInputElement).value).toBe('')
})

test('扫码正常返回后不等待流水刷新就清空并重新聚焦', async () => {
  let resolveScan: ((value: ReturnType<typeof successOperation>) => void) | undefined
  apiMocks.scanCode.mockImplementation(() => new Promise((resolve) => {
    resolveScan = resolve
  }))
  apiMocks.listScanEvents
    .mockResolvedValueOnce({ items: [], total: 0, page: 1, page_size: 10 })
    .mockImplementationOnce(() => new Promise(() => {}))
  const wrapper = await mountWorkspace()
  const input = wrapper.get('input[name="scan_code"]')

  await input.setValue('6900000000101')
  void input.trigger('keydown.enter')
  ;(input.element as HTMLInputElement).blur()
  resolveScan?.(successOperation())
  await flushPromises()

  expect((input.element as HTMLInputElement).value).toBe('')
  expect(document.activeElement).toBe(input.element)
})

test('过滤非数字，网络失败后修改编码并再次确认会使用新 request_id', async () => {
  apiMocks.scanCode
    .mockRejectedValueOnce(new Error('网络连接失败'))
    .mockResolvedValueOnce(successOperation())
  const wrapper = await mountWorkspace()
  const input = wrapper.get('input[name="scan_code"]')

  await input.setValue('69000000001A1')
  await flushPromises()
  expect((input.element as HTMLInputElement).value).toBe('690000000011')
  expect(apiMocks.scanCode).not.toHaveBeenCalled()

  await input.setValue('6900000000101')
  await input.trigger('keydown.enter')
  await flushPromises()
  const firstRequest = apiMocks.scanCode.mock.calls[0]?.[1]
  expect((input.element as HTMLInputElement).value).toBe('6900000000101')

  await input.setValue('6900000000102')
  await input.trigger('keydown.enter')
  await flushPromises()
  const secondRequest = apiMocks.scanCode.mock.calls[1]?.[1]
  expect(secondRequest.request_id).not.toBe(firstRequest.request_id)
  expect((input.element as HTMLInputElement).value).toBe('')
})

test('歧义候选可稍后解决，查看员只能查看状态', async () => {
  const ambiguous = successOperation('AMBIGUOUS')
  apiMocks.getScanState.mockResolvedValueOnce(ambiguous.state)
  apiMocks.resolveAmbiguity.mockResolvedValue(successOperation())
  const wrapper = await mountWorkspace()

  expect(wrapper.text()).toContain('待处理歧义')
  expect(wrapper.text()).toContain('测试卷烟')
  await wrapper.get('[data-action="resolve-31-42"]').trigger('click')
  await flushPromises()
  expect(apiMocks.resolveAmbiguity).toHaveBeenCalledWith(8, {
    request_id: expect.any(String),
    event_id: 31,
    product_id: 42,
  })
  expect(wrapper.text()).toContain('歧义已处理')

  wrapper.unmount()
  const viewer = await mountWorkspace('VIEWER')
  expect(viewer.find('input[name="scan_code"]').exists()).toBe(false)
  expect(viewer.text()).toContain('只读查看')
})

test('盘点工作台展示统计、最近识别和同名称条码平铺表格', async () => {
  const first = successOperation()
  const secondItem = {
    ...first.state.items[0],
    id: 12,
    product_id: 43,
    carton_count: 2,
    total_sticks: 400,
    product_snapshot: {
      ...product,
      product_id: 43,
      carton_code: '6901028129999',
      carton_retail_price: '400.00',
    },
  }
  const latest = {
    ...first.event,
    created_at: '2026-08-31T07:47:22Z',
  }
  apiMocks.getScanState.mockResolvedValue({
    ...first.state,
    items: [...first.state.items, secondItem],
    summary: {
      ...first.state.summary,
      product_count: 2,
      carton_count: 3,
      total_sticks: 600,
      unknown_count: 2,
    },
    catalog_summary: emptyState.catalog_summary,
    latest_successful_event: latest,
  })
  apiMocks.listScanEvents.mockResolvedValue({
    items: Array.from({ length: 10 }, (_, index) => ({
      ...latest,
      id: 100 + index,
      request_id: `00000000-0000-4000-8000-${index.toString().padStart(12, '0')}`,
    })),
    total: 11,
    page: 1,
    page_size: 10,
  })

  const wrapper = await mountWorkspace()

  expect(wrapper.text()).toContain('累计扫描数量')
  expect(wrapper.text()).toContain('已盘品规')
  expect(wrapper.text()).toContain('参考零售价合计')
  expect(wrapper.text()).toContain('未识别条码')
  expect(wrapper.text()).toContain('基础库：41 个编码 / 39 个标准品规')
  expect(wrapper.text()).toContain('2026/08/31 15:47:22')
  expect(wrapper.text()).toContain('条码后 6 位')
  for (const heading of [
    '序号', '品牌', '卷烟名称（标准品规）', '已扫描条码',
    '类型', '条支比', '零售价', '数量（条）', '金额小计', '操作',
  ]) expect(wrapper.text()).toContain(heading)
  expect(wrapper.find('[data-inventory-group]').exists()).toBe(false)
  expect(wrapper.find('[data-product-version]').exists()).toBe(false)
  expect(wrapper.find('table.product-table').exists()).toBe(true)
  expect(wrapper.findAll('table.product-table thead th')).toHaveLength(10)
  expect(wrapper.get('table.product-table thead').text()).not.toContain('条码后 6 位')
  expect(wrapper.findAll('[data-product-row]')).toHaveLength(2)
  for (const row of wrapper.findAll('[data-product-row]')) {
    expect(row.findAll('td')).toHaveLength(10)
  }
  const firstBarcode = wrapper.get('[data-product-row] .barcode')
  expect(firstBarcode.text()).toBe('6900000000101')
  expect(firstBarcode.get('.barcode-suffix').text()).toBe('000101')
  expect(wrapper.text()).toContain('相同条码品规自动累计；同名称不同条码平级显示。')
  expect(wrapper.text()).not.toContain('导出统计')
  expect(wrapper.text()).not.toContain('CSV 导出')
  expect(wrapper.text()).not.toContain('清空盘点')
  expect(wrapper.findAll('button[data-action^="delete-"]')).toHaveLength(2)
  expect(wrapper.text()).toContain('¥900.00')
})

test('删除品规需要确认，取消不请求，确认后采用后端状态并刷新流水', async () => {
  const operation = successOperation()
  apiMocks.getScanState.mockResolvedValue(operation.state)
  apiMocks.removeScanSessionItem.mockResolvedValue({
    event: {
      ...operation.event,
      event_type: 'ADJUST',
      unit_type: 'STICK',
      delta_sticks: -200,
      reason: '删除品规统计：数量归零并隐藏',
    },
    state: emptyState,
    idempotent_replay: false,
  })
  const wrapper = await mountWorkspace()

  await wrapper.get('[data-action="delete-42"]').trigger('click')
  expect(wrapper.get('[role="dialog"]').text()).toContain('测试卷烟')
  expect(wrapper.get('[role="dialog"]').text()).toContain('6900000000101')
  await wrapper.get('[data-action="cancel-remove"]').trigger('click')
  expect(apiMocks.removeScanSessionItem).not.toHaveBeenCalled()

  await wrapper.get('[data-action="delete-42"]').trigger('click')
  await wrapper.get('[data-action="confirm-remove"]').trigger('click')
  await flushPromises()

  expect(apiMocks.removeScanSessionItem).toHaveBeenCalledWith(8, 42, {
    request_id: expect.any(String),
  })
  expect(wrapper.find('[data-product-row]').exists()).toBe(false)
  expect(wrapper.text()).toContain('删除品规统计：数量归零并隐藏')
  expect(apiMocks.listScanEvents).toHaveBeenLastCalledWith(8, { page: 1, page_size: 10 })
})

test('删除失败后再次确认复用 request_id，只读用户的删除按钮禁用', async () => {
  const operation = successOperation()
  apiMocks.getScanState.mockResolvedValue(operation.state)
  apiMocks.removeScanSessionItem
    .mockRejectedValueOnce(new Error('网络连接失败'))
    .mockResolvedValueOnce({
      event: {
        ...operation.event,
        event_type: 'ADJUST',
        unit_type: 'STICK',
        delta_sticks: -200,
        reason: '删除品规统计：数量归零并隐藏',
      },
      state: emptyState,
      idempotent_replay: true,
    })
  const wrapper = await mountWorkspace()

  await wrapper.get('[data-action="delete-42"]').trigger('click')
  await wrapper.get('[data-action="confirm-remove"]').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('网络连接失败')
  const firstRequestId = apiMocks.removeScanSessionItem.mock.calls[0]?.[2].request_id

  await wrapper.get('[data-action="delete-42"]').trigger('click')
  await wrapper.get('[data-action="confirm-remove"]').trigger('click')
  await flushPromises()
  expect(apiMocks.removeScanSessionItem.mock.calls[1]?.[2].request_id).toBe(firstRequestId)

  wrapper.unmount()
  apiMocks.getScanState.mockResolvedValue(operation.state)
  const viewer = await mountWorkspace('VIEWER')
  expect(viewer.get('[data-action="delete-42"]').attributes('disabled')).toBeDefined()
})

test('品规条数按 0.1 加减、设置一位小数并刷新流水分页', async () => {
  const operation = successOperation()
  apiMocks.getScanState.mockResolvedValue({
    ...operation.state,
    catalog_summary: emptyState.catalog_summary,
    latest_successful_event: operation.event,
  })
  apiMocks.adjustCartonQuantity.mockResolvedValue(operation)
  apiMocks.listScanEvents.mockImplementation((_id: number, query: { page: number }) => (
    Promise.resolve({
      items: [operation.event], total: 11, page: query.page, page_size: 10,
    })
  ))

  const wrapper = await mountWorkspace()
  await wrapper.get('[data-action="increment-42"]').trigger('click')
  expect(wrapper.get('[data-adjustment-dialog]').text()).toContain('调整原因')
  await wrapper.get('[data-action="confirm-adjustment"]').trigger('click')
  await flushPromises()
  expect(apiMocks.adjustCartonQuantity).toHaveBeenCalledWith(8, 42, {
    request_id: expect.any(String),
    operation: 'DELTA',
    quantity: 0.1,
    reason_type: 'ONSITE_VERIFICATION',
    reason_note: '',
  })

  await wrapper.get('[data-action="decrement-42"]').trigger('click')
  await wrapper.get('[data-action="confirm-adjustment"]').trigger('click')
  await flushPromises()
  expect(apiMocks.adjustCartonQuantity).toHaveBeenLastCalledWith(8, 42, {
    request_id: expect.any(String),
    operation: 'DELTA',
    quantity: -0.1,
    reason_type: 'ONSITE_VERIFICATION',
    reason_note: '',
  })

  const quantity = wrapper.get('input[name="carton-quantity-42"]')
  expect(quantity.attributes('step')).toBe('0.1')
  await quantity.setValue('1.5')
  await quantity.trigger('keydown.enter')
  await wrapper.get('[data-action="confirm-adjustment"]').trigger('click')
  await flushPromises()
  expect(apiMocks.adjustCartonQuantity).toHaveBeenLastCalledWith(8, 42, {
    request_id: expect.any(String),
    operation: 'SET',
    quantity: 1.5,
    reason_type: 'ONSITE_VERIFICATION',
    reason_note: '',
  })

  const callCount = apiMocks.adjustCartonQuantity.mock.calls.length
  await quantity.setValue('1.55')
  await quantity.trigger('keydown.enter')
  await flushPromises()
  expect(apiMocks.adjustCartonQuantity).toHaveBeenCalledTimes(callCount)

  await wrapper.get('[data-action="next-events"]').trigger('click')
  await flushPromises()
  expect(apiMocks.listScanEvents).toHaveBeenLastCalledWith(8, { page: 2, page_size: 10 })
})

test('操作员完成来源拆分后可确认完成批次并下载 Excel', async () => {
  const operation = successOperation()
  apiMocks.getScanState.mockResolvedValue({
    ...operation.state,
    summary: {
      ...operation.state.summary,
      unknown_count: 2,
      ambiguous_count: 1,
    },
  })
  apiMocks.getSourceAllocations.mockResolvedValue({
    items: [{
      product_id: 42,
      product_snapshot: product,
      required_pack_count: 10,
      allocated_pack_count: 0,
      remaining_pack_count: 10,
      allocations: [],
    }],
  })
  apiMocks.replaceSourceAllocations.mockResolvedValue({
    product_id: 42,
    product_snapshot: product,
    required_pack_count: 10,
    allocated_pack_count: 10,
    remaining_pack_count: 0,
    allocations: [{
      id: 1,
      source_type: 'UNKNOWN',
      source_type_name: '来源不详',
      province_name: null,
      city_name: null,
      pack_count: 10,
      equivalent_cartons: '1.0',
      quantity_sticks: 200,
    }],
  })
  apiMocks.completeScanSession.mockResolvedValue({
    scan_session: { ...sessionFixture, status: 'COMPLETED', status_name: '已完成' },
    summary: operation.state.summary,
    source_product_count: 1,
    source_allocated_product_count: 1,
    unknown_count: 2,
    unresolved_ambiguity_count: 1,
  })
  apiMocks.downloadScanSessionExport.mockResolvedValue({
    blob: new Blob(['xlsx']),
    filename: '涉案卷烟统计.xlsx',
  })
  const wrapper = await mountWorkspace()

  await wrapper.get('[data-action="allocate-source-42"]').trigger('click')
  expect(wrapper.get('[data-source-dialog]').text()).toContain('测试卷烟')
  await wrapper.get('select[name="source-type-0"]').setValue('UNKNOWN')
  await wrapper.get('input[name="source-pack-count-0"]').setValue('10')
  await wrapper.get('[data-action="save-source-allocations"]').trigger('click')
  await flushPromises()
  expect(apiMocks.replaceSourceAllocations).toHaveBeenCalledWith(8, 42, {
    items: [{ source_type: 'UNKNOWN', province_name: null, city_name: null, pack_count: 10 }],
  })

  await wrapper.get('[data-action="complete-session"]').trigger('click')
  expect(wrapper.get('[data-completion-dialog]').text()).toContain('异常编码')
  await wrapper.get('input[name="confirm-exceptions"]').setValue(true)
  await wrapper.get('[data-action="confirm-completion"]').trigger('click')
  await flushPromises()
  expect(apiMocks.completeScanSession).toHaveBeenCalledWith(8, { confirm_exceptions: true })
  expect(wrapper.text()).toContain('批次已完成')

  await wrapper.get('[data-action="download-excel"]').trigger('click')
  await flushPromises()
  expect(apiMocks.downloadScanSessionExport).toHaveBeenCalledWith(8)
})

test('已完成批次确认后只调用一次简道云导入并切换为已导入', async () => {
  apiMocks.getScanSession.mockResolvedValue({
    scan_session: { ...sessionFixture, status: 'COMPLETED', status_name: '已完成' },
  })
  apiMocks.importToJianDaoYun.mockResolvedValue({
    snapshot: {
      status: 'SUCCEEDED',
      external_data_id: 'external-id',
      attempt_count: 1,
      last_error_code: null,
      last_error_message: null,
      created_at: '2026-09-04T04:00:00Z',
      updated_at: '2026-09-04T04:00:01Z',
      succeeded_at: '2026-09-04T04:00:01Z',
    },
  })
  const wrapper = await mountWorkspace()

  await wrapper.get('[data-action="import-jiandaoyun"]').trigger('click')
  expect(wrapper.get('[data-integration-dialog]').text()).toContain('确认导入简道云')
  await wrapper.get('[data-action="confirm-jiandaoyun-import"]').trigger('click')
  await flushPromises()

  expect(apiMocks.importToJianDaoYun).toHaveBeenCalledTimes(1)
  expect(apiMocks.importToJianDaoYun).toHaveBeenCalledWith(8)
  const button = wrapper.get('[data-action="import-jiandaoyun"]')
  expect(button.text()).toBe('已导入')
  expect(button.attributes('disabled')).toBeDefined()
  expect(button.attributes('title')).toBe(
    '该盘点批次已经导入简道云，不能重复导入。',
  )
})

test('失败可重新导入，不确定状态要求人工核查且禁止点击', async () => {
  const { default: CompletionPanel } = await import('../components/scanning/CompletionPanel.vue')
  const baseProps = {
    status: 'COMPLETED' as const,
    canWrite: true,
    sourceStates: [],
    unknownCount: 0,
    ambiguityCount: 0,
    completing: false,
    downloading: false,
    importing: false,
  }
  const failed = mount(CompletionPanel, {
    props: {
      ...baseProps,
      integrationSnapshot: {
        status: 'FAILED' as const,
        external_data_id: null,
        attempt_count: 1,
        last_error_code: 'EXTERNAL_REJECTED',
        last_error_message: '简道云明确拒绝请求',
        created_at: '2026-09-04T04:00:00Z',
        updated_at: '2026-09-04T04:00:01Z',
        succeeded_at: null,
      },
    },
  })
  expect(failed.get('[data-action="import-jiandaoyun"]').text()).toBe('重新导入')
  expect(failed.text()).toContain('简道云明确拒绝请求')

  await failed.setProps({
    integrationSnapshot: {
      status: 'UNCERTAIN',
      external_data_id: null,
      attempt_count: 1,
      last_error_code: 'EXTERNAL_UNCERTAIN',
      last_error_message: '结果不确定',
      created_at: '2026-09-04T04:00:00Z',
      updated_at: '2026-09-04T04:00:01Z',
      succeeded_at: null,
    },
  })
  const uncertain = failed.get('[data-action="import-jiandaoyun"]')
  expect(uncertain.text()).toBe('导入结果待核查')
  expect(uncertain.attributes('disabled')).toBeDefined()
  expect(failed.text()).toContain('请按标识 ID 到简道云人工核查')
})

test('外省来源选择省级后城市默认不详且可以直接保存', async () => {
  const wrapper = mount(SourceAllocationDialog, {
    props: {
      state: {
        product_id: 42,
        product_snapshot: product,
        required_pack_count: 1,
        allocated_pack_count: 0,
        remaining_pack_count: 1,
        allocations: [],
      },
      catalog: {
        source_types: [
          { value: 'OUTSIDE_PROVINCE', label: '外省流入' },
          { value: 'UNKNOWN', label: '来源不详' },
          { value: 'LOCAL_HUAINAN', label: '市内串码' },
          { value: 'ANHUI_OTHER_CITY', label: '省内市外' },
        ],
        provinces: [
          { name: '天津市', cities: [{ name: '天津市' }] },
          { name: '安徽省', cities: [{ name: '淮南市' }, { name: '合肥市' }] },
        ],
      },
      saving: false,
    },
  })

  await wrapper.get('select[name="source-type-0"]').setValue('OUTSIDE_PROVINCE')
  await wrapper.get('select[aria-label="来源省"]').setValue('天津市')

  expect((wrapper.get('select[aria-label="来源市"]').element as HTMLSelectElement).value).toBe('不详')
  expect(wrapper.get('select[aria-label="来源市"]').text()).toContain('不详')
  expect(wrapper.get('[data-action="save-source-allocations"]').attributes('disabled')).toBeUndefined()
})

test('已完成结果不显示扫码框，操作员可查询品规并按来源新增', async () => {
  apiMocks.getScanSession.mockResolvedValue({
    scan_session: { ...sessionFixture, status: 'COMPLETED', status_name: '已完成' },
  })
  apiMocks.searchProductOptions.mockResolvedValue({
    items: [{
      id: 42,
      carton_code: product.carton_code,
      brand: product.brand,
      standard_name: product.standard_name,
      carton_retail_price: product.carton_retail_price,
      sticks_per_pack: 20,
      packs_per_carton: 10,
    }],
    total: 1,
    page: 1,
    page_size: 20,
  })
  apiMocks.addResultItem.mockResolvedValue({
    item: successOperation().state.items[0],
    source_state: {
      product_id: 42,
      product_snapshot: product,
      required_pack_count: 5,
      allocated_pack_count: 5,
      remaining_pack_count: 0,
      allocations: [],
    },
    event: successOperation().event,
    idempotent_replay: false,
  })
  const wrapper = await mountWorkspace()

  expect(wrapper.find('input[name="scan_code"]').exists()).toBe(false)
  await wrapper.get('[data-action="add-result-item"]').trigger('click')
  await wrapper.get('input[name="product-query"]').setValue('000101')
  await wrapper.get('[data-action="search-products"]').trigger('click')
  await flushPromises()
  expect(apiMocks.searchProductOptions).toHaveBeenCalledWith('000101', 1, 20)
  await wrapper.get('[data-product-option="42"]').trigger('click')
  await wrapper.get('input[name="result-quantity"]').setValue('0.5')
  await wrapper.get('[data-action="continue-result-item"]').trigger('click')
  await wrapper.get('select[name="source-type-0"]').setValue('UNKNOWN')
  await wrapper.get('input[name="source-pack-count-0"]').setValue('5')
  await wrapper.get('[data-action="save-source-allocations"]').trigger('click')
  await flushPromises()

  expect(apiMocks.addResultItem).toHaveBeenCalledWith(8, {
    request_id: expect.any(String),
    product_id: 42,
    quantity_cartons: 0.5,
    source_allocations: [
      { source_type: 'UNKNOWN', province_name: null, city_name: null, pack_count: 5 },
    ],
  })
})

test('已完成结果可修改现有品规数量并保留来源为一次提交', async () => {
  const operation = successOperation()
  apiMocks.getScanSession.mockResolvedValue({
    scan_session: { ...sessionFixture, status: 'COMPLETED', status_name: '已完成' },
  })
  apiMocks.getScanState.mockResolvedValue(operation.state)
  apiMocks.getSourceAllocations.mockResolvedValue({ items: [{
    product_id: 42,
    product_snapshot: product,
    required_pack_count: 10,
    allocated_pack_count: 10,
    remaining_pack_count: 0,
    allocations: [{
      id: 1, source_type: 'UNKNOWN', source_type_name: '来源不详',
      province_name: null, city_name: null, pack_count: 10,
      equivalent_cartons: '1.0', quantity_sticks: 200,
    }],
  }] })
  apiMocks.replaceResultItem.mockResolvedValue({
    item: operation.state.items[0], source_state: {}, event: operation.event, idempotent_replay: false,
  })
  const wrapper = await mountWorkspace()

  await wrapper.get('[data-action="edit-result-42"]').trigger('click')
  await wrapper.get('input[name="result-quantity"]').setValue('0.5')
  await wrapper.get('[data-action="continue-result-item"]').trigger('click')
  await wrapper.get('input[name="source-pack-count-0"]').setValue('5')
  await wrapper.get('[data-action="save-source-allocations"]').trigger('click')
  await flushPromises()

  expect(apiMocks.replaceResultItem).toHaveBeenCalledWith(8, 42, {
    request_id: expect.any(String),
    quantity_cartons: 0.5,
    source_allocations: [
      { source_type: 'UNKNOWN', province_name: null, city_name: null, pack_count: 5 },
    ],
  })
})
