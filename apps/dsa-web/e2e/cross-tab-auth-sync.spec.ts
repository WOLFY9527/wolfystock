import { expect, test, type BrowserContext, type Page, type Route } from '@playwright/test';
import { createMockAdminUser, createMockAuthStatus } from '../src/test-utils/adminAuthHarness';
import { createMockProductAuthStatus, createMockProductUser } from '../src/test-utils/productAuthHarness';
import type { CurrentUser } from '../src/api/auth';

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installTwoTabAuthHarness(
  context: BrowserContext,
  user: CurrentUser,
  createStatus: (currentUser: CurrentUser | null) => unknown,
) {
  let isLoggedIn = true;
  const requests: string[] = [];

  await context.route('**/api/v1/auth/status**', async (route) => {
    requests.push('GET /api/v1/auth/status');
    await fulfillJson(route, createStatus(isLoggedIn ? user : null));
  });
  await context.route('**/api/v1/auth/me**', async (route) => {
    requests.push('GET /api/v1/auth/me');
    await (isLoggedIn
      ? fulfillJson(route, user)
      : fulfillJson(route, { error: 'not_authenticated' }, 401));
  });
  await context.route('**/api/v1/auth/logout**', async (route) => {
    requests.push('POST /api/v1/auth/logout');
    isLoggedIn = false;
    await fulfillJson(route, { ok: true });
  });

  return {
    requests,
    getLoginState: () => isLoggedIn,
  };
}

async function openAuthenticatedTab(context: BrowserContext, path: string) {
  const page = await context.newPage();
  await page.goto(path);
  await expect(page.getByTestId('auth-guard-overlay')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '账户中心' })).toBeVisible({ timeout: 15_000 });
  return page;
}

async function logoutFromAccountCenter(page: Page) {
  await page.getByTestId('shell-account-center-entry').getByRole('button', { name: '账户中心' }).click();
  await page.getByTestId('shell-account-center-menu').getByRole('menuitem', { name: '退出登录' }).click();
  await page.getByRole('button', { name: '确认退出' }).click();
}

async function expectConsumerGuestConvergence(page: Page, expectedUrl: RegExp) {
  await expect(page).toHaveURL(expectedUrl);
  await expect(page.getByTestId('auth-guard-overlay')).toBeVisible({ timeout: 5_000 });
  await expect(page.getByTestId('auth-guard-overlay')).toContainText(/需要登录|登录/i);
  await expect(page.getByRole('button', { name: '账户中心' })).toHaveCount(0);
}

async function expectAdminGuestConvergence(page: Page, expectedUrl: RegExp) {
  await expect(page).toHaveURL(expectedUrl);
  await expect(page.getByText('需要管理员登录')).toBeVisible({ timeout: 5_000 });
  await expect(page.getByRole('heading', { name: '请使用管理员账户登录后打开系统设置' })).toBeVisible();
  await expect(page.getByRole('link', { name: '登录' }).first()).toHaveAttribute('href', '/zh/login?redirect=%2Fzh%2Fsettings%2Fsystem');
  await expect(page.getByRole('button', { name: '账户中心' })).toHaveCount(0);
}

test.describe('cross-tab auth state synchronization', () => {
  test('consumer logout converges another tab to unauthenticated UI state', async ({ browser }) => {
    const context = await browser.newContext();
    const session = await installTwoTabAuthHarness(
      context,
      createMockProductUser({ username: 'playwright-user', displayName: 'Playwright User' }),
      createMockProductAuthStatus,
    );

    const tabA = await openAuthenticatedTab(context, '/zh/watchlist');
    const tabB = await openAuthenticatedTab(context, '/zh/portfolio');

    try {
      await logoutFromAccountCenter(tabA);

      await expect(tabA).toHaveURL(/\/zh\/guest$/);
      expect(session.getLoginState()).toBe(false);
      expect(session.requests).toContain('POST /api/v1/auth/logout');
      await expectConsumerGuestConvergence(tabB, /\/zh\/portfolio$/);
    } finally {
      await context.close();
    }
  });

  test('admin logout converges another tab to unauthenticated admin guard state', async ({ browser }) => {
    const context = await browser.newContext();
    const session = await installTwoTabAuthHarness(
      context,
      createMockAdminUser({ username: 'playwright-admin', displayName: 'Playwright Admin' }),
      createMockAuthStatus,
    );

    const tabA = await openAuthenticatedTab(context, '/zh/market-overview');
    const tabB = await openAuthenticatedTab(context, '/zh/settings/system');

    try {
      await logoutFromAccountCenter(tabA);

      await expect(tabA).toHaveURL(/\/zh\/guest$/);
      expect(session.getLoginState()).toBe(false);
      expect(session.requests).toContain('POST /api/v1/auth/logout');
      await expectAdminGuestConvergence(tabB, /\/zh\/settings\/system$/);
    } finally {
      await context.close();
    }
  });
});
