import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import MarketOverviewPage from '../MarketOverviewPage';
import { marketOverviewApi } from '../../api/marketOverview';
import { marketApi } from '../../api/market';
import { DataFreshnessBadge, MarketDataRow } from '../../components/market-overview/marketOverviewPrimitives';
import { UiLanguageProvider } from '../../contexts/UiLanguageContext';
import { UI_LANGUAGE_STORAGE_KEY } from '../../i18n/core';

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

const quoteItem = (
  symbol: string,
  label: string,
  value: number,
  changePct: number,
  source = 'yahoo',
) => ({
  symbol,
  label,
  value,
  unit: 'pts',
  changePct,
  riskDirection: changePct >= 0 ? 'decreasing' as const : 'increasing' as const,
  trend: [value * 0.98, value * 0.99, value],
  source,
  sourceLabel: source === 'sina' ? 'Sina' : 'Yahoo Finance',
  updatedAt: '2026-04-29T10:01:00',
  asOf: '2026-04-29T10:00:00',
  freshness: 'delayed' as const,
  isFallback: false,
  isStale: false,
});

const denseQuotePanel = (panelName: string, items: ReturnType<typeof quoteItem>[], source = 'yahoo') => ({
  ...panel(panelName, items[0]?.symbol || 'SPX', items[0]?.label || 'S&P 500'),
  source: source === 'mixed' ? 'mixed' : source,
  sourceLabel: source === 'mixed' ? 'Sina + Yahoo Finance' : source === 'sina' ? 'Sina' : 'Yahoo Finance',
  items,
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
  const button = screen.queryByRole('button', { name: /待接入真实数据源/i });
  if (!button) {
    return;
  }
  if (button.getAttribute('aria-expanded') !== 'true') {
    fireEvent.click(button);
  }
}

function getPrimaryCardOrder(): string[] {
  return Array.from(screen.getByTestId('market-overview-primary-rail').querySelectorAll('[data-testid^="market-overview-card-"]'))
    .map((node) => node.getAttribute('data-testid')?.replace('market-overview-card-', '') || '');
}

function getSideCardOrder(): string[] {
  return Array.from(screen.getByTestId('market-overview-side-rail').querySelectorAll('[data-testid^="market-overview-card-"]'))
    .map((node) => node.getAttribute('data-testid')?.replace('market-overview-card-', '') || '');
}

function getDeepCardOrder(): string[] {
  return Array.from(screen.getByTestId('market-overview-deep-panels').querySelectorAll('[data-testid^="market-overview-card-"]'))
    .map((node) => node.getAttribute('data-testid')?.replace('market-overview-card-', '') || '');
}

function renderMarketOverviewWithLanguage(language: 'zh' | 'en') {
  window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, language);
  return render(
    <UiLanguageProvider>
      <MarketOverviewPage />
    </UiLanguageProvider>,
  );
}

describe('MarketOverviewPage', () => {
  let originalClipboard: Navigator['clipboard'] | undefined;
  const writeTextMock = vi.fn().mockResolvedValue(undefined);

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
    originalClipboard = navigator.clipboard;
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: writeTextMock,
      },
    });
    writeTextMock.mockClear();
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
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: originalClipboard,
    });
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
    expect(await screen.findByText(/信号可信：高/i)).toBeInTheDocument();
    expect(screen.getByTestId('market-temperature-strip')).toBeInTheDocument();
    expect(screen.getByText(/可信度：高/i)).toBeInTheDocument();
    expect(screen.getByTestId('market-briefing-card')).toBeInTheDocument();
    expect(screen.getByText(/美股风险偏好偏暖/i)).toBeInTheDocument();

    const shell = screen.getByTestId('market-overview-shell');
    const workbench = screen.getByTestId('market-overview-workbench');
    expect(shell).toHaveAttribute('data-bento-surface', 'true');
    expect(shell).toHaveClass('bento-surface-root', 'w-full', 'flex', 'flex-1', 'min-h-0', 'min-w-0', 'flex-col', 'gap-6');
    expect(shell).not.toHaveClass('px-4', 'sm:px-6', 'lg:px-8', '2xl:px-10', 'py-6');
    expect(shell.className).not.toContain('max-w-[1280px]');
    expect(shell.className).not.toContain('max-w-[1600px]');
    expect(shell.className).not.toContain('max-w-[1800px]');
    expect(workbench).toHaveClass('flex', 'w-full', 'flex-1', 'min-h-0', 'min-w-0', 'flex-col', 'gap-6');
    expect(workbench).not.toHaveClass('mx-auto', 'max-w-[1280px]', 'max-w-[1600px]', 'max-w-[1800px]');
    expect(shell.className).not.toContain('max-w-5xl');
    expect(shell.className).not.toContain('max-w-6xl');
    expect(screen.getByTestId('market-overview-category-tabs')).toHaveClass('w-full', 'flex', 'bg-white/[0.02]', 'backdrop-blur-md');
    expect(screen.getByTestId('market-overview-category-tabs')).toHaveClass('min-w-0');
    expect(screen.getByTestId('market-overview-export-summary')).toHaveTextContent('复制摘要');
    expect(screen.getByTestId('market-overview-category-tabs')).not.toHaveClass('sticky', 'top-0', 'z-20', '-mx-4');
    expect(screen.getByTestId('market-overview-top-stack')).toContainElement(screen.getByTestId('market-overview-category-tabs'));
    expect(screen.getByTestId('market-overview-top-stack').firstElementChild).toBe(screen.getByTestId('market-overview-category-tabs'));
    expect(screen.getByTestId('market-overview-category-tabs')).toHaveAttribute('data-selector-position', 'static-safe');
    expect(screen.getByTestId('market-overview-category-tabs').querySelector('.ui-scroll-x-quiet')).not.toBeNull();
    expect(shell).toContainElement(screen.getByTestId('market-overview-category-tabs'));
    expect(shell).toContainElement(screen.getByTestId('market-overview-workbench'));
    expect(screen.getByTestId('market-overview-status-strip')).toContainElement(screen.getByTestId('market-overview-temperature-summary'));
    expect(screen.getByTestId('market-overview-status-strip')).toContainElement(screen.getByTestId('market-overview-data-quality-summary'));
    expect(shell).toContainElement(screen.getByTestId('market-overview-hero-ribbon'));
    expect(shell).toContainElement(screen.getByTestId('market-temperature-strip'));
    expect(shell).toContainElement(screen.getByTestId('market-data-quality'));
    expect(shell).toContainElement(screen.getByTestId('market-briefing-card'));
    expect(shell).toContainElement(screen.getByTestId('market-overview-main-grid'));

    expect(await screen.findByTestId('market-overview-main-grid')).toHaveClass('grid', 'grid-cols-1', 'xl:grid-cols-12', 'gap-4', 'items-start');
    expect(screen.getByTestId('market-overview-primary-rail')).toHaveClass('xl:col-span-9', 'flex', 'flex-col');
    expect(screen.getByTestId('market-overview-side-rail')).toHaveClass('xl:col-span-3', 'flex', 'flex-col', 'gap-3');
    expect(screen.getByTestId('market-overview-deep-panels')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /全球核心指数走势/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /A股与港股指数/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /加密货币行情/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /波动率与风险压力/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /ETF 资金流向/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /宏观经济与流动性/i })).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-rail-pending')).toHaveTextContent(/待接入真实数据源/);
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
    expect(screen.getByTestId('market-overview-rail-quality')).toHaveTextContent(/数据质量：部分备用/i);
    expect(screen.getAllByTestId('data-freshness-badge-fallback').length).toBeGreaterThan(0);
    expect(screen.getAllByTestId('data-freshness-badge-delayed').length).toBeGreaterThan(0);
    await waitFor(() => expect(marketOverviewApi.getMacro).toHaveBeenCalledTimes(1));
  });

  it('renders a stable workstation skeleton with grouped deep panels and an always-visible signal rail', async () => {
    render(<MarketOverviewPage />);

    expect(await screen.findByTestId('market-overview-pulse-header')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-category-tabs')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-hero-ribbon')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-status-strip')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-summary-band')).toContainElement(screen.getByTestId('market-overview-status-strip'));

    const mainGrid = screen.getByTestId('market-overview-main-grid');
    const primaryRail = screen.getByTestId('market-overview-primary-rail');
    const sideRail = screen.getByTestId('market-overview-side-rail');
    const deepPanels = screen.getByTestId('market-overview-deep-panels');

    expect(mainGrid).toHaveAttribute('data-workbench-split', '9:3');
    expect(primaryRail).toHaveClass('flex', 'flex-col');
    expect(primaryRail).not.toHaveClass('overflow-x-auto', 'stealth-scrollbar');
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-rail-coverage'));
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-rail-state'));
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-rail-quality'));
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-rail-briefing'));
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-rail-pending'));
    expect(screen.queryByTestId('market-overview-signal-disclosure')).not.toBeInTheDocument();
    expect(deepPanels).toHaveAttribute('data-panel-grouping', 'balanced');
    expect(getDeepCardOrder().length).toBeGreaterThan(0);
  });

  it('renders compact rail cards in the required order without expand-only behavior', async () => {
    render(<MarketOverviewPage />);

    const sideRail = await screen.findByTestId('market-overview-side-rail');
    const railCards = within(sideRail).getAllByTestId('market-overview-compact-rail-card');

    expect(railCards).toHaveLength(5);
    expect(railCards.map((card) => card.getAttribute('data-rail-card'))).toEqual([
      'coverage',
      'state',
      'quality',
      'briefing',
      'pending',
    ]);
    railCards.forEach((card) => {
      expect(card).toHaveAttribute('data-market-card-size', 'rail');
      expect(card).toHaveClass('overflow-hidden', 'min-w-0');
    });
    expect(sideRail).not.toContainElement(screen.queryByRole('button', { name: /展开/i }));
    expect(screen.queryByTestId('market-overview-fallback-section')).not.toBeInTheDocument();
  });

  it('keeps mobile DOM order as controls, pulse, summary, main, rail, then deep panels', async () => {
    render(<MarketOverviewPage />);

    const workbench = await screen.findByTestId('market-overview-workbench');
    const orderedNodes = Array.from(workbench.querySelectorAll('[data-mobile-order]'))
      .map((node) => node.getAttribute('data-mobile-order'));

    expect(orderedNodes).toEqual(['controls', 'pulse', 'summary', 'main', 'rail', 'deep']);
    const sideBeforeDeep = screen.getByTestId('market-overview-side-rail')
      .compareDocumentPosition(screen.getByTestId('market-overview-deep-panels'));
    expect(Boolean(sideBeforeDeep & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
  });

  it('renders each tab with a hero lane, secondary grid, and deep group', async () => {
    render(<MarketOverviewPage />);

    const expectations: Array<[string, string[]]> = [
      ['全部', ['market-overview-card-volatility', 'market-overview-card-fundsFlow', 'market-overview-card-indices']],
      ['美股', ['market-overview-card-volatility', 'market-overview-card-fundsFlow', 'market-overview-card-indices']],
      ['A股/港股', ['market-overview-card-cnIndices', 'market-overview-card-cnBreadth', 'market-overview-card-cnFlows']],
      ['全球宏观', ['market-overview-card-rates', 'market-overview-card-fxCommodities', 'market-overview-card-macro']],
      ['加密货币', ['market-overview-card-crypto', 'market-overview-card-volatility', 'market-overview-card-macro']],
    ];

    for (const [tab, heroCards] of expectations) {
      fireEvent.click(await screen.findByRole('button', { name: tab }));
      const heroLane = await screen.findByTestId('market-overview-hero-lane');
      const secondaryGrid = screen.getByTestId('market-overview-secondary-grid');
      const deepPanels = screen.getByTestId('market-overview-deep-panels');
      heroCards.forEach((testId) => {
        expect(screen.getByTestId(testId)).toBeInTheDocument();
      });
      expect(heroLane).toHaveAttribute('data-card-tier', 'hero');
      expect(secondaryGrid).toHaveAttribute('data-card-tier', 'secondary');
      expect(deepPanels).toHaveAttribute('data-card-tier', 'deep');
    }
  });

  it('renders bounded market row layout with value, change, and constrained sparkline', () => {
    render(
      <UiLanguageProvider>
        <MarketDataRow
          item={{
            ...quoteItem('VERY-LONG-SYMBOL-NAME', 'Very Long Cross Market Instrument Name That Must Truncate', 5120.25, 0.42),
            hoverDetails: ['extra source detail'],
          }}
          neutralLabel="中性"
        />
      </UiLanguageProvider>,
    );

    const row = screen.getByTestId('market-overview-data-row');
    expect(row).toHaveAttribute('data-row-layout', 'bounded-market-row');
    expect(row).toHaveClass('min-w-0', 'overflow-hidden');
    expect(within(row).getByTestId('market-overview-quote-value')).toHaveClass('text-right', 'font-mono');
    expect(within(row).getByTestId('market-overview-quote-change')).toHaveClass('text-right', 'font-mono');
    expect(within(row).getByTestId('market-overview-dense-quote-sparkline')).toHaveClass('w-[64px]');
  });

  it('places quote metadata in a compact middle column instead of a right-side stack', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValueOnce(denseQuotePanel('IndexTrendsCard', [
      quoteItem('SPX', 'S&P 500', 5120.25, 0.42),
      quoteItem('NDX', 'Nasdaq 100', 18220.42, 0.68),
    ]));

    render(<MarketOverviewPage />);

    const indicesCard = await screen.findByTestId('market-overview-card-indices');
    const firstQuote = within(indicesCard).getAllByTestId('market-overview-dense-quote-item')[0];
    const metadata = within(firstQuote).getByTestId('market-overview-quote-metadata');
    const valueBlock = within(firstQuote).getByTestId('market-overview-quote-value');
    const changeBlock = within(firstQuote).getByTestId('market-overview-quote-change');

    expect(metadata).toHaveAttribute('data-metadata-position', 'middle-left');
    expect(metadata).toHaveClass('col-start-2', 'whitespace-nowrap', 'overflow-hidden');
    expect(metadata).not.toHaveClass('col-span-3', 'justify-end');
    expect(metadata).toHaveTextContent(/Yahoo Finance/);
    expect(metadata).toHaveTextContent(/行情时间/);
    expect(metadata).toHaveTextContent(/更新/);
    expect(valueBlock).toHaveClass('col-start-4', 'text-right');
    expect(changeBlock).toHaveClass('col-start-5', 'text-right');
  });

  it('copies a market overview summary from the current visible state', async () => {
    render(<MarketOverviewPage />);

    const exportButton = await screen.findByTestId('market-overview-export-summary');
    fireEvent.click(exportButton);

    await waitFor(() => expect(writeTextMock).toHaveBeenCalledTimes(1));
    const copiedText = String(writeTextMock.mock.calls[0]?.[0] || '');
    expect(copiedText).toContain('市场总览 | 全部');
    expect(copiedText).toContain('市场温度：偏暖（62）');
    expect(copiedText).toContain('数据质量：部分备用');
    expect(copiedText).toContain('市场解读：美股风险偏好偏暖');
    expect(await screen.findByText('已复制摘要')).toBeInTheDocument();
  });

  it('filters China indices out of the US core index card', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValueOnce(denseQuotePanel('IndexTrendsCard', [
      quoteItem('SPX', 'S&P 500', 5120.25, 0.42),
      quoteItem('NDX', 'Nasdaq 100', 18220.42, 0.68),
      quoteItem('DJI', 'Dow Jones', 38920.18, -0.12),
      quoteItem('000001.SH', '上证指数', 3120.55, 0.39, 'sina'),
      quoteItem('399001.SZ', '深证成指', 9842.31, -0.18, 'sina'),
    ]));

    render(<MarketOverviewPage />);

    fireEvent.click(await screen.findByRole('button', { name: '美股' }));

    const indicesCard = await screen.findByTestId('market-overview-card-indices');
    expect(within(indicesCard).getByText('标普500')).toBeInTheDocument();
    expect(within(indicesCard).getByText('纳斯达克100')).toBeInTheDocument();
    expect(within(indicesCard).queryByText('上证指数')).not.toBeInTheDocument();
    expect(within(indicesCard).queryByText('深证成指')).not.toBeInTheDocument();
  });

  it('uses professional Chinese display names where market mappings exist', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValueOnce(denseQuotePanel('IndexTrendsCard', [
      quoteItem('SPX', 'S&P 500', 5120.25, 0.42),
      quoteItem('NDX', 'Nasdaq 100', 18220.42, 0.68),
      quoteItem('DJI', 'Dow Jones', 38920.18, -0.12),
      quoteItem('RUT', 'Russell 2000', 2088.5, 0.21),
    ]));
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce(denseQuotePanel('ChinaIndicesCard', [
      quoteItem('000001.SH', 'Shanghai Composite', 3120.55, 0.39, 'sina'),
      quoteItem('399001.SZ', 'Shenzhen Component', 9842.31, -0.18, 'sina'),
      quoteItem('000300.SH', 'CSI 300', 3588.12, 0.44, 'sina'),
      quoteItem('HSI', 'Hang Seng Index', 17712.5, 0.73, 'sina'),
      quoteItem('HSTECH', 'Hang Seng TECH', 3650.1, 0.62, 'sina'),
    ], 'mixed'));
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());
    vi.mocked(marketApi.getRates).mockResolvedValueOnce(denseQuotePanel('RatesCard', [
      quoteItem('US10Y', 'US 10Y', 4.62, -0.14),
    ]));
    vi.mocked(marketApi.getFxCommodities).mockResolvedValueOnce(denseQuotePanel('FxCommoditiesCard', [
      quoteItem('DXY', 'US Dollar Index', 106.2, 0.2),
      quoteItem('GOLD', 'Gold', 2380.3, 0.5),
      quoteItem('WTI', 'WTI Crude', 78.4, -0.3),
    ]));

    renderMarketOverviewWithLanguage('zh');

    const indicesCard = await screen.findByTestId('market-overview-card-indices');
    await waitFor(() => {
      expect(within(indicesCard).getByText('标普500')).toBeInTheDocument();
      expect(within(indicesCard).getByText('纳斯达克100')).toBeInTheDocument();
      expect(within(indicesCard).getByText('道琼斯工业平均指数')).toBeInTheDocument();
      expect(within(indicesCard).getByText('罗素2000')).toBeInTheDocument();
    });

    const cnIndicesCard = await screen.findByTestId('market-overview-card-cnIndices');
    await waitFor(() => {
      expect(within(cnIndicesCard).getByText('上证指数')).toBeInTheDocument();
      expect(within(cnIndicesCard).getByText('深证成指')).toBeInTheDocument();
      expect(within(cnIndicesCard).getByText('沪深300')).toBeInTheDocument();
      expect(within(cnIndicesCard).getByText('恒生指数')).toBeInTheDocument();
      expect(within(cnIndicesCard).getByText('恒生科技指数')).toBeInTheDocument();
    });

    const cryptoCard = await screen.findByTestId('market-overview-card-crypto');
    await waitFor(() => {
      expect(within(cryptoCard).getByText('比特币')).toBeInTheDocument();
      expect(within(cryptoCard).getByText('以太坊')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '全球宏观' }));
    await waitFor(() => {
      expect(screen.getAllByText('美国10年期国债收益率').length).toBeGreaterThan(0);
      expect(screen.getAllByText('美元指数').length).toBeGreaterThan(0);
      expect(screen.getByText('黄金')).toBeInTheDocument();
      expect(screen.getByText('WTI 原油')).toBeInTheDocument();
    });
  });

  it('keeps English display names in English UI', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValueOnce(denseQuotePanel('IndexTrendsCard', [
      quoteItem('SPX', 'S&P 500', 5120.25, 0.42),
      quoteItem('NDX', 'Nasdaq 100', 18220.42, 0.68),
    ]));
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());

    renderMarketOverviewWithLanguage('en');

    expect((await screen.findAllByText('S&P 500')).length).toBeGreaterThan(0);
    expect(screen.getByText('Nasdaq 100')).toBeInTheDocument();
    expect(screen.getAllByText('Bitcoin').length).toBeGreaterThan(0);
    expect(screen.queryByText('标普500')).not.toBeInTheDocument();
    expect(screen.queryByText('比特币')).not.toBeInTheDocument();
  });

  it('downgrades unreliable market temperature and briefing copy', async () => {
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce(unreliableTemperaturePayload());
    vi.mocked(marketApi.getMarketBriefing).mockResolvedValueOnce(unreliableBriefingPayload());

    render(<MarketOverviewPage />);

    expect(await screen.findByTestId('market-temperature-unreliable-summary')).toHaveTextContent('市场温度：数据不足');
    expect(screen.getByText(/真实输入不足，暂不生成综合判断/i)).toBeInTheDocument();
    expect(screen.getByText(/可信度：数据不足/i)).toBeInTheDocument();
    expect(screen.queryByText(/综合市场温度/i)).not.toBeInTheDocument();
    expect(screen.getByTestId('market-overview-rail-state')).toHaveTextContent(/真实 0.*备用 18.*排除 18.*confidence 0/i);
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
      expect(screen.getByText(/真实 2 · 备用 10 · 排除 10/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/真实 0/i)).not.toBeInTheDocument();
  });

  it('does not force indices and fundsFlow into the side rail globally', async () => {
    render(<MarketOverviewPage />);

    const primaryRail = await screen.findByTestId('market-overview-primary-rail');
    const sideRail = screen.getByTestId('market-overview-side-rail');

    expect(screen.getByTestId('market-overview-shell')).toHaveClass('bento-surface-root', 'w-full', 'flex-1');
    expect(screen.getByTestId('market-overview-workbench')).toHaveClass('w-full', 'flex-1');
    expect(screen.getByTestId('market-overview-workbench')).not.toHaveClass('mx-auto', 'max-w-[1800px]');
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
    expect(await screen.findByTestId('market-overview-card-cnIndices')).toHaveClass('min-w-0', 'w-full');
    expect(screen.getByTestId('market-overview-card-crypto')).toHaveClass('min-w-0', 'w-full');
    expect(screen.queryByText('实时行情')).not.toBeInTheDocument();
  });

  it('keeps the primary market cards in a stable responsive grid below desktop', async () => {
    render(<MarketOverviewPage />);

    const primaryRail = await screen.findByTestId('market-overview-primary-rail');
    expect(primaryRail).toHaveClass('flex', 'flex-col', 'gap-4');
    expect(screen.getByTestId('market-overview-hero-lane')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-secondary-grid')).toBeInTheDocument();
    expect(primaryRail).not.toHaveClass('stealth-scrollbar', 'overflow-x-auto', 'overscroll-x-contain');
    expect(screen.getByTestId('market-overview-card-indices')).toHaveClass('min-w-0', 'w-full');
  });

  it('renders quote-heavy primary cards as dense responsive quote grids', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValueOnce(denseQuotePanel('IndexTrendsCard', [
      quoteItem('SPX', 'S&P 500', 5120.25, 0.42),
      quoteItem('NDX', 'Nasdaq 100', 18220.42, 0.68),
      quoteItem('DJI', 'Dow Jones', 38920.18, -0.12),
      quoteItem('RUT', 'Russell 2000', 2088.5, 0.21),
    ]));
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce(denseQuotePanel('ChinaIndicesCard', [
      quoteItem('000001.SH', '上证指数', 3120.55, 0.39, 'sina'),
      quoteItem('000300.SH', '沪深300', 3588.12, 0.44, 'sina'),
      quoteItem('399001.SZ', '深证成指', 9842.31, -0.18, 'sina'),
      quoteItem('HSI', '恒生指数', 17712.5, 0.73, 'sina'),
    ], 'mixed'));
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());

    render(<MarketOverviewPage />);

    const primaryRail = await screen.findByTestId('market-overview-primary-rail');
    const secondaryGrid = screen.getByTestId('market-overview-secondary-grid');
    for (const cardKey of ['indices', 'cnIndices', 'crypto'] as const) {
      const card = await screen.findByTestId(`market-overview-card-${cardKey}`);
      if (cardKey === 'indices') {
        expect(primaryRail).toContainElement(card);
      } else {
        expect(secondaryGrid).toContainElement(card);
      }
      expect(card).toHaveAttribute('data-market-card-size', 'large');
      expect(card).toHaveAttribute('data-market-card-density', 'dense-quote');
      const denseCard = within(card).getByTestId('market-overview-dense-quote-card');
      const grid = within(denseCard).getByTestId('market-overview-dense-quote-grid');
      expect(grid).toHaveClass('flex', 'flex-col', 'border-y');
      expect(within(grid).getAllByTestId('market-overview-dense-quote-item').length).toBeGreaterThanOrEqual(2);
    }
  });

  it('uses compact quote item grids without a flexible empty sparkline region', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValueOnce(denseQuotePanel('IndexTrendsCard', [
      quoteItem('SPX', 'S&P 500', 5120.25, 0.42),
      quoteItem('NDX', 'Nasdaq 100', 18220.42, 0.68),
    ]));

    render(<MarketOverviewPage />);

    const indicesCard = await screen.findByTestId('market-overview-card-indices');
    const firstQuote = within(indicesCard).getAllByTestId('market-overview-dense-quote-item')[0];
    expect(firstQuote).toHaveAttribute('data-quote-item-layout', 'compact-grid');
    expect(firstQuote).toHaveClass('grid', 'min-w-0', 'grid-cols-[minmax(96px,1fr)_minmax(104px,0.9fr)_76px_minmax(82px,max-content)_minmax(92px,max-content)]');
    expect(within(firstQuote).getByTestId('market-overview-quote-metadata')).toHaveClass('col-start-2');
    const sparklineSlot = within(firstQuote).getByTestId('market-overview-dense-quote-sparkline');
    expect(sparklineSlot.className).toContain('w-[76px]');
    expect(sparklineSlot.className).not.toContain('flex-1');
    expect(within(firstQuote).getByTestId('market-overview-quote-value')).toHaveClass('col-start-4');
    expect(within(firstQuote).getByTestId('market-overview-quote-change')).toHaveClass('col-start-5');
    expect(within(firstQuote).getByText('标普500')).toBeInTheDocument();
    expect(within(firstQuote).getByText('SPX')).toBeInTheDocument();
    expect(within(firstQuote).getByText('5,120.25')).toBeInTheDocument();
    expect(within(firstQuote).getByTestId('data-freshness-badge-delayed')).toBeInTheDocument();
  });

  it('keeps quote-heavy cards out of the insight rail and reserves it for compact helpers', async () => {
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce(denseQuotePanel('ChinaIndicesCard', [
      quoteItem('000001.SH', '上证指数', 3120.55, 0.39, 'sina'),
      quoteItem('000300.SH', '沪深300', 3588.12, 0.44, 'sina'),
    ], 'mixed'));
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());

    render(<MarketOverviewPage />);

    const sideRail = await screen.findByTestId('market-overview-side-rail');
    expect(sideRail).not.toContainElement(screen.getByTestId('market-overview-card-indices'));
    expect(sideRail).not.toContainElement(screen.getByTestId('market-overview-card-cnIndices'));
    expect(sideRail).not.toContainElement(screen.getByTestId('market-overview-card-crypto'));
    expect(sideRail).toContainElement(screen.getByTestId('market-temperature-strip'));
    expect(sideRail).toContainElement(screen.getByTestId('market-data-quality'));
    expect(sideRail).toContainElement(screen.getByTestId('market-briefing-card'));
    expect(screen.queryByTestId('market-overview-signal-disclosure')).not.toBeInTheDocument();
    expect(sideRail.className).not.toContain('max-h');
    expect(sideRail.className).not.toContain('overflow-y-auto');
  });

  it('compresses the top status row into temperature, data quality, and briefing summaries', async () => {
    render(<MarketOverviewPage />);

    const statusStrip = screen.getByTestId('market-overview-status-strip');
    expect(statusStrip).toHaveClass('grid', 'grid-cols-1', 'md:grid-cols-3', 'gap-3');
    expect(statusStrip).toContainElement(screen.getByTestId('market-overview-temperature-summary'));
    expect(statusStrip).toContainElement(screen.getByTestId('market-overview-data-quality-summary'));
    expect(statusStrip).toContainElement(screen.getByTestId('market-overview-briefing-summary'));
    expect(screen.getByTestId('market-temperature-strip')).toBeInTheDocument();
    expect(statusStrip).not.toContainElement(await screen.findByTestId('market-temperature-strip'));
    expect(statusStrip).not.toContainElement(screen.getByTestId('market-data-quality'));
    expect(statusStrip).not.toContainElement(screen.getByTestId('market-briefing-card'));
  });

  it('keeps VIX risk module high priority in US and global views', async () => {
    vi.mocked(marketOverviewApi.getVolatility).mockResolvedValueOnce(denseQuotePanel('VolatilityCard', [
      quoteItem('VIX', 'VIX', 17.8, -2.4),
      quoteItem('VVIX', 'VVIX', 86.1, -1.2),
    ]));
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce(denseQuotePanel('ChinaIndicesCard', [
      quoteItem('000001.SH', '上证指数', 3120.55, 0.39, 'sina'),
    ], 'mixed'));
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());
    vi.mocked(marketApi.getRates).mockResolvedValueOnce(panel('RatesCard', 'US10Y', 'US 10Y'));

    render(<MarketOverviewPage />);

    fireEvent.click(await screen.findByRole('button', { name: '美股' }));
    expect(getPrimaryCardOrder()).toEqual(['indices', 'volatility', 'fundsFlow']);
    expect(within(screen.getByTestId('market-overview-card-volatility')).getByText('VIX 恐慌指数')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '全球宏观' }));
    const globalOrder = getPrimaryCardOrder();
    expect(globalOrder).toContain('rates');
    expect(globalOrder).toContain('volatility');
  });

  it('keeps deterministic workstation card order for every category', async () => {
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
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());
    vi.mocked(marketApi.getRates).mockResolvedValueOnce(panel('RatesCard', 'US10Y', 'US 10Y'));

    render(<MarketOverviewPage />);

    await screen.findByTestId('market-overview-primary-rail');
    await waitFor(() => {
      expect(getPrimaryCardOrder()).toEqual(['volatility', 'fundsFlow', 'indices', 'cnIndices', 'crypto', 'rates', 'macro', 'sentiment']);
    });
    expect(getDeepCardOrder()).toEqual(['cnBreadth', 'cnFlows', 'sectorRotation', 'cnShortSentiment', 'fxCommodities', 'futures']);
    expect(getSideCardOrder()).toEqual([]);

    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    expect(getPrimaryCardOrder()).toEqual(['indices', 'volatility', 'fundsFlow']);
    expect(getDeepCardOrder()).toEqual(['rates', 'macro', 'sentiment', 'futures']);
    expect(getSideCardOrder()).toEqual([]);

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    expect(getPrimaryCardOrder()).toEqual(['cnIndices', 'cnBreadth', 'cnFlows']);
    expect(getDeepCardOrder()).toEqual(['sectorRotation', 'cnShortSentiment', 'fxCommodities', 'sentiment']);
    expect(getSideCardOrder()).toEqual([]);

    fireEvent.click(screen.getByRole('button', { name: '全球宏观' }));
    expect(getPrimaryCardOrder()).toEqual(['rates', 'fxCommodities', 'macro', 'indices', 'volatility']);
    expect(getDeepCardOrder()).toEqual(['sentiment', 'futures']);
    expect(getSideCardOrder()).toEqual([]);
    expect(screen.getByTestId('market-overview-card-macro')).toHaveClass('min-w-0', 'w-full');

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));
    expect(getPrimaryCardOrder()).toEqual(['crypto', 'volatility', 'macro']);
    expect(getDeepCardOrder()).toEqual(['fxCommodities', 'sentiment']);
    expect(getSideCardOrder()).toEqual([]);
    expect(screen.getByTestId('market-overview-card-crypto')).toHaveClass('lg:col-span-2');
  });

  it('keeps mixed data cards in grouped deep panels when the tab uses them as supporting content', async () => {
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

    await screen.findByTestId('market-overview-primary-rail');
    const secondaryGrid = screen.getByTestId('market-overview-secondary-grid');
    const cnIndicesCard = await screen.findByTestId('market-overview-card-cnIndices');
    expect(secondaryGrid).toContainElement(cnIndicesCard);
    expect(cnIndicesCard).toHaveAttribute('data-market-card-rank', '0');
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

  it('shows category data coverage while keeping fallback-heavy cards grouped in the workstation', async () => {
    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));

    expect(await screen.findByTestId('market-overview-coverage-summary')).toHaveTextContent('A股/港股数据覆盖：真实 1 · 混合 0 · 备用 6');

    expect(screen.getByRole('heading', { name: /市场宽度与赚钱效应/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /行业与主题强弱/i })).toBeInTheDocument();
  });

  it('counts a real crypto card in crypto category coverage', async () => {
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());

    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));

    await waitFor(() => {
      expect(screen.getByTestId('market-overview-coverage-summary')).toHaveTextContent(/加密货币数据覆盖：真实 [1-9]/);
    });
    expect(screen.getByTestId('market-overview-card-crypto').closest('[data-testid="market-overview-main-grid"]')).toBeTruthy();
  });

  it('does not show an empty state when fallback cards are still useful grouped content', async () => {
    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));

    expect(await screen.findByTestId('market-overview-card-cnIndices')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-card-cnBreadth')).toBeInTheDocument();
    expect(screen.queryByTestId('market-overview-category-empty-state')).not.toBeInTheDocument();
  });

  it('keeps fallback-only cards accessible without an empty-state detour', async () => {
    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));

    expect(await screen.findByRole('heading', { name: /市场宽度与赚钱效应/i })).toBeInTheDocument();
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
    expect(screen.getByTestId('market-overview-temperature-summary')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-briefing-summary')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-coverage-summary')).toHaveTextContent('A股/港股数据覆盖');
    expect(screen.getByRole('heading', { name: /A股短线情绪/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /A股与港股指数/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /市场宽度与赚钱效应/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /资金流向/i })).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-card-cnIndices')).toHaveAttribute('data-market-card-rank', '0');
    expect(screen.getByTestId('market-overview-card-cnBreadth')).toHaveAttribute('data-market-card-rank', '0');
    expect(screen.getByTestId('market-overview-card-cnShortSentiment')).toHaveAttribute('data-market-card-rank', '1');

    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    expect(screen.getByRole('heading', { name: /全球核心指数走势/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /波动率与风险压力/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /ETF 资金流向/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /宏观经济与流动性/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /情绪与资金面/i })).toBeInTheDocument();
    expect(screen.queryByText('CSI 300')).not.toBeInTheDocument();
    expect(screen.queryByText('Shanghai Composite')).not.toBeInTheDocument();
    expect(screen.queryByText('Shenzhen Component')).not.toBeInTheDocument();
    expect(screen.queryByText('DXY')).not.toBeInTheDocument();
    expect(screen.getByTestId('market-overview-card-indices')).toHaveAttribute('data-market-card-rank', '0');
    expect(screen.getByTestId('market-overview-card-volatility')).toHaveAttribute('data-market-card-rank', '0');
    expect(screen.getByTestId('market-overview-card-fundsFlow')).toHaveAttribute('data-market-card-rank', '1');

    expect(marketApi.getCnIndices).toHaveBeenCalledTimes(1);
    expect(marketApi.getRates).toHaveBeenCalledTimes(1);
  });

  it('keeps other cards visible when one initial API request fails', async () => {
    vi.mocked(marketApi.getCnBreadth).mockRejectedValueOnce(new Error('breadth down'));

    render(<MarketOverviewPage />);

    expect(await screen.findByTestId('market-overview-main-grid')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-temperature-summary')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('heading', { name: /情绪与资金面/i })).toBeInTheDocument());
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

    expect(await screen.findByTestId('market-overview-temperature-summary')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-briefing-summary')).toBeInTheDocument();
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

    expect(screen.getByTestId('market-overview-card-volatility')).toHaveAttribute('data-market-card-rank', '0');
    expect(screen.getByTestId('market-overview-card-fundsFlow')).toHaveAttribute('data-market-card-rank', '1');
    expect(screen.getByTestId('market-overview-card-indices')).toHaveAttribute('data-market-card-rank', '2');
    expect(await screen.findByTestId('market-overview-card-cnIndices')).toHaveAttribute('data-market-card-rank', '0');
    expect(screen.getByTestId('market-overview-card-crypto')).toHaveAttribute('data-market-card-rank', '1');
    expect(window.localStorage.getItem('market-overview-order-all')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));

    expect(screen.getByTestId('market-overview-card-cnIndices')).toHaveAttribute('data-market-card-rank', '0');
    expect(screen.getByTestId('market-overview-card-cnBreadth')).toHaveAttribute('data-market-card-rank', '0');
    expect(window.localStorage.getItem('market-overview-order-cn')).toBeNull();
  });
});
