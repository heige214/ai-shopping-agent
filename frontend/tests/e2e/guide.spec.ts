import { expect, test, type Page } from '@playwright/test'

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
