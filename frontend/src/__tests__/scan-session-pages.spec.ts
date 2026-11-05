import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const apiMocks = vi.hoisted(() => ({
  adjustCartonQuantity: vi.fn(),
  completeScanSession: vi.fn(),
  downloadScanSessionExport: vi.fn(),
  getRegionCatalog: vi.fn(),
  getIntegrationSnapshot: vi.fn(),
  listScanSessions: vi.fn(),
  getScanSession: vi.fn(),
  getScanState: vi.fn(),
  getSourceAllocations: vi.fn(),
  listScanEvents: vi.fn(),
  removeScanSessionItem: vi.fn(),
  replaceSourceAllocations: vi.fn(),
  scanCode: vi.fn(),
  resolveAmbiguity: vi.fn(),
}))
vi.mock('../api/scanSessions', () => apiMocks)

const fixture = {
  id: 8,
  session_no: 'PD20260827-163000-0001',
  business_type: 'MARKET_INSPECTION',
  business_type_name: '市场检查',
  filing_case_no: '凤烟立〔2026〕001号',
  location: '凤台县城关镇',
  notes: '现场登记',
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

function activateUser(role: 'ADMIN' | 'OPERATOR' | 'VIEWER' = 'OPERATOR') {
  setActivePinia(createPinia())
  const auth = useAuthStore()
  auth.user = {
    id: 2,
    username: 'zhangsan',
    display_name: '张三',
    role,
    branch_code: role === 'ADMIN' ? null : 'FENGTAI',
    branch_name: role === 'ADMIN' ? null : '凤台县局',
  }
  auth.initialized = true
}

beforeEach(() => {
  vi.clearAllMocks()
  apiMocks.listScanSessions.mockResolvedValue({ items: [fixture], total: 1, page: 1, page_size: 20 })
  apiMocks.getScanSession.mockResolvedValue({ scan_session: fixture })
  apiMocks.getRegionCatalog.mockResolvedValue({ source_types: [], provinces: [] })
  apiMocks.getSourceAllocations.mockResolvedValue({ items: [] })
  apiMocks.getIntegrationSnapshot.mockResolvedValue({ snapshot: null })
  apiMocks.listScanEvents.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 10 })
  apiMocks.getScanState.mockResolvedValue({
    summary: {
      product_count: 0, carton_count: 0, pack_count: 0,
      total_sticks: 0, unknown_count: 0, ambiguous_count: 0,
    },
    items: [], recent_events: [], pending_ambiguities: [],
  })
})

test('批次列表显示固定标识、状态和案件摘要', async () => {
  activateUser()
  const { default: ScanSessionListView } = await import('../views/ScanSessionListView.vue')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/scan-sessions', component: ScanSessionListView },
      { path: '/scan-results', component: { template: '<div />' } },
      { path: '/scan-sessions/new', component: { template: '<div />' } },
      { path: '/scan-sessions/:id/scan', component: { template: '<div />' } },
    ],
  })
  await router.push('/scan-sessions')
  await router.isReady()
  const wrapper = mount(ScanSessionListView, { global: { plugins: [router] } })
  await flushPromises()

  expect(apiMocks.listScanSessions).toHaveBeenCalledWith({ status: 'DRAFT', page: 1, page_size: 20 })
  expect(wrapper.text()).toContain(fixture.display_label)
  expect(wrapper.text()).toContain('PD20260827-163000-0001')
  expect(wrapper.text()).toContain('凤烟立〔2026〕001号')
  expect(wrapper.text()).toContain('进行中')
})

test('批次列表支持关键词回车查询、重置和接口总数', async () => {
  activateUser()
  apiMocks.listScanSessions.mockResolvedValue({ items: [fixture], total: 37, page: 1, page_size: 20 })
  const { default: ScanSessionListView } = await import('../views/ScanSessionListView.vue')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/scan-sessions', component: ScanSessionListView },
      { path: '/scan-results', component: { template: '<div />' } },
      { path: '/scan-sessions/new', component: { template: '<div />' } },
      { path: '/scan-sessions/:id/scan', component: { template: '<div />' } },
    ],
  })
  await router.push('/scan-sessions')
  await router.isReady()
  const wrapper = mount(ScanSessionListView, { global: { plugins: [router] } })
  await flushPromises()

  expect(wrapper.text()).toContain('共 37 条')
  const input = wrapper.get('input[name="session_query"]')
  await input.setValue('  PD2026  ')
  await input.trigger('keyup.enter')
  await flushPromises()
  expect(apiMocks.listScanSessions).toHaveBeenLastCalledWith({
    query: 'PD2026', status: 'DRAFT', page: 1, page_size: 20,
  })

  await wrapper.get('[data-action="reset-session-query"]').trigger('click')
  await flushPromises()
  expect((input.element as HTMLInputElement).value).toBe('')
  expect(apiMocks.listScanSessions).toHaveBeenLastCalledWith({
    status: 'DRAFT', page: 1, page_size: 20,
  })
})

test('盘点结果入口只查询已完成批次并进入结果详情', async () => {
  activateUser()
  apiMocks.listScanSessions.mockResolvedValue({
    items: [{ ...fixture, status: 'COMPLETED', status_name: '已完成' }],
    total: 1,
    page: 1,
    page_size: 20,
  })
  const { default: ScanSessionListView } = await import('../views/ScanSessionListView.vue')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/scan-sessions', component: { template: '<div />' } },
      { path: '/scan-sessions/new', component: { template: '<div />' } },
      {
        path: '/scan-results',
        name: 'scan-result-list',
        component: ScanSessionListView,
        meta: { sessionStatus: 'COMPLETED' },
      },
      { path: '/scan-results/:id', name: 'scan-result-detail', component: { template: '<div />' } },
    ],
  })
  await router.push('/scan-results')
  await router.isReady()
  const wrapper = mount(ScanSessionListView, { global: { plugins: [router] } })
  await flushPromises()

  expect(apiMocks.listScanSessions).toHaveBeenCalledWith({
    status: 'COMPLETED', page: 1, page_size: 20,
  })
  expect(wrapper.get('h1').text()).toBe('盘点结果')
  expect(wrapper.find('a[href="/scan-sessions/new"]').exists()).toBe(false)
  await wrapper.get('.session-row').trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.fullPath).toBe('/scan-results/8')
})

test('扫码页加载批次详情和持久化扫码状态', async () => {
  activateUser()
  const { default: ScanWorkspaceView } = await import('../views/ScanWorkspaceView.vue')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/scan-sessions/:id/scan', component: ScanWorkspaceView }],
  })
  await router.push('/scan-sessions/8/scan')
  await router.isReady()
  const wrapper = mount(ScanWorkspaceView, { global: { plugins: [router] } })
  await flushPromises()

  expect(apiMocks.getScanSession).toHaveBeenCalledWith(8)
  expect(apiMocks.getScanState).toHaveBeenCalledWith(8)
  expect(wrapper.get('h1').text()).toBe(fixture.display_label)
  expect(wrapper.text()).toContain('扫描条码或包码')
  expect(wrapper.find('input[name="scan_code"]').exists()).toBe(true)
})

test('工作台为操作员提供快捷新建，查看员只提供批次查看', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div />' } }],
  })
  await router.push('/')
  await router.isReady()
  activateUser('OPERATOR')
  const { default: HomeView } = await import('../views/HomeView.vue')
  const operatorWrapper = mount(HomeView, {
    global: { plugins: [router], stubs: { RouterLink: { template: '<a :href="to"><slot /></a>', props: ['to'] } } },
  })
  expect(operatorWrapper.get('[data-action="new-session"]').text()).toContain('新建盘点作业')
  expect(operatorWrapper.get('[data-action="result-list"]').text()).toContain('查看盘点结果')

  activateUser('VIEWER')
  const viewerWrapper = mount(HomeView, {
    global: { plugins: [router], stubs: { RouterLink: { template: '<a :href="to"><slot /></a>', props: ['to'] } } },
  })
  expect(viewerWrapper.find('[data-action="new-session"]').exists()).toBe(false)
  expect(viewerWrapper.get('[data-action="session-list"]').text()).toContain('查看盘点作业')
})
