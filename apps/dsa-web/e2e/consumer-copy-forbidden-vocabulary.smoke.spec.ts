import { expect, test, type Page, type Route } from '@playwright/test';
import { createMockProductAuthStatus, createMockProductUser } from '../src/test-utils/productAuthHarness';
import { expectNoConsumerRawLeakage } from './fixtures/consumerRawLeakageGuard';

const consumerRoutes = [
  { path: '/zh' },
  { path: '/zh/market-overview' },
  { path: '/zh/market/liquidity-monitor' },
  { path: '/zh/market/rotation-radar' },
  { path: '/zh/scanner' },
  { path: '/zh/watchlist' },
  { path: '/zh/portfolio' },
] as const;

const productUser = createMockProductUser({ displayName: 'Playwright User' });

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installProductAuth(page: Page) {
  let isLoggedIn = false;

  await page.route('**/api/v1/auth/status**', async (route) => {
    if (!isLoggedIn) {
      await fulfillJson(route, {
        authEnabled: true,
        loggedIn: false,
        passwordSet: true,
        passwordChangeable: false,
        setupState: 'enabled',
        currentUser: null,
      });
      return;
    }
    await fulfillJson(route, createMockProductAuthStatus(productUser));
  });

  await page.route('**/api/v1/auth/me**', async (route) => {
    if (!isLoggedIn) {
      await fulfillJson(route, { error: 'not_authenticated' }, 401);
      return;
    }
    await fulfillJson(route, productUser);
  });

  await page.route('**/api/v1/auth/login**', async (route) => {
    isLoggedIn = true;
    await fulfillJson(route, { ok: true, currentUser: productUser });
  });

  await page.route('**/api/v1/auth/logout**', async (route) => {
    isLoggedIn = false;
    await fulfillJson(route, { ok: true });
  });

  await page.route('**/api/v1/auth/preferences/notifications**', async (route) => {
    await fulfillJson(route, {
      channel: 'multi',
      enabled: false,
      email: null,
      emailEnabled: false,
      discordEnabled: false,
      discordWebhook: null,
      deliveryAvailable: false,
      emailDeliveryAvailable: false,
      discordDeliveryAvailable: false,
      updatedAt: '2026-06-07T00:00:00+08:00',
    });
  });

  await page.route('**/api/v1/agent/status**', async (route) => {
    await fulfillJson(route, { enabled: false });
  });
}

async function signInAsProduct(page: Page, redirectPath: string) {
  await page.goto(`/login?redirect=${encodeURIComponent(redirectPath)}`);
  await page.waitForLoadState('domcontentloaded');

  const username = page.locator('#username');
  if (await username.isVisible().catch(() => false)) {
    await username.fill('wolfy-user');
  }

  await expect(page.locator('#password')).toBeVisible({ timeout: 15_000 });
  await page.locator('#password').fill('mock-password');

  await Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/v1/auth/login') && response.status() === 200),
    page.getByRole('button', { name: /sign in|登录继续|授权进入工作台|完成设置并登录/i }).click(),
  ]);
}

test('consumer routes keep backend/provider/debug vocabulary out of default copy', async ({ page }) => {
  test.slow();
  await installProductAuth(page);
  await signInAsProduct(page, consumerRoutes[0].path);

  for (const route of consumerRoutes) {
    await test.step(route.path, async () => {
      await page.goto(route.path);
      await page.waitForLoadState('domcontentloaded');
      await expect(page).toHaveURL(new RegExp(`${route.path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?:$|[?#])`));
      await expect.poll(async () => page.locator('body').innerText().then((text) => text.trim().length)).toBeGreaterThan(0);
      await expectNoConsumerRawLeakage(page.locator('body'), { label: route.path });
    });
  }
});
