import { createPinia, setActivePinia } from 'pinia'

import { useAuthStore } from '../stores/auth'

const user = {
  id: 1,
  username: 'admin',
  display_name: '系统管理员',
  role: 'ADMIN' as const,
  branch_code: null,
  branch_name: null,
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.restoreAllMocks()
})

test('登录成功后保存当前用户且请求携带 Cookie', async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({ success: true, data: { user }, trace_id: 'trace-1' }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ),
  )
  vi.stubGlobal('fetch', fetchMock)

  const store = useAuthStore()
  await store.login(' admin ', 'correct-password')

  expect(store.user?.display_name).toBe('系统管理员')
  expect(store.user?.branch_name).toBeNull()
  expect(fetchMock).toHaveBeenCalledWith(
    '/api/v1/auth/login',
    expect.objectContaining({ method: 'POST', credentials: 'include' }),
  )
})

test('登录失败时显示后端业务错误且不保留用户', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          success: false,
          error: { code: 'AUTH_INVALID_CREDENTIALS', message: '用户名或密码错误' },
          trace_id: 'trace-2',
        }),
        { status: 401, headers: { 'Content-Type': 'application/json' } },
      ),
    ),
  )

  const store = useAuthStore()
  await expect(store.login('admin', 'wrong-password')).rejects.toThrow('用户名或密码错误')
  expect(store.user).toBeNull()
})
