import { expect, test, type Page } from '@playwright/test'

test.setTimeout(60_000)

const password = 'support123'
const username = `e2e_support_${Date.now()}`
let productId = 0

test.beforeAll(async ({ request }) => {
  const health = await request.get('/api/health')
  expect(health.ok()).toBeTruthy()

  const register = await request.post('/api/auth/register', {
    data: { username, password, nickname: 'E2E 客服用户' },
  })
  expect(register.ok()).toBeTruthy()

  const products = await request.get('/api/products', {
    params: { q: '衬衫', page_size: 1 },
  })
  expect(products.ok()).toBeTruthy()
  const body = await products.json()
  if (body.total === 0) {
    throw new Error(
      '商品种子为空：请先运行 cd backend && python -m scripts.seed_catalog',
    )
  }
  productId = body.items[0].id
})

async function login(page: Page): Promise<void> {
  await page.goto('/login')
  await page.getByPlaceholder('用户名').fill(username)
  await page.getByPlaceholder('密码').fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL('/')
}

async function ask(page: Page, question: string): Promise<void> {
  await page.locator('.support-input').fill(question)
  await page.getByRole('button', { name: '发送' }).click()
  await expect(page.locator('.user-bubble').last()).toHaveText(question)
}

test('商品客服：尺码库存直答 → 材质引用 → 未知问题引导 → 兜底转人工', async ({ page }) => {
  await login(page)
  await page.goto(`/product/${productId}`)
  await expect(page.locator('.detail-title')).not.toBeEmpty()

  // 商品详情底部「客服」进入客服页
  await page.locator('.bottom-icon').filter({ hasText: '客服' }).click()
  await expect(page).toHaveURL(new RegExp(`/product/${productId}/support`))
  await expect(page.locator('.header-title')).toHaveText('AI 客服')
  await expect(page.locator('.mini-product')).toBeVisible()
  await expect(page.locator('.ai-bubble').first()).toContainText('AI 客服')

  // 裸尺码问题：没有“尺码/码”字样，也要直接查商品尺码库存
  await ask(page, '有XS的吗')
  const sizeAnswer = page
    .locator('.ai-bubble')
    .filter({ hasText: '没有 XS 码' })
  await expect(sizeAnswer).toBeVisible()
  await expect(sizeAnswer).toContainText('S、M、L、XL、XXL')
  await sizeAnswer.locator('.citation-chip').first().click()
  await expect(page.locator('.citation-table')).toBeVisible()
  await expect(page.locator('.citation-table tbody tr')).toHaveCount(5)
  await page.locator('.citation-close').click()
  await expect(page.locator('.citation-popup')).toBeHidden()

  // 材质问题：RAG 回答带引用
  await ask(page, '这件衣服是什么材质？')
  const answer = page.locator('.ai-bubble').filter({ hasText: '材质是' })
  await expect(answer).toBeVisible()
  await expect(answer).toContainText(/材质|纯棉|面料/)
  const citation = answer.locator('.citation-chip').first()
  await expect(citation).toBeVisible()

  // 点击引用查看知识原文
  await citation.click()
  await expect(page.locator('.citation-popup')).toBeVisible()
  await expect(page.locator('.citation-body')).not.toBeEmpty()
  await page.locator('.citation-close').click()
  await expect(page.locator('.citation-popup')).toBeHidden()

  // 反馈按钮
  const feedbackRow = page
    .locator('.ai-content')
    .filter({ hasText: '材质是' })
  await feedbackRow.getByRole('button', { name: '有帮助' }).click()
  await expect(page.locator('.van-toast__text')).toHaveText('感谢反馈')
  await page.locator('.van-toast').waitFor({ state: 'hidden' })

  // 知识库外问题：第一次澄清，第二次兜底
  await ask(page, '今天天气怎么样')
  await expect(
    page.locator('.ai-bubble').filter({ hasText: '方便再具体说说' }),
  ).toBeVisible()

  await ask(page, '今天天气怎么样')
  const fallback = page
    .locator('.ai-bubble')
    .filter({ hasText: '知识库暂未检索到有效信息' })
  await expect(fallback).toBeVisible()
  await expect(
    fallback.getByRole('button', { name: '转人工客服' }),
  ).toBeVisible()

  // 转人工：进入 waiting_human，展示等待条并禁用输入
  await fallback.getByRole('button', { name: '转人工客服' }).click()
  await expect(page.locator('.waiting-banner')).toContainText(
    '已转人工，等待客服接入',
  )
  await expect(page.locator('.handoff-pill')).toHaveText('等待人工')
  await expect(page.locator('.support-input')).toBeDisabled()
  await expect(page.locator('.support-input')).toHaveAttribute(
    'placeholder',
    '等待客服接入…',
  )
})
