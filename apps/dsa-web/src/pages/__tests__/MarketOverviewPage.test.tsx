import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import MarketOverviewPage from '../MarketOverviewPage';
import { marketOverviewApi } from '../../api/marketOverview';
import { marketApi } from '../../api/market';
import { DataFreshnessBadge } from '../../components/market-overview/marketOverviewPrimitives';

vi.mock('../../api/marketOverview', () => ({
  marketOverviewApi: {
    getIndices: vi.fn(),
    getVolatility: vi.fn(),
    getFundsFlow: vi.fn(),
    getMacro: vi.fn(),
  },
}));

vi.mock('../../api/market', () => ({
  marketApi: {
    getCrypto: vi.fn(),
    getSentiment: vi.fn(),
    getCnIndices: vi.fn(),
    getCnBreadth: vi.fn(),
    getCnFlows: vi.fn(),
    getSectorRotation: vi.fn(),
    getRates: vi.fn(),
    getFxCommodities: vi.fn(),
    getTemperature: vi.fn(),
    getMarketBriefing: vi.fn(),
    getFutures: vi.fn(),
    getCnShortSentiment: vi.fn(),
    cryptoStreamUrl: vi.fn(() => '/api/v1/market/crypto/stream'),
    normalizeCryptoStreamPayload: vi.fn((payload) => payload),
  },
}));

const panel = (panelName: string, symbol: string, label = symbol) => ({
  panelName,
  lastRefreshAt: '2026-04-29T10:00:00',
  status: 'success' as const,
  logSessionId: `${panelName}-log`,
  source: 'yahoo',
  sourceLabel: 'Yahoo Finance',
  updatedAt: '2026-04-29T10:01:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'delayed' as const,
  isFallback: false,
  isStale: false,
  items: [
    {
      symbol,
      label,
      value: 100,
      unit: 'pts',
      changePct: 1.2,
      riskDirection: 'decreasing' as const,
      trend: [96, 98, 100],
      source: 'yahoo',
      sourceLabel: 'Yahoo Finance',
      updatedAt: '2026-04-29T10:01:00',
      asOf: '2026-04-29T10:00:00',
      freshness: 'delayed' as const,
      isFallback: false,
      isStale: false,
    },
  ],
});

const macroPanel = () => ({
  ...panel('MacroIndicatorsCard', 'US10Y', 'US 10Y'),
  items: [
    ...panel('MacroIndicatorsCard', 'US10Y').items,
    {
      symbol: 'FEDFUNDS',
      label: 'Fed Funds',
      value: null,
      unit: '%',
      changePct: null,
      riskDirection: 'neutral' as const,
      trend: [],
    },
  ],
});

const cryptoPanel = () => ({
  panelName: 'CryptoCard',
  lastRefreshAt: '2026-04-29T10:00:00',
  status: 'success' as const,
  logSessionId: 'crypto-log',
  items: [
    {
      symbol: 'BTC',
      label: 'Bitcoin',
      value: 76837.04,
      unit: 'USD',
      changePct: 1.47,
      riskDirection: 'decreasing' as const,
      trend: [74211, 75120, 76003, 76837.04],
      hoverDetails: ['24H +1.47%', '7D +3.22%'],
    },
  ],
});

const cryptoFullPanel = () => ({
  ...cryptoPanel(),
  source: 'binance',
  sourceLabel: 'Binance',
  updatedAt: '2026-04-29T10:00:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'delayed' as const,
  isFallback: false,
  isRefreshing: false,
  items: [
    ...cryptoPanel().items,
    {
      symbol: 'ETH',
      label: 'Ethereum',
      value: 3120,
      unit: 'USD',
      changePct: -0.4,
      riskDirection: 'increasing' as const,
      trend: [3090, 3148, 3120],
      hoverDetails: ['24H -0.40%'],
    },
    {
      symbol: 'BNB',
      label: 'BNB',
      value: 590,
      unit: 'USD',
      changePct: 0.3,
      riskDirection: 'decreasing' as const,
      trend: [584, 588, 590],
      hoverDetails: ['24H +0.30%'],
    },
  ],
});

const cryptoLivePanel = () => ({
  ...cryptoFullPanel(),
  source: 'binance_ws',
  sourceLabel: 'Binance WS',
  updatedAt: '2026-04-29T10:00:01',
  asOf: '2026-04-29T10:00:01',
  freshness: 'live' as const,
  items: [
    {
      symbol: 'BTC',
      label: 'Bitcoin',
      value: 77001.25,
      unit: 'USD',
      changePct: 0.42,
      riskDirection: 'decreasing' as const,
      trend: [76837.04, 77001.25],
      source: 'binance_ws',
      sourceLabel: 'Binance WS',
      freshness: 'live' as const,
      isFallback: false,
    },
    {
      symbol: 'ETH',
      label: 'Ethereum',
      value: 3201,
      unit: 'USD',
      changePct: 0.8,
      riskDirection: 'decreasing' as const,
      trend: [3120, 3201],
      source: 'binance_ws',
      sourceLabel: 'Binance WS',
      freshness: 'live' as const,
      isFallback: false,
    },
    {
      symbol: 'BNB',
      label: 'BNB',
      value: 600,
      unit: 'USD',
      changePct: 0.5,
      riskDirection: 'decreasing' as const,
      trend: [590, 600],
      source: 'binance_ws',
      sourceLabel: 'Binance WS',
      freshness: 'live' as const,
      isFallback: false,
    },
  ],
});

const cryptoFallbackPanel = () => ({
  panelName: 'CryptoCard',
  lastRefreshAt: '2026-04-29T10:00:00',
  status: 'failure' as const,
  source: 'fallback',
  sourceLabel: '备用数据',
  updatedAt: '2026-04-29T10:00:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'fallback' as const,
  isFallback: true,
  isRefreshing: true,
  warning: '正在获取实时加密货币行情，当前显示备用快照',
  items: [
    {
      symbol: 'BTC',
      label: 'Bitcoin',
      value: 75800,
      unit: 'USD',
      changePct: -0.2,
      riskDirection: 'increasing' as const,
      trend: [75220, 75640, 75800],
      source: 'fallback',
      sourceLabel: '备用数据',
      freshness: 'fallback' as const,
      isFallback: true,
      warning: '正在获取实时加密货币行情，当前显示备用快照',
    },
    {
      symbol: 'ETH',
      label: 'Ethereum',
      value: 3120,
      unit: 'USD',
      changePct: -0.4,
      riskDirection: 'increasing' as const,
      trend: [3090, 3148, 3120],
      source: 'fallback',
      sourceLabel: '备用数据',
      freshness: 'fallback' as const,
      isFallback: true,
      warning: '正在获取实时加密货币行情，当前显示备用快照',
    },
    {
      symbol: 'BNB',
      label: 'BNB',
      value: 590,
      unit: 'USD',
      changePct: 0.3,
      riskDirection: 'decreasing' as const,
      trend: [584, 588, 590],
      source: 'fallback',
      sourceLabel: '备用数据',
      freshness: 'fallback' as const,
      isFallback: true,
      warning: '正在获取实时加密货币行情，当前显示备用快照',
    },
  ],
});

const sentimentPanel = () => ({
  panelName: 'MarketSentimentCard',
  lastRefreshAt: '2026-04-29T10:00:00',
  status: 'success' as const,
  logSessionId: 'sentiment-log',
  items: [
    {
      symbol: 'FGI',
      label: 'Fear & Greed',
      value: 26,
      unit: 'score',
      changePct: -7,
      riskDirection: 'increasing' as const,
      trend: [42, 38, 33, 26],
      hoverDetails: ['24H -7.00%', '7D -18.00%'],
    },
    {
      symbol: 'SOURCE',
      label: 'Provider',
      value: 26,
      unit: 'fallback',
      changePct: null,
      riskDirection: 'neutral' as const,
      trend: [26, 26],
    },
  ],
  errorMessage: '更新失败：已回退到最近一次有效数据',
});

const snapshotPanel = (panelName: string, symbol: string, label = symbol) => ({
  panelName,
  lastRefreshAt: '2026-04-29T10:00:00',
  status: 'success' as const,
  logSessionId: `${panelName}-log`,
  source: 'fallback',
  sourceLabel: '备用数据',
  updatedAt: '2026-04-29T10:00:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'fallback' as const,
  isFallback: true,
  warning: '备用示例数据，不代表当前行情',
  items: [
    {
      symbol,
      label,
      value: 100,
      unit: 'pts',
      changePct: 1.2,
      riskDirection: 'decreasing' as const,
      trend: [96, 98, 100],
      source: 'fallback',
      sourceLabel: '备用数据',
      updatedAt: '2026-04-29T10:00:00',
      asOf: '2026-04-29T10:00:00',
      freshness: 'fallback' as const,
      isFallback: true,
      warning: '备用示例数据，不代表当前行情',
      hoverDetails: ['fallback snapshot'],
    },
  ],
});

const temperaturePayload = () => ({
  source: 'computed',
  sourceLabel: '系统计算',
  updatedAt: '2026-04-29T10:00:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'cached' as const,
  isFallback: false,
  isStale: false,
  confidence: 0.82,
  reliableInputCount: 12,
  fallbackInputCount: 2,
  excludedInputCount: 2,
  isReliable: true,
  scores: {
    overall: { value: 62, label: '偏暖', trend: 'improving' as const, description: '风险偏好改善，但宏观压力仍需关注。' },
    usRiskAppetite: { value: 68, label: '偏暖', trend: 'improving' as const, description: '美股指数与风险情绪同步改善。' },
    cnMoneyEffect: { value: 55, label: '中性', trend: 'stable' as const, description: '指数表现尚可，但市场宽度一般。' },
    macroPressure: { value: 58, label: '中性偏高', trend: 'rising' as const, description: '美元与利率走强。' },
    liquidity: { value: 52, label: '中性', trend: 'stable' as const, description: '资金环境整体平稳。' },
  },
});

const briefingPayload = () => ({
  source: 'computed',
  sourceLabel: '系统计算',
  updatedAt: '2026-04-29T10:00:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'cached' as const,
  isFallback: false,
  isStale: false,
  confidence: 0.82,
  reliableInputCount: 12,
  fallbackInputCount: 2,
  excludedInputCount: 2,
  isReliable: true,
  items: [
    { title: '美股风险偏好偏暖', message: '主要指数走强，VIX 回落。', severity: 'positive' as const, category: 'us', confidence: 0.82 },
    { title: 'A股赚钱效应中性', message: '指数上涨但上涨家数占比一般。', severity: 'neutral' as const, category: 'cn', confidence: 0.82 },
    { title: '宏观压力仍需关注', message: '美债收益率和美元指数同步走强。', severity: 'warning' as const, category: 'macro', confidence: 0.82 },
  ],
});

const unreliableTemperaturePayload = () => ({
  source: 'fallback',
  sourceLabel: '备用数据',
  updatedAt: '2026-04-29T10:00:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'fallback' as const,
  isFallback: true,
  warning: '当前真实数据不足，市场温度仅供界面演示',
  confidence: 0,
  reliableInputCount: 0,
  fallbackInputCount: 18,
  excludedInputCount: 18,
  isReliable: false,
  scores: {
    overall: { value: 50, label: '数据不足', trend: 'stable' as const, description: '当前真实数据不足，市场温度仅供界面演示。' },
    usRiskAppetite: { value: 50, label: '数据不足', trend: 'stable' as const, description: '当前真实数据不足，市场温度仅供界面演示。' },
    cnMoneyEffect: { value: 50, label: '数据不足', trend: 'stable' as const, description: '当前真实数据不足，市场温度仅供界面演示。' },
    macroPressure: { value: 50, label: '数据不足', trend: 'stable' as const, description: '当前真实数据不足，市场温度仅供界面演示。' },
    liquidity: { value: 50, label: '数据不足', trend: 'stable' as const, description: '当前真实数据不足，市场温度仅供界面演示。' },
  },
});

const limitedRealTemperaturePayload = () => ({
  ...unreliableTemperaturePayload(),
  source: 'mixed',
  sourceLabel: '多来源',
  freshness: 'stale' as const,
  isFallback: false,
  confidence: 0.32,
  reliableInputCount: 2,
  fallbackInputCount: 10,
  excludedInputCount: 10,
});

const unreliableBriefingPayload = () => ({
  source: 'fallback',
  sourceLabel: '备用数据',
  updatedAt: '2026-04-29T10:00:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'fallback' as const,
  isFallback: true,
  warning: '当前真实数据不足，暂不生成强市场判断。',
  confidence: 0,
  reliableInputCount: 0,
  fallbackInputCount: 18,
  excludedInputCount: 18,
  isReliable: false,
  items: [
    { title: '当前真实数据不足', message: '当前真实数据不足，暂不生成强市场判断。', severity: 'warning' as const, category: 'risk', confidence: 0 },
    { title: '备用数据已降级', message: '备用示例数据仅用于保持界面结构，不参与市场温度评分。', severity: 'neutral' as const, category: 'risk', confidence: 0 },
  ],
});

const futuresPayload = () => ({
  source: 'fallback',
  sourceLabel: '备用数据',
  updatedAt: '2026-04-29T10:00:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'fallback' as const,
  isFallback: true,
  warning: '备用示例数据，不代表当前行情',
  items: [
    { name: '纳指期货', symbol: 'NQ', value: 18420.5, change: 65.2, changePercent: 0.35, market: 'US', session: 'premarket', sparkline: [18320, 18380, 18420.5], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback' as const, isFallback: true, warning: '备用示例数据，不代表当前行情' },
    { name: '富时A50期货', symbol: 'CN00Y', value: 12580, change: 38, changePercent: 0.3, market: 'CN', session: 'day', sparkline: [12420, 12542, 12580], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback' as const, isFallback: true, warning: '备用示例数据，不代表当前行情' },
  ],
});

const cnShortSentimentPayload = () => ({
  source: 'fallback',
  sourceLabel: '备用数据',
  updatedAt: '2026-04-29T10:00:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'fallback' as const,
  isFallback: true,
  warning: '备用示例数据，不代表当前行情',
  sentimentScore: 64,
  summary: '涨停家数占优，炸板率可控，短线情绪偏暖。',
  metrics: {
    limitUpCount: 68,
    limitDownCount: 18,
    failedLimitUpRate: 24.5,
    maxConsecutiveLimitUps: 5,
    yesterdayLimitUpPerformance: 2.8,
    firstBoardCount: 42,
    secondBoardCount: 12,
    highBoardCount: 6,
    twentyCmLimitUpCount: 9,
    stRiskLevel: 'normal',
  },
});

function expandPendingDataSourceSection() {
  const button = screen.getByRole('button', { name: /待接入真实数据源/i });
  if (button.getAttribute('aria-expanded') !== 'true') {
    fireEvent.click(button);
  }
}

describe('MarketOverviewPage', () => {
  class MockEventSource {
    static instances: MockEventSource[] = [];
    onmessage: ((event: MessageEvent) => void) | null = null;
    onerror: (() => void) | null = null;
    closed = false;
    url: string;

    constructor(url: string) {
      this.url = url;
      MockEventSource.instances.push(this);
    }

    close() {
      this.closed = true;
    }

    emit(payload: unknown) {
      this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent);
    }

    error() {
      this.onerror?.();
    }
  }

  beforeEach(() => {
    window.localStorage.clear();
    MockEventSource.instances = [];
    vi.stubGlobal('EventSource', MockEventSource);
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValue(panel('IndexTrendsCard', 'SPX'));
    vi.mocked(marketOverviewApi.getVolatility).mockResolvedValue(panel('VolatilityCard', 'VIX'));
    vi.mocked(marketOverviewApi.getFundsFlow).mockResolvedValue(panel('FundsFlowCard', 'ETF'));
    vi.mocked(marketOverviewApi.getMacro).mockResolvedValue(macroPanel());
    vi.mocked(marketApi.getCrypto).mockResolvedValue(cryptoPanel());
    vi.mocked(marketApi.getSentiment).mockResolvedValue(sentimentPanel());
    vi.mocked(marketApi.getCnIndices).mockResolvedValue({
      ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300'),
      items: [
        ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300').items,
        {
          symbol: '000001.SH',
          label: '上证指数',
          value: 3120.55,
          unit: 'pts',
          changePct: 0.39,
          riskDirection: 'decreasing' as const,
          trend: [3098, 3105, 3120.55],
          source: 'fallback',
          sourceLabel: '备用数据',
          updatedAt: '2026-04-29T10:00:00',
          asOf: '2026-04-29T10:00:00',
          freshness: 'fallback' as const,
          isFallback: true,
          warning: '备用示例数据，不代表当前行情',
        },
      ],
    });
    vi.mocked(marketApi.getCnBreadth).mockResolvedValue(snapshotPanel('ChinaBreadthCard', 'BREADTH', '赚钱效应'));
    vi.mocked(marketApi.getCnFlows).mockResolvedValue(snapshotPanel('ChinaFlowsCard', 'NORTHBOUND', '北向资金'));
    vi.mocked(marketApi.getSectorRotation).mockResolvedValue(snapshotPanel('SectorRotationCard', 'AI', 'AI / 算力'));
    vi.mocked(marketApi.getRates).mockResolvedValue({
      ...snapshotPanel('RatesCard', 'US10Y', 'US 10Y'),
      items: [
        ...snapshotPanel('RatesCard', 'US10Y', 'US 10Y').items,
        {
          symbol: 'CN10Y',
          label: '中国10年国债收益率',
          value: 2.35,
          unit: '%',
          changePct: -1.5,
          riskDirection: 'decreasing' as const,
          trend: [2.4, 2.37, 2.35],
          source: 'fallback',
          sourceLabel: '备用数据',
          freshness: 'fallback' as const,
          isFallback: true,
          warning: '备用示例数据，不代表当前行情',
        },
      ],
    });
    vi.mocked(marketApi.getFxCommodities).mockResolvedValue({
      ...snapshotPanel('FxCommoditiesCard', 'DXY', 'DXY'),
      items: [
        ...snapshotPanel('FxCommoditiesCard', 'DXY', 'DXY').items,
        {
          symbol: 'USDCNH',
          label: 'USD/CNH',
          value: 7.24,
          unit: '',
          changePct: 0.2,
          riskDirection: 'increasing' as const,
          trend: [7.2, 7.22, 7.24],
          source: 'fallback',
          sourceLabel: '备用数据',
          freshness: 'fallback' as const,
          isFallback: true,
          warning: '备用示例数据，不代表当前行情',
        },
      ],
    });
    vi.mocked(marketApi.getTemperature).mockResolvedValue(temperaturePayload());
    vi.mocked(marketApi.getMarketBriefing).mockResolvedValue(briefingPayload());
    vi.mocked(marketApi.getFutures).mockResolvedValue(futuresPayload());
    vi.mocked(marketApi.getCnShortSentiment).mockResolvedValue(cnShortSentimentPayload());
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('renders stable main grid with primary and side rails', async () => {
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce({
      ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300'),
      source: 'mixed',
      sourceLabel: 'Sina + 备用数据',
      freshness: 'delayed' as const,
      isFallback: false,
      items: [
        {
          ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300').items[0],
          source: 'sina',
          sourceLabel: 'Sina',
          freshness: 'delayed' as const,
          isFallback: false,
        },
        snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数').items[0],
      ],
    });
    render(<MarketOverviewPage />);

    expect(screen.getByRole('button', { name: '全部' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: '美股' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'A股/港股' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '全球宏观' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '加密货币' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /大市全景监控/i })).not.toBeInTheDocument();

    expect(screen.getByTestId('market-overview-hero-ribbon')).toBeInTheDocument();
    expect(screen.getByTestId('market-temperature-strip')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /市场温度总览/i })).toBeInTheDocument();
    expect(await screen.findByText(/可信度：高/i)).toBeInTheDocument();
    expect(screen.getByText(/综合市场温度/i)).toBeInTheDocument();
    expect(screen.getAllByText(/美股风险偏好/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/A股赚钱效应/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/全球宏观压力/i)).toBeInTheDocument();
    expect(screen.getByText(/流动性环境/i)).toBeInTheDocument();
    expect(screen.getByTestId('market-briefing-card')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /今日市场解读/i })).toBeInTheDocument();
    expect(screen.getByText(/美股风险偏好偏暖/i)).toBeInTheDocument();

    expect(await screen.findByTestId('market-overview-main-grid')).toHaveClass('grid', 'grid-cols-1', 'xl:grid-cols-12', 'gap-6', 'items-start');
    expect(screen.getByTestId('market-overview-primary-rail')).toHaveClass('xl:col-span-8', 'lg:grid-cols-2');
    expect(screen.getByTestId('market-overview-side-rail')).toHaveClass('xl:col-span-4', 'flex', 'flex-col', 'gap-6');
    expect(screen.getByRole('heading', { name: /全球核心指数走势/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /A股与港股指数/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /加密货币行情/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /波动率与风险压力/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /ETF 资金流向/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /宏观经济与流动性/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /待接入真实数据源/i })).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('button', { name: /同步最新行情/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/同步完成/i)).not.toBeInTheDocument();

    expect(screen.getAllByText(/比特币/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/标普500/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText('76,837.04').length).toBeGreaterThan(0);
    expect(screen.queryByText('pts')).not.toBeInTheDocument();

    expect(screen.getAllByTestId('market-overview-sparkline').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText(/Log:/i)).not.toBeInTheDocument();
    expect(screen.getAllByText(/备用示例数据，不代表当前行情/i).length).toBeGreaterThan(0);
    expect(screen.getByTestId('market-data-quality')).toBeInTheDocument();
    expect(screen.getByText(/当前数据质量：部分备用/i)).toBeInTheDocument();
    expect(screen.getAllByTestId('data-freshness-badge-fallback').length).toBeGreaterThan(0);
    expect(screen.getAllByTestId('data-freshness-badge-delayed').length).toBeGreaterThan(0);
    await waitFor(() => expect(marketOverviewApi.getMacro).toHaveBeenCalledTimes(1));
  });

  it('downgrades unreliable market temperature and briefing copy', async () => {
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce(unreliableTemperaturePayload());
    vi.mocked(marketApi.getMarketBriefing).mockResolvedValueOnce(unreliableBriefingPayload());

    render(<MarketOverviewPage />);

    expect(await screen.findByTestId('market-temperature-unreliable-summary')).toHaveTextContent('市场温度：数据不足');
    expect(screen.getByText(/当前真实数据源不足，暂不生成综合判断/i)).toBeInTheDocument();
    expect(screen.getByText(/可信度：数据不足/i)).toBeInTheDocument();
    expect(screen.queryByText(/综合市场温度/i)).not.toBeInTheDocument();
    expect(await screen.findByTestId('market-temperature-unreliable-summary')).toHaveTextContent('真实 0');
    expect(screen.getByTestId('market-temperature-unreliable-summary')).toHaveTextContent('备用 18');
    expect(screen.getByTestId('market-temperature-unreliable-summary')).toHaveTextContent('排除 18');
    expect(screen.getByTestId('market-temperature-unreliable-summary')).toHaveTextContent('confidence 0');
    fireEvent.click(screen.getByRole('button', { name: /查看占位评分/i }));
    expect(screen.getByText(/综合市场温度/i)).toBeInTheDocument();
    expect(screen.getByTestId('market-briefing-warning')).toHaveTextContent('当前真实数据不足，暂不生成强市场判断');
    expect(screen.getByText(/备用示例数据仅用于保持界面结构/i)).toBeInTheDocument();
  });

  it('shows limited real temperature inputs instead of collapsing them to zero', async () => {
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce(limitedRealTemperaturePayload());

    render(<MarketOverviewPage />);

    const summary = await screen.findByTestId('market-temperature-unreliable-summary');
    expect(summary).toHaveTextContent('市场温度：数据不足');
    await waitFor(() => {
      expect(summary).toHaveTextContent('真实输入不足，暂不生成综合判断');
      expect(summary).toHaveTextContent('真实 2');
      expect(summary).toHaveTextContent('备用 10');
      expect(summary).toHaveTextContent('排除 10');
    });
    expect(screen.queryByText(/真实 0/i)).not.toBeInTheDocument();
  });

  it('does not force indices and fundsFlow into the side rail globally', async () => {
    render(<MarketOverviewPage />);

    const primaryRail = await screen.findByTestId('market-overview-primary-rail');
    const sideRail = screen.getByTestId('market-overview-side-rail');

    expect(screen.getByTestId('market-overview-page-container')).toHaveClass('mx-auto', 'w-full', 'max-w-[1280px]');
    expect(primaryRail).toContainElement(screen.getByTestId('market-overview-card-indices'));
    expect(primaryRail).toContainElement(screen.getByTestId('market-overview-card-fundsFlow'));
    expect(sideRail).not.toContainElement(screen.getByTestId('market-overview-card-indices'));
    expect(sideRail).not.toContainElement(screen.getByTestId('market-overview-card-fundsFlow'));
  });

  it('has no side rail internal scroll and makes wide primary cards span columns', async () => {
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce({
      ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300'),
      source: 'mixed',
      sourceLabel: 'Sina + 备用数据',
      freshness: 'delayed' as const,
      isFallback: false,
      items: [
        {
          ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300').items[0],
          source: 'sina',
          sourceLabel: 'Sina',
          freshness: 'delayed' as const,
          isFallback: false,
        },
        snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数').items[0],
      ],
    });
    render(<MarketOverviewPage />);

    const sideRail = await screen.findByTestId('market-overview-side-rail');
    expect(sideRail.className).not.toContain('max-h-[800px]');
    expect(sideRail.className).not.toContain('overflow-y-auto');
    expect(screen.getByTestId('market-overview-card-indices')).toHaveClass('lg:col-span-2');
    expect(await screen.findByTestId('market-overview-card-cnIndices')).toHaveClass('lg:col-span-2');
    expect(screen.getByTestId('market-overview-card-crypto')).toHaveClass('lg:col-span-2');
    expect(screen.queryByText('实时行情')).not.toBeInTheDocument();
  });

  it('keeps mixed data cards in the main grid', async () => {
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce({
      ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300'),
      source: 'mixed',
      sourceLabel: 'Sina + 备用数据',
      freshness: 'delayed' as const,
      isFallback: false,
      items: [
        {
          ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300').items[0],
          source: 'sina',
          sourceLabel: 'Sina',
          freshness: 'delayed' as const,
          isFallback: false,
        },
        {
          ...snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数').items[0],
        },
      ],
    });

    render(<MarketOverviewPage />);

    const primaryRail = await screen.findByTestId('market-overview-primary-rail');
    expect(primaryRail).toContainElement(screen.getByTestId('market-overview-card-cnIndices'));
    expect(screen.getByTestId('market-overview-card-cnIndices')).toHaveAttribute('data-market-card-rank', '1');
  });

  it('counts A-share and Hong Kong mixed coverage without marking the category all fallback', async () => {
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce({
      ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300'),
      source: 'mixed',
      sourceLabel: 'Sina + 备用数据',
      freshness: 'delayed' as const,
      isFallback: false,
      items: [
        {
          ...snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数').items[0],
          source: 'sina',
          sourceLabel: 'Sina',
          freshness: 'delayed' as const,
          isFallback: false,
        },
        {
          ...snapshotPanel('ChinaIndicesCard', 'CN00Y', '富时A50期货').items[0],
        },
      ],
    });

    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));

    await waitFor(() => {
      expect(screen.getByTestId('market-overview-coverage-summary')).toHaveTextContent(/A股\/港股数据覆盖：真实 \d+ · 混合 [1-9]/);
    });
    expect(screen.queryByTestId('market-overview-category-empty-state')).not.toBeInTheDocument();
  });

  it('shows category data coverage and collapses fallback-heavy category cards', async () => {
    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));

    expect(await screen.findByTestId('market-overview-coverage-summary')).toHaveTextContent('A股/港股数据覆盖：真实 0 · 混合 0 · 备用 8');
    expect(screen.queryByRole('heading', { name: /市场宽度与赚钱效应/i })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /待接入真实数据源/i })).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(screen.getByRole('button', { name: /待接入真实数据源/i }));

    expect(screen.getByRole('heading', { name: /市场宽度与赚钱效应/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /行业与主题强弱/i })).toBeInTheDocument();
  });

  it('counts a real crypto card in crypto category coverage', async () => {
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());

    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));

    expect(await screen.findByTestId('market-overview-coverage-summary')).toHaveTextContent(/加密货币数据覆盖：真实 [1-9]/);
    expect(screen.getByTestId('market-overview-card-crypto').closest('[data-testid="market-overview-main-grid"]')).toBeTruthy();
  });

  it('shows an empty state when a category has no real or mixed cards', async () => {
    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));

    expect(await screen.findByTestId('market-overview-category-empty-state')).toHaveTextContent('当前分类暂无可用真实数据，备用模块已移入待接入真实数据源。');
    expect(screen.getByRole('button', { name: /查看待接入模块/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /待接入真实数据源/i })).toHaveAttribute('aria-expanded', 'false');
  });

  it('expands fallback-only cards from the category empty state', async () => {
    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    fireEvent.click(await screen.findByRole('button', { name: /查看待接入模块/i }));

    expect(screen.getByRole('button', { name: /待接入真实数据源/i })).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('heading', { name: /市场宽度与赚钱效应/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /行业与主题强弱/i })).toBeInTheDocument();
  });

  it('does not show the category empty state when real cards are visible', async () => {
    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));

    expect(await screen.findByTestId('market-overview-card-crypto')).toBeInTheDocument();
    expect(screen.queryByTestId('market-overview-category-empty-state')).not.toBeInTheDocument();
    expect(screen.queryByText(/当前分类暂无可用真实数据/i)).not.toBeInTheDocument();
  });

  it('uses REST crypto snapshot first and updates from the realtime stream', async () => {
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());

    render(<MarketOverviewPage />);

    await waitFor(() => expect(screen.getAllByText('76,837.04').length).toBeGreaterThan(0));
    expect(MockEventSource.instances[0].url).toContain('/api/v1/market/crypto/stream');

    act(() => {
      MockEventSource.instances[0].emit(cryptoLivePanel());
    });

    await waitFor(() => expect(screen.getAllByText('77,001.25').length).toBeGreaterThan(0));
    expect(screen.getAllByTestId('data-freshness-badge-live').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Binance WS/i).length).toBeGreaterThan(0);
  });

  it('keeps the latest crypto snapshot when the realtime stream errors', async () => {
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());

    render(<MarketOverviewPage />);

    await waitFor(() => expect(screen.getAllByText('76,837.04').length).toBeGreaterThan(0));
    act(() => {
      MockEventSource.instances[0].error();
    });

    expect(screen.getAllByText('76,837.04').length).toBeGreaterThan(0);
    expect(await screen.findByTestId('market-overview-card-crypto')).toBeInTheDocument();
  });

  it('closes the crypto realtime stream on unmount', async () => {
    const view = render(<MarketOverviewPage />);

    expect(await screen.findByTestId('market-overview-card-crypto')).toBeInTheDocument();
    const source = MockEventSource.instances[0];
    view.unmount();

    expect(source.closed).toBe(true);
  });

  it('keeps REST mode when EventSource is unavailable', async () => {
    vi.stubGlobal('EventSource', undefined);
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());

    render(<MarketOverviewPage />);

    await waitFor(() => expect(screen.getAllByText('76,837.04').length).toBeGreaterThan(0));
    expect(screen.getByTestId('market-overview-card-crypto')).toBeInTheDocument();
    expect(MockEventSource.instances).toHaveLength(0);
  });

  it('renders all data freshness badge states', () => {
    render(
      <div>
        {(['live', 'delayed', 'cached', 'stale', 'fallback', 'mock', 'error'] as const).map((freshness) => (
          <DataFreshnessBadge key={freshness} freshness={freshness} />
        ))}
      </div>,
    );

    expect(screen.getByText('实时')).toBeInTheDocument();
    expect(screen.getByText('延迟')).toBeInTheDocument();
    expect(screen.getByText('快照')).toBeInTheDocument();
    expect(screen.getByText('旧数据')).toBeInTheDocument();
    expect(screen.getByText('备用')).toBeInTheDocument();
    expect(screen.getByText('模拟')).toBeInTheDocument();
    expect(screen.getByText('异常')).toBeInTheDocument();
  });

  it('shows stale card data as old data', async () => {
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce({
      ...snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数'),
      freshness: 'stale' as const,
      isFallback: false,
      isStale: true,
      warning: '数据可能已过期，请以交易所/券商行情为准',
      items: [
        {
          ...snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数').items[0],
          freshness: 'stale' as const,
          isFallback: false,
          isStale: true,
          warning: '数据可能已过期，请以交易所/券商行情为准',
        },
      ],
    });

    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    expandPendingDataSourceSection();
    await waitFor(() => expect(screen.getAllByText('旧数据').length).toBeGreaterThan(0));
    expect(screen.getAllByText(/数据可能已过期/i).length).toBeGreaterThan(0);
  });

  it('shows snapshot refresh status without clearing stale card data', async () => {
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce({
      ...snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数'),
      isRefreshing: true,
      items: [
        {
          ...snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数').items[0],
          value: 3120.55,
        },
      ],
    });

    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    expandPendingDataSourceSection();
    await waitFor(() => expect(screen.getByText(/正在刷新快照/)).toBeInTheDocument());
    expect(screen.getByText('上证指数')).toBeInTheDocument();
    expect(screen.getByText(/3,120.55|3120.55/)).toBeInTheDocument();
  });

  it('switches market categories without refetching all cards', async () => {
    render(<MarketOverviewPage />);

    await waitFor(() => expect(marketApi.getCnIndices).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    expect(screen.getByRole('button', { name: 'A股/港股' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('heading', { name: /市场温度总览/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /今日市场解读/i })).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-coverage-summary')).toHaveTextContent('A股/港股数据覆盖');
    expect(screen.queryByRole('heading', { name: /A股短线情绪/i })).not.toBeInTheDocument();
    expandPendingDataSourceSection();
    expect(screen.getByRole('heading', { name: /A股短线情绪/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /A股与港股指数/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /市场宽度与赚钱效应/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /资金流向/i })).toBeInTheDocument();
    expect(screen.getByText('USD/CNH')).toBeInTheDocument();
    expect(screen.getByText('中国10年国债收益率')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-card-cnIndices')).toHaveAttribute('data-market-card-rank', '0');
    expect(screen.getByTestId('market-overview-card-cnBreadth')).toHaveAttribute('data-market-card-rank', '1');
    expect(screen.getByTestId('market-overview-card-cnShortSentiment')).toHaveAttribute('data-market-card-rank', '4');

    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    expect(screen.getByRole('heading', { name: /全球核心指数走势/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /波动率与风险压力/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /ETF 资金流向/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /宏观经济与流动性/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /情绪与资金面/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /待接入真实数据源/i })).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByText('CSI 300')).not.toBeInTheDocument();
    expect(screen.queryByText('Shanghai Composite')).not.toBeInTheDocument();
    expect(screen.queryByText('Shenzhen Component')).not.toBeInTheDocument();
    expect(screen.queryByText('DXY')).not.toBeInTheDocument();
    expect(screen.getByTestId('market-overview-card-indices')).toHaveAttribute('data-market-card-rank', '0');
    expect(screen.getByTestId('market-overview-card-volatility')).toHaveAttribute('data-market-card-rank', '1');

    expect(marketApi.getCnIndices).toHaveBeenCalledTimes(1);
    expect(marketApi.getRates).toHaveBeenCalledTimes(1);
  });

  it('keeps other cards visible when one initial API request fails', async () => {
    vi.mocked(marketApi.getCnBreadth).mockRejectedValueOnce(new Error('breadth down'));

    render(<MarketOverviewPage />);

    expect(await screen.findByTestId('market-overview-main-grid')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /市场温度总览/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /情绪与资金面/i })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('heading', { name: /波动率与风险压力/i })).toBeInTheDocument());
  });

  it('does not block settled cards when global indices request is still pending', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockReturnValueOnce(new Promise(() => {}));

    render(<MarketOverviewPage />);

    expect(await screen.findByText(/贪婪与恐慌指数/i)).toBeInTheDocument();
    expect(screen.getByText('26.00')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-main-grid')).toBeInTheDocument();
  });

  it('stops showing global indices loading when the request fails', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockRejectedValueOnce(new Error('indices down'));

    render(<MarketOverviewPage />);

    expect(await screen.findByTestId('market-overview-card-indices')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /全球核心指数走势/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText(/正在获取最新快照/i)).not.toBeInTheDocument();
    });
    expect(screen.getAllByTestId('data-freshness-badge-error').length).toBeGreaterThan(0);
  });

  it('does not leave crypto loading forever when the initial request is pending', async () => {
    vi.useFakeTimers();
    vi.mocked(marketApi.getCrypto).mockReturnValueOnce(new Promise(() => {}));

    render(<MarketOverviewPage />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3100);
    });

    expandPendingDataSourceSection();
    expect(screen.getByTestId('market-overview-card-crypto')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /加密货币行情/i })).toBeInTheDocument();
    expect(screen.getByText('BTC')).toBeInTheDocument();
    expect(screen.getByText('ETH')).toBeInTheDocument();
    expect(screen.getAllByText('BNB').length).toBeGreaterThan(0);
    expect(screen.getAllByTestId('data-freshness-badge-fallback').length).toBeGreaterThan(0);
    expect(screen.queryByText(/正在获取最新快照/i)).not.toBeInTheDocument();
  });

  it('renders the crypto fallback response as a card with freshness metadata', async () => {
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFallbackPanel());

    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));
    await screen.findByTestId('market-overview-fallback-section');
    expandPendingDataSourceSection();
    expect(await screen.findByRole('heading', { name: /加密货币行情/i })).toBeInTheDocument();
    expect((await screen.findAllByText(/75,800/)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/3,120/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/590/).length).toBeGreaterThan(0);
    expect(screen.getByText(/正在刷新快照/i)).toBeInTheDocument();
    expect(screen.getAllByTestId('data-freshness-badge-fallback').length).toBeGreaterThan(0);
    expect(screen.queryByTestId('data-freshness-badge-live')).not.toBeInTheDocument();
  });

  it('uses the same crypto write path for initial load and manual refresh', async () => {
    vi.mocked(marketApi.getCrypto)
      .mockResolvedValueOnce(cryptoFallbackPanel())
      .mockResolvedValueOnce(cryptoFullPanel());

    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));
    await screen.findByTestId('market-overview-fallback-section');
    expandPendingDataSourceSection();
    expect(await screen.findByText('BTC')).toBeInTheDocument();
    expect(screen.getByText('ETH')).toBeInTheDocument();
    expect(screen.getByText('BNB')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /刷新 加密货币行情/i }));

    await waitFor(() => expect(marketApi.getCrypto).toHaveBeenCalledTimes(2));
    expect(screen.getByText('BTC')).toBeInTheDocument();
    expect(screen.getByText('ETH')).toBeInTheDocument();
    expect(screen.getByText('BNB')).toBeInTheDocument();
    expect(screen.getAllByText('76,837.04').length).toBeGreaterThan(0);
  });

  it('keeps other market cards visible when crypto initial API fails', async () => {
    vi.mocked(marketApi.getCrypto).mockRejectedValueOnce(new Error('crypto down'));

    render(<MarketOverviewPage />);

    expandPendingDataSourceSection();
    expect(await screen.findByTestId('market-overview-card-crypto')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /加密货币行情/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /情绪与资金面/i })).toBeInTheDocument();
    expect(await screen.findByText('BTC')).toBeInTheDocument();
    expect(screen.queryByText(/正在获取最新快照/i)).not.toBeInTheDocument();
  });

  it('refreshes only the requested panel when a card refresh icon is clicked', async () => {
    render(<MarketOverviewPage />);

    await waitFor(() => expect(marketOverviewApi.getMacro).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    fireEvent.click(screen.getByRole('button', { name: /刷新 波动率与风险压力/i }));

    await waitFor(() => {
      expect(marketOverviewApi.getVolatility).toHaveBeenCalledTimes(2);
    });
    expect(marketOverviewApi.getIndices).toHaveBeenCalledTimes(1);
    expect(marketApi.getCrypto).toHaveBeenCalledTimes(1);
    expect(marketApi.getSentiment).toHaveBeenCalledTimes(1);
    expect(marketOverviewApi.getFundsFlow).toHaveBeenCalledTimes(1);
    expect(marketOverviewApi.getMacro).toHaveBeenCalledTimes(1);
    expect(marketApi.getFutures).toHaveBeenCalledTimes(1);
  });

  it('keeps fallback summary modules visible when new APIs fail', async () => {
    vi.mocked(marketApi.getTemperature).mockRejectedValueOnce(new Error('temperature down'));
    vi.mocked(marketApi.getMarketBriefing).mockRejectedValueOnce(new Error('briefing down'));
    vi.mocked(marketApi.getFutures).mockRejectedValueOnce(new Error('futures down'));
    vi.mocked(marketApi.getCnShortSentiment).mockRejectedValueOnce(new Error('sentiment down'));

    render(<MarketOverviewPage />);

    expect(await screen.findByRole('heading', { name: /市场温度总览/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /今日市场解读/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    expandPendingDataSourceSection();
    expect(screen.getByRole('heading', { name: /期货与盘前风向/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    expandPendingDataSourceSection();
    expect(screen.getByRole('heading', { name: /A股短线情绪/i })).toBeInTheDocument();
  });

  it('keeps stale card data visible while refreshing a single card', async () => {
    let resolveRefresh: ((value: ReturnType<typeof snapshotPanel>) => void) | undefined;
    vi.mocked(marketApi.getCnIndices)
      .mockResolvedValueOnce(snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数'))
      .mockReturnValueOnce(new Promise((resolve) => {
        resolveRefresh = resolve;
      }));

    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    expandPendingDataSourceSection();
    expect(await screen.findByText('上证指数')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /刷新 A股与港股指数/i }));
    expect(screen.getByText('上证指数')).toBeInTheDocument();

    resolveRefresh?.(snapshotPanel('ChinaIndicesCard', '399001.SZ', '深证成指'));
    expect(await screen.findByText('深证成指')).toBeInTheDocument();
  });

  it('polls market cards on the configured interval', async () => {
    const setIntervalSpy = vi.spyOn(window, 'setInterval');
    render(<MarketOverviewPage />);

    await waitFor(() => expect(marketApi.getCrypto).toHaveBeenCalledTimes(1));

    const pollCallback = setIntervalSpy.mock.calls[0]?.[0] as TimerHandler | undefined;
    expect(typeof pollCallback).toBe('function');
    (pollCallback as () => void)();

    await waitFor(() => {
      expect(marketApi.getCrypto).toHaveBeenCalledTimes(2);
      expect(marketApi.getSentiment).toHaveBeenCalledTimes(2);
    });
    setIntervalSpy.mockRestore();
  });

  it('uses deterministic layout instead of drag-sorted local card order', async () => {
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce({
      ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300'),
      source: 'mixed',
      sourceLabel: 'Sina + 备用数据',
      freshness: 'delayed' as const,
      isFallback: false,
      items: [
        {
          ...snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300').items[0],
          source: 'sina',
          sourceLabel: 'Sina',
          freshness: 'delayed' as const,
          isFallback: false,
        },
        snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数').items[0],
      ],
    });
    render(<MarketOverviewPage />);

    await waitFor(() => expect(marketApi.getCrypto).toHaveBeenCalledTimes(1));

    expect(screen.getByTestId('market-overview-card-indices')).toHaveAttribute('data-market-card-rank', '0');
    expect(await screen.findByTestId('market-overview-card-cnIndices')).toHaveAttribute('data-market-card-rank', '1');
    expect(screen.getByTestId('market-overview-card-crypto')).toHaveAttribute('data-market-card-rank', '2');
    expect(window.localStorage.getItem('market-overview-order-all')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    expandPendingDataSourceSection();

    expect(screen.getByTestId('market-overview-card-cnIndices')).toHaveAttribute('data-market-card-rank', '0');
    expect(screen.getByTestId('market-overview-card-cnBreadth')).toHaveAttribute('data-market-card-rank', '0');
    expect(window.localStorage.getItem('market-overview-order-cn')).toBeNull();
  });
});
