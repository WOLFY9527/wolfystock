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
import {
  forbiddenPortfolioCredentialSentinels,
  forbiddenPortfolioOwnerSentinels,
  installPortfolioSmokeHarness,
  visibleOwnerPortfolioSentinels,
} from './fixtures/portfolioSmoke';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
];

const rawLaunchArtifactPattern = /raw\s+(payload|response|trace)|debug\s+(payload|response|schema|panel)|provider\s+(payload|credential)|stack\s+(trace|details)|traceback|bearer\s+[a-z0-9._-]+|api[_\s-]?key\s*[=:]|password\s*[=:]|session[_\s-]?id\s*[=:]|cookie\s*[=:]|secret\s*[=:]|sk-[a-z0-9_-]{12,}|ghp_[a-z0-9_]{12,}|xox[baprs]-[a-z0-9-]{12,}/i;
const brokerCredentialOrOrderPattern = /broker[_\s-]?credentials?|broker[_\s-]?order|order[_\s-]?payload|place[_\s-]?order|submit[_\s-]?order|execute[_\s-]?order|payload_json|sync_metadata_json|raw[_\s-]?provider[_\s-]?payload|provider[_\s-]?credential|api[_\s-]?key|access[_\s-]?token|refresh[_\s-]?token|session[_\s-]?token|cookie\s*[=:]|debug[_\s-]?schema|stack[_\s-]?trace/i;

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

async function expectNoBrokerCredentialOrOrderPayloads(page: Page) {
  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(brokerCredentialOrOrderPattern);
}

async function expectVisibleTextPresent(page: Page, sentinels: string[]) {
  const bodyText = await page.locator('body').innerText();
  for (const sentinel of sentinels) {
    expect(bodyText).toContain(sentinel);
  }
}

async function expectVisibleTextAbsent(page: Page, sentinels: string[]) {
  const bodyText = await page.locator('body').innerText();
  for (const sentinel of sentinels) {
    expect(bodyText).not.toContain(sentinel);
  }
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
  await expectNoBrokerCredentialOrOrderPayloads(page);
}

async function assertAdminShell(page: Page) {
  await expectRootNonEmpty(page);
  await expectNoHorizontalOverflow(page);
  await expectNoRawSecretLikeText(page);
  await expectNoRawLaunchArtifacts(page);
  await expectNoBrokerCredentialOrOrderPayloads(page);
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

  appTest('market rotation radar stays clean on desktop and mobile', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);

      await installAuthenticatedAppSmokeSession(page);
      await page.goto('/zh/market-overview');
      await page.waitForLoadState('domcontentloaded');
      if (viewport.width >= 768) {
        const primaryNav = page.getByRole('navigation', { name: '导航菜单' });
        await appExpect(primaryNav.getByRole('link', { name: '市场总览' })).toHaveClass(/is-active/);
        const rotationNavLink = primaryNav.getByRole('link', { name: '轮动雷达' });
        await appExpect(rotationNavLink).toBeVisible();
        await appExpect(rotationNavLink).toHaveAttribute('href', '/zh/market/rotation-radar');
        await rotationNavLink.click();
      } else {
        await page.getByRole('button', { name: '打开导航菜单' }).click();
        const drawerNav = page.getByRole('navigation', { name: '导航菜单' });
        const rotationNavLink = drawerNav.getByRole('link', { name: '轮动雷达' });
        await appExpect(rotationNavLink).toBeVisible();
        await rotationNavLink.click();
      }

      await appExpect(page).toHaveURL(/\/zh\/market\/rotation-radar$/);
      await appExpect(page.getByTestId('market-rotation-radar-page')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByRole('heading', { name: '资金轮动雷达' })).toBeVisible();
      if (viewport.width >= 768) {
        const rotationNavLink = page.getByRole('navigation', { name: '导航菜单' }).getByRole('link', { name: '轮动雷达' });
        await appExpect(rotationNavLink).toBeVisible();
        await appExpect(rotationNavLink).toHaveAttribute('href', '/zh/market/rotation-radar');
        await appExpect(rotationNavLink).toHaveClass(/is-active/);
        await appExpect(page.getByRole('navigation', { name: '导航菜单' }).getByRole('link', { name: '市场总览' })).not.toHaveClass(/is-active/);
      } else {
        await appExpect(page.getByTestId('shell-mobile-active-route')).toHaveText('轮动雷达');
        await page.getByRole('button', { name: '打开导航菜单' }).click();
        await appExpect(page.getByRole('navigation', { name: '导航菜单' }).getByRole('link', { name: '轮动雷达' })).toBeVisible();
      }
      await appExpect(page.getByTestId('rotation-radar-summary-band')).toBeVisible();
      await appExpect(page.getByTestId('rotation-theme-card-ai_applications')).toBeVisible();
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

      await page.setViewportSize(viewport);
      await installAuthenticatedAppSmokeSession(page);
      await page.goto('/backtest/results/34');
      await page.waitForLoadState('domcontentloaded');
      await appExpect(page.getByTestId('deterministic-backtest-result-page')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('backtest-result-report')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByRole('button', { name: '导出交易CSV' })).toBeVisible();
      await appExpect(page.getByRole('button', { name: '导出账本CSV' })).toBeVisible();
      await appExpect(page.getByTestId('backtest-report-advanced-details')).toBeVisible();
      await expectVisibleTextAbsent(page, [
        'mock-canary-place-order-payload',
        'mock-canary-broker-credentials',
        'mock-canary-raw-provider-payload',
      ]);
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
      await expectVisibleTextPresent(page, visibleOwnerPortfolioSentinels);
      await expectVisibleTextAbsent(page, [
        ...forbiddenPortfolioOwnerSentinels,
        ...forbiddenPortfolioCredentialSentinels,
      ]);
      await assertProductShell(page);

      expect(harness.requests.count('GET', '/api/v1/auth/status')).toBeGreaterThan(0);
      expect(harness.requests.count('GET', '/api/v1/portfolio/snapshot')).toBeGreaterThan(0);
      expect(harness.requests.count('GET', '/api/v1/portfolio/risk')).toBeGreaterThan(0);
      expect(harness.requests.calls.filter((entry) => entry.startsWith('POST '))).toEqual([]);
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

  adminTest('admin user portfolio projection stays read-only and owner-safe on desktop and mobile', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      const harness = await openAdminRouteWithHarness(page, '/zh/admin/users/user-123?tab=portfolio');

      await appExpect(page.getByRole('heading', { name: '组合只读总览' })).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByText('只读投影').first()).toBeVisible();
      await expectVisibleTextPresent(page, ['Alice Launch Portfolio', 'AAPL']);
      await expectVisibleTextAbsent(page, [
        'Bob Admin Portfolio',
        'MSFT-ADMIN-BOB-PRIVATE',
        'mock-canary-bob-admin-broker-account',
        'mock-canary-bob-admin-session-token',
        'mock-canary-admin-broker-account',
        'mock-canary-admin-api-key',
        'mock-canary-admin-access-token',
        'mock-canary-admin-broker-order-payload',
        'mock-canary-admin-place-order-payload',
        'mock-canary-admin-raw-provider-payload',
        'mock-canary-admin-execute-order-payload',
        'mock-canary-admin-broker-credentials',
      ]);
      await assertAdminShell(page);

      expect(harness.requests.count('GET', '/api/v1/admin/users/user-123/portfolio-summary')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/users/user-123/holdings')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/users/user-123/portfolio-activity')).toBe(1);
      expect(harness.requests.calls.filter((entry) => entry.startsWith('POST '))).toEqual([]);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });
});
