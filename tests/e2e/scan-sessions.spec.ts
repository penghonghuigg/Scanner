import { expect, test } from '../../frontend/node_modules/@playwright/test/index.js'

const username = process.env.E2E_ADMIN_USERNAME
const password = process.env.E2E_ADMIN_PASSWORD
const sessionToken = process.env.E2E_SESSION_TOKEN

test('管理员新建批次、扫码并在刷新后恢复持久化统计', async ({ page }) => {
  test.skip(
    !sessionToken && (!username || !password),
    '需要临时会话或 E2E 管理员凭据',
  )
  const filingCaseNo = `E2E-${Date.now()}`

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

  const catalogResponse = await page.request.get(
    '/api/v1/products?is_active=true&page=1&page_size=100',
  )
  expect(catalogResponse.ok()).toBeTruthy()
  const catalogPayload = await catalogResponse.json()
  const product = catalogPayload.data.items.find(
    (item: { carton_code: string; is_pack_ambiguous: boolean }) => (
      item.carton_code.length === 13 && !item.is_pack_ambiguous
    ),
  )
  expect(product).toBeTruthy()

  await page.locator('[data-action="new-session"]').click()
  await expect(page).toHaveURL(/\/scan-sessions\/new$/)
  await page.locator('label', { hasText: '市场检查' }).click()
  await page.locator('select[name="branch_code"]').selectOption('FENGTAI')
  await page.getByLabel('立案编号 选填').fill(filingCaseNo)
  await page.getByLabel('检查地点 选填').fill('凤台县城关镇')
  await page.getByRole('button', { name: /创建并进入扫码页/ }).click()

  await expect(page).toHaveURL(/\/scan-sessions\/\d+\/scan$/)
  const scanInput = page.locator('input[name="scan_code"]')
  await expect(scanInput).toBeVisible()
  await expect(scanInput).toBeFocused()
  await expect(page.getByText('凤台县局')).toBeVisible()
  await scanInput.fill(product.carton_code)
  await expect(page.getByText(/识别成功/).first()).toBeVisible()
  await expect(page.getByText(product.standard_name).first()).toBeVisible()
  if (product.pack_code?.length === 13) {
    await scanInput.fill(product.pack_code)
    await expect(page.getByText(/本次增加 1 包/)).toBeVisible()
  }
  await page.reload()
  await expect(page.getByText(product.standard_name).first()).toBeVisible()
  await expect(page.getByText(/总卷烟数量/)).toBeVisible()
  await page.getByRole('button', { name: /扫描批次/ }).click()
  await expect(page).toHaveURL(/\/scan-sessions$/)
  await expect(page.getByText(filingCaseNo)).toBeVisible()
})
