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
const executableTradingActionPattern = /买入按钮|建议买入|建议卖出|卖出指令|立即交易|订单载荷|开仓|平仓|加仓|减仓|持仓建议|仓位建议|决策级|decision[-\s]?grade|buy now|sell now|place order|submit order|best contract|guaranteed/i;
const providerCircuitSecondaryDisclosureLabel = 'L2 分组诊断：熔断状态 / 事件 / 配额 / 探测 / SLA（已脱敏摘要）';

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

async function expectCriticalSurfaceClean(page: Page, expectedExpandedDisclosureCount = 0) {
  await expectRootNonEmpty(page);
  await expectNoHorizontalOverflow(page);
  await expectForbiddenTradingWordingAbsent(page);
  await expectNoRawSecretLikeText(page);
  await expect(page.getByRole('button', { name: /^收起 / })).toHaveCount(expectedExpandedDisclosureCount);

  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(rawDebugArtifactPattern);
}

async function expectOptionsLabSurfaceClean(page: Page) {
  await expectRootNonEmpty(page);
  await expectNoHorizontalOverflow(page);
  await expectNoRawSecretLikeText(page);
  await expect(page.getByRole('button', { name: /^收起 / })).toHaveCount(0);

  const bodyText = await page.locator('body').innerText();
  expect(bodyText).not.toMatch(rawDebugArtifactPattern);
  expect(bodyText).not.toMatch(executableTradingActionPattern);
}

async function expectProviderCircuitSecondaryDisclosure(page: Page) {
  const expandButton = page.getByRole('button', { name: `展开 ${providerCircuitSecondaryDisclosureLabel}` });

  await expect(page.getByText(providerCircuitSecondaryDisclosureLabel, { exact: true })).toBeVisible();
  await expect(page.getByText(/已脱敏 bucket\/边界默认折叠/)).toBeVisible();
  await expect(expandButton).toBeVisible();
  await expect(expandButton).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByRole('heading', { name: '最近熔断事件' })).toHaveCount(0);
  await expandButton.click();
  await expect(page.getByRole('button', { name: `收起 ${providerCircuitSecondaryDisclosureLabel}` })).toHaveAttribute('aria-expanded', 'true');
  await expect(page.getByRole('heading', { name: '最近熔断事件', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: '配额窗口', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: '探测事件', exact: true })).toBeVisible();
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
      await expectOptionsLabSurfaceClean(page);

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
      await expect(page.getByRole('heading', { name: '总资产' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByRole('heading', { name: /当前持仓/ })).toBeVisible({ timeout: 15_000 });
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
      await expect(page.getByTestId('llm-ledger-panel')).toHaveCount(0);
      await expect(page.getByTestId('model-pricing-policy-panel')).toHaveCount(0);
      await expectCriticalSurfaceClean(page);

      expect(harness.requests.count('GET', '/api/v1/admin/cost/duplicate-summary')).toBeGreaterThan(0);
      expect(harness.requests.count('POST', '/api/v1/admin/cost/quota-dry-run')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/cost/llm-ledger-summary')).toBe(0);
      expect(harness.requests.count('GET', '/api/v1/admin/cost/model-pricing-policies')).toBe(0);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  adminTest('provider diagnostics uses mocked read-only APIs without raw provider detail leakage', async ({ page }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport.size);
      const harness = await openAdminRouteWithHarness(page, '/zh/admin/provider-circuits');

      await expect(page.getByRole('heading', { name: '数据源熔断诊断' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByText('熔断状态', { exact: true })).toBeVisible();
      await expectCriticalSurfaceClean(page);
      await expectProviderCircuitSecondaryDisclosure(page);
      await expectCriticalSurfaceClean(page, 1);

      expect(harness.requests.count('GET', '/api/v1/admin/providers/circuits')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/providers/circuits/events')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/providers/quota-windows')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/providers/probe-events')).toBe(1);
      expect(harness.requests.count('GET', '/api/v1/admin/providers/sla-readiness')).toBe(1);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });
});
