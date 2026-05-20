import { fireEvent, render, screen } from '@testing-library/react';
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
      key: 'us_breadth_proxy',
      label: 'US 广度代理',
      status: 'partial',
      freshness: 'delayed',
      includedInScore: true,
      scoreContribution: 6,
      scoreWeight: 6,
      summary: '8 / 3',
      updatedAt: '2026-05-07T10:00:00+08:00',
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
  advisoryDisclosure: '仅用于观察市场流动性环境，非买卖建议，不触发扫描、回测或组合动作。',
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
    expect(screen.getByText('仅用于观察市场流动性环境，非买卖建议，不触发扫描、回测或组合动作。')).toBeInTheDocument();
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

  it('renders partial and unavailable indicators compactly', async () => {
    getLiquidityMonitor.mockResolvedValueOnce(payload);

    render(<LiquidityMonitorPage />);

    await screen.findByRole('heading', { name: '流动性监测' });
    expect(screen.getByText('部分可用')).toBeInTheDocument();
    expect(screen.getByText('暂不可用')).toBeInTheDocument();
    expect(screen.getByText('Crypto 资金费率')).toBeVisible();
    expect(screen.getByText('仅在真实 funding 快照存在时显示')).toBeVisible();
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
