import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const apiMocks = vi.hoisted(() => ({
  getScanSession: vi.fn(),
  getScanState: vi.fn(),
  scanCode: vi.fn(),
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
})

test('扫码框前 12 位不提交，第 13 位自动提交且尾随回车不重复', async () => {
  apiMocks.scanCode.mockResolvedValue(successOperation())
  const wrapper = await mountWorkspace()
  const input = wrapper.get('input[name="scan_code"]')

  expect(document.activeElement).toBe(input.element)
  await input.setValue('690000000010')
  await flushPromises()
  expect(apiMocks.scanCode).not.toHaveBeenCalled()

  await input.setValue('6900000000101')
  await flushPromises()
  expect(apiMocks.scanCode).toHaveBeenCalledTimes(1)
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

test('网络失败保留输入并用同一 request_id 重试', async () => {
  apiMocks.scanCode
    .mockRejectedValueOnce(new Error('网络连接失败'))
    .mockResolvedValueOnce(successOperation())
  const wrapper = await mountWorkspace()
  const input = wrapper.get('input[name="scan_code"]')

  await input.setValue('6900000000101')
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

test('过滤非数字，网络失败后修改编码会使用新 request_id 自动提交', async () => {
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
  await flushPromises()
  const firstRequest = apiMocks.scanCode.mock.calls[0]?.[1]
  expect((input.element as HTMLInputElement).value).toBe('6900000000101')

  await input.setValue('6900000000102')
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
