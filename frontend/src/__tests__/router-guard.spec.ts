import { createPinia, setActivePinia } from 'pinia'

import { router } from '../router'
import { useAuthStore } from '../stores/auth'

test('普通操作员直接访问人员注册页时返回工作台', async () => {
  setActivePinia(createPinia())
  const auth = useAuthStore()
  auth.user = {
    id: 2,
    username: 'operator',
    display_name: '操作人员',
    role: 'OPERATOR',
    branch_code: 'PANJI',
    branch_name: '潘集分局',
  }
  auth.initialized = true

  await router.push('/users/register')
  await router.isReady()

  expect(router.currentRoute.value.name).toBe('home')
  expect(router.currentRoute.value.query).toEqual({ denied: '1' })
})

test('管理员仅凭角色即可访问人员注册页', async () => {
  setActivePinia(createPinia())
  const auth = useAuthStore()
  auth.user = {
    id: 1,
    username: 'admin',
    display_name: '系统管理员',
    role: 'ADMIN',
    branch_code: null,
    branch_name: null,
  }
  auth.initialized = true

  await router.push('/users/register')
  await router.isReady()

  expect(router.currentRoute.value.name).toBe('user-register')
})

test('品规管理页仅允许管理员访问', async () => {
  setActivePinia(createPinia())
  const auth = useAuthStore()
  auth.user = {
    id: 2,
    username: 'operator',
    display_name: '操作人员',
    role: 'OPERATOR',
    branch_code: 'PANJI',
    branch_name: '潘集分局',
  }
  auth.initialized = true

  await router.push('/products')
  await router.isReady()

  expect(router.currentRoute.value.name).toBe('home')
  expect(router.currentRoute.value.query).toEqual({ denied: '1' })
})

test('查看员不能新建批次，操作员可以新建', async () => {
  setActivePinia(createPinia())
  const auth = useAuthStore()
  auth.user = {
    id: 3,
    username: 'viewer',
    display_name: '查看人员',
    role: 'VIEWER',
    branch_code: 'PANJI',
    branch_name: '潘集分局',
  }
  auth.initialized = true

  await router.push('/scan-sessions/new')
  await router.isReady()
  expect(router.currentRoute.value.name).toBe('home')
  expect(router.currentRoute.value.query).toEqual({ denied: '1' })

  auth.user.role = 'OPERATOR'
  await router.push('/scan-sessions/new')
  expect(router.currentRoute.value.name).toBe('scan-session-create')
})
