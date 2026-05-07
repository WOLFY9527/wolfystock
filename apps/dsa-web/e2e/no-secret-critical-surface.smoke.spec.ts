import { expect, type Page } from '@playwright/test';
import { test as appTest } from './fixtures/appSmoke';
import {
  expectForbiddenTradingWordingAbsent,
  expectNoHorizontalOverflow,
  expectRootNonEmpty,
  openProductRouteWithHarness,
  test as productTest,
} from './fixtures/productAuth';
import {
  expectNoRawSecretLikeText,
  openAdminRouteWithHarness,
  test as adminTest,
} from './fixtures/adminAuth';
import { installPortfolioSmokeHarness } from './fixtures/portfolioSmoke';

const viewports = [
  { size: { width: 1440, height: 1000 } },
  { size: { width: 390, height: 844 } },
] as const;

const rawDebugArtifactPattern = /raw\s+(payload|response)|debug\s+(payload|response|panel)|stack\s+(trace|details)|traceback|bearer\s+[a-z0-9._-]+|api[_\s-]?key\s*[=:]|password\s*[=:]|session[_\s-]?id\s*[=:]|secret\s*[=:]|sk-[a-z0-9_-]{12,}|ghp_[a-z0-9_]{12,}|xox[baprs]-[a-z0-9-]{12,}/i;

async function installAuthenticatedAppSmokeSession(page: Page) {
  await page.route('**/api/v1/auth/status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        authEnabled: true,
        loggedIn: true,
        passwordSet: true,
        passwordChangeable: true,
        setupState: 'enabled',
        currentUser: {
          id: 'user-1',
          username: 'wolfy-user',
          displayName: 'Wolfy User',
          role: 'user',
          isAdmin: false,
          isAuthenticated: true,
          transitional: false,
          authEnabled: true,
        },
      }),
    });
  });
}

async function expectCriticalSurfaceClean(page: Page) {
  await expectRootNonEmpty(page);
  await expectNoHorizontalOverflow(page);
  await expectForbiddenTradingWordingAbsent(page);
  await expectNoRawSecretLikeText(page);
  await expect(page.locator('details[open]')).toHaveCount(0);

  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(rawDebugArtifactPattern);
}

appTest.describe('no-secret critical public surfaces', () => {
  appTest('home/dashboard exposes no raw secrets or debug artifacts', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport.size);

      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');
      await expect(page.getByTestId('home-bento-dashboard')).toBeVisible({ timeout: 15_000 });
      await expectCriticalSurfaceClean(page);
    }
  });

  appTest('market overview exposes no raw secrets or debug artifacts', async ({ page }) => {
    await installAuthenticatedAppSmokeSession(page);

    for (const viewport of viewports) {
      await page.setViewportSize(viewport.size);

      await page.goto('/market-overview');
      await page.waitForLoadState('domcontentloaded');
      await expect(page.getByTestId('market-overview-shell')).toBeVisible({ timeout: 15_000 });
      await expectCriticalSurfaceClean(page);
    }
  });
});

productTest.describe('no-secret critical product surfaces', () => {
  productTest('options lab keeps developer diagnostics collapsed and secret-free', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport.size);
      const harness = await openProductRouteWithHarness(page, '/zh/options-lab');

      await expect(page.getByRole('heading', { name: '期权实验室' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('options-lab-strategy-comparison')).toBeVisible();
      await expect(page.getByTestId('options-lab-decision-engine')).toBeVisible();
      await expect(page.getByTestId('options-lab-calls-table')).toBeVisible();
      await expectCriticalSurfaceClean(page);

      expect(harness.requests.count('GET', '/api/v1/options/underlyings/TEM/summary')).toBeGreaterThan(0);
      expect(harness.requests.count('POST', '/api/v1/options/strategies/compare')).toBeGreaterThan(0);
      expect(harness.requests.count('POST', '/api/v1/options/decision/evaluate')).toBeGreaterThan(0);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  productTest('portfolio exposes no raw secrets or order wording with mocked data', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport.size);
      const harness = await installPortfolioSmokeHarness(page);

      await page.goto('/portfolio');
      await page.waitForLoadState('domcontentloaded');
      await expect(page.getByTestId('portfolio-bento-page')).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('portfolio-total-assets-card')).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('portfolio-current-holdings-panel')).toBeVisible({ timeout: 15_000 });
      await expectCriticalSurfaceClean(page);

      expect(harness.requests.count('GET', '/api/v1/portfolio/snapshot')).toBeGreaterThan(0);
      expect(harness.requests.count('GET', '/api/v1/portfolio/risk')).toBeGreaterThan(0);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });
});

adminTest.describe('no-secret critical admin diagnostics surfaces', () => {
  adminTest('cost observability keeps raw details collapsed and secret-free', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport.size);
      const harness = await openAdminRouteWithHarness(page, '/zh/admin/cost-observability');

      await expect(page.getByRole('heading', { name: '成本观测' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('quota-dry-run-panel')).toBeVisible();
      await expect(page.getByTestId('llm-ledger-panel')).toBeVisible();
      await expect(page.getByTestId('model-pricing-policy-panel')).toBeVisible();
      await expectCriticalSurfaceClean(page);

      expect(harness.requests.count('GET', '/api/v1/admin/cost/duplicate-summary')).toBeGreaterThan(0);
      expect(harness.requests.count('POST', '/api/v1/admin/cost/quota-dry-run')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/cost/llm-ledger-summary')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/cost/model-pricing-policies')).toBe(1);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  adminTest('provider diagnostics uses mocked read-only APIs without raw provider detail leakage', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport.size);
      const harness = await openAdminRouteWithHarness(page, '/zh/admin/provider-circuits');

      await expect(page.getByRole('heading', { name: 'Provider 熔断诊断' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByText('当前熔断状态', { exact: true })).toBeVisible();
      await expect(page.getByRole('heading', { name: '最近熔断事件' })).toBeVisible();
      await expect(page.getByRole('heading', { name: '配额窗口' })).toBeVisible();
      await expect(page.getByRole('heading', { name: '探测事件' })).toBeVisible();
      await expectCriticalSurfaceClean(page);

      expect(harness.requests.count('GET', '/api/v1/admin/providers/circuits')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/providers/circuits/events')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/providers/quota-windows')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/providers/probe-events')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/providers/sla-readiness')).toBe(1);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });
});
