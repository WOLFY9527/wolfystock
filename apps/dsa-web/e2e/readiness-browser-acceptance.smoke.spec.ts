import { expect, type Page, type Route } from '@playwright/test';
import { expect as appExpect, test as appTest } from './fixtures/appSmoke';
import {
  expectForbiddenTradingWordingAbsent,
  expectNoHorizontalOverflow,
  expectRootNonEmpty,
  openProductRouteWithHarness,
  test as productTest,
} from './fixtures/productAuth';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
] as const;

const rawLeakPattern = /raw|debug|provider|schema|payload|trace|internal/i;
const tradingPattern = /buy|sell|order|trade|broker|买入|卖出|下单|交易|券商/i;
const safeVerdictPattern = /研究证据可用|仅观察|证据不足|等待证据更新|Research-ready|Observe only|Evidence insufficient|Waiting/i;

const signedInUser = {
  id: 'user-1',
  username: 'wolfy-user',
  displayName: 'Wolfy User',
  role: 'user',
  isAdmin: false,
  isAuthenticated: true,
  transitional: false,
  authEnabled: true,
};

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function installSignedInHomeRoutes(page: Page) {
  await page.route('**/api/v1/auth/status**', async (route) => {
    await fulfillJson(route, {
      authEnabled: true,
      loggedIn: true,
      passwordSet: true,
      passwordChangeable: true,
      setupState: 'enabled',
      currentUser: signedInUser,
    });
  });

  await page.route('**/api/v1/auth/me**', async (route) => {
    await fulfillJson(route, signedInUser);
  });

  await page.route('**/api/v1/stocks/*/evidence**', async (route) => {
    await fulfillJson(route, {
      symbols: ['ORCL'],
      items: [
        {
          symbol: 'ORCL',
          market: 'US',
          stock_evidence_packet: {
            schema_version: 'stock_evidence_packet_v1',
            not_investment_advice: true,
            observation_only: true,
            fundamentals_summary: {
              market_cap: 512300000000,
              period: 'TTM',
              source: 'financial_digest',
              freshness: 'partial',
              missing_fields: ['pe_ttm', 'pb', 'roe', 'roa'],
              not_investment_advice: true,
              observation_only: true,
              score_contribution_allowed: false,
              source_authority_allowed: false,
            },
          },
        },
      ],
      meta: {
        generated_at: '2026-06-02T00:00:00Z',
        source: 'read_only_evidence_v2',
      },
    });
  });

  await page.route('**/api/v1/stocks/ORCL/history**', async (route) => {
    await fulfillJson(route, {
      stock_code: 'ORCL',
      stock_name: 'Oracle',
      period: 'daily',
      source: 'fixture_history',
      source_confidence: {
        source: 'fixture_history',
        source_label: '本地审核样例',
        as_of: '2026-06-02T00:00:00Z',
        freshness: 'available',
        is_fallback: false,
        is_stale: false,
        is_partial: false,
        is_synthetic: false,
        is_unavailable: false,
        confidence_weight: 1,
        coverage: 1,
      },
      data: [
        { date: '2026-05-27', open: 120.0, high: 121.2, low: 119.4, close: 120.8, volume: 8100000, change_percent: 0.7 },
        { date: '2026-05-28', open: 120.9, high: 122.4, low: 120.1, close: 121.7, volume: 7900000, change_percent: 0.74 },
        { date: '2026-05-29', open: 121.8, high: 123.1, low: 121.0, close: 122.2, volume: 8400000, change_percent: 0.41 },
        { date: '2026-05-30', open: 122.0, high: 123.6, low: 121.4, close: 123.1, volume: 8600000, change_percent: 0.74 },
        { date: '2026-06-02', open: 123.2, high: 124.1, low: 122.7, close: 123.8, volume: 8050000, change_percent: 0.57 },
      ],
    });
  });
}

async function openSignedInHome(page: Page) {
  await installSignedInHomeRoutes(page);
  await page.goto('/zh');
  await page.waitForLoadState('domcontentloaded');
  await appExpect(page.getByTestId('home-bento-dashboard')).toBeVisible({ timeout: 15_000 });
}

async function signIn(page: Page, redirectPath: string) {
  await page.goto(`/login?redirect=${encodeURIComponent(redirectPath)}`);
  const username = page.locator('#username');
  if (await username.waitFor({ state: 'visible', timeout: 10_000 }).then(() => true).catch(() => false)) {
    await username.fill('wolfy-user');
    await page.locator('#password').fill('mock-password');
    await Promise.all([
      page.waitForResponse((response) => response.url().includes('/api/v1/auth/login') && response.status() === 200),
      page.getByRole('button', { name: /sign in|登录继续|授权进入工作台|完成设置并登录/i }).click(),
    ]);
    await page.waitForURL(/\/$/);
  }
  await page.goto(redirectPath);
  await page.waitForLoadState('domcontentloaded');
}

async function expectSafeReadinessStrip(page: Page, testId: string) {
  const strip = page.getByTestId(testId);
  await appExpect(strip).toBeVisible({ timeout: 15_000 });
  await appExpect(strip).toContainText(/研究就绪度|Research readiness/);
  await appExpect(strip).toContainText(safeVerdictPattern);
  await appExpect(strip).not.toContainText(rawLeakPattern);
  await appExpect(strip).not.toContainText(tradingPattern);
}

appTest.describe('consumer research readiness browser acceptance', () => {
  appTest('Home readiness strip is visible and consumer-safe', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await openSignedInHome(page);
      await expectRootNonEmpty(page);
      await expectNoHorizontalOverflow(page);
      await expectSafeReadinessStrip(page, 'home-research-readiness-strip');
      expect(consoleErrors).toEqual([]);
      expect(unhandledApiRoutes).toEqual([]);
    }
  });

  appTest('Market Overview readiness strip is visible and consumer-safe', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await installSignedInHomeRoutes(page);
      await signIn(page, '/market-overview');
      await appExpect(page.getByTestId('market-overview-shell')).toBeVisible({ timeout: 15_000 });
      await expectRootNonEmpty(page);
      await expectNoHorizontalOverflow(page);
      await expectSafeReadinessStrip(page, 'market-overview-research-readiness-strip');
      expect(consoleErrors).toEqual([]);
      expect(unhandledApiRoutes).toEqual([]);
    }
  });

  appTest('Scanner readiness strip is visible and consumer-safe', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await page.route('**/api/v1/auth/status', async (route) => {
        await fulfillJson(route, {
          authEnabled: true,
          loggedIn: true,
          passwordSet: true,
          passwordChangeable: true,
          setupState: 'enabled',
          currentUser: signedInUser,
        });
      });
      await page.goto('/zh/scanner');
      await page.waitForLoadState('domcontentloaded');
      await appExpect(page.getByTestId('user-scanner-workspace')).toBeVisible({ timeout: 15_000 });
      await expectRootNonEmpty(page);
      await expectNoHorizontalOverflow(page);
      await expectSafeReadinessStrip(page, 'scanner-research-readiness-strip');
      expect(consoleErrors).toEqual([]);
      expect(unhandledApiRoutes).toEqual([]);
    }
  });
});

productTest.describe('Options Lab readiness browser acceptance', () => {
  productTest('readiness verdict is visible and consumer-safe', async ({ page, consoleErrors }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await openProductRouteWithHarness(page, '/zh/options-lab');
      await expectRootNonEmpty(page);
      await expectNoHorizontalOverflow(page);
      await expectSafeReadinessStrip(page, 'options-lab-research-readiness-strip');
      await expectForbiddenTradingWordingAbsent(page);
      expect(consoleErrors).toEqual([]);
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });
});
