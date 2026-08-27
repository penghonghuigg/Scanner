import { registerUser } from '../api/users'

test('人员注册请求携带 Cookie 且不提交角色字段', async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({
        success: true,
        data: {
          user: {
            id: 2,
            username: 'zhangsan',
            display_name: '张三',
            role: 'OPERATOR',
            branch_code: 'FENGTAI',
            branch_name: '凤台县局',
          },
        },
        trace_id: 'trace-1',
      }),
      { status: 201, headers: { 'Content-Type': 'application/json' } },
    ),
  )
  vi.stubGlobal('fetch', fetchMock)

  await registerUser({
    username: 'zhangsan',
    display_name: '张三',
    branch_code: 'FENGTAI',
    password: 'initial-password',
    password_confirmation: 'initial-password',
  })

  const [path, requestValue] = fetchMock.mock.calls[0]!
  const request = requestValue as RequestInit
  expect(path).toBe('/api/v1/users')
  expect(request.credentials).toBe('include')
  expect(JSON.parse(request.body as string)).toEqual({
    username: 'zhangsan',
    display_name: '张三',
    branch_code: 'FENGTAI',
    password: 'initial-password',
    password_confirmation: 'initial-password',
  })
})
