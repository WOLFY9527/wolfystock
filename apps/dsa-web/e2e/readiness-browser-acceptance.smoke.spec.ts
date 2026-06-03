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
const internalEvidenceCoveragePattern =
  /provider_timeout|sourceauthority|source_authority|fallbackorproxy|fallback_or_proxy|router|cache|credential|providerroute|partial_coverage|coverage_not_assembled|env/i;

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

  await page.route('**/api/v1/history/3**', async (route) => {
    await fulfillJson(route, {
      meta: {
        id: 3,
        queryId: 'q3',
        stockCode: 'ORCL',
        stockName: 'Oracle',
        companyName: 'Oracle',
        reportType: 'detailed',
        createdAt: '2026-04-27T08:00:00Z',
        reportGeneratedAt: '2026-04-27T08:03:00Z',
        currentPrice: 130.2,
        changePct: -0.4,
        modelUsed: 'fixture-model',
        isTest: true,
      },
      summary: {
        analysisSummary: 'Oracle is holding its post-earnings platform.',
        operationAdvice: 'Wait for a controlled pullback before adding.',
        trendPrediction: 'Constructive for the next 72 hours.',
        sentimentScore: 78,
        sentimentLabel: 'Bullish',
      },
      strategy: {
        idealBuy: '121.80 - 124.60',
        stopLoss: '117.40',
        takeProfit: '133.50',
      },
      details: {
        dataQualityReport: {
          dataQualityTier: 'analysis_grade',
          dataQualityScore: 68,
          requiredAvailable: true,
          importantMissing: ['fundamentals.eps'],
          optionalMissing: ['optional_enrichment_pending'],
          staleSources: [],
          providerTimeouts: ['gnews:news'],
          providerCooldowns: ['fmp:fundamentals'],
          confidenceCap: 70,
          reasonCodes: ['important_data_missing', 'optional_enrichment_missing'],
          freshness: { marketSessionDate: '2026-05-05' },
          enrichmentStatus: 'pending',
          enrichmentSources: ['news', 'sentiment', 'detailed_fundamentals'],
          completedSources: ['sentiment'],
          pendingSources: ['news'],
          failedSources: [],
          skippedSources: ['detailed_fundamentals'],
          enrichmentReasons: { news: ['optional_news_timeout'] },
          enrichmentUpdatedAt: '2026-05-06T01:01:00Z',
          enrichmentAsOf: '2026-05-06T01:00:00Z',
        },
        standardReport: {
          summaryPanel: {
            stock: 'Oracle',
            ticker: 'ORCL',
            oneSentence: 'Cloud backlog keeps the medium-term floor intact.',
          },
          decisionContext: {
            shortTermView: 'Post-earnings strength still holds the upper rail',
          },
          decisionPanel: {
            idealEntry: '121.80 - 124.60',
            target: '133.50',
            stopLoss: '117.40',
            buildStrategy: 'Start light, then add only after the pullback stays orderly.',
          },
          reasonLayer: {
            coreReasons: ['Institutional sponsorship remains intact after earnings.'],
          },
          technicalFields: [
            { label: 'MACD', value: 'Second expansion above zero' },
            { label: 'Moving Averages', value: 'MA20 lifting MA60' },
          ],
          fundamentalFields: [
            { label: 'Revenue Growth', value: '+9.4%' },
            { label: 'Free Cash Flow', value: '$12.1B' },
          ],
        },
      },
      dataQualityReport: {
        dataQualityTier: 'analysis_grade',
        dataQualityScore: 68,
        requiredAvailable: true,
        importantMissing: ['fundamentals.eps'],
        optionalMissing: ['optional_enrichment_pending'],
        staleSources: [],
        providerTimeouts: ['gnews:news'],
        providerCooldowns: ['fmp:fundamentals'],
        confidenceCap: 70,
        reasonCodes: ['important_data_missing', 'optional_enrichment_missing'],
        freshness: { marketSessionDate: '2026-05-05' },
        enrichmentStatus: 'pending',
        enrichmentSources: ['news', 'sentiment', 'detailed_fundamentals'],
        completedSources: ['sentiment'],
        pendingSources: ['news'],
        failedSources: [],
        skippedSources: ['detailed_fundamentals'],
        enrichmentReasons: { news: ['optional_news_timeout'] },
        enrichmentUpdatedAt: '2026-05-06T01:01:00Z',
        enrichmentAsOf: '2026-05-06T01:00:00Z',
      },
      evidenceCoverageFrame: {
        technicals: {
          status: 'available',
          missingReasons: [],
          nextEvidenceNeeded: [],
        },
        fundamentals: {
          status: 'degraded',
          missingReasons: ['partial_coverage', 'provider_timeout'],
          nextEvidenceNeeded: ['补充基本面证据'],
        },
        news: {
          status: 'missing',
          missingReasons: ['evidence_missing'],
          nextEvidenceNeeded: ['补充新闻证据'],
        },
        catalysts: {
          status: 'blocked',
          missingReasons: ['provider_timeout'],
          nextEvidenceNeeded: ['补充催化证据'],
        },
        earnings: {
          status: 'pending',
          missingReasons: ['evidence_pending'],
          nextEvidenceNeeded: ['补充财报证据'],
        },
        valuation: {
          status: 'not_applicable',
          missingReasons: [],
          nextEvidenceNeeded: [],
        },
      },
      decisionTrace: {
        engineVersion: 'analysis_decision_trace_v1',
        mode: 'rule_scoring_with_llm_explanation',
        endpoint: '/api/v1/analysis/analyze',
        taskId: 'q3',
        symbol: 'ORCL',
        market: 'US',
        decisionFields: {
          action: { value: 'hold', source: 'rule', confidence: 0.78, notes: 'stabilized score path' },
          score: { value: 78, source: 'rule', scale: '0-100' },
          confidence: { value: '高', source: 'llm' },
          entry: { value: '121.80 - 124.60', source: 'llm' },
          target: { value: '133.50', source: 'llm' },
          stop: { value: '117.40', source: 'llm' },
        },
        dataSources: [
          { name: 'quote', status: 'used', provider: 'Yahoo Finance' },
          { name: 'fundamental', status: 'fallback', provider: 'FMP' },
          { name: 'news', status: 'missing', provider: null },
        ],
        signals: [
          { name: 'MA alignment', value: 'bullish', impact: 'positive', source: 'technical_rule' },
        ],
        llm: {
          used: true,
          provider: 'openai',
          model: 'openai/gpt-4.1-mini',
          template: 'decision_dashboard_v2',
          structuredOutput: true,
          schemaValidated: true,
          promptExposed: false,
        },
        conflicts: [
          {
            type: 'action_plan_mismatch',
            severity: 'warning',
            message: 'Action says sell but plan includes entry/accumulation.',
          },
        ],
        limitations: ['fundamental data partial'],
      },
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

async function expectSafeEvidenceCoverageStrip(page: Page) {
  const strip = page.getByTestId('home-evidence-coverage-strip');
  await appExpect(strip).toBeVisible({ timeout: 15_000 });
  await appExpect(strip).toContainText('证据覆盖');
  await appExpect(strip).toContainText('技术面 可用');
  await appExpect(strip).toContainText('基本面 降级');
  await appExpect(strip).toContainText('新闻 缺失');
  await appExpect(strip).toContainText('催化 阻断');
  await appExpect(strip).toContainText('财报 待补');
  await appExpect(strip).toContainText('补充基本面证据');
  await appExpect(strip).toContainText('补充新闻证据');
  await appExpect(strip).toContainText('补充催化证据');
  await appExpect(strip).toContainText('补充财报证据');
  await appExpect(strip).not.toContainText(internalEvidenceCoveragePattern);
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
      await expectSafeEvidenceCoverageStrip(page);
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
