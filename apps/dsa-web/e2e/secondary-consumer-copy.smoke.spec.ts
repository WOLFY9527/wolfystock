import type { Page, Route } from '@playwright/test';
import { expect, test } from './fixtures/appSmoke';
import { installPortfolioSmokeHarness } from './fixtures/portfolioSmoke';

const forbiddenInternalTerms = [
  'raw',
  'debug',
  'providerRoute',
  'sourceAuthority',
  'provider payload',
  'cache router',
  'env',
  'trace',
  'credential',
  'prompt',
  'stack trace',
  'payload',
];

const forbiddenTradingTerms = [
  '小仓试错',
  '第二笔',
  '建仓',
  '加仓',
  '减仓',
  '买入',
  '卖出',
  '下单',
  '券商',
  'buy',
  'sell',
  'order',
  'broker',
];

const allowedBoundaryTerms = [
  '不构成交易指令',
  '不构成交易或下单指令',
  '不构成交易建议',
];

const mockCurrentUser = {
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

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function buildForbiddenPattern(terms: string[]) {
  return new RegExp(terms.map(escapeRegExp).join('|'), 'i');
}

const forbiddenInternalPattern = buildForbiddenPattern(forbiddenInternalTerms);
const forbiddenTradingPattern = buildForbiddenPattern(forbiddenTradingTerms);
const forbiddenExecutionPattern = buildForbiddenPattern([
  '小仓试错',
  '第二笔',
  '建仓',
  '加仓',
  '减仓',
  '下单',
  '券商',
  'order',
  'broker',
]);

async function expectNoHorizontalOverflow(page: Page) {
  await expect
    .poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
    .toBe(true);
}

async function expectNoForbiddenTerms(page: Page, pattern: RegExp, allowed: string[] = []) {
  const bodyText = await page.locator('body').innerText();
  const sanitizedText = allowed.reduce((text, term) => text.replaceAll(term, ''), bodyText);
  expect(sanitizedText).not.toMatch(pattern);
}

async function installLiquidityPayload(page: Page) {
  await page.route('**/api/v1/market/liquidity-monitor', async (route) => {
    await fulfillJson(route, {
      endpoint: '/api/v1/market/liquidity-monitor',
      generatedAt: '2026-06-05T09:30:00+08:00',
      score: {
        value: 50,
        regime: 'neutral',
        confidence: 0.42,
        includedIndicatorCount: 1,
        possibleIndicatorWeight: 43,
        includedIndicatorWeight: 8,
      },
      freshness: {
        status: 'partial',
        weakestIndicatorFreshness: 'delayed',
        latestAsOf: '2026-06-05T09:30:00+08:00',
      },
      indicators: [
        {
          key: 'usd_pressure',
          label: 'DXY / 美元压力',
          status: 'partial',
          freshness: 'delayed',
          includedInScore: false,
          scoreContribution: 0,
          scoreWeight: 0,
          summary: '当前只有观察级样本，暂不形成方向结论。',
          updatedAt: '2026-06-05T09:30:00+08:00',
        },
      ],
      liquidityImpulseSynthesis: {
        liquidityImpulse: 'neutral',
        impulseLabel: '无明显方向',
        subtype: 'insufficient_evidence',
        confidence: 0.12,
        confidenceLabel: 'low',
        pillarScores: {
          dollar_pressure: 0,
          equity_flow_proxy: 0,
          crypto_liquidity_beta: 0,
          funding_stress: 0,
        },
        directionScore: 0,
        dominantDrivers: [],
        counterEvidence: [],
        dataGaps: [
          {
            key: 'missing:equity_flow_proxy',
            label: 'Missing scoring evidence for equity_flow_proxy',
            pillar: 'equity_flow_proxy',
            reason: 'missing_scoring_evidence',
          },
        ],
        narrativeBullets: [
          '数据不足，暂不形成结论。',
        ],
        evidenceQuality: {
          version: 'liquidity_impulse_synthesis_v1',
          inputCount: 1,
          scoringEvidenceCount: 0,
          scoringPillarCount: 0,
          coveredPillars: [],
          missingPillars: ['dollar_pressure', 'equity_flow_proxy', 'crypto_liquidity_beta', 'funding_stress'],
          discountedEvidenceCount: 0,
          observationOnlyEvidenceCount: 1,
          scoreBlockedEvidenceCount: 1,
          proxyOnlyScoringCount: 0,
          realScoringEvidenceCount: 0,
          allScoringEvidenceProxyOnly: false,
          dataGapCount: 1,
        },
        notInvestmentAdvice: true,
      },
      advisoryDisclosure: '仅用于观察市场流动性环境，不构成交易/下单指令。',
      sourceMetadata: {
        externalProviderCalls: false,
        providerRuntimeChanged: false,
        marketCacheMutation: false,
      },
    });
  });
}

async function installPortfolioEmptyHarness(page: Page) {
  await page.route('**/api/v1/portfolio/snapshot**', async (route) => {
    await fulfillJson(route, {
      as_of: '2026-04-15',
      cost_method: 'fifo',
      currency: 'USD',
      account_count: 1,
      realized_pnl: 0,
      unrealized_pnl: 0,
      fee_total: 0,
      tax_total: 0,
      fx_stale: false,
      total_cash: 5000,
      total_market_value: 0,
      total_equity: 5000,
      accounts: [
        {
          account_id: 1,
          account_name: 'Launch Owner Main',
          owner_id: 'user-1',
          broker: 'IBKR',
          market: 'us',
          base_currency: 'USD',
          as_of: '2026-04-15',
          cost_method: 'fifo',
          total_cash: 5000,
          total_market_value: 0,
          total_equity: 5000,
          realized_pnl: 0,
          unrealized_pnl: 0,
          fee_total: 0,
          tax_total: 0,
          fx_stale: false,
          positions: [],
        },
      ],
    });
  });
  await page.route('**/api/v1/portfolio/risk**', async (route) => {
    await fulfillJson(route, {
      as_of: '2026-04-15',
      account_id: null,
      cost_method: 'fifo',
      currency: 'USD',
      thresholds: {},
      concentration: {
        total_market_value: 0,
        top_weight_pct: 0,
        alert: false,
        top_positions: [],
      },
      sector_concentration: {
        total_market_value: 0,
        top_weight_pct: 0,
        alert: false,
        top_sectors: [],
        coverage: {},
        errors: [],
      },
      drawdown: {
        series_points: 0,
        max_drawdown_pct: 0,
        current_drawdown_pct: 0,
        alert: false,
        fx_stale: false,
      },
      stop_loss: {
        near_alert: false,
        triggered_count: 0,
        near_count: 0,
        items: [],
      },
    });
  });
  await page.route('**/api/v1/portfolio/trades**', async (route) => {
    await fulfillJson(route, { items: [], total: 0, page: 1, page_size: 20 });
  });
  await page.route('**/api/v1/portfolio/cash-ledger**', async (route) => {
    await fulfillJson(route, { items: [], total: 0, page: 1, page_size: 20 });
  });
  await page.route('**/api/v1/portfolio/corporate-actions**', async (route) => {
    await fulfillJson(route, { items: [], total: 0, page: 1, page_size: 20 });
  });
}

async function installWatchlistEmptyHarness(page: Page) {
  await page.route('**/api/v1/watchlist/items', async (route) => {
    await fulfillJson(route, { items: [] });
  });
  await page.route('**/api/v1/watchlist/refresh-status', async (route) => {
    await fulfillJson(route, {
      enabled: true,
      usTime: '08:45',
      cnTime: '09:00',
      hkTime: '09:00',
      status: 'idle',
      lastRunAt: null,
      nextRunAt: null,
    });
  });
  await page.route('**/api/v1/user-alerts/rules', async (route) => {
    await fulfillJson(route, {
      contract_version: 'user_alert_contract_v1',
      delivery_mode: 'in_app',
      in_app_only: true,
      owner_scoped: true,
      items: [],
    });
  });
  await page.route('**/api/v1/user-alerts/events**', async (route) => {
    await fulfillJson(route, {
      contract_version: 'user_alert_contract_v1',
      delivery_mode: 'in_app',
      in_app_only: true,
      owner_scoped: true,
      total: 0,
      limit: 20,
      offset: 0,
      items: [],
    });
  });
}

async function openRouteWithMockSession(page: Page, path: string) {
  await page.route('**/api/v1/auth/status**', async (route) => {
    await fulfillJson(route, {
      authEnabled: true,
      loggedIn: true,
      passwordSet: true,
      passwordChangeable: true,
      setupState: 'enabled',
      currentUser: mockCurrentUser,
    });
  });
  await page.route('**/api/v1/auth/me**', async (route) => {
    await fulfillJson(route, mockCurrentUser);
  });
  await page.goto(path);
  await page.waitForLoadState('domcontentloaded');
  await expect(page).not.toHaveURL(/\/guest(?:$|[/?#])/);
}

test.describe('secondary consumer copy smoke', () => {
  test('liquidity monitor keeps consumer-safe degraded copy', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await installLiquidityPayload(page);
    await openRouteWithMockSession(page, '/zh/market/liquidity-monitor');

    try {
      await expect(page.getByRole('heading', { name: '流动性监测' })).toBeVisible({ timeout: 15_000 });
      await expect(page.getByTestId('liquidity-summary-strip')).toContainText('仅观察');
      await expect(page.getByTestId('liquidity-context-rail')).toContainText('数据不足，暂不形成结论');
      await expectNoForbiddenTerms(page, forbiddenInternalPattern);
      await expectNoForbiddenTerms(page, forbiddenTradingPattern, allowedBoundaryTerms);
      await expectNoHorizontalOverflow(page);
    } finally {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  test('portfolio keeps empty-state CTA copy without execution wording', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await installPortfolioSmokeHarness(page);
    await installPortfolioEmptyHarness(page);
    await page.goto('/zh/portfolio');
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByTestId('portfolio-bento-page')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('portfolio-start-card')).toContainText('暂无持仓');
    await expect(page.getByTestId('portfolio-start-card')).toContainText(/先创建或选择账户|导入历史记录/);
    await expectNoForbiddenTerms(page, forbiddenInternalPattern);
    await expectNoForbiddenTerms(page, forbiddenTradingPattern, allowedBoundaryTerms);
    await expectNoHorizontalOverflow(page);
    expect(page.url()).toContain('/zh/portfolio');
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  });

  test('watchlist keeps empty-state CTA copy without harsh wording', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await installWatchlistEmptyHarness(page);
    await openRouteWithMockSession(page, '/zh/watchlist');

    try {
      await expect(page.getByTestId('watchlist-page')).toBeVisible({ timeout: 15_000 });
      await expect(page.locator('body')).toContainText(/观察列表|watchlist/i);
      await expect(page.getByTestId('watchlist-compact-empty-state')).toContainText('先从扫描器加入候选，也可以在扫描器手动补充代码。');
      await expect(page.getByTestId('watchlist-compact-empty-state')).toContainText('打开扫描器');
      await expectNoForbiddenTerms(page, forbiddenInternalPattern);
      await expectNoForbiddenTerms(page, forbiddenExecutionPattern, allowedBoundaryTerms);
      await expectNoHorizontalOverflow(page);
    } finally {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });

  test('backtest keeps rule preview and research-simulation boundary copy', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await openRouteWithMockSession(page, '/zh/backtest');

    try {
      await expect(page.getByTestId('backtest-bento-page')).toBeVisible({ timeout: 15_000 });
      await expect(page.locator('body')).toContainText('回测规则预览');
      await expect(page.locator('body')).toContainText('固定规则回测流程');
      await expect(page.locator('body')).toContainText(/研究模拟/);
      await expectNoForbiddenTerms(page, forbiddenInternalPattern);
      await expectNoForbiddenTerms(page, forbiddenExecutionPattern, allowedBoundaryTerms);
      await expectNoHorizontalOverflow(page);
    } finally {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  });
});
