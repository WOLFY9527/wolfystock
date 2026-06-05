import { expect, type Page, type Route } from '@playwright/test';
import { expect as appExpect, test } from './fixtures/appSmoke';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
] as const;

const rawLeakPattern =
  /raw|debug|provider|schema|payload|trace|internal|cache|router|env|credential|sourceauthority|source_authority/i;
const tradingPattern = /buy|sell|order|trade|broker|买入|卖出|下单|交易|券商/i;

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

async function installSignedInAuthRoutes(page: Page) {
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
}

async function installHomeEvidenceOverrides(page: Page) {
  await installSignedInAuthRoutes(page);
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
      data: [
        { date: '2026-05-27', open: 120.0, high: 121.2, low: 119.4, close: 120.8, volume: 8100000, change_percent: 0.7 },
        { date: '2026-05-28', open: 120.9, high: 122.4, low: 120.1, close: 121.7, volume: 7900000, change_percent: 0.74 },
        { date: '2026-05-29', open: 121.8, high: 123.1, low: 121.0, close: 122.2, volume: 8400000, change_percent: 0.41 },
        { date: '2026-05-30', open: 122.0, high: 123.6, low: 121.4, close: 123.1, volume: 8600000, change_percent: 0.74 },
        { date: '2026-06-02', open: 123.2, high: 124.1, low: 122.7, close: 123.8, volume: 8050000, change_percent: 0.57 },
      ],
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
        valuation: { status: 'not_applicable', missingReasons: [], nextEvidenceNeeded: [] },
      },
      sourceProvenanceFrame: [
        {
          contractVersion: 'source_provenance_v1',
          sourceId: 'polygon_us_grouped_daily',
          sourceLabel: 'Polygon Grouped Daily',
          evidenceDomain: 'market_data',
          authorityTier: 'score_grade',
          freshnessState: 'fresh',
          sourceTier: 'authorized_feed',
          fallbackOrProxy: false,
          observationOnly: false,
          scoreContributionAllowed: true,
          limitations: [],
          nextEvidenceNeeded: [],
          debugRef: 'analysis:orcl-price',
        },
        {
          contractVersion: 'source_provenance_v1',
          sourceId: 'fmp',
          sourceLabel: 'FMP',
          evidenceDomain: 'fundamentals',
          authorityTier: 'score_grade',
          freshnessState: 'cached',
          sourceTier: 'official_public',
          fallbackOrProxy: false,
          observationOnly: false,
          scoreContributionAllowed: true,
          limitations: [],
          nextEvidenceNeeded: [],
          debugRef: 'analysis:orcl-fundamentals',
        },
        {
          contractVersion: 'source_provenance_v1',
          sourceId: 'fallback_snapshot',
          sourceLabel: 'Fallback snapshot',
          evidenceDomain: 'news',
          authorityTier: 'observation_only',
          freshnessState: 'fallback',
          sourceTier: 'fallback',
          fallbackOrProxy: true,
          observationOnly: true,
          scoreContributionAllowed: false,
          limitations: ['fallback_or_proxy_source', 'observation_only'],
          nextEvidenceNeeded: ['authorized_primary_source'],
          debugRef: 'analysis:orcl-news',
        },
        {
          contractVersion: 'source_provenance_v1',
          sourceId: 'unknown_source',
          sourceLabel: '未知来源',
          evidenceDomain: 'research',
          authorityTier: 'unknown',
          freshnessState: 'unknown',
          sourceTier: 'unknown',
          fallbackOrProxy: true,
          observationOnly: true,
          scoreContributionAllowed: false,
          limitations: ['unknown_source'],
          nextEvidenceNeeded: ['verified_source_metadata'],
          debugRef: 'analysis:orcl-research',
        },
      ],
    });
  });
}

async function installScannerEvidenceOverrides(page: Page) {
  await installSignedInAuthRoutes(page);
  const runSummary = {
    id: 11,
    market: 'cn',
    profile: 'cn_preopen_v1',
    profile_label: 'A-share Pre-open v1',
    status: 'completed',
    run_at: '2026-06-02T09:00:00Z',
    completed_at: '2026-06-02T09:00:10Z',
    watchlist_date: '2026-06-02',
    trigger_mode: 'manual',
    universe_name: 'cn_a_liquid_watchlist_v1',
    shortlist_size: 18,
    universe_size: 320,
    preselected_size: 72,
    evaluated_size: 48,
    source_summary: 'Mocked scanner payload',
    headline: 'Mock scanner shortlist for scanner evidence smoke',
    universe_type: 'theme',
    theme_id: 'ai_semiconductors',
    theme_label: 'AI 半导体',
    requested_symbols_count: 0,
    accepted_symbols_count: 0,
    rejected_symbols: [],
    top_symbols: ['NVDA'],
    notification_status: 'not_attempted',
    failure_reason: null,
  };

  await page.route('**/api/v1/scanner/runs**', async (route) => {
    await fulfillJson(route, {
      total: 1,
      page: 1,
      limit: 10,
      items: [runSummary],
    });
  });

  await page.route('**/api/v1/scanner/watchlists/recent**', async (route) => {
    await fulfillJson(route, {
      total: 1,
      page: 1,
      limit: 10,
      items: [runSummary],
    });
  });

  await page.route('**/api/v1/scanner/runs/11', async (route) => {
    await fulfillJson(route, {
      id: 11,
      market: 'cn',
      profile: 'cn_preopen_v1',
      profile_label: 'A-share Pre-open v1',
      status: 'completed',
      run_at: '2026-06-02T09:00:00Z',
      completed_at: '2026-06-02T09:00:10Z',
      watchlist_date: '2026-06-02',
      trigger_mode: 'manual',
      universe_name: 'cn_a_liquid_watchlist_v1',
      shortlist_size: 1,
      universe_size: 320,
      preselected_size: 72,
      evaluated_size: 48,
      source_summary: 'Mocked scanner payload',
      headline: 'Mock scanner shortlist for scanner evidence smoke',
      universe_type: 'theme',
      theme_id: 'ai_semiconductors',
      theme_label: 'AI 半导体',
      requested_symbols_count: 0,
      accepted_symbols_count: 0,
      rejected_symbols: [],
      shortlist: [
        {
          symbol: 'NVDA',
          name: 'NVIDIA',
          company_name: 'NVIDIA Corp',
          rank: 1,
          score: 98,
          quality_hint: 'Liquid and trend-aligned',
          reason_summary: 'NVDA keeps relative strength and breadth support.',
          reasons: ['NVDA is holding above the recent breakout range.'],
          key_metrics: [
            { label: 'Entry range', value: '100-102' },
            { label: 'Target price', value: '112' },
            { label: 'Stop loss', value: '96' },
          ],
          feature_signals: [
            { label: 'Theme', value: 'AI infrastructure' },
            { label: 'Momentum', value: 'Improving' },
          ],
          risk_notes: ['Crowded trade if volume stalls.'],
          watch_context: [{ label: 'Plan', value: 'Wait for first controlled pullback.' }],
          boards: ['semis'],
          tags: [{ name: 'High conviction', description: 'Top-ranked mock setup.', tone: 'indigo' }],
          appeared_in_recent_runs: 2,
          last_trade_date: '2026-06-01',
          scan_timestamp: '2026-06-02T09:00:00Z',
          ai_interpretation: {
            available: false,
            status: 'not_configured',
            summary: null,
            opportunity_type: null,
            risk_interpretation: null,
            watch_plan: null,
            review_commentary: null,
            provider: null,
            model: null,
            generated_at: null,
            message: null,
          },
          realized_outcome: {
            review_status: 'pending',
            outcome_label: 'pending',
            thesis_match: 'pending',
            review_window_days: 3,
            anchor_date: '2026-06-01',
            window_end_date: '2026-06-04',
            same_day_close_return_pct: null,
            next_day_return_pct: null,
            review_window_return_pct: null,
            max_favorable_move_pct: null,
            max_adverse_move_pct: null,
            benchmark_code: null,
            benchmark_return_pct: null,
            outperformed_benchmark: null,
          },
          diagnostics: {},
          candidateEvidenceFrame: {
            contractVersion: 'scanner_candidate_evidence_v1',
            coverageState: 'observe_only',
            domains: {
              technicals: { state: 'available', observationOnly: false },
              priceHistory: { state: 'available', observationOnly: false },
              liquidity: { state: 'partial', observationOnly: true },
              theme: { state: 'available', observationOnly: true },
              fundamentals: { state: 'missing', observationOnly: true },
              newsCatalyst: { state: 'missing', observationOnly: true },
            },
            coverage: {
              availableCount: 2,
              partialCount: 1,
              observeOnlyCount: 4,
              missingCount: 2,
              totalCount: 6,
            },
            noAdviceBoundary: true,
          },
          candidateResearchReadiness: {
            contractVersion: 'research_readiness_v1',
            researchReady: false,
            readinessState: 'observe_only',
            verdictLabel: '仅观察',
            blockingReasons: [],
            missingEvidence: ['fundamentals', 'newsCatalyst'],
            consumerActionBoundary: 'no_advice',
            noAdviceBoundary: true,
          },
          candidateSourceProvenanceFrame: {
            contractVersion: 'source_provenance_v1',
            entryCount: 4,
            authorityTierCounts: {
              observation_only: 2,
              score_grade: 1,
              unknown: 1,
            },
            freshnessStateCounts: {
              cached: 1,
              fallback: 1,
              fresh: 1,
              unknown: 1,
            },
            evidenceDomainCounts: {
              fundamentals: 1,
              market_data: 1,
              news: 1,
              research: 1,
            },
            fallbackOrProxyCount: 2,
            observationOnlyCount: 3,
            scoreContributionAllowedCount: 1,
            entries: [
              {
                contractVersion: 'source_provenance_v1',
                sourceId: 'polygon_us_grouped_daily',
                sourceLabel: 'Polygon Grouped Daily',
                evidenceDomain: 'market_data',
                authorityTier: 'score_grade',
                freshnessState: 'fresh',
                sourceTier: 'authorized_feed',
                fallbackOrProxy: false,
                observationOnly: false,
                scoreContributionAllowed: true,
                limitations: [],
                nextEvidenceNeeded: [],
                debugRef: 'scanner:nvda-price',
              },
              {
                contractVersion: 'source_provenance_v1',
                sourceId: 'fallback_snapshot',
                sourceLabel: 'Fallback snapshot',
                evidenceDomain: 'news',
                authorityTier: 'observation_only',
                freshnessState: 'fallback',
                sourceTier: 'fallback',
                fallbackOrProxy: true,
                observationOnly: true,
                scoreContributionAllowed: false,
                limitations: ['fallback_or_proxy_source', 'observation_only'],
                nextEvidenceNeeded: ['authorized_primary_source'],
                debugRef: 'scanner:nvda-news',
              },
              {
                contractVersion: 'source_provenance_v1',
                sourceId: 'fmp',
                sourceLabel: 'FMP',
                evidenceDomain: 'fundamentals',
                authorityTier: 'observation_only',
                freshnessState: 'cached',
                sourceTier: 'official_public',
                fallbackOrProxy: false,
                observationOnly: true,
                scoreContributionAllowed: false,
                limitations: ['observation_only'],
                nextEvidenceNeeded: ['score_grade_authority_source'],
                debugRef: 'scanner:nvda-fundamentals',
              },
              {
                contractVersion: 'source_provenance_v1',
                sourceId: 'unknown_source',
                sourceLabel: '未知来源',
                evidenceDomain: 'research',
                authorityTier: 'unknown',
                freshnessState: 'unknown',
                sourceTier: 'unknown',
                fallbackOrProxy: true,
                observationOnly: true,
                scoreContributionAllowed: false,
                limitations: ['unknown_source'],
                nextEvidenceNeeded: ['verified_source_metadata'],
                debugRef: 'scanner:nvda-research',
              },
            ],
          },
        },
      ],
      summary: {
        selected_count: 18,
        rejected_count: 5,
        data_failed_count: 1,
        error_count: 0,
      },
      scanner_context_frame: {
        market_readiness: {
          contract_version: 'research_readiness_v1',
          research_ready: false,
          readiness_state: 'observe_only',
          verdict_label: '仅观察',
          blocking_reasons: [],
          missing_evidence: [],
          evidence_coverage: {
            score_grade_count: 2,
            observation_only_count: 1,
            missing_count: 0,
            total_count: 3,
          },
          source_authority: 'observationOnly',
          freshness_floor: 'cached',
          consumer_action_boundary: 'no_advice',
          next_evidence_needed: ['继续结合市场与主题框架观察'],
        },
        macro_regime: {
          state: 'supportive',
          label: 'Supportive macro regime',
          freshness: 'cached',
          blockers: [],
          observation_only: false,
          source_authority_allowed: true,
          score_contribution_allowed: true,
        },
        liquidity_frame: {
          state: 'supportive',
          label: 'Liquidity supports equity leadership',
          freshness: 'cached',
          blockers: [],
          observation_only: false,
          source_authority_allowed: true,
          score_contribution_allowed: true,
          proxy_only: false,
        },
        asset_class_bias: {
          state: 'supportive',
          label: 'Equities preferred',
          blockers: [],
          observation_only: false,
        },
        theme_frame: {
          state: 'observe_only',
          label: 'AI leadership is still observation-only',
          freshness: 'cached',
          blockers: [],
          observation_only: true,
          proxy_only: true,
          themes: [
            { id: 'ai', label: 'AI', observation_only: true, proxy_only: true },
          ],
        },
        universe_policy: {
          type: 'theme',
          label: 'Theme universe',
          blockers: [],
        },
        no_advice_boundary: true,
      },
    });
  });
}

async function expectNoHorizontalOverflow(page: Page) {
  await expect
    .poll(async () => page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth))
    .toBe(true);
}

async function openSignedInRoute(page: Page, path: string) {
  await page.goto(path);
  await page.waitForLoadState('domcontentloaded');
}

test.describe('Home and Scanner evidence browser smoke', () => {
  test('Home shows evidence packet strip without raw leakage or trading wording', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await installHomeEvidenceOverrides(page);
      await openSignedInRoute(page, '/zh');
      await appExpect(page.getByTestId('home-bento-dashboard')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('home-evidence-packet-strip')).toBeVisible({ timeout: 15_000 });
      const strip = page.getByTestId('home-evidence-packet-strip');
      await appExpect(strip).toContainText('证据包摘要');
      await appExpect(strip).toContainText('整体状态');
      await appExpect(strip).toContainText('仅观察');
      await appExpect(strip).toContainText('价格历史 可用');
      await appExpect(strip).toContainText('技术面 可用');
      await appExpect(strip).toContainText('基本面 降级');
      await appExpect(strip).toContainText('财报 待补');
      await appExpect(strip).toContainText('新闻 缺失');
      await appExpect(strip).toContainText('催化 阻断');
      await appExpect(strip).toContainText('估值 等待');
      await appExpect(strip).toContainText('基本面/财报：数据不足');
      await appExpect(strip).toContainText(/新闻\/催化：1\s*条新闻，催化待补/);
      await appExpect(strip).toContainText('数据不足，结论仅供观察');
      await appExpect(strip).toContainText('仅供观察，不构成投资建议');
      await appExpect(strip).not.toContainText(rawLeakPattern);
      await appExpect(strip).not.toContainText(tradingPattern);
      const provenance = page.getByTestId('home-provenance-strip');
      await appExpect(provenance).toBeVisible({ timeout: 15_000 });
      await appExpect(provenance).toContainText('来源依据');
      await appExpect(provenance).toContainText('来源确认：含评分级');
      await appExpect(provenance).toContainText('回退/代理 2 项');
      await appExpect(provenance).toContainText('待核验 1 项');
      await appExpect(provenance).not.toContainText(rawLeakPattern);
      await appExpect(provenance).not.toContainText(tradingPattern);
      await expectNoHorizontalOverflow(page);
      expect(consoleErrors).toEqual([]);
      expect(unhandledApiRoutes).toEqual([]);
      await page.unroute('**/api/v1/auth/status**');
      await page.unroute('**/api/v1/auth/me**');
      await page.unroute('**/api/v1/stocks/*/evidence**');
      await page.unroute('**/api/v1/stocks/ORCL/history**');
      await page.unroute('**/api/v1/history/3');
    }
  });

  test('Scanner shows candidate evidence coverage without raw leakage or trading wording', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await installScannerEvidenceOverrides(page);
      await openSignedInRoute(page, '/zh/scanner');
      await appExpect(page.getByTestId('user-scanner-workspace')).toBeVisible({ timeout: 15_000 });
      await appExpect(page.getByTestId('scanner-result-row-NVDA')).toBeVisible({ timeout: 15_000 });
      const strip = page.getByTestId('scanner-inline-candidate-evidence-NVDA');
      await appExpect(strip).toBeVisible({ timeout: 15_000 });
      await appExpect(strip).toContainText('仅观察');
      await appExpect(strip).toContainText('待补 基本面 / 新闻催化');
      await appExpect(strip).toContainText('技术面');
      await appExpect(strip).toContainText('可用');
      await appExpect(strip).toContainText('价格历史');
      await appExpect(strip).toContainText('流动性');
      await appExpect(strip).toContainText('主题');
      await appExpect(strip).toContainText('基本面');
      await appExpect(strip).toContainText('新闻催化');
      await appExpect(strip).toContainText('来源确认：含评分级');
      await appExpect(strip).toContainText('观察级 3 项');
      await appExpect(strip).toContainText('来源依据');
      await appExpect(strip).not.toContainText(rawLeakPattern);
      await appExpect(strip).not.toContainText(tradingPattern);
      await expectNoHorizontalOverflow(page);
      expect(consoleErrors).toEqual([]);
      expect(unhandledApiRoutes).toEqual([]);
      await page.unroute('**/api/v1/auth/status**');
      await page.unroute('**/api/v1/auth/me**');
      await page.unroute('**/api/v1/scanner/runs**');
      await page.unroute('**/api/v1/scanner/watchlists/recent**');
      await page.unroute('**/api/v1/scanner/runs/11');
    }
  });
});
