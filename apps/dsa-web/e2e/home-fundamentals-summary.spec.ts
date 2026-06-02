import { expect as baseExpect, type Page, type Route } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';

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

const forbiddenFundamentalsCopyPattern =
  /buy|sell|undervalued|overvalued|rawProviderPayload|adminDiagnostics|providerRoute|valuationOpinion/i;

type EvidenceScenario = 'stable' | 'insufficient';

async function fulfillJson(route: Route, payload: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

function createEvidencePayload(scenario: EvidenceScenario) {
  if (scenario === 'insufficient') {
    return {
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
              raw_provider_payload: { provider_route: 'must-not-emit' },
              admin_diagnostics: { provider_route: 'must-not-emit' },
              provider_route: 'must-not-emit',
              valuation_opinion: 'undervalued',
            },
          },
        },
      ],
      meta: {
        generated_at: '2026-06-02T00:00:00Z',
        source: 'read_only_evidence_v2',
      },
    };
  }

  return {
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
            pe_ttm: 31.7,
            roe: 0.714,
            operating_margin: 0.412,
            period: 'TTM',
            source: 'financial_digest',
            freshness: 'recent',
            missing_fields: ['roa'],
            not_investment_advice: true,
            observation_only: true,
            score_contribution_allowed: false,
            source_authority_allowed: false,
            raw_provider_payload: { provider_route: 'must-not-emit' },
            admin_diagnostics: { provider_route: 'must-not-emit' },
            provider_route: 'must-not-emit',
            valuation_opinion: 'undervalued',
            buy_advice: 'buy',
            sell_advice: 'sell',
            undervalued_advice: 'undervalued',
            overvalued_advice: 'overvalued',
          },
        },
      },
    ],
    meta: {
      generated_at: '2026-06-02T00:00:00Z',
      source: 'read_only_evidence_v2',
    },
  };
}

async function installSignedInHomeRoutes(page: Page, scenario: EvidenceScenario) {
  let evidenceRequests = 0;

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
    evidenceRequests += 1;
    await fulfillJson(route, createEvidencePayload(scenario));
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

  return {
    getEvidenceRequests: () => evidenceRequests,
  };
}

async function expectNoHorizontalOverflow(page: Page) {
  await baseExpect.poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
}

async function openSignedInHome(page: Page) {
  await page.goto('/zh');
  await page.waitForLoadState('domcontentloaded');
  await expect(page.getByTestId('home-bento-dashboard')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText('Oracle Corporation')).toBeVisible({ timeout: 15_000 });
}

test.describe('home fundamentals summary browser smoke', () => {
  test('renders a compact consumer-safe fundamentals summary in the Home research console', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    const routes = await installSignedInHomeRoutes(page, 'stable');

    await openSignedInHome(page);

    const summary = page.getByTestId('home-stock-fundamentals-summary');
    await expect(summary).toBeVisible();
    await expect(summary).toHaveAttribute('data-research-card', 'fundamentals-summary');
    await expect(summary).toContainText('基本面摘要');
    await expect(summary).toContainText('仅供观察，不构成投资建议');
    await expect(summary).toContainText('TTM');
    await expect(summary).toContainText('最近更新');
    await expect(summary).toContainText('待补充 1 项');
    await expect(summary.getByTestId('home-stock-fundamentals-metric-market-cap')).toContainText('市值');
    await expect(summary.getByTestId('home-stock-fundamentals-metric-pe-ttm')).toContainText('PE(TTM)');
    await expect(summary.getByTestId('home-stock-fundamentals-metric-roe')).toContainText('ROE');
    await expect(summary.getByTestId('home-stock-fundamentals-metric-operating-margin')).toContainText('营业利润率');
    await expect(summary).toContainText('31.7x');
    await expect(summary).toContainText('71.4%');
    await expect(summary).toContainText('41.2%');

    const summaryText = await summary.innerText();
    expect(summaryText).not.toMatch(forbiddenFundamentalsCopyPattern);
    expect(routes.getEvidenceRequests()).toBeGreaterThanOrEqual(1);
    await expectNoHorizontalOverflow(page);
    expect(consoleErrors).toEqual([]);
    expect(unhandledApiRoutes).toEqual([]);
  });

  test('degrades to an observation-only insufficient-data state when fundamentals coverage is not stable', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    const routes = await installSignedInHomeRoutes(page, 'insufficient');

    await openSignedInHome(page);

    const summary = page.getByTestId('home-stock-fundamentals-summary');
    await expect(summary).toBeVisible();
    await expect(summary).toContainText('基本面摘要');
    await expect(summary).toContainText('暂无稳定基本面摘要');
    await expect(summary).toContainText('数据不足');
    await expect(summary).toContainText('TTM');
    await expect(summary).toContainText('部分更新');
    await expect(summary).toContainText('待补充 4 项');
    await expect(summary).toContainText('仅作观察');
    await expect(summary.getByTestId('home-bento-drawer-trigger-fundamentals')).toBeVisible();
    await expect(summary.getByTestId('home-stock-fundamentals-metric-market-cap')).toHaveCount(0);

    const summaryText = await summary.innerText();
    expect(summaryText).not.toMatch(forbiddenFundamentalsCopyPattern);
    expect(routes.getEvidenceRequests()).toBeGreaterThanOrEqual(1);
    await expectNoHorizontalOverflow(page);
    expect(consoleErrors).toEqual([]);
    expect(unhandledApiRoutes).toEqual([]);
  });
});
