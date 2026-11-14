import { expect, test } from '@playwright/test'

test.beforeAll(async ({ request }) => {
  const health = await request.get('/api/health')
  expect(health.ok()).toBeTruthy()

  const products = await request.get('/api/products?page_size=1')
  expect(products.ok()).toBeTruthy()
  if ((await products.json()).total === 0) {
    throw new Error(
      '商品种子为空：请先运行 cd backend && python -m scripts.seed_catalog',
    )
  }

  const login = await request.post('/api/auth/login', {
    data: { username: 'demo', password: 'demo123' },
  })
  expect(login.ok()).toBeTruthy()
  const token = (await login.json()).access_token
  const headers = { Authorization: `Bearer ${token}` }

  const cart = await request.get('/api/cart', { headers })
  expect(cart.ok()).toBeTruthy()
  for (const item of (await cart.json()).items) {
    await request.delete(`/api/cart/items/${item.id}`, { headers })
  }

  const addresses = await request.get('/api/addresses', { headers })
  expect(addresses.ok()).toBeTruthy()
  for (const address of await addresses.json()) {
    await request.delete(`/api/addresses/${address.id}`, { headers })
  }
})

test('普通用户访问客服端会被带回首页', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('用户名').fill('demo')
  await page.getByPlaceholder('密码').fill('demo123')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL('/')

  await page.goto('/agent/orders')
  await expect(page).toHaveURL('/')
})

test('完整交易链路：加购 → 结算 → 下单 → 支付 → 客服发货 → 确认收货', async ({
  page,
}) => {
  await page.goto('/login')
  await page.getByPlaceholder('用户名').fill('demo')
  await page.getByPlaceholder('密码').fill('demo123')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL('/')
  await expect(page.locator('.guide-input')).toBeVisible()

  // 分类 → 商品详情 → 加购（M4 起首页分类入口改为发送查询，分类页直接访问）
  await page.goto('/category/1')
  await expect(page).toHaveURL(/\/category\/\d+/)
  await expect(page.locator('.product-card').first()).toBeVisible()
  await page.locator('.product-card').first().click()
  await expect(page).toHaveURL(/\/product\/\d+/)
  await expect(page.locator('.detail-title')).not.toBeEmpty()

  const sizeChip = page.locator('.size-chip:not(.disabled)').first()
  if (await sizeChip.count()) {
    await sizeChip.click()
  }
  await page.getByRole('button', { name: '加入购物车' }).click()
  await expect(page.locator('.van-toast__text')).toHaveText('已加入购物车')
  await page.locator('.van-toast').waitFor({ state: 'hidden' })

  await expect(
    page.getByRole('link', { name: '购物车' }),
  ).toContainText('1')
  await page.getByRole('link', { name: '购物车' }).click()
  await expect(page).toHaveURL('/cart')
  await expect(page.locator('.cart-row')).toHaveCount(1)

  // 购物车 → 结算
  await page.getByRole('button', { name: /结算/ }).click()
  await expect(page).toHaveURL('/checkout')

  // 新增地址
  await page.getByRole('button', { name: '新增地址' }).click()
  await page
    .getByPlaceholder('请填写收货人姓名')
    .fill('小鹿')
  await page
    .getByPlaceholder('请填写 11 位手机号')
    .fill('13800008888')
  await page.getByPlaceholder('如：上海市（省）').fill('上海市')
  await page.getByPlaceholder('如：上海市（市）').fill('上海市')
  await page.getByPlaceholder('如：浦东新区').fill('浦东新区')
  await page
    .getByPlaceholder('街道、门牌号、楼栋房间号')
    .fill('世纪大道 100 号 8 栋 1201 室')
  await page.getByRole('button', { name: '保存' }).click()
  await page.getByPlaceholder('请填写收货人姓名').waitFor({ state: 'hidden' })
  await expect(page.getByText('小鹿', { exact: true })).toBeVisible()

  // 提交订单 → 订单详情 → 模拟支付
  await page.getByRole('button', { name: '提交订单' }).click()
  await expect(page).toHaveURL(/\/orders\/\d+/)
  const orderNo = (await page.locator('.order-no').innerText()).trim()
  expect(orderNo).toHaveLength(19)

  await page.getByRole('button', { name: '模拟支付' }).click()
  await expect(page.locator('.van-toast__text')).toHaveText('支付成功')
  await page.locator('.van-toast').waitFor({ state: 'hidden' })
  await expect(page.locator('.status-line h2')).toHaveText('待发货')

  // 用户退出，客服登录并发货
  await page.goto('/me')
  await page.getByRole('button', { name: '退出登录' }).click()
  await page.getByRole('button', { name: '确认', exact: true }).click()
  await expect(page).toHaveURL('/login')

  await page.setViewportSize({ width: 1280, height: 800 })
  await page.getByPlaceholder('用户名').fill('agent')
  await page.getByPlaceholder('密码').fill('agent123')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL('/agent/orders')
  await expect(page.getByText('客服工作台')).toBeVisible()

  const agentRow = page.locator(`tr[data-order-no="${orderNo}"]`)
  await expect(agentRow).toBeVisible()
  await agentRow.getByRole('button', { name: '模拟发货' }).click()
  await page.getByRole('button', { name: '确认', exact: true }).click()
  await expect(page.locator('.van-toast__text')).toHaveText('已发货')
  await page.locator('.van-toast').waitFor({ state: 'hidden' })
  await expect(agentRow).toHaveCount(0)

  // 客服退出，用户确认收货
  await page.getByRole('button', { name: '退出登录' }).click()
  await expect(page).toHaveURL('/login')

  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByPlaceholder('用户名').fill('demo')
  await page.getByPlaceholder('密码').fill('demo123')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL('/')

  await page.goto('/orders')
  const orderCard = page.locator(`[data-order-no="${orderNo}"]`)
  await expect(orderCard).toBeVisible()
  await orderCard.click()
  await expect(page).toHaveURL(/\/orders\/\d+/)
  await page.getByRole('button', { name: '确认收货' }).click()
  await page.getByRole('button', { name: '确认', exact: true }).click()
  await expect(page.locator('.van-toast__text')).toHaveText('已确认收货')
  await page.locator('.van-toast').waitFor({ state: 'hidden' })
  await expect(page.locator('.status-line h2')).toHaveText('已完成')

  // 我的页订单 / 地址入口
  await page.goto('/me')
  await page.getByText('我的订单', { exact: true }).click()
  await expect(page).toHaveURL('/orders')
  await page.goto('/me')
  await page.getByText('收货地址', { exact: true }).click()
  await expect(page).toHaveURL('/addresses')
  await expect(page.locator('.address-card').first()).toBeVisible()
})
