import { expect, type Page } from '@playwright/test';
import { expect as appExpect, test } from './fixtures/appSmoke';
import {
  expectNoHorizontalOverflow,
  fulfillJson,
  installSignedInSessionRoutes,
  openSignedInRoute,
} from './fixtures/authenticatedRouteSmoke';
import {
  buildHomeEvidencePacketShell,
  buildHomeHistoryPayload,
  buildHomeReportMeta,
  buildHomeSingleStockEvidencePacketBase,
  buildHomeSourceProvenanceFrame,
  buildHomeStrategyBase,
  buildScannerCandidateEvidenceFrame,
  buildScannerCandidateResearchReadiness,
  buildScannerCandidateSourceProvenanceFrame,
  buildScannerContextFrameBase,
  buildScannerNvdaCandidateBase,
  buildScannerRunSummaryBase,
  expectSurfaceTextSafe,
} from './fixtures/smokeEvidence';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
] as const;

const rawLeakPattern =
  /raw|debug|provider|schema|payload|trace|internal|cache|router|env|credential|sourceauthority|source_authority/i;
const tradingPattern = /buy|sell|order|trade|broker|买入|卖出|下单|交易|券商/i;

async function installHomeEvidenceOverrides(page: Page) {
  await installSignedInSessionRoutes(page);
  await page.route('**/api/v1/stocks/*/evidence**', async (route) => {
    await fulfillJson(route, buildHomeEvidencePacketShell());
  });

  await page.route('**/api/v1/stocks/ORCL/history**', async (route) => {
    await fulfillJson(route, buildHomeHistoryPayload());
  });

  await page.route('**/api/v1/history/3', async (route) => {
    await fulfillJson(route, {
      meta: buildHomeReportMeta(),
      summary: {
        analysisSummary: 'Oracle is holding its post-earnings platform.',
        operationAdvice: 'Wait for a controlled pullback before adding.',
        trendPrediction: 'Constructive for the next 72 hours.',
        sentimentScore: 78,
        sentimentLabel: 'Bullish',
      },
      strategy: buildHomeStrategyBase(),
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
          singleStockEvidencePacket: buildHomeSingleStockEvidencePacketBase(),
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
      sourceProvenanceFrame: buildHomeSourceProvenanceFrame(),
    });
  });
}

async function installScannerEvidenceOverrides(page: Page) {
  await installSignedInSessionRoutes(page);
  const runSummary = {
    ...buildScannerRunSummaryBase(),
    shortlist_size: 18,
    headline: 'Mock scanner shortlist for scanner evidence smoke',
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
      ...buildScannerRunSummaryBase(),
      shortlist_size: 1,
      headline: 'Mock scanner shortlist for scanner evidence smoke',
      shortlist: [
        {
          ...buildScannerNvdaCandidateBase(),
          diagnostics: {},
          candidateEvidenceFrame: buildScannerCandidateEvidenceFrame(),
          candidateResearchReadiness: buildScannerCandidateResearchReadiness(),
          candidateSourceProvenanceFrame: buildScannerCandidateSourceProvenanceFrame(),
        },
      ],
      summary: {
        selected_count: 18,
        rejected_count: 5,
        data_failed_count: 1,
        error_count: 0,
      },
      scanner_context_frame: buildScannerContextFrameBase(),
    });
  });
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
      await expectSurfaceTextSafe(strip, {
        forbiddenPatterns: [rawLeakPattern, tradingPattern],
      });
      const provenance = page.getByTestId('home-provenance-strip');
      await appExpect(provenance).toBeVisible({ timeout: 15_000 });
      await appExpect(provenance).toContainText('来源依据');
      await appExpect(provenance).toContainText('来源确认：含评分级');
      await appExpect(provenance).toContainText('回退/代理 2 项');
      await appExpect(provenance).toContainText('待核验 1 项');
      await expectSurfaceTextSafe(provenance, {
        forbiddenPatterns: [rawLeakPattern, tradingPattern],
      });
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
      const workflow = page.getByTestId('scanner-workflow-summary');
      await appExpect(workflow).toBeVisible({ timeout: 15_000 });
      await appExpect(workflow).toContainText('先看市场驱动');
      await appExpect(workflow).toContainText('当前候选 NVDA');
      await appExpect(workflow).toContainText('来源确认：含评分级');
      await appExpect(workflow).toContainText('查看排名主表');
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
      await expectSurfaceTextSafe(strip, {
        forbiddenPatterns: [rawLeakPattern, tradingPattern],
      });
      const workflowBox = await workflow.boundingBox();
      const rankedListBox = await page.getByTestId('scanner-ranked-list').boundingBox();
      expect(workflowBox?.y ?? Number.POSITIVE_INFINITY).toBeLessThan(rankedListBox?.y ?? Number.NEGATIVE_INFINITY);
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
