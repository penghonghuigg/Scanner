import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'
import type { AuthUser } from '../types/auth'
import HomeView from '../views/HomeView.vue'
import UserRegisterView from '../views/UserRegisterView.vue'

function adminUser(): AuthUser {
  return {
    id: 1,
    username: 'admin',
    display_name: '系统管理员',
    role: 'ADMIN' as const,
    branch_code: null,
    branch_name: null,
  }
}

async function testRouter() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: HomeView },
      { path: '/users/register', component: UserRegisterView },
      { path: '/products', component: { template: '<div>品规管理</div>' } },
      { path: '/scan-sessions', component: { template: '<div>扫描批次</div>' } },
      { path: '/scan-results', component: { template: '<div>盘点结果</div>' } },
      { path: '/scan-sessions/new', component: { template: '<div>新建扫描批次</div>' } },
      { path: '/login', component: { template: '<div>登录</div>' } },
    ],
  })
  await router.push('/users/register')
  await router.isReady()
  return router
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
})

test('注册页展示五个分局和两次密码输入', async () => {
  const wrapper = mount(UserRegisterView, {
    global: { plugins: [await testRouter()] },
  })

  expect(wrapper.get('h1').text()).toBe('人员注册')
  expect(wrapper.findAll('select[name="branch_code"] option')).toHaveLength(6)
  expect(wrapper.get('select[name="branch_code"]').text()).toContain('田大分局')
  expect(wrapper.get('select[name="branch_code"]').text()).toContain('凤台县局')
  expect(wrapper.get('input[name="password"]').attributes('type')).toBe('password')
  expect(wrapper.get('input[name="password_confirmation"]').attributes('type')).toBe('password')
})

test('管理员工作台显示注册入口而操作员不显示', async () => {
  const auth = useAuthStore()
  auth.user = adminUser()
  const router = await testRouter()
  const adminView = mount(HomeView, { global: { plugins: [router] } })
  expect(adminView.get('a[href="/users/register"]').text()).toContain('人员注册')
  expect(adminView.get('a[href="/products"]').text()).toContain('品规管理')

  auth.user = {
    ...adminUser(),
    username: 'operator',
    display_name: '操作人员',
    role: 'OPERATOR',
    branch_code: 'PANJI',
    branch_name: '潘集分局',
  }
  const operatorView = mount(HomeView, { global: { plugins: [router] } })
  expect(operatorView.find('a[href="/users/register"]').exists()).toBe(false)
  expect(operatorView.find('a[href="/products"]').exists()).toBe(false)
  expect(operatorView.text()).toContain('潘集分局')
})

test('管理员进入人员注册后盘点作业和盘点结果菜单仍然可见', async () => {
  const auth = useAuthStore()
  auth.user = adminUser()
  const wrapper = mount(UserRegisterView, {
    global: { plugins: [await testRouter()] },
  })

  expect(wrapper.get('a[href="/scan-sessions"]').text()).toContain('盘点作业')
  expect(wrapper.get('a[href="/scan-results"]').text()).toContain('盘点结果')
  expect(wrapper.get('a[href="/users/register"]').text()).toContain('人员注册')
  expect(wrapper.get('a[href="/products"]').text()).toContain('品规管理')
})
