import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import LiquidityMonitorPage from '../LiquidityMonitorPage';

const { getLiquidityMonitor, useProductSurfaceMock } = vi.hoisted(() => ({
  getLiquidityMonitor: vi.fn(),
  useProductSurfaceMock: vi.fn(),
}));

vi.mock('../../api/liquidityMonitor', () => ({
  liquidityMonitorApi: {
    getLiquidityMonitor,
  },
}));

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: 'zh',
    t: (key: string) => key,
  }),
}));

vi.mock('../../hooks/useProductSurface', () => ({
  useProductSurface: useProductSurfaceMock,
}));

const payload = {
  endpoint: '/api/v1/market/liquidity-monitor',
  generatedAt: '2026-05-07T10:00:00+08:00',
  score: {
    value: 69,
    regime: 'supportive',
    confidence: 0.44,
    includedIndicatorCount: 3,
    possibleIndicatorWeight: 43,
    includedIndicatorWeight: 19,
  },
  freshness: {
    status: 'delayed',
    weakestIndicatorFreshness: 'delayed',
    latestAsOf: '2026-05-07T10:00:00+08:00',
  },
  indicators: [
    {
      key: 'vix_pressure',
      label: 'VIX / 波动率压力',
      status: 'live',
      freshness: 'live',
      includedInScore: true,
      scoreContribution: 8,
      scoreWeight: 8,
      summary: '均值 -2.50%',
      updatedAt: '2026-05-07T10:00:00+08:00',
      evidence: {
        contractVersion: 'source_confidence_contract_v1',
        source: 'fred',
        sourceLabel: 'Official macro',
        asOf: '2026-05-07T10:00:00+08:00',
        freshness: 'live',
        isFallback: false,
        isStale: false,
        isPartial: false,
        isUnavailable: false,
        coverage: 1,
        confidenceWeight: 1,
        inputs: [
          {
            key: 'VIX',
            label: 'VIX',
            source: 'fred',
            sourceLabel: 'FRED VIXCLS',
            sourceType: 'official_public',
            sourceTier: 'official_public',
            trustLevel: 'reliable',
            asOf: '2026-05-07T10:00:00+08:00',
            freshness: 'live',
            isFallback: false,
            isStale: false,
            isPartial: false,
            isUnavailable: false,
            observationOnly: false,
            sourceAuthorityAllowed: true,
            scoreContributionAllowed: true,
            sourceAuthorityReason: null,
            sourceAuthorityRouteRejected: false,
            routeRejectedReasonCodes: [],
            officialSeriesId: 'VIXCLS',
            officialObservationDate: '2026-05-06',
            officialAsOf: '2026-05-06',
            confidenceWeight: 1,
          },
        ],
      },
      coverageDiagnostics: {
        indicatorId: 'vix_pressure',
        indicatorName: 'VIX / 波动率压力',
        requiredInputs: ['VIX'],
        fulfilledInputs: ['VIX'],
        missingInputs: [],
        requiredProviderClass: 'official_public.vix_or_volatility',
        configuredProviderAvailable: true,
        realSourceAvailable: true,
        proxyOnly: false,
        observationOnly: false,
        scoreContributionAllowed: true,
        scoreExclusionReason: null,
        requiredRealSourceForScore: true,
        proxyObservationOnlyReason: null,
        missingProviderReason: null,
        paidDataLikelyRequired: false,
        sourceTier: 'official_public',
        freshness: 'live',
        trustLevel: 'reliable',
        contributesToScore: true,
        scoreContribution: 8,
        capReason: null,
        degradationReason: null,
        sourceAuthorityRouteRejected: false,
        sourceAuthorityReason: null,
        routeRejectedReasonCodes: [],
      },
    },
    {
      key: 'us_rates_pressure',
      label: 'US Rates / 利率压力',
      status: 'partial',
      freshness: 'fallback',
      includedInScore: false,
      scoreContribution: 0,
      scoreWeight: 10,
      summary: '官方曲线缺口，当前仅保留受限快照',
      updatedAt: '2026-05-07T10:00:00+08:00',
      evidence: {
        contractVersion: 'source_confidence_contract_v1',
        source: 'mixed',
        sourceLabel: 'Macro rates context',
        asOf: '2026-05-07T10:00:00+08:00',
        freshness: 'partial',
        isFallback: true,
        isStale: false,
        isPartial: true,
        isUnavailable: false,
        coverage: 0.66,
        confidenceWeight: 0.45,
        inputs: [
          {
            key: 'SOFR',
            label: 'SOFR',
            source: 'fred',
            sourceLabel: 'FRED SOFR',
            sourceType: 'official_public',
            sourceTier: 'official_public',
            trustLevel: 'reliable',
            asOf: '2026-05-07T10:00:00+08:00',
            freshness: 'cached',
            isFallback: false,
            isStale: false,
            isPartial: false,
            isUnavailable: false,
            observationOnly: false,
            sourceAuthorityAllowed: true,
            scoreContributionAllowed: true,
            sourceAuthorityReason: null,
            sourceAuthorityRouteRejected: false,
            routeRejectedReasonCodes: [],
            officialSeriesId: 'SOFR',
            officialObservationDate: '2026-05-06',
            officialAsOf: '2026-05-06',
            confidenceWeight: 1,
          },
          {
            key: 'DFF',
            label: 'Fed Funds Effective Rate',
            source: 'proxy',
            sourceLabel: 'Proxy money-market context',
            sourceType: 'public_proxy',
            sourceTier: 'unofficial_public_api',
            trustLevel: 'usable_with_caution',
            asOf: '2026-05-07T10:00:00+08:00',
            freshness: 'fallback',
            isFallback: true,
            isStale: false,
            isPartial: true,
            isUnavailable: false,
            observationOnly: false,
            sourceAuthorityAllowed: false,
            scoreContributionAllowed: false,
            sourceAuthorityReason: 'proxy_context_only',
            sourceAuthorityRouteRejected: false,
            routeRejectedReasonCodes: [],
            officialSeriesId: 'DFF',
            officialObservationDate: null,
            officialAsOf: null,
            confidenceWeight: 0.2,
          },
          {
            key: 'US2Y',
            label: 'US 2Y',
            source: 'treasury',
            sourceLabel: 'Treasury DGS2',
            sourceType: 'official_public',
            sourceTier: 'official_public',
            trustLevel: 'reliable',
            asOf: '2026-05-07T10:00:00+08:00',
            freshness: 'cached',
            isFallback: false,
            isStale: false,
            isPartial: false,
            isUnavailable: false,
            observationOnly: false,
            sourceAuthorityAllowed: true,
            scoreContributionAllowed: true,
            sourceAuthorityReason: null,
            sourceAuthorityRouteRejected: false,
            routeRejectedReasonCodes: [],
            officialSeriesId: 'DGS2',
            officialObservationDate: '2026-05-06',
            officialAsOf: '2026-05-06',
            confidenceWeight: 1,
          },
          {
            key: 'US10Y',
            label: 'US 10Y',
            source: 'treasury',
            sourceLabel: 'Treasury DGS10',
            sourceType: 'official_public',
            sourceTier: 'official_public',
            trustLevel: 'reliable',
            asOf: '2026-05-07T10:00:00+08:00',
            freshness: 'cached',
            isFallback: false,
            isStale: false,
            isPartial: false,
            isUnavailable: false,
            observationOnly: false,
            sourceAuthorityAllowed: true,
            scoreContributionAllowed: true,
            sourceAuthorityReason: null,
            sourceAuthorityRouteRejected: false,
            routeRejectedReasonCodes: [],
            officialSeriesId: 'DGS10',
            officialObservationDate: '2026-05-06',
            officialAsOf: '2026-05-06',
            confidenceWeight: 1,
          },
          {
            key: 'US30Y',
            label: 'US 30Y',
            source: 'unavailable',
            sourceLabel: 'Treasury DGS30 unavailable',
            sourceType: 'official_public',
            sourceTier: 'official_public',
            trustLevel: 'unavailable',
            asOf: '2026-05-07T10:00:00+08:00',
            freshness: 'unavailable',
            isFallback: false,
            isStale: false,
            isPartial: false,
            isUnavailable: true,
            observationOnly: false,
            sourceAuthorityAllowed: false,
            scoreContributionAllowed: false,
            sourceAuthorityReason: 'source_authority_router_rejected',
            sourceAuthorityRouteRejected: true,
            routeRejectedReasonCodes: ['provider_forbidden_for_use_case'],
            officialSeriesId: 'DGS30',
            officialObservationDate: null,
            officialAsOf: null,
            confidenceWeight: 0,
          },
        ],
      },
      coverageDiagnostics: {
        indicatorId: 'us_rates_pressure',
        indicatorName: 'US Rates / 利率压力',
        requiredInputs: ['SOFR', 'DFF', 'US2Y', 'US10Y', 'US30Y'],
        fulfilledInputs: ['SOFR', 'US2Y', 'US10Y'],
        missingInputs: ['DFF', 'US30Y'],
        requiredProviderClass: 'official_public.us_treasury_curve',
        configuredProviderAvailable: true,
        realSourceAvailable: true,
        proxyOnly: false,
        observationOnly: false,
        scoreContributionAllowed: false,
        scoreExclusionReason: 'partial_coverage',
        requiredRealSourceForScore: true,
        proxyObservationOnlyReason: null,
        missingProviderReason: null,
        paidDataLikelyRequired: false,
        sourceTier: 'official_public',
        freshness: 'partial',
        trustLevel: 'usable_with_caution',
        contributesToScore: false,
        scoreContribution: 0,
        capReason: 'partial_coverage',
        degradationReason: 'partial_coverage',
        sourceAuthorityRouteRejected: false,
        sourceAuthorityReason: null,
        routeRejectedReasonCodes: [],
      },
    },
    {
      key: 'crypto_funding',
      label: 'Crypto Funding',
      status: 'unavailable',
      freshness: 'fallback',
      includedInScore: false,
      scoreContribution: 0,
      scoreWeight: 0,
      summary: '仅在真实 funding 快照存在时显示',
      updatedAt: '2026-05-07T10:00:00+08:00',
    },
    {
      key: 'credit_spread',
      label: 'Credit / 信用利差',
      status: 'partial',
      freshness: 'cached',
      includedInScore: false,
      scoreContribution: 0,
      scoreWeight: 4,
      summary: '官方利差仅作观察，不直接计分',
      updatedAt: '2026-05-07T10:00:00+08:00',
      evidence: {
        contractVersion: 'source_confidence_contract_v1',
        source: 'fred',
        sourceLabel: 'FRED credit spread',
        asOf: '2026-05-07T10:00:00+08:00',
        freshness: 'cached',
        isFallback: false,
        isStale: false,
        isPartial: false,
        isUnavailable: false,
        coverage: 1,
        confidenceWeight: 0.35,
        inputs: [
          {
            key: 'CREDIT',
            label: 'Credit spreads',
            source: 'fred',
            sourceLabel: 'FRED BAMLH0A0HYM2',
            sourceType: 'official_public',
            sourceTier: 'official_public',
            trustLevel: 'reliable',
            asOf: '2026-05-07T10:00:00+08:00',
            freshness: 'cached',
            isFallback: false,
            isStale: false,
            isPartial: false,
            isUnavailable: false,
            observationOnly: true,
            sourceAuthorityAllowed: true,
            scoreContributionAllowed: false,
            sourceAuthorityReason: null,
            sourceAuthorityRouteRejected: false,
            routeRejectedReasonCodes: [],
            officialSeriesId: 'BAMLH0A0HYM2',
            officialObservationDate: '2026-05-06',
            officialAsOf: '2026-05-06',
            confidenceWeight: 0.35,
          },
        ],
      },
      coverageDiagnostics: {
        indicatorId: 'credit_spread',
        indicatorName: 'Credit / 信用利差',
        requiredInputs: ['CREDIT'],
        fulfilledInputs: ['CREDIT'],
        missingInputs: [],
        requiredProviderClass: 'official_public.credit_spread',
        configuredProviderAvailable: true,
        realSourceAvailable: true,
        proxyOnly: false,
        observationOnly: true,
        scoreContributionAllowed: false,
        scoreExclusionReason: 'observation_only',
        requiredRealSourceForScore: false,
        proxyObservationOnlyReason: null,
        missingProviderReason: null,
        paidDataLikelyRequired: false,
        sourceTier: 'official_public',
        freshness: 'cached',
        trustLevel: 'reliable',
        contributesToScore: false,
        scoreContribution: 0,
        capReason: null,
        degradationReason: null,
        sourceAuthorityRouteRejected: false,
        sourceAuthorityReason: null,
        routeRejectedReasonCodes: [],
      },
    },
  ],
  liquidityImpulseSynthesis: {
    liquidityImpulse: 'contracting_liquidity',
    impulseLabel: 'Liquidity appears to be contracting',
    subtype: 'rates_driven_tightening',
    confidence: 0.71,
    confidenceLabel: 'high',
    pillarScores: {
      rates_pressure: 0.63,
      dollar_pressure: 0.42,
      volatility_stress: 0.51,
    },
    directionScore: -0.58,
    dominantDrivers: [
      {
        key: 'liquidity_monitor:us_rates_pressure',
        label: 'US Rates / 利率压力',
        pillar: 'rates_pressure',
        direction: 'supports_contraction',
        signal: 0.63,
        impact: 0.58,
        source: 'treasury',
        scoreContributionAllowed: true,
      },
      {
        key: 'liquidity_monitor:usd_pressure',
        label: 'USD / 美元压力',
        pillar: 'dollar_pressure',
        direction: 'supports_contraction',
        signal: 0.42,
        impact: 0.31,
        source: 'fred',
        scoreContributionAllowed: true,
      },
    ],
    counterEvidence: [
      {
        key: 'liquidity_monitor:btc_momentum',
        label: 'BTC 动量',
        pillar: 'crypto_liquidity_beta',
        reason: 'conflicts_with_primary_regime',
        signal: -0.22,
        source: 'binance',
      },
    ],
    dataGaps: [
      {
        key: 'liquidity_monitor:cn_hk_flows',
        label: 'CN/HK Flows',
        pillar: 'china_liquidity_context',
        reason: 'score_contribution_not_allowed',
        source: 'unavailable',
        scoreContributionAllowed: false,
      },
    ],
    narrativeBullets: ['Rates and dollar pressure are dominating the current liquidity signal.'],
    evidenceQuality: {
      scoringEvidenceCount: 2,
      scoringPillarCount: 2,
      discountedEvidenceCount: 0,
      dataGapCount: 1,
      proxyOnlyScoringCount: 0,
      realScoringEvidenceCount: 2,
      allScoringEvidenceProxyOnly: false,
    },
    notInvestmentAdvice: true,
  },
  advisoryDisclosure: '仅用于观察市场流动性环境，非投资建议，不触发扫描、回测或组合动作。',
  sourceMetadata: {
    externalProviderCalls: false,
    providerRuntimeChanged: false,
    marketCacheMutation: false,
  },
};

const officialBreadthIndicator = {
  key: 'us_breadth_proxy',
  label: 'US 广度代理',
  status: 'live',
  freshness: 'delayed',
  includedInScore: true,
  scoreContribution: 6,
  scoreWeight: 6,
  summary: '7000/4000 | NH/NL 318/42',
  updatedAt: '2026-05-21T16:00:00+08:00',
  evidence: {
    contractVersion: 'source_confidence_contract_v1',
    source: 'nyse_official_breadth',
    sourceLabel: 'NYSE Official Breadth Cache',
    asOf: '2026-05-21T16:00:00+08:00',
    freshness: 'delayed',
    isFallback: false,
    isStale: false,
    isPartial: false,
    isUnavailable: false,
    coverage: 1,
    confidenceWeight: 1,
    inputs: [
      { key: 'ADVANCERS', label: 'Advancers', source: 'nyse_official_breadth', sourceLabel: 'NYSE breadth', sourceType: 'official_public', sourceTier: 'official_public', freshness: 'delayed', observationOnly: false, sourceAuthorityAllowed: true, scoreContributionAllowed: true },
      { key: 'DECLINERS', label: 'Decliners', source: 'nyse_official_breadth', sourceLabel: 'NYSE breadth', sourceType: 'official_public', sourceTier: 'official_public', freshness: 'delayed', observationOnly: false, sourceAuthorityAllowed: true, scoreContributionAllowed: true },
      { key: 'UNCHANGED', label: 'Unchanged', source: 'nyse_official_breadth', sourceLabel: 'NYSE breadth', sourceType: 'official_public', sourceTier: 'official_public', freshness: 'delayed', observationOnly: false, sourceAuthorityAllowed: true, scoreContributionAllowed: true },
      { key: 'ADVANCE_DECLINE_RATIO', label: 'Advance/Decline ratio', source: 'nyse_official_breadth', sourceLabel: 'NYSE breadth', sourceType: 'official_public', sourceTier: 'official_public', freshness: 'delayed', observationOnly: false, sourceAuthorityAllowed: true, scoreContributionAllowed: true },
      { key: 'NEW_HIGHS', label: 'New highs', source: 'nyse_official_breadth', sourceLabel: 'NYSE breadth', sourceType: 'official_public', sourceTier: 'official_public', freshness: 'delayed', observationOnly: false, sourceAuthorityAllowed: true, scoreContributionAllowed: true },
      { key: 'NEW_LOWS', label: 'New lows', source: 'nyse_official_breadth', sourceLabel: 'NYSE breadth', sourceType: 'official_public', sourceTier: 'official_public', freshness: 'delayed', observationOnly: false, sourceAuthorityAllowed: true, scoreContributionAllowed: true },
      { key: 'HIGH_LOW_RATIO', label: 'High/Low ratio', source: 'nyse_official_breadth', sourceLabel: 'NYSE breadth', sourceType: 'official_public', sourceTier: 'official_public', freshness: 'delayed', observationOnly: false, sourceAuthorityAllowed: true, scoreContributionAllowed: true },
    ],
  },
  coverageDiagnostics: {
    indicatorId: 'us_breadth_proxy',
    indicatorName: 'US 广度代理',
    requiredInputs: ['ADVANCERS', 'DECLINERS', 'UNCHANGED', 'ADVANCE_DECLINE_RATIO', 'NEW_HIGHS', 'NEW_LOWS', 'HIGH_LOW_RATIO'],
    fulfilledInputs: ['ADVANCERS', 'DECLINERS', 'UNCHANGED', 'ADVANCE_DECLINE_RATIO', 'NEW_HIGHS', 'NEW_LOWS', 'HIGH_LOW_RATIO'],
    missingInputs: [],
    requiredProviderClass: 'official_or_authorized.us_market_breadth',
    configuredProviderAvailable: true,
    realSourceAvailable: true,
    proxyOnly: false,
    observationOnly: false,
    scoreContributionAllowed: true,
    scoreExclusionReason: null,
    requiredRealSourceForScore: true,
    proxyObservationOnlyReason: null,
    missingProviderReason: null,
    paidDataLikelyRequired: false,
    sourceTier: 'official_public',
    freshness: 'delayed',
    trustLevel: 'reliable',
    contributesToScore: true,
    scoreContribution: 6,
    capReason: null,
    degradationReason: null,
    sourceAuthorityRouteRejected: false,
    sourceAuthorityReason: null,
    routeRejectedReasonCodes: [],
  },
};

const degradedBreadthIndicator = {
  key: 'us_breadth_proxy',
  label: 'US 广度代理',
  status: 'partial',
  freshness: 'stale',
  includedInScore: false,
  scoreContribution: 0,
  scoreWeight: 6,
  summary: '8/3 | RSP/SPY +1.20%',
  updatedAt: '2026-05-21T16:00:00+08:00',
  evidence: {
    contractVersion: 'source_confidence_contract_v1',
    source: 'yfinance_proxy',
    sourceLabel: 'Yahoo Finance',
    asOf: '2026-05-21T16:00:00+08:00',
    freshness: 'partial',
    isFallback: false,
    isStale: true,
    isPartial: true,
    isUnavailable: false,
    coverage: 0.4,
    confidenceWeight: 0.7,
    degradationReason: 'partial_coverage',
    capReason: 'partial_coverage',
    inputs: [
      { key: 'SECTORS_UP', label: 'Sectors Up', source: 'yfinance_proxy', sourceLabel: 'Yahoo Finance', sourceType: 'unofficial_proxy', sourceTier: 'unofficial_proxy', freshness: 'stale', observationOnly: true, sourceAuthorityAllowed: false, scoreContributionAllowed: false },
      { key: 'SECTORS_DOWN', label: 'Sectors Down', source: 'yfinance_proxy', sourceLabel: 'Yahoo Finance', sourceType: 'unofficial_proxy', sourceTier: 'unofficial_proxy', freshness: 'stale', observationOnly: true, sourceAuthorityAllowed: false, scoreContributionAllowed: false },
    ],
  },
  coverageDiagnostics: {
    indicatorId: 'us_breadth_proxy',
    indicatorName: 'US 广度代理',
    requiredInputs: ['SECTORS_UP', 'SECTORS_DOWN', 'RSP_SPY', 'IWM_SPY', 'QQQ_SPY'],
    fulfilledInputs: ['SECTORS_UP', 'SECTORS_DOWN'],
    missingInputs: ['RSP_SPY', 'IWM_SPY', 'QQQ_SPY'],
    requiredProviderClass: 'official_or_authorized.us_market_breadth',
    configuredProviderAvailable: true,
    realSourceAvailable: false,
    proxyOnly: true,
    observationOnly: false,
    scoreContributionAllowed: false,
    scoreExclusionReason: 'proxy_only_missing_real_source',
    requiredRealSourceForScore: true,
    proxyObservationOnlyReason: 'proxy_only_missing_real_source',
    missingProviderReason: 'requires_official_or_authorized.us_market_breadth',
    paidDataLikelyRequired: true,
    sourceTier: 'unofficial_public_api',
    freshness: 'stale',
    trustLevel: 'usable_with_caution',
    contributesToScore: false,
    scoreContribution: 0,
    capReason: 'partial_coverage',
    degradationReason: 'partial_coverage',
    sourceAuthorityRouteRejected: false,
    sourceAuthorityReason: 'representative_sample_not_full_market_breadth',
    routeRejectedReasonCodes: ['representative_sample_not_full_market_breadth'],
  },
};

function withBreadthIndicator(indicator: Record<string, unknown>) {
  return {
    ...payload,
    indicators: [
      indicator,
      ...payload.indicators.filter((item) => item.key !== 'us_breadth_proxy'),
    ],
  };
}

describe('LiquidityMonitorPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: false,
      canReadProviders: false,
    });
  });

  async function expandLiquidityDetails(): Promise<HTMLElement> {
    const disclosure = await screen.findByTestId('liquidity-monitor-admin-details');
    fireEvent.click(within(disclosure).getByRole('button', { name: '展开 技术细节' }));
    return disclosure;
  }

  it('renders a consumer-safe first-screen summary and hides technical diagnostics by default', async () => {
    getLiquidityMonitor.mockResolvedValueOnce(payload);

    render(<LiquidityMonitorPage />);

    expect(await screen.findByRole('heading', { name: '流动性监测' })).toBeInTheDocument();
    const pageShell = screen.getByRole('heading', { name: '流动性监测' }).closest('[data-terminal-primitive="page-shell"]');
    expect(pageShell).toHaveAttribute('data-workspace-width', 'near-full');
    expect(pageShell).toHaveClass('max-w-[1840px]');
    const guidancePanel = screen.getByTestId('liquidity-monitor-guidance-panel');
    expect(guidancePanel).toHaveTextContent('流动性状态');
    expect(guidancePanel).toHaveTextContent('部分可用');
    expect(guidancePanel).toHaveTextContent('评分状态');
    expect(guidancePanel).toHaveTextContent('评分已暂停');
    expect(guidancePanel).toHaveTextContent('数据更新');
    expect(guidancePanel).toHaveTextContent('当前流动性信号置信度较低，仅供观察。');
    expect(screen.getAllByText('延迟').length).toBeGreaterThan(0);
    expect(screen.getByText('仅用于观察市场流动性环境，非投资建议，不触发扫描、回测或组合动作。')).toBeInTheDocument();
    expect(screen.queryByTestId('liquidity-monitor-admin-details')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '展开 技术细节' })).not.toBeInTheDocument();
    expect(screen.queryByTestId('liquidity-impulse-synthesis-header')).not.toBeInTheDocument();
    expect(guidancePanel.textContent || '').not.toMatch(
      /provider_unavailable|fallback_source|score_contribution_not_allowed|sourceAuthorityAllowed|scoreContributionAllowed|observationOnly|routeRejectedReasonCodes|外部调用|运行顺序|缓存写入|来源覆盖诊断|来源与约束|查看提供方覆盖|前往数据源设置/i,
    );
  });

  it('renders the liquidity impulse synthesis header with evidence rows inside admin details', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: true,
      canReadProviders: true,
    });
    getLiquidityMonitor.mockResolvedValueOnce(payload);

    render(<LiquidityMonitorPage />);

    await screen.findByRole('heading', { name: '流动性监测' });
    await screen.findByTestId('liquidity-monitor-admin-details');
    const details = await expandLiquidityDetails();
    expect(within(details).getByTestId('liquidity-impulse-synthesis-header')).toBeInTheDocument();
    expect(within(details).getByTestId('liquidity-impulse-synthesis-title')).toHaveTextContent('流动性收缩');
    expect(within(details).getByTestId('liquidity-impulse-synthesis-subtype-chip')).toHaveTextContent('利率驱动收紧');
    expect(within(details).getByTestId('liquidity-impulse-synthesis-confidence-chip')).toHaveTextContent('高');
    expect(within(details).getByTestId('liquidity-impulse-synthesis-direction-chip')).toHaveTextContent('-0.58');
    expect(within(details).getByTestId('liquidity-impulse-synthesis-dominant-drivers')).toHaveTextContent('美国利率压力');
    expect(within(details).getByTestId('liquidity-impulse-synthesis-counter-evidence')).toHaveTextContent('BTC 动量');
    expect(within(details).getByTestId('liquidity-impulse-synthesis-data-gaps')).toHaveTextContent('中港资金流');
  });

  it('renders a compact consumer summary without backend diagnostic wording', async () => {
    getLiquidityMonitor.mockResolvedValueOnce(payload);

    render(<LiquidityMonitorPage />);

    const guidancePanel = await screen.findByTestId('liquidity-monitor-guidance-panel');
    expect(guidancePanel).toHaveTextContent('部分流动性数据暂不可用，当前评分已暂停。');
    expect(guidancePanel).toHaveTextContent('当前受限模块');
    expect(guidancePanel).toHaveTextContent('最近更新');
    expect(guidancePanel).toHaveTextContent('美国利率压力');
    expect(guidancePanel).toHaveTextContent('Crypto 资金费率');
    expect(guidancePanel.textContent || '').not.toMatch(
      /score_contribution_not_allowed|source_authority_router_rejected|provider_unavailable|fallback_source|sourceAuthorityAllowed|scoreContributionAllowed|Liquidity Regime Gauge|Proxy-only/i,
    );
  });

  it('renders consumer-safe paused and unavailable states without provider remediation CTAs', async () => {
    getLiquidityMonitor.mockResolvedValueOnce(payload);
    const readyView = render(<LiquidityMonitorPage />);

    await waitFor(() => expect(screen.getByTestId('liquidity-decision-readiness')).toHaveTextContent('评分已暂停'));
    const resolvedReadyBand = screen.getByTestId('liquidity-decision-readiness');
    expect(resolvedReadyBand).toHaveTextContent('流动性状态');
    expect(resolvedReadyBand).toHaveTextContent('当前流动性信号置信度较低，仅供观察。');
    expect(resolvedReadyBand).not.toHaveTextContent('阻塞项');
    expect(resolvedReadyBand).not.toHaveTextContent('提升证据');
    expect(within(resolvedReadyBand).queryByText('查看提供方覆盖')).not.toBeInTheDocument();
    expect(within(resolvedReadyBand).queryByText('前往数据源设置')).not.toBeInTheDocument();
    expect(resolvedReadyBand.textContent || '').not.toMatch(/买入|卖出|buy now|sell now|recommend/i);
    readyView.unmount();

    getLiquidityMonitor.mockResolvedValueOnce({
      ...payload,
      liquidityImpulseSynthesis: {
        ...payload.liquidityImpulseSynthesis,
        liquidityImpulse: 'expanding_liquidity',
        impulseLabel: 'Liquidity appears to be expanding',
        subtype: 'crypto_beta_expansion',
        confidence: 0.33,
        confidenceLabel: 'low',
        dominantDrivers: [
          {
            key: 'liquidity_monitor:btc',
            label: 'BTC',
            pillar: 'crypto_liquidity_beta',
            direction: 'supports_expansion',
            signal: 0.44,
            impact: 0.22,
            source: 'coinbase',
            proxyOnly: true,
            scoreContributionAllowed: false,
            observationOnly: true,
          },
        ],
        counterEvidence: [],
        dataGaps: [],
        evidenceQuality: {
          scoringEvidenceCount: 1,
          scoringPillarCount: 1,
          discountedEvidenceCount: 1,
          dataGapCount: 0,
          proxyOnlyScoringCount: 1,
          realScoringEvidenceCount: 0,
          allScoringEvidenceProxyOnly: true,
        },
      },
    });

    const observationView = render(<LiquidityMonitorPage />);
    await screen.findByTestId('liquidity-decision-readiness');
    await waitFor(() => expect(screen.getByTestId('liquidity-decision-readiness')).toHaveTextContent('评分已暂停'));
    const observationBand = screen.getByTestId('liquidity-decision-readiness');
    expect(observationBand).toHaveTextContent('当前流动性信号置信度较低，仅供观察。');
    expect(observationBand).not.toHaveTextContent('代理证据不能升级方向');
    expect(observationBand).not.toHaveTextContent('提供方');
    expect(observationBand).not.toHaveTextContent('数据源设置');
    expect(observationBand.textContent || '').not.toMatch(/买入|卖出|下单|立即交易|稳赚|保证收益|recommend|investment|profit|guarantee/i);
    observationView.unmount();

    getLiquidityMonitor.mockResolvedValueOnce({
      ...payload,
      score: {
        ...payload.score,
        value: 0,
        regime: 'unavailable',
        confidence: 0,
        includedIndicatorCount: 0,
        includedIndicatorWeight: 0,
      },
      indicators: payload.indicators.map((indicator) => ({
        ...indicator,
        status: 'unavailable',
        freshness: 'unavailable',
        includedInScore: false,
        scoreContribution: 0,
        coverageDiagnostics: {
          ...(indicator.coverageDiagnostics || {
            indicatorId: indicator.key,
            indicatorName: indicator.label,
            requiredInputs: [],
            fulfilledInputs: [],
            missingInputs: [],
          }),
          configuredProviderAvailable: false,
          realSourceAvailable: false,
          scoreContributionAllowed: false,
          scoreExclusionReason: 'provider_unavailable',
          missingInputs: ['required_source'],
        },
      })),
      liquidityImpulseSynthesis: {
        ...payload.liquidityImpulseSynthesis,
        liquidityImpulse: 'data_insufficient',
        confidence: 0,
        confidenceLabel: 'insufficient',
        dominantDrivers: [],
        counterEvidence: [],
        dataGaps: [
          {
            key: 'liquidity_monitor:funding',
            label: 'Funding',
            reason: 'provider_unavailable',
            scoreContributionAllowed: false,
          },
        ],
        evidenceQuality: {
          scoringEvidenceCount: 0,
          scoringPillarCount: 0,
          discountedEvidenceCount: 0,
          dataGapCount: 1,
        },
      },
    });

    render(<LiquidityMonitorPage />);
    await screen.findByTestId('liquidity-decision-readiness');
    await waitFor(() => expect(screen.getByTestId('liquidity-decision-readiness')).toHaveTextContent('本模块暂不可用，请稍后重试。'));
    const unavailableBand = screen.getByTestId('liquidity-decision-readiness');
    expect(unavailableBand).toHaveTextContent('本模块暂不可用，请稍后重试。');
    expect(unavailableBand).toHaveTextContent('评分已暂停');
    expect(unavailableBand).not.toHaveTextContent('数据源不可用');
    expect(unavailableBand).not.toHaveTextContent('Provider unavailable');
    expect(unavailableBand).not.toHaveTextContent('前往数据源设置');
  });

  it('renders admin-only technical diagnostics when provider readers open the disclosure', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: true,
      canReadProviders: true,
    });
    getLiquidityMonitor.mockResolvedValueOnce({
      ...payload,
      liquidityImpulseSynthesis: {
        ...payload.liquidityImpulseSynthesis,
        liquidityImpulse: 'expanding_liquidity',
        impulseLabel: 'Liquidity appears to be expanding',
        subtype: 'crypto_beta_expansion',
        confidence: 0.33,
        confidenceLabel: 'low',
        dominantDrivers: [
          {
            key: 'liquidity_monitor:btc',
            label: 'BTC',
            pillar: 'crypto_liquidity_beta',
            direction: 'supports_expansion',
            signal: 0.44,
            impact: 0.22,
            source: 'coinbase',
            proxyOnly: true,
            scoreContributionAllowed: false,
            observationOnly: true,
          },
        ],
        counterEvidence: [],
        dataGaps: [],
        evidenceQuality: {
          scoringEvidenceCount: 1,
          scoringPillarCount: 1,
          discountedEvidenceCount: 1,
          dataGapCount: 0,
          proxyOnlyScoringCount: 1,
          realScoringEvidenceCount: 0,
          allScoringEvidenceProxyOnly: true,
        },
      },
    });

    render(<LiquidityMonitorPage />);

    const adminDetails = await screen.findByTestId('liquidity-monitor-admin-details');
    expect(adminDetails).not.toHaveAttribute('open');
    expect(screen.getByTestId('liquidity-regime-gauge')).toHaveTextContent('流动性刻度');

    await expandLiquidityDetails();
    const gauge = screen.getByTestId('liquidity-regime-gauge');
    expect(gauge).toHaveTextContent('流动性刻度');
    expect(gauge).toHaveTextContent('流动性状态：证据不足');
    expect(gauge).toHaveTextContent('刻度 69 / 100');
    expect(gauge).toHaveTextContent('趋势：未知');
    expect(gauge).toHaveTextContent('可用证据 1');
    expect(gauge).toHaveTextContent('缺失或阻塞 2');
    expect(gauge).toHaveTextContent('流动性证据不足');
    expect(gauge).toHaveTextContent('仅可作为观察背景');
    expect(gauge.textContent || '').not.toMatch(/买入|卖出|建议买入|建议卖出|buy now|sell now|recommend/i);
    expect(gauge.textContent || '').not.toMatch(/liquidityMonitor\./);
    expect(gauge.textContent || '').not.toMatch(/Liquidity Regime Gauge|Proxy-only/);
  });

  it('renders partial and unavailable indicators compactly inside admin details', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: true,
      canReadProviders: true,
    });
    getLiquidityMonitor.mockResolvedValueOnce(payload);

    render(<LiquidityMonitorPage />);

    await screen.findByRole('heading', { name: '流动性监测' });
    const indicatorDisclosure = await expandLiquidityDetails();
    expect(within(indicatorDisclosure).getAllByText('部分可用').length).toBeGreaterThan(0);
    expect(within(indicatorDisclosure).getByText('暂不可用')).toBeInTheDocument();
    expect(within(indicatorDisclosure).getByText('Crypto 资金费率')).toBeVisible();
    expect(within(indicatorDisclosure).getByText('仅在真实 funding 快照存在时显示')).toBeVisible();
  });

  it('shows compact official macro authority diagnostics for official, observation-only, fallback, and rejected rows', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: true,
      canReadProviders: true,
    });
    getLiquidityMonitor.mockResolvedValueOnce(payload);

    render(<LiquidityMonitorPage />);

    await screen.findByRole('heading', { name: '流动性监测' });
    const details = await expandLiquidityDetails();
    const diagnostics = within(details).getByTestId('liquidity-monitor-official-macro-diagnostics');
    expect(diagnostics).toHaveTextContent('可计分 4');
    expect(diagnostics).toHaveTextContent('官方 5');
    expect(diagnostics).toHaveTextContent('代理/观察 2');
    expect(diagnostics).toHaveTextContent('缺口 1');
    expect(within(diagnostics).queryByText(/provider_forbidden_for_use_case/, { selector: 'p' })).not.toBeInTheDocument();

    fireEvent.click(within(diagnostics).getByRole('button', { name: '展开 来源覆盖诊断' }));

    expect(diagnostics).toHaveTextContent('Official');
    expect(diagnostics).toHaveTextContent('Score-eligible');
    expect(diagnostics).toHaveTextContent('Observation-only');
    expect(diagnostics).toHaveTextContent('Fallback');
    expect(diagnostics).toHaveTextContent('Rejected');
    expect(diagnostics).toHaveTextContent('provider_forbidden_for_use_case');
    expect(diagnostics).toHaveTextContent('As-of 2026-05-06');
    expect(within(diagnostics).getByText(/provider_forbidden_for_use_case/, { selector: 'p' })).toBeVisible();
  });

  it('renders score-grade official breadth truth strips in the row and detail panel', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: true,
      canReadProviders: true,
    });
    getLiquidityMonitor.mockResolvedValueOnce(withBreadthIndicator(officialBreadthIndicator));

    render(<LiquidityMonitorPage />);

    await screen.findByRole('heading', { name: '流动性监测' });
    const details = await expandLiquidityDetails();
    const rowStrip = within(details).getByTestId('liquidity-breadth-truth-strip-row');
    expect(rowStrip).toHaveTextContent('评分级证据');
    expect(rowStrip).toHaveTextContent('官方宽度');
    expect(rowStrip).toHaveTextContent('延迟');
    expect(rowStrip).toHaveTextContent('覆盖 7/7');
    expect(rowStrip).toHaveTextContent('当前以官方宽度作为评分级宽度证据。');
    expect(rowStrip).toHaveTextContent('来源：NYSE Official Breadth Cache');
    expect(rowStrip).not.toHaveTextContent('仅观察');

    const breadthRow = within(details).getAllByText('美国市场广度')[0]?.closest('tr');
    expect(breadthRow).toBeTruthy();
    fireEvent.click(breadthRow!);

    const detailStrip = within(details).getByTestId('liquidity-breadth-truth-strip-detail');
    expect(detailStrip).toHaveTextContent('评分级证据');
    expect(detailStrip).toHaveTextContent('官方宽度');
    expect(detailStrip).toHaveTextContent('覆盖 7/7');
    expect(detailStrip.textContent || '').not.toMatch(/买入|卖出|加仓|减仓|buy|sell|recommend/i);
  });

  it('renders proxy breadth as observation-only with stale partial coverage gaps', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: true,
      canReadProviders: true,
    });
    getLiquidityMonitor.mockResolvedValueOnce(withBreadthIndicator(degradedBreadthIndicator));

    render(<LiquidityMonitorPage />);

    await screen.findByRole('heading', { name: '流动性监测' });
    const details = await expandLiquidityDetails();
    const rowStrip = within(details).getByTestId('liquidity-breadth-truth-strip-row');
    expect(rowStrip).toHaveTextContent('仅观察');
    expect(rowStrip).toHaveTextContent('代理宽度');
    expect(rowStrip).toHaveTextContent('过期');
    expect(rowStrip).toHaveTextContent('覆盖 2/5');
    expect(rowStrip).toHaveTextContent('当前仅展示代理宽度观察，不进入计分。');
    expect(rowStrip).toHaveTextContent('来源：Yahoo Finance');
    expect(rowStrip).toHaveTextContent('缺口：RSP/SPY、IWM/SPY、QQQ/SPY');
    expect(rowStrip).toHaveTextContent('限制：缺少官方/授权宽度主源；代表性样本，不等于全市场宽度');

    const breadthRow = within(details).getAllByText('美国市场广度')[0]?.closest('tr');
    expect(breadthRow).toBeTruthy();
    fireEvent.click(breadthRow!);

    const detailStrip = within(details).getByTestId('liquidity-breadth-truth-strip-detail');
    expect(detailStrip).toHaveTextContent('仅观察');
    expect(detailStrip).toHaveTextContent('代理宽度');
    expect(detailStrip).toHaveTextContent('过期');
    expect(detailStrip).toHaveTextContent('覆盖 2/5');
    expect(detailStrip.textContent || '').not.toMatch(/买入|卖出|加仓|减仓|buy|sell|recommend/i);
  });

  it('shows the selected indicator inspector and collapsed source details', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: true,
      canReadProviders: true,
    });
    getLiquidityMonitor.mockResolvedValueOnce(payload);

    render(<LiquidityMonitorPage />);

    await screen.findByRole('heading', { name: '流动性监测' });
    const details = await expandLiquidityDetails();
    expect(within(details).getAllByText('波动率压力').length).toBeGreaterThan(0);
    expect(within(details).getAllByText('均值 -2.50%').length).toBeGreaterThan(0);
    expect(within(details).getByText('指标细节')).toBeInTheDocument();
    expect(within(details).getByText('来源与约束')).toBeInTheDocument();
    expect(within(details).getByText('外部调用')).toBeInTheDocument();
    expect(within(details).getAllByText('未发生').length).toBeGreaterThan(0);
  });

  it('shows low-confidence proxy-only synthesis without promoting expansion or contraction', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: true,
      canReadProviders: true,
    });
    getLiquidityMonitor.mockResolvedValueOnce({
      ...payload,
      liquidityImpulseSynthesis: {
        ...payload.liquidityImpulseSynthesis,
        liquidityImpulse: 'expanding_liquidity',
        impulseLabel: 'Liquidity appears to be expanding',
        subtype: 'crypto_beta_expansion',
        confidence: 0.33,
        confidenceLabel: 'low',
        dominantDrivers: [
          {
            key: 'liquidity_monitor:btc',
            label: 'BTC',
            pillar: 'crypto_liquidity_beta',
            direction: 'supports_expansion',
            signal: 0.44,
            impact: 0.22,
            source: 'coinbase',
            proxyOnly: true,
            scoreContributionAllowed: false,
            observationOnly: true,
          },
        ],
        counterEvidence: [],
        dataGaps: [],
        evidenceQuality: {
          scoringEvidenceCount: 1,
          scoringPillarCount: 1,
          discountedEvidenceCount: 1,
          dataGapCount: 0,
          proxyOnlyScoringCount: 1,
          realScoringEvidenceCount: 0,
          allScoringEvidenceProxyOnly: true,
        },
      },
    });

    render(<LiquidityMonitorPage />);

    const guidancePanel = await screen.findByTestId('liquidity-monitor-guidance-panel');
    expect(guidancePanel).toHaveTextContent('部分可参考');
    expect(screen.getByTestId('liquidity-monitor-coverage-summary')).toHaveTextContent('可计分证据 1');
    const details = await expandLiquidityDetails();
    expect(within(details).getByTestId('liquidity-impulse-synthesis-title')).toHaveTextContent('流动性方向待确认');
    expect(within(details).getByTestId('liquidity-impulse-synthesis-state-chip')).toHaveTextContent('代理证据');
    expect(within(details).getByTestId('liquidity-impulse-synthesis-summary')).toHaveTextContent('不升级为真实扩张或收缩结论');
  });

  it('shows a missing synthesis payload honestly without fabricating a call', async () => {
    useProductSurfaceMock.mockReturnValue({
      isAdminMode: true,
      canReadProviders: true,
    });
    const { liquidityImpulseSynthesis, ...payloadWithoutSynthesis } = payload;
    void liquidityImpulseSynthesis;
    getLiquidityMonitor.mockResolvedValueOnce(payloadWithoutSynthesis);

    render(<LiquidityMonitorPage />);

    await screen.findByTestId('liquidity-monitor-guidance-panel');
    const details = await expandLiquidityDetails();
    expect(within(details).getByTestId('liquidity-impulse-synthesis-title')).toHaveTextContent('流动性方向待返回');
    expect(within(details).getByTestId('liquidity-impulse-synthesis-state-chip')).toHaveTextContent('载荷缺失');
    expect(within(details).getByTestId('liquidity-impulse-synthesis-summary')).toHaveTextContent('不推断扩张或收缩');
  });
});
