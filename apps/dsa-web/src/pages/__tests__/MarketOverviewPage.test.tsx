import { StrictMode } from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import MarketOverviewPage from '../MarketOverviewPage';
import { MarketOverviewWorkbench } from '../../components/market-overview/MarketOverviewWorkbench';
import { MARKET_OVERVIEW_TAB_CONFIG } from '../MarketOverviewTabConfig';
import { marketOverviewApi } from '../../api/marketOverview';
import { marketApi } from '../../api/market';
import { DataFreshnessBadge, MarketDataRow } from '../../components/market-overview/marketOverviewPrimitives';
import { TerminalPageHeading } from '../../components/terminal';
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

vi.mock('../../api/market', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/market')>();
  return {
    ...actual,
    marketApi: {
      getCrypto: vi.fn(),
      getSentiment: vi.fn(),
      getCnIndices: vi.fn(),
      getCnBreadth: vi.fn(),
      getCnFlows: vi.fn(),
      getSectorRotation: vi.fn(),
      getUsBreadth: vi.fn(),
      getRates: vi.fn(),
      getFxCommodities: vi.fn(),
      getTemperature: vi.fn(),
      getMarketBriefing: vi.fn(),
      getFutures: vi.fn(),
      getCnShortSentiment: vi.fn(),
      cryptoStreamUrl: vi.fn(() => '/api/v1/market/crypto/stream'),
      normalizeCryptoStreamPayload: vi.fn((payload) => payload),
    },
  };
});

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

const officialMacroPanel = () => ({
  ...panel('MacroIndicatorsCard', 'VIX', 'VIX'),
  source: 'mixed',
  sourceLabel: 'Official macro mix',
  freshness: 'cached' as const,
  isFallback: false,
  items: [
    {
      symbol: 'VIX',
      label: 'VIX',
      value: 18.4,
      unit: 'pts',
      changePct: -1.2,
      riskDirection: 'decreasing' as const,
      trend: [19.2, 18.9, 18.4],
      source: 'fred',
      sourceLabel: 'FRED VIXCLS',
      sourceType: 'official_public',
      sourceTier: 'official_public',
      trustLevel: 'reliable',
      updatedAt: '2026-05-21T10:00:05+08:00',
      asOf: '2026-05-21T10:00:00+08:00',
      freshness: 'cached' as const,
      isFallback: false,
      isPartial: false,
      isUnavailable: false,
      observationOnly: false,
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
      sourceAuthorityReason: null,
      sourceAuthorityRouteRejected: false,
      routeRejectedReasonCodes: [],
      officialSeriesId: 'VIXCLS',
      officialObservationDate: '2026-05-20',
      officialAsOf: '2026-05-20',
    },
    {
      symbol: 'FEDFUNDS',
      label: 'Fed Funds',
      value: 5.33,
      unit: '%',
      changePct: 0,
      riskDirection: 'neutral' as const,
      trend: [5.33, 5.33, 5.33],
      source: 'fred',
      sourceLabel: 'FRED DFF',
      sourceType: 'official_public',
      sourceTier: 'official_public',
      trustLevel: 'reliable',
      updatedAt: '2026-05-21T10:00:05+08:00',
      asOf: '2026-05-21T10:00:00+08:00',
      freshness: 'cached' as const,
      isFallback: false,
      isPartial: false,
      isUnavailable: false,
      observationOnly: false,
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
      sourceAuthorityReason: null,
      sourceAuthorityRouteRejected: false,
      routeRejectedReasonCodes: [],
      officialSeriesId: 'DFF',
      officialObservationDate: '2026-05-20',
      officialAsOf: '2026-05-20',
    },
    {
      symbol: 'CREDIT',
      label: 'Credit spreads',
      value: 3.75,
      unit: '%',
      changePct: 0.1,
      riskDirection: 'increasing' as const,
      trend: [3.6, 3.7, 3.75],
      source: 'fred',
      sourceLabel: 'FRED BAMLH0A0HYM2',
      sourceType: 'official_public',
      sourceTier: 'official_public',
      trustLevel: 'reliable',
      updatedAt: '2026-05-21T10:00:05+08:00',
      asOf: '2026-05-21T10:00:00+08:00',
      freshness: 'cached' as const,
      isFallback: false,
      isPartial: false,
      isUnavailable: false,
      observationOnly: true,
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: false,
      sourceAuthorityReason: null,
      sourceAuthorityRouteRejected: false,
      routeRejectedReasonCodes: [],
      officialSeriesId: 'BAMLH0A0HYM2',
      officialObservationDate: '2026-05-20',
      officialAsOf: '2026-05-20',
    },
    {
      symbol: 'US2Y',
      label: 'US 2Y',
      value: null,
      unit: '%',
      changePct: null,
      riskDirection: 'neutral' as const,
      trend: [],
      source: 'yahoo',
      sourceLabel: 'Yahoo proxy',
      sourceType: 'public_proxy',
      sourceTier: 'unofficial_public_api',
      trustLevel: 'usable_with_caution',
      updatedAt: '2026-05-21T10:00:05+08:00',
      asOf: '2026-05-21T10:00:00+08:00',
      freshness: 'fallback' as const,
      isFallback: true,
      isPartial: true,
      isUnavailable: false,
      observationOnly: false,
      sourceAuthorityAllowed: false,
      scoreContributionAllowed: false,
      sourceAuthorityReason: 'proxy_context_only',
      sourceAuthorityRouteRejected: false,
      routeRejectedReasonCodes: [],
      officialSeriesId: 'DGS2',
      officialObservationDate: null,
      officialAsOf: null,
    },
    {
      symbol: 'US30Y',
      label: 'US 30Y',
      value: null,
      unit: '%',
      changePct: null,
      riskDirection: 'neutral' as const,
      trend: [],
      source: 'unavailable',
      sourceLabel: 'Not returned',
      sourceType: 'unavailable',
      sourceTier: 'unavailable',
      trustLevel: 'unavailable',
      updatedAt: '2026-05-21T10:00:05+08:00',
      asOf: '2026-05-21T10:00:00+08:00',
      freshness: 'unavailable' as const,
      isFallback: false,
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
      symbol: 'SOL',
      label: 'Solana',
      value: 143.2,
      unit: 'USD',
      changePct: 1.8,
      riskDirection: 'decreasing' as const,
      trend: [139, 141, 143.2],
      hoverDetails: ['24H +1.80%'],
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
    {
      symbol: 'BTC_FUNDING',
      label: 'BTC Funding',
      value: 0.012,
      unit: '%',
      changePct: 0.012,
      riskDirection: 'increasing' as const,
      trend: [0.01, 0.012],
      hoverDetails: ['Binance Futures'],
    },
  ],
});

const usBreadthPanel = () => denseQuotePanel('UsBreadthCard', [
  quoteItem('SECTORS_UP', 'Sectors Up', 8, 0),
  quoteItem('SECTORS_DOWN', 'Sectors Down', 3, 0),
  quoteItem('STRONGEST_SECTOR', 'Strongest XLK', 1.8, 1.8),
  quoteItem('WEAKEST_SECTOR', 'Weakest XLE', -0.6, -0.6),
  quoteItem('RSP_SPY', 'RSP vs SPY', -0.4, -0.4),
  quoteItem('IWM_SPY', 'IWM vs SPY', -0.8, -0.8),
], 'yahoo');

const polygonUsBreadthPanel = () => ({
  ...denseQuotePanel('UsBreadthCard', [
    {
      ...quoteItem('ADVANCERS', '上涨家数', 2874, 0, 'polygon'),
      unit: '家',
      sourceLabel: 'Polygon grouped daily',
      sourceType: 'authorized_computed',
      sourceTier: 'authorized_market_data',
      trustLevel: 'score_grade_partial',
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
    },
    {
      ...quoteItem('DECLINERS', '下跌家数', 1986, 0, 'polygon'),
      unit: '家',
      sourceLabel: 'Polygon grouped daily',
      sourceType: 'authorized_computed',
      sourceTier: 'authorized_market_data',
      trustLevel: 'score_grade_partial',
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
    },
    {
      ...quoteItem('UNCHANGED', '平盘家数', 214, 0, 'polygon'),
      unit: '家',
      sourceLabel: 'Polygon grouped daily',
      sourceType: 'authorized_computed',
      sourceTier: 'authorized_market_data',
      trustLevel: 'score_grade_partial',
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
    },
    {
      ...quoteItem('ADVANCE_DECLINE_RATIO', '上涨/下跌比', 1.45, 0, 'polygon'),
      unit: '',
      sourceLabel: 'Polygon grouped daily',
      sourceType: 'authorized_computed',
      sourceTier: 'authorized_market_data',
      trustLevel: 'score_grade_partial',
      sourceAuthorityAllowed: true,
      scoreContributionAllowed: true,
    },
  ], 'polygon'),
  source: 'computed_from_authorized_polygon_grouped_daily',
  sourceLabel: 'Polygon grouped daily',
  sourceType: 'authorized_computed',
  freshness: 'delayed' as const,
  isFallback: false,
  isPartial: true,
  breadthClaimType: 'computed_from_authorized_eod_grouped_daily',
  officialExchangePublishedBreadth: false,
  fulfilledMetrics: ['ADVANCERS', 'DECLINERS', 'UNCHANGED', 'ADVANCE_DECLINE_RATIO'],
  missingMetrics: ['NEW_HIGHS', 'NEW_LOWS', 'HIGH_LOW_RATIO'],
  metricCoverageRatio: 4 / 7,
  sourceAuthorityAllowed: true,
  scoreContributionAllowed: true,
  broadMarketClaimAllowed: true,
  reasonCodes: ['polygon_high_low_history_unavailable'],
  providerHealth: {
    provider: 'polygon',
    status: 'partial' as const,
    asOf: '2026-05-21',
    updatedAt: '2026-05-22T04:00:00Z',
    latencyMs: 120,
    isFallback: false,
    isStale: false,
    isRefreshing: false,
    sourceLabel: 'Polygon grouped daily',
  },
  warning: 'High/low breadth unavailable.',
});

const usBreadthUnavailablePanel = () => ({
  ...snapshotPanel('UsBreadthCard', 'SECTOR_PROXY_UNAVAILABLE', '数据暂不可用'),
  source: 'unavailable',
  sourceLabel: '未接入',
  freshness: 'fallback' as const,
  isFallback: true,
  items: [
    {
      ...snapshotPanel('UsBreadthCard', 'SECTOR_PROXY_UNAVAILABLE', '数据暂不可用').items[0],
      value: null,
      changePct: null,
      unit: '',
      source: 'unavailable',
      sourceLabel: '未接入',
      freshness: 'fallback' as const,
      isFallback: true,
      hoverDetails: ['Sector ETF proxy 暂不可用'],
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

const cryptoPartialRefreshingPanel = () => ({
  ...cryptoFallbackPanel(),
  status: 'success' as const,
  source: 'mixed',
  sourceLabel: 'Binance + Cache',
  sourceType: 'mixed',
  freshness: 'stale' as const,
  isFallback: false,
  isStale: true,
  isRefreshing: true,
  providerHealth: {
    provider: 'binance',
    status: 'partial' as const,
    asOf: '2026-04-29T10:00:00',
    updatedAt: '2026-04-29T10:00:00',
    latencyMs: 480,
    errorSummary: 'background refresh in progress',
    isFallback: false,
    isStale: true,
    isRefreshing: true,
    sourceLabel: 'Binance partial snapshot',
    card: 'CryptoCard',
  },
  warning: '后台刷新进行中，当前显示部分可用快照',
  items: [
    {
      ...cryptoFallbackPanel().items[0],
      source: 'binance',
      sourceLabel: 'Binance',
      freshness: 'stale' as const,
      isFallback: false,
      isStale: true,
      isRefreshing: true,
    },
    {
      ...cryptoFallbackPanel().items[1],
      source: 'cache',
      sourceLabel: 'Recent Cache',
      freshness: 'stale' as const,
      isFallback: false,
      isStale: true,
      isRefreshing: true,
    },
    {
      ...cryptoFallbackPanel().items[2],
      source: 'cache',
      sourceLabel: 'Recent Cache',
      freshness: 'stale' as const,
      isFallback: false,
      isStale: true,
      isRefreshing: true,
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
  requiredReliableInputCount: 5,
  reliablePanelCount: 5,
  requiredReliablePanelCount: 3,
  fallbackInputCount: 2,
  excludedInputCount: 2,
  isReliable: true,
  temperatureAvailable: true,
  disabledReason: null,
  unavailableReason: null,
  insufficientReliableInputs: false,
  trustLevel: 'reliable',
  sourceTier: 'unofficial_public_api',
  conclusionAllowed: true,
  marketRegimeSynthesis: regimeSynthesisPayload(),
  marketDecisionSemantics: marketDecisionSemanticsPayload(),
  scores: {
    overall: { value: 62, label: '偏暖', trend: 'improving' as const, description: '风险偏好改善，但宏观压力仍需关注。' },
    usRiskAppetite: { value: 68, label: '偏暖', trend: 'improving' as const, description: '美股指数与风险情绪同步改善。' },
    cnMoneyEffect: { value: 55, label: '中性', trend: 'stable' as const, description: '指数表现尚可，但市场宽度一般。' },
    macroPressure: { value: 58, label: '中性偏高', trend: 'rising' as const, description: '美元与利率走强。' },
    liquidity: { value: 52, label: '中性', trend: 'stable' as const, description: '资金环境整体平稳。' },
  },
});

const marketDecisionSemanticsPayload = () => ({
  version: 'market_decision_semantics_v1',
  posture: 'offensive',
  postureConfidence: {
    value: 64,
    label: 'medium',
    capReasons: ['counter_evidence_present'],
  },
  exposureBias: 'risk_on_watch',
  directionReadiness: {
    status: 'direction_ready',
    confidenceLabel: 'medium',
    scoreGradePillars: {
      count: 3,
      items: [
        { pillar: 'official_macro_rates_volatility', label: 'Official macro/rates/volatility', reasonCode: 'score_grade_evidence' },
        { pillar: 'liquidity_conditions', label: 'Liquidity/conditions', reasonCode: 'score_grade_evidence' },
        { pillar: 'rotation_or_risk_participation', label: 'Rotation/risk participation', reasonCode: 'score_grade_evidence' },
      ],
    },
    observationOnlyPillars: { count: 0, items: [] },
    missingPillars: { count: 0, items: [] },
    blockingReasons: [],
    claimBoundaries: [
      { claim: 'market_direction_readiness_context', allowed: true, reasonCode: 'direction_ready' },
      { claim: 'trade_instruction', allowed: false, reasonCode: 'not_investment_advice' },
      { claim: 'allocation_or_suitability_guidance', allowed: false, reasonCode: 'not_investment_advice' },
    ],
    notInvestmentAdvice: true,
  },
  styleTilts: [
    { tilt: 'liquidity_beta_watch', label: 'Liquidity beta watch', detail: 'Risk-on regime and expanding liquidity align, but this remains watch-only.' },
    { tilt: 'rotation_leadership_watch', label: 'Rotation leadership watch', detail: 'Score-grade rotation leadership is confirming the posture watch.' },
  ],
  confirmationSignals: [
    { signal: 'regime_alignment', detail: 'Primary regime should remain score-grade.' },
    { signal: 'liquidity_alignment', detail: 'Liquidity impulse should remain expanding.' },
  ],
  invalidationTriggers: [
    { trigger: 'liquidity_stops_expanding', detail: 'Remove the risk-on watch if liquidity turns mixed or contracting.' },
  ],
  counterEvidence: [
    { surface: 'market_regime_synthesis', key: 'rates:US10Y', label: 'US10Y', detail: 'Rates pressure remains a contradiction.' },
  ],
  dataGaps: [
    { surface: 'liquidity_impulse_synthesis', key: 'official:fed_liquidity', label: 'Fed liquidity', reason: 'missing_scoring_evidence' },
  ],
  claimBoundaries: [
    { claim: 'observational_posture_watch', allowed: true, reasonCode: 'watch_only_language', detail: 'Only observational posture watch language is allowed.' },
    { claim: 'direct_trade_action', allowed: false, reasonCode: 'not_investment_advice', detail: 'No execution language.' },
    { claim: 'position_size_guidance', allowed: false, reasonCode: 'not_investment_advice', detail: 'No sizing language.' },
  ],
  notInvestmentAdvice: true,
});

const insufficientMarketDecisionSemanticsPayload = () => ({
  ...marketDecisionSemanticsPayload(),
  posture: 'data_insufficient',
  postureConfidence: {
    value: 18,
    label: 'insufficient',
    capReasons: ['missing_scoring_pillars', 'proxy_or_observation_only_evidence'],
  },
  exposureBias: 'no_bias_data_insufficient',
  directionReadiness: {
    status: 'data_insufficient',
    confidenceLabel: 'insufficient',
    scoreGradePillars: { count: 0, items: [] },
    observationOnlyPillars: {
      count: 2,
      items: [
        { pillar: 'official_macro_rates_volatility', label: 'Official macro/rates/volatility', reasonCode: 'fallback_or_proxy_evidence' },
        { pillar: 'rotation_or_risk_participation', label: 'Rotation/risk participation', reasonCode: 'observation_only_evidence' },
      ],
    },
    missingPillars: {
      count: 1,
      items: [
        { pillar: 'liquidity_conditions', label: 'Liquidity/conditions', reasonCode: 'missing_scoring_evidence' },
      ],
    },
    blockingReasons: [
      'no_meaningful_score_grade_pillars',
      'fallback_proxy_or_observation_only_evidence_present',
    ],
    claimBoundaries: [
      { claim: 'market_direction_readiness_context', allowed: false, reasonCode: 'data_insufficient' },
      { claim: 'trade_instruction', allowed: false, reasonCode: 'not_investment_advice' },
      { claim: 'allocation_or_suitability_guidance', allowed: false, reasonCode: 'not_investment_advice' },
    ],
    notInvestmentAdvice: true,
  },
  styleTilts: [],
  confirmationSignals: [],
  invalidationTriggers: [],
  counterEvidence: [],
  dataGaps: [
    { surface: 'market_regime_synthesis', key: 'crypto:BTC', label: 'BTC', reason: 'observation_only_discount' },
  ],
  claimBoundaries: [
    { claim: 'observational_posture_watch', allowed: false, reasonCode: 'insufficient_score_grade_evidence', detail: 'No posture watch is supportable.' },
    { claim: 'direct_trade_action', allowed: false, reasonCode: 'not_investment_advice', detail: 'No execution language.' },
    { claim: 'position_size_guidance', allowed: false, reasonCode: 'not_investment_advice', detail: 'No sizing language.' },
  ],
});

const regimeSynthesisPayload = () => ({
  primaryRegime: 'risk_on_liquidity_expansion',
  secondaryRegimes: ['goldilocks_soft_landing'],
  regimeScores: {
    risk_on_liquidity_expansion: 0.72,
    goldilocks_soft_landing: 0.44,
  },
  liquidityImpulse: 0.31,
  riskAppetite: 0.58,
  ratesPressure: -0.14,
  dollarPressure: -0.18,
  volatilityStress: -0.36,
  cryptoRiskBeta: 0.42,
  breadthHealth: 0.16,
  chinaRiskAppetite: 0.08,
  rotationQuality: 0.02,
  confidence: 0.66,
  confidenceLabel: 'medium',
  topDrivers: [
    {
      key: 'indices:SPX',
      label: '标普500',
      pillar: 'risk_appetite',
      direction: 'positive',
      signal: 0.58,
      weight: 0.94,
      impact: 0.54,
      source: 'sina',
      sourceTier: 'official_public',
      trustLevel: 'high',
      freshness: 'cached',
      observationOnly: false,
      scoreContributionAllowed: true,
      discountReasons: [],
    },
    {
      key: 'volatility:VIX',
      label: 'VIX',
      pillar: 'volatility_stress',
      direction: 'negative',
      signal: -0.42,
      weight: 0.91,
      impact: 0.49,
      source: 'fred',
      sourceTier: 'official_public',
      trustLevel: 'high',
      freshness: 'cached',
      observationOnly: false,
      scoreContributionAllowed: true,
      discountReasons: [],
    },
    {
      key: 'crypto:BTC',
      label: '比特币',
      pillar: 'crypto_risk_beta',
      direction: 'positive',
      signal: 0.39,
      weight: 0.67,
      impact: 0.33,
      source: 'binance',
      sourceTier: 'exchange_public',
      trustLevel: 'usable',
      freshness: 'delayed',
      observationOnly: false,
      scoreContributionAllowed: true,
      discountReasons: ['freshness_discount'],
    },
  ],
  counterEvidence: [
    {
      key: 'rates:US10Y',
      label: '美国10年期国债收益率',
      pillar: 'rates_pressure',
      signal: 0.24,
      expectedDirection: 'negative',
      reason: 'conflicts_with_primary_regime',
    },
    {
      key: 'fx:DXY',
      label: '美元指数',
      pillar: 'dollar_pressure',
      signal: 0.18,
      expectedDirection: 'negative',
      reason: 'conflicts_with_primary_regime',
    },
  ],
  dataGaps: [
    {
      key: 'breadth:CN',
      label: 'A股宽度',
      pillar: 'breadth_health',
      reason: 'missing_scoring_evidence',
      source: 'unavailable',
      sourceTier: 'unavailable',
      trustLevel: 'unavailable',
      freshness: 'unavailable',
      observationOnly: false,
      scoreContributionAllowed: false,
      degradationReason: 'provider_unavailable',
    },
    {
      key: 'rotation:small_caps',
      label: '小盘股轮动',
      pillar: 'rotation_leadership',
      reason: 'freshness_discount',
      source: 'snapshot',
      sourceTier: 'cache_snapshot',
      trustLevel: 'weak',
      freshness: 'stale',
      observationOnly: false,
      scoreContributionAllowed: true,
      degradationReason: 'stale',
    },
  ],
  narrativeBullets: ['Risk appetite is improving but rates pressure remains a live contradiction.'],
  evidenceQuality: {
    scoringEvidenceCount: 6,
    scoringPillarCount: 5,
    discountedEvidenceCount: 1,
    dataGapCount: 2,
  },
  notInvestmentAdvice: true,
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
  requiredReliableInputCount: 5,
  reliablePanelCount: 0,
  requiredReliablePanelCount: 3,
  fallbackInputCount: 18,
  excludedInputCount: 18,
  isReliable: false,
  temperatureAvailable: false,
  disabledReason: 'insufficient_reliable_inputs',
  unavailableReason: 'insufficient_reliable_inputs',
  insufficientReliableInputs: true,
  trustLevel: 'unavailable',
  sourceTier: 'static_fallback',
  conclusionAllowed: false,
  marketDecisionSemantics: insufficientMarketDecisionSemanticsPayload(),
  marketRegimeSynthesis: {
    primaryRegime: 'data_insufficient',
    secondaryRegimes: [],
    regimeScores: {},
    liquidityImpulse: 0,
    riskAppetite: 0,
    ratesPressure: 0,
    dollarPressure: 0,
    volatilityStress: 0,
    cryptoRiskBeta: 0,
    breadthHealth: 0,
    chinaRiskAppetite: 0,
    rotationQuality: 0,
    confidence: 0.22,
    confidenceLabel: 'insufficient',
    topDrivers: [
      {
        key: 'indices:SPX',
        label: '标普500',
        pillar: 'risk_appetite',
        direction: 'positive',
        signal: 0.18,
        weight: 0.35,
        impact: 0.08,
        source: 'fallback',
        sourceTier: 'static_fallback',
        trustLevel: 'weak',
        freshness: 'fallback',
        observationOnly: false,
        scoreContributionAllowed: false,
        discountReasons: ['source_tier_discount'],
      },
    ],
    counterEvidence: [],
    dataGaps: [
      {
        key: 'breadth:CN',
        label: 'A股宽度',
        pillar: 'breadth_health',
        reason: 'missing_scoring_evidence',
        source: 'unavailable',
        sourceTier: 'unavailable',
        trustLevel: 'unavailable',
        freshness: 'unavailable',
        observationOnly: false,
        scoreContributionAllowed: false,
        degradationReason: 'provider_unavailable',
      },
      {
        key: 'crypto:BTC',
        label: '比特币',
        pillar: 'crypto_risk_beta',
        reason: 'observation_only_discount',
        source: 'coinbase',
        sourceTier: 'exchange_public',
        trustLevel: 'usable',
        freshness: 'delayed',
        observationOnly: true,
        scoreContributionAllowed: false,
        degradationReason: 'observation_only',
      },
    ],
    narrativeBullets: ['Coverage remains below scoring threshold.'],
    evidenceQuality: {
      scoringEvidenceCount: 2,
      scoringPillarCount: 2,
      discountedEvidenceCount: 2,
      dataGapCount: 2,
    },
    notInvestmentAdvice: true,
  },
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
  reliablePanelCount: 2,
  fallbackInputCount: 10,
  excludedInputCount: 10,
  trustLevel: 'weak',
  sourceTier: 'unofficial_public_api',
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

const MARKET_OVERVIEW_LKG_STORAGE_KEY = 'wolfystock.marketOverview.lastKnownGood.v1';

function localSnapshotPayload(overrides: Record<string, unknown> = {}) {
  return {
    schemaVersion: 1,
    savedAt: '2026-05-04T10:15:00.000Z',
    payload: {
      indices: {
        ...panel('IndexTrendsCard', 'SPX', 'S&P 500'),
        source: 'local-cache',
        sourceLabel: 'Local Cache',
        freshness: 'stale' as const,
        isStale: true,
        isFromSnapshot: true,
        lastSuccessfulAt: '2026-05-04T10:00:00+08:00',
        items: [
          {
            ...quoteItem('SPX', 'S&P 500', 5111.11, 0.31),
            source: 'local-cache',
            sourceLabel: 'Local Cache',
            freshness: 'stale' as const,
            isStale: true,
          },
        ],
      },
      crypto: {
        ...cryptoFullPanel(),
        source: 'local-cache',
        sourceLabel: 'Local Cache',
        freshness: 'stale' as const,
        isStale: true,
      },
      temperature: temperaturePayload(),
      briefing: briefingPayload(),
      futures: futuresPayload(),
      cnShortSentiment: cnShortSentimentPayload(),
      ...overrides,
    },
  };
}

function expandPendingDataSourceSection() {
  const button = screen.queryByRole('button', { name: /待接入真实数据源/i });
  if (!button) {
    return;
  }
  if (button.getAttribute('aria-expanded') !== 'true') {
    fireEvent.click(button);
  }
}

function getRowCardOrder(rowId: string): string[] {
  const row = screen.getByTestId('market-overview-main-grid').querySelector(`[data-row-id="${rowId}"]`);
  return Array.from(row?.querySelectorAll('[data-testid^="market-overview-card-"]') || [])
    .map((node) => node.getAttribute('data-testid')?.replace('market-overview-card-', '') || '');
}

function getRowIds(): string[] {
  return Array.from(screen.getByTestId('market-overview-main-grid').querySelectorAll('[data-testid="market-overview-row"]'))
    .map((node) => node.getAttribute('data-row-id') || '');
}

function getSideCardOrder(): string[] {
  return Array.from(screen.getByTestId('market-overview-side-rail').querySelectorAll('[data-testid^="market-overview-card-"]'))
    .map((node) => node.getAttribute('data-testid')?.replace('market-overview-card-', '') || '');
}

function getPulseText(): string {
  return screen.getByTestId('market-overview-hero-ribbon').textContent || '';
}

function expandMarketDecisionDetails() {
  const disclosure = screen.getByTestId('market-decision-debug-details');
  const toggle = within(disclosure).getByRole('button', { name: /展开 技术细节 \/ Details/i });
  fireEvent.click(toggle);
  return disclosure;
}

function renderMarketOverviewWithLanguage(language: 'zh' | 'en') {
  window.localStorage.setItem(UI_LANGUAGE_STORAGE_KEY, language);
  return render(
    <UiLanguageProvider>
      <MarketOverviewPage />
    </UiLanguageProvider>,
  );
}

function renderMarketOverviewWorkbench() {
  return render(
    <UiLanguageProvider>
      <MarketOverviewWorkbench
        heading={<TerminalPageHeading data-testid="market-overview-page-heading" title="市场总览" />}
        panels={localSnapshotPayload().payload}
        loading={false}
        localSnapshotSavedAt="2026-04-29T10:00:00"
        refreshErrorCount={0}
        refreshingPanel={null}
        cryptoRealtimeStatus="snapshot"
        isCnShortSentimentBootstrapping={false}
        onRefreshPanel={() => {}}
      />
    </UiLanguageProvider>,
  );
}

function renderMarketOverviewWorkbenchWithProps(overrides: Partial<Parameters<typeof MarketOverviewWorkbench>[0]> = {}) {
  const basePanels = localSnapshotPayload().payload;
  return render(
    <UiLanguageProvider>
      <MarketOverviewWorkbench
        heading={<TerminalPageHeading data-testid="market-overview-page-heading" title="市场总览" />}
        panels={basePanels}
        loading={false}
        localSnapshotSavedAt="2026-04-29T10:00:00"
        refreshErrorCount={0}
        refreshingPanel={null}
        cryptoRealtimeStatus="snapshot"
        isCnShortSentimentBootstrapping={false}
        onRefreshPanel={() => {}}
        {...overrides}
      />
    </UiLanguageProvider>,
  );
}

const primaryMarketPanelRequests = [
  marketOverviewApi.getIndices,
  marketOverviewApi.getVolatility,
  marketApi.getCrypto,
  marketApi.getSentiment,
  marketOverviewApi.getFundsFlow,
  marketApi.getCnIndices,
  marketApi.getRates,
  marketApi.getFxCommodities,
  marketApi.getTemperature,
  marketApi.getMarketBriefing,
] as const;

const firstStagedMarketPanelRequests = [
  marketOverviewApi.getMacro,
  marketApi.getCnBreadth,
  marketApi.getUsBreadth,
] as const;

const secondStagedMarketPanelRequests = [
  marketApi.getCnFlows,
  marketApi.getSectorRotation,
  marketApi.getFutures,
  marketApi.getCnShortSentiment,
] as const;

const allMarketPanelRequests = [
  ...primaryMarketPanelRequests,
  ...firstStagedMarketPanelRequests,
  ...secondStagedMarketPanelRequests,
] as const;

const AUTO_REVALIDATE_OBSERVATION_WINDOW_MS = 5_000;

type MarketPanelRequestMock = (typeof allMarketPanelRequests)[number];
type DeferredPromise<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
};

function createDeferredPromise<T>(): DeferredPromise<T> {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve;
  });
  return { promise, resolve };
}

function countMarketPanelRequests(): number {
  return allMarketPanelRequests.reduce((total, request) => total + vi.mocked(request).mock.calls.length, 0);
}

function expectMarketPanelRequestsCalledOnce(requests: readonly MarketPanelRequestMock[]): void {
  requests.forEach((request) => {
    expect(request).toHaveBeenCalledTimes(1);
  });
}

function expectMarketPanelRequestsNotCalled(requests: readonly MarketPanelRequestMock[]): void {
  requests.forEach((request) => {
    expect(request).not.toHaveBeenCalled();
  });
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
    vi.mocked(marketApi.getUsBreadth).mockResolvedValue(usBreadthPanel());
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

  it('renders the MarketMonitor boundary with stable controls and collapsed diagnostics', async () => {
    renderMarketOverviewWorkbench();

    expect(screen.getByTestId('market-overview-workbench')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-shell')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-market-monitor')).toBeInTheDocument();
    expect(screen.getByTestId('market-decision-semantics-strip')).toHaveTextContent('市场判断摘要');
    expect(screen.getByTestId('market-overview-grid-loading')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-grid-loading')).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByTestId('market-overview-grid-loading')).not.toHaveClass('bg-black');
    expect(await screen.findByTestId('market-overview-main-grid')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-side-rail')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '展开 技术细节 / Details' })).toBeInTheDocument();
    expect(screen.queryByTestId('market-regime-synthesis-header')).not.toBeInTheDocument();
    const details = expandMarketDecisionDetails();
    expect(within(details).getByTestId('market-regime-synthesis-header')).toBeInTheDocument();
    expect(within(details).getByTestId('market-overview-temperature-summary')).toBeInTheDocument();
    expect(within(details).getByTestId('market-overview-official-macro-diagnostics')).toBeInTheDocument();

    const usTab = screen.getByRole('button', { name: '美股' });
    fireEvent.click(usTab);

    expect(usTab).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('market-overview-export-summary')).toBeInTheDocument();
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

  it('renders exactly one compact semantic market overview heading without internal terms', async () => {
    renderMarketOverviewWithLanguage('zh');

    const heading = await screen.findByRole('heading', { level: 1, name: '市场总览' });
    expect(heading).toHaveClass('text-xl', 'md:text-2xl');
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.queryByText(/开发者详情|debug|raw|schema|trace|provider_timeout|not_enough_history|MarketCache|generatedCandidates|failedCandidates|LLM Ledger|QUOTA PILOT/i)).not.toBeInTheDocument();
  });

  it('exposes a distinct tab composition registry for market overview tabs', () => {
    expect(Object.keys(MARKET_OVERVIEW_TAB_CONFIG)).toEqual(['all', 'us', 'cn', 'global', 'crypto']);
    expect(MARKET_OVERVIEW_TAB_CONFIG.all.pulse).toEqual(expect.arrayContaining(['SPX', 'CSI300', 'HSI', 'BTC', 'VIX', 'US10Y', 'DXY']));
    expect(MARKET_OVERVIEW_TAB_CONFIG.us.pulse).toEqual(expect.arrayContaining(['SPX', 'NDX', 'DJI', 'RUT', 'VIX', 'US10Y', 'DXY']));
    expect(MARKET_OVERVIEW_TAB_CONFIG.cn.pulse).toEqual(expect.arrayContaining(['SHCOMP', 'SZCOMP', 'CSI300', 'HSI', 'HSTECH', 'A50', 'USDCNH']));
    expect(MARKET_OVERVIEW_TAB_CONFIG.global.pulse).toEqual(expect.arrayContaining(['US10Y', 'DXY', 'USDJPY', 'USDCNH', 'GOLD', 'WTI', 'VIX', 'BTC']));
    expect(MARKET_OVERVIEW_TAB_CONFIG.crypto.pulse).toEqual(expect.arrayContaining(['BTC', 'ETH', 'SOL', 'BNB']));
    expect(MARKET_OVERVIEW_TAB_CONFIG.crypto.pulse).not.toEqual(expect.arrayContaining(['SPX', 'CSI300', 'HSI', 'DJI']));
    expect(new Set(MARKET_OVERVIEW_TAB_CONFIG.crypto.modules)).not.toEqual(new Set(MARKET_OVERVIEW_TAB_CONFIG.us.modules));
    expect(MARKET_OVERVIEW_TAB_CONFIG.crypto.modules).toEqual(expect.arrayContaining(['cryptoMomentum', 'cryptoLiquidity', 'cryptoRiskContext']));
  });

  it('switches pulse metrics and primary modules from the tab registry', async () => {
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
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce({
      ...cryptoFullPanel(),
      items: [
        ...cryptoFullPanel().items,
        quoteItem('SOL', 'Solana', 143.2, 1.8, 'binance'),
      ],
    });
    vi.mocked(marketApi.getRates).mockResolvedValueOnce(denseQuotePanel('RatesCard', [
      quoteItem('US10Y', 'US 10Y', 4.62, -0.14),
      quoteItem('US2Y', 'US 2Y', 4.91, 0.04),
      quoteItem('US30Y', 'US 30Y', 4.74, -0.08),
    ]));
    vi.mocked(marketApi.getFxCommodities).mockResolvedValueOnce(denseQuotePanel('FxCommoditiesCard', [
      quoteItem('DXY', 'US Dollar Index', 106.2, 0.2),
      quoteItem('USDJPY', 'USD/JPY', 155.9, 0.1),
      quoteItem('USDCNH', 'USD/CNH', 7.24, 0.2),
      quoteItem('GOLD', 'Gold', 2380.3, 0.5),
      quoteItem('WTI', 'WTI Crude', 78.4, -0.3),
    ]));

    render(<MarketOverviewPage />);

    await screen.findByTestId('market-overview-hero-ribbon');
    expect(getPulseText()).toMatch(/标普500/);
    expect(getPulseText()).toMatch(/沪深300/);
    expect(getPulseText()).toMatch(/恒生指数/);
    expect(getPulseText()).toMatch(/比特币/);

    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    expect(getPulseText()).toMatch(/标普500/);
    expect(getPulseText()).toMatch(/纳斯达克100/);
    expect(getPulseText()).toMatch(/道琼斯工业平均指数/);
    expect(getPulseText()).toMatch(/罗素2000/);
    expect(getPulseText()).not.toMatch(/沪深300|恒生指数|比特币/);
    expect(screen.queryByTestId('market-overview-module-cryptoCore')).not.toBeInTheDocument();
    expect(screen.queryByTestId('market-overview-module-cnBreadth')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    expect(getPulseText()).toMatch(/上证指数/);
    expect(getPulseText()).toMatch(/深证成指/);
    expect(getPulseText()).toMatch(/沪深300/);
    expect(getPulseText()).toMatch(/恒生科技指数/);
    expect(getPulseText()).toMatch(/USD\/CNH/);
    expect(getPulseText()).not.toMatch(/比特币|以太坊|标普500/);
    expect(screen.queryByTestId('market-overview-module-cryptoCore')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '全球宏观' }));
    expect(getPulseText()).toMatch(/美国10年期国债收益率/);
    expect(getPulseText()).toMatch(/美元指数/);
    expect(getPulseText()).toMatch(/USD\/JPY/);
    expect(getPulseText()).toMatch(/黄金/);
    expect(getPulseText()).toMatch(/WTI 原油/);

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));
    expect(getPulseText()).toMatch(/比特币/);
    expect(getPulseText()).toMatch(/以太坊/);
    expect(getPulseText()).toMatch(/Solana/);
    expect(getPulseText()).toMatch(/BNB/);
    expect(getPulseText()).not.toMatch(/标普500|沪深300|恒生指数|道琼斯/);
    expect(screen.getByTestId('market-overview-module-cryptoCore')).toHaveTextContent(/加密核心/);
    expect(screen.getByTestId('market-overview-module-cryptoMomentum')).toHaveTextContent(/加密动量/);
    expect(screen.getByTestId('market-overview-module-cryptoLiquidity')).toHaveTextContent(/BTC 资金费率|未接入/);
    expect(screen.getByTestId('market-overview-module-cryptoRiskContext')).toHaveTextContent(/宏观压力|加密风险上下文/);
    expect(screen.queryByTestId('market-overview-module-cnHkIndices')).not.toBeInTheDocument();
    expect(screen.queryByTestId('market-overview-module-usIndices')).not.toBeInTheDocument();
  });

  it('keeps signal watch and coverage labels tab aware while switching tabs', async () => {
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());
    render(<MarketOverviewPage />);

    await screen.findByTestId('market-overview-rail-signal-watch');
    expect(screen.getByTestId('market-overview-coverage-summary')).toHaveTextContent(/全部数据覆盖/);
    expect(screen.getByTestId('market-overview-rail-signal-watch')).toHaveTextContent(/VIX/);
    expect(screen.getByTestId('market-overview-rail-signal-watch')).toHaveTextContent(/BTC/);

    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    expect(screen.getByTestId('market-overview-coverage-summary')).toHaveTextContent(/美股数据覆盖/);
    expect(screen.getByTestId('market-overview-rail-signal-watch')).toHaveTextContent(/NDX|SPX/);
    expect(screen.getByTestId('market-overview-rail-signal-watch')).not.toHaveTextContent(/HSI/);

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    expect(screen.getByTestId('market-overview-coverage-summary')).toHaveTextContent(/A股\/港股数据覆盖/);
    expect(screen.getByTestId('market-overview-rail-signal-watch')).toHaveTextContent(/CSI300/);
    expect(screen.getByTestId('market-overview-rail-signal-watch')).toHaveTextContent(/USDCNH/);

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));
    expect(screen.getByTestId('market-overview-coverage-summary')).toHaveTextContent(/加密货币数据覆盖/);
    expect(screen.getByTestId('market-overview-rail-signal-watch')).toHaveTextContent(/BTC/);
    expect(screen.getByTestId('market-overview-rail-signal-watch')).toHaveTextContent(/ETH/);
    expect(screen.getByTestId('market-overview-card-cryptoCore')).toBeInTheDocument();
    expect(screen.getByText(/复制摘要|已复制摘要/)).toBeInTheDocument();
  });

  it('uses metric aliases for executive summary cards instead of rendering N/A for explicit backend values', async () => {
    const basePanels = localSnapshotPayload().payload;
    renderMarketOverviewWorkbenchWithProps({
      panels: {
        ...basePanels,
        indices: denseQuotePanel('IndexTrendsCard', [
          quoteItem('^GSPC', 'S&P 500', 5120.25, 0.42),
        ]),
        cnIndices: denseQuotePanel('ChinaIndicesCard', [
          quoteItem('000300.SS', 'CSI 300', 3588.12, 0.44, 'sina'),
        ], 'sina'),
        rates: denseQuotePanel('RatesCard', [
          quoteItem('10Y YIELD', 'US 10Y', 4.62, -0.14),
        ]),
        fxCommodities: denseQuotePanel('FxCommoditiesCard', [
          quoteItem('US DOLLAR INDEX', 'US Dollar Index', 106.2, 0.2),
        ]),
        crypto: denseQuotePanel('CryptoCard', [
          quoteItem('BITCOIN', 'Bitcoin', 67000, 1.5, 'binance'),
        ], 'binance'),
      },
    });

    const usGroup = await screen.findByTestId('market-overview-secondary-group-us');
    const cnGroup = screen.getByTestId('market-overview-secondary-group-cn');
    const macroGroup = screen.getByTestId('market-overview-secondary-group-macro');
    const cryptoGroup = screen.getByTestId('market-overview-secondary-group-crypto');

    expect(usGroup).toHaveTextContent('5,120.25');
    expect(cnGroup).toHaveTextContent('3,588.12');
    expect(macroGroup).toHaveTextContent('4.62');
    expect(cryptoGroup).toHaveTextContent('67,000');
    [usGroup, cnGroup, macroGroup, cryptoGroup].forEach((group) => {
      expect(group).not.toHaveTextContent('N/A');
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
    expect(screen.getByTestId('market-overview-hero-ribbon')).toHaveAttribute('data-linear-primitive', 'key-level-strip');
    expect(screen.getByTestId('market-decision-semantics-strip')).toBeInTheDocument();
    expect(screen.getByTestId('market-decision-semantics-strip')).toHaveTextContent(/市场判断摘要/);
    expect(screen.getByTestId('market-command-chips')).toHaveTextContent(/风险/);
    expect(screen.getByTestId('market-command-chips')).toHaveTextContent(/流动性/);
    expect(screen.getByTestId('market-command-chips').querySelectorAll('[data-terminal-primitive="chip"]').length).toBeGreaterThanOrEqual(3);
    expect(screen.getByTestId('market-decision-semantics-advice-boundary')).toHaveTextContent(/方向判断|方向结论/);
    const details = expandMarketDecisionDetails();
    expect(within(details).getByTestId('market-regime-synthesis-header')).toBeInTheDocument();
    expect(within(details).getByTestId('market-regime-synthesis-title')).toHaveTextContent(/风险偏好修复 \/ 流动性扩张|综合结论待返回/);
    expect(within(details).getByTestId('market-temperature-strip')).toBeInTheDocument();
    expect(within(details).getByTestId('market-briefing-card')).toHaveTextContent(/主要指数走强，VIX 回落|当前真实数据不足/);

    const shell = screen.getByTestId('market-overview-shell');
    const workbench = screen.getByTestId('market-overview-workbench');
    expect(shell).toHaveAttribute('data-bento-surface', 'true');
    expect(shell).toHaveClass(
      'bento-surface-root',
      'w-full',
      'flex',
      'flex-1',
      'min-h-0',
      'min-w-0',
      'flex-col',
      'gap-6',
      'overflow-y-auto',
      'overflow-x-hidden',
      'no-scrollbar',
    );
    expect(shell).not.toHaveClass('py-5', 'md:py-6', 'px-4', 'sm:px-6', 'lg:px-8', '2xl:px-10', 'py-6');
    expect(shell).not.toHaveClass('bg-[#030303]', 'bg-[#050505]');
    expect(shell.className).not.toContain('bg-black');
    expect(shell.className).not.toContain('max-w-[1280px]');
    expect(shell.className).not.toContain('max-w-[1600px]');
    expect(shell.className).not.toContain('max-w-[1800px]');
    expect(shell.parentElement).toHaveAttribute('data-workspace-width', 'near-full');
    expect(workbench).toHaveAttribute('data-terminal-primitive', 'page-shell');
    expect(workbench).toHaveClass(
      'flex',
      'w-full',
      'flex-1',
      'min-h-0',
      'flex-col',
      'gap-5',
      'mx-auto',
      'max-w-[1600px]',
      'px-4',
      'xl:px-8',
      'py-5',
      'md:py-6',
    );
    expect(workbench).not.toHaveClass('overflow-y-auto', 'overflow-x-auto', 'no-scrollbar', 'bg-[#030303]', 'bg-[#050505]');
    expect(workbench.className).not.toContain('bg-black');
    expect(shell.className).not.toContain('max-w-5xl');
    expect(shell.className).not.toContain('max-w-6xl');
    expect(screen.getByTestId('market-overview-category-tabs')).toHaveClass('w-full', 'flex', 'bg-white/[0.02]', 'backdrop-blur-md');
    expect(screen.getByTestId('market-overview-category-tabs')).toHaveClass('min-w-0');
    expect(screen.getByTestId('market-overview-export-summary')).toHaveTextContent('复制摘要');
    expect(screen.getByTestId('market-overview-category-tabs')).not.toHaveClass('sticky', 'top-0', 'z-20', '-mx-4');
    expect(screen.getByTestId('market-overview-top-stack')).toContainElement(screen.getByTestId('market-overview-category-tabs'));
    expect(screen.getByTestId('market-overview-top-stack').firstElementChild).toContainElement(screen.getByTestId('market-decision-semantics-strip'));
    expect(screen.getByTestId('market-overview-category-tabs')).toHaveAttribute('data-selector-position', 'static-safe');
    expect(screen.getByTestId('market-overview-category-tabs').querySelector('.ui-scroll-x-quiet')).not.toBeNull();
    expect(shell).toContainElement(screen.getByTestId('market-overview-category-tabs'));
    expect(shell).toContainElement(screen.getByTestId('market-overview-workbench'));
    expect(shell).toContainElement(screen.getByTestId('market-overview-hero-ribbon'));
    expect(shell).toContainElement(screen.getByTestId('market-data-quality'));
    expect(shell).toContainElement(screen.getByTestId('market-overview-main-grid'));

    expect(await screen.findByTestId('market-overview-main-grid')).toHaveClass('grid', 'grid-cols-1', 'xl:grid-cols-12', 'gap-4', 'items-start');
    expect(screen.getByTestId('market-overview-primary-rail')).toHaveClass('xl:col-span-9', 'flex', 'flex-col');
    expect(screen.getByTestId('market-overview-side-rail')).toHaveClass('xl:col-span-3', 'flex', 'flex-col', 'gap-3');
    expect(screen.getByTestId('market-overview-deep-panels')).toContainElement(screen.getByTestId('market-overview-executive-secondary-groups'));
    expect(screen.getByRole('heading', { name: /全球核心指数走势/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /加密货币行情/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /波动率与风险压力/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /ETF 资金流向/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /A股与港股指数/i })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /宏观经济与流动性/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /市场宽度与赚钱效应/i })).not.toBeInTheDocument();
    expect(screen.getByTestId('market-overview-rail-action-hint')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /同步最新行情/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/同步完成/i)).not.toBeInTheDocument();

    expect(screen.getAllByText(/比特币/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/标普500/i).length).toBeGreaterThan(0);
    expect(screen.queryByText('pts')).not.toBeInTheDocument();

    expect(screen.getAllByTestId('market-overview-sparkline').length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText(/Log:/i)).not.toBeInTheDocument();
    expect(screen.queryAllByTestId('market-overview-fallback-only-notice')).toHaveLength(0);
    expect(screen.getByTestId('market-data-quality')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-rail-quality')).toHaveTextContent(/数据质量：部分备用/i);
    expect(screen.queryAllByTestId('market-overview-compact-error-badge').length).toBeLessThanOrEqual(2);
    expect(screen.getAllByTestId('data-freshness-badge-fallback').length).toBeGreaterThan(0);
    expect(screen.getAllByTestId('data-freshness-badge-cache').length).toBeGreaterThan(0);
    await waitFor(() => expect(marketOverviewApi.getMacro).toHaveBeenCalledTimes(1));
  });

  it('hydrates market overview from localStorage before backend responses settle', async () => {
    window.localStorage.setItem(MARKET_OVERVIEW_LKG_STORAGE_KEY, JSON.stringify(localSnapshotPayload()));
    vi.mocked(marketOverviewApi.getIndices).mockReturnValueOnce(new Promise(() => {}));

    render(<MarketOverviewPage />);

    expect((await screen.findAllByText('5,111.11')).length).toBeGreaterThan(0);
    const details = expandMarketDecisionDetails();
    expect(within(details).getByTestId('market-overview-cache-status')).toHaveTextContent(/刷新中/i);
    expect(within(details).getByTestId('market-overview-cache-status')).not.toHaveTextContent(/LOCAL CACHE/i);
    expect(within(details).getByTestId('market-overview-cache-status')).toHaveTextContent(/更新时间/i);
    expect(screen.queryByText(/indices request timed out/i)).not.toBeInTheDocument();
  });

  it('persists latest usable backend data to the market overview local snapshot', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValueOnce(denseQuotePanel('IndexTrendsCard', [
      quoteItem('SPX', 'S&P 500', 5222.22, 0.52),
    ]));

    render(<MarketOverviewPage />);

    await waitFor(() => {
      const saved = JSON.parse(window.localStorage.getItem(MARKET_OVERVIEW_LKG_STORAGE_KEY) || '{}');
      expect(saved.payload?.indices?.items?.[0]?.value).toBe(5222.22);
    });
    const saved = JSON.parse(window.localStorage.getItem(MARKET_OVERVIEW_LKG_STORAGE_KEY) || '{}');
    expect(saved.schemaVersion).toBe(1);
    expect(saved.payload.indices.items[0].value).toBe(5222.22);
    expect(JSON.stringify(saved)).not.toContain('request timed out');
  });

  it('keeps local snapshot visible when backend refresh fails and keeps errors compact', async () => {
    window.localStorage.setItem(MARKET_OVERVIEW_LKG_STORAGE_KEY, JSON.stringify(localSnapshotPayload()));
    vi.mocked(marketOverviewApi.getIndices).mockRejectedValueOnce(new Error('indices request timed out'));
    vi.mocked(marketApi.getRates).mockRejectedValueOnce(new Error('rates request timed out'));

    render(<MarketOverviewPage />);

    expect((await screen.findAllByText('5,111.11')).length).toBeGreaterThan(0);
    const details = expandMarketDecisionDetails();
    await waitFor(() => expect(within(details).getByTestId('market-overview-cache-status')).toHaveTextContent(/待刷新|部分外部数据暂不可用|备用数据/i));
    expect(within(details).getByTestId('market-overview-cache-status')).not.toHaveTextContent(/REFRESH FAILED|CACHE|STALE|ERROR/i);
    expect(screen.getAllByText('标普500').length).toBeGreaterThan(0);
    expect(screen.queryByText(/更新失败：indices request timed out/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/provider_down|provider_error|UNKNOWN/i)).not.toBeInTheDocument();
    expect(within(details).getByTestId('market-overview-data-state-unavailable-chip')).toHaveTextContent(/部分外部数据暂不可用/);
    expect(within(details).getByTestId('market-overview-data-state-unavailable-chip')).toHaveAttribute('data-terminal-primitive', 'chip');
  });

  it('stages noncritical market overview panels after the primary route data starts loading', async () => {
    vi.useFakeTimers();

    render(<MarketOverviewPage />);

    expect(countMarketPanelRequests()).toBe(10);
    expectMarketPanelRequestsCalledOnce(primaryMarketPanelRequests);
    expectMarketPanelRequestsNotCalled([
      ...firstStagedMarketPanelRequests,
      ...secondStagedMarketPanelRequests,
    ]);
    expect(MockEventSource.instances).toHaveLength(1);

    await act(async () => {
      vi.advanceTimersByTime(250);
      await Promise.resolve();
    });

    expect(countMarketPanelRequests()).toBe(13);
    expectMarketPanelRequestsCalledOnce([
      ...primaryMarketPanelRequests,
      ...firstStagedMarketPanelRequests,
    ]);
    expectMarketPanelRequestsNotCalled(secondStagedMarketPanelRequests);

    await act(async () => {
      vi.advanceTimersByTime(400);
      await Promise.resolve();
    });

    expect(countMarketPanelRequests()).toBe(17);
    expectMarketPanelRequestsCalledOnce(allMarketPanelRequests);
    expect(MockEventSource.instances).toHaveLength(1);
  });

  it('dedupes route-entry market requests and the crypto stream under React StrictMode', async () => {
    vi.useFakeTimers();

    render(
      <StrictMode>
        <MarketOverviewPage />
      </StrictMode>,
    );

    expect(countMarketPanelRequests()).toBe(10);
    expectMarketPanelRequestsCalledOnce(primaryMarketPanelRequests);
    expectMarketPanelRequestsNotCalled([
      ...firstStagedMarketPanelRequests,
      ...secondStagedMarketPanelRequests,
    ]);

    await act(async () => {
      vi.advanceTimersByTime(250);
      await Promise.resolve();
    });

    expect(countMarketPanelRequests()).toBe(13);
    expectMarketPanelRequestsCalledOnce([
      ...primaryMarketPanelRequests,
      ...firstStagedMarketPanelRequests,
    ]);
    expectMarketPanelRequestsNotCalled(secondStagedMarketPanelRequests);

    await act(async () => {
      vi.advanceTimersByTime(400);
      await Promise.resolve();
    });

    expect(countMarketPanelRequests()).toBe(17);
    expectMarketPanelRequestsCalledOnce(allMarketPanelRequests);
    expect(MockEventSource.instances).toHaveLength(1);
  });

  it('renders a stable MarketMonitor skeleton with grouped deep panels and collapsed diagnostics', async () => {
    render(<MarketOverviewPage />);

    expect(await screen.findByTestId('market-overview-pulse-header')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-category-tabs')).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-market-monitor')).toBeInTheDocument();
    expect(screen.getByTestId('market-decision-semantics-strip')).toBeInTheDocument();

    const mainGrid = screen.getByTestId('market-overview-main-grid');
    const primaryRail = screen.getByTestId('market-overview-primary-rail');
    const sideRail = screen.getByTestId('market-overview-side-rail');

    expect(mainGrid).toHaveAttribute('data-market-monitor-layout', 'board-plus-context');
    expect(primaryRail).toHaveClass('flex', 'flex-col');
    expect(primaryRail).not.toHaveClass('overflow-x-auto', 'stealth-scrollbar');
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-runtime-details'));
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-signal-disclosure'));
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-action-disclosure'));
    expect(screen.getByRole('button', { name: '展开 技术细节 / Details' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '展开 关键观测' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '展开 观察提示' })).toBeInTheDocument();
    expect(screen.getByTestId('market-overview-deep-panels')).toContainElement(screen.getByTestId('market-overview-executive-secondary-groups'));
  });

  it('renders compact diagnostic disclosures instead of always-open rail cards', async () => {
    render(<MarketOverviewPage />);

    const sideRail = await screen.findByTestId('market-overview-side-rail');
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-runtime-details'));
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-signal-disclosure'));
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-action-disclosure'));
    expect(within(sideRail).getAllByRole('button', { name: /展开/i })).toHaveLength(3);
    expect(screen.queryByTestId('market-overview-compact-rail-card')).not.toBeInTheDocument();
    expect(screen.queryByTestId('market-overview-fallback-section')).not.toBeInTheDocument();
  });

  it('keeps mobile DOM order with data state ahead of the overview summary', async () => {
    render(<MarketOverviewPage />);

    await screen.findByTestId('market-overview-workbench');
    expect(screen.getByTestId('market-overview-top-stack').firstElementChild).toContainElement(
      screen.getByTestId('market-decision-semantics-strip'),
    );
    expect(screen.getByTestId('market-overview-top-stack')).toContainElement(screen.getByTestId('market-overview-category-tabs'));
    expect(screen.getByTestId('market-overview-top-stack')).toContainElement(screen.getByTestId('market-overview-hero-ribbon'));
  });

  it('puts market state and compact data status ahead of controls and panel sprawl', async () => {
    render(<MarketOverviewPage />);

    const topStack = await screen.findByTestId('market-overview-top-stack');
    expect(topStack.firstElementChild).toContainElement(screen.getByTestId('market-decision-semantics-strip'));
    expect(topStack.querySelectorAll('[data-market-research-flow="decision-semantics"]')).toHaveLength(1);
    expect(screen.getByTestId('market-overview-main-grid').compareDocumentPosition(screen.getByTestId('market-decision-semantics-strip'))).toBe(Node.DOCUMENT_POSITION_PRECEDING);
  });

  it('renders each tab with deterministic row groups and the shared decision layer', async () => {
    render(<MarketOverviewPage />);

    const expectations: Array<[string, string[], string[]]> = [
      ['全部', ['all-hero', 'all-modules-1', 'all-modules-2', 'all-modules-3', 'all-modules-4'], ['market-overview-card-indices', 'market-overview-card-sentiment']],
      ['美股', ['us-hero', 'us-modules-1', 'us-modules-2', 'us-modules-3'], ['market-overview-card-indices', 'market-overview-card-usBreadth']],
      ['A股/港股', ['cn-hero', 'cn-modules-1', 'cn-modules-2', 'cn-modules-3'], ['market-overview-card-cnIndices', 'market-overview-card-cnShortSentiment']],
      ['全球宏观', ['global-hero', 'global-modules-1', 'global-modules-2'], ['market-overview-card-rates', 'market-overview-card-globalRisk']],
      ['加密货币', ['crypto-hero', 'crypto-modules-1', 'crypto-modules-2'], ['market-overview-card-cryptoCore', 'market-overview-card-cryptoLiquidity']],
    ];

    for (const [tab, rowIds, visibleCards] of expectations) {
      fireEvent.click(await screen.findByRole('button', { name: tab }));
      const heroLane = await screen.findByTestId('market-overview-hero-lane');
      const secondaryGrid = screen.getByTestId('market-overview-secondary-grid');
      visibleCards.forEach((testId) => {
        expect(screen.getByTestId(testId)).toBeInTheDocument();
      });
      expect(getRowIds()).toEqual(rowIds);
      expect(screen.getByTestId('market-decision-semantics-strip')).toBeInTheDocument();
      expect(heroLane).toHaveAttribute('data-card-tier', 'hero');
      expect(secondaryGrid).toHaveAttribute('data-card-tier', 'secondary');
      if (tab === '全部' || tab === '美股' || tab === 'A股/港股') {
        expect(screen.getByTestId('market-overview-deep-panels')).toHaveAttribute('data-card-tier', 'deep');
      } else {
        expect(screen.queryByTestId('market-overview-deep-panels')).not.toBeInTheDocument();
      }
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
    await waitFor(() => {
      expect(within(indicesCard).getAllByTestId('market-overview-dense-quote-item').length).toBeGreaterThan(0);
    });
    const firstQuote = within(indicesCard).getAllByTestId('market-overview-dense-quote-item')[0];
    const metadata = within(firstQuote).getByTestId('market-overview-quote-metadata');
    const valueBlock = within(firstQuote).getByTestId('market-overview-quote-value');
    const changeBlock = within(firstQuote).getByTestId('market-overview-quote-change');

    expect(metadata).toHaveAttribute('data-metadata-position', 'middle-left');
    expect(metadata).toHaveClass('col-start-2', 'whitespace-nowrap', 'overflow-hidden');
    expect(metadata).not.toHaveClass('col-span-3', 'justify-end');
    expect(metadata).toHaveTextContent(/2026/);
    expect(metadata).not.toHaveTextContent(/Yahoo Finance/);
    expect(metadata).not.toHaveTextContent(/Quote/);
    expect(metadata).not.toHaveTextContent(/Update/);
    expect(metadata).toHaveAttribute('title', expect.stringContaining('Yahoo Finance'));
    expect(valueBlock).toHaveClass('col-start-4', 'text-right');
    expect(changeBlock).toHaveClass('col-start-5', 'text-right');
  });

  it('copies a market overview summary from the current visible state', async () => {
    render(<MarketOverviewPage />);

    const exportButton = await screen.findByTestId('market-overview-export-summary');
    await waitFor(() => expect(screen.getByTestId('market-decision-semantics-strip')).toHaveTextContent('风险偏暖'));
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

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    const cnIndicesCard = await screen.findByTestId('market-overview-card-cnIndices');
    await waitFor(() => {
      expect(within(cnIndicesCard).getByText('上证指数')).toBeInTheDocument();
      expect(within(cnIndicesCard).getByText('深证成指')).toBeInTheDocument();
      expect(within(cnIndicesCard).getByText('沪深300')).toBeInTheDocument();
      expect(within(cnIndicesCard).getByText('恒生指数')).toBeInTheDocument();
      expect(within(cnIndicesCard).getByText('恒生科技指数')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));
    const cryptoCard = await screen.findByTestId('market-overview-card-cryptoCore');
    await waitFor(() => {
      expect(within(cryptoCard).getByText('比特币')).toBeInTheDocument();
      expect(within(cryptoCard).getByText('以太坊')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '全球宏观' }));
    await waitFor(() => {
      expect(screen.getAllByText('美国10年期国债收益率').length).toBeGreaterThan(0);
      expect(screen.getAllByText('美元指数').length).toBeGreaterThan(0);
      expect(screen.getAllByText('黄金').length).toBeGreaterThan(0);
      expect(screen.getAllByText('WTI 原油').length).toBeGreaterThan(0);
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
    expect(await screen.findByTestId('market-overview-direction-summary')).toHaveTextContent('Market Bias / Direction Summary');
    expect(screen.getByTestId('market-overview-direction-summary')).toHaveTextContent('Current market:');
    fireEvent.click(screen.getByRole('button', { name: 'US' }));
    expect(screen.getAllByText('Nasdaq 100').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Bitcoin').length).toBeGreaterThan(0);
    expect(screen.queryByText('标普500')).not.toBeInTheDocument();
    expect(screen.queryByText('比特币')).not.toBeInTheDocument();
  });

  it('renders a top directional summary for mixed low-confidence evidence', async () => {
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce(limitedRealTemperaturePayload());
    vi.mocked(marketApi.getMarketBriefing).mockResolvedValueOnce(unreliableBriefingPayload());

    render(<MarketOverviewPage />);

    const summary = await screen.findByTestId('market-overview-direction-summary');
    expect(summary).toHaveTextContent('Market Bias / Direction Summary');
    expect(summary).toHaveTextContent('当前市场：证据不足');
    expect(summary).toHaveTextContent('证据强度：低');
    expect(summary).toHaveTextContent('不支持强方向判断');
    expect(summary).toHaveTextContent('主要拖累');
    expect(summary).toHaveTextContent('A股宽度');
    expect(summary).toHaveTextContent('比特币');
    expect(summary).toHaveTextContent('可观察方向');
    expect(summary.textContent || '').not.toMatch(/买入|卖出|加仓|减仓|仓位|建议买入|建议卖出|buy now|sell now|recommend/i);
    expect(summary.textContent || '').not.toMatch(/marketOverviewPage\./);
  });

  it('downgrades unreliable market temperature and briefing copy', async () => {
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce(unreliableTemperaturePayload());
    vi.mocked(marketApi.getMarketBriefing).mockResolvedValueOnce(unreliableBriefingPayload());

    render(<MarketOverviewPage />);

    const details = expandMarketDecisionDetails();
    await waitFor(() => {
      expect(within(details).getByTestId('market-overview-temperature-summary')).toHaveTextContent('可靠输入不足');
    });
    const temperatureSummary = within(details).getByTestId('market-overview-temperature-summary');
    expect(temperatureSummary).toHaveTextContent('可靠输入不足');
    expect(temperatureSummary).toHaveTextContent('暂不判定');
    expect(temperatureSummary).not.toHaveTextContent('N/A');
    expect(within(details).getByTestId('market-temperature-unreliable-summary')).toHaveTextContent('可靠输入不足，暂不生成综合判断');
    expect(within(details).getByText(/可靠输入不足，暂不生成综合判断/i)).toBeInTheDocument();
    expect(within(details).getByText(/信号可信：数据不足/i)).toBeInTheDocument();
    expect(screen.queryByText(/综合市场温度/i)).not.toBeInTheDocument();
    expect(within(details).getByTestId('market-regime-synthesis-title')).toHaveTextContent('数据不足');
    expect(within(details).getByTestId('market-regime-synthesis-state-chip')).toHaveTextContent('数据不足');
    expect(within(details).getByTestId('market-regime-synthesis-confidence-chip')).toHaveTextContent('数据不足 · 22%');
    expect(within(details).getByTestId('market-regime-synthesis-summary')).toHaveTextContent('当前覆盖或置信度不足');
    expect(within(details).getByTestId('market-regime-synthesis-data-gaps')).toHaveTextContent(/A股宽度/);
    expect(screen.getByTestId('market-overview-rail-action-hint')).toHaveTextContent(/优先观察已验证信号，暂不生成强判断|等待刷新完成后再生成强判断|部分关键面板暂不可用，暂不生成强判断/i);
    expect(within(details).getByTestId('market-briefing-warning')).toHaveTextContent('当前真实数据不足，暂不生成强市场判断');
    expect(screen.getByTestId('market-decision-semantics-advice-boundary')).toHaveTextContent(/当前不能形成可靠方向判断|当前暂不形成方向结论/);
  });

  it('renders a compact observational posture panel from market decision semantics', async () => {
    render(<MarketOverviewPage />);

    const posturePanel = await screen.findByTestId('market-decision-semantics-strip');

    expect(posturePanel).toHaveTextContent('市场判断摘要');
    expect(posturePanel).toHaveTextContent('支持证据');
    expect(posturePanel).toHaveTextContent('反证 / 风险');
    expect(posturePanel).toHaveTextContent('缺失证据');
    expect(posturePanel).toHaveTextContent('下一步观察');
    expect(posturePanel).toHaveTextContent('Liquidity beta watch');
    expect(posturePanel).toHaveTextContent('Liquidity impulse should remain expanding.');
    expect(posturePanel).toHaveTextContent('Remove the risk-on watch if liquidity turns mixed or contracting.');
    expect(posturePanel).not.toHaveTextContent('liquidity_stops_expanding');
    expect(posturePanel).toHaveTextContent('US10Y');
    expect(posturePanel).toHaveTextContent('Fed liquidity');
    expect(posturePanel).toHaveTextContent('非投资建议');
    expect(posturePanel).not.toHaveTextContent('counter_evidence_present');
    expect(posturePanel).not.toHaveTextContent('not_investment_advice');
    expect(posturePanel).toHaveTextContent('可计分证据 3');
    expect(posturePanel).toHaveTextContent('观察证据 0');
    expect(posturePanel).toHaveTextContent('缺失证据 0');

    const debug = within(posturePanel).getByTestId('market-decision-debug-details');
    expect(debug).not.toHaveAttribute('open');
    fireEvent.click(within(debug).getByRole('button', { name: '展开 技术细节 / Details' }));
    const readinessStrip = within(posturePanel).getByTestId('market-direction-readiness-strip');
    expect(readinessStrip).toHaveTextContent('方向可用');
    expect(readinessStrip).toHaveTextContent('评分级 3');
    expect(readinessStrip).toHaveTextContent('观察级 0');
    expect(readinessStrip).toHaveTextContent('缺口 0');
    expect(readinessStrip).toHaveTextContent('Official macro/rates/volatility');
    expect(debug).toHaveTextContent('counter_evidence_present');
    expect(debug).toHaveTextContent('not_investment_advice');
  });

  it('keeps data-insufficient posture conservative without trading advice language', async () => {
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce(unreliableTemperaturePayload());
    vi.mocked(marketApi.getMarketBriefing).mockResolvedValueOnce(unreliableBriefingPayload());

    render(<MarketOverviewPage />);

    const posturePanel = await screen.findByTestId('market-decision-semantics-strip');
    const text = posturePanel.textContent || '';

    expect(posturePanel).toHaveTextContent(/方向不可用|暂不形成方向结论/);
    expect(posturePanel).toHaveTextContent('当前不能形成可靠方向判断');
    expect(posturePanel).toHaveTextContent('当前可靠证据不足');
    expect(posturePanel).toHaveTextContent('缺少评分级证据');
    expect(posturePanel).toHaveTextContent(/观察证据|仅作观察|需要权威来源/);
    expect(posturePanel).not.toHaveTextContent('missing_scoring_pillars');
    expect(posturePanel).toHaveTextContent('BTC');
    const debug = within(posturePanel).getByTestId('market-decision-debug-details');
    fireEvent.click(within(debug).getByRole('button', { name: '展开 技术细节 / Details' }));
    expect(within(posturePanel).getByTestId('market-direction-readiness-strip')).toHaveTextContent('数据不足');
    expect(within(posturePanel).getByTestId('market-direction-readiness-reasons')).toHaveTextContent('缺少评分级证据');
    expect(within(posturePanel).getByTestId('market-direction-readiness-reasons')).not.toHaveTextContent('fallback_proxy_or_observation_only_evidence_present');
    expect(text).not.toMatch(/买入|卖出|加仓|减仓|仓位|看多|看空|bullish|bearish|buy|sell|add|reduce|position-size/i);
  });

  it('shows a missing synthesis fallback when the temperature payload omits the additive field', async () => {
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce({
      source: 'computed',
      sourceLabel: '系统计算',
      updatedAt: '2026-04-29T10:00:00',
      asOf: '2026-04-29T10:00:00',
      freshness: 'cached',
      isFallback: false,
      confidence: 0.18,
      reliableInputCount: 1,
      requiredReliableInputCount: 5,
      reliablePanelCount: 1,
      requiredReliablePanelCount: 3,
      fallbackInputCount: 3,
      excludedInputCount: 2,
      isReliable: false,
      temperatureAvailable: false,
      disabledReason: 'insufficient_reliable_inputs',
      unavailableReason: 'insufficient_reliable_inputs',
      insufficientReliableInputs: true,
      trustLevel: 'weak',
      sourceTier: 'unofficial_public_api',
      conclusionAllowed: false,
      scores: {
        liquidity: { value: 51, label: '中性', trend: 'stable', description: '流动性输入部分可用。' },
      },
    } as never);

    render(<MarketOverviewPage />);

    expect(await screen.findByTestId('market-overview-shell')).toBeInTheDocument();
    const details = expandMarketDecisionDetails();
    expect(within(details).getByTestId('market-temperature-unreliable-summary')).toHaveTextContent('可靠输入不足，暂不生成综合判断');
    expect(within(details).getByTestId('market-overview-temperature-summary')).toHaveTextContent(/可靠输入不足|暂不判定/);
    expect(within(details).getByTestId('market-overview-temperature-summary')).not.toHaveTextContent('N/A');
    expect(screen.getByTestId('market-decision-semantics-advice-boundary')).toHaveTextContent(/当前不能形成可靠方向判断|当前暂不形成方向结论/);
    expect(within(details).getByTestId('market-regime-synthesis-title')).toHaveTextContent('综合结论待返回');
    expect(within(details).getByTestId('market-regime-synthesis-state-chip')).toHaveTextContent('载荷缺失');
    expect(within(details).getByTestId('market-regime-synthesis-confidence-chip')).toHaveTextContent('未返回');
    expect(within(details).queryByTestId('market-regime-synthesis-regime-chip')).not.toBeInTheDocument();
    expect(within(details).getByTestId('market-regime-synthesis-top-drivers')).toHaveTextContent('暂无可展示驱动');
    expect(screen.queryByText(/raw|payload/i)).not.toBeInTheDocument();
  });

  it('keeps the reliable-inputs fallback copy when additive flags are omitted but counts are still insufficient', async () => {
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce({
      source: 'computed',
      sourceLabel: '系统计算',
      updatedAt: '2026-04-29T10:00:00',
      asOf: '2026-04-29T10:00:00',
      freshness: 'cached',
      isFallback: false,
      confidence: 0.18,
      reliableInputCount: 1,
      requiredReliableInputCount: 5,
      reliablePanelCount: 1,
      requiredReliablePanelCount: 3,
      fallbackInputCount: 3,
      excludedInputCount: 2,
      isReliable: false,
      temperatureAvailable: false,
      trustLevel: 'weak',
      sourceTier: 'unofficial_public_api',
      conclusionAllowed: false,
      scores: {
        liquidity: { value: 51, label: '中性', trend: 'stable', description: '流动性输入部分可用。' },
      },
    } as never);

    render(<MarketOverviewPage />);

    expect(await screen.findByTestId('market-overview-shell')).toBeInTheDocument();
    const details = expandMarketDecisionDetails();
    expect(within(details).getByTestId('market-temperature-unreliable-summary')).toHaveTextContent('可靠输入不足，暂不生成综合判断');
    expect(within(details).getByTestId('market-overview-temperature-summary')).not.toHaveTextContent('N/A');
  });

  it('shows limited real temperature inputs instead of collapsing them to zero', async () => {
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce(limitedRealTemperaturePayload());

    render(<MarketOverviewPage />);

    const details = expandMarketDecisionDetails();
    const summary = await within(details).findByTestId('market-temperature-unreliable-summary');
    expect(summary).toHaveTextContent('可靠输入不足，暂不生成综合判断');
    await waitFor(() => {
      expect(summary).toHaveTextContent('可靠输入不足，暂不生成综合判断');
      expect(within(details).getByTestId('market-temperature-strip')).toHaveTextContent(/真实 2.*备用 10.*排除 10/i);
    });
    expect(screen.queryByText(/R 0/i)).not.toBeInTheDocument();
  });

  it('does not overstate top status when delayed and proxy panels are mostly usable', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValueOnce(denseQuotePanel('IndexTrendsCard', [
      quoteItem('SPX', 'S&P 500', 5120.25, 0.42),
      quoteItem('NDX', 'Nasdaq 100', 18220.42, 0.68),
      quoteItem('DJI', 'Dow Jones', 38920.18, -0.12),
    ]));
    vi.mocked(marketOverviewApi.getVolatility).mockResolvedValueOnce(denseQuotePanel('VolatilityCard', [
      quoteItem('VIX', 'VIX', 14.8, -2.4),
      quoteItem('VVIX', 'VVIX', 88.2, -1.1),
    ]));
    vi.mocked(marketOverviewApi.getFundsFlow).mockResolvedValueOnce(denseQuotePanel('FundsFlowCard', [
      quoteItem('SPY_FLOW', 'SPY Flow', 2.1, 2.1),
      quoteItem('QQQ_FLOW', 'QQQ Flow', 1.7, 1.7),
    ], 'yahoo'));
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce(denseQuotePanel('ChinaIndicesCard', [
      quoteItem('000300.SH', 'CSI 300', 3588.12, 0.44, 'sina'),
      quoteItem('HSI', 'Hang Seng Index', 17712.5, 0.73, 'sina'),
      {
        ...quoteItem('HSTECH', 'Hang Seng TECH', 3650.1, 0.62, 'fallback'),
        source: 'fallback',
        sourceLabel: '备用数据',
        freshness: 'fallback' as const,
        isFallback: true,
      },
    ], 'mixed'));
    vi.mocked(marketApi.getRates).mockResolvedValueOnce(denseQuotePanel('RatesCard', [
      quoteItem('US10Y', 'US 10Y', 4.62, -0.14, 'fred'),
      quoteItem('US2Y', 'US 2Y', 4.91, 0.04, 'fred'),
      quoteItem('US30Y', 'US 30Y', 4.74, -0.08, 'treasury'),
    ], 'fred'));
    vi.mocked(marketApi.getFxCommodities).mockResolvedValueOnce(denseQuotePanel('FxCommoditiesCard', [
      quoteItem('DXY', 'US Dollar Index', 106.2, 0.2, 'yfinance_proxy'),
      quoteItem('USDJPY', 'USD/JPY', 155.9, 0.1, 'yfinance_proxy'),
      {
        ...quoteItem('USDCNH', 'USD/CNH', 7.24, 0.2, 'fallback'),
        source: 'fallback',
        sourceLabel: '备用数据',
        freshness: 'fallback' as const,
        isFallback: true,
      },
    ], 'mixed'));
    vi.mocked(marketApi.getUsBreadth).mockResolvedValueOnce(usBreadthPanel());
    vi.mocked(marketApi.getTemperature).mockResolvedValueOnce(limitedRealTemperaturePayload());
    vi.mocked(marketApi.getMarketBriefing).mockResolvedValueOnce(unreliableBriefingPayload());

    render(<MarketOverviewPage />);

    expect(await screen.findByTestId('market-decision-semantics-advice-boundary')).toHaveTextContent('当前不能形成可靠方向判断');
    expect(screen.getByTestId('market-decision-semantics-strip')).toHaveTextContent('当前可见信号包含延迟、代理或缺失项');
    expect(screen.getByTestId('market-overview-rail-action-hint')).not.toHaveTextContent(/等待实时源补齐后再生成强判断/);
  });

  it('keeps a warning top status when visible panels are fallback-heavy', async () => {
    renderMarketOverviewWorkbenchWithProps({
      panels: {
        indices: snapshotPanel('IndexTrendsCard', 'SPX', 'S&P 500'),
        volatility: snapshotPanel('VolatilityCard', 'VIX', 'VIX'),
        crypto: snapshotPanel('CryptoCard', 'BTC', 'Bitcoin'),
        sentiment: snapshotPanel('MarketSentimentCard', 'FGI', 'Fear & Greed'),
        fundsFlow: snapshotPanel('FundsFlowCard', 'ETF', 'ETF'),
        macro: snapshotPanel('MacroIndicatorsCard', 'US10Y', 'US 10Y'),
        cnIndices: snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300'),
        cnBreadth: snapshotPanel('ChinaBreadthCard', 'BREADTH', '赚钱效应'),
        cnFlows: snapshotPanel('ChinaFlowsCard', 'NORTHBOUND', '北向资金'),
        sectorRotation: snapshotPanel('SectorRotationCard', 'AI', 'AI / 算力'),
        usBreadth: usBreadthUnavailablePanel(),
        rates: snapshotPanel('RatesCard', 'US10Y', 'US 10Y'),
        fxCommodities: snapshotPanel('FxCommoditiesCard', 'DXY', 'DXY'),
        temperature: unreliableTemperaturePayload(),
        briefing: unreliableBriefingPayload(),
        futures: futuresPayload(),
        cnShortSentiment: cnShortSentimentPayload(),
      },
    });

    expect(screen.getByTestId('market-decision-semantics-advice-boundary')).toHaveTextContent('当前不能形成可靠方向判断');
    expect(screen.getByTestId('market-decision-semantics-strip')).toHaveTextContent('关键面板暂不可用');
  });

  it('uses a refresh-state top status only while the overview is truly refreshing', async () => {
    renderMarketOverviewWorkbenchWithProps({
      loading: true,
      panels: {
        ...localSnapshotPayload({
          indices: snapshotPanel('IndexTrendsCard', 'SPX', 'S&P 500'),
          volatility: snapshotPanel('VolatilityCard', 'VIX', 'VIX'),
          crypto: snapshotPanel('CryptoCard', 'BTC', 'Bitcoin'),
          fundsFlow: snapshotPanel('FundsFlowCard', 'ETF', 'ETF'),
          macro: snapshotPanel('MacroIndicatorsCard', 'US10Y', 'US 10Y'),
          cnIndices: snapshotPanel('ChinaIndicesCard', 'CSI300', '沪深300'),
          cnBreadth: snapshotPanel('ChinaBreadthCard', 'BREADTH', '赚钱效应'),
          cnFlows: snapshotPanel('ChinaFlowsCard', 'NORTHBOUND', '北向资金'),
          sectorRotation: snapshotPanel('SectorRotationCard', 'AI', 'AI / 算力'),
          usBreadth: usBreadthUnavailablePanel(),
          rates: snapshotPanel('RatesCard', 'US10Y', 'US 10Y'),
          fxCommodities: snapshotPanel('FxCommoditiesCard', 'DXY', 'DXY'),
          temperature: unreliableTemperaturePayload(),
          briefing: unreliableBriefingPayload(),
          futures: futuresPayload(),
          cnShortSentiment: cnShortSentimentPayload(),
        }).payload,
      },
    });

    expect(screen.getByTestId('market-decision-semantics-advice-boundary')).toHaveTextContent('当前不能形成可靠方向判断');
    expect(screen.getByTestId('market-decision-semantics-strip')).toHaveTextContent('关键实时源仍在刷新');
    const details = expandMarketDecisionDetails();
    expect(within(details).getByTestId('market-overview-cache-status')).toHaveTextContent(/刷新中/i);
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
    expect(getRowCardOrder('all-hero')).toEqual(['indices']);
    expect(screen.getByTestId('market-overview-card-indices')).toHaveAttribute('data-market-card-row', 'hero');
    expect(screen.getByTestId('market-overview-secondary-group-cn')).toHaveClass('min-w-0');
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
    for (const cardKey of ['indices', 'crypto'] as const) {
      const card = await screen.findByTestId(`market-overview-card-${cardKey}`);
      if (cardKey === 'indices') {
        expect(primaryRail).toContainElement(card);
      } else {
        expect(screen.getByTestId('market-overview-deep-panels')).toContainElement(card);
      }
      expect(card).toHaveAttribute('data-market-card-size', cardKey === 'indices' ? 'large' : 'list');
      expect(card).toHaveAttribute('data-market-card-density', 'dense-quote');
      const grid = within(card).getByTestId('market-overview-dense-quote-grid');
      expect(grid).toHaveClass('flex', 'flex-col', 'border-y');
      expect(within(grid).getAllByTestId('market-overview-dense-quote-item').length).toBeGreaterThanOrEqual(2);
    }

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    const cnIndicesCard = await screen.findByTestId('market-overview-card-cnIndices');
    expect(screen.getByTestId('market-overview-hero-lane')).toContainElement(cnIndicesCard);
    expect(cnIndicesCard).toHaveAttribute('data-market-card-size', 'large');
  });

  it('uses compact quote item grids without a flexible empty sparkline region', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockResolvedValueOnce(denseQuotePanel('IndexTrendsCard', [
      quoteItem('SPX', 'S&P 500', 5120.25, 0.42),
      quoteItem('NDX', 'Nasdaq 100', 18220.42, 0.68),
    ]));

    render(<MarketOverviewPage />);

    const indicesCard = await screen.findByTestId('market-overview-card-indices');
    const firstQuote = await waitFor(() => within(indicesCard).getAllByTestId('market-overview-dense-quote-item')[0]);
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
    expect(within(firstQuote).getByTestId('data-freshness-badge-cache')).toBeInTheDocument();
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
    expect(sideRail).not.toContainElement(screen.queryByTestId('market-overview-card-cnIndices'));
    expect(sideRail).not.toContainElement(screen.getByTestId('market-overview-card-crypto'));
    expect(sideRail).toContainElement(screen.getByTestId('market-data-quality'));
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-rail-signal-watch'));
    expect(sideRail).toContainElement(screen.getByTestId('market-overview-rail-action-hint'));
    expect(sideRail).not.toContainElement(screen.queryByTestId('market-briefing-card'));
    expect(screen.getByTestId('market-overview-signal-disclosure')).toBeInTheDocument();
    expect(sideRail.className).not.toContain('max-h');
    expect(sideRail.className).not.toContain('overflow-y-auto');
  });

  it('keeps temperature and briefing summaries compact while moving data quality into the data-state strip', async () => {
    render(<MarketOverviewPage />);

    const details = expandMarketDecisionDetails();
    const statusStrip = within(details).getByTestId('market-overview-status-strip');
    expect(statusStrip).toHaveClass('grid', 'grid-cols-1', 'gap-3');
    expect(statusStrip).toContainElement(within(details).getByTestId('market-overview-temperature-summary'));
    expect(statusStrip).toContainElement(within(details).getByTestId('market-overview-briefing-summary'));
    expect(within(details).getByTestId('market-temperature-strip')).toBeInTheDocument();
    expect(statusStrip).toContainElement(await within(details).findByTestId('market-temperature-strip'));
    expect(statusStrip).toContainElement(within(details).getByTestId('market-briefing-card'));
    expect(within(details).getByTestId('market-overview-data-state-strip')).toHaveTextContent(/数据状态/);
    expect(within(details).getByTestId('market-overview-data-state-strip')).toHaveTextContent(/备用数据/);
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
    expect(getRowCardOrder('us-hero')).toEqual(['indices']);
    expect(getRowCardOrder('us-modules-1')).toEqual(['volatility', 'usRates']);
    expect(within(screen.getByTestId('market-overview-card-volatility')).getByText('VIX 恐慌指数')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '全球宏观' }));
    expect(getRowCardOrder('global-hero')).toEqual(['rates']);
    expect(getRowCardOrder('global-modules-1')).toEqual(['fxCommodities', 'globalRisk']);
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
      expect(getRowIds()).toEqual(['all-hero', 'all-modules-1', 'all-modules-2', 'all-modules-3', 'all-modules-4']);
    });
    expect(getRowCardOrder('all-hero')).toEqual(['indices']);
    expect(getRowCardOrder('all-modules-1')).toEqual(['volatility', 'fundsFlow']);
    expect(getRowCardOrder('all-modules-2')).toEqual(['sentiment', 'rates']);
    expect(getRowCardOrder('all-modules-3')).toEqual(['fxCommodities', 'crypto']);
    expect(screen.getByTestId('market-overview-deep-panels')).toContainElement(screen.getByTestId('market-overview-executive-secondary-groups'));
    expect(getSideCardOrder()).toEqual([]);

    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    expect(getRowIds()).toEqual(['us-hero', 'us-modules-1', 'us-modules-2', 'us-modules-3']);
    expect(getRowCardOrder('us-hero')).toEqual(['indices']);
    expect(getRowCardOrder('us-modules-1')).toEqual(['volatility', 'usRates']);
    expect(getRowCardOrder('us-modules-2')).toEqual(['sentiment', 'usBreadth']);
    expect(getRowCardOrder('us-modules-3')).toEqual(['usSectorRotation', 'macroContext']);
    expect(getSideCardOrder()).toEqual([]);

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    expect(getRowIds()).toEqual(['cn-hero', 'cn-modules-1', 'cn-modules-2', 'cn-modules-3']);
    expect(getRowCardOrder('cn-hero')).toEqual(['cnIndices']);
    expect(getRowCardOrder('cn-modules-1')).toEqual(['cnBreadth', 'cnFlows']);
    expect(getRowCardOrder('cn-modules-2')).toEqual(['sectorRotation', 'cnShortSentiment']);
    expect(getRowCardOrder('cn-modules-3')).toEqual(['fxCnhContext']);
    expect(getSideCardOrder()).toEqual([]);

    fireEvent.click(screen.getByRole('button', { name: '全球宏观' }));
    expect(getRowIds()).toEqual(['global-hero', 'global-modules-1', 'global-modules-2']);
    expect(getRowCardOrder('global-hero')).toEqual(['rates']);
    expect(getRowCardOrder('global-modules-1')).toEqual(['fxCommodities', 'globalRisk']);
    expect(getRowCardOrder('global-modules-2')).toEqual(['sentiment', 'volatility']);
    expect(getSideCardOrder()).toEqual([]);
    expect(screen.getByTestId('market-overview-card-globalRisk')).toHaveClass('min-w-0', 'w-full');

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));
    expect(getRowIds()).toEqual(['crypto-hero', 'crypto-modules-1', 'crypto-modules-2']);
    expect(getRowCardOrder('crypto-hero')).toEqual(['cryptoCore']);
    expect(getRowCardOrder('crypto-modules-1')).toEqual(['cryptoMomentum', 'cryptoLiquidity']);
    expect(getRowCardOrder('crypto-modules-2')).toEqual(['cryptoRiskContext', 'sentiment']);
    expect(getSideCardOrder()).toEqual([]);
    expect(screen.getByTestId('market-overview-card-cryptoCore')).toHaveAttribute('data-market-card-row', 'hero');
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
    expect(screen.getByTestId('market-overview-card-cnIndices')).toHaveAttribute('data-market-overview-module', 'cnSnapshot');
    expect(getRowCardOrder('all-modules-3')).toEqual(['fxCommodities', 'crypto']);
    expect(getRowCardOrder('all-modules-4')).toEqual(['cnIndices']);
    expect(screen.getByTestId('market-overview-secondary-group-cn')).toHaveTextContent(/CN\/HK/);
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

    expect(await screen.findByTestId('market-overview-coverage-summary')).toHaveTextContent(/A股\/港股数据覆盖：真实 \d+ · 混合 \d+ · 备用 \d+/);

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
    expect(screen.getByTestId('market-overview-card-cryptoCore').closest('[data-testid="market-overview-main-grid"]')).toBeTruthy();
  });

  it('renders US breadth and sector health from the depth endpoint', async () => {
    vi.mocked(marketApi.getUsBreadth).mockResolvedValue(usBreadthPanel());

    render(<MarketOverviewPage />);

    fireEvent.click(await screen.findByRole('button', { name: '美股' }));

    const breadthCard = await screen.findByTestId('market-overview-card-usBreadth');
    expect(within(breadthCard).getByRole('heading', { name: /美股宽度|宽度代理/i })).toBeInTheDocument();
    expect(breadthCard).toHaveTextContent(/行业 ETF 代理/);
    await waitFor(() => expect(breadthCard).toHaveTextContent(/Sectors Up|Strongest XLK|RSP vs SPY/));
    expect(breadthCard).not.toHaveTextContent(/未接入/);

    const sectorCard = screen.getByTestId('market-overview-card-usSectorRotation');
    await waitFor(() => expect(sectorCard).toHaveTextContent(/Sector Health|Strongest XLK|Weakest XLE/));
  });

  it('renders Polygon EOD computed US breadth with visible partial high-low gaps', async () => {
    vi.mocked(marketApi.getUsBreadth).mockResolvedValue(polygonUsBreadthPanel());

    render(<MarketOverviewPage />);

    fireEvent.click(await screen.findByRole('button', { name: '美股' }));

    const breadthCard = await screen.findByTestId('market-overview-card-usBreadth');
    await waitFor(() => expect(breadthCard).toHaveTextContent(/Polygon EOD 计算宽度/));

    expect(breadthCard).toHaveTextContent(/AD 指标可用/);
    expect(breadthCard).toHaveTextContent(/高低点宽度缺失/);
    expect(breadthCard).toHaveTextContent(/非 NYSE\/Nasdaq 官方发布宽度/);
    expect(breadthCard).toHaveTextContent(/上涨家数|ADVANCERS/);
    expect(breadthCard).toHaveTextContent(/下跌家数|DECLINERS/);
    expect(breadthCard).toHaveTextContent(/平盘家数|UNCHANGED/);
    expect(breadthCard).toHaveTextContent(/上涨\/下跌比|ADVANCE_DECLINE_RATIO/);
    expect(breadthCard).toHaveTextContent(/NEW_HIGHS/);
    expect(breadthCard).toHaveTextContent(/NEW_LOWS/);
    expect(breadthCard).toHaveTextContent(/HIGH_LOW_RATIO/);
    expect(breadthCard).not.toHaveTextContent(/行业 ETF 代理|RSP vs SPY|IWM vs SPY/);
    expect(breadthCard.textContent || '').not.toMatch(/买入|卖出|加仓|减仓|buy|sell|add|reduce/i);
  });

  it('keeps US breadth unavailable state compact and honest', async () => {
    renderMarketOverviewWorkbenchWithProps({
      panels: {
        ...localSnapshotPayload().payload,
        usBreadth: usBreadthUnavailablePanel(),
      },
    });

    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    const breadthCard = await screen.findByTestId('market-overview-card-usBreadth');

    await waitFor(() => expect(breadthCard).toHaveTextContent(/数据暂不可用|未接入/));
    expect(breadthCard).toHaveTextContent(/暂不可用|未接入/);
    expect(within(breadthCard).queryByText(/Advance \/ decline：未接入/)).not.toBeInTheDocument();
  });

  it('renders crypto funding and compact unavailable liquidity context without market dumps', async () => {
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFullPanel());

    render(<MarketOverviewPage />);

    fireEvent.click(await screen.findByRole('button', { name: '加密货币' }));

    expect(await screen.findByTestId('market-overview-card-cryptoCore')).toHaveTextContent(/Bitcoin|Ethereum|Solana|BNB/);
    expect(screen.getByTestId('market-overview-card-cryptoMomentum')).toHaveTextContent(/Bitcoin|Ethereum|Solana|BNB/);
    const liquidityCard = screen.getByTestId('market-overview-card-cryptoLiquidity');
    expect(liquidityCard).toHaveTextContent(/资金费率|BTC Funding|BTC 资金费率/);
    expect(liquidityCard).toHaveTextContent(/稳定币流动性.*未接入|BTC 占比.*未接入/);
    expect(screen.getByTestId('market-overview-card-cryptoRiskContext')).toHaveTextContent(/DXY|US 10Y|VIX/);
    expect(screen.queryByTestId('market-overview-module-cnHkIndices')).not.toBeInTheDocument();
    expect(screen.queryByTestId('market-overview-module-usIndices')).not.toBeInTheDocument();
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

    expect(await screen.findByTestId('market-overview-card-cryptoCore')).toBeInTheDocument();
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
    expect(
      screen.getAllByTestId('market-overview-quote-metadata')
        .some((node) => node.getAttribute('title')?.includes('Binance WS')),
    ).toBe(true);
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
    await act(async () => {
      await Promise.resolve();
    });

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

  it('renders all provider health badge states in Chinese', () => {
    render(
      <div>
        {(['live', 'cache', 'stale', 'fallback', 'partial', 'unavailable', 'refreshing', 'error'] as const).map((status) => (
          <DataFreshnessBadge key={status} status={status} />
        ))}
      </div>,
    );

    expect(screen.getByText('实时')).toBeInTheDocument();
    expect(screen.getByText('缓存')).toBeInTheDocument();
    expect(screen.getByText('过期')).toBeInTheDocument();
    expect(screen.getByText('备用')).toBeInTheDocument();
    expect(screen.getByText('部分数据')).toBeInTheDocument();
    expect(screen.getByText('暂不可用')).toBeInTheDocument();
    expect(screen.getByText('刷新中')).toBeInTheDocument();
    expect(screen.getByText('数据异常')).toBeInTheDocument();
  });

  it('shows stale card data as expired data', async () => {
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
    const details = expandMarketDecisionDetails();
    await waitFor(() => expect(within(details).getByTestId('market-overview-cache-status')).toHaveTextContent(/待刷新/i));
    expect(screen.getAllByText(/数据可能已过期/i).length).toBeGreaterThan(0);
  });

  it('shows snapshot refresh status without clearing stale card data', async () => {
    vi.mocked(marketApi.getCnIndices).mockResolvedValueOnce({
      ...snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数'),
      isRefreshing: true,
      providerHealth: {
        provider: 'sina',
        status: 'refreshing' as const,
        asOf: '2026-04-29T10:00:00',
        updatedAt: '2026-04-29T10:01:00',
        latencyMs: 120,
        errorSummary: null,
        isFallback: false,
        isStale: false,
        isRefreshing: true,
        sourceLabel: 'Sina',
      },
      items: [
        {
          ...snapshotPanel('ChinaIndicesCard', '000001.SH', '上证指数').items[0],
          value: 3120.55,
          providerHealth: {
            provider: 'sina',
            status: 'refreshing' as const,
            asOf: '2026-04-29T10:00:00',
            updatedAt: '2026-04-29T10:01:00',
            latencyMs: 120,
            errorSummary: null,
            isFallback: false,
            isStale: false,
            isRefreshing: true,
            sourceLabel: 'Sina',
          },
        },
      ],
    });

    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    expandPendingDataSourceSection();
    await waitFor(() => expect(screen.getAllByTestId('data-freshness-badge-refreshing').length).toBeGreaterThan(0));
    expect(screen.getAllByText('上证指数').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/3,120.55|3120.55/).length).toBeGreaterThan(0);
  });

  it('switches market categories without refetching all cards', async () => {
    render(<MarketOverviewPage />);

    await waitFor(() => expect(marketApi.getCnIndices).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));
    expect(screen.getByRole('button', { name: 'A股/港股' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('market-overview-coverage-summary')).toHaveTextContent('A股/港股数据覆盖');
    expect(screen.getByRole('heading', { name: /A股短线情绪/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /A股与港股指数/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /市场宽度与赚钱效应/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /资金流向/i })).toBeInTheDocument();
    expect(getRowCardOrder('cn-hero')).toEqual(['cnIndices']);
    expect(getRowCardOrder('cn-modules-1')).toEqual(['cnBreadth', 'cnFlows']);
    expect(getRowCardOrder('cn-modules-2')).toEqual(['sectorRotation', 'cnShortSentiment']);

    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    expect(screen.getByRole('heading', { name: /US Index Core/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /波动率与风险压力/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /US Rates/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /宏观压力/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /情绪与资金面/i })).toBeInTheDocument();
    expect(screen.queryByText('CSI 300')).not.toBeInTheDocument();
    expect(screen.queryByText('Shanghai Composite')).not.toBeInTheDocument();
    expect(screen.queryByText('Shenzhen Component')).not.toBeInTheDocument();
    expect(screen.getByTestId('market-overview-rail-signal-watch')).toHaveTextContent('DXY');
    expect(getRowCardOrder('us-hero')).toEqual(['indices']);
    expect(getRowCardOrder('us-modules-1')).toEqual(['volatility', 'usRates']);
    expect(getRowCardOrder('us-modules-2')).toEqual(['sentiment', 'usBreadth']);

    expect(marketApi.getCnIndices).toHaveBeenCalledTimes(1);
    expect(marketApi.getRates).toHaveBeenCalledTimes(1);
  });

  it('keeps other cards visible when one initial API request fails', async () => {
    vi.mocked(marketApi.getCnBreadth).mockRejectedValueOnce(new Error('breadth down'));

    render(<MarketOverviewPage />);

    expect(await screen.findByTestId('market-overview-main-grid')).toBeInTheDocument();
    expect(screen.getByTestId('market-decision-semantics-strip')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('heading', { name: /情绪与资金面/i })).toBeInTheDocument());
    await waitFor(() => expect(screen.getByRole('heading', { name: /波动率与风险压力/i })).toBeInTheDocument());
  });

  it('does not block settled cards when global indices request is still pending', async () => {
    vi.mocked(marketOverviewApi.getIndices).mockReturnValueOnce(new Promise(() => {}));

    render(<MarketOverviewPage />);

    expect(await screen.findByTestId('market-sentiment-compact-card')).toBeInTheDocument();
    expect((await screen.findAllByText('26')).length).toBeGreaterThan(0);
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
    expect(screen.getAllByText('BTC').length).toBeGreaterThan(0);
    expect(screen.getAllByText('ETH').length).toBeGreaterThan(0);
    expect(screen.getAllByText('BNB').length).toBeGreaterThan(0);
    expect(screen.getAllByTestId('data-freshness-badge-fallback').length).toBeGreaterThan(0);
    expect(screen.queryByText(/正在获取最新快照/i)).not.toBeInTheDocument();
  });

  it('renders the crypto fallback response as a card with freshness metadata', async () => {
    vi.mocked(marketApi.getCrypto).mockResolvedValueOnce(cryptoFallbackPanel());

    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));
    expect(await screen.findByRole('heading', { name: /加密核心/i })).toBeInTheDocument();
    expect((await screen.findAllByText(/75,800/)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/3,120/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/590/).length).toBeGreaterThan(0);
    expect(screen.getAllByTestId('data-freshness-badge-fallback').length).toBeGreaterThan(0);
    expect(screen.getAllByTestId('data-freshness-badge-fallback').length).toBeGreaterThan(0);
    expect(screen.queryByTestId('data-freshness-badge-live')).not.toBeInTheDocument();
  });

  it('auto revalidates partial refreshing cards and replaces them without manual refresh', async () => {
    vi.useFakeTimers();
    vi.mocked(marketApi.getCrypto)
      .mockResolvedValueOnce(cryptoPartialRefreshingPanel())
      .mockResolvedValueOnce(cryptoFullPanel());

    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByRole('heading', { name: /加密核心/i })).toBeInTheDocument();
    expect(screen.getAllByTestId('data-freshness-badge-refreshing').length).toBeGreaterThan(0);
    expect(marketApi.getCrypto).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(AUTO_REVALIDATE_OBSERVATION_WINDOW_MS);
    });

    expect(marketApi.getCrypto).toHaveBeenCalledTimes(2);
    expect(screen.getAllByText('76,837.04').length).toBeGreaterThan(0);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(AUTO_REVALIDATE_OBSERVATION_WINDOW_MS);
    });

    expect(marketApi.getCrypto).toHaveBeenCalledTimes(2);
  });

  it('stops auto revalidation after bounded attempts when a card remains partial', async () => {
    vi.useFakeTimers();
    vi.mocked(marketApi.getCrypto).mockResolvedValue(cryptoPartialRefreshingPanel());

    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByRole('heading', { name: /加密核心/i })).toBeInTheDocument();
    expect(screen.getAllByTestId('data-freshness-badge-refreshing').length).toBeGreaterThan(0);
    expect(marketApi.getCrypto).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(AUTO_REVALIDATE_OBSERVATION_WINDOW_MS);
    });
    expect(marketApi.getCrypto).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(AUTO_REVALIDATE_OBSERVATION_WINDOW_MS);
    });
    expect(marketApi.getCrypto).toHaveBeenCalledTimes(3);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(AUTO_REVALIDATE_OBSERVATION_WINDOW_MS);
    });
    expect(marketApi.getCrypto).toHaveBeenCalledTimes(4);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(AUTO_REVALIDATE_OBSERVATION_WINDOW_MS);
    });

    expect(marketApi.getCrypto).toHaveBeenCalledTimes(4);
  });

  it('uses the same crypto write path for initial load and manual refresh', async () => {
    vi.mocked(marketApi.getCrypto)
      .mockResolvedValueOnce(cryptoFallbackPanel())
      .mockResolvedValueOnce(cryptoFullPanel());

    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: '加密货币' }));
    expect((await screen.findAllByText('BTC')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('ETH').length).toBeGreaterThan(0);
    expect(screen.getAllByText('BNB').length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: /刷新 加密核心/i }));

    await waitFor(() => expect(marketApi.getCrypto).toHaveBeenCalledTimes(2));
    expect(screen.getAllByText('BTC').length).toBeGreaterThan(0);
    expect(screen.getAllByText('ETH').length).toBeGreaterThan(0);
    expect(screen.getAllByText('BNB').length).toBeGreaterThan(0);
    expect((await screen.findAllByText('76,837.04')).length).toBeGreaterThan(0);
  });

  it('keeps other market cards visible when crypto initial API fails', async () => {
    vi.mocked(marketApi.getCrypto).mockRejectedValueOnce(new Error('crypto down'));

    render(<MarketOverviewPage />);

    expandPendingDataSourceSection();
    expect(await screen.findByTestId('market-overview-card-crypto')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /加密货币行情/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /情绪与资金面/i })).toBeInTheDocument();
    expect((await screen.findAllByText('BTC')).length).toBeGreaterThan(0);
    expect(screen.queryByText(/正在获取最新快照/i)).not.toBeInTheDocument();
  });

  it('refreshes only the requested panel when a card refresh icon is clicked', async () => {
    vi.mocked(marketApi.getFutures).mockResolvedValue({
      ...futuresPayload(),
      source: 'computed',
      sourceLabel: '系统计算',
      freshness: 'cached' as const,
      isFallback: false,
      items: futuresPayload().items.map((item) => ({
        ...item,
        source: 'computed',
        sourceLabel: '系统计算',
        freshness: 'cached' as const,
        isFallback: false,
      })),
    });

    render(<MarketOverviewPage />);

    await waitFor(() => expect(marketOverviewApi.getMacro).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(marketApi.getFutures).toHaveBeenCalledTimes(1));

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

  it('coalesces duplicate in-flight polling refreshes for the same market overview panels', async () => {
    vi.useFakeTimers();
    const setIntervalSpy = vi.spyOn(window, 'setInterval');

    render(<MarketOverviewPage />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(650);
    });
    expectMarketPanelRequestsCalledOnce(allMarketPanelRequests);

    const intervalByDelay = new Map(
      setIntervalSpy.mock.calls.map(([callback, delay]) => [delay, callback as () => void]),
    );
    const fastCallback = intervalByDelay.get(45_000);
    expect(typeof fastCallback).toBe('function');

    const indicesRefresh = createDeferredPromise<ReturnType<typeof panel>>();
    const volatilityRefresh = createDeferredPromise<ReturnType<typeof panel>>();
    const cryptoRefresh = createDeferredPromise<ReturnType<typeof cryptoPanel>>();
    vi.mocked(marketOverviewApi.getIndices).mockReturnValueOnce(indicesRefresh.promise);
    vi.mocked(marketOverviewApi.getVolatility).mockReturnValueOnce(volatilityRefresh.promise);
    vi.mocked(marketApi.getCrypto).mockReturnValueOnce(cryptoRefresh.promise);

    await act(async () => {
      fastCallback?.();
      fastCallback?.();
      await Promise.resolve();
    });

    expect(marketOverviewApi.getIndices).toHaveBeenCalledTimes(2);
    expect(marketOverviewApi.getVolatility).toHaveBeenCalledTimes(2);
    expect(marketApi.getCrypto).toHaveBeenCalledTimes(2);

    await act(async () => {
      indicesRefresh.resolve(panel('IndexTrendsCard', 'SPX'));
      volatilityRefresh.resolve(panel('VolatilityCard', 'VIX'));
      cryptoRefresh.resolve(cryptoPanel());
      await Promise.resolve();
    });
  });

  it('keeps different panel refreshes independent while one manual refresh is still in flight', async () => {
    const volatilityRefresh = createDeferredPromise<ReturnType<typeof panel>>();
    const sentimentRefresh = createDeferredPromise<ReturnType<typeof sentimentPanel>>();

    render(<MarketOverviewPage />);

    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    await waitFor(() => expect(marketOverviewApi.getVolatility).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(marketApi.getSentiment).toHaveBeenCalledTimes(1));

    vi.mocked(marketOverviewApi.getVolatility).mockReturnValueOnce(volatilityRefresh.promise);
    vi.mocked(marketApi.getSentiment).mockReturnValueOnce(sentimentRefresh.promise);

    fireEvent.click(screen.getByRole('button', { name: /刷新 波动率与风险压力/i }));
    fireEvent.click(screen.getByRole('button', { name: /刷新 情绪与资金面/i }));

    expect(marketOverviewApi.getVolatility).toHaveBeenCalledTimes(2);
    expect(marketApi.getSentiment).toHaveBeenCalledTimes(2);

    await act(async () => {
      volatilityRefresh.resolve(panel('VolatilityCard', 'VIX'));
      sentimentRefresh.resolve(sentimentPanel());
      await Promise.resolve();
    });
  });

  it('keeps fallback summary modules visible when new APIs fail', async () => {
    vi.mocked(marketApi.getTemperature).mockRejectedValueOnce(new Error('temperature down'));
    vi.mocked(marketApi.getMarketBriefing).mockRejectedValueOnce(new Error('briefing down'));
    vi.mocked(marketApi.getFutures).mockRejectedValueOnce(new Error('futures down'));
    vi.mocked(marketApi.getCnShortSentiment).mockRejectedValueOnce(new Error('sentiment down'));

    render(<MarketOverviewPage />);

    const details = expandMarketDecisionDetails();
    expect(await within(details).findByTestId('market-overview-temperature-summary')).toBeInTheDocument();
    expect(within(details).getByTestId('market-overview-briefing-summary')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '美股' }));
    expandPendingDataSourceSection();
    expect(screen.getByRole('heading', { name: /美股宽度/i })).toBeInTheDocument();
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
    expect((await screen.findAllByText('上证指数')).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: /刷新 A股与港股指数/i }));
    expect(screen.getAllByText('上证指数').length).toBeGreaterThan(0);

    resolveRefresh?.(snapshotPanel('ChinaIndicesCard', '399001.SZ', '深证成指'));
    expect((await screen.findAllByText('深证成指')).length).toBeGreaterThan(0);
  });

  it('polls market cards in TTL-aware groups instead of one all-panel interval', async () => {
    vi.useFakeTimers();
    const setIntervalSpy = vi.spyOn(window, 'setInterval');
    render(<MarketOverviewPage />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(650);
    });
    expectMarketPanelRequestsCalledOnce(allMarketPanelRequests);

    expect(setIntervalSpy).toHaveBeenCalledTimes(3);
    const intervalByDelay = new Map(
      setIntervalSpy.mock.calls.map(([callback, delay]) => [delay, callback as TimerHandler]),
    );
    const fastCallback = intervalByDelay.get(45_000);
    const mediumCallback = intervalByDelay.get(120_000);
    const slowCallback = intervalByDelay.get(300_000);
    expect(typeof fastCallback).toBe('function');
    expect(typeof mediumCallback).toBe('function');
    expect(typeof slowCallback).toBe('function');

    (fastCallback as () => void)();
    expect(marketApi.getCrypto).toHaveBeenCalledTimes(2);
    expect(marketOverviewApi.getIndices).toHaveBeenCalledTimes(2);
    expect(marketOverviewApi.getVolatility).toHaveBeenCalledTimes(2);
    expect(marketApi.getSentiment).toHaveBeenCalledTimes(1);
    expect(marketApi.getCnIndices).toHaveBeenCalledTimes(1);
    expect(marketApi.getFutures).toHaveBeenCalledTimes(1);

    (mediumCallback as () => void)();
    expect(marketApi.getCnIndices).toHaveBeenCalledTimes(2);
    expect(marketApi.getCnBreadth).toHaveBeenCalledTimes(2);
    expect(marketApi.getFutures).toHaveBeenCalledTimes(2);
    expect(marketApi.getSentiment).toHaveBeenCalledTimes(1);
    expect(marketApi.getCnFlows).toHaveBeenCalledTimes(1);

    (slowCallback as () => void)();
    expect(marketApi.getSentiment).toHaveBeenCalledTimes(2);
    expect(marketOverviewApi.getMacro).toHaveBeenCalledTimes(2);
    expect(marketApi.getCnFlows).toHaveBeenCalledTimes(2);
    expect(marketApi.getRates).toHaveBeenCalledTimes(2);
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

    expect(getRowCardOrder('all-hero')).toEqual(['indices']);
    expect(getRowCardOrder('all-modules-1')).toEqual(['volatility', 'fundsFlow']);
    expect(getRowCardOrder('all-modules-3')).toEqual(['fxCommodities', 'crypto']);
    expect(window.localStorage.getItem('market-overview-order-all')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'A股/港股' }));

    expect(getRowCardOrder('cn-hero')).toEqual(['cnIndices']);
    expect(getRowCardOrder('cn-modules-1')).toEqual(['cnBreadth', 'cnFlows']);
    expect(window.localStorage.getItem('market-overview-order-cn')).toBeNull();
  });

  it('shows compact official macro authority diagnostics without promoting degraded rows', async () => {
    vi.mocked(marketOverviewApi.getMacro).mockResolvedValueOnce(officialMacroPanel());

    render(<MarketOverviewPage />);

    const details = expandMarketDecisionDetails();
    const diagnostics = within(details).getByTestId('market-overview-official-macro-diagnostics');
    await waitFor(() => expect(diagnostics).toHaveTextContent('可计分 2'));
    expect(diagnostics).toHaveTextContent('官方 3');
    expect(diagnostics).toHaveTextContent('代理/观察 2');
    expect(diagnostics).toHaveTextContent('缺口 3');
    expect(within(diagnostics).queryByText(/provider_forbidden_for_use_case/, { selector: 'p' })).not.toBeInTheDocument();

    fireEvent.click(within(diagnostics).getByRole('button', { name: '展开 来源覆盖诊断' }));

    expect(diagnostics).toHaveTextContent('Official');
    expect(diagnostics).toHaveTextContent('Score-eligible');
    expect(diagnostics).toHaveTextContent('Observation-only');
    expect(diagnostics).toHaveTextContent('Fallback');
    expect(diagnostics).toHaveTextContent('Rejected');
    expect(diagnostics).toHaveTextContent('provider_forbidden_for_use_case');
    expect(diagnostics).toHaveTextContent('As-of 2026-05-20');
    expect(within(diagnostics).getByText(/provider_forbidden_for_use_case/, { selector: 'p' })).toBeVisible();
  });
});
