import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const apiMocks = vi.hoisted(() => ({ createScanSession: vi.fn() }))
vi.mock('../api/scanSessions', () => apiMocks)

function sessionFixture() {
  return {
    id: 8,
    session_no: 'PD20260827-163000-0001',
    business_type: 'MARKET_INSPECTION',
    business_type_name: '市场检查',
    filing_case_no: null,
    location: null,
    notes: null,
    branch_code: 'FENGTAI',
    branch_name: '凤台县局',
    operator_id: 2,
    operator_name: '张三',
    status: 'DRAFT',
    status_name: '草稿',
    product_count: 0,
    total_sticks: 0,
    display_label: '2026-08-27 16:30—张三—0个品规—0支卷烟',
    completed_at: null,
    created_at: '2026-08-27T08:30:00Z',
    updated_at: '2026-08-27T08:30:00Z',
  }
}

async function mountView(role: 'ADMIN' | 'OPERATOR' = 'OPERATOR') {
  setActivePinia(createPinia())
  const auth = useAuthStore()
  auth.user = role === 'ADMIN'
    ? { id: 1, username: 'admin', display_name: '管理员', role, branch_code: null, branch_name: null }
    : { id: 2, username: 'zhangsan', display_name: '张三', role, branch_code: 'FENGTAI', branch_name: '凤台县局' }
  auth.initialized = true

  const { default: ScanSessionCreateView } = await import('../views/ScanSessionCreateView.vue')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/scan-sessions/new', component: ScanSessionCreateView },
      { path: '/scan-sessions/:id/scan', name: 'scan-workspace', component: { template: '<div>扫码页</div>' } },
    ],
  })
  await router.push('/scan-sessions/new')
  await router.isReady()
  return { wrapper: mount(ScanSessionCreateView, { global: { plugins: [router] } }), router }
}

beforeEach(() => {
  vi.clearAllMocks()
  apiMocks.createScanSession.mockResolvedValue({ scan_session: sessionFixture() })
})

test('操作员看到固定所属分局和四种业务类型', async () => {
  const { wrapper } = await mountView()

  expect(wrapper.get('h1').text()).toBe('新建扫描批次')
  expect(wrapper.text()).toContain('市场检查')
  expect(wrapper.text()).toContain('寄递渠道')
  expect(wrapper.text()).toContain('专车运输')
  expect(wrapper.text()).toContain('其他')
  expect(wrapper.get('[data-field="branch-readonly"]').text()).toContain('凤台县局')
  expect(wrapper.find('select[name="branch_code"]').exists()).toBe(false)
  expect(wrapper.get('input[name="filing_case_no"]').attributes('maxlength')).toBe('100')
  expect(wrapper.get('input[name="location"]').attributes('maxlength')).toBe('200')
  expect(wrapper.get('textarea[name="notes"]').attributes('maxlength')).toBe('500')
  expect(wrapper.get('.session-docket').text()).toContain('进行中')
  expect(wrapper.get('.session-actions').text()).toContain('进行中')
})

test('操作员提交时不向后端指定分局并进入空扫码页', async () => {
  const { wrapper, router } = await mountView()

  await wrapper.get('input[value="MARKET_INSPECTION"]').setValue(true)
  await wrapper.get('input[name="filing_case_no"]').setValue('凤烟立〔2026〕001号')
  await wrapper.get('input[name="location"]').setValue('凤台县城关镇')
  await wrapper.get('textarea[name="notes"]').setValue('现场登记')
  await wrapper.get('form[data-form="scan-session"]').trigger('submit')

  await vi.waitFor(() => expect(apiMocks.createScanSession).toHaveBeenCalledWith({
    business_type: 'MARKET_INSPECTION',
    filing_case_no: '凤烟立〔2026〕001号',
    location: '凤台县城关镇',
    notes: '现场登记',
    branch_code: undefined,
  }))
  await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/scan-sessions/8/scan'))
})

test('管理员必须选择所属分局', async () => {
  const { wrapper } = await mountView('ADMIN')

  expect(wrapper.get('select[name="branch_code"]').attributes('required')).toBeDefined()
  expect(wrapper.text()).toContain('田大分局')
  expect(wrapper.text()).toContain('凤台县局')
})
