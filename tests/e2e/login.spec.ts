import { expect, test } from '../../frontend/node_modules/@playwright/test/index.js'

test('未登录用户通过 Nginx 进入登录页', async ({ page }) => {
  const failedResponses: string[] = []
  page.on('response', (response) => {
    if (response.status() >= 400) {
      failedResponses.push(`${response.status()} ${response.url()}`)
    }
  })

  await page.goto('/')
  await page.waitForLoadState('networkidle')

  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('heading', { name: '涉案卷烟 智能统计系统' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '账号登录' })).toBeVisible()
  await expect(page.getByLabel('账号')).toBeFocused()
  await expect(page.getByLabel('密码')).toHaveAttribute('type', 'password')
  await expect(page.getByRole('button', { name: '登录系统' })).toBeDisabled()
  expect(failedResponses).toEqual(['401 http://localhost:8080/api/v1/auth/me'])
})

test('未登录用户不能直接进入人员注册页', async ({ page }) => {
  await page.goto('/users/register')
  await page.waitForLoadState('networkidle')

  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('heading', { name: '账号登录' })).toBeVisible()
})
