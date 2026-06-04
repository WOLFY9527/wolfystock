import type { Page, Route } from '@playwright/test';
import { expect as appExpect, test as appTest } from './fixtures/appSmoke';
import { expect as adminExpect, expectNoHorizontalOverflow as expectNoAdminHorizontalOverflow, expectNoRawSecretLikeText, openAdminRouteWithHarness, test as adminTest } from './fixtures/adminAuth';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
] as const;

const forbiddenAffordancePattern = /Bootstrap Admin|debug|internal|provider route|cache router|\benv\b|credential/i;
const adminMenuLabelPattern = /系统|System/i;

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installSignedInProductSession(page: Page) {
  const currentUser = {
    id: 'user-1',
    username: 'wolfy-user',
    displayName: 'Wolfy User',
    role: 'user',
    isAdmin: false,
    isAuthenticated: true,
    transitional: false,
    authEnabled: true,
  };

  await page.route('**/api/v1/auth/status**', async (route) => {
    await fulfillJson(route, {
      authEnabled: true,
      loggedIn: true,
      passwordSet: true,
      passwordChangeable: true,
      setupState: 'enabled',
      currentUser,
    });
  });

  await page.route('**/api/v1/auth/me**', async (route) => {
    await fulfillJson(route, currentUser);
  });
}

async function installGuestProductSession(page: Page) {
  await page.route('**/api/v1/auth/status**', async (route) => {
    await fulfillJson(route, {
      authEnabled: true,
      loggedIn: false,
      passwordSet: true,
      passwordChangeable: false,
      setupState: 'enabled',
      currentUser: null,
    });
  });

  await page.route('**/api/v1/auth/me**', async (route) => {
    await fulfillJson(route, { error: 'not_authenticated' }, 401);
  });
}

async function expectNoHorizontalOverflow(page: Page) {
  await appExpect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function expectRootNonEmpty(page: Page) {
  await appExpect.poll(async () => page.locator('#root').evaluate((root) => root.textContent?.trim().length ?? 0)).toBeGreaterThan(0);
}

function normalizeText(text: string) {
  return text.replace(/\s+/g, ' ').trim();
}

async function expectNoForbiddenAffordanceText(text: string) {
  appExpect(text).not.toMatch(forbiddenAffordancePattern);
}

async function readVisibleText(page: Page) {
  return normalizeText(await page.locator('body').innerText());
}

async function openVisibleAdminMenu(page: Page, isMobile: boolean) {
  if (isMobile) {
    return null;
  }

  const adminButton = page.getByTestId('shell-header-utility-island').getByRole('button', { name: adminMenuLabelPattern });
  await adminExpect(adminButton).toBeVisible();
  await adminExpect(adminButton).toHaveAttribute('aria-expanded', 'false');
  await adminButton.click();
  return page.getByTestId('shell-admin-utility-menu');
}

async function expectMarketRedirectSurface(page: Page, isMobile: boolean) {
  await appExpect(page).toHaveURL(/\/zh\/market-overview$/);
  await appExpect(page.getByTestId('market-overview-shell')).toBeVisible({ timeout: 15_000 });
  await appExpect(page.getByRole('heading', { name: '市场总览' })).toBeVisible();
  await expectRootNonEmpty(page);
  await expectNoHorizontalOverflow(page);

  if (isMobile) {
    await appExpect(page.getByTestId('shell-mobile-active-route')).toHaveText('市场总览');
  } else {
    const nav = page.getByRole('navigation', { name: '导航菜单' });
    await appExpect(nav.getByRole('link', { name: '市场总览' })).toHaveClass(/is-active/);
    const accountEntry = page.getByTestId('shell-account-center-entry');
    await appExpect(accountEntry).toBeVisible();
    await appExpect(accountEntry).toContainText('Wolfy User');
    await expectNoForbiddenAffordanceText(await accountEntry.innerText());
  }

  await expectNoForbiddenAffordanceText(await readVisibleText(page));
}

async function expectGuestAdminGate(page: Page) {
  await appExpect(page).toHaveURL(/\/zh\/guest$/);
  await appExpect(page.getByTestId('guest-home-clean-search')).toBeVisible({ timeout: 15_000 });
  await appExpect(page.getByTestId('guest-home-command-surface')).toBeVisible();
  await appExpect(page.getByTestId('guest-home-capability-strip')).toContainText('登录后解锁');
  await appExpect(page.getByTestId('guest-home-command-workflow')).toContainText('搜索');
  await appExpect(page.getByTestId('guest-home-command-workflow')).toContainText('分析');
  await appExpect(page.getByTestId('guest-home-command-workflow')).toContainText('观察');
  await appExpect(page.getByTestId('guest-home-registration-link')).toBeVisible();
  await expectRootNonEmpty(page);
  await expectNoHorizontalOverflow(page);

  await expectNoForbiddenAffordanceText(await readVisibleText(page));
}

async function expectAdminRedirectSurface(page: Page, isMobile: boolean) {
  await adminExpect(page).toHaveURL(/\/zh\/settings\/system$/);
  await adminExpect(page.getByTestId('settings-bento-page')).toBeAttached();
  await adminExpect(page.getByRole('heading', { name: '系统设置' })).toBeVisible({ timeout: 15_000 });
  await adminExpect(page.getByTestId('system-health-summary')).toBeVisible();
  await adminExpect(page.getByTestId('duckdb-quant-panel')).toBeAttached();
  await adminExpect(page.getByText('当前已进入全局系统控制面')).toBeVisible();
  await expectNoAdminHorizontalOverflow(page);
  await expectNoRawSecretLikeText(page);

  if (isMobile) {
    await adminExpect(page.getByTestId('shell-mobile-active-route')).toHaveText('系统');
  } else {
    const accountEntry = page.getByTestId('shell-account-center-entry');
    await adminExpect(accountEntry).toBeVisible();
    await adminExpect(accountEntry).toContainText('管理员');
    await adminExpect(accountEntry).not.toContainText(/Bootstrap Admin/i);
    await expectNoForbiddenAffordanceText(await accountEntry.innerText());
  }

  const adminMenu = await openVisibleAdminMenu(page, isMobile);
  if (adminMenu) {
    await adminExpect(adminMenu).toBeVisible();
    await adminExpect(adminMenu).toContainText('系统');
    await adminExpect(adminMenu).toContainText('用户治理');
    await adminExpect(adminMenu).toContainText('成本观测');
    await adminExpect(adminMenu).toContainText('通知');
    await adminExpect(adminMenu).toContainText('数据源运维');
    await adminExpect(adminMenu).toContainText('熔断诊断');
    await adminExpect(adminMenu).toContainText('证据复核');
    await adminExpect(adminMenu).toContainText('日志');
    await expectNoForbiddenAffordanceText(await adminMenu.innerText());
  }
}

appTest.describe('shell route clarity smoke', () => {
  appTest('redirects /zh/market to market overview with product-safe shell affordances', async ({ page }) => {
    for (const viewport of viewports) {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await page.setViewportSize(viewport);
      await installSignedInProductSession(page);
      await page.goto('/zh/market');
      await page.waitForLoadState('domcontentloaded');
      await expectMarketRedirectSurface(page, viewport.width < 768);
    }
  });

  appTest('redirects guest /zh/admin to understandable admin sign-in guidance', async ({ page }) => {
    for (const viewport of viewports) {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await page.setViewportSize(viewport);
      await installGuestProductSession(page);
      await page.goto('/zh/admin');
      await page.waitForLoadState('domcontentloaded');
      await expectGuestAdminGate(page);
    }
  });
});

adminTest.describe('admin redirect affordance smoke', () => {
  adminTest('redirects /zh/admin to system settings with product-safe admin affordances', async ({ page }) => {
    for (const viewport of viewports) {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      await page.setViewportSize(viewport);
      await openAdminRouteWithHarness(page, '/zh/admin', { displayName: 'Bootstrap Admin' });
      await expectAdminRedirectSurface(page, viewport.width < 768);
    }
  });
});
