import { expect, test } from '../../frontend/node_modules/@playwright/test/index.js'

const username = process.env.E2E_ADMIN_USERNAME
const password = process.env.E2E_ADMIN_PASSWORD
const sessionToken = process.env.E2E_SESSION_TOKEN

test('管理员通过 Nginx 查看已导入品规并下载模板', async ({ page }) => {
  test.skip(
    !sessionToken && (!username || !password),
    '需要临时会话或 E2E 管理员凭据',
  )

  if (sessionToken) {
    await page.context().addCookies([{
      name: 'scanner_session', value: sessionToken, domain: 'localhost', path: '/',
      httpOnly: true, sameSite: 'Lax', secure: false,
    }])
    await page.goto('/')
  } else {
    await page.goto('/login')
    await page.getByLabel('账号').fill(username!)
    await page.getByLabel('密码').fill(password!)
    await page.getByRole('button', { name: '登录系统' }).click()
  }
  await expect(page).toHaveURL(/\/$/)

  await page.getByRole('link', { name: '品规管理' }).click()
  await expect(page).toHaveURL(/\/products$/)
  await expect(page.getByRole('heading', { name: '卷烟品规' })).toBeVisible()
  await expect(page.getByText('4982', { exact: true }).first()).toBeVisible()
  await expect(page.locator('tbody tr').first()).toContainText('¥')

  const downloadPromise = page.waitForEvent('download')
  await page.locator('button[data-action="template"]').click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('卷烟品规导入模板.xlsx')
})
