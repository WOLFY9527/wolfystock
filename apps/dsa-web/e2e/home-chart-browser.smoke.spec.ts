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

const homeChartLeakPattern =
  /raw|debug|provider|schema|payload|trace|internal|cache|router|env|credential|sourceauthority|source_authority/i;
const tradingPattern = /buy|sell|order|trade|broker|买入|卖出|下单|交易|券商/i;

const homeHistoryData = [
  { date: '2026-05-27', open: 120.0, high: 121.2, low: 119.4, close: 120.8, volume: 8100000, change_percent: 0.7 },
  { date: '2026-05-28', open: 120.9, high: 122.4, low: 120.1, close: 121.7, volume: 7900000, change_percent: 0.74 },
  { date: '2026-05-29', open: 121.8, high: 123.1, low: 121.0, close: 122.2, volume: 8400000, change_percent: 0.41 },
  { date: '2026-05-30', open: 122.0, high: 123.6, low: 121.4, close: 123.1, volume: 8600000, change_percent: 0.74 },
  { date: '2026-06-02', open: 123.2, high: 124.1, low: 122.7, close: 123.8, volume: 8050000, change_percent: 0.57 },
];

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
      data: homeHistoryData,
    });
  });

  await page.route('**/api/v1/history/3', async (route) => {
    await fulfillJson(route, {
      meta: {
        id: 3,
        queryId: 'q3',
        stockCode: 'ORCL',
        stockName: 'Oracle',
        companyName: 'Oracle Corporation',
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
        operationAdvice: '数据不足，结论仅供观察。',
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
            buildStrategy: 'Use mocked data only to review the chart surface.',
          },
        },
        analysisResult: {
          singleStockEvidencePacket: {
            packetState: 'observe_only',
            priceHistory: { status: 'available' },
            technicals: { status: 'available' },
            fundamentals: { status: 'degraded' },
            earnings: { status: 'pending' },
            news: { status: 'missing' },
            catalysts: { status: 'blocked' },
            valuation: { status: 'waiting' },
            fundamentalsEarnings: {
              normalizerState: 'insufficient',
              missingEvidence: ['roe', 'pb'],
              blockingReasons: ['partial_coverage'],
              evidenceLabels: [],
            },
            newsCatalysts: {
              topNewsItems: [{ headline: 'Oracle cloud backlog remains stable.' }],
              topCatalystItems: [],
              blockingReasons: ['provider_timeout'],
            },
          },
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
        technicals: { status: 'available', missingReasons: [], nextEvidenceNeeded: [] },
        fundamentals: {
          status: 'degraded',
          missingReasons: ['partial_coverage'],
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
        valuation: { status: 'not_applicable', missingReasons: [], nextEvidenceNeeded: [] },
      },
    });
  });
}

async function openSignedInHome(page: Page) {
  await page.goto('/zh');
  await page.waitForLoadState('domcontentloaded');
  await expect(page.getByTestId('home-bento-dashboard')).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText('Oracle Corporation')).toBeVisible({ timeout: 15_000 });
}

async function expectNoHorizontalOverflow(page: Page) {
  await baseExpect
    .poll(async () => page.evaluate(() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)))
    .toBeLessThanOrEqual(1);
}

async function expectMinimumHitArea(page: Page, testIds: string[], minimumHeight: number) {
  for (const testId of testIds) {
    await baseExpect
      .poll(async () => page.getByTestId(testId).evaluate((node) => Math.round(node.getBoundingClientRect().height)))
      .toBeGreaterThanOrEqual(minimumHeight);
  }
}

test.describe('Home chart browser smoke', () => {
  test('renders the Home technical chart on desktop without blank state or unsafe copy', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await installSignedInHomeRoutes(page);

    await openSignedInHome(page);

    const chartSection = page.getByTestId('home-research-chart-section');
    const chartWorkspace = page.getByTestId('home-research-chart-workspace');
    const chartRoot = page.getByTestId('home-linear-technical-chart');
    const chartFrame = page.getByTestId('home-candlestick-chart-frame');

    await expect(chartSection).toBeVisible();
    await expect(chartWorkspace).toBeVisible();
    await expect(chartRoot).toBeVisible();
    await expect(chartFrame).toBeVisible();
    await expect(page.getByTestId('home-candlestick-echarts-node')).toBeVisible();
    await expect(chartRoot).toHaveAttribute('data-chart-engine', 'echarts');
    await expect(chartRoot).toHaveAttribute('data-chart-timeframe', '1D');
    await expect(chartRoot.getByTestId('home-chart-context-price')).toContainText('价格');
    await expect(chartRoot.getByTestId('home-chart-context-volume')).toContainText('成交量');
    await expect(chartRoot.getByTestId('home-chart-range-hint')).toContainText('缩放');
    await expect(page.getByTestId('home-candlestick-chart-fallback')).toHaveCount(0);
    await expect(page.getByTestId('home-candlestick-unavailable')).toHaveCount(0);

    const regionText = await chartSection.innerText();
    expect(regionText).not.toMatch(homeChartLeakPattern);
    expect(regionText).not.toMatch(tradingPattern);
    await expectNoHorizontalOverflow(page);
    expect(consoleErrors).toEqual([]);
    expect(unhandledApiRoutes).toEqual([]);
  });

  test('keeps the Home technical chart visible at 390px without horizontal overflow', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await installSignedInHomeRoutes(page);

    await openSignedInHome(page);

    const chartSection = page.getByTestId('home-research-chart-section');
    const chartRoot = page.getByTestId('home-linear-technical-chart');
    const chartFrame = page.getByTestId('home-candlestick-chart-frame');

    await expect(chartSection).toBeVisible();
    await expect(chartRoot).toBeVisible();
    await expect(chartFrame).toBeVisible();
    await expect(page.getByTestId('home-candlestick-echarts-node')).toBeVisible();
    await expect(chartRoot.getByTestId('home-chart-timeframe-controls')).toBeVisible();
    await expect(chartRoot.getByTestId('home-chart-indicator-controls')).toBeVisible();
    await expect(chartRoot.getByTestId('home-chart-context-price')).toContainText('价格');
    await expect(chartRoot.getByTestId('home-chart-context-volume')).toContainText('成交量');
    await expect(chartRoot.getByTestId('home-chart-range-hint')).toContainText('缩放');
    await expect(page.getByTestId('home-candlestick-chart-fallback')).toHaveCount(0);
    await expect(page.getByTestId('home-candlestick-unavailable')).toHaveCount(0);
    await expectMinimumHitArea(page, ['home-chart-timeframe-1D', 'home-chart-timeframe-1W', 'home-chart-timeframe-1M'], 40);
    await expectMinimumHitArea(page, ['home-chart-indicator-ma20', 'home-chart-indicator-ma60', 'home-chart-indicator-vwap'], 40);

    const regionText = await chartSection.innerText();
    expect(regionText).not.toMatch(homeChartLeakPattern);
    expect(regionText).not.toMatch(tradingPattern);
    await expectNoHorizontalOverflow(page);
    expect(consoleErrors).toEqual([]);
    expect(unhandledApiRoutes).toEqual([]);
  });
});
