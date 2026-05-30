import { test, expect } from '@playwright/test'

test.describe('auth happy path', () => {
  test.beforeEach(async ({ context }) => {
    // Clear any persisted access token from prior runs.
    await context.clearCookies()
  })

  test('login → dashboard with sample projects visible', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible()

    await page.getByLabel(/email/i).fill('demo@indusia.example')
    await page.getByLabel(/^password$/i).fill('any-password')
    await page.getByRole('button', { name: /sign in/i }).click()

    await expect(page).toHaveURL('/')
    await expect(page.getByText('PCB-A12 Main Board')).toBeVisible()
    await expect(page.getByText('PCB-B07 Driver Board')).toBeVisible()
    await expect(page.getByText('PCB-C03 Power Supply')).toBeVisible()
  })

  test('signup → dashboard happy path', async ({ page }) => {
    await page.goto('/signup')
    await expect(page.getByRole('heading', { name: /create account/i })).toBeVisible()

    await page.getByLabel(/email/i).fill('newuser@indusia.example')
    await page.getByLabel(/^password$/i).fill('strong-password')
    await page.getByLabel(/confirm password/i).fill('strong-password')
    await page.getByRole('button', { name: /create account/i }).click()

    await expect(page).toHaveURL('/')
  })

  test('signup password mismatch shows inline error', async ({ page }) => {
    await page.goto('/signup')
    await page.getByLabel(/email/i).fill('mismatch@indusia.example')
    await page.getByLabel(/^password$/i).fill('aaaaaaaa')
    await page.getByLabel(/confirm password/i).fill('bbbbbbbb')
    await page.getByRole('button', { name: /create account/i }).click()
    await expect(page.getByRole('alert')).toContainText(/do not match/i)
    await expect(page).toHaveURL(/\/signup/)
  })

  test('protected route redirects to login with next param', async ({ page }) => {
    await page.goto('/projects/abc/wizard')
    await expect(page).toHaveURL(/\/login\?next=/)
  })

  test('locale switcher swaps top-bar copy', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel(/email/i).fill('demo@indusia.example')
    await page.getByLabel(/^password$/i).fill('any-password')
    await page.getByRole('button', { name: /sign in/i }).click()
    await expect(page).toHaveURL('/')

    await page.getByRole('button', { name: 'ID', exact: true }).click()
    // Logout button is named "Keluar" in Bahasa Indonesia
    await expect(page.getByRole('button', { name: 'Keluar' })).toBeVisible({ timeout: 5000 })
  })
})

test.describe('end-to-end realistic flow', () => {
  test('login → wizard step 1 (project create) → step 2 (BOM preview)', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel(/email/i).fill('demo@indusia.example')
    await page.getByLabel(/^password$/i).fill('any-password')
    await page.getByRole('button', { name: /sign in/i }).click()
    await expect(page).toHaveURL('/')

    await page.getByRole('button', { name: /\+ new project/i }).click()
    await expect(page).toHaveURL(/\/projects\/new\/wizard/)

    // The label is a <span> inside <label>, so target by placeholder instead.
    await page.getByPlaceholder(/Mainboard XR-200/i).fill('Smoke PCB')
    await page.getByPlaceholder(/mainboard-xr-200/i).fill('smoke-pcb')
    await page.getByRole('button', { name: /continue/i }).click()

    // Step 2 heading; disambiguates from stepper label.
    await expect(page.getByRole('heading', { name: /upload bill of materials/i })).toBeVisible()
    await expect(page).toHaveURL(/\/projects\/[0-9a-f-]{36}\/wizard/, { timeout: 5000 })
  })
})
