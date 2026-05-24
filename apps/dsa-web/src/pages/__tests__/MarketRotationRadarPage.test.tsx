import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import MarketRotationRadarPage from '../MarketRotationRadarPage';
import { marketRotationApi } from '../../api/marketRotation';
import type { MarketRotationRadarResponse } from '../../api/marketRotation';

vi.mock('../../api/marketRotation', () => ({
  marketRotationApi: {
    getRotationRadar: vi.fn(),
  },
}));

const forbiddenTradingActionPattern =
  /买入按钮|建议买入|建议卖出|买卖|卖出指令|立即交易|下单|提交订单|订单载荷|开仓|平仓|加仓|减仓|持仓建议|仓位建议|决策级|decision[-\s]?grade|buy now|sell now|place order|submit order|best contract|guaranteed|recommend(?:ation|ations|ed|s)?/i;

const rawI18nKeyPattern = /\b(?:rotationRadar|marketRotationRadar|marketIntelligence)\.[A-Za-z0-9_.-]+/;

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
    safeWording: ['仅观察', '证据不足', '非买卖建议'],
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

  it('renders a compact top-N radar instead of a full theme card wall by default', async () => {
    render(<MarketRotationRadarPage />);

    const page = await screen.findByTestId('market-rotation-radar-page');
    expect(page).toHaveTextContent('主题轮动雷达');
    expect(page.className).not.toContain('bg-[#030303]');
    expect(page.querySelector('[data-terminal-primitive="page-shell"]')).not.toBeNull();
    expect(screen.getByTestId('rotation-capital-summary')).toHaveTextContent('轮动结论');
    expect(screen.getByTestId('rotation-capital-summary')).toHaveTextContent('仅观察');
    expect(screen.getByTestId('rotation-capital-summary')).toHaveTextContent('确认主线');
    expect(screen.getByTestId('rotation-capital-summary')).toHaveTextContent('暂无真实流向确认');
    expect(screen.getByTestId('rotation-capital-summary')).toHaveTextContent('候选观察');
    expect(screen.getByTestId('rotation-capital-summary')).toHaveTextContent('AI 应用');
    expect(screen.getByTestId('rotation-capital-summary')).toHaveTextContent('分类库');
    expect(screen.getByTestId('rotation-capital-summary')).not.toHaveTextContent('AI算力');
    expect(screen.getByTestId('rotation-capital-summary')).not.toHaveTextContent(/Capital Rotation Summary|Candidate watchlist|taxonomy-only/i);
    expect(screen.getByTestId('rotation-capital-summary').textContent || '').not.toMatch(forbiddenTradingActionPattern);
    expect(screen.getByTestId('rotation-radar-summary-band')).toHaveAttribute('data-terminal-primitive', 'panel');
    expect(screen.getByTestId('rotation-radar-summary-band')).toHaveTextContent('当前状态');
    expect(screen.getByTestId('rotation-radar-summary-band')).toHaveTextContent('当前可用 / 观察信号');
    expect(screen.getByTestId('rotation-radar-summary-band')).toHaveTextContent('缺哪些证据 / 升级条件');
    expect(screen.getByTestId('rotation-radar-summary-band')).toHaveTextContent('真实流向确认');
    expect(screen.getByTestId('rotation-radar-guidance')).toHaveTextContent('下一步应配置或等待什么数据');
    expect(screen.getByTestId('rotation-radar-mode-controls')).toHaveTextContent('美股');
    expect(screen.getByTestId('rotation-radar-mode-controls')).toHaveAttribute('data-linear-primitive', 'command-bar');
    expect(screen.getByTestId('rotation-taxonomy-mode-note')).toHaveTextContent('主题优先');
    expect(screen.getByTestId('rotation-radar-mode-controls')).not.toHaveTextContent('ETF代理');
    expect(screen.getByTestId('rotation-market-tab-US')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: '刷新主题轮动雷达' })).toHaveAttribute('data-terminal-primitive', 'button');
    expect(screen.getByTestId('rotation-radar-freshness')).toHaveAttribute('data-terminal-primitive', 'nested-block');
    expect(screen.queryByTestId('rotation-radar-lane-band')).not.toBeInTheDocument();

    const leaderList = screen.getByTestId('rotation-radar-leader-list');
    expect(leaderList).toHaveAttribute('data-linear-primitive', 'data-workbench-frame');
    expect(within(leaderList).getAllByTestId(/rotation-radar-leader-row-/)).toHaveLength(3);
    expect(within(leaderList).getAllByTestId(/rotation-radar-laggard-row-/).length).toBeGreaterThan(0);
    expect(within(leaderList).getByText('AI 应用')).toBeInTheDocument();
    expect(within(leaderList).queryByText('AI算力')).not.toBeInTheDocument();
    expect(within(leaderList).queryByText('Layer 1')).not.toBeInTheDocument();
    expect(screen.queryByTestId('rotation-theme-card-ai_applications')).not.toBeInTheDocument();
    expect(screen.queryByText('下一观察：')).not.toBeInTheDocument();

    const detail = screen.getByTestId('rotation-theme-detail-panel');
    expect(detail).toHaveAttribute('data-linear-primitive', 'context-rail');
    expect(detail).toHaveTextContent('AI 应用');
    expect(within(detail).getAllByText('相对强弱')[0]).toHaveAttribute('data-terminal-primitive', 'chip');
    expect(within(detail).getAllByText('受限代理级')[0]).toHaveAttribute('data-terminal-primitive', 'chip');
    expect(within(detail).getByText('确认轮动')).toHaveAttribute('data-terminal-primitive', 'chip');
    expect(within(detail).getByText(/^置信度 \d+%$/)).toHaveAttribute('data-terminal-primitive', 'chip');
    expect(within(detail).getByText('延迟可用')).toHaveAttribute('data-terminal-primitive', 'chip');
    expect(within(detail).getByText('非交易指令')).toHaveAttribute('data-terminal-primitive', 'chip');
    expect(screen.getByTestId('rotation-radar-universe-list')).toHaveTextContent('主题 / 行业板');
    expect(screen.getByPlaceholderText('搜索主题、英文名或成员')).toBeInTheDocument();

    const bodyText = page.textContent?.toLowerCase() || '';
    expect(bodyText).not.toMatch(/raw_payload|provider_payload|api_key|password|session_id|cookie|secret/);
    expect(bodyText).not.toMatch(forbiddenTradingActionPattern);
  });

  it('renders a bounded ETF leadership diagnostics panel from etfLeadershipDiagnostics only', async () => {
    render(<MarketRotationRadarPage />);

    const disclosure = await screen.findByTestId('rotation-etf-diagnostics-disclosure');
    fireEvent.click(within(disclosure).getByRole('button', { name: '展开 ETF 权威来源技术细节' }));
    const panel = await screen.findByTestId('rotation-radar-etf-leadership-panel');
    expect(panel).toHaveTextContent('ETF 代理权威检查');
    expect(panel).toHaveTextContent('SPY / QQQ / IWM / SMH / SOXX / IGV');
    expect(panel).toHaveTextContent('已启用');
    expect(panel).toHaveTextContent('置信度 高');
    expect(panel).toHaveTextContent('来源 权威行情源');
    expect(panel).toHaveTextContent('SMH');
    expect(panel).toHaveTextContent('SOXX');
    expect(panel).toHaveTextContent('QQQ');
    expect(panel).toHaveTextContent('IWM');
    expect(panel).toHaveTextContent('IGV');
    expect(panel).toHaveTextContent('SPY');
    expect(panel).toHaveTextContent(/ETF 权威来源\s*已启用/);
    expect(panel).not.toHaveTextContent('bounded_etf_authority_active');
    expect(panel).toHaveTextContent('权威 6/6');
    expect(panel).toHaveTextContent('可计分 6/6');
    expect(panel.textContent || '').not.toMatch(/headline eligible|top theme|bullish|risk-on/i);
    expect(panel.textContent || '').not.toMatch(/alpaca_etf_authority_spine|Alpaca SIP|Score-Eligible|Source|Confidence/i);
    expect(panel.textContent || '').not.toMatch(forbiddenTradingActionPattern);

    const debug = within(panel).getByTestId('rotation-etf-raw-reason-codes');
    expect(debug).not.toHaveAttribute('open');
    fireEvent.click(within(debug).getByRole('button', { name: '展开 原始来源 / 原因代码' }));
    expect(debug).toHaveTextContent('alpaca_etf_authority_spine');
    expect(debug).toHaveTextContent('Alpaca SIP');
    expect(debug).toHaveTextContent('bounded_etf_authority_active');
  });

  it('keeps shell spacing on TerminalPageShell with the shared desktop rhythm', async () => {
    render(<MarketRotationRadarPage />);

    const page = await screen.findByTestId('market-rotation-radar-page');
    const shell = page.querySelector('[data-terminal-primitive="page-shell"]');

    expect(page).not.toHaveClass('py-5', 'md:py-6');
    expect(shell).toHaveAttribute('data-workspace-width', 'near-full');
    expect(shell).toHaveClass('max-w-[1840px]');
    expect(shell).toHaveClass('py-5', 'md:py-6');
  });

  it('switches market tabs to populated CN HK and Crypto taxonomy universes', async () => {
    render(<MarketRotationRadarPage />);

    await screen.findByTestId('market-rotation-radar-page');
    fireEvent.click(screen.getByTestId('rotation-market-tab-CN'));

    await waitFor(() => expect(marketRotationApi.getRotationRadar).toHaveBeenLastCalledWith('CN'));
    const taxonomySummary = screen.getByTestId('rotation-capital-summary');
    expect(taxonomySummary).toHaveTextContent('轮动结论');
    expect(taxonomySummary).toHaveTextContent('当前无法判断轮动方向');
    expect(taxonomySummary).toHaveTextContent('确认主线');
    expect(taxonomySummary).toHaveTextContent('暂无真实流向确认');
    expect(taxonomySummary).toHaveTextContent('候选观察');
    expect(taxonomySummary).toHaveTextContent('暂无候选主题');
    expect(taxonomySummary).toHaveTextContent('分类库');
    expect(taxonomySummary).toHaveTextContent('AI算力');
    expect(taxonomySummary).toHaveTextContent('当前无法判断轮动方向');
    expect(taxonomySummary.textContent || '').not.toMatch(/rotationRadar\./);
    expect(screen.getByTestId('rotation-market-tab-CN')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('rotation-radar-leader-list')).toHaveTextContent(/当前无法判断轮动方向|按主题分类浏览/);
    expect(within(screen.getByTestId('rotation-radar-leader-list')).queryAllByTestId(/rotation-radar-leader-row-/)).toHaveLength(0);
    expect(screen.getByTestId('rotation-radar-universe-list')).toHaveTextContent('AI算力');
    expect(screen.getByTestId('rotation-theme-detail-panel')).toHaveTextContent('当前无法判断轮动方向');
    expect(screen.getByTestId('rotation-theme-detail-panel')).toHaveTextContent('需要真实流向确认、权威来源检查、广度确认与多时窗行情同时补齐后，才能升级为轮动方向判断。');
    expect(screen.getByTestId('rotation-theme-detail-panel')).toHaveTextContent('寒武纪');
    expect(document.body.textContent || '').not.toMatch(/\bN\/A\b/g);

    fireEvent.click(screen.getByTestId('rotation-market-tab-HK'));
    await waitFor(() => expect(marketRotationApi.getRotationRadar).toHaveBeenLastCalledWith('HK'));
    expect(within(screen.getByTestId('rotation-radar-leader-list')).queryAllByTestId(/rotation-radar-leader-row-/)).toHaveLength(0);
    expect(screen.getByTestId('rotation-radar-universe-list')).toHaveTextContent('港股科技');

    fireEvent.click(screen.getByTestId('rotation-market-tab-CRYPTO'));
    await waitFor(() => expect(marketRotationApi.getRotationRadar).toHaveBeenLastCalledWith('CRYPTO'));
    expect(within(screen.getByTestId('rotation-radar-leader-list')).queryAllByTestId(/rotation-radar-leader-row-/)).toHaveLength(0);
    expect(screen.getByTestId('rotation-radar-universe-list')).toHaveTextContent('DeFi');
  });

  it('updates the single selected detail panel when a leader row is selected', async () => {
    render(<MarketRotationRadarPage />);

    await screen.findByTestId('market-rotation-radar-page');
    expect(screen.getByTestId('rotation-theme-detail-panel')).toHaveTextContent('AI 应用');

    fireEvent.click(screen.getByTestId('rotation-radar-leader-row-theme_2'));

    const detail = screen.getByTestId('rotation-theme-detail-panel');
    expect(detail).toHaveTextContent('半导体设备');
    expect(detail).toHaveTextContent('半导体设备 Cluster');
    expect(detail).toHaveTextContent('US2');
    expect(detail).not.toHaveTextContent('AI 应用 当前以相对强弱');
  });

  it('keeps the full universe compact and searchable without noisy cards', async () => {
    render(<MarketRotationRadarPage />);

    await screen.findByTestId('market-rotation-radar-page');
    fireEvent.change(screen.getByPlaceholderText('搜索主题、英文名或成员'), { target: { value: '能源' } });

    const universe = screen.getByTestId('rotation-radar-universe-list');
    expect(universe).toHaveTextContent('能源');
    expect(universe).not.toHaveTextContent('半导体');
    expect(screen.queryByTestId('rotation-theme-card-theme_11')).not.toBeInTheDocument();
  });

  it('marks fallback radar data as fallback instead of live', async () => {
    vi.mocked(marketRotationApi.getRotationRadar).mockResolvedValueOnce({
      ...radarFixture(),
      source: 'fallback',
      sourceLabel: '备用数据',
      freshness: 'fallback',
      isFallback: true,
      warning: '未配置实时 quote provider，返回降级主题篮子。',
      summary: {
        strongestThemes: [],
        acceleratingThemes: [],
        fadingThemes: [],
        safeWording: ['资金轮动迹象', '非买卖建议'],
      },
      themes: [
        {
          ...radarFixture().themes[0],
          rotationScore: 34,
          confidence: 0.12,
          stage: 'weak_or_no_signal',
          freshness: 'fallback',
          isFallback: true,
          riskLabels: ['stale_or_incomplete_windows', 'thin_breadth'],
          alertCandidates: [],
          newslessRotation: false,
          evidence: ['静态主题篮子示例，未接入行情快照。'],
        },
      ],
    });

    render(<MarketRotationRadarPage />);

    await waitFor(() => expect(screen.getByTestId('rotation-radar-freshness')).toHaveTextContent('备用'));
    const leaderList = screen.getByTestId('rotation-radar-leader-list');
    expect(within(leaderList).queryAllByTestId(/rotation-radar-leader-row-/)).toHaveLength(0);
    expect(leaderList).toHaveTextContent(/当前无法判断轮动方向|真实流向确认|广度确认/);
    const detail = screen.getByTestId('rotation-theme-detail-panel');
    expect(detail).toHaveTextContent('信号较弱');
    expect(detail).toHaveTextContent('备用');
    expect(within(detail).getByTestId('data-freshness-badge-fallback')).toBeInTheDocument();
    expect(within(detail).queryByTestId('data-freshness-badge-live')).not.toBeInTheDocument();
    expect(screen.getByText('部分外部数据暂不可用').closest('[data-terminal-primitive="notice"]')).not.toBeNull();
  });

  it('keeps ETF-disabled non-taxonomy evidence in the candidate watchlist', async () => {
    const fixture = etfDisabledCandidateFixture();
    vi.mocked(marketRotationApi.getRotationRadar).mockResolvedValueOnce(fixture);

    render(<MarketRotationRadarPage />);

    expect(await screen.findByTestId('rotation-radar-guidance')).toHaveTextContent('仅观察');
    expect(screen.getByTestId('rotation-radar-guidance')).toHaveTextContent('暂不能判断轮动方向');
    expect(screen.getByTestId('rotation-radar-guidance')).not.toHaveTextContent('主题库模式');
    const capitalSummary = screen.getByTestId('rotation-capital-summary');
    expect(capitalSummary).toHaveTextContent('仅观察');
    expect(capitalSummary).toHaveTextContent('确认主线');
    expect(capitalSummary).toHaveTextContent('暂无真实流向确认');
    expect(capitalSummary).toHaveTextContent('候选观察');
    expect(capitalSummary).toHaveTextContent('AI 应用');
    expect(capitalSummary).toHaveTextContent('分类库');
    expect(capitalSummary).toHaveTextContent('暂无分类库条目');

    const leaderList = screen.getByTestId('rotation-radar-leader-list');
    expect(leaderList).toHaveTextContent('候选观察');
    expect(within(leaderList).getByTestId('rotation-radar-leader-row-ai_applications')).toHaveTextContent('AI 应用');
    expect(within(leaderList).getByTestId('rotation-radar-leader-row-ai_applications')).toHaveTextContent('78');
    expect(within(leaderList).getByTestId('rotation-radar-leader-row-ai_applications')).not.toHaveTextContent('主题库');

    const detail = screen.getByTestId('rotation-theme-detail-panel');
    expect(detail).toHaveTextContent('相对强弱');
    expect(detail).toHaveTextContent('受限代理级');
    expect(detail).toHaveTextContent('需要权威来源');
    expect(detail).not.toHaveTextContent('主题库不是机会榜');

    const disclosure = await screen.findByTestId('rotation-etf-diagnostics-disclosure');
    fireEvent.click(within(disclosure).getByRole('button', { name: '展开 ETF 权威来源技术细节' }));
    const panel = await screen.findByTestId('rotation-radar-etf-leadership-panel');
    expect(panel).toHaveTextContent('未启用');
    expect(panel).toHaveTextContent('置信度 未启用');
    expect(panel).toHaveTextContent('ETF 必要时窗缺失');
    expect(panel).toHaveTextContent(/ETF 权威来源\s*未满足可用条件/);
    expect(panel).not.toHaveTextContent('missing_required_windows');
    expect(panel).not.toHaveTextContent('ineligible_bounded_etf');
    expect(panel).not.toHaveTextContent('disabled');
    expect(panel).toHaveTextContent('权威 0/1');
    expect(panel).toHaveTextContent('可计分 0/1');
    expect(panel).not.toHaveTextContent('leadingSymbols');
    expect(panel.textContent || '').not.toMatch(/bullish|risk-on|outperform breakout/i);
    expect(panel.textContent || '').not.toMatch(forbiddenTradingActionPattern);

    const debug = within(panel).getByTestId('rotation-etf-raw-reason-codes');
    fireEvent.click(within(debug).getByRole('button', { name: '展开 原始来源 / 原因代码' }));
    expect(debug).toHaveTextContent('missing_required_windows');
    expect(debug).toHaveTextContent('ineligible_bounded_etf');

    const bodyText = document.body.textContent || '';
    expect(bodyText).not.toMatch(forbiddenTradingActionPattern);
    expect(bodyText).not.toMatch(rawI18nKeyPattern);
  });

  it('renders an actionable insufficient-evidence empty state without promoting a rotation direction', async () => {
    vi.mocked(marketRotationApi.getRotationRadar).mockResolvedValueOnce(insufficientEvidenceFixture());

    render(<MarketRotationRadarPage />);

    const page = await screen.findByTestId('market-rotation-radar-page');
    const decisionReadiness = await screen.findByTestId('rotation-decision-readiness');
    expect(decisionReadiness).toHaveTextContent('当前无法判断轮动方向');
    expect(decisionReadiness).toHaveTextContent('当前证据不足');
    expect(screen.getByTestId('rotation-capital-summary')).toHaveTextContent('轮动结论');
    expect(screen.getByTestId('rotation-capital-summary')).toHaveTextContent('当前无法判断轮动方向');
    expect(screen.getByTestId('rotation-radar-guidance')).toHaveTextContent('缺哪些证据 / 升级条件');
    expect(screen.getByTestId('rotation-radar-guidance')).toHaveTextContent('可比较主题/行业/概念样本');
    expect(screen.getByTestId('rotation-radar-guidance')).toHaveTextContent('下一步应配置或等待什么数据');
    expect(screen.getByTestId('rotation-radar-guidance')).toHaveTextContent('先补齐对应市场的行情');

    const emptyState = screen.getByTestId('rotation-radar-insufficient-empty');
    expect(emptyState).toHaveTextContent('当前无法判断轮动方向');
    expect(emptyState).toHaveTextContent('没有可比较的行情时窗、成员广度、真实流向或权威来源确认');
    expect(emptyState).toHaveTextContent('真实流向确认');
    expect(emptyState).toHaveTextContent('权威来源检查');
    expect(emptyState).toHaveTextContent('广度确认');
    expect(emptyState).toHaveTextContent('等待新的多时窗快照');
    expect(emptyState).not.toHaveTextContent('暂无');

    const details = screen.getByTestId('rotation-guidance-technical-details');
    expect(details).toHaveAttribute('data-terminal-primitive', 'disclosure');
    expect(details).not.toHaveAttribute('open');
    expect(screen.queryByTestId('rotation-radar-lane-band')).not.toBeInTheDocument();
    fireEvent.click(within(details).getByRole('button', { name: '展开 技术细节' }));
    expect(screen.getByTestId('rotation-radar-lane-band')).toHaveTextContent('证据不足');

    expect(screen.getByTestId('rotation-radar-mode-controls')).toHaveTextContent('美股');
    expect(screen.getByTestId('rotation-market-tab-US')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByPlaceholderText('搜索主题、英文名或成员')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '刷新主题轮动雷达' })).toBeInTheDocument();
    expect(screen.queryByTestId('rotation-theme-detail-panel')).not.toBeInTheDocument();

    const bodyText = page.textContent || '';
    expect(bodyText).not.toMatch(forbiddenTradingActionPattern);
    expect(bodyText).not.toMatch(rawI18nKeyPattern);
    expect(bodyText).not.toMatch(/Capital Rotation Summary|Candidate watchlist|taxonomy-only|ETF authority|score-grade|real-flow|breadth confirmation|Details|Enabled|Disabled|Confidence|Source|Score-Eligible/i);
  });

  it('keeps full taxonomy-only markets in library framing only', async () => {
    vi.mocked(marketRotationApi.getRotationRadar).mockResolvedValueOnce(taxonomyMarketFixture('CN'));

    render(<MarketRotationRadarPage />);

    expect(await screen.findByTestId('rotation-radar-guidance')).toHaveTextContent('当前无法判断轮动方向');
    const capitalSummary = screen.getByTestId('rotation-capital-summary');
    expect(capitalSummary).toHaveTextContent('轮动结论');
    expect(capitalSummary).toHaveTextContent('确认主线');
    expect(capitalSummary).toHaveTextContent('暂无真实流向确认');
    expect(capitalSummary).toHaveTextContent('候选观察');
    expect(capitalSummary).toHaveTextContent('暂无候选主题');
    expect(capitalSummary).toHaveTextContent('分类库');
    expect(capitalSummary).toHaveTextContent('AI算力');
    expect(capitalSummary).not.toHaveTextContent('仅候选观察');

    const leaderList = screen.getByTestId('rotation-radar-leader-list');
    expect(leaderList).toHaveTextContent(/当前无法判断轮动方向|按主题分类浏览/);
    expect(within(leaderList).queryAllByTestId(/rotation-radar-leader-row-/)).toHaveLength(0);
    expect(screen.getByTestId('rotation-radar-universe-list')).toHaveTextContent('主题库');

    const detail = screen.getByTestId('rotation-theme-detail-panel');
    expect(detail).toHaveTextContent('当前无法判断轮动方向');
    expect(detail).toHaveTextContent('分类映射');
    expect(detail).toHaveTextContent('寒武纪');

    const bodyText = document.body.textContent || '';
    expect(bodyText).not.toMatch(forbiddenTradingActionPattern);
    expect(bodyText).not.toMatch(rawI18nKeyPattern);
  });

  it('puts score-grade real-flow evidence in confirmed leaders without promoting proxy candidates', async () => {
    vi.mocked(marketRotationApi.getRotationRadar).mockResolvedValueOnce(realFlowConfirmedFixture());

    render(<MarketRotationRadarPage />);

    expect(await screen.findByTestId('rotation-radar-guidance')).toHaveTextContent('可判断');
    const capitalSummary = screen.getByTestId('rotation-capital-summary');
    expect(capitalSummary).toHaveTextContent('可判断');
    expect(capitalSummary).toHaveTextContent('确认主线');
    expect(capitalSummary).toHaveTextContent('半导体真实流向');
    expect(capitalSummary).toHaveTextContent('候选观察');
    expect(capitalSummary).toHaveTextContent('AI 代理候选');

    const leaderList = screen.getByTestId('rotation-radar-leader-list');
    expect(within(leaderList).getByTestId('rotation-radar-leader-row-real_flow_semis')).toHaveTextContent('半导体真实流向');
    expect(within(leaderList).getByTestId('rotation-radar-leader-row-real_flow_semis')).toHaveTextContent('86');
    expect(within(leaderList).queryByTestId('rotation-radar-leader-row-proxy_ai')).not.toBeInTheDocument();

    const detail = screen.getByTestId('rotation-theme-detail-panel');
    expect(detail).toHaveTextContent('真实流向确认');
    expect(detail).toHaveTextContent('真实流向级');
    expect(detail).not.toHaveTextContent('AI 代理候选 当前具备真实资金流证据');

    const bodyText = document.body.textContent || '';
    expect(bodyText).not.toMatch(forbiddenTradingActionPattern);
    expect(bodyText).not.toMatch(rawI18nKeyPattern);
  });

  it('distinguishes rotation readiness for confirmed flow, candidate-only, and taxonomy evidence', async () => {
    vi.mocked(marketRotationApi.getRotationRadar).mockResolvedValueOnce(realFlowConfirmedFixture());

    const readyView = render(<MarketRotationRadarPage />);
    const readyBand = await screen.findByTestId('rotation-decision-readiness');
    expect(readyBand).toHaveTextContent('判断可用性');
    expect(readyBand).toHaveTextContent('可判断');
    expect(readyBand).toHaveTextContent('确认 1');
    expect(readyBand).toHaveTextContent('权威可计分');
    expect(within(readyBand).queryByText('查看需配置的数据源')).not.toBeInTheDocument();
    expect(readyBand.textContent || '').not.toMatch(forbiddenTradingActionPattern);
    readyView.unmount();

    vi.mocked(marketRotationApi.getRotationRadar).mockResolvedValueOnce(etfDisabledCandidateFixture());

    const observationView = render(<MarketRotationRadarPage />);
    const observationBand = await screen.findByTestId('rotation-decision-readiness');
    expect(observationBand).toHaveTextContent('仅观察');
    expect(observationBand).toHaveTextContent('暂不能判断轮动方向');
    expect(observationBand).toHaveTextContent('真实流向确认缺失');
    const observationSetupPath = within(observationBand).getByTestId('rotation-setup-path');
    expect(observationSetupPath).toHaveTextContent('查看需配置的数据源');
    expect(observationSetupPath).toHaveTextContent('补齐行情覆盖');
    expect(observationSetupPath).toHaveTextContent('减少备用或代理证据');
    expect(observationSetupPath).toHaveTextContent('提升为可评分证据的可能性');
    expect(within(observationSetupPath).getByRole('link', { name: '查看提供方运维' })).toHaveAttribute('href', '/admin/market-providers?surface=rotation_radar');
    expect(within(observationSetupPath).getByRole('link', { name: '前往数据源设置' })).toHaveAttribute('href', '/settings/system?panel=data_sources&surface=rotation_radar');
    expect(observationSetupPath.textContent || '').not.toMatch(forbiddenTradingActionPattern);
    observationView.unmount();

    vi.mocked(marketRotationApi.getRotationRadar).mockResolvedValueOnce(taxonomyMarketFixture('CN'));

    render(<MarketRotationRadarPage />);
    const unavailableBand = await screen.findByTestId('rotation-decision-readiness');
    expect(unavailableBand).toHaveTextContent('当前无法判断轮动方向');
    expect(unavailableBand).toHaveTextContent('仅有主题分类');
    expect(unavailableBand).toHaveTextContent('当前证据不足');
    expect(within(unavailableBand).getByTestId('rotation-setup-path')).toHaveTextContent('前往数据源设置');
    expect(unavailableBand.textContent || '').not.toMatch(forbiddenTradingActionPattern);
  });

  it('renders proxy-only evidence chips without real fund-flow claims', async () => {
    render(<MarketRotationRadarPage />);

    const detail = await screen.findByTestId('rotation-theme-detail-panel');
    expect(within(detail).getByText('轮动代理证据')).toBeInTheDocument();
    expect(within(detail).getByText('分类观察')).toBeInTheDocument();
    expect(within(detail).getByText('真实资金流暂缺')).toBeInTheDocument();
    expect(within(detail).getAllByText('相对强弱').length).toBeGreaterThan(0);
    expect(within(detail).getAllByText('受限代理级').length).toBeGreaterThan(0);
    expect(detail.textContent || '').not.toMatch(/真实资金流确认|资金流入确认/);

    const evidenceDetails = within(detail).getByTestId('rotation-theme-evidence-details-ai_applications');
    expect(evidenceDetails).toHaveAttribute('data-terminal-primitive', 'disclosure');
    expect(evidenceDetails).not.toHaveAttribute('open');
    expect(within(evidenceDetails).queryByText('AI 应用 观察证据')).not.toBeInTheDocument();
    fireEvent.click(within(evidenceDetails).getByRole('button', { name: '展开 证据详情' }));
    expect(evidenceDetails).toHaveTextContent('AI 应用 观察证据');
  });

  it('keeps proxy diagnostics user-facing and omits developer diagnostics by default', async () => {
    const fixture = radarFixture();
    fixture.warning = 'provider_timeout';
    fixture.metadata = {
      ...fixture.metadata,
      raw_payload: { provider_payload: true, debug: true },
    };
    fixture.themes[0] = {
      ...fixture.themes[0],
      stageExplanation: 'not_enough_history',
      evidence: ['technical_indicators_unavailable'],
      riskExplanations: ['fundamentals_unavailable'],
      proxyQuality: {
        ...fixture.themes[0].proxyQuality,
        label: 'ETF 代理部分可用',
        coveragePercent: 50,
        availableProxyCount: 2,
        totalProxyCount: 4,
        freshness: 'stale',
        hasMissingRequiredProxy: true,
        hasStaleProxy: true,
        missingReasons: {
          IWM: 'proxy_stale',
          IGV: 'proxy_quote_missing',
        },
        explanation: 'ETF 代理部分可用：ETF 代理覆盖 2/4，缺口 IWM/IGV。',
      },
      benchmarkProxies: {
        ...fixture.themes[0].benchmarkProxies,
        IWM: {
          ...fixture.themes[0].benchmarkProxies?.IWM,
          symbol: 'IWM',
          freshness: 'stale',
          isStale: true,
          quality: {
            available: false,
            freshness: 'stale',
            missingReason: 'proxy_stale',
            qualityLabel: '代理过期',
            coverageContribution: 0,
          },
        },
        IGV: {
          ...fixture.themes[0].benchmarkProxies?.IGV,
          symbol: 'IGV',
          freshness: 'fallback',
          isFallback: true,
          quality: {
            available: false,
            freshness: 'fallback',
            missingReason: 'proxy_quote_missing',
            qualityLabel: '代理缺口',
            coverageContribution: 0,
          },
        },
      },
    };
    vi.mocked(marketRotationApi.getRotationRadar).mockResolvedValueOnce(fixture);

    render(<MarketRotationRadarPage />);

    const detail = await screen.findByTestId('rotation-theme-detail-panel');
    const quality = within(detail).getByTestId('rotation-proxy-quality-summary-ai_applications');
    expect(quality).toHaveTextContent('覆盖 2/4');
    expect(quality).toHaveTextContent('50.0%');
    expect(quality).toHaveTextContent('过期');
    expect(quality).toHaveTextContent('代理缺口');

    expect(screen.queryByTestId('rotation-proxy-row-IWM')).not.toBeInTheDocument();
    expect(screen.queryByText('schemaVersion')).not.toBeInTheDocument();
    expect(screen.queryByText('/api/v1/market/rotation-radar')).not.toBeInTheDocument();
    expect(screen.queryByText('proxy_quote_missing')).not.toBeInTheDocument();
    expect(screen.queryByText('proxy_stale')).not.toBeInTheDocument();
    expect(screen.getByText('部分外部数据暂不可用')).toBeInTheDocument();
    expect(document.body.textContent || '').toMatch(/历史数据不足|技术指标数据不足|基本面数据缺失/);

    const proxyDetails = within(detail).getByTestId('rotation-theme-proxy-details-ai_applications');
    expect(proxyDetails).toHaveAttribute('data-terminal-primitive', 'disclosure');
    expect(proxyDetails).not.toHaveAttribute('open');
    fireEvent.click(within(proxyDetails).getByRole('button', { name: '展开 数据诊断' }));
    expect(within(proxyDetails).getByTestId('rotation-proxy-row-IWM')).toBeInTheDocument();
    expect(within(proxyDetails).getByTestId('rotation-proxy-row-IGV')).toBeInTheDocument();
    expect(screen.queryByTestId('rotation-radar-developer-details')).not.toBeInTheDocument();
    expect(document.body.textContent || '').not.toMatch(/开发者|Developer|schemaVersion|provider_payload|raw_payload|debug|trace/i);
  });

  it('renders derived rotation buckets and collapsed page mechanics', async () => {
    render(<MarketRotationRadarPage />);

    await screen.findByTestId('market-rotation-radar-page');
    const buckets = screen.getByTestId('rotation-radar-buckets');
    expect(buckets).toHaveTextContent('新近走强');
    expect(buckets).toHaveTextContent('走弱降温');
    expect(buckets).toHaveTextContent('广泛参与');
    expect(buckets).toHaveTextContent('窄幅龙头');

    const mechanics = screen.getByTestId('rotation-radar-mechanics-details');
    expect(mechanics).toHaveAttribute('data-terminal-primitive', 'disclosure');
    expect(mechanics).toHaveTextContent('证据边界 / 来源说明');
    expect(mechanics).not.toHaveAttribute('open');
    expect(screen.queryByText('不代表实时方向结论，不触发交易、通知、组合或新的外部数据请求。')).not.toBeInTheDocument();
    fireEvent.click(within(mechanics).getByRole('button', { name: '展开 证据边界 / 来源说明' }));
    expect(screen.getByText('不代表实时方向结论，不触发交易、通知、组合或新的外部数据请求。')).toBeInTheDocument();
    expect(mechanics).not.toHaveTextContent('schemaVersion');
  });
});
