import { expect, test } from '@playwright/test'

test('演示账号登录后看到双 Tab 空壳', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('用户名').fill('demo')
  await page.getByPlaceholder('密码').fill('demo123')
  await page.getByRole('button', { name: '登录' }).click()

  await expect(page).toHaveURL('/')
  const tabs = page.locator('.van-tabbar-item')
  await expect(tabs.filter({ hasText: 'AI 找货' })).toBeVisible()
  await expect(tabs.filter({ hasText: '我的' })).toBeVisible()
  await expect(page.getByText('你好，小鹿')).toBeVisible()

  await tabs.filter({ hasText: '我的' }).click()
  await expect(page).toHaveURL('/me')
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible()

  // 回归：从「我的」点「AI 找货」必须能回到首页
  await tabs.filter({ hasText: 'AI 找货' }).click()
  await expect(page).toHaveURL('/')

  // 退出登录后回到登录页
  await tabs.filter({ hasText: '我的' }).click()
  await page.getByRole('button', { name: '退出登录' }).click()
  await page.getByRole('button', { name: '确认' }).click()
  await expect(page).toHaveURL('/login')
})

test('未登录访问 /me 会被带回登录页并保留目标', async ({ page }) => {
  await page.goto('/me')
  await expect(page).toHaveURL(/\/login\?redirect=/)
  expect(new URL(page.url()).searchParams.get('redirect')).toBe('/me')

  await page.getByPlaceholder('用户名').fill('demo')
  await page.getByPlaceholder('密码').fill('demo123')
  await page.getByRole('button', { name: '登录' }).click()

  // 登录后应回到原目标 /me
  await expect(page).toHaveURL('/me')
  await expect(page.getByRole('button', { name: '退出登录' })).toBeVisible()
})
