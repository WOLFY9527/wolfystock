import {
  expect,
  expectForbiddenTradingWordingAbsent,
  expectNoHorizontalOverflow,
  expectRootNonEmpty,
  installGuestProductHarness,
  installProductAuthHarness,
  openProductRouteWithHarness,
  test,
} from './fixtures/productAuth';
import type { Page } from '@playwright/test';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
];

async function clickOptionsLabNav(page: Page) {
  const visibleHeaderLink = page.getByRole('link', { name: '期权实验室' }).first();
  if (await visibleHeaderLink.isVisible().catch(() => false)) {
    await visibleHeaderLink.click();
    return;
  }

  await page.getByRole('button', { name: '打开导航菜单' }).click();
  await page.getByRole('link', { name: '期权实验室' }).last().click();
}

test.describe('mocked product route auth browser harness', () => {
  test('renders localized Options Lab on direct authenticated reload', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await openProductRouteWithHarness(page, '/zh/options-lab');

      await expect(page).toHaveURL(/\/zh\/options-lab$/);
      await expect(page.getByRole('heading', { name: '期权实验室' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('options-lab-strategy-comparison')).toBeVisible();
      await expect(page.getByTestId('options-lab-decision-engine')).toBeVisible();
      await expect(page.getByTestId('options-lab-calls-table')).toBeVisible();
      expect(harness.requests.count('GET', '/api/v1/auth/status')).toBeGreaterThan(0);
      expect(harness.requests.count('GET', '/api/v1/options/underlyings/TEM/summary')).toBeGreaterThan(0);
      expect(harness.requests.count('POST', '/api/v1/options/strategies/compare')).toBeGreaterThan(0);
      expect(harness.requests.count('POST', '/api/v1/options/decision/evaluate')).toBeGreaterThan(0);
      await expect(page).not.toHaveURL(/\/guest(?:$|[/?#])/);
      await expectRootNonEmpty(page);
      await expectNoHorizontalOverflow(page);
      await expectForbiddenTradingWordingAbsent(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  test('keeps Options Lab reachable after client navigation from the product shell', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await installProductAuthHarness(page);

      await page.goto('/zh/options-lab');
      await expect(page.getByRole('heading', { name: '期权实验室' })).toBeVisible({ timeout: 15_000 });
      await expect(page).not.toHaveURL(/\/guest(?:$|[/?#])/);
      await clickOptionsLabNav(page);

      await expect(page).toHaveURL(/\/options-lab$/);
      await expect(page.getByRole('heading', { name: '期权实验室' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('options-lab-strategy-comparison')).toBeVisible();
      expect(harness.requests.count('GET', '/api/v1/auth/status')).toBeGreaterThan(0);
      await expectRootNonEmpty(page);
      await expectNoHorizontalOverflow(page);
      await expectForbiddenTradingWordingAbsent(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  test('guards logged-out direct Options Lab entry without rendering product content', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await installGuestProductHarness(page);

      await page.goto('/zh/options-lab');
      await page.waitForLoadState('domcontentloaded');

      await expect(page).toHaveURL(/\/zh\/options-lab$/);
      await expect(page.getByRole('heading', { name: '登录解锁 期权实验室' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('options-lab-strategy-comparison')).toHaveCount(0);
      expect(harness.requests.count('GET', '/api/v1/auth/status')).toBeGreaterThan(0);
      expect(harness.requests.wasFetched('GET', '/api/v1/options/underlyings/TEM/summary')).toBe(false);
      await expectRootNonEmpty(page);
      await expectNoHorizontalOverflow(page);
      await expectForbiddenTradingWordingAbsent(page);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });
});
