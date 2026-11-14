import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from '@playwright/test'

test.setTimeout(60_000)

const password = 'guide123'
const username = `e2e_guide_${Date.now()}`

test.beforeAll(async ({ request }) => {
  const health = await request.get('/api/health')
  expect(health.ok()).toBeTruthy()

  const register = await request.post('/api/auth/register', {
    data: { username, password, nickname: '导购用户' },
  })
  expect(register.ok()).toBeTruthy()
})

async function login(
  page: Page,
  user = username,
  pass = password,
): Promise<void> {
  await page.goto('/login')
  await page.getByPlaceholder('用户名').fill(user)
  await page.getByPlaceholder('密码').fill(pass)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL('/')
}

async function registerFresh(
  request: APIRequestContext,
  label: string,
): Promise<string> {
  const name = `e2e_${label}_${Date.now()}`
  const response = await request.post('/api/auth/register', {
    data: { username: name, password },
  })
  expect(response.ok()).toBeTruthy()
  return name
}

async function demoAuth(
  request: APIRequestContext,
): Promise<{ token: string; headers: { Authorization: string } }> {
  const response = await request.post('/api/auth/login', {
    data: { username: 'demo', password: 'demo123' },
  })
  expect(response.ok()).toBeTruthy()
  const token = (await response.json()).access_token as string
  return { token, headers: { Authorization: `Bearer ${token}` } }
}

async function clearCart(
  request: APIRequestContext,
  headers: { Authorization: string },
): Promise<void> {
  const cart = await request.get('/api/cart', { headers })
  expect(cart.ok()).toBeTruthy()
  for (const item of (await cart.json()).items) {
    await request.delete(`/api/cart/items/${item.id}`, { headers })
  }
}

test('图片找货：选择图片 → 预览 → 发送 → 缩略图与商品卡', async ({
  page,
  request,
}) => {
  const name = await registerFresh(request, 'image')
  await login(page, name)

  await page
    .locator('[data-testid="image-input"]')
    .setInputFiles('tests/fixtures/sample.png')
  await expect(page.locator('.image-attachment img')).toBeVisible()
  await page.locator('.guide-input').fill('找类似这种的')
  await page.getByRole('button', { name: '发送' }).click()

  await expect(page.locator('.message-image')).toBeVisible()
  await expect(page.locator('.guide-product-card').first()).toBeVisible()
  await expect(page.locator('.guide-product-card').first()).toContainText('¥')
  await expect(page.locator('.guide-product-card').first()).toContainText(
    '蓝色',
  )
})

test('语音找货：录音 → 转写回填 → 用户确认发送', async ({
  page,
  request,
}) => {
  const name = await registerFresh(request, 'voice')
  await login(page, name)

  await page.getByRole('button', { name: '语音输入' }).click()
  await expect(page.locator('.voice-panel')).toBeVisible()
  await page.waitForTimeout(1500)
  await page.getByRole('button', { name: '完成录音' }).click()

  await expect(page.locator('.guide-input')).toHaveValue('推荐几件衬衫', {
    timeout: 20_000,
  })
  await expect(page.locator('.voice-attachment')).toContainText(
    '推荐几件衬衫',
  )

  await page.getByRole('button', { name: '发送' }).click()
  await expect(page.locator('.message-audio')).toBeVisible()
  await expect(page.locator('.guide-product-card')).toHaveCount(8)
})

test('加购卡：第二件确认 → 去购物车 → 重复确认不重复加购 → 取消幂等', async ({
  page,
  request,
}) => {
  const auth = await demoAuth(request)
  await clearCart(request, auth.headers)
  await login(page, 'demo', 'demo123')
  await page.getByRole('button', { name: '新对话' }).click()
  await expect(page.locator('.guide-example-chip').first()).toBeVisible()

  await page.getByRole('button', { name: '推荐几件衬衫' }).click()
  await expect(page.locator('.guide-product-card')).toHaveCount(8)
  const secondTitle = await page
    .locator('.guide-product-card')
    .nth(1)
    .locator('.guide-card-title')
    .innerText()

  await page.locator('.guide-input').fill('把第二件加入购物车')
  await page.getByRole('button', { name: '发送' }).click()
  const actionCard = page.locator('.guide-action-card')
  await expect(actionCard).toBeVisible()
  await expect(actionCard).toContainText(secondTitle)
  const actionId = await actionCard.getAttribute('data-action-id')
  expect(actionId).toBeTruthy()

  await page.getByRole('button', { name: '确认加入' }).click()
  await expect(page.locator('.action-success')).toContainText('已加入购物车')

  const token = await page.evaluate(() =>
    localStorage.getItem('ai-shop-access-token'),
  )
  const headers = { Authorization: `Bearer ${token}` }
  const repeated = await request.post(
    `/api/chat/actions/${actionId}/confirm`,
    { headers },
  )
  expect(repeated.ok()).toBeTruthy()
  expect((await repeated.json()).status).toBe('executed')
  const cart = await request.get('/api/cart', { headers })
  expect((await cart.json()).total_quantity).toBe(1)

  await page.getByRole('link', { name: '去购物车' }).click()
  await expect(page).toHaveURL('/cart')
  await expect(page.locator('.cart-row')).toHaveCount(1)

  // 再开一轮并取消；取消接口重复调用仍返回 cancelled
  await page.goto('/')
  await page.getByRole('button', { name: '新对话' }).click()
  await expect(page.locator('.guide-example-chip').first()).toBeVisible()
  await page.getByRole('button', { name: '推荐几件衬衫' }).click()
  await expect(page.locator('.guide-product-card')).toHaveCount(8)
  await page.locator('.guide-input').fill('把第二件加入购物车')
  await page.getByRole('button', { name: '发送' }).click()
  await expect(page.locator('.guide-action-card')).toBeVisible()
  const cancelId = await page
    .locator('.guide-action-card')
    .getAttribute('data-action-id')
  await page.getByRole('button', { name: '取消' }).click()
  await expect(page.locator('.action-cancelled')).toContainText('已取消')

  const cancelFirst = await request.post(
    `/api/chat/actions/${cancelId}/cancel`,
    { headers },
  )
  const cancelSecond = await request.post(
    `/api/chat/actions/${cancelId}/cancel`,
    { headers },
  )
  expect((await cancelFirst.json()).status).toBe('cancelled')
  expect((await cancelSecond.json()).status).toBe('cancelled')
  const confirmCancelled = await request.post(
    `/api/chat/actions/${cancelId}/confirm`,
    { headers },
  )
  expect((await confirmCancelled.json()).status).toBe('cancelled')
})

test('加购失败卡：库存不足展示原因与可换尺码', async ({
  page,
  request,
}) => {
  const auth = await demoAuth(request)
  await clearCart(request, auth.headers)

  const list = await request.get('/api/products', {
    params: { q: '衬衫', page_size: 20 },
  })
  expect(list.ok()).toBeTruthy()
  const items = (await list.json()).items as Array<{ id: number }>
  let target: { title: string; skuId: number; size: string; stock: number } | null =
    null
  for (const item of items) {
    const detail = await request.get(`/api/products/${item.id}`)
    if (!detail.ok()) continue
    const product = await detail.json()
    const sku = (product.skus as Array<{
      id: number
      size: string
      stock: number
      status: string
    }>).find((row) => row.status === 'active' && row.stock >= 2)
    if (sku) {
      target = {
        title: product.title as string,
        skuId: sku.id,
        size: sku.size,
        stock: sku.stock,
      }
      break
    }
  }
  expect(target).not.toBeNull()
  if (!target) return

  // 先把购物车填到 stock-1，确认时再加 2 件会超过库存
  const fill = await request.post('/api/cart/items', {
    headers: auth.headers,
    data: { sku_id: target.skuId, quantity: target.stock - 1 },
  })
  expect(fill.ok()).toBeTruthy()

  await login(page, 'demo', 'demo123')
  await page.getByRole('button', { name: '新对话' }).click()
  await expect(page.locator('.guide-example-chip').first()).toBeVisible()
  await page.locator('.guide-input').fill(
    `把${target.title}加入购物车，${target.size}码，2件`,
  )
  await page.getByRole('button', { name: '发送' }).click()
  await expect(page.locator('.guide-action-card')).toBeVisible()
  await page.getByRole('button', { name: '确认加入' }).click()

  await expect(page.locator('.action-failed')).toContainText('库存不足')
  await expect(page.locator('.action-size-list')).toBeVisible()

  await clearCart(request, auth.headers)
})

test('AI 导购：空状态 → 示例问法 → 商品卡 → 多轮条件 → 历史抽屉 → 新对话', async ({
  page,
}) => {
  await login(page)

  // 空状态保留问候、品类入口、热门商品
  await expect(page.getByText('你好，导购用户')).toBeVisible()
  await expect(page.locator('.guide-example-chip')).toHaveCount(3)
  await expect(page.locator('.guide-category-tile')).toHaveCount(4)
  await expect(page.locator('.product-card')).toHaveCount(8)
  await expect(page.getByText('按品类逛逛')).toBeVisible()

  // 示例问法直接发送，返回 6~8 张商品卡
  await page.getByRole('button', { name: '推荐几件衬衫' }).click()
  await expect(page.locator('.user-bubble').last()).toHaveText('推荐几件衬衫')
  await expect(page.locator('.guide-product-card')).toHaveCount(8)
  await expect(page.locator('.guide-product-card').first()).toContainText('¥')

  // 商品卡进入详情
  await page.locator('.guide-product-card').first().click()
  await expect(page).toHaveURL(/\/product\/\d+/)
  await expect(page.locator('.detail-title')).not.toBeEmpty()

  // 返回首页后历史消息与卡片恢复
  await page.goto('/')
  await expect(page.locator('.guide-product-card')).toHaveCount(8)

  // 多轮 refine：保留衬衫品类，增加蓝色条件
  await page.locator('.guide-input').fill('要蓝色的')
  await page.getByRole('button', { name: '发送' }).click()
  await expect(page.locator('.user-bubble').last()).toHaveText('要蓝色的')
  await expect(page.locator('.guide-product-card')).toHaveCount(9)
  await expect(page.locator('.guide-product-card').last()).toContainText('蓝色')
  await expect(page.locator('.ai-bubble').last()).toContainText('蓝色')

  // 历史抽屉：当前会话显示标题并高亮
  await page.getByRole('button', { name: '历史' }).click()
  const drawer = page.locator('.history-popup')
  await expect(drawer).toBeVisible()
  await expect(drawer.locator('.history-item')).toHaveCount(1)
  await expect(drawer.locator('.history-item').first()).toContainText(
    '推荐几件衬衫',
  )
  await expect(drawer.locator('.history-item').first()).toHaveClass(/active/)
  await drawer.locator('.history-close').click()
  await expect(drawer).toBeHidden()

  // 新对话显式创建，再开一个会话
  await page.getByRole('button', { name: '新对话' }).click()
  await expect(page.locator('.guide-example-chip').first()).toBeVisible()
  await page.getByRole('button', { name: '通勤双肩包' }).click()
  await expect(page.locator('.user-bubble').last()).toHaveText('通勤双肩包')
  await expect(page.locator('.guide-product-card')).toHaveCount(8)

  // 历史抽屉列出两个会话，最新会话在前
  await page.getByRole('button', { name: '历史' }).click()
  await expect(drawer).toBeVisible()
  await expect(drawer.locator('.history-item')).toHaveCount(2)
  await expect(drawer.locator('.history-item').first()).toContainText(
    '通勤双肩包',
  )
  await expect(drawer.locator('.history-item').first()).toHaveClass(/active/)

  // 切回旧会话：消息与商品卡恢复
  await drawer
    .locator('.history-item')
    .filter({ hasText: '推荐几件衬衫' })
    .click()
  await expect(drawer).toBeHidden()
  await expect(page.locator('.user-bubble')).toHaveCount(2)
  await expect(page.locator('.user-bubble').first()).toHaveText('推荐几件衬衫')
  await expect(page.locator('.user-bubble').last()).toHaveText('要蓝色的')
  await expect(page.locator('.guide-product-card')).toHaveCount(9)

  // 再开新对话，回到空状态
  await page.getByRole('button', { name: '新对话' }).click()
  await expect(page.locator('.guide-example-chip').first()).toBeVisible()
  await expect(page.locator('.user-bubble')).toHaveCount(0)
})

test('商品详情按演示账号档案显示尺码推荐', async ({ page, request }) => {
  const products = await request.get('/api/products', {
    params: { q: '衬衫', page_size: 10 },
  })
  expect(products.ok()).toBeTruthy()
  const body = await products.json()
  let productId = 0
  for (const item of body.items) {
    const detail = await request.get(`/api/products/${item.id}`)
    const json = await detail.json()
    if (
      json.size_chart &&
      json.skus.some(
        (sku: { size: string; stock: number }) =>
          sku.size === 'L' && sku.stock > 0,
      )
    ) {
      productId = item.id
      break
    }
  }
  expect(productId).toBeGreaterThan(0)

  await login(page, 'demo', 'demo123')
  await page.goto(`/product/${productId}`)
  await expect(page.locator('.detail-title')).not.toBeEmpty()

  const card = page.locator('.size-recommend-card')
  await expect(card).toBeVisible()
  await expect(card).toContainText('推荐 L 码')
  await expect(card).toContainText('按身材档案')

  await card.getByRole('button', { name: '选择 L 码' }).click()
  await expect(page.locator('.size-chip.active')).toHaveText('L')
})
