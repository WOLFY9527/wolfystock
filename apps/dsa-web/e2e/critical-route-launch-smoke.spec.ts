import { expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { expect as appExpect, test as appTest } from './fixtures/appSmoke';
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
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
];

const rawLaunchArtifactPattern = /raw\s+(payload|response|trace)|debug\s+(payload|response|schema|panel)|provider\s+payload|stack\s+(trace|details)|traceback|bearer\s+[a-z0-9._-]+|api[_\s-]?key\s*[=:]|password\s*[=:]|session[_\s-]?id\s*[=:]|secret\s*[=:]|sk-[a-z0-9_-]{12,}|ghp_[a-z0-9_]{12,}|xox[baprs]-[a-z0-9-]{12,}/i;

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

async function expectNoRawLaunchArtifacts(page: Page) {
  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(rawLaunchArtifactPattern);
}

async function assertPublicShell(page: Page) {
  await expectRootNonEmpty(page);
  await expectNoHorizontalOverflow(page);
  await expectForbiddenTradingWordingAbsent(page);
  await expectNoRawLaunchArtifacts(page);
}

async function assertProductShell(page: Page) {
  await expectRootNonEmpty(page);
  await expectNoHorizontalOverflow(page);
  await expectForbiddenTradingWordingAbsent(page);
  await expectNoRawLaunchArtifacts(page);
}

async function assertAdminShell(page: Page) {
  await expectRootNonEmpty(page);
  await expectNoHorizontalOverflow(page);
  await expectNoRawSecretLikeText(page);
  await expectNoRawLaunchArtifacts(page);
}

appTest.describe('public launch route smoke', () => {
  appTest('home/dashboard stays clean on desktop and mobile', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);

      await page.goto('/');
      await page.waitForLoadState('domcontentloaded');
      await appExpect(page.getByTestId('home-bento-dashboard')).toBeVisible({ timeout: 15_000 });
      await assertPublicShell(page);
    }
  });

  appTest('market overview stays clean on desktop and mobile', async ({ page }) => {
    await installAuthenticatedAppSmokeSession(page);

    for (const viewport of viewports) {
      await page.setViewportSize(viewport);

      await page.goto('/market-overview');
      await page.waitForLoadState('domcontentloaded');
      await appExpect(page.getByTestId('market-overview-shell')).toBeVisible({ timeout: 15_000 });
      await assertPublicShell(page);
    }
  });

  appTest('scanner and backtest launch routes stay clean on desktop and mobile', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);

      await installAuthenticatedAppSmokeSession(page);
      await page.goto('/scanner');
      await page.waitForLoadState('domcontentloaded');
      await appExpect(page.getByTestId('user-scanner-bento-page')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('scanner-sidebar')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('scanner-results-pane')).toBeVisible({ timeout: 15_000 });
      await assertProductShell(page);

      await page.setViewportSize(viewport);
      await installAuthenticatedAppSmokeSession(page);
      await page.goto('/backtest');
      await page.waitForLoadState('domcontentloaded');
      await appExpect(page.getByTestId('backtest-bento-page')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('backtest-subnav')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('backtest-v1-page')).toBeVisible({ timeout: 15_000 });
      await assertProductShell(page);
    }
  });
});

productTest.describe('product launch route smoke', () => {
  productTest('options lab stays clean on desktop and mobile', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await openProductRouteWithHarness(page, '/zh/options-lab');

      await appExpect(page.getByRole('heading', { name: '期权实验室' })).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('options-lab-strategy-comparison')).toBeVisible();
      await appExpect(page.getByTestId('options-lab-decision-engine')).toBeVisible();
      await appExpect(page.getByTestId('options-lab-calls-table')).toBeVisible();
      await expectForbiddenTradingWordingAbsent(page);
      await assertProductShell(page);

      expect(harness.requests.count('GET', '/api/v1/auth/status')).toBeGreaterThan(0);
      expect(harness.requests.count('GET', '/api/v1/options/underlyings/TEM/summary')).toBeGreaterThan(0);
      expect(harness.requests.count('POST', '/api/v1/options/strategies/compare')).toBeGreaterThan(0);
      expect(harness.requests.count('POST', '/api/v1/options/decision/evaluate')).toBeGreaterThan(0);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  productTest('portfolio route stays clean on desktop and mobile when mocked', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await installPortfolioSmokeHarness(page);

      await page.goto('/portfolio');
      await page.waitForLoadState('domcontentloaded');
      await appExpect(page.getByTestId('portfolio-bento-page')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('portfolio-total-assets-card')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('portfolio-current-holdings-panel')).toBeVisible({ timeout: 15_000 });
      await assertProductShell(page);

      expect(harness.requests.count('GET', '/api/v1/auth/status')).toBeGreaterThan(0);
      expect(harness.requests.count('GET', '/api/v1/portfolio/snapshot')).toBeGreaterThan(0);
      expect(harness.requests.count('GET', '/api/v1/portfolio/risk')).toBeGreaterThan(0);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });
});

adminTest.describe('admin launch route smoke', () => {
  adminTest('cost observability stays clean on desktop and mobile', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await openAdminRouteWithHarness(page, '/zh/admin/cost-observability');

      await appExpect(page.getByRole('heading', { name: '成本观测' })).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('quota-dry-run-panel')).toBeVisible();
      await appExpect(page.getByTestId('llm-ledger-panel')).toBeVisible();
      await appExpect(page.getByTestId('model-pricing-policy-panel')).toBeVisible();
      await assertAdminShell(page);

      expect(harness.requests.count('GET', '/api/v1/admin/cost/duplicate-summary')).toBeGreaterThan(0);
      expect(harness.requests.count('POST', '/api/v1/admin/cost/quota-dry-run')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/cost/llm-ledger-summary')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/cost/model-pricing-policies')).toBe(1);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  adminTest('provider diagnostics stays clean on desktop and mobile', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await openAdminRouteWithHarness(page, '/zh/admin/provider-circuits');

      await appExpect(page.getByRole('heading', { name: 'Provider 熔断诊断' })).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByText('当前熔断状态', { exact: true })).toBeVisible();
      await appExpect(page.getByRole('heading', { name: '最近熔断事件' })).toBeVisible();
      await appExpect(page.getByRole('heading', { name: '配额窗口' })).toBeVisible();
      await appExpect(page.getByRole('heading', { name: '探测事件' })).toBeVisible();
      await assertAdminShell(page);

      expect(harness.requests.count('GET', '/api/v1/admin/providers/circuits')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/providers/circuits/events')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/providers/quota-windows')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/providers/probe-events')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/providers/sla-readiness')).toBe(1);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  adminTest('system settings stays clean on desktop and mobile', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await openAdminRouteWithHarness(page, '/zh/settings/system');

      await appExpect(page.getByTestId('settings-bento-page')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('system-health-summary')).toBeVisible();
      await appExpect(page.getByTestId('duckdb-quant-panel')).toBeVisible();
      await assertAdminShell(page);

      expect(harness.requests.count('GET', '/api/v1/system/config')).toBeGreaterThan(0);
      expect(harness.requests.count('GET', '/api/v1/quant/duckdb/health')).toBeGreaterThan(0);
      expect(harness.requests.count('GET', '/api/v1/quant/duckdb/coverage')).toBeGreaterThan(0);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });
});
