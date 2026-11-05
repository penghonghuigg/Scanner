import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const apiMocks = vi.hoisted(() => ({
  listProducts: vi.fn(),
  createProduct: vi.fn(),
  updateProduct: vi.fn(),
  importProducts: vi.fn(),
  fetchImportTemplate: vi.fn(),
  buildImportIssuesCsv: vi.fn(() => 'csv'),
}))

vi.mock('../api/products', () => apiMocks)

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
    is_pack_ambiguous: true,
    is_active: true,
    created_at: '2026-08-27T08:00:00',
    updated_at: '2026-08-27T08:00:00',
  }
}

async function mountView() {
  const { default: ProductManagementView } = await import('../views/ProductManagementView.vue')
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div>首页</div>' } },
      { path: '/users/register', component: { template: '<div>人员注册</div>' } },
      { path: '/products', component: ProductManagementView },
      { path: '/scan-sessions', component: { template: '<div>盘点作业</div>' } },
      { path: '/scan-results', component: { template: '<div>盘点结果</div>' } },
    ],
  })
  await router.push('/products')
  await router.isReady()
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.user = {
    id: 1,
    username: 'admin',
    display_name: '系统管理员',
    role: 'ADMIN',
    branch_code: null,
    branch_name: null,
  }
  return mount(ProductManagementView, { global: { plugins: [pinia, router] } })
}

beforeEach(() => {
  vi.clearAllMocks()
  apiMocks.listProducts.mockResolvedValue({
    items: [productFixture()],
    total: 1,
    page: 1,
    page_size: 20,
    summary: { total_count: 1, active_count: 1, inactive_count: 0, ambiguous_count: 1 },
  })
})

test('品规页展示统计、价格、歧义文字和三项主要操作', async () => {
  const wrapper = await mountView()
  await vi.waitFor(() => expect(wrapper.text()).toContain('测试品牌（经典）'))

  expect(wrapper.get('h1').text()).toBe('卷烟品规')
  expect(wrapper.text()).toContain('100.00')
  expect(wrapper.text()).toContain('10.00')
  expect(wrapper.text()).toContain('歧义包码')
  expect(wrapper.get('button[data-action="create"]').text()).toContain('新增品规')
  expect(wrapper.get('button[data-action="template"]').text()).toContain('下载模板')
  expect(wrapper.get('label[data-action="import"]').text()).toContain('批量导入')
  expect(wrapper.get('a[href="/scan-sessions"]').text()).toContain('盘点作业')
  expect(wrapper.get('a[href="/scan-results"]').text()).toContain('盘点结果')
})

test('管理员可以在页面新增一个品规版本', async () => {
  apiMocks.createProduct.mockResolvedValue({ product: productFixture() })
  const wrapper = await mountView()
  await vi.waitFor(() => expect(apiMocks.listProducts).toHaveBeenCalled())

  await wrapper.get('button[data-action="create"]').trigger('click')
  await wrapper.get('input[name="carton_code"]').setValue('6901028000011')
  await wrapper.get('input[name="pack_code"]').setValue('6901028000028')
  await wrapper.get('input[name="brand"]').setValue('测试品牌')
  await wrapper.get('input[name="standard_name"]').setValue('测试品牌（经典）')
  await wrapper.get('input[name="carton_retail_price"]').setValue('100.00')
  await wrapper.get('input[name="sticks_per_pack"]').setValue('20')
  await wrapper.get('input[name="packs_per_carton"]').setValue('10')
  await wrapper.get('form[data-form="product"]').trigger('submit')

  await vi.waitFor(() => expect(apiMocks.createProduct).toHaveBeenCalledWith({
    carton_code: '6901028000011',
    pack_code: '6901028000028',
    brand: '测试品牌',
    standard_name: '测试品牌（经典）',
    carton_retail_price: '100.00',
    sticks_per_pack: 20,
    packs_per_carton: 10,
    is_active: true,
  }))
  expect(wrapper.text()).toContain('品规已新增')
})
