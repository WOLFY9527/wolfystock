import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import LiquidityMonitorPage from '../LiquidityMonitorPage';

const { getLiquidityMonitor } = vi.hoisted(() => ({
  getLiquidityMonitor: vi.fn(),
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

describe('LiquidityMonitorPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders score regime confidence freshness and disclosure', async () => {
    getLiquidityMonitor.mockResolvedValueOnce(payload);

    render(<LiquidityMonitorPage />);

    expect(await screen.findByRole('heading', { name: '流动性监测' })).toBeInTheDocument();
    const pageShell = screen.getByRole('heading', { name: '流动性监测' }).closest('[data-terminal-primitive="page-shell"]');
    expect(pageShell).toHaveAttribute('data-workspace-width', 'near-full');
    expect(pageShell).toHaveClass('max-w-[1840px]');
    expect(screen.getAllByText('支撑').length).toBeGreaterThan(0);
    expect(screen.getByText('69')).toBeInTheDocument();
    expect(screen.getByText('44%')).toBeInTheDocument();
    expect(screen.getAllByText('延迟').length).toBeGreaterThan(0);
    expect(screen.getByText('仅用于观察市场流动性环境，非投资建议，不触发扫描、回测或组合动作。')).toBeInTheDocument();
  });

  it('renders the liquidity impulse synthesis header with evidence rows', async () => {
    getLiquidityMonitor.mockResolvedValueOnce(payload);

    render(<LiquidityMonitorPage />);

    expect(await screen.findByTestId('liquidity-impulse-synthesis-header')).toBeInTheDocument();
    expect(screen.getByTestId('liquidity-impulse-synthesis-title')).toHaveTextContent('流动性收缩');
    expect(screen.getByTestId('liquidity-impulse-synthesis-impulse-chip')).toHaveTextContent('Liquidity appears to be contracting');
    expect(screen.getByTestId('liquidity-impulse-synthesis-subtype-chip')).toHaveTextContent('利率驱动收紧');
    expect(screen.getByTestId('liquidity-impulse-synthesis-confidence-chip')).toHaveTextContent('高');
    expect(screen.getByTestId('liquidity-impulse-synthesis-direction-chip')).toHaveTextContent('-0.58');
    expect(screen.getByTestId('liquidity-impulse-synthesis-dominant-drivers')).toHaveTextContent('US Rates / 利率压力');
    expect(screen.getByTestId('liquidity-impulse-synthesis-counter-evidence')).toHaveTextContent('BTC 动量');
    expect(screen.getByTestId('liquidity-impulse-synthesis-data-gaps')).toHaveTextContent('CN/HK Flows');
  });

  it('renders a compact direction-readiness summary with score-grade coverage and blocking reasons', async () => {
    getLiquidityMonitor.mockResolvedValueOnce(payload);

    render(<LiquidityMonitorPage />);

    const summary = await screen.findByTestId('liquidity-monitor-coverage-summary');
    expect(summary).toHaveTextContent('方向证据可用');
    expect(summary).toHaveTextContent('Score-grade evidence 2');
    expect(summary).toHaveTextContent('Observation-only evidence 1');
    expect(summary).toHaveTextContent('Missing evidence 2');
    expect(summary).toHaveTextContent('为什么不是完整方向结论');
    expect(summary).toHaveTextContent('覆盖不完整');
    expect(summary).toHaveTextContent('仅观察态');
    expect(summary).toHaveTextContent('仅在真实 funding 快照存在时显示');
    expect(summary.textContent || '').not.toMatch(/score_contribution_not_allowed|source_authority_router_rejected/);
  });

  it('renders partial and unavailable indicators compactly', async () => {
    getLiquidityMonitor.mockResolvedValueOnce(payload);

    render(<LiquidityMonitorPage />);

    await screen.findByRole('heading', { name: '流动性监测' });
    expect(screen.getAllByText('部分可用').length).toBeGreaterThan(0);
    const indicatorDisclosure = screen.getByTestId('liquidity-monitor-indicator-disclosure');
    expect(indicatorDisclosure).not.toHaveAttribute('open');
    expect(screen.queryByText('Crypto 资金费率')).not.toBeInTheDocument();
    fireEvent.click(within(indicatorDisclosure).getByRole('button', { name: '展开 完整指标矩阵' }));
    expect(screen.getByText('暂不可用')).toBeInTheDocument();
    expect(screen.getByText('Crypto 资金费率')).toBeVisible();
    expect(screen.getByText('仅在真实 funding 快照存在时显示')).toBeVisible();
  });

  it('shows compact official macro authority diagnostics for official, observation-only, fallback, and rejected rows', async () => {
    getLiquidityMonitor.mockResolvedValueOnce(payload);

    render(<LiquidityMonitorPage />);

    const diagnostics = await screen.findByTestId('liquidity-monitor-official-macro-diagnostics');
    const details = diagnostics.querySelector('details');
    const summary = diagnostics.querySelector('summary');
    expect(details).not.toBeNull();
    expect(summary).not.toBeNull();
    expect(details).not.toHaveAttribute('open');
    expect(diagnostics).toHaveTextContent('评分级证据 4');
    expect(diagnostics).toHaveTextContent('官方覆盖 5');
    expect(diagnostics).toHaveTextContent('代理/观察 2');
    expect(diagnostics).toHaveTextContent('备用 1');
    expect(diagnostics).toHaveTextContent('缺口 1');
    expect(diagnostics).toHaveTextContent('VIXCLS');
    expect(diagnostics).toHaveTextContent('SOFR');
    expect(diagnostics).toHaveTextContent('DFF');
    expect(diagnostics).toHaveTextContent('DGS2');
    expect(diagnostics).toHaveTextContent('DGS10');
    expect(diagnostics).toHaveTextContent('DGS30');
    expect(diagnostics).toHaveTextContent('BAMLH0A0HYM2');
    expect(within(diagnostics).getByText(/provider_forbidden_for_use_case/, { selector: 'p' })).not.toBeVisible();

    fireEvent.click(summary as HTMLElement);

    expect(details).toHaveAttribute('open');
    expect(diagnostics).toHaveTextContent('Official');
    expect(diagnostics).toHaveTextContent('Score-eligible');
    expect(diagnostics).toHaveTextContent('Observation-only');
    expect(diagnostics).toHaveTextContent('Fallback');
    expect(diagnostics).toHaveTextContent('Rejected');
    expect(diagnostics).toHaveTextContent('provider_forbidden_for_use_case');
    expect(diagnostics).toHaveTextContent('As-of 2026-05-06');
    expect(within(diagnostics).getByText(/provider_forbidden_for_use_case/, { selector: 'p' })).toBeVisible();
  });

  it('shows the selected indicator inspector and collapsed source details', async () => {
    getLiquidityMonitor.mockResolvedValueOnce(payload);

    render(<LiquidityMonitorPage />);

    await screen.findByRole('heading', { name: '流动性监测' });
    expect(screen.getAllByText('VIX / 波动率压力').length).toBeGreaterThan(0);
    expect(screen.getAllByText('均值 -2.50%').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: '展开 数据源细节' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '展开 数据源细节' }));
    expect(screen.getByText('外部调用')).toBeInTheDocument();
    expect(screen.getAllByText('未发生').length).toBeGreaterThan(0);
  });

  it('shows low-confidence proxy-only synthesis without promoting expansion or contraction', async () => {
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

    expect(await screen.findByTestId('liquidity-impulse-synthesis-title')).toHaveTextContent('流动性方向待确认');
    expect(screen.getByTestId('liquidity-impulse-synthesis-state-chip')).toHaveTextContent('Proxy-only');
    expect(screen.getByTestId('liquidity-impulse-synthesis-summary')).toHaveTextContent('不升级为真实扩张或收缩结论');
    expect(screen.getByTestId('liquidity-monitor-coverage-summary')).toHaveTextContent('方向证据不足');
    expect(screen.getByTestId('liquidity-monitor-coverage-summary')).toHaveTextContent('Score-grade evidence 0');
  });

  it('shows a missing synthesis payload honestly without fabricating a call', async () => {
    const { liquidityImpulseSynthesis, ...payloadWithoutSynthesis } = payload;
    void liquidityImpulseSynthesis;
    getLiquidityMonitor.mockResolvedValueOnce(payloadWithoutSynthesis);

    render(<LiquidityMonitorPage />);

    expect(await screen.findByTestId('liquidity-impulse-synthesis-title')).toHaveTextContent('流动性方向待返回');
    expect(screen.getByTestId('liquidity-impulse-synthesis-state-chip')).toHaveTextContent('载荷缺失');
    expect(screen.getByTestId('liquidity-impulse-synthesis-summary')).toHaveTextContent('不推断扩张或收缩');
  });
});
