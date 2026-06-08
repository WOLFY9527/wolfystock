import React from 'react';
import '@testing-library/jest-dom/vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import MarketRotationRadarPage from '../MarketRotationRadarPage';
import { marketRotationApi } from '../../api/marketRotation';
import type { MarketRotationRadarResponse, MarketRotationSummaryItem } from '../../api/marketRotation';

vi.mock('../../api/marketRotation', () => ({
  marketRotationApi: {
    getRotationRadar: vi.fn(),
  },
}));

afterEach(() => {
  vi.useRealTimers();
  cleanup();
});

const forbiddenTradingActionPattern =
  /买入按钮|建议买入|建议卖出|买卖|卖出指令|立即交易|下单|提交订单|订单载荷|开仓|平仓|加仓|减仓|持仓建议|仓位建议|决策级|decision[-\s]?grade|buy now|sell now|place order|submit order|best contract|guaranteed|recommend(?:ation|ations|ed|s)?/i;

const rawI18nKeyPattern = /\b(?:rotationRadar|marketRotationRadar|marketIntelligence)\.[A-Za-z0-9_.-]+/;
const consumerDiagnosticLeakPattern =
  /alpaca|alpaca_etf_authority_spine|Alpaca SIP|bounded_etf_authority_active|missing_required_windows|ineligible_bounded_etf|entitlement|reasonCodes?|reasonFamilies|sourceAuthorityAllowed|scoreContributionAllowed|observationOnly|local_taxonomy|taxonomy-only|fallback_static|synthetic_fixture|official_public|authorized_licensed_feed|public_proxy|unofficial_proxy|provider|quote provider|提供方运维|数据源设置|原始来源|原因代码|ETF 权威|ETF 代理|权威来源|权威检查|权威可计分|可计分证据|代理缺口|代理过期|代理完整|proxy_quote_missing|proxy_stale|backend|raw_payload|provider_payload|debug|trace/i;
const consumerMetadataLeakPattern =
  /schema[_\s-]?version|reasonCodes?|sourceAuthorityAllowed|scoreContributionAllowed|providerState|runtime|cache|debug|trace|internal|synthetic|partial_source|raw_payload|provider_payload/i;

type ThemeFlowSignalFixture = NonNullable<NonNullable<MarketRotationRadarResponse['themes'][number]['themeFlowSignal']>> & {
  leadershipEvidence?: string | null;
};
type ObservationSummaryFixtureItem = MarketRotationSummaryItem & Partial<MarketRotationRadarResponse['themes'][number]>;

function buildThemeFlowSignalFixture(
  overrides: Partial<ThemeFlowSignalFixture> = {},
): ThemeFlowSignalFixture {
  return {
    themeFlowState: 'leading',
    confidence: 0.72,
    confidenceLabel: '高',
    reasonCodes: ['source_authority_missing'],
    explanation: 'AI 应用当前由相对强弱与量能扩张支持，属于领涨观察。',
    leadershipEvidence: '龙头成员 APP、PLTR，集中度 36.0%。',
    breadthEvidence: '上涨广度 100.0% / 跑赢广度 100.0% ，3/3 成员有可用观察。',
    relativeStrengthEvidence: '相对 QQQ 强弱 +2.80% 。',
    ...overrides,
  };
}

const radarFixture = (): MarketRotationRadarResponse => ({
  endpoint: '/api/v1/market/rotation-radar',
  market: 'US',
  supportedMarkets: ['US', 'CN', 'HK', 'CRYPTO'],
  generatedAt: '2026-05-07T09:50:00Z',
  source: 'computed',
  sourceLabel: '主题篮子计算',
  freshness: 'delayed',
  isFallback: false,
  isStale: false,
  warning: null,
  noAdviceDisclosure: '仅用于观察资金轮动迹象，非买卖建议。',
  metadata: {
    noExternalCalls: true,
    schemaVersion: 'market_rotation_radar_phase4_v1',
    timeWindows: ['5m', '15m', '60m', '1d'],
    proxyQualityRequired: true,
    alertsAreReadOnlyEvidence: true,
    notificationDeliveryEnabled: false,
  },
  benchmarks: {
    QQQ: { symbol: 'QQQ', changePercent: 0.8, timeWindows: {}, freshness: 'delayed', isFallback: false, isStale: false },
    SPY: { symbol: 'SPY', changePercent: 0.4, timeWindows: {}, freshness: 'delayed', isFallback: false, isStale: false },
    IWM: { symbol: 'IWM', changePercent: 0.1, timeWindows: {}, freshness: 'delayed', isFallback: false, isStale: false },
    IGV: { symbol: 'IGV', changePercent: 0.6, timeWindows: {}, freshness: 'delayed', isFallback: false, isStale: false },
  },
  etfLeadershipDiagnostics: {
    enabled: true,
    source: 'alpaca_etf_authority_spine',
    asOf: '2026-05-07T09:45:00Z',
    eligibleSymbols: ['SPY', 'QQQ', 'IWM', 'SMH', 'SOXX', 'IGV'],
    leadingSymbols: ['SMH', 'SOXX', 'QQQ'],
    laggingSymbols: ['IWM', 'IGV', 'SPY'],
    leadershipSpread: 1.24,
    confidenceLabel: 'high',
    reasonCodes: ['bounded_etf_authority_active'],
    evidence: [
      {
        symbol: 'SPY',
        sourceLabel: 'Alpaca SIP',
        freshness: 'live',
        sourceAuthorityAllowed: true,
        scoreContributionAllowed: true,
        reasonCodes: [],
      },
      {
        symbol: 'QQQ',
        sourceLabel: 'Alpaca SIP',
        freshness: 'live',
        sourceAuthorityAllowed: true,
        scoreContributionAllowed: true,
        reasonCodes: [],
      },
      {
        symbol: 'IWM',
        sourceLabel: 'Alpaca SIP',
        freshness: 'live',
        sourceAuthorityAllowed: true,
        scoreContributionAllowed: true,
        reasonCodes: [],
      },
      {
        symbol: 'SMH',
        sourceLabel: 'Alpaca SIP',
        freshness: 'live',
        sourceAuthorityAllowed: true,
        scoreContributionAllowed: true,
        reasonCodes: [],
      },
      {
        symbol: 'SOXX',
        sourceLabel: 'Alpaca SIP',
        freshness: 'live',
        sourceAuthorityAllowed: true,
        scoreContributionAllowed: true,
        reasonCodes: [],
      },
      {
        symbol: 'IGV',
        sourceLabel: 'Alpaca SIP',
        freshness: 'live',
        sourceAuthorityAllowed: true,
        scoreContributionAllowed: true,
        reasonCodes: [],
      },
    ],
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
        dataGaps: ['true_flow_data_missing', 'flow_methodology_missing'],
        themeFlowSignal: buildThemeFlowSignalFixture(),
      },
    ],
    acceleratingThemes: [
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
        themeFlowSignal: buildThemeFlowSignalFixture(),
      },
    ],
    fadingThemes: [
      {
        id: 'robotics',
        name: '机器人',
        rotationScore: 38,
        confidence: 0.31,
        stage: 'weak_or_no_signal',
        freshness: 'fallback',
        isFallback: true,
        riskLabels: ['stale_or_incomplete_windows'],
        signalType: 'insufficient_evidence',
        flowEvidenceType: 'none',
        flowLanguageAllowed: false,
        sourceAuthorityAllowed: false,
        evidenceQuality: 'insufficient',
        dataGaps: ['true_flow_data_missing', 'source_authority_rejected'],
      },
    ],
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
        themeFlowSignal: buildThemeFlowSignalFixture({
          confidence: 0.68,
          explanation: 'AI / 软件家族当前由 AI 应用领涨，属于领涨观察。',
          leadershipEvidence: '领涨主题 AI 应用。',
          breadthEvidence: '1 个主题纳入观察，平均上涨广度 100.0% ，平均跑赢广度 100.0% 。',
          relativeStrengthEvidence: '平均相对强弱 +2.80% ，当前最强主题为 AI 应用',
        }),
      },
      {
        familyId: 'defensive',
        familyName: '防御',
        themeIds: ['robotics'],
        themeNames: ['机器人'],
        leaderThemeIds: ['robotics'],
        themeCount: 1,
        signalThemeCount: 1,
        averageRotationScore: 38,
        averageConfidence: 0.31,
        themeFlowSignal: buildThemeFlowSignalFixture({
          themeFlowState: 'fading',
          confidence: 0.31,
          confidenceLabel: '低',
          reasonCodes: ['fallback_source'],
          explanation: '防御家族相对强势回落，属于热度降温观察。',
          leadershipEvidence: '领涨主题 机器人。',
          breadthEvidence: '1 个主题纳入观察，平均上涨广度 42.0% ，平均跑赢广度 38.0% 。',
          relativeStrengthEvidence: '平均相对强弱 -0.30% ，当前最强主题为 机器人',
        }),
      },
    ],
    watchlistSignals: [
      { themeId: 'ai_applications', themeName: 'AI 应用', symbol: 'APP', label: '关注候选', signal: 'confirmed_rotation', signalLabel: '确认轮动', confidence: 0.72, persistenceScore: 0.86, readOnly: true, deliveryEnabled: false, reasons: ['AI 应用：确认轮动'], sortExplanation: '按主题轮动强度、置信度、跨时窗持续证据、成员相对强弱和量能扩张排序；仅用于观察信号排队，非买卖建议。' },
    ],
    watchlistSortingExplanation: '关注候选按主题轮动强度、置信度、跨时窗持续证据和成员相对强弱排序；仅作为观察信号，非买卖建议。',
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
      themeFlowSignal: buildThemeFlowSignalFixture(),
      dataGaps: ['true_flow_data_missing', 'flow_methodology_missing', 'benchmark_proxy_missing'],
      stage: 'confirmed_rotation',
      stageExplanation: '价格、量能、广度和同步性同时满足阈值。置信度 72%，3 个分钟级时窗可用。',
      riskLabels: ['gap_fade_risk'],
      riskExplanations: ['涨幅较大但 VWAP、量能或广度确认不足，需防止冲高回落。'],
      newslessRotation: true,
      newslessRotationEvidence: '无明显新闻的同步异动：未配置新闻催化证据。',
      persistenceScore: 0.86,
      persistenceEvidence: {
        score: 0.86,
        label: '跨时窗延续',
        availableWindows: ['5m', '15m', '60m', '1d'],
        missingWindows: [],
        staleOrFallbackWindows: [],
        positiveWindowCount: 4,
        negativeWindowCount: 0,
        sameDirectionWindowCount: 4,
        requiredWindows: ['5m', '15m', '60m', '1d'],
        explanation: '跨时窗延续：可用 5m/15m/60m/1d，缺失 无，备用/过期 无。',
      },
      alertCandidates: [
        { themeId: 'ai_applications', themeName: 'AI 应用', symbol: 'APP', label: '关注候选', signal: 'confirmed_rotation', signalLabel: '确认轮动', confidence: 0.72, persistenceScore: 0.86, persistenceLabel: '跨时窗延续', readOnly: true, deliveryEnabled: false, reasons: ['AI 应用：确认轮动'], sortExplanation: '按主题轮动强度、置信度、跨时窗持续证据、成员相对强弱和量能扩张排序；仅用于观察信号排队，非买卖建议。' },
      ],
      relativeStrength: {
        benchmark: 'QQQ',
        benchmarkChangePercent: 0.8,
        averageThemeChangePercent: 3.6,
        averageRelativeStrengthPercent: 2.8,
        vsBenchmarks: { QQQ: 2.8, SPY: 3.2, IWM: 3.5 },
      },
      proxyQuality: {
        label: 'ETF 代理完整',
        coveragePercent: 100,
        availableProxyCount: 4,
        totalProxyCount: 4,
        requiredProxies: ['QQQ', 'SPY', 'IWM', 'IGV'],
        freshness: 'delayed',
        hasMissingRequiredProxy: false,
        hasStaleProxy: false,
        missingReasons: {},
        explanation: 'ETF 代理完整：ETF 代理覆盖 4/4，缺口 无。',
      },
      benchmarkProxies: {
        QQQ: { symbol: 'QQQ', role: 'market_proxy', changePercent: 0.8, relativeStrength: 2.8, freshness: 'delayed', isFallback: false, isStale: false, sourceLabel: 'Unit Fixture', quality: { available: true, freshness: 'delayed', missingReason: null, qualityLabel: '可用代理', coverageContribution: 1 } },
        SPY: { symbol: 'SPY', role: 'market_proxy', changePercent: 0.4, relativeStrength: 3.2, freshness: 'delayed', isFallback: false, isStale: false, sourceLabel: 'Unit Fixture', quality: { available: true, freshness: 'delayed', missingReason: null, qualityLabel: '可用代理', coverageContribution: 1 } },
        IWM: { symbol: 'IWM', role: 'market_proxy', changePercent: 0.1, relativeStrength: 3.5, freshness: 'delayed', isFallback: false, isStale: false, sourceLabel: 'Unit Fixture', quality: { available: true, freshness: 'delayed', missingReason: null, qualityLabel: '可用代理', coverageContribution: 1 } },
        IGV: { symbol: 'IGV', role: 'sector_proxy', changePercent: 0.6, relativeStrength: 3.0, freshness: 'delayed', isFallback: false, isStale: false, sourceLabel: 'Unit Fixture', quality: { available: true, freshness: 'delayed', missingReason: null, qualityLabel: '可用代理', coverageContribution: 1 } },
      },
      timeWindows: {
        '5m': { window: '5m', label: '5分钟', available: true, changePercent: 0.8, relativeVolume: 1.3, freshness: 'delayed', isFallback: false, isStale: false, sourceLabel: 'Unit Fixture' },
        '15m': { window: '15m', label: '15分钟', available: true, changePercent: 1.4, relativeVolume: 1.5, freshness: 'delayed', isFallback: false, isStale: false, sourceLabel: 'Unit Fixture' },
        '60m': { window: '60m', label: '60分钟', available: true, changePercent: 2.2, relativeVolume: 1.7, freshness: 'delayed', isFallback: false, isStale: false, sourceLabel: 'Unit Fixture' },
        '1d': { window: '1d', label: '日内/日线', available: true, changePercent: 3.6, relativeVolume: 1.8, freshness: 'delayed', isFallback: false, isStale: false, sourceLabel: 'Unit Fixture' },
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
          { symbol: 'PLTR', name: 'PLTR', changePercent: 4.6, relativeStrengthVsBenchmark: 3.8, volumeRatio: 2.0, freshness: 'delayed', isFallback: false },
        ],
      },
      themeDetail: {
        watchlistLabel: '观察清单证据',
        watchlistSafe: true,
        safeActionLabel: '仅观察，不构成买卖建议',
        leaderSectionLabel: '领先成员',
        laggardSectionLabel: '落后/待验证成员',
        leaderExplanation: '领先成员按相对强弱和量能扩张排序，仅代表观察信号强弱。',
        laggardExplanation: '落后/待验证成员用于观察扩散不足或分歧，不是买卖建议。',
        leadershipMembers: [
          { symbol: 'APP', name: 'APP', role: 'leader', roleLabel: '领先成员', changePercent: 5.1, relativeStrengthVsBenchmark: 4.3, freshness: 'delayed', freshnessLabel: '延迟', observed: true },
        ],
        laggardMembers: [
          { symbol: 'CRM', name: 'CRM', role: 'laggard', roleLabel: '落后成员', changePercent: 2.8, relativeStrengthVsBenchmark: 2.0, freshness: 'delayed', freshnessLabel: '延迟', observed: true },
        ],
        memberEvidence: [],
        freshnessLabel: '延迟',
        asOf: '2026-05-07T09:45:00Z',
        disclosure: '仅用于观察资金轮动迹象，非买卖建议。',
      },
      freshness: 'delayed',
      isFallback: false,
      isStale: false,
      source: 'computed',
      sourceLabel: '主题篮子计算',
      asOf: '2026-05-07T09:45:00Z',
      updatedAt: '2026-05-07T09:50:00Z',
      evidence: ['无明显新闻的同步异动', '成交额扩张迹象', '相对 QQQ 强弱 +2.80%'],
      members: [],
      noAdviceDisclosure: '仅用于观察资金轮动迹象，非买卖建议。',
      rotationStateEvidence: {
        state: 'insufficient_evidence',
        stateLabel: '轮动代理证据',
        flowEvidenceType: 'proxy_only',
        flowLanguageAllowed: false,
        requiredDataStatus: {
          hasSufficientEvidence: false,
          summaryLabel: '分类观察',
        },
        riskLabels: ['gap_fade_risk'],
      },
    },
  ],
  consumerEvidenceSnapshot: {
    market: 'US',
    generatedAt: '2026-05-07T09:50:00Z',
    asOf: '2026-05-07T09:45:00Z',
    freshness: 'partial',
    isFallback: false,
    isStale: false,
    isPartial: true,
    authorityGrant: false,
    headlineEligibleThemeCount: 1,
    observationThemeCount: 1,
    taxonomyThemeCount: 0,
    scoreContributionAllowed: false,
    reasonCodes: ['partial_source'],
    themes: [],
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
        themeFlowSignal: buildThemeFlowSignalFixture({
          confidence: 0.68,
          reasonCodes: ['partial_source'],
          explanation: 'AI / 软件家族当前由 AI 应用领涨，属于领涨观察。',
          leadershipEvidence: '领涨主题 AI 应用。',
          breadthEvidence: '1 个主题纳入观察，平均上涨广度 100.0% ，平均跑赢广度 100.0% 。',
          relativeStrengthEvidence: '平均相对强弱 +2.80% ，当前最强主题为 AI 应用',
        }),
      },
    ],
  },
});

const themeNames = [
  'AI 应用',
  '半导体',
  '半导体设备',
  '网络安全',
  '云软件',
  '数据中心电力',
  '液冷散热',
  '机器人',
  '工业自动化',
  '国防航天',
  '医疗生物科技',
  '金融科技',
  '消费者互联网',
  '能源',
];

const marketThemeNames: Record<string, string[]> = {
  CN: ['AI算力', 'AI基建 / 液冷散热', '光模块 / CPO', '半导体设备', '国产芯片', '机器人', '低空经济', '新能源车链', '创新药', '证券金融'],
  HK: ['港股科技', '互联网平台', '港股生物科技', '新能源汽车', '金融保险', '能源资源', '消费服务', '高股息红利'],
  CRYPTO: ['Layer 1', 'Layer 2', 'DeFi', 'AI Crypto', 'Exchange / Platform', 'Stablecoin Infrastructure', 'Bitcoin Ecosystem', 'DePIN'],
};

function radarUniverseFixture(): MarketRotationRadarResponse {
  const fixture = radarFixture();
  const baseTheme = fixture.themes[0];
  const themes = themeNames.map((name, index) => {
    const score = 88 - index * 4;
    const isWeak = score < 56;
    const leaderSymbol = name === '机器人' ? 'BOTZ' : index === 0 ? 'APP' : `US${index}`;
    return {
      ...baseTheme,
      id: index === 0 ? 'ai_applications' : `theme_${index}`,
      name,
      englishName: name === '机器人' ? 'Robotics' : `${name} Cluster`,
      rotationScore: score,
      confidence: Math.max(0.18, 0.84 - index * 0.05),
      stage: isWeak ? 'weak_or_no_signal' : index > 7 ? 'cooling_watch' : baseTheme.stage,
      stageExplanation: `${name} 当前以相对强弱、成交额扩张、广度和同步性作为观察依据。`,
      focus: `${name} 代表性成员与代理观察`,
      riskLabels: isWeak ? ['thin_breadth'] : index % 3 === 0 ? ['gap_fade_risk'] : [],
      riskExplanations: isWeak ? ['广度偏薄，暂不放大解释。'] : [],
      relativeStrength: {
        ...baseTheme.relativeStrength,
        averageRelativeStrengthPercent: 3.8 - index * 0.35,
      },
      volume: {
        ...baseTheme.volume,
        averageRelativeVolume: Math.max(0.75, 1.9 - index * 0.08),
      },
      breadth: {
        ...baseTheme.breadth,
        percentUp: Math.max(25, 96 - index * 5),
        percentOutperformingBenchmark: Math.max(20, 92 - index * 5),
      },
      synchronization: {
        ...baseTheme.synchronization,
        sameDirectionPercent: Math.max(20, 94 - index * 6),
      },
      leadership: {
        ...baseTheme.leadership,
        leadershipConcentrationPercent: Math.min(78, 28 + index * 4),
        broadParticipationPercent: Math.max(18, 76 - index * 4),
        topMembers: [
          { symbol: leaderSymbol, name: leaderSymbol, changePercent: 5.1 - index * 0.2, relativeStrengthVsBenchmark: 4.3 - index * 0.2, volumeRatio: 2.2, freshness: 'delayed', isFallback: false },
        ],
      },
      evidence: [`${name} 观察证据`, '成交额扩张迹象'],
      alertCandidates: index < 2 ? [
        {
          ...baseTheme.alertCandidates?.[0],
          themeId: index === 0 ? 'ai_applications' : `theme_${index}`,
          themeName: name,
          symbol: index === 0 ? 'APP' : 'BOTZ',
          label: '关注候选',
          signalLabel: isWeak ? '信号较弱' : '确认轮动',
        },
      ] : [],
    };
  });
  fixture.themes = themes;
  fixture.summary = {
    ...fixture.summary,
    strongestThemes: themes.slice(0, 3),
    acceleratingThemes: themes.slice(0, 2),
    fadingThemes: themes.slice(-3),
    watchlistSignals: [
      { themeId: 'ai_applications', themeName: 'AI 应用', symbol: 'APP', label: '关注候选', signal: 'confirmed_rotation', signalLabel: '确认轮动', confidence: 0.84, readOnly: true, deliveryEnabled: false },
      { themeId: 'theme_7', themeName: '机器人', symbol: 'BOTZ', label: '关注候选', signal: 'confirmed_rotation', signalLabel: '确认轮动', confidence: 0.79, readOnly: true, deliveryEnabled: false },
    ],
  };
  return fixture;
}

function taxonomyMarketFixture(market: 'CN' | 'HK' | 'CRYPTO'): MarketRotationRadarResponse {
  const fixture = radarFixture();
  const names = marketThemeNames[market];
  fixture.market = market;
  fixture.source = 'local_taxonomy';
  fixture.sourceLabel = '静态主题库';
  fixture.freshness = 'fallback';
  fixture.isFallback = true;
  fixture.warning = '当前为静态主题库，本地行情覆盖后可计算轮动强度。不代表实时买卖信号。';
  fixture.metadata = {
    ...fixture.metadata,
    taxonomyOnlyThemeCount: names.length,
  };
  const baseTheme = fixture.themes[0];
  fixture.themes = names.map((name, index) => ({
    ...baseTheme,
    id: `${market}:theme_cluster:${index}`,
    market,
    name,
    englishName: market === 'CRYPTO' ? `${name} Theme` : `${name} Cluster`,
    focus: `${name} 静态主题分类观察`,
    benchmark: `${market}_LOCAL_TAXONOMY`,
    sectorBenchmark: null,
    membersConfigured: market === 'CN' ? ['寒武纪', '中科曙光', '工业富联'] : market === 'HK' ? ['0700.HK', '9988.HK'] : ['BTC', 'ETH'],
    rotationScore: 18,
    confidence: 0.12,
    confidenceLabel: '待行情确认',
    dataQuality: 'taxonomy_only',
    dataCoverage: 'taxonomy_only',
    staticThemeOnly: true,
    taxonomyType: 'theme_cluster',
    signalType: 'taxonomy_fallback',
    flowEvidenceType: 'none',
    flowLanguageAllowed: false,
    sourceAuthorityAllowed: false,
    evidenceQuality: 'taxonomy_only',
    dataGaps: ['taxonomy_only', 'true_flow_data_missing'],
    stage: 'weak_or_no_signal',
    stageExplanation: '主题库已载入，行情评分待本地数据覆盖，仅作分类观察。',
    riskLabels: ['stale_or_incomplete_windows'],
    riskExplanations: ['行情评分待本地数据覆盖。'],
    newslessRotation: false,
    alertCandidates: [],
    relativeStrength: {},
    benchmarkProxies: {},
    proxyQuality: { label: '静态主题库', coveragePercent: 0, availableProxyCount: 0, totalProxyCount: 0 },
    timeWindows: {},
    volume: { averageRelativeVolume: null, availableMemberCount: 0, label: '待接入本地行情' },
    breadth: { observedMembers: 0, configuredMembers: 0, coveragePercent: 0, percentUp: null, percentOutperformingBenchmark: null },
    synchronization: { sameDirectionPercent: null, aboveVwapPercent: null, persistencePercent: null, label: '分类观察' },
    leadership: { leadershipConcentrationPercent: null, broadParticipationPercent: null, topMembers: [] },
    themeDetail: {
      watchlistSafe: true,
      safeActionLabel: '仅观察，不构成买卖建议',
      mappedConcepts: names.slice(0, 3),
      representativeLabels: market === 'CN' ? ['寒武纪', '中科曙光'] : market === 'HK' ? ['0700.HK', '9988.HK'] : ['BTC', 'ETH'],
      dataStateLabel: '待接入本地行情',
      nextStep: '本地行情覆盖后可计算轮动强度。',
      disclosure: '仅用于观察资金轮动迹象，非买卖建议。',
    },
    freshness: 'fallback',
    isFallback: true,
    source: 'local_taxonomy',
    sourceLabel: '静态主题库',
    evidence: ['主题库已载入', '行情评分待本地数据覆盖', '仅作分类观察'],
    members: [],
  }));
  fixture.summary = {
    ...fixture.summary,
    strongestThemes: [],
    acceleratingThemes: [],
    fadingThemes: [],
    watchlistSignals: [],
  };
  fixture.etfLeadershipDiagnostics = {
    enabled: false,
    source: 'alpaca_etf_authority_spine',
    asOf: '2026-05-07T09:45:00Z',
    eligibleSymbols: [],
    leadingSymbols: [],
    laggingSymbols: [],
    leadershipSpread: null,
    confidenceLabel: 'disabled',
    reasonCodes: ['market_not_supported'],
    evidence: [],
  };
  return fixture;
}

function etfDisabledCandidateFixture(): MarketRotationRadarResponse {
  const fixture = radarFixture();
  fixture.etfLeadershipDiagnostics = {
    enabled: false,
    source: 'alpaca_etf_authority_spine',
    asOf: '2026-05-07T09:45:00Z',
    eligibleSymbols: ['SPY', 'QQQ', 'IWM', 'SOXX', 'IGV'],
    leadingSymbols: [],
    laggingSymbols: [],
    leadershipSpread: null,
    confidenceLabel: 'disabled',
    reasonCodes: ['missing_required_windows', 'ineligible_bounded_etf'],
    evidence: [
      {
        symbol: 'SMH',
        sourceLabel: 'Alpaca SIP',
        freshness: 'live',
        sourceAuthorityAllowed: false,
        scoreContributionAllowed: false,
        reasonCodes: ['missing_required_windows', 'entitlement'],
      },
    ],
  };
  fixture.summary = {
    ...fixture.summary,
    strongestThemes: [],
    acceleratingThemes: [],
    headlineEligibleThemeCount: 0,
    noHeadlineReason: '没有可用于头部排名；ETF authority fail-closed。',
    headlineWarning: '当前头部主题未满足 score-grade real-flow 条件。',
  };
  fixture.themes = [
    {
      ...fixture.themes[0],
      sourceAuthorityAllowed: false,
      evidenceQuality: 'degraded_proxy',
      dataGaps: ['true_flow_data_missing', 'source_authority_rejected'],
      rankingLane: 'observation',
      headlineEligible: false,
      scoreContributionAllowed: false,
    },
  ];
  return fixture;
}

function observationThemesPrimaryFixture(): MarketRotationRadarResponse {
  const fixture = radarFixture();
  const baseTheme = fixture.themes[0];
  const observationTheme: MarketRotationRadarResponse['themes'][number] = {
    ...baseTheme,
    id: 'observation_ai',
    name: 'AI 观察主题',
    englishName: 'AI Observation Theme',
    focus: '对比样本强弱与广度扩散',
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
    relativeStrength: {},
    breadth: {
      observedMembers: 0,
      configuredMembers: 3,
      coveragePercent: 0,
      percentUp: null,
      percentOutperformingBenchmark: null,
    },
    volume: { averageRelativeVolume: null, availableMemberCount: 0, label: '待确认' },
    synchronization: { sameDirectionPercent: undefined, aboveVwapPercent: undefined, persistencePercent: undefined, label: '待确认' },
    leadership: { leadershipConcentrationPercent: null, broadParticipationPercent: null, topMembers: [] },
    stage: 'weak_or_no_signal',
    stageExplanation: 'sourceAuthorityAllowed reasonCodes provider debug raw_payload',
    themeFlowSignal: undefined,
    evidence: ['provider runtime trace'],
  };
  const observationSummary: ObservationSummaryFixtureItem = {
    id: observationTheme.id,
    name: observationTheme.name,
    rotationScore: 68,
    confidence: 0.64,
    stage: 'early_watch',
    freshness: 'delayed',
    isFallback: false,
    riskLabels: [],
    rankEligible: false,
    taxonomyOnly: false,
    observationOnly: true,
    headlineEligible: false,
    rankingLane: 'observation',
    scoreContributionAllowed: false,
    signalType: 'relative_strength',
    flowEvidenceType: 'proxy_only',
    flowLanguageAllowed: false,
    sourceAuthorityAllowed: false,
    evidenceQuality: 'degraded_proxy',
    dataGaps: ['true_flow_data_missing', 'source_authority_rejected'],
    focus: '对比样本强弱与广度扩散',
    relativeStrength: {
      benchmark: 'QQQ',
      benchmarkChangePercent: 0.2,
      averageThemeChangePercent: 2.6,
      averageRelativeStrengthPercent: 2.4,
      vsBenchmarks: { QQQ: 2.4 },
    },
    breadth: {
      observedMembers: 3,
      configuredMembers: 3,
      coveragePercent: 100,
      percentUp: 72,
      percentOutperformingBenchmark: 68,
    },
    volume: { averageRelativeVolume: 1.42, availableMemberCount: 3, label: '成交额扩张' },
    synchronization: { sameDirectionPercent: 70, aboveVwapPercent: 66, persistencePercent: 62, label: '同步改善' },
    leadership: {
      leadershipConcentrationPercent: 34,
      broadParticipationPercent: 66,
      topMembers: [
        { symbol: 'APP', name: 'APP', changePercent: 3.1, relativeStrengthVsBenchmark: 2.7, volumeRatio: 1.8, freshness: 'delayed', isFallback: false },
      ],
    },
    stageExplanation: 'AI 观察主题由对比样本强弱与广度扩散支持，仅作走势观察。',
    themeFlowSignal: buildThemeFlowSignalFixture({
      confidence: 0.64,
      reasonCodes: ['partial_source'],
      explanation: 'AI 观察主题由相对强弱与广度扩散支持，仅作走势观察。',
      leadershipEvidence: '龙头成员 APP，集中度 34.0%。',
      breadthEvidence: '上涨广度 72.0% / 跑赢广度 68.0% ，3/3 成员有可用观察。',
      relativeStrengthEvidence: '相对 QQQ 强弱 +2.40% 。',
    }),
    evidence: ['相对 QQQ 强弱 +2.40%', '上涨广度 72.0%'],
    membersConfigured: ['APP', 'PLTR', 'CRM'],
  };
  fixture.etfLeadershipDiagnostics = {
    enabled: false,
    source: 'alpaca_etf_authority_spine',
    asOf: '2026-05-07T09:45:00Z',
    eligibleSymbols: ['SPY', 'QQQ'],
    leadingSymbols: [],
    laggingSymbols: [],
    leadershipSpread: null,
    confidenceLabel: 'disabled',
    reasonCodes: ['source_authority_rejected'],
    evidence: [],
  };
  fixture.summary = {
    ...fixture.summary,
    strongestThemes: [],
    acceleratingThemes: [],
    fadingThemes: [],
    observationThemes: [observationSummary],
    headlineEligibleThemeCount: 0,
    observationThemeCount: 1,
    noHeadlineReason: 'sourceAuthorityAllowed scoreContributionAllowed reasonCodes provider',
    headlineWarning: 'provider runtime cache debug trace',
  };
  fixture.consumerEvidenceSnapshot = {
    ...fixture.consumerEvidenceSnapshot,
    headlineEligibleThemeCount: 0,
    observationThemeCount: 1,
    scoreContributionAllowed: false,
    reasonCodes: ['source_authority_rejected', 'partial_source'],
    providerState: {
      present: true,
      status: 'unavailable',
      sourceAuthorityAllowed: false,
      scoreContributionAllowed: false,
    },
  };
  fixture.themes = [observationTheme];
  return fixture;
}

function insufficientEvidenceFixture(): MarketRotationRadarResponse {
  const fixture = radarFixture();
  fixture.source = 'fallback';
  fixture.sourceLabel = '备用数据';
  fixture.freshness = 'fallback';
  fixture.isFallback = true;
  fixture.warning = 'data_insufficient';
  fixture.summary = {
    ...fixture.summary,
    strongestThemes: [],
    acceleratingThemes: [],
    fadingThemes: [],
    watchlistSignals: [],
    noHeadlineReason: '没有可比较主题/行业/概念样本。',
    safeWording: ['仅观察', '暂不能判断', '非买卖建议'],
  };
  fixture.themes = [];
  fixture.etfLeadershipDiagnostics = {
    enabled: false,
    source: 'alpaca_etf_authority_spine',
    asOf: '2026-05-07T09:45:00Z',
    eligibleSymbols: [],
    leadingSymbols: [],
    laggingSymbols: [],
    leadershipSpread: null,
    confidenceLabel: 'disabled',
    reasonCodes: ['data_insufficient'],
    evidence: [],
  };
  return fixture;
}

function realFlowConfirmedFixture(): MarketRotationRadarResponse {
  const fixture = radarFixture();
  const confirmed: MarketRotationRadarResponse['themes'][number] = {
    ...fixture.themes[0],
    id: 'real_flow_semis',
    name: '半导体真实流向',
    englishName: 'Semiconductor Real Flow',
    signalType: 'real_flow',
    flowEvidenceType: 'real_flow',
    flowLanguageAllowed: true,
    sourceAuthorityAllowed: true,
    evidenceQuality: 'score_grade_real_flow',
    dataGaps: [],
    stage: 'confirmed_rotation',
    rankingLane: 'headline',
    headlineEligible: true,
    scoreContributionAllowed: true,
    rotationScore: 86,
    confidence: 0.81,
    stageExplanation: '真实流向、广度与持续证据同时满足阈值。',
    rotationStateEvidence: {
      state: 'confirmed_rotation',
      stateLabel: '真实流向确认',
      flowEvidenceType: 'real_flow',
      flowLanguageAllowed: true,
      requiredDataStatus: {
        hasSufficientEvidence: true,
        summaryLabel: '真实流向可用',
      },
      riskLabels: [],
    },
  };
  const candidate: MarketRotationRadarResponse['themes'][number] = {
    ...fixture.themes[0],
    id: 'proxy_ai',
    name: 'AI 代理候选',
    englishName: 'AI Proxy Candidate',
    signalType: 'momentum_proxy',
    flowEvidenceType: 'proxy_only',
    flowLanguageAllowed: false,
    sourceAuthorityAllowed: false,
    evidenceQuality: 'degraded_proxy',
    dataGaps: ['true_flow_data_missing', 'source_authority_rejected'],
    stage: 'early_watch',
    rankingLane: 'observation',
    headlineEligible: false,
    scoreContributionAllowed: false,
    rotationScore: 74,
    confidence: 0.62,
  };
  fixture.themes = [confirmed, candidate];
  fixture.summary = {
    ...fixture.summary,
    strongestThemes: [confirmed],
    acceleratingThemes: [confirmed],
    observationThemes: [candidate],
    fadingThemes: [],
    watchlistSignals: [],
  };
  return fixture;
}

async function waitForMarketUniverseToSettle(market: 'CN' | 'HK' | 'CRYPTO', expectedTheme: string) {
  await waitFor(() => expect(marketRotationApi.getRotationRadar).toHaveBeenLastCalledWith(market));
  await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  expect(await screen.findByTestId('rotation-radar-universe-list')).toHaveTextContent(expectedTheme);
}

describe('MarketRotationRadarPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(marketRotationApi.getRotationRadar).mockImplementation((market?: string) => {
      if (market === 'CN' || market === 'HK' || market === 'CRYPTO') {
        return Promise.resolve(taxonomyMarketFixture(market));
      }
      return Promise.resolve(radarUniverseFixture());
    });
  });

  it('keeps shell spacing on TerminalPageShell with the shared desktop rhythm', async () => {
    render(<MarketRotationRadarPage />);

    const page = await screen.findByTestId('market-rotation-radar-page');
    const workspaceShell = page.querySelector('[data-workspace-width="near-full"]');
    const shell = page.querySelector('[data-terminal-primitive="page-shell"]');

    expect(page).not.toHaveClass('py-5', 'md:py-6');
    expect(workspaceShell).toHaveAttribute('data-workspace-width', 'near-full');
    expect(workspaceShell).toHaveClass('[--wolfy-consumer-shell-max:1880px]');
    expect(shell).toHaveClass('py-5', 'md:py-6');
  });

  it('renders a compact consumer default view without diagnostic surfaces', async () => {
    render(<MarketRotationRadarPage />);

    const page = await screen.findByTestId('market-rotation-radar-page');
    const controls = await screen.findByTestId('rotation-radar-mode-controls');
    expect(page).toHaveTextContent('主题轮动雷达');
    expect(screen.queryByTestId('rotation-radar-loading-fallback')).not.toBeInTheDocument();
    expect(controls).toHaveAttribute('data-linear-primitive', 'command-bar');
    expect(screen.getByTestId('rotation-market-tab-US')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByPlaceholderText('搜索主题、英文名或成员')).toBeInTheDocument();
    expect(screen.getByTestId('rotation-radar-freshness')).toHaveTextContent('更新时间');

    const guidance = screen.getByTestId('rotation-radar-guidance');
    const pageHeading = screen.getByRole('heading', { level: 1, name: '主题轮动雷达' });
    const heroHeading = screen.getByTestId('rotation-radar-hero-title');
    expect(guidance).toHaveTextContent('信号待确认');
    expect(guidance).toHaveTextContent('AI 应用');
    expect(guidance).toHaveTextContent('当前以相对强弱、成交额扩张、广度和同步性作为观察依据。');
    expect(guidance).not.toHaveTextContent('下一步');
    expect(guidance.querySelectorAll('[data-terminal-primitive="chip"]').length).toBeLessThanOrEqual(2);
    expect(pageHeading).toHaveClass('text-xl', 'md:text-2xl');
    expect(heroHeading).toHaveClass('text-base', 'md:text-lg');
    expect(heroHeading).not.toHaveClass('text-2xl');

    const summaryBand = screen.getByTestId('rotation-radar-summary-band');
    expect(summaryBand).toHaveAttribute('data-terminal-primitive', 'panel');
    expect(summaryBand.children).toHaveLength(3);
    expect(summaryBand).toHaveTextContent('当前市场');
    expect(summaryBand).toHaveTextContent('轮动方向');
    expect(summaryBand).toHaveTextContent('数据状态');

    const visualMatrix = screen.getByTestId('rotation-radar-visual-matrix');
    expect(visualMatrix).toHaveTextContent('相对强弱矩阵');
    expect(visualMatrix).toHaveTextContent('主题排行');
    expect(visualMatrix).toHaveTextContent('AI 应用');
    expect(visualMatrix).toHaveTextContent('半导体');
    expect(within(visualMatrix).getAllByTestId(/rotation-radar-matrix-point-/).length).toBeGreaterThanOrEqual(3);
    expect(within(visualMatrix).getAllByTestId(/rotation-radar-ranking-bar-/).length).toBeGreaterThanOrEqual(3);
    expect(screen.queryByTestId('rotation-radar-visual-unavailable')).not.toBeInTheDocument();

    const familyRollup = screen.getByTestId('rotation-family-flow-rollup');
    expect(familyRollup).toHaveTextContent('家族流向观察');
    expect(familyRollup).toHaveTextContent('AI / 软件');
    expect(familyRollup).toHaveTextContent('领涨观察');
    expect(familyRollup).toHaveTextContent('信号 68%');
    expect(familyRollup).toHaveTextContent('领涨主题 AI 应用。');
    expect(familyRollup).toHaveTextContent('平均相对强弱 +2.80%');
    expect(familyRollup).toHaveTextContent('观察项');

    const mechanics = screen.getByTestId('rotation-radar-mechanics-details');
    expect(mechanics).toHaveAttribute('data-terminal-primitive', 'disclosure');
    expect(mechanics).not.toHaveAttribute('open');
    expect(within(mechanics).getByRole('button', { name: '展开 查看轮动说明' })).toHaveAttribute('aria-expanded', 'false');

    const universeList = screen.getByTestId('rotation-radar-universe-list');
    const leaderList = screen.getByTestId('rotation-radar-leader-list');
    const detail = screen.getByTestId('rotation-theme-detail-panel');
    expect(visualMatrix.compareDocumentPosition(leaderList) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(leaderList.compareDocumentPosition(detail) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(detail.compareDocumentPosition(universeList) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(universeList.compareDocumentPosition(guidance) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(universeList).toHaveTextContent('AI 应用');
    expect(leaderList).toHaveAttribute('data-linear-primitive', 'data-workbench-frame');
    expect(within(leaderList).getAllByTestId(/rotation-radar-leader-row-/)).toHaveLength(3);
    expect(within(leaderList).getByText('AI 应用')).toBeInTheDocument();
    expect(within(screen.getByTestId('rotation-radar-leader-row-ai_applications')).getByText(/信号 \d+%/)).toBeInTheDocument();

    expect(detail).toHaveAttribute('data-linear-primitive', 'context-rail');
    expect(detail).toHaveTextContent('当前主题');
    expect(detail).toHaveTextContent('AI 应用');
    expect(detail).toHaveTextContent('轮动方向');
    expect(detail).toHaveTextContent('走势分化');
    expect(detail).toHaveTextContent('观察重点');
    expect(detail).toHaveTextContent('观察标的');
    const dataNotes = screen.getByTestId('rotation-theme-data-notes');
    expect(dataNotes).toHaveAttribute('data-terminal-primitive', 'disclosure');
    expect(within(dataNotes).getByRole('button', { name: '展开 查看数据说明' })).toHaveAttribute('aria-expanded', 'false');
    const themeFlow = screen.getByTestId('rotation-theme-flow-signal');
    expect(themeFlow).toHaveAttribute('data-terminal-primitive', 'disclosure');
    expect(themeFlow).not.toHaveAttribute('open');
    expect(within(themeFlow).getByRole('button', { name: '展开 查看主题流向观察' })).toHaveAttribute('aria-expanded', 'false');

    expect(screen.queryByTestId('rotation-capital-summary')).not.toBeInTheDocument();
    expect(screen.queryByTestId('rotation-decision-readiness')).not.toBeInTheDocument();
    expect(screen.queryByTestId('rotation-radar-buckets')).not.toBeInTheDocument();
    expect(screen.queryByTestId('rotation-etf-diagnostics-disclosure')).not.toBeInTheDocument();

    const bodyText = page.textContent || '';
    expect(bodyText).not.toMatch(rawI18nKeyPattern);
    expect(bodyText).not.toMatch(consumerDiagnosticLeakPattern);
    expect(bodyText).not.toMatch(/缺失证据|结论状态|观察就绪|置信度/);
    expect(bodyText).not.toMatch(forbiddenTradingActionPattern);
    expect(bodyText).not.toMatch(/\bDetails\b/i);
  });

  it('shows a bounded user-visible fallback while the route request remains unresolved', async () => {
    vi.useFakeTimers();
    vi.mocked(marketRotationApi.getRotationRadar).mockImplementationOnce(
      () => new Promise<MarketRotationRadarResponse>(() => {}),
    );

    render(<MarketRotationRadarPage />);

    expect(screen.getByRole('status')).toHaveTextContent('正在读取主题轮动 / 相对强弱雷达');
    expect(screen.getByRole('status')).toHaveTextContent('正在整理主题强弱、轮动线索与最近更新时间。');
    expect(screen.getByRole('status')).toHaveTextContent('准备好后会自动显示当前市场、头部主题和观察重点。');
    expect(screen.getByRole('status')).toHaveTextContent('结果出来前不会补写临时轮动方向。');
    expect(screen.queryByTestId('rotation-radar-loading-fallback')).not.toBeInTheDocument();

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      await vi.runAllTicks();
      await vi.advanceTimersByTimeAsync(5_000);
    });

    const fallback = screen.getByTestId('rotation-radar-loading-fallback');
    expect(fallback).toHaveTextContent('轮动数据暂未返回');
    expect(fallback).toHaveTextContent('可稍后重试');
    expect(fallback).toHaveTextContent('当前不会补写临时轮动方向');
    expect(fallback).toHaveTextContent('重新读取');
    expect(screen.queryByTestId('rotation-radar-guidance')).not.toBeInTheDocument();

    const bodyText = document.body.textContent || '';
    expect(bodyText).not.toMatch(rawI18nKeyPattern);
    expect(bodyText).not.toMatch(consumerDiagnosticLeakPattern);
    expect(bodyText).not.toMatch(forbiddenTradingActionPattern);
  });

  it('falls back to consumer evidence family rollup when summary family data is absent', async () => {
    const fixture = radarFixture();
    fixture.summary.rotationFamilyRollup = [];
    fixture.consumerEvidenceSnapshot = {
      ...fixture.consumerEvidenceSnapshot,
      rotationFamilyRollup: [
        {
          familyId: 'defensive',
          familyName: '防御',
          themeIds: ['robotics'],
          themeNames: ['机器人'],
          leaderThemeIds: ['robotics'],
          themeCount: 1,
          signalThemeCount: 1,
          averageRotationScore: 48,
          averageConfidence: 0.42,
          themeFlowSignal: buildThemeFlowSignalFixture({
            themeFlowState: 'rotating',
            confidence: 0.42,
            confidenceLabel: '中',
            reasonCodes: ['partial_source'],
            explanation: '防御家族仍在轮动切换阶段，强弱优势尚在形成。',
            leadershipEvidence: '领涨主题 机器人。',
            breadthEvidence: '1 个主题纳入观察，平均上涨广度 56.0% ，平均跑赢广度 52.0% 。',
            relativeStrengthEvidence: '平均相对强弱 +0.35% ，当前最强主题为 机器人',
          }),
        },
      ],
    };
    vi.mocked(marketRotationApi.getRotationRadar).mockResolvedValueOnce(fixture);

    render(<MarketRotationRadarPage />);

    const familyRollup = await screen.findByTestId('rotation-family-flow-rollup');
    expect(familyRollup).toHaveTextContent('防御');
    expect(familyRollup).toHaveTextContent('轮动切换');
    expect(familyRollup.textContent || '').not.toMatch(consumerDiagnosticLeakPattern);
  });

  it('keeps theme flow observation collapsed by default and consumer-safe when expanded', async () => {
    render(<MarketRotationRadarPage />);

    const detail = await screen.findByTestId('rotation-theme-detail-panel');
    const themeFlow = within(detail).getByTestId('rotation-theme-flow-signal');

    expect(themeFlow).not.toHaveAttribute('open');
    expect(themeFlow).not.toHaveTextContent('AI 应用当前由相对强弱与量能扩张支持，属于领涨观察。');
    expect(themeFlow).not.toHaveTextContent('Source Authority Missing');

    fireEvent.click(within(themeFlow).getByRole('button', { name: '展开 查看主题流向观察' }));

    expect(themeFlow).toHaveTextContent('领涨观察');
    expect(themeFlow).toHaveTextContent('信号 72%');
    expect(themeFlow).toHaveTextContent('AI 应用当前由相对强弱与量能扩张支持，属于领涨观察。');
    expect(themeFlow).toHaveTextContent('龙头成员 APP、PLTR，集中度 36.0%。');
    expect(themeFlow).toHaveTextContent('上涨广度 100.0% / 跑赢广度 100.0% ，3/3 成员有可用观察。');
    expect(themeFlow).toHaveTextContent('信号待确认');
    expect(themeFlow.textContent || '').not.toMatch(consumerDiagnosticLeakPattern);
    expect(themeFlow.textContent || '').not.toMatch(forbiddenTradingActionPattern);
  });

  it('uses observation themes as the primary view when headline gates have no eligible themes', async () => {
    vi.mocked(marketRotationApi.getRotationRadar).mockResolvedValueOnce(observationThemesPrimaryFixture());

    render(<MarketRotationRadarPage />);

    const guidance = await screen.findByTestId('rotation-radar-guidance');
    expect(guidance).toHaveTextContent('信号待确认');
    expect(guidance).toHaveTextContent('AI 观察主题');
    expect(guidance).not.toHaveTextContent('板块强弱可读');

    const visualMatrix = screen.getByTestId('rotation-radar-visual-matrix');
    expect(visualMatrix).toHaveTextContent('观察数据');
    expect(visualMatrix).toHaveTextContent('对比样本与观察数据');
    expect(visualMatrix).toHaveTextContent('不形成强结论');
    expect(visualMatrix).toHaveTextContent('AI 观察主题');
    expect(within(visualMatrix).getByTestId('rotation-radar-matrix-point-observation_ai')).toHaveTextContent('+2.4%');
    expect(screen.queryByTestId('rotation-radar-visual-unavailable')).not.toBeInTheDocument();

    const leaderList = screen.getByTestId('rotation-radar-leader-list');
    expect(leaderList).toHaveTextContent('观察数据');
    expect(leaderList).toHaveTextContent('前 1 个观察数据');
    expect(within(leaderList).getByTestId('rotation-radar-leader-row-observation_ai')).toHaveTextContent('AI 观察主题');
    expect(screen.queryByTestId('rotation-radar-insufficient-empty')).not.toBeInTheDocument();

    const detail = screen.getByTestId('rotation-theme-detail-panel');
    expect(detail).toHaveTextContent('AI 观察主题');
    expect(detail).toHaveTextContent('AI 观察主题由对比样本强弱与广度扩散支持，仅作走势观察。');

    const bodyText = document.body.textContent || '';
    expect(bodyText).not.toMatch(rawI18nKeyPattern);
    expect(bodyText).not.toMatch(consumerDiagnosticLeakPattern);
    expect(bodyText).not.toMatch(consumerMetadataLeakPattern);
    expect(bodyText).not.toMatch(forbiddenTradingActionPattern);
    expect(bodyText).not.toMatch(/决策级|decision[-\s]?grade/i);
  });

  it('omits the theme flow disclosure cleanly when the selected theme has no investor signal', async () => {
    const fixture = radarFixture();
    fixture.themes = fixture.themes.map((theme, index) => (
      index === 0
        ? {
            ...theme,
            themeFlowSignal: undefined,
          }
        : theme
    ));
    vi.mocked(marketRotationApi.getRotationRadar).mockResolvedValueOnce(fixture);

    render(<MarketRotationRadarPage />);

    const detail = await screen.findByTestId('rotation-theme-detail-panel');
    expect(detail).toHaveTextContent('当前主题');
    expect(detail).toHaveTextContent('AI 应用');
    expect(within(detail).queryByTestId('rotation-theme-flow-signal')).not.toBeInTheDocument();
  });

  it('switches market tabs to populated taxonomy universes with compact library framing', async () => {
    render(<MarketRotationRadarPage />);

    await screen.findByTestId('rotation-radar-mode-controls');
    fireEvent.click(screen.getByTestId('rotation-market-tab-CN'));
    await waitForMarketUniverseToSettle('CN', 'AI算力');

    expect(screen.getByTestId('rotation-market-tab-CN')).toHaveAttribute('aria-pressed', 'true');
    expect(within(screen.getByTestId('rotation-radar-leader-list')).queryAllByTestId(/rotation-radar-leader-row-/)).toHaveLength(0);
    expect(screen.getByTestId('rotation-radar-guidance')).toHaveTextContent('轮动方向待确认');
    expect(screen.getByTestId('rotation-radar-visual-unavailable')).toHaveTextContent('矩阵暂不可用');
    expect(screen.queryByTestId('rotation-radar-visual-matrix')).not.toBeInTheDocument();
    expect(screen.getByTestId('rotation-radar-universe-list')).toHaveTextContent('AI算力');
    expect(screen.getByTestId('rotation-theme-detail-panel')).toHaveTextContent('当前主题');
    expect(screen.getByTestId('rotation-theme-detail-panel')).toHaveTextContent('AI算力');
    expect(screen.getByTestId('rotation-theme-detail-panel')).toHaveTextContent('分类浏览');
    expect(screen.getByTestId('rotation-theme-detail-panel')).toHaveTextContent('寒武纪');

    fireEvent.click(screen.getByTestId('rotation-market-tab-HK'));
    await waitForMarketUniverseToSettle('HK', '港股科技');
    expect(screen.getByTestId('rotation-radar-universe-list')).toHaveTextContent('港股科技');

    fireEvent.click(screen.getByTestId('rotation-market-tab-CRYPTO'));
    await waitForMarketUniverseToSettle('CRYPTO', 'DeFi');
    expect(screen.getByTestId('rotation-radar-universe-list')).toHaveTextContent('DeFi');
  });

  it('updates the compact selected theme panel when a row is selected', async () => {
    render(<MarketRotationRadarPage />);

    await screen.findByTestId('rotation-radar-mode-controls');
    const detail = screen.getByTestId('rotation-theme-detail-panel');
    expect(detail).toHaveTextContent('AI 应用');

    fireEvent.click(screen.getByTestId('rotation-radar-leader-row-theme_2'));

    expect(detail).toHaveTextContent('半导体设备');
    expect(detail).not.toHaveTextContent('AI 应用 当前以主题强弱与广度变化为主');
  });

  it('keeps the full universe searchable and compact', async () => {
    render(<MarketRotationRadarPage />);

    await screen.findByTestId('rotation-radar-mode-controls');
    fireEvent.change(screen.getByPlaceholderText('搜索主题、英文名或成员'), { target: { value: '能源' } });

    const universe = screen.getByTestId('rotation-radar-universe-list');
    expect(universe).toHaveTextContent('能源');
    expect(universe).not.toHaveTextContent('半导体');

    fireEvent.change(screen.getByPlaceholderText('搜索主题、英文名或成员'), { target: { value: '不存在的主题' } });
    expect(universe).toHaveTextContent('没有匹配主题。');
  });

  it('renders compact observation and unavailable states without leaking internals', async () => {
    vi.mocked(marketRotationApi.getRotationRadar).mockResolvedValueOnce(etfDisabledCandidateFixture());

    render(<MarketRotationRadarPage />);

    const observationGuidance = await screen.findByTestId('rotation-radar-guidance');
    expect(observationGuidance).toHaveTextContent('信号待确认');
    expect(observationGuidance).toHaveTextContent('AI 应用');
    expect(observationGuidance.textContent || '').not.toMatch(consumerDiagnosticLeakPattern);
    expect(screen.getByTestId('rotation-radar-visual-matrix')).toBeInTheDocument();

    vi.mocked(marketRotationApi.getRotationRadar).mockResolvedValueOnce(insufficientEvidenceFixture());
    fireEvent.click(screen.getByRole('button', { name: '刷新主题轮动雷达' }));

    const unavailableGuidance = await screen.findByTestId('rotation-radar-guidance');
    expect(unavailableGuidance).toHaveTextContent('轮动方向待确认');
    expect(unavailableGuidance).toHaveTextContent('当前缺少足够行情与时间窗口数据，轮动方向待确认。');
    expect(screen.getByTestId('rotation-radar-visual-unavailable')).toHaveTextContent('矩阵暂不可用');
    expect(screen.getByTestId('rotation-radar-insufficient-empty')).toHaveTextContent('轮动方向待确认');
    expect(screen.queryByTestId('rotation-theme-detail-panel')).not.toBeInTheDocument();

    const bodyText = document.body.textContent || '';
    expect(bodyText).not.toMatch(forbiddenTradingActionPattern);
    expect(bodyText).not.toMatch(rawI18nKeyPattern);
    expect(bodyText).not.toMatch(consumerDiagnosticLeakPattern);
  });

  it('keeps metadata and diagnostics vocabulary hidden behind consumer-safe wording', async () => {
    const fixture = radarFixture();
    fixture.metadata = {
      ...fixture.metadata,
      schemaVersion: 'market_rotation_radar_phase4_boundary_v1',
      runtimeBoundary: 'provider_state_cache_trace',
    };
    fixture.warning = 'provider runtime cache unavailable';
    fixture.summary.headlineWarning = 'reasonCodes sourceAuthorityAllowed scoreContributionAllowed partial_source';
    fixture.summary.noHeadlineReason = 'schema_version synthetic internal trace provider_payload';
    fixture.summary.rankingPolicy = 'providerState runtime cache internal';
    fixture.consumerEvidenceSnapshot = {
      ...fixture.consumerEvidenceSnapshot,
      reasonCodes: ['partial_source', 'synthetic_fixture'],
      providerState: {
        present: true,
        status: 'unavailable',
        quoteMode: 'synthetic',
        sourceType: 'synthetic_bundle',
        sourceTier: 'public_proxy',
        providerTier: 'cache_runtime',
        freshness: 'unavailable',
        asOf: '2026-05-07T09:45:00Z',
        sourceAuthorityAllowed: false,
        scoreContributionAllowed: false,
        noExternalCalls: true,
      },
      etfProxySummary: {
        present: true,
        proxyOnly: true,
        label: 'synthetic proxy pack',
        fundFlowAuthorityAllowed: false,
        enabled: false,
        source: 'synthetic_proxy',
        asOf: '2026-05-07T09:45:00Z',
        reasonCodes: ['synthetic_fixture', 'provider_timeout'],
      },
      themes: [
        {
          id: 'ai_applications',
          name: 'AI 应用',
          freshness: 'unavailable',
          isFallback: true,
          isStale: true,
          isPartial: true,
          evidenceQuality: 'synthetic_only',
          dataGaps: ['synthetic_fixture', 'provider_timeout'],
        },
      ],
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
            ...buildThemeFlowSignalFixture(),
            reasonCodes: ['synthetic_fixture', 'partial_source'],
            explanation: 'provider runtime cache trace boundary',
          },
        },
      ],
    };
    fixture.themes = fixture.themes.map((theme, index) => (
      index === 0
        ? {
            ...theme,
            stageExplanation: 'provider runtime cache synthetic internal reasonCodes sourceAuthorityAllowed',
            evidence: [
              'provider payload trace',
              'runtime cache providerState',
            ],
            riskExplanations: [
              'schema_version partial_source',
              'synthetic internal trace',
            ],
            dataGaps: ['synthetic_fixture', 'provider_timeout'],
            themeFlowSignal: buildThemeFlowSignalFixture({
              explanation: 'provider runtime cache trace raw_payload',
              reasonCodes: ['synthetic_fixture', 'provider_timeout'],
              leadershipEvidence: 'sourceAuthorityAllowed provider_state',
              breadthEvidence: 'reasonCodes cache_runtime',
              relativeStrengthEvidence: 'debug trace synthetic',
            }),
          }
        : theme
    ));
    vi.mocked(marketRotationApi.getRotationRadar).mockResolvedValueOnce(fixture);

    render(<MarketRotationRadarPage />);

    const page = await screen.findByTestId('market-rotation-radar-page');
    const detail = screen.getByTestId('rotation-theme-detail-panel');
    expect(detail).toHaveTextContent('部分轮动数据暂不可用。');
    expect(detail.textContent || '').not.toMatch(consumerMetadataLeakPattern);

    const dataNotes = screen.getByTestId('rotation-theme-data-notes');
    fireEvent.click(within(dataNotes).getByRole('button', { name: '展开 查看数据说明' }));
    expect(dataNotes).toHaveTextContent('部分轮动数据暂不可用。');
    expect(dataNotes.textContent || '').not.toMatch(consumerMetadataLeakPattern);

    const themeFlow = screen.getByTestId('rotation-theme-flow-signal');
    fireEvent.click(within(themeFlow).getByRole('button', { name: '展开 查看主题流向观察' }));
    expect(themeFlow).toHaveTextContent('部分轮动数据暂不可用。');
    expect(themeFlow.textContent || '').not.toMatch(consumerMetadataLeakPattern);

    fireEvent.click(screen.getByRole('button', { name: '展开 查看轮动说明' }));
    const mechanics = screen.getByTestId('rotation-radar-mechanics-details');
    expect(mechanics.textContent || '').not.toMatch(consumerMetadataLeakPattern);

    const bodyText = page.textContent || '';
    expect(bodyText).not.toMatch(rawI18nKeyPattern);
    expect(bodyText).not.toMatch(consumerDiagnosticLeakPattern);
    expect(bodyText).not.toMatch(consumerMetadataLeakPattern);
    expect(bodyText).not.toMatch(forbiddenTradingActionPattern);
  });

  it('fails closed when the route request never settles', async () => {
    vi.useFakeTimers();
    vi.mocked(marketRotationApi.getRotationRadar).mockImplementationOnce(
      () => new Promise<MarketRotationRadarResponse>(() => {}),
    );

    render(<MarketRotationRadarPage />);

    expect(screen.getByRole('status')).toHaveTextContent('正在读取主题轮动 / 相对强弱雷达');

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      await vi.runAllTicks();
      await vi.advanceTimersByTimeAsync(12_000);
      await vi.runAllTicks();
      await Promise.resolve();
    });

    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('主题轮动暂时不可用');
    expect(alert).toHaveTextContent('页面未在预期时间内完成读取，当前无法判断轮动方向。请稍后刷新重试。');
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.queryByTestId('rotation-radar-loading-fallback')).not.toBeInTheDocument();
    expect(screen.queryByTestId('rotation-radar-guidance')).not.toBeInTheDocument();
    expect(alert.textContent || '').not.toMatch(forbiddenTradingActionPattern);
    expect(alert.textContent || '').not.toMatch(consumerDiagnosticLeakPattern);
  });

  it('keeps real-flow-ready states compact while preserving selected theme usability', async () => {
    vi.mocked(marketRotationApi.getRotationRadar).mockResolvedValueOnce(realFlowConfirmedFixture());

    render(<MarketRotationRadarPage />);

    const guidance = await screen.findByTestId('rotation-radar-guidance');
    expect(guidance).toHaveTextContent('板块强弱可读');
    expect(guidance).toHaveTextContent('半导体真实流向');
    const leaderList = screen.getByTestId('rotation-radar-leader-list');
    expect(within(leaderList).getAllByTestId(/rotation-radar-leader-row-/)).toHaveLength(1);
    expect(within(leaderList).getByTestId('rotation-radar-leader-row-real_flow_semis')).toHaveTextContent('半导体真实流向');
    const detail = screen.getByTestId('rotation-theme-detail-panel');
    expect(detail).toHaveTextContent('当前主题');
    expect(detail).toHaveTextContent('半导体真实流向');
    expect(detail).toHaveTextContent('确认轮动');
    expect(detail).toHaveTextContent('观察重点');
    expect(detail.textContent || '').not.toMatch(/置信度|置信 \d+%/);
    expect(document.body.textContent || '').not.toMatch(forbiddenTradingActionPattern);
  });
});
