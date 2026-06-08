import { expect as baseExpect } from '@playwright/test';
import { expect as appExpect, test as appTest } from './fixtures/appSmoke';
import { expectNoHorizontalOverflow, fulfillJson, installSignedInSessionRoutes, openSignedInRoute } from './fixtures/authenticatedRouteSmoke';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
] as const;

const forbiddenRotationInternalPattern =
  /provider|runtime|cache|debug|trace|raw_payload|provider_payload|schema|reasonCodes?|sourceAuthorityAllowed|scoreContributionAllowed|decision[-\s]?grade|决策级/i;

function observationModeRotationPayload() {
  const timestamp = '2026-05-07T09:50:00Z';
  const observationTheme = {
    id: 'observation_ai',
    name: 'AI 观察主题',
    englishName: 'AI Observation Theme',
    focus: '对比样本强弱与广度扩散',
    benchmark: 'QQQ',
    sectorBenchmark: 'IGV',
    membersConfigured: ['APP', 'PLTR', 'CRM'],
    rotationScore: 12,
    confidence: 0.14,
    signalType: 'insufficient_evidence',
    flowEvidenceType: 'none',
    flowLanguageAllowed: false,
    sourceAuthorityAllowed: false,
    evidenceQuality: 'insufficient',
    dataGaps: ['source_authority_rejected'],
    rankingLane: 'observation',
    observationOnly: true,
    headlineEligible: false,
    scoreContributionAllowed: false,
    stage: 'weak_or_no_signal',
    stageExplanation: 'sourceAuthorityAllowed reasonCodes provider debug raw_payload',
    riskLabels: [],
    riskExplanations: [],
    newslessRotation: false,
    relativeStrength: {},
    volume: { averageRelativeVolume: null, availableMemberCount: 0, label: '待确认' },
    breadth: {
      observedMembers: 0,
      configuredMembers: 3,
      coveragePercent: 0,
      percentUp: null,
      percentOutperformingBenchmark: null,
    },
    synchronization: { sameDirectionPercent: null, aboveVwapPercent: null, persistencePercent: null, label: '待确认' },
    leadership: { leadershipConcentrationPercent: null, broadParticipationPercent: null, topMembers: [] },
    themeDetail: {
      representativeLabels: ['APP', 'PLTR', 'CRM'],
      disclosure: '仅用于观察资金轮动迹象，非买卖建议。',
    },
    freshness: 'delayed',
    isFallback: false,
    isStale: false,
    evidence: ['provider runtime trace'],
    members: [],
    noAdviceDisclosure: '仅用于观察资金轮动迹象，非买卖建议。',
  };
  const observationSummary = {
    ...observationTheme,
    rotationScore: 68,
    confidence: 0.64,
    signalType: 'relative_strength',
    flowEvidenceType: 'proxy_only',
    evidenceQuality: 'degraded_proxy',
    stage: 'early_watch',
    stageExplanation: 'AI 观察主题由对比样本强弱与广度扩散支持，仅作走势观察。',
    relativeStrength: {
      benchmark: 'QQQ',
      benchmarkChangePercent: 0.2,
      averageThemeChangePercent: 2.6,
      averageRelativeStrengthPercent: 2.4,
      vsBenchmarks: { QQQ: 2.4 },
    },
    volume: { averageRelativeVolume: 1.42, availableMemberCount: 3, label: '成交额扩张' },
    breadth: {
      observedMembers: 3,
      configuredMembers: 3,
      coveragePercent: 100,
      percentUp: 72,
      percentOutperformingBenchmark: 68,
    },
    synchronization: { sameDirectionPercent: 70, aboveVwapPercent: 66, persistencePercent: 62, label: '同步改善' },
    leadership: {
      leadershipConcentrationPercent: 34,
      broadParticipationPercent: 66,
      topMembers: [
        { symbol: 'APP', name: 'APP', changePercent: 3.1, relativeStrengthVsBenchmark: 2.7, volumeRatio: 1.8, freshness: 'delayed', isFallback: false },
      ],
    },
    themeFlowSignal: {
      themeFlowState: 'leading',
      confidence: 0.64,
      confidenceLabel: '中',
      reasonCodes: ['partial_source'],
      explanation: 'AI 观察主题由相对强弱与广度扩散支持，仅作走势观察。',
      leadershipEvidence: '龙头成员 APP，集中度 34.0%。',
      breadthEvidence: '上涨广度 72.0% / 跑赢广度 68.0% ，3/3 成员有可用观察。',
      relativeStrengthEvidence: '相对 QQQ 强弱 +2.40% 。',
    },
    evidence: ['相对 QQQ 强弱 +2.40%', '上涨广度 72.0%'],
  };

  return {
    endpoint: '/api/v1/market/rotation-radar',
    market: 'US',
    supportedMarkets: ['US', 'CN', 'HK', 'CRYPTO'],
    generatedAt: timestamp,
    source: 'computed',
    sourceLabel: 'provider raw label should stay hidden',
    freshness: 'delayed',
    isFallback: false,
    isStale: false,
    warning: 'provider runtime cache debug trace',
    noAdviceDisclosure: '仅用于观察资金轮动迹象，非买卖建议。',
    benchmarks: {},
    etfLeadershipDiagnostics: {
      enabled: false,
      source: 'alpaca_etf_authority_spine',
      asOf: timestamp,
      eligibleSymbols: ['SPY', 'QQQ'],
      leadingSymbols: [],
      laggingSymbols: [],
      leadershipSpread: null,
      confidenceLabel: 'disabled',
      reasonCodes: ['source_authority_rejected'],
      evidence: [],
    },
    summary: {
      strongestThemes: [],
      acceleratingThemes: [],
      fadingThemes: [],
      observationThemes: [observationSummary],
      taxonomyThemes: [],
      rotationFamilyRollup: [],
      eligibleThemeCount: 0,
      headlineEligibleThemeCount: 0,
      observationThemeCount: 1,
      headlineWarning: 'provider runtime cache debug trace',
      noHeadlineReason: 'sourceAuthorityAllowed scoreContributionAllowed reasonCodes provider',
      rankingPolicy: 'providerState runtime cache internal',
      watchlistSignals: [],
      safeWording: ['资金轮动迹象', '相对强势扩散', '非买卖建议'],
    },
    themes: [observationTheme],
    consumerEvidenceSnapshot: {
      market: 'US',
      generatedAt: timestamp,
      asOf: timestamp,
      freshness: 'partial',
      isFallback: false,
      isStale: false,
      isPartial: true,
      authorityGrant: false,
      headlineEligibleThemeCount: 0,
      observationThemeCount: 1,
      taxonomyThemeCount: 0,
      scoreContributionAllowed: false,
      reasonCodes: ['source_authority_rejected', 'partial_source'],
      rotationFamilyRollup: [],
    },
    metadata: {
      schemaVersion: 'market_rotation_observation_mode_test',
      providerState: 'debug_trace_should_not_render',
    },
  };
}

appTest.describe('rotation observation themes primary view', () => {
  appTest('renders observation-mode matrix/list when headline gates have no eligible themes', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await installSignedInSessionRoutes(page);
      await page.route('**/api/v1/market/rotation-radar**', async (route) => {
        await fulfillJson(route, observationModeRotationPayload());
      });

      await openSignedInRoute(page, '/zh/market/rotation-radar');

      const routeRoot = page.getByTestId('market-rotation-radar-page');
      const visualMatrix = page.getByTestId('rotation-radar-visual-matrix');
      const leaderList = page.getByTestId('rotation-radar-leader-list');
      await appExpect(routeRoot).toBeVisible({ timeout: 15_000 });
      await appExpect(visualMatrix).toBeVisible();
      await appExpect(visualMatrix).toContainText('观察数据');
      await appExpect(visualMatrix).toContainText('对比样本与观察数据');
      await appExpect(visualMatrix).toContainText('不形成强结论');
      await appExpect(visualMatrix).toContainText('AI 观察主题');
      await appExpect(page.getByTestId('rotation-radar-matrix-point-observation_ai')).toContainText('↑ +2.4%');
      await appExpect(page.getByTestId('rotation-radar-matrix-point-observation_ai')).toBeVisible();
      await appExpect(page.getByTestId('rotation-radar-visual-unavailable')).toHaveCount(0);
      await appExpect(leaderList).toContainText('前 1 个观察数据');
      await appExpect(leaderList.getByTestId('rotation-radar-leader-row-observation_ai')).toContainText('对比样本观察');
      await appExpect(leaderList.getByTestId('rotation-radar-leader-row-observation_ai')).toContainText('升温观察');
      await appExpect(page.getByTestId('rotation-radar-insufficient-empty')).toHaveCount(0);
      await appExpect(page.getByTestId('rotation-theme-detail-panel')).toContainText('对比样本观察');
      await appExpect(page.getByTestId('rotation-theme-detail-panel')).toContainText('升温观察');
      await appExpect(page.getByTestId('rotation-theme-detail-panel')).toContainText('方向线索：相对 QQQ +2.4%');

      const bodyText = await page.locator('body').innerText();
      baseExpect(bodyText).not.toMatch(forbiddenRotationInternalPattern);
      baseExpect(consoleErrors).toEqual([]);
      baseExpect(unhandledApiRoutes).toEqual([]);
      await expectNoHorizontalOverflow(page);
      await page.unroute('**/api/v1/market/rotation-radar**');
    }
  });
});
