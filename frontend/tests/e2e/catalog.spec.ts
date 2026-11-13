import { expect, test } from '@playwright/test'

test.beforeAll(async ({ request }) => {
  const health = await request.get('/api/health')
  expect(health.ok()).toBeTruthy()

  const products = await request.get('/api/products?page_size=1')
  expect(products.ok()).toBeTruthy()
  const body = await products.json()
  if (body.total === 0) {
    throw new Error(
      '商品种子为空：请先运行 cd backend && python -m scripts.seed_catalog',
    )
  }
})

test('列表 → 详情 → 收藏 → 我的收藏 → 取消收藏', async ({ page, request }) => {
  await page.goto('/login')
  await page.getByPlaceholder('用户名').fill('demo')
  await page.getByPlaceholder('密码').fill('demo123')
  await page.getByRole('button', { name: '登录', exact: true }).click()

  await expect(page).toHaveURL('/')
  await expect(page.getByText('你好，小鹿')).toBeVisible()
  await expect(page.getByText('按品类逛逛')).toBeVisible()

  await page.getByRole('link', { name: /服装/ }).first().click()
  await expect(page).toHaveURL(/\/category\/\d+/)
  await expect(page.locator('.product-card').first()).toBeVisible()

  await page.locator('.product-card').first().click()
  await expect(page).toHaveURL(/\/product\/\d+/)
  const productId = Number(page.url().match(/\/product\/(\d+)/)?.[1])
  expect(productId).toBeGreaterThan(0)
  await expect(page.locator('.detail-title')).not.toBeEmpty()

  const token = await page.evaluate(() =>
    localStorage.getItem('ai-shop-access-token'),
  )
  expect(token).toBeTruthy()

  // 清理历史收藏状态，保证从「未收藏」开始
  await request.delete(`/api/products/${productId}/favorite`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  await page.reload()
  await expect(page.locator('.detail-title')).not.toBeEmpty()

  await page.getByRole('button', { name: '收藏', exact: true }).click()
  await expect(page.locator('.van-toast__text')).toHaveText('已收藏')
  await page.locator('.van-toast').waitFor({ state: 'hidden' })

  await page.goto('/me')
  await page.getByText('我的收藏', { exact: true }).click()
  await expect(page).toHaveURL('/favorites')
  await expect(
    page.locator(`a[href="/product/${productId}"]`).first(),
  ).toBeVisible()

  await page.locator(`a[href="/product/${productId}"]`).first().click()
  await expect(page).toHaveURL(new RegExp(`/product/${productId}$`))
  await page.getByRole('button', { name: '取消收藏', exact: true }).click()
  await expect(page.locator('.van-toast__text')).toHaveText('已取消收藏')
  await page.locator('.van-toast').waitFor({ state: 'hidden' })

  await page.goto('/favorites')
  await expect(
    page.locator(`a[href="/product/${productId}"]`),
  ).toHaveCount(0)
})
