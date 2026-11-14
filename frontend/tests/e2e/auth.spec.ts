import { expect, test } from '@playwright/test'

// 演示资料来自 backend/scripts/seed_demo_user.py；修改种子时同步断言
test('演示账号登录后看到双 Tab 空壳', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('用户名').fill('demo')
  await page.getByPlaceholder('密码').fill('demo123')
  await page.getByRole('button', { name: '登录', exact: true }).click()

  await expect(page).toHaveURL('/')
  const tabs = page.getByRole('tab')
  await expect(tabs).toHaveCount(2)
  await expect(page.getByRole('tab', { name: 'AI 找货' })).toBeVisible()
  await expect(page.getByRole('tab', { name: '我的' })).toBeVisible()
  // demo 可能已有历史导购会话，首页不一定显示空状态问候
  await expect(page.locator('.guide-input')).toBeVisible()

  await page.getByRole('tab', { name: '我的' }).click()
  await expect(page).toHaveURL('/me')
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible()
  await expect(page.getByText('172cm · 75kg · 常穿 M 码')).toBeVisible()

  // 回归：从「我的」点「AI 找货」必须能回到首页
  await page.getByRole('tab', { name: 'AI 找货' }).click()
  await expect(page).toHaveURL('/')

  // 退出登录后回到登录页
  await page.getByRole('tab', { name: '我的' }).click()
  await page.getByRole('button', { name: '退出登录' }).click()
  await page.getByRole('button', { name: '确认' }).click()
  await expect(page).toHaveURL('/login')
  await page.reload()
  await expect(page).toHaveURL('/login')
})

test('未登录访问 /me 会被带回登录页并保留目标', async ({ page }) => {
  await page.goto('/me')
  await expect(page).toHaveURL(/\/login\?redirect=/)
  expect(new URL(page.url()).searchParams.get('redirect')).toBe('/me')

  await page.getByPlaceholder('用户名').fill('demo')
  await page.getByPlaceholder('密码').fill('demo123')
  await page.getByRole('button', { name: '登录', exact: true }).click()

  // 登录后应回到原目标 /me
  await expect(page).toHaveURL('/me')
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible()
})
