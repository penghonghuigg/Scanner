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
  let integrationStatus: 'SUCCEEDED' | null = null
  let integrationCreateCount = 0

  await page.route('**/api/v1/scan-sessions/*/integration-snapshot', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          snapshot: integrationStatus === null ? null : {
            status: integrationStatus,
            external_data_id: 'e2e-external-id',
            attempt_count: 1,
            last_error_code: null,
            last_error_message: null,
            created_at: '2026-09-04T04:00:00Z',
            updated_at: '2026-09-04T04:00:01Z',
            succeeded_at: '2026-09-04T04:00:01Z',
          },
        },
        trace_id: 'e2e-integration-status',
      }),
    })
  })
  await page.route('**/api/v1/scan-sessions/*/jiandaoyun-import', async (route) => {
    integrationCreateCount += 1
    integrationStatus = 'SUCCEEDED'
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          snapshot: {
            status: 'SUCCEEDED',
            external_data_id: 'e2e-external-id',
            attempt_count: 1,
            last_error_code: null,
            last_error_message: null,
            created_at: '2026-09-04T04:00:00Z',
            updated_at: '2026-09-04T04:00:01Z',
            succeeded_at: '2026-09-04T04:00:01Z',
          },
        },
        trace_id: 'e2e-integration-create',
      }),
    })
  })

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
      /^\d{6,64}$/.test(item.carton_code) && !item.is_pack_ambiguous
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
  await expect(page.getByText(/识别成功/)).toHaveCount(0)
  await scanInput.press('Enter')
  await expect(page.getByText(/识别成功/).first()).toBeVisible()
  await expect(scanInput).toHaveValue('')
  await expect(scanInput).toBeFocused()
  await expect(page.getByText(product.standard_name).first()).toBeVisible()
  const latestRecognition = page.locator('[data-latest-recognition]')
  await expect(latestRecognition).toContainText(product.standard_name)
  await expect(latestRecognition).toContainText(product.carton_code.slice(-6))
  await expect(latestRecognition.locator('time')).toHaveText(
    /^\d{4}\/\d{2}\/\d{2} \d{2}:\d{2}:\d{2}$/,
  )
  if (product.pack_code && /^\d{6,64}$/.test(product.pack_code)) {
    await scanInput.fill(product.pack_code)
    await scanInput.press('Enter')
    await expect(page.getByText(/本次增加 1 包/)).toBeVisible()
  }

  const productVersion = page.locator('[data-product-row]', {
    hasText: product.carton_code,
  })
  const barcodeSuffix = productVersion.locator('.barcode-suffix')
  await expect(barcodeSuffix).toHaveText(product.carton_code.slice(-6))
  expect(await barcodeSuffix.evaluate((element) => getComputedStyle(element).color)).toBe(
    'rgb(194, 57, 52)',
  )
  const tableViewport = page.locator('.product-table-scroll')
  expect(await tableViewport.evaluate((element) => (
    element.scrollWidth <= element.clientWidth + 1
    && !['auto', 'scroll'].includes(getComputedStyle(element).overflowX)
  ))).toBeTruthy()
  const quantityInput = productVersion.locator('input[type="number"]')
  const incrementButton = productVersion.locator('[data-action^="increment-"]')
  await incrementButton.click()
  await page.locator('[data-adjustment-dialog] [data-action="confirm-adjustment"]').click()
  await expect(quantityInput).toHaveValue('1.1')
  for (let index = 0; index < 8; index += 1) {
    await incrementButton.click()
    await page.locator('[data-adjustment-dialog] [data-action="confirm-adjustment"]').click()
    await expect(quantityInput).toHaveValue((1.2 + index / 10).toFixed(1))
  }
  await quantityInput.fill('1.5')
  await quantityInput.press('Enter')
  await page.locator('[data-adjustment-dialog] [data-action="confirm-adjustment"]').click()
  await expect(quantityInput).toHaveValue('1.5')
  await expect(page.locator('[data-scan-event]')).toHaveCount(10)
  const nextEvents = page.locator('[data-action="next-events"]')
  await expect(nextEvents).toBeEnabled()
  await nextEvents.click()
  await expect(page.locator('[data-scan-event]').first()).toBeVisible()
  await expect(page.getByText('人工调整').first()).toBeVisible()

  await page.reload()
  await expect(page.getByText(product.standard_name).first()).toBeVisible()
  await expect(page.getByText(/累计扫描数量/)).toBeVisible()
  await expect(page.locator('[data-product-row]', {
    hasText: product.carton_code,
  }).locator('input[type="number"]')).toHaveValue('1.5')

  const persistedRow = page.locator('[data-product-row]', {
    hasText: product.carton_code,
  })
  await persistedRow.getByRole('button', { name: '删除' }).click()
  const removeDialog = page.getByRole('dialog')
  await expect(removeDialog).toContainText(product.standard_name)
  await expect(removeDialog).toContainText(product.carton_code)
  await removeDialog.getByRole('button', { name: '确认删除' }).click()
  await expect(page.locator('[data-product-row]', {
    hasText: product.carton_code,
  })).toHaveCount(0)
  await expect(page.getByText('删除品规统计：数量归零并隐藏').first()).toBeVisible()

  await scanInput.fill(product.carton_code)
  await scanInput.press('Enter')
  const recreatedRow = page.locator('[data-product-row]', {
    hasText: product.carton_code,
  })
  await expect(recreatedRow).toBeVisible()
  await expect(recreatedRow.locator('input[type="number"]')).toHaveValue('1')

  await recreatedRow.locator('[data-action^="allocate-source-"]').click()
  const sourceDialog = page.locator('[data-source-dialog]')
  await expect(sourceDialog).toContainText(product.standard_name)
  await sourceDialog.locator('[data-action="save-source-allocations"]').click()
  await expect(sourceDialog).toHaveCount(0)

  await page.locator('[data-action="complete-session"]').click()
  await page.locator('[data-completion-dialog] [data-action="confirm-completion"]').click()
  await expect(page.getByText('批次已完成').first()).toBeVisible()
  await expect(scanInput).toHaveCount(0)

  await page.locator('[data-action="import-jiandaoyun"]').click()
  await expect(page.locator('[data-integration-dialog]')).toBeVisible()
  await page.locator('[data-action="confirm-jiandaoyun-import"]').click()
  const integrationButton = page.locator('[data-action="import-jiandaoyun"]')
  await expect(integrationButton).toHaveText('已导入')
  await expect(integrationButton).toBeDisabled()
  expect(integrationCreateCount).toBe(1)
  await page.reload()
  await expect(page.locator('[data-action="import-jiandaoyun"]')).toHaveText('已导入')
  await expect(page.locator('[data-action="import-jiandaoyun"]')).toBeDisabled()
  expect(integrationCreateCount).toBe(1)

  await recreatedRow.locator('[data-action^="edit-result-"]').click()
  await page.locator('input[name="result-quantity"]').fill('0.5')
  await page.locator('[data-action="continue-result-item"]').click()
  await page.locator('[data-source-dialog] input[name="source-pack-count-0"]').fill('5')
  await page.locator('[data-source-dialog] [data-action="save-source-allocations"]').click()
  await expect(recreatedRow.locator('.completed-quantity strong')).toHaveText('0.5')

  await page.reload()
  await expect(page.locator('[data-product-row]', { hasText: product.carton_code })
    .locator('.completed-quantity strong')).toHaveText('0.5')

  const downloadPromise = page.waitForEvent('download')
  await page.locator('[data-action="download-excel"]').click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toContain('PD')
  expect(download.suggestedFilename()).toMatch(/\.xlsx$/)

  await page.getByRole('button', { name: /盘点结果/ }).click()
  await expect(page).toHaveURL(/\/scan-results$/)
  await expect(page.getByText(filingCaseNo)).toBeVisible()
})
