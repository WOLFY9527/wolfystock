import { expect as baseExpect } from '@playwright/test';
import { expect as appExpect, test as appTest } from './fixtures/appSmoke';
import { expectNoHorizontalOverflow, fulfillJson, installSignedInSessionRoutes, openSignedInRoute } from './fixtures/authenticatedRouteSmoke';

const viewports = [
  { width: 1440, height: 1000 },
  { width: 390, height: 844 },
] as const;

const forbiddenRotationInternalPattern =
  /provider|runtime|cache|debug|trace|raw_payload|provider_payload|schema|reasonCodes?|sourceAuthorityAllowed|scoreContributionAllowed|decision[-\s]?grade|决策级/i;

function familyDensityPayload() {
  const timestamp = '2026-05-07T09:50:00Z';

  return {
    endpoint: '/api/v1/market/rotation-radar',
    market: 'US',
    supportedMarkets: ['US', 'CN', 'HK', 'CRYPTO'],
    generatedAt: timestamp,
    source: 'computed',
    sourceLabel: '主题篮子计算',
    freshness: 'delayed',
    isFallback: false,
    isStale: false,
    warning: null,
    noAdviceDisclosure: '仅用于观察资金轮动迹象，非买卖建议。',
    metadata: {
      noExternalCalls: true,
      schemaVersion: 'rotation_family_density_test',
      timeWindows: ['5m', '15m', '60m', '1d'],
      proxyQualityRequired: true,
      alertsAreReadOnlyEvidence: true,
      notificationDeliveryEnabled: false,
    },
    benchmarks: {
      QQQ: { symbol: 'QQQ', changePercent: 0.8, timeWindows: {}, freshness: 'delayed', isFallback: false, isStale: false },
    },
    etfLeadershipDiagnostics: {
      enabled: true,
      source: 'alpaca_etf_authority_spine',
      asOf: timestamp,
      eligibleSymbols: ['SPY', 'QQQ'],
      leadingSymbols: ['QQQ'],
      laggingSymbols: ['SPY'],
      leadershipSpread: 1.24,
      confidenceLabel: 'high',
      reasonCodes: ['bounded_etf_authority_active'],
      evidence: [],
    },
    summary: {
      strongestThemes: [
        {
          id: 'ai_applications',
          name: 'AI 应用',
          rotationScore: 78,
          confidence: 0.72,
          stage: 'confirmed_rotation',
          freshness: 'delayed',
          isFallback: false,
          riskLabels: [],
          signalType: 'relative_strength',
          flowEvidenceType: 'proxy_only',
          flowLanguageAllowed: false,
          sourceAuthorityAllowed: true,
          evidenceQuality: 'degraded_proxy',
          dataGaps: ['true_flow_data_missing'],
        },
      ],
      acceleratingThemes: [],
      fadingThemes: [],
      observationThemes: [],
      taxonomyThemes: [],
      rotationFamilyRollup: [
        {
          familyId: 'ai',
          familyName: 'AI / 软件',
          themeIds: ['ai_applications'],
          themeNames: ['AI 应用'],
          leaderThemeIds: ['ai_applications'],
          themeCount: 1,
          signalThemeCount: 1,
          averageRotationScore: 78,
          averageConfidence: 0.68,
          themeFlowSignal: {
            themeFlowState: 'leading',
            confidence: 0.68,
            confidenceLabel: '高',
            reasonCodes: ['partial_source'],
            explanation: 'AI / 软件家族当前由 AI 应用领涨，属于领涨观察。',
            leadershipEvidence: '领涨主题 AI 应用。',
            breadthEvidence: '1 个主题纳入观察，平均上涨广度 100.0% ，平均跑赢广度 100.0% 。',
            relativeStrengthEvidence: '平均相对强弱 +2.80% ，当前最强主题为 AI 应用',
          },
        },
        {
          familyId: 'defensive_zero',
          familyName: '低信号防御',
          themeIds: ['zero_signal_defensive'],
          themeNames: ['低信号防御'],
          leaderThemeIds: ['zero_signal_defensive'],
          themeCount: 1,
          signalThemeCount: 0,
          averageRotationScore: 0,
          averageConfidence: 0,
          themeFlowSignal: null,
        },
      ],
      watchlistSignals: [],
      watchlistSortingExplanation: '仅作为观察信号，非买卖建议。',
      safeWording: ['资金轮动迹象', '成交额扩张', '相对强势扩散', '板块同步性增强', '非买卖建议'],
    },
    themes: [
      {
        id: 'ai_applications',
        name: 'AI 应用',
        englishName: 'AI Applications',
        focus: '应用层软件、数据工作流与企业 AI 落地',
        benchmark: 'QQQ',
        sectorBenchmark: 'IGV',
        membersConfigured: ['APP', 'PLTR', 'CRM'],
        rotationScore: 78,
        confidence: 0.72,
        signalType: 'relative_strength',
        flowEvidenceType: 'proxy_only',
        flowLanguageAllowed: false,
        sourceAuthorityAllowed: true,
        evidenceQuality: 'degraded_proxy',
        dataGaps: ['true_flow_data_missing'],
        stage: 'confirmed_rotation',
        stageExplanation: '价格、量能、广度和同步性同时满足阈值。',
        riskLabels: [],
        riskExplanations: [],
        persistenceScore: 0.86,
        persistenceEvidence: { score: 0.86, label: '跨时窗延续' },
        alertCandidates: [],
        relativeStrength: {
          benchmark: 'QQQ',
          benchmarkChangePercent: 0.8,
          averageThemeChangePercent: 3.6,
          averageRelativeStrengthPercent: 2.8,
          vsBenchmarks: { QQQ: 2.8 },
        },
        volume: { averageRelativeVolume: 1.8, availableMemberCount: 3, label: '成交额扩张明显' },
        breadth: {
          observedMembers: 3,
          configuredMembers: 3,
          coveragePercent: 100,
          percentUp: 100,
          percentOutperformingBenchmark: 100,
        },
        synchronization: { sameDirectionPercent: 100, aboveVwapPercent: 100, persistencePercent: 100, label: '板块同步性增强' },
        leadership: {
          leadershipConcentrationPercent: 36,
          broadParticipationPercent: 64,
          topMembers: [
            { symbol: 'APP', name: 'APP', changePercent: 5.1, relativeStrengthVsBenchmark: 4.3, volumeRatio: 2.2, freshness: 'delayed', isFallback: false },
          ],
        },
        themeDetail: {
          watchlistSafe: true,
          safeActionLabel: '仅观察，不构成买卖建议',
          disclosure: '仅用于观察资金轮动迹象，非买卖建议。',
        },
        freshness: 'delayed',
        isFallback: false,
        isStale: false,
        source: 'computed',
        sourceLabel: '主题篮子计算',
        asOf: timestamp,
        updatedAt: timestamp,
        evidence: ['成交额扩张迹象', '相对 QQQ 强弱 +2.80%'],
        members: [],
        noAdviceDisclosure: '仅用于观察资金轮动迹象，非买卖建议。',
        themeFlowSignal: {
          themeFlowState: 'leading',
          confidence: 0.72,
          confidenceLabel: '高',
          reasonCodes: ['partial_source'],
          explanation: 'AI 应用当前由相对强弱与量能扩张支持，属于领涨观察。',
          leadershipEvidence: '龙头成员 APP、PLTR，集中度 36.0%。',
          breadthEvidence: '上涨广度 100.0% / 跑赢广度 100.0% ，3/3 成员有可用观察。',
          relativeStrengthEvidence: '相对 QQQ 强弱 +2.80% 。',
        },
      },
      {
        id: 'zero_signal_defensive',
        name: '低信号防御',
        englishName: 'Defensive Zero Signal',
        focus: '观察线索',
        benchmark: 'QQQ',
        sectorBenchmark: null,
        membersConfigured: ['XLU'],
        rotationScore: 0,
        confidence: 0,
        signalType: 'insufficient_evidence',
        flowEvidenceType: 'none',
        flowLanguageAllowed: false,
        sourceAuthorityAllowed: false,
        evidenceQuality: 'insufficient',
        dataGaps: ['true_flow_data_missing', 'source_authority_rejected'],
        stage: 'weak_or_no_signal',
        stageExplanation: '当前缺少足够行情与时间窗口数据，暂不能形成稳定轮动判断',
        riskLabels: ['stale_or_incomplete_windows'],
        riskExplanations: ['信号待确认。'],
        persistenceScore: null,
        persistenceEvidence: null,
        alertCandidates: [],
        relativeStrength: {},
        volume: { averageRelativeVolume: null, availableMemberCount: 0, label: '待确认' },
        breadth: {
          observedMembers: 0,
          configuredMembers: 1,
          coveragePercent: 0,
          percentUp: null,
          percentOutperformingBenchmark: null,
        },
        synchronization: { sameDirectionPercent: null, aboveVwapPercent: null, persistencePercent: null, label: '待确认' },
        leadership: { leadershipConcentrationPercent: null, broadParticipationPercent: null, topMembers: [] },
        themeDetail: {
          watchlistSafe: true,
          safeActionLabel: '仅观察，不构成买卖建议',
          disclosure: '仅用于观察资金轮动迹象，非买卖建议。',
        },
        freshness: 'delayed',
        isFallback: false,
        isStale: false,
        source: 'computed',
        sourceLabel: '主题篮子计算',
        asOf: timestamp,
        updatedAt: timestamp,
        evidence: ['当前缺少足够行情与时间窗口数据，暂不能形成稳定轮动判断'],
        members: [],
        noAdviceDisclosure: '仅用于观察资金轮动迹象，非买卖建议。',
      },
    ],
    consumerEvidenceSnapshot: {
      market: 'US',
      generatedAt: timestamp,
      asOf: timestamp,
      freshness: 'partial',
      isFallback: false,
      isStale: false,
      isPartial: true,
      authorityGrant: false,
      headlineEligibleThemeCount: 1,
      observationThemeCount: 0,
      taxonomyThemeCount: 0,
      scoreContributionAllowed: false,
      reasonCodes: ['partial_source'],
      themes: [],
      rotationFamilyRollup: [],
    },
  };
}

appTest.describe('rotation radar family density', () => {
  appTest('keeps low-signal families collapsed by default while preserving an expand path', async ({ page, consoleErrors, unhandledApiRoutes }) => {
    for (const viewport of viewports) {
      await page.setViewportSize(viewport);
      await installSignedInSessionRoutes(page);
      await page.route('**/api/v1/market/rotation-radar**', async (route) => {
        await fulfillJson(route, familyDensityPayload());
      });

      await openSignedInRoute(page, '/zh/market/rotation-radar');

      const familyRollup = page.getByTestId('rotation-family-flow-rollup');
      const spotlightRow = page.getByTestId('rotation-family-rollup-row-ai');
      const collapsedDisclosure = page.getByTestId('rotation-family-rollup-collapsed');

      await appExpect(familyRollup).toBeVisible({ timeout: 15_000 });
      await appExpect(familyRollup).toContainText('家族流向观察');
      await appExpect(familyRollup).toContainText('首屏优先保留有信号家族');
      await appExpect(spotlightRow).toContainText('AI / 软件');
      await appExpect(spotlightRow).toContainText('领涨观察');
      await appExpect(collapsedDisclosure.getByRole('button', { name: '展开 查看低信号家族' })).toHaveAttribute('aria-expanded', 'false');
      await appExpect(page.getByTestId('rotation-family-rollup-collapsed-row-defensive_zero')).toHaveCount(0);

      await collapsedDisclosure.getByRole('button', { name: '展开 查看低信号家族' }).click();

      const collapsedRow = page.getByTestId('rotation-family-rollup-collapsed-row-defensive_zero');
      await appExpect(collapsedRow).toBeVisible();
      await appExpect(collapsedRow).toContainText('低信号防御');
      await appExpect(collapsedRow).toContainText('0/1 个有信号');
      await appExpect(collapsedRow).toContainText('默认折叠保留查阅入口');

      const bodyText = await page.locator('body').innerText();
      baseExpect(bodyText).not.toMatch(forbiddenRotationInternalPattern);
      baseExpect(consoleErrors).toEqual([]);
      baseExpect(unhandledApiRoutes).toEqual([]);
      await expectNoHorizontalOverflow(page);
      await page.unroute('**/api/v1/market/rotation-radar**');
    }
  });
});
