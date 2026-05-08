import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { MarketOverviewItem, MarketOverviewPanel } from '../api/marketOverview';
import { marketOverviewApi } from '../api/marketOverview';
import type {
  CnShortSentimentResponse,
  MarketBriefingResponse,
  MarketFuturesResponse,
  MarketTemperatureResponse,
  MarketTemperatureScore,
} from '../api/market';
import { marketApi, normalizeMarketTemperatureResponse } from '../api/market';
import { FundsFlowCard } from '../components/market-overview/FundsFlowCard';
import { MarketSentimentCard } from '../components/market-overview/MarketSentimentCard';
import { MarketOverviewCard } from '../components/market-overview/MarketOverviewCard';
import { VolatilityCard } from '../components/market-overview/VolatilityCard';
import {
  MARKET_OVERVIEW_TAB_CONFIG,
  type MarketOverviewModuleId,
  type MarketOverviewPulseMetricId,
  type MarketOverviewTab,
} from './MarketOverviewTabConfig';
import { resolveMarketOverviewDisplayLabel } from '../components/market-overview/marketOverviewLabels';
import { formatMarketOverviewTimestamp } from '../components/market-overview/marketOverviewFormat';
import {
  DataFreshnessBadge,
  MARKET_OVERVIEW_GHOST_CARD_CLASS,
  MarketOverviewCardFrame,
  MarketOverviewDenseQuoteItem,
  MarketOverviewPanelFooter,
  MarketOverviewRefreshButton,
} from '../components/market-overview/marketOverviewPrimitives';
import { useI18n } from '../contexts/UiLanguageContext';
import { GlassCard } from '../components/common';
import { cn } from '../utils/cn';

type PanelState = {
  indices?: MarketOverviewPanel;
  volatility?: MarketOverviewPanel;
  crypto?: MarketOverviewPanel;
  sentiment?: MarketOverviewPanel;
  fundsFlow?: MarketOverviewPanel;
  macro?: MarketOverviewPanel;
  cnIndices?: MarketOverviewPanel;
  cnBreadth?: MarketOverviewPanel;
  cnFlows?: MarketOverviewPanel;
  sectorRotation?: MarketOverviewPanel;
  usBreadth?: MarketOverviewPanel;
  rates?: MarketOverviewPanel;
  fxCommodities?: MarketOverviewPanel;
  temperature: MarketTemperatureResponse;
  briefing: MarketBriefingResponse;
  futures: MarketFuturesResponse;
  cnShortSentiment: CnShortSentimentResponse;
};

type PanelKey = keyof PanelState;
type CardKey = Exclude<PanelKey, 'temperature' | 'briefing'>;
type CardCoverageKind = 'real' | 'mixed' | 'fallback';
type CryptoRealtimeStatus = 'live' | 'reconnecting' | 'snapshot';
type MarketOverviewRowTier = 'hero' | 'secondary' | 'deep';
type MarketOverviewRowColumns = 1 | 2 | 3;
type MarketOverviewLayoutRow = {
  id: string;
  tier: MarketOverviewRowTier;
  columns: MarketOverviewRowColumns;
  modules: MarketOverviewModuleId[];
  allowSingleFullWidth?: boolean;
};
type WorkbenchRail = MarketOverviewRowTier;
type LocalSnapshotEnvelope = {
  schemaVersion: 1;
  savedAt: string;
  payload: Partial<PanelState>;
};

const MARKET_OVERVIEW_LKG_STORAGE_KEY = 'wolfystock.marketOverview.lastKnownGood.v1';

const MODULE_COVERAGE_CARDS: Record<MarketOverviewModuleId, CardKey[]> = {
  globalIndices: ['indices'],
  usIndices: ['indices'],
  cnHkIndices: ['cnIndices'],
  cryptoCore: ['crypto'],
  volatility: ['volatility'],
  fundsFlow: ['fundsFlow'],
  sentiment: ['sentiment'],
  rates: ['rates'],
  fxCommodities: ['fxCommodities'],
  cryptoSnapshot: ['crypto'],
  cnSnapshot: ['cnIndices'],
  usRates: ['rates', 'fxCommodities'],
  usSentiment: ['sentiment'],
  usBreadth: ['usBreadth'],
  usSectorRotation: ['usBreadth'],
  macroContext: ['volatility', 'rates', 'fxCommodities', 'crypto'],
  cnBreadth: ['cnBreadth'],
  cnFlows: ['cnFlows'],
  sectorRotation: ['sectorRotation'],
  shortSentiment: ['cnShortSentiment'],
  fxCnhContext: ['fxCommodities', 'rates'],
  macroRates: ['rates'],
  macroFxCommodities: ['fxCommodities'],
  globalRisk: ['volatility', 'crypto', 'indices'],
  cryptoMomentum: ['crypto'],
  cryptoLiquidity: ['crypto'],
  cryptoRiskContext: ['fxCommodities', 'rates', 'volatility'],
  cryptoSentiment: ['sentiment'],
};

const CATEGORY_CARDS: Record<MarketOverviewTab, CardKey[]> = Object.fromEntries(
  Object.entries(MARKET_OVERVIEW_TAB_CONFIG).map(([tab, config]) => [
    tab,
    Array.from(new Set([...config.hero, ...config.modules].flatMap((moduleId) => MODULE_COVERAGE_CARDS[moduleId]))),
  ]),
) as Record<MarketOverviewTab, CardKey[]>;

const MODULE_LAYOUT_META: Record<MarketOverviewModuleId, {
  size: 'compact' | 'standard' | 'list' | 'large' | 'rail';
  priority: 'primary' | 'secondary' | 'fallback';
}> = {
  globalIndices: { size: 'large', priority: 'primary' },
  usIndices: { size: 'large', priority: 'primary' },
  cnHkIndices: { size: 'large', priority: 'primary' },
  cryptoCore: { size: 'large', priority: 'primary' },
  volatility: { size: 'standard', priority: 'primary' },
  fundsFlow: { size: 'standard', priority: 'primary' },
  rates: { size: 'list', priority: 'secondary' },
  fxCommodities: { size: 'list', priority: 'secondary' },
  cryptoSnapshot: { size: 'list', priority: 'secondary' },
  cnSnapshot: { size: 'list', priority: 'secondary' },
  usRates: { size: 'list', priority: 'secondary' },
  usSentiment: { size: 'compact', priority: 'secondary' },
  usBreadth: { size: 'compact', priority: 'fallback' },
  usSectorRotation: { size: 'compact', priority: 'fallback' },
  macroContext: { size: 'list', priority: 'secondary' },
  sentiment: { size: 'compact', priority: 'secondary' },
  cnBreadth: { size: 'standard', priority: 'fallback' },
  cnFlows: { size: 'standard', priority: 'fallback' },
  sectorRotation: { size: 'standard', priority: 'fallback' },
  shortSentiment: { size: 'compact', priority: 'fallback' },
  fxCnhContext: { size: 'list', priority: 'secondary' },
  macroRates: { size: 'list', priority: 'primary' },
  macroFxCommodities: { size: 'list', priority: 'primary' },
  globalRisk: { size: 'list', priority: 'secondary' },
  cryptoMomentum: { size: 'list', priority: 'primary' },
  cryptoLiquidity: { size: 'compact', priority: 'fallback' },
  cryptoRiskContext: { size: 'list', priority: 'secondary' },
  cryptoSentiment: { size: 'compact', priority: 'secondary' },
};
const DENSE_QUOTE_MODULES = new Set<MarketOverviewModuleId>([
  'globalIndices',
  'usIndices',
  'cnHkIndices',
  'cryptoCore',
  'rates',
  'fxCommodities',
  'cryptoSnapshot',
  'cnSnapshot',
  'usRates',
  'macroContext',
  'fxCnhContext',
  'macroRates',
  'macroFxCommodities',
  'globalRisk',
  'cryptoMomentum',
  'cryptoRiskContext',
]);
const AUTO_REFRESH_MS = 60_000;
const PANEL_REQUEST_TIMEOUT_MS = 3_000;
const FIRST_STAGE_PANEL_DELAY_MS = 250;
const SECOND_STAGE_PANEL_DELAY_MS = 650;

type PanelRequest = readonly [PanelKey, () => Promise<PanelState[PanelKey]>];
type StagedPanelRequestGroup = {
  delayMs: number;
  requests: PanelRequest[];
};

const MARKET_OVERVIEW_PRIMARY_REQUESTS: PanelRequest[] = [
  ['indices', marketOverviewApi.getIndices],
  ['volatility', marketOverviewApi.getVolatility],
  ['crypto', marketApi.getCrypto],
  ['sentiment', marketApi.getSentiment],
  ['fundsFlow', marketOverviewApi.getFundsFlow],
  ['cnIndices', marketApi.getCnIndices],
  ['rates', marketApi.getRates],
  ['fxCommodities', marketApi.getFxCommodities],
  ['temperature', marketApi.getTemperature],
  ['briefing', marketApi.getMarketBriefing],
];

const MARKET_OVERVIEW_STAGED_REQUEST_GROUPS: StagedPanelRequestGroup[] = [
  {
    delayMs: FIRST_STAGE_PANEL_DELAY_MS,
    requests: [
      ['macro', marketOverviewApi.getMacro],
      ['cnBreadth', marketApi.getCnBreadth],
      ['usBreadth', marketApi.getUsBreadth],
    ],
  },
  {
    delayMs: SECOND_STAGE_PANEL_DELAY_MS,
    requests: [
      ['cnFlows', marketApi.getCnFlows],
      ['sectorRotation', marketApi.getSectorRotation],
      ['futures', marketApi.getFutures],
      ['cnShortSentiment', marketApi.getCnShortSentiment],
    ],
  },
];

function buildCategoryLayout(tab: MarketOverviewTab): MarketOverviewLayoutRow[] {
  const config = MARKET_OVERVIEW_TAB_CONFIG[tab];
  const rows: MarketOverviewLayoutRow[] = [];
  if (config.hero.length > 0) {
    rows.push({
      id: `${tab}-hero`,
      tier: 'hero',
      columns: Math.min(config.hero.length, 2) as MarketOverviewRowColumns,
      modules: config.hero,
      allowSingleFullWidth: true,
    });
  }
  for (let index = 0; index < config.modules.length; index += 2) {
    const modules = config.modules.slice(index, index + 2);
    rows.push({
      id: `${tab}-modules-${index / 2 + 1}`,
      tier: index < 4 ? 'secondary' : 'deep',
      columns: Math.min(modules.length, 2) as MarketOverviewRowColumns,
      modules,
      allowSingleFullWidth: false,
    });
  }
  return rows;
}

const CATEGORY_LAYOUT: Record<MarketOverviewTab, MarketOverviewLayoutRow[]> = {
  all: buildCategoryLayout('all'),
  us: buildCategoryLayout('us'),
  cn: buildCategoryLayout('cn'),
  global: buildCategoryLayout('global'),
  crypto: buildCategoryLayout('crypto'),
};

const FALLBACK_TEMPERATURE: MarketTemperatureResponse = {
  source: 'fallback',
  sourceLabel: '备用数据',
  updatedAt: new Date(0).toISOString(),
  freshness: 'fallback',
  isFallback: true,
  warning: '当前真实数据不足，市场温度仅供界面演示',
  confidence: 0,
  reliableInputCount: 0,
  fallbackInputCount: 0,
  excludedInputCount: 0,
  isReliable: false,
  scores: {
    overall: { value: 50, label: '数据不足', trend: 'stable', description: '当前真实数据不足，市场温度仅供界面演示。' },
    usRiskAppetite: { value: 50, label: '数据不足', trend: 'stable', description: '当前真实数据不足，市场温度仅供界面演示。' },
    cnMoneyEffect: { value: 50, label: '数据不足', trend: 'stable', description: '当前真实数据不足，市场温度仅供界面演示。' },
    macroPressure: { value: 50, label: '数据不足', trend: 'stable', description: '当前真实数据不足，市场温度仅供界面演示。' },
    liquidity: { value: 50, label: '数据不足', trend: 'stable', description: '当前真实数据不足，市场温度仅供界面演示。' },
  },
};

const FALLBACK_BRIEFING: MarketBriefingResponse = {
  source: 'fallback',
  sourceLabel: '备用数据',
  updatedAt: new Date(0).toISOString(),
  freshness: 'fallback',
  isFallback: true,
  warning: '当前真实数据不足，暂不生成强市场判断。',
  confidence: 0,
  reliableInputCount: 0,
  fallbackInputCount: 0,
  excludedInputCount: 0,
  isReliable: false,
  items: [
    { title: '当前真实数据不足', message: '当前真实数据不足，暂不生成强市场判断。', severity: 'warning', category: 'risk', confidence: 0 },
    { title: '备用数据已降级', message: '备用示例数据仅用于保持界面结构，不参与市场温度评分。', severity: 'neutral', category: 'risk', confidence: 0 },
    { title: '等待真实行情源', message: '接入足够真实输入后，再恢复风险偏好、赚钱效应和流动性判断。', severity: 'neutral', category: 'risk', confidence: 0 },
  ],
};

const FALLBACK_FUTURES: MarketFuturesResponse = {
  source: 'fallback',
  sourceLabel: '备用数据',
  updatedAt: new Date(0).toISOString(),
  freshness: 'fallback',
  isFallback: true,
  warning: '备用示例数据，不代表当前行情',
  items: [
    { name: '纳指期货', symbol: 'NQ', value: 18420.5, change: 65.2, changePercent: 0.35, market: 'US', session: 'premarket', sparkline: [18320, 18380, 18420.5], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback', isFallback: true, warning: '备用示例数据，不代表当前行情' },
    { name: '标普500期货', symbol: 'ES', value: 5238.25, change: 14.5, changePercent: 0.28, market: 'US', session: 'premarket', sparkline: [5208, 5218, 5238.25], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback', isFallback: true, warning: '备用示例数据，不代表当前行情' },
    { name: '道指期货', symbol: 'YM', value: 38980, change: 72, changePercent: 0.19, market: 'US', session: 'premarket', sparkline: [38820, 38930, 38980], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback', isFallback: true, warning: '备用示例数据，不代表当前行情' },
    { name: '罗素2000期货', symbol: 'RTY', value: 2094.6, change: -3.8, changePercent: -0.18, market: 'US', session: 'premarket', sparkline: [2108, 2098, 2094.6], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback', isFallback: true, warning: '备用示例数据，不代表当前行情' },
    { name: '富时A50期货', symbol: 'CN00Y', value: 12580, change: 38, changePercent: 0.3, market: 'CN', session: 'day', sparkline: [12420, 12542, 12580], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback', isFallback: true, warning: '备用示例数据，不代表当前行情' },
    { name: '恒指期货', symbol: 'HSI_F', value: 17712, change: 128, changePercent: 0.73, market: 'HK', session: 'day', sparkline: [17490, 17640, 17712], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback', isFallback: true, warning: '备用示例数据，不代表当前行情' },
  ],
};

const FALLBACK_CRYPTO_PANEL: MarketOverviewPanel = {
  panelName: 'CryptoCard',
  lastRefreshAt: new Date(0).toISOString(),
  status: 'failure',
  source: 'fallback',
  sourceLabel: '备用数据',
  updatedAt: new Date(0).toISOString(),
  asOf: new Date(0).toISOString(),
  freshness: 'fallback',
  isFallback: true,
  isRefreshing: true,
  warning: '正在刷新，稍后自动更新',
  items: [
    { symbol: 'BTC', label: 'Bitcoin', value: 75800, unit: 'USD', changePct: -0.2, riskDirection: 'increasing', trend: [75220, 75640, 76110, 75800], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback', isFallback: true, warning: '正在刷新，稍后自动更新' },
    { symbol: 'ETH', label: 'Ethereum', value: 3120, unit: 'USD', changePct: -0.4, riskDirection: 'increasing', trend: [3090, 3148, 3162, 3120], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback', isFallback: true, warning: '正在刷新，稍后自动更新' },
    { symbol: 'BNB', label: 'BNB', value: 590, unit: 'USD', changePct: 0.3, riskDirection: 'decreasing', trend: [584, 588, 586, 590], source: 'fallback', sourceLabel: '备用数据', freshness: 'fallback', isFallback: true, warning: '正在刷新，稍后自动更新' },
  ],
};

const FALLBACK_CN_SHORT_SENTIMENT: CnShortSentimentResponse = {
  source: 'fallback',
  sourceLabel: '备用数据',
  updatedAt: new Date(0).toISOString(),
  freshness: 'fallback',
  isFallback: true,
  warning: '备用示例数据，不代表当前行情',
  sentimentScore: 50,
  summary: '暂未接入真实数据源，当前为备用示例数据。',
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
};

function readLocalMarketOverviewSnapshot(): LocalSnapshotEnvelope | null {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(MARKET_OVERVIEW_LKG_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as LocalSnapshotEnvelope;
    if (!parsed || parsed.schemaVersion !== 1 || !parsed.payload || typeof parsed.payload !== 'object') {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function hasUsablePanelValue(value: unknown): boolean {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const payload = value as {
    source?: string;
    freshness?: string;
    errorMessage?: string | null;
    items?: unknown[];
    scores?: unknown;
    metrics?: unknown;
    summary?: unknown;
  };
  if ((payload.source === 'error' || payload.freshness === 'error') && !payload.items?.length) {
    return false;
  }
  return Boolean(
    (Array.isArray(payload.items) && payload.items.length > 0)
    || payload.scores
    || payload.metrics
    || payload.summary
  );
}

function buildInitialPanelsFromLocalSnapshot(): { panels: PanelState; source: 'local' | 'empty'; savedAt?: string } {
  const localSnapshot = readLocalMarketOverviewSnapshot();
  if (!localSnapshot) {
    return {
      source: 'empty',
      panels: {
        temperature: normalizeMarketTemperatureResponse(FALLBACK_TEMPERATURE),
        briefing: FALLBACK_BRIEFING,
        futures: FALLBACK_FUTURES,
        cnShortSentiment: FALLBACK_CN_SHORT_SENTIMENT,
      },
    };
  }
  const panels = {
    temperature: FALLBACK_TEMPERATURE,
    briefing: FALLBACK_BRIEFING,
    futures: FALLBACK_FUTURES,
    cnShortSentiment: FALLBACK_CN_SHORT_SENTIMENT,
    ...localSnapshot.payload,
  } as PanelState;
  panels.temperature = normalizeMarketTemperatureResponse(panels.temperature);
  return {
    source: 'local',
    savedAt: localSnapshot.savedAt,
    panels,
  };
}

function writeLocalMarketOverviewSnapshot(panels: PanelState): void {
  if (typeof window === 'undefined') {
    return;
  }
  const payload: Partial<PanelState> = {};
  (Object.keys(panels) as PanelKey[]).forEach((panelKey) => {
    const value = panels[panelKey];
    if (hasUsablePanelValue(value)) {
      payload[panelKey] = value as never;
    }
  });
  if (Object.keys(payload).length === 0) {
    return;
  }
  try {
    window.localStorage.setItem(MARKET_OVERVIEW_LKG_STORAGE_KEY, JSON.stringify({
      schemaVersion: 1,
      savedAt: new Date().toISOString(),
      payload,
    } satisfies LocalSnapshotEnvelope));
  } catch {
    // localStorage can be unavailable in private or quota-limited sessions.
  }
}

type HeroAnchor = {
  key: string;
  label: string;
  item?: MarketOverviewItem;
};

type MetricRegistryEntry = {
  label: string;
  symbols: string[];
  panelKeys: CardKey[];
};

const MARKET_OVERVIEW_METRIC_REGISTRY: Record<MarketOverviewPulseMetricId, MetricRegistryEntry> = {
  SPX: { label: '标普500', symbols: ['SPX', '^GSPC', 'S&P 500'], panelKeys: ['indices'] },
  NDX: { label: '纳斯达克100', symbols: ['NDX', '^NDX', 'NASDAQ 100'], panelKeys: ['indices'] },
  DJI: { label: '道琼斯工业平均指数', symbols: ['DJI', 'DJIA', '^DJI', 'DOW JONES'], panelKeys: ['indices'] },
  RUT: { label: '罗素2000', symbols: ['RUT', '^RUT', 'RUSSELL 2000'], panelKeys: ['indices'] },
  SHCOMP: { label: '上证指数', symbols: ['SHCOMP', '000001.SH', '000001.SS', 'SH000001', 'SHANGHAI COMPOSITE'], panelKeys: ['cnIndices', 'indices'] },
  SZCOMP: { label: '深证成指', symbols: ['SZCOMP', '399001.SZ', 'SZ399001', 'SHENZHEN COMPONENT'], panelKeys: ['cnIndices', 'indices'] },
  CHINEXT: { label: '创业板指', symbols: ['CHINEXT', '399006.SZ', 'SZ399006'], panelKeys: ['cnIndices'] },
  CSI300: { label: '沪深300', symbols: ['CSI300', '000300.SH', '000300.SS', 'CSI 300'], panelKeys: ['cnIndices', 'indices'] },
  HSI: { label: '恒生指数', symbols: ['HSI', 'HANG SENG INDEX'], panelKeys: ['cnIndices', 'indices'] },
  HSTECH: { label: '恒生科技指数', symbols: ['HSTECH', 'HANG SENG TECH'], panelKeys: ['cnIndices'] },
  A50: { label: '富时A50', symbols: ['A50', 'CN00Y', 'FTSE A50'], panelKeys: ['cnIndices', 'fxCommodities'] },
  BTC: { label: '比特币', symbols: ['BTC', 'BITCOIN'], panelKeys: ['crypto'] },
  ETH: { label: '以太坊', symbols: ['ETH', 'ETHEREUM'], panelKeys: ['crypto'] },
  SOL: { label: 'Solana', symbols: ['SOL', 'SOLANA'], panelKeys: ['crypto'] },
  BNB: { label: 'BNB', symbols: ['BNB'], panelKeys: ['crypto'] },
  VIX: { label: 'VIX 恐慌指数', symbols: ['VIX'], panelKeys: ['volatility'] },
  VVIX: { label: 'VVIX', symbols: ['VVIX'], panelKeys: ['volatility'] },
  US10Y: { label: '美国10年期国债收益率', symbols: ['US10Y', 'US 10Y', '10Y YIELD'], panelKeys: ['rates', 'macro'] },
  US2Y: { label: '美国2年期国债收益率', symbols: ['US2Y', 'US 2Y', '2Y YIELD'], panelKeys: ['rates', 'macro'] },
  US30Y: { label: '美国30年期国债收益率', symbols: ['US30Y', 'US 30Y', '30Y YIELD'], panelKeys: ['rates', 'macro'] },
  DXY: { label: '美元指数', symbols: ['DXY', 'US DOLLAR INDEX'], panelKeys: ['fxCommodities', 'macro'] },
  USDJPY: { label: 'USD/JPY', symbols: ['USDJPY', 'USD/JPY'], panelKeys: ['fxCommodities', 'macro'] },
  USDCNH: { label: 'USD/CNH', symbols: ['USDCNH', 'USD/CNH'], panelKeys: ['fxCommodities', 'macro'] },
  GOLD: { label: '黄金', symbols: ['GOLD', 'GOLD FUTURES'], panelKeys: ['fxCommodities'] },
  WTI: { label: 'WTI 原油', symbols: ['WTI', 'OIL', 'WTI CRUDE'], panelKeys: ['fxCommodities'] },
};

const MARKET_OVERVIEW_SIGNAL_WATCH: Record<MarketOverviewTab, MarketOverviewPulseMetricId[]> = {
  all: ['VIX', 'US10Y', 'DXY', 'BTC'],
  us: ['VIX', 'US10Y', 'DXY', 'NDX'],
  cn: ['CSI300', 'HSI', 'HSTECH', 'USDCNH'],
  global: ['US10Y', 'DXY', 'GOLD', 'WTI', 'VIX'],
  crypto: ['BTC', 'ETH', 'SOL', 'DXY'],
};

function findPanelItem(panel: MarketOverviewPanel | undefined, symbols: string[]): MarketOverviewItem | undefined {
  const normalizedSymbols = symbols.map((symbol) => symbol.toUpperCase());
  return panel?.items.find((item) => normalizedSymbols.includes(item.symbol.toUpperCase()));
}

function panelByCardKey(panels: PanelState, cardKey: CardKey): MarketOverviewPanel | undefined {
  if (cardKey === 'futures' || cardKey === 'cnShortSentiment') {
    return undefined;
  }
  return panels[cardKey];
}

function findMetricItem(panels: PanelState, metricId: MarketOverviewPulseMetricId): MarketOverviewItem | undefined {
  const entry = MARKET_OVERVIEW_METRIC_REGISTRY[metricId];
  for (const panelKey of entry.panelKeys) {
    const item = findPanelItem(panelByCardKey(panels, panelKey), entry.symbols);
    if (item) {
      return item;
    }
  }
  return undefined;
}

function missingMetricItem(metricId: MarketOverviewPulseMetricId): MarketOverviewItem {
  const entry = MARKET_OVERVIEW_METRIC_REGISTRY[metricId];
  return {
    symbol: metricId,
    label: entry.label,
    value: null,
    unit: '',
    changePct: null,
    changeText: '未接入',
    riskDirection: 'neutral',
    trend: [],
    source: 'unavailable',
    sourceLabel: '未接入',
    freshness: 'cached',
    hoverDetails: ['等待数据'],
  };
}

function buildMetricItems(panels: PanelState, metricIds: MarketOverviewPulseMetricId[]): MarketOverviewItem[] {
  return metricIds.map((metricId) => findMetricItem(panels, metricId) || missingMetricItem(metricId));
}

function firstSourcePanelForMetrics(panels: PanelState, metricIds: MarketOverviewPulseMetricId[]): MarketOverviewPanel | undefined {
  for (const metricId of metricIds) {
    for (const panelKey of MARKET_OVERVIEW_METRIC_REGISTRY[metricId].panelKeys) {
      const panel = panelByCardKey(panels, panelKey);
      if (panel) {
        return panel;
      }
    }
  }
  return undefined;
}

function buildMetricPanel(
  panels: PanelState,
  panelName: string,
  metricIds: MarketOverviewPulseMetricId[],
): MarketOverviewPanel {
  const basePanel = firstSourcePanelForMetrics(panels, metricIds);
  return {
    panelName,
    lastRefreshAt: basePanel?.lastRefreshAt || new Date(0).toISOString(),
    status: basePanel?.status || 'success',
    source: basePanel?.source || 'unavailable',
    sourceLabel: basePanel?.sourceLabel || '未接入',
    updatedAt: basePanel?.updatedAt,
    asOf: basePanel?.asOf,
    freshness: basePanel?.freshness || 'cached',
    isFallback: basePanel?.isFallback,
    isStale: basePanel?.isStale,
    warning: basePanel?.warning,
    items: buildMetricItems(panels, metricIds),
  };
}

function buildFilteredPanel(
  sourcePanel: MarketOverviewPanel | undefined,
  panelName: string,
  symbols: string[],
  fallbackItems: MarketOverviewItem[] = [],
): MarketOverviewPanel {
  const symbolSet = new Set(symbols);
  const items = sourcePanel?.items.filter((item) => symbolSet.has(item.symbol)) || [];
  const updatedAt = sourcePanel?.updatedAt || new Date(0).toISOString();
  return {
    panelName,
    lastRefreshAt: sourcePanel?.lastRefreshAt || updatedAt,
    status: sourcePanel?.status || 'success',
    source: sourcePanel?.source || 'unavailable',
    sourceLabel: sourcePanel?.sourceLabel || '未接入',
    updatedAt,
    asOf: sourcePanel?.asOf,
    freshness: sourcePanel?.freshness || 'fallback',
    isFallback: sourcePanel?.isFallback,
    isStale: sourcePanel?.isStale,
    warning: sourcePanel?.warning,
    items: items.length > 0 ? items : fallbackItems,
  };
}

function unavailableMarketItem(symbol: string, label: string, message: string): MarketOverviewItem {
  return {
    symbol,
    label,
    value: null,
    unit: '',
    changePct: null,
    changeText: message,
    riskDirection: 'neutral',
    trend: [],
    source: 'unavailable',
    sourceLabel: '未接入',
    freshness: 'fallback',
    isFallback: true,
    warning: message,
    hoverDetails: [message],
  };
}

function buildCryptoLiquidityPanel(sourcePanel: MarketOverviewPanel | undefined): MarketOverviewPanel {
  const fallbackItems = [
    unavailableMarketItem('BTC_FUNDING', 'BTC 资金费率', '暂不可用'),
    unavailableMarketItem('ETH_FUNDING', 'ETH 资金费率', '暂不可用'),
    unavailableMarketItem('SOL_FUNDING', 'SOL 资金费率', '暂不可用'),
    unavailableMarketItem('BNB_FUNDING', 'BNB 资金费率', '暂不可用'),
    unavailableMarketItem('STABLECOIN_LIQUIDITY', '稳定币流动性', '未接入'),
    unavailableMarketItem('BTC_DOMINANCE', 'BTC 占比', '未接入'),
  ];
  const panel = buildFilteredPanel(
    sourcePanel,
    'CryptoLiquidityModule',
    ['BTC_FUNDING', 'ETH_FUNDING', 'SOL_FUNDING', 'BNB_FUNDING', 'STABLECOIN_LIQUIDITY', 'BTC_DOMINANCE'],
    fallbackItems,
  );
  const existingSymbols = new Set(panel.items.map((item) => item.symbol));
  return {
    ...panel,
    items: [
      ...panel.items,
      ...fallbackItems.filter((item) => !existingSymbols.has(item.symbol)),
    ],
  };
}

function buildHeroAnchors(panels: PanelState, metricIds: MarketOverviewPulseMetricId[]): HeroAnchor[] {
  return metricIds.map((metricId) => {
    const entry = MARKET_OVERVIEW_METRIC_REGISTRY[metricId];
    return {
      key: metricId,
      label: entry.label,
      item: findMetricItem(panels, metricId) || missingMetricItem(metricId),
    };
  });
}

function formatHeroValue(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 'N/A';
  }
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: Math.abs(value) >= 100 ? 2 : 3,
  }).format(value);
}

function formatHeroChange(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 'N/A';
  }
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
}

function heroToneClass(item: MarketOverviewItem | undefined): string {
  if (!item || item.changePct == null) {
    return 'text-white/35';
  }
  return item.changePct >= 0
    ? 'text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.36)]'
    : 'text-rose-400 drop-shadow-[0_0_8px_rgba(251,113,133,0.36)]';
}

function formatCoverageSummaryLine(label: string, summary: Record<CardCoverageKind, number>, language: 'zh' | 'en'): string {
  if (language === 'en') {
    return `Coverage (${label}): real ${summary.real} | mixed ${summary.mixed} | fallback ${summary.fallback}`;
  }
  return `${label}数据覆盖：真实 ${summary.real} | 混合 ${summary.mixed} | 备用 ${summary.fallback}`;
}

function buildMarketOverviewSummaryText(params: {
  activeCategoryLabel: string;
  coverageSummary: Record<CardCoverageKind, number>;
  dataQuality: DataQualitySummary;
  heroAnchors: HeroAnchor[];
  language: 'zh' | 'en';
  temperature: MarketTemperatureResponse;
  briefing: MarketBriefingResponse;
}): string {
  const {
    activeCategoryLabel,
    coverageSummary,
    dataQuality,
    heroAnchors,
    language,
    temperature,
    briefing,
  } = params;

  const heroLine = heroAnchors
    .slice(0, 3)
    .map((anchor) => {
      const displayLabel = anchor.item
        ? resolveMarketOverviewDisplayLabel(anchor.item, language)
        : { primary: anchor.label, secondary: anchor.key };
      return `${displayLabel.primary} ${formatHeroValue(anchor.item?.value)} (${formatHeroChange(anchor.item?.changePct)})`;
    })
    .join(' | ');

  const briefingLine = briefing.items
    .slice(0, 3)
    .map((item) => `${item.title}: ${item.message}`)
    .join(language === 'en' ? ' | ' : '；');

  const lines = language === 'en'
    ? [
      `Market Overview | ${activeCategoryLabel}`,
      `Market temperature: ${temperature.scores.overall.label} (${temperature.scores.overall.value})`,
      `Data quality: ${dataQuality.status}`,
      formatCoverageSummaryLine(activeCategoryLabel, coverageSummary, language),
      `Cross asset snapshot: ${heroLine}`,
      `Briefing: ${briefingLine}`,
    ]
    : [
      `市场总览 | ${activeCategoryLabel}`,
      `市场温度：${temperature.scores.overall.label}（${temperature.scores.overall.value}）`,
      `数据质量：${dataQuality.status}`,
      formatCoverageSummaryLine(activeCategoryLabel, coverageSummary, language),
      `跨资产快照：${heroLine}`,
      `市场解读：${briefingLine}`,
    ];

  return lines.join('\n');
}

const CrossAssetHeroRibbon: React.FC<{ anchors: HeroAnchor[] }> = ({ anchors }) => {
  const { language } = useI18n();
  return (
    <GlassCard
      as="section"
      data-testid="market-overview-hero-ribbon"
      data-mobile-order="pulse"
      className={cn(MARKET_OVERVIEW_GHOST_CARD_CLASS, 'overflow-hidden p-0')}
      aria-label="Cross asset hero ribbon"
    >
      <div className="grid grid-cols-[repeat(auto-fit,minmax(112px,1fr))] divide-x divide-y divide-white/5">
        {anchors.map((anchor) => {
          const displayLabel = anchor.item ? resolveMarketOverviewDisplayLabel(anchor.item, language) : { primary: anchor.label, secondary: anchor.key };
          return (
            <div
              key={anchor.key}
              data-testid={`market-overview-hero-${anchor.key}`}
              className="min-w-0 bg-white/[0.02] px-4 py-3.5"
            >
              <p className="block truncate text-[10px] font-semibold uppercase tracking-widest text-white/50">
                {displayLabel.primary}
                {displayLabel.secondary ? <span className="ml-1 text-white/28">({displayLabel.secondary})</span> : null}
              </p>
              <p className="mt-1 truncate font-mono text-[22px] font-semibold leading-none text-white md:text-2xl">
                {formatHeroValue(anchor.item?.value)}
              </p>
              <p className={`mt-1 font-mono text-xs font-semibold ${heroToneClass(anchor.item)}`}>
                {formatHeroChange(anchor.item?.changePct)}
              </p>
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
};

function formatNumber(value: number | null | undefined, digits = 2): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '-';
  }
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(value);
}

function scoreTone(score: MarketTemperatureScore, pressure = false): string {
  if (pressure) {
    return score.value >= 65 ? 'text-rose-400' : score.value >= 55 ? 'text-amber-300' : 'text-emerald-400';
  }
  return score.value >= 76 ? 'text-amber-200' : score.value >= 61 ? 'text-emerald-400' : score.value <= 45 ? 'text-sky-300' : 'text-white';
}

function confidenceLabel(confidence?: number): string {
  if (confidence === 0) {
    return '数据不足';
  }
  if (confidence == null) {
    return '中';
  }
  if (confidence >= 0.75) {
    return '高';
  }
  if (confidence >= 0.45) {
    return '中';
  }
  return '低';
}

function isTemperatureReliable(data: MarketTemperatureResponse): boolean {
  return Boolean(
    data.isReliable !== false
    && (data.confidence == null || data.confidence >= 0.45)
    && (data.reliableInputCount == null || data.reliableInputCount >= 3),
  );
}

function isFallbackOnlyMeta(meta: {
  source?: string;
  freshness?: string;
  isFallback?: boolean;
  isReliable?: boolean;
  metadata?: { isReliable?: boolean };
  items?: Array<{ source?: string; freshness?: string; isFallback?: boolean }>;
}): boolean {
  const items = meta.items || [];
  return Boolean(
    meta.source === 'fallback'
    || meta.freshness === 'fallback'
    || meta.isFallback
    || meta.isReliable === false
    || meta.metadata?.isReliable === false
    || (items.length > 0 && items.every((item) => item.isFallback || item.freshness === 'fallback' || item.source === 'fallback')),
  );
}

function isItemFallback(item: { source?: string; freshness?: string; isFallback?: boolean }): boolean {
  return Boolean(item.isFallback || item.freshness === 'fallback' || item.source === 'fallback');
}

function getCardMeta(panels: PanelState, cardKey: CardKey): {
  source?: string;
  freshness?: string;
  isFallback?: boolean;
  isReliable?: boolean;
  metadata?: { isReliable?: boolean };
  items?: Array<{ source?: string; freshness?: string; isFallback?: boolean }>;
} {
  if (cardKey === 'futures') {
    return panels.futures;
  }
  if (cardKey === 'cnShortSentiment') {
    return panels.cnShortSentiment;
  }
  return panels[cardKey] || {};
}

function getCardCoverageKind(panels: PanelState, cardKey: CardKey): CardCoverageKind {
  const meta = getCardMeta(panels, cardKey);
  const items = meta.items || [];
  if (!meta.source && !meta.freshness && items.length === 0) {
    return 'fallback';
  }
  if (meta.source === 'error' || meta.freshness === 'error') {
    return 'mixed';
  }
  if (isFallbackOnlyMeta(meta)) {
    return 'fallback';
  }
  if (meta.source === 'mixed' || items.some(isItemFallback)) {
    return 'mixed';
  }
  return 'real';
}

function summarizeCardCoverage(panels: PanelState, cards: CardKey[]): Record<CardCoverageKind, number> {
  return cards.reduce<Record<CardCoverageKind, number>>((summary, cardKey) => {
    summary[getCardCoverageKind(panels, cardKey)] += 1;
    return summary;
  }, { real: 0, mixed: 0, fallback: 0 });
}

type FreshnessCountKey = 'live' | 'delayed' | 'cached' | 'stale' | 'fallback' | 'mock' | 'error';
type DataQualitySummary = {
  status: string;
  counts: Record<FreshnessCountKey, number>;
  hasConcern: boolean;
};

function collectFreshnessValues(panels: PanelState): FreshnessCountKey[] {
  const values: FreshnessCountKey[] = [];
  const push = (freshness?: string, isFallback?: boolean, isStale?: boolean) => {
    if (freshness && ['live', 'delayed', 'cached', 'stale', 'fallback', 'mock', 'error'].includes(freshness)) {
      values.push(freshness as FreshnessCountKey);
    } else if (isFallback) {
      values.push('fallback');
    } else if (isStale) {
      values.push('stale');
    } else {
      values.push('cached');
    }
  };
  const panelKeys: CardKey[] = ['indices', 'volatility', 'crypto', 'sentiment', 'fundsFlow', 'macro', 'cnIndices', 'cnBreadth', 'cnFlows', 'sectorRotation', 'usBreadth', 'rates', 'fxCommodities'];
  panelKeys.forEach((key) => {
    const panel = panels[key] as MarketOverviewPanel | undefined;
    if (!panel) {
      return;
    }
    push(panel.freshness, panel.isFallback, panel.isStale);
    panel.items.forEach((item) => push(item.freshness, item.isFallback, item.isStale));
  });
  push(panels.temperature.freshness, panels.temperature.isFallback, panels.temperature.isStale);
  push(panels.briefing.freshness, panels.briefing.isFallback, panels.briefing.isStale);
  push(panels.futures.freshness, panels.futures.isFallback, panels.futures.isStale);
  panels.futures.items.forEach((item) => push(item.freshness, item.isFallback, item.isStale));
  push(panels.cnShortSentiment.freshness, panels.cnShortSentiment.isFallback, panels.cnShortSentiment.isStale);
  return values;
}

function summarizeDataQuality(panels: PanelState): DataQualitySummary {
  const counts: Record<FreshnessCountKey, number> = {
    live: 0,
    delayed: 0,
    cached: 0,
    stale: 0,
    fallback: 0,
    mock: 0,
    error: 0,
  };
  collectFreshnessValues(panels).forEach((freshness) => {
    counts[freshness] += 1;
  });
  const status = counts.error > 0
    ? '异常'
    : counts.stale > 0
      ? '存在过期数据'
      : counts.fallback + counts.mock > 0
        ? '部分备用'
        : '良好';
  return {
    status,
    counts,
    hasConcern: counts.fallback + counts.mock + counts.stale + counts.error > 0,
  };
}

type DecisionChip = {
  label: '风险' | '流动性' | '宽度' | '观察';
  value: string;
  tone?: string;
};

function describeDirectionalItem(item?: MarketOverviewItem, fallbackLabel = 'N/A'): string {
  if (!item) {
    return fallbackLabel;
  }
  const label = item.label || item.symbol;
  if (item.changePct == null || !Number.isFinite(item.changePct)) {
    return `${label} 中性`;
  }
  if (item.changePct > 0.15) {
    return `${label} 偏强`;
  }
  if (item.changePct < -0.15) {
    return `${label} 偏弱`;
  }
  return `${label} 横盘`;
}

function scoreStateLabel(score: MarketTemperatureScore, pressure = false): string {
  if (pressure) {
    return score.value >= 65 ? '偏高' : score.value >= 55 ? '中性偏高' : score.value <= 40 ? '偏低' : '中性';
  }
  return score.label || (score.value >= 60 ? '偏强' : score.value <= 45 ? '偏弱' : '中性');
}

function buildDecisionChipTone(value: number, pressure = false): string {
  if (pressure) {
    return value >= 65 ? 'border-rose-300/25 text-rose-200' : value >= 55 ? 'border-amber-300/25 text-amber-200' : 'border-emerald-300/20 text-emerald-200';
  }
  return value >= 60 ? 'border-emerald-300/20 text-emerald-200' : value <= 45 ? 'border-sky-300/20 text-sky-200' : 'border-white/10 text-white/60';
}

function buildMarketDecision(params: {
  activeCategory: MarketOverviewTab;
  panels: PanelState;
  dataQuality: DataQualitySummary;
}): { text: string; chips: DecisionChip[] } {
  const { activeCategory, panels, dataQuality } = params;
  const temperature = panels.temperature;
  const reliable = isTemperatureReliable(temperature);
  const hasLoadedSignals = CATEGORY_CARDS[activeCategory].some((cardKey) => {
    const meta = getCardMeta(panels, cardKey);
    return Boolean(meta.source || meta.freshness || (meta.items?.length || 0) > 0);
  });
  if (!reliable && !hasLoadedSignals) {
    const watchSignals = MARKET_OVERVIEW_SIGNAL_WATCH[activeCategory].slice(0, 3).join(' / ');
    return {
      text: '数据不足 · 等待更多实时源',
      chips: [
        { label: '风险', value: '数据不足', tone: 'border-amber-300/20 text-amber-200' },
        { label: '流动性', value: 'N/A', tone: 'border-white/10 text-white/45' },
        { label: '宽度', value: 'N/A', tone: 'border-white/10 text-white/45' },
        { label: '观察', value: watchSignals, tone: 'border-white/10 text-white/60' },
      ],
    };
  }

  const vix = findPanelItem(panels.volatility, ['VIX']);
  const btc = findPanelItem(panels.crypto, ['BTC']);
  const spx = findPanelItem(panels.indices, ['SPX']);
  const csi = findPanelItem(panels.cnIndices, ['CSI300', '000300.SH']) || findPanelItem(panels.indices, ['CSI300']);
  const us10y = findPanelItem(panels.rates, ['US10Y']) || findPanelItem(panels.macro, ['US10Y']);
  const dxy = findPanelItem(panels.fxCommodities, ['DXY']) || findPanelItem(panels.macro, ['DXY']);
  const hsi = findPanelItem(panels.cnIndices, ['HSI']);

  const riskLabel = reliable ? scoreStateLabel(temperature.scores.overall) : '数据不足';
  const liquidityLabel = reliable ? scoreStateLabel(temperature.scores.liquidity) : 'N/A';
  const breadthLabel = reliable ? scoreStateLabel(temperature.scores.cnMoneyEffect) : 'N/A';
  const watchSignals = MARKET_OVERVIEW_SIGNAL_WATCH[activeCategory]
    .map((metricId) => findMetricItem(panels, metricId)?.symbol || metricId)
    .slice(0, 3)
    .join(' / ') || '实时源';
  const chips: DecisionChip[] = [
    { label: '风险', value: riskLabel, tone: reliable ? buildDecisionChipTone(temperature.scores.overall.value) : 'border-amber-300/20 text-amber-200' },
    { label: '流动性', value: liquidityLabel, tone: reliable ? buildDecisionChipTone(temperature.scores.liquidity.value) : 'border-white/10 text-white/45' },
    { label: '宽度', value: breadthLabel, tone: reliable ? buildDecisionChipTone(temperature.scores.cnMoneyEffect.value) : 'border-white/10 text-white/45' },
    { label: '观察', value: watchSignals, tone: 'border-white/10 text-white/60' },
  ];

  if (!reliable) {
    return {
      text: '数据不足 · 等待更多实时源',
      chips,
    };
  }

  const compareUsCn = typeof spx?.changePct === 'number' && typeof csi?.changePct === 'number'
    ? spx.changePct >= csi.changePct ? '美股强于A股' : 'A股强于美股'
    : '跨市场强弱待确认';
  const texts: Record<MarketOverviewTab, string> = {
    all: `风险${riskLabel} · ${compareUsCn} · ${describeDirectionalItem(btc, 'BTC 待确认')} · 重点观察 ${watchSignals}`,
    us: `美股风险${scoreStateLabel(temperature.scores.usRiskAppetite)} · ${describeDirectionalItem(vix, 'VIX 待确认')} · ${describeDirectionalItem(spx, '标普500 待确认')}`,
    cn: `A股宽度${breadthLabel} · ${describeDirectionalItem(csi, '沪深300 待确认')} · ${describeDirectionalItem(hsi, '港股待确认')}`,
    global: `宏观压力${scoreStateLabel(temperature.scores.macroPressure, true)} · ${describeDirectionalItem(dxy, 'DXY 待确认')} · ${describeDirectionalItem(us10y, 'US10Y 待确认')}`,
    crypto: `${describeDirectionalItem(btc, 'BTC 待确认')} · ${describeDirectionalItem(findPanelItem(panels.crypto, ['ETH']), 'ETH 待确认')} · 宏观风险${riskLabel}`,
  };

  const qualityHint = dataQuality.hasConcern ? ` · ${dataQuality.status}` : '';
  return {
    text: `${texts[activeCategory]}${qualityHint}`,
    chips,
  };
}

const MarketDecisionStrip: React.FC<{
  activeCategory: MarketOverviewTab;
  panels: PanelState;
  dataQuality: DataQualitySummary;
}> = ({ activeCategory, panels, dataQuality }) => {
  const decision = buildMarketDecision({ activeCategory, panels, dataQuality });
  const reliable = isTemperatureReliable(panels.temperature);
  return (
    <section
      data-testid="market-decision-strip"
      data-command-bar="market-state"
      data-mobile-order="decision"
      data-market-research-flow="state"
      className={cn(
        MARKET_OVERVIEW_GHOST_CARD_CLASS,
        'relative overflow-hidden p-0 shadow-[0_0_24px_rgba(59,130,246,0.10)]',
      )}
    >
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-blue-500/0 via-blue-400/45 to-purple-500/0" aria-hidden="true" />
      <div className="flex min-w-0 flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <p className="text-[10px] font-bold tracking-widest text-white/40">市场状态</p>
          <p data-testid="market-decision-text" className="mt-1 line-clamp-2 font-mono text-base font-semibold leading-6 text-white/88 md:truncate">
            {decision.text}
          </p>
          {!reliable ? (
            <p data-testid="market-command-safe-state" className="mt-1 truncate text-[11px] font-semibold text-amber-200/78">
              当前不生成强判断，只显示可验证信号
            </p>
          ) : null}
        </div>
        <div data-testid="market-command-chips" className="ui-scroll-x-quiet -mx-1 flex min-w-0 max-w-full gap-2 px-1 md:mx-0 md:shrink-0 md:px-0">
          {decision.chips.map((chip) => (
            <span
              key={`${chip.label}-${chip.value}`}
              className={cn('inline-flex shrink-0 items-center gap-1 rounded-md border bg-white/[0.025] px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-widest', chip.tone)}
            >
              <span className="text-white/36">{chip.label}</span>
              <span className="max-w-[150px] truncate font-mono normal-case tracking-normal">{chip.value}</span>
            </span>
          ))}
        </div>
      </div>
    </section>
  );
};

const CompactRailCard: React.FC<{
  railKey: string;
  testId: string;
  eyebrow: string;
  title: string;
  value?: string;
  tone?: string;
  lines: React.ReactNode[];
}> = ({ railKey, testId, eyebrow, title, value, tone = 'text-white', lines }) => (
  <MarketOverviewCardFrame
    size="rail"
    testId="market-overview-compact-rail-card"
    railKey={railKey}
    className="min-w-0 overflow-hidden"
  >
    <div data-testid={testId} className="flex h-full min-w-0 flex-col gap-2">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[10px] font-bold uppercase tracking-widest text-white/40">{eyebrow}</p>
          <p className="mt-1 truncate text-sm font-semibold text-white/80">{title}</p>
        </div>
        {value ? <p className={cn('shrink-0 text-right font-mono text-lg font-semibold leading-none tabular-nums', tone)}>{value}</p> : null}
      </div>
      <div className="min-w-0 space-y-1 text-[11px] leading-4 text-white/46">
        {lines.slice(0, 4).map((line, index) => (
          <div key={index} className="truncate">{line}</div>
        ))}
      </div>
    </div>
  </MarketOverviewCardFrame>
);

const CategoryCoverageSummary: React.FC<{
  label: string;
  summary: Record<CardCoverageKind, number>;
}> = ({ label, summary }) => (
  <CompactRailCard
    railKey="coverage"
    testId="market-overview-rail-coverage"
    eyebrow="覆盖"
    title={`${label}数据覆盖`}
    value={`${summary.real}/${summary.real + summary.mixed + summary.fallback}`}
    lines={[
      <span key="coverage" data-testid="market-overview-coverage-summary"><span className="text-white/62">{label}数据覆盖：</span><span className="font-mono">真实 {summary.real} · 混合 {summary.mixed} · 备用 {summary.fallback}</span></span>,
    ]}
  />
);

const SignalWatchRailCard: React.FC<{ panels: PanelState; activeCategory: MarketOverviewTab }> = ({ panels, activeCategory }) => {
  const chips = MARKET_OVERVIEW_SIGNAL_WATCH[activeCategory]
    .map((metricId) => [metricId, findMetricItem(panels, metricId) || missingMetricItem(metricId)] as const);

  return (
    <MarketOverviewCardFrame
      size="rail"
      testId="market-overview-compact-rail-card"
      railKey="signal-watch"
      className="min-w-0 overflow-hidden"
    >
      <div data-testid="market-overview-rail-signal-watch" className="flex h-full min-w-0 flex-col gap-2">
        <div className="min-w-0">
          <p className="truncate text-[10px] font-bold tracking-widest text-white/40">信号观察</p>
          <p className="mt-1 truncate text-sm font-semibold text-white/80">关键观测</p>
        </div>
        <div className="flex min-w-0 flex-wrap gap-1.5 overflow-hidden">
          {chips.map(([label, item]) => (
            <span key={label} className="inline-flex max-w-full items-center gap-1 rounded-md border border-white/10 bg-white/[0.025] px-2 py-1 text-[10px] font-bold uppercase tracking-widest text-white/48">
              <span className="shrink-0">{label}</span>
              <span className={cn('min-w-0 truncate font-mono tracking-normal', heroToneClass(item))}>
                {formatHeroChange(item?.changePct)}
              </span>
            </span>
          ))}
        </div>
      </div>
    </MarketOverviewCardFrame>
  );
};

const ActionHintRailCard: React.FC<{ temperature: MarketTemperatureResponse }> = ({ temperature }) => {
  const reliable = isTemperatureReliable(temperature);
  return (
    <CompactRailCard
      railKey="action-hint"
      testId="market-overview-rail-action-hint"
      eyebrow="观察提示"
      title={reliable ? '同步观察' : '安全状态'}
      lines={[
        reliable ? '优先观察风险、流动性、宽度是否同向变化' : '等待实时源补齐后再生成强判断',
      ]}
    />
  );
};

const CompactStatusTile: React.FC<{
  testId: string;
  eyebrow: string;
  title: string;
  value: string;
  meta: React.ReactNode;
  tone?: string;
}> = ({ testId, eyebrow, title, value, meta, tone = 'text-white' }) => (
  <GlassCard
    as="section"
    data-testid={testId}
    className={cn(MARKET_OVERVIEW_GHOST_CARD_CLASS, 'min-w-0 p-3')}
  >
    <div className="flex min-w-0 items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-white/38">{eyebrow}</p>
        <p className="mt-1 truncate text-sm font-semibold text-white/78">{title}</p>
      </div>
      <p className={cn('shrink-0 text-right font-mono text-lg font-semibold leading-none tabular-nums', tone)}>{value}</p>
    </div>
    <div className="mt-2 min-w-0 text-xs leading-5 text-white/45">{meta}</div>
  </GlassCard>
);

const MarketTemperatureCompactSummary: React.FC<{ data: MarketTemperatureResponse }> = ({ data }) => {
  const score = data.scores.overall;
  const reliable = isTemperatureReliable(data);
  return (
    <CompactStatusTile
      testId="market-overview-temperature-summary"
      eyebrow="温度"
      title="市场温度"
      value={reliable ? formatNumber(score.value, 0) : 'N/A'}
      tone={reliable ? scoreTone(score) : 'text-white/45'}
      meta={(
        <div data-testid="market-temperature-strip" className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="font-semibold text-white/68">{reliable ? score.label : '数据不足'}</span>
          <span>信号可信：{confidenceLabel(data.confidence)}</span>
          <span className="font-mono tabular-nums">真实 {data.reliableInputCount ?? 0} · 备用 {data.fallbackInputCount ?? 0} · 排除 {data.excludedInputCount ?? 0}</span>
          {!reliable ? <span data-testid="market-temperature-unreliable-summary">真实输入不足，暂不生成综合判断</span> : null}
        </div>
      )}
    />
  );
};

const DataQualityCompactSummary: React.FC<{ summary: DataQualitySummary }> = ({ summary }) => (
  <CompactStatusTile
    testId="market-overview-data-quality-summary"
    eyebrow="质量"
    title={`数据质量：${summary.status}`}
    value={`${summary.counts.live + summary.counts.delayed + summary.counts.cached}`}
    tone={summary.hasConcern ? 'text-amber-200' : 'text-emerald-300'}
    meta={(
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <span>可用快照</span>
        <span className="font-mono tabular-nums">备用 {summary.counts.fallback} · 过期 {summary.counts.stale} · 异常 {summary.counts.error}</span>
      </div>
    )}
  />
);

const MarketBriefingCompactSummary: React.FC<{ data: MarketBriefingResponse }> = ({ data }) => {
  const lead = data.items[0];
  return (
    <CompactStatusTile
      testId="market-overview-briefing-summary"
      eyebrow="简报"
      title="今日市场解读"
      value={confidenceLabel(data.confidence)}
      tone={data.isReliable === false || data.isFallback ? 'text-amber-200' : 'text-white'}
      meta={(
        <div className="min-w-0">
          <p data-testid="market-briefing-card" className="truncate text-white/55">{lead?.message || data.warning || '暂无简报'}</p>
          {data.warning ? <p data-testid="market-briefing-warning" className="truncate text-amber-200/70">{data.warning}</p> : null}
        </div>
      )}
    />
  );
};

const MarketOverviewStatusStrip: React.FC<{
  temperature: React.ReactNode;
  dataQuality: React.ReactNode;
  briefing: React.ReactNode;
}> = ({ temperature, dataQuality, briefing }) => (
  <section
    data-testid="market-overview-status-strip"
    className="grid w-full grid-cols-1 gap-3 md:grid-cols-3 xl:grid-cols-[1.15fr_1fr_1.35fr]"
  >
    {temperature}
    {dataQuality}
    {briefing}
  </section>
);

const MarketOverviewCacheStatus: React.FC<{
  hasLocalSnapshot: boolean;
  localSnapshotSavedAt?: string;
  loading: boolean;
  refreshingPanel: PanelKey | null;
  refreshErrorCount: number;
  dataQuality: DataQualitySummary;
}> = ({ hasLocalSnapshot, localSnapshotSavedAt, loading, refreshingPanel, refreshErrorCount, dataQuality }) => {
  const statusLabel = refreshErrorCount > 0
    ? '刷新失败'
    : loading && hasLocalSnapshot
      ? '本地缓存'
      : dataQuality.counts.stale > 0
        ? '过期'
        : dataQuality.counts.fallback > 0
          ? '缓存'
          : '实时';
  const message = refreshErrorCount > 0
    ? '部分数据源刷新失败，当前显示最近成功快照'
    : loading && hasLocalSnapshot
      ? '正在刷新，当前显示本地缓存'
      : dataQuality.hasConcern
        ? '部分面板使用缓存或备用快照'
        : '实时数据已更新';
  const timestamp = formatMarketOverviewTimestamp(localSnapshotSavedAt) || '';
  return (
    <details
      data-testid="market-overview-cache-status"
      data-market-research-flow="cache"
      data-mobile-order="cache-status"
      className={cn(
        'group min-w-0 rounded-xl border px-3 py-2 text-xs',
        refreshErrorCount > 0 || dataQuality.hasConcern
          ? 'border-amber-300/18 bg-amber-400/[0.055] text-amber-100/82'
          : 'border-emerald-300/16 bg-emerald-400/[0.045] text-emerald-100/78',
      )}
    >
      <summary className="flex cursor-pointer list-none flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <span className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="shrink-0 rounded-md border border-current/20 px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-widest">
            {statusLabel}
          </span>
          <span className="min-w-0 truncate">{message}</span>
        </span>
        <span className="shrink-0 text-[10px] font-semibold text-white/42 group-open:text-white/62">
          {dataQuality.hasConcern || refreshErrorCount > 0 ? '查看数据状态' : '状态详情'}
        </span>
      </summary>
      <div className="mt-2 flex min-w-0 flex-col gap-2 border-t border-white/[0.05] pt-2 md:flex-row md:items-center md:justify-between">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="shrink-0 rounded-md border border-current/20 px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-widest">
            {statusLabel}
          </span>
          {refreshingPanel ? <span className="font-mono text-[10px] text-white/45">刷新 {String(refreshingPanel)}</span> : null}
          <span className="font-mono text-[10px] text-white/45">
            可用 {dataQuality.counts.live + dataQuality.counts.delayed + dataQuality.counts.cached} · 备用 {dataQuality.counts.fallback} · 过期 {dataQuality.counts.stale}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-2 font-mono text-[10px] tracking-widest text-white/42">
          {timestamp ? <span>本地 {timestamp}</span> : null}
          <span data-testid="market-overview-refresh-error-count">错误 {refreshErrorCount}</span>
        </div>
      </div>
    </details>
  );
};

const MarketOverviewRow: React.FC<{
  row: MarketOverviewLayoutRow;
  children: React.ReactNode;
}> = ({ row, children }) => (
  <section
    data-testid="market-overview-row"
    data-row-id={row.id}
    data-row-tier={row.tier}
    data-row-columns={row.columns}
    className={cn(
      'grid w-full min-w-0 grid-cols-1 items-stretch gap-4',
      row.columns === 2 ? 'md:grid-cols-2 md:auto-rows-fr' : '',
      row.columns === 3 ? 'md:grid-cols-3 md:auto-rows-fr' : '',
    )}
  >
    {children}
  </section>
);

const MarketOverviewFullWidthRow: React.FC<{
  row: MarketOverviewLayoutRow;
  children: React.ReactNode;
}> = ({ row, children }) => (
  <MarketOverviewRow row={{ ...row, columns: 1 }}>
    {children}
  </MarketOverviewRow>
);

const MarketOverviewTwoColumnRow: React.FC<{
  row: MarketOverviewLayoutRow;
  children: React.ReactNode;
}> = ({ row, children }) => (
  <MarketOverviewRow row={{ ...row, columns: 2 }}>
    {children}
  </MarketOverviewRow>
);

const MarketOverviewThreeColumnRow: React.FC<{
  row: MarketOverviewLayoutRow;
  children: React.ReactNode;
}> = ({ row, children }) => (
  <MarketOverviewRow row={{ ...row, columns: 3 }}>
    {children}
  </MarketOverviewRow>
);

const MarketOverviewMainStack: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div data-testid="market-overview-main-stack" className="flex min-w-0 flex-col gap-4">
    {children}
  </div>
);

const ExecutiveSecondaryGroups: React.FC<{
  panels: PanelState;
}> = ({ panels }) => {
  const groups: Array<{
    id: string;
    label: string;
    cardKey: CardKey;
    focus: string;
    item?: MarketOverviewItem;
  }> = [
    { id: 'us', label: 'US', cardKey: 'indices', focus: 'SPX / VIX', item: findPanelItem(panels.indices, ['SPX']) },
    { id: 'cn', label: 'CN/HK', cardKey: 'cnIndices', focus: 'CSI300 / HSI', item: findPanelItem(panels.cnIndices, ['CSI300', '000300.SH']) || findPanelItem(panels.cnIndices, ['HSI']) },
    { id: 'macro', label: 'MACRO', cardKey: 'rates', focus: 'US10Y / DXY', item: findPanelItem(panels.rates, ['US10Y']) || findPanelItem(panels.fxCommodities, ['DXY']) },
    { id: 'crypto', label: 'CRYPTO', cardKey: 'crypto', focus: 'BTC / ETH', item: findPanelItem(panels.crypto, ['BTC']) },
  ];

  return (
    <section
      data-testid="market-overview-executive-secondary-groups"
      className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4"
    >
      {groups.map((group) => {
        const coverage = getCardCoverageKind(panels, group.cardKey);
        const freshness = getCardMeta(panels, group.cardKey).freshness;
        return (
          <MarketOverviewCardFrame
            key={group.id}
            size="compact"
            testId={`market-overview-secondary-group-${group.id}`}
            className="h-full"
          >
            <div className="flex h-full min-w-0 flex-col justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[10px] font-bold uppercase tracking-widest text-white/40">{group.label}</p>
                <p className="mt-1 truncate text-sm font-semibold text-white/80">{group.focus}</p>
              </div>
              <div className="flex min-w-0 items-end justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-mono text-lg font-semibold leading-none text-white">
                    {formatHeroValue(group.item?.value)}
                  </p>
                  <p className={cn('mt-1 truncate font-mono text-[11px] font-bold', heroToneClass(group.item))}>
                    {formatHeroChange(group.item?.changePct)}
                  </p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  <DataFreshnessBadge
                    freshness={(freshness || (coverage === 'fallback' ? 'fallback' : 'cached')) as MarketOverviewPanel['freshness']}
                    status={coverage === 'mixed' ? 'partial' : undefined}
                    className="px-1.5 text-[9px]"
                  />
                  <span className="font-mono text-[10px] uppercase text-white/32">{coverage}</span>
                </div>
              </div>
            </div>
          </MarketOverviewCardFrame>
        );
      })}
    </section>
  );
};

const DataQualityCompactRailCard: React.FC<{ summary: DataQualitySummary }> = ({ summary }) => (
  <CompactRailCard
    railKey="quality"
    testId="market-overview-rail-quality"
    eyebrow="质量"
    title={`数据质量：${summary.status}`}
    value={`${summary.counts.live + summary.counts.delayed + summary.counts.cached}`}
    tone={summary.hasConcern ? 'text-amber-200' : 'text-emerald-300'}
    lines={[
      <span key="quality" data-testid="market-data-quality">可用快照 · 备用 {summary.counts.fallback}</span>,
      <span key="risk" className="font-mono">过期 {summary.counts.stale} · 缺失 {summary.counts.error}</span>,
    ]}
  />
);

const CnShortSentimentCard: React.FC<{
  data: CnShortSentimentResponse;
  loading?: boolean;
  refreshing?: boolean;
  onRefresh: () => void;
}> = ({ data, loading = false, refreshing = false, onRefresh }) => {
  const { t } = useI18n();
  const title = t('marketOverviewPage.cards.cnShortSentiment.title');
  const panel: MarketOverviewPanel = {
    panelName: 'CnShortSentimentCard',
    status: data.isFallback ? 'failure' : 'success',
    lastRefreshAt: data.updatedAt,
    items: [],
    ...data,
  };
  const metrics = [
    ['limitUpCount', t('marketOverviewPage.cards.cnShortSentiment.metrics.limitUpCount'), data.metrics.limitUpCount],
    ['limitDownCount', t('marketOverviewPage.cards.cnShortSentiment.metrics.limitDownCount'), data.metrics.limitDownCount],
    ['failedLimitUpRate', t('marketOverviewPage.cards.cnShortSentiment.metrics.failedLimitUpRate'), `${data.metrics.failedLimitUpRate}%`],
    ['maxConsecutiveLimitUps', t('marketOverviewPage.cards.cnShortSentiment.metrics.maxConsecutiveLimitUps'), data.metrics.maxConsecutiveLimitUps],
    ['yesterdayLimitUpPerformance', t('marketOverviewPage.cards.cnShortSentiment.metrics.yesterdayLimitUpPerformance'), `${data.metrics.yesterdayLimitUpPerformance >= 0 ? '+' : ''}${data.metrics.yesterdayLimitUpPerformance}%`],
    ['firstBoardCount', t('marketOverviewPage.cards.cnShortSentiment.metrics.firstBoardCount'), data.metrics.firstBoardCount],
    ['secondBoardCount', t('marketOverviewPage.cards.cnShortSentiment.metrics.secondBoardCount'), data.metrics.secondBoardCount],
    ['highBoardCount', t('marketOverviewPage.cards.cnShortSentiment.metrics.highBoardCount'), data.metrics.highBoardCount],
    ['twentyCmLimitUpCount', t('marketOverviewPage.cards.cnShortSentiment.metrics.twentyCmLimitUpCount'), data.metrics.twentyCmLimitUpCount],
  ] as const;
  const fallbackOnly = isFallbackOnlyMeta(data);
  return (
    <MarketOverviewCardFrame size="compact" className={cn('h-full', fallbackOnly ? 'border-orange-300/12' : '')}>
      <div className="flex min-h-0 h-full flex-col gap-3">
        <div className="flex shrink-0 items-center justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40">{t('marketOverviewPage.cards.cnShortSentiment.eyebrow')}</p>
            <h2 className="mt-1 truncate text-sm font-semibold text-white/84">{title}</h2>
          </div>
          <MarketOverviewRefreshButton label={t('marketOverviewPage.refreshCard', { title })} refreshing={refreshing} onRefresh={onRefresh} />
        </div>
      <div className="min-w-0 rounded-lg border border-white/[0.06] bg-white/[0.025] px-3 py-2.5">
        <div className="flex items-end justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs text-white/45">{t('marketOverviewPage.cards.cnShortSentiment.score')}</p>
            <p className={cn('mt-1 font-mono text-2xl font-semibold', fallbackOnly ? 'text-white/55' : 'text-emerald-400')}>{data.sentimentScore}</p>
          </div>
          <p className="min-w-0 max-w-[220px] truncate text-right text-xs leading-5 text-white/55">{data.summary}</p>
        </div>
      </div>
      <div className="grid min-h-0 grid-cols-2 gap-2 overflow-y-auto no-scrollbar ui-scroll-y-quiet">
        {metrics.slice(0, 6).map(([key, label, value]) => (
          <div key={key} className="min-w-0 rounded-lg border border-white/[0.06] bg-white/[0.025] px-3 py-2">
            <p className="truncate text-[10px] text-white/38">{label}</p>
            <p className="mt-1 font-mono text-sm font-semibold text-white">{value}</p>
          </div>
        ))}
      </div>
      {metrics.length > 6 ? <p className="text-[10px] text-white/38">+{metrics.length - 6} 项保留在数据源快照中</p> : null}
      {loading ? <div className="mt-3 rounded-lg border border-white/8 bg-white/[0.03] p-3 text-sm text-white/60">{t('marketOverviewPage.loading')}</div> : null}
      <MarketOverviewPanelFooter panel={panel} sourceLabel={data.sourceLabel || `${t('marketOverviewPage.cards.cnShortSentiment.source')}: ${data.source.toUpperCase()}`} />
      </div>
    </MarketOverviewCardFrame>
  );
};

const ContextMetricModuleCard: React.FC<{
  moduleId: MarketOverviewModuleId;
  title: string;
  eyebrow: string;
  description: string;
  panel: MarketOverviewPanel;
  sourceLabel: string;
  refreshing?: boolean;
  onRefresh?: () => void;
}> = ({
  moduleId,
  title,
  eyebrow,
  description,
  panel,
  sourceLabel,
  refreshing = false,
  onRefresh,
}) => {
  const { t } = useI18n();
  const visibleItems = panel.items.slice(0, 8);
  const hiddenItemCount = Math.max(panel.items.length - visibleItems.length, 0);

  return (
    <MarketOverviewCardFrame
      size={MODULE_LAYOUT_META[moduleId].size}
      testId={`market-overview-module-${moduleId}`}
      className="h-full"
    >
      <div className="flex h-full min-h-0 flex-col gap-3">
        <div className="flex shrink-0 items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-white/40">{eyebrow}</p>
            <h2 className="mt-1 truncate text-sm font-semibold text-white/84">{title}</h2>
            <p className="mt-1 line-clamp-1 text-[11px] leading-4 text-white/42">{description}</p>
          </div>
          {onRefresh ? (
            <MarketOverviewRefreshButton
              label={t('marketOverviewPage.refreshCard', { title })}
              refreshing={refreshing}
              onRefresh={onRefresh}
            />
          ) : null}
        </div>
        <div className="flex min-h-0 flex-col overflow-y-auto no-scrollbar border-y border-white/[0.045] ui-scroll-y-quiet">
          {visibleItems.map((item) => (
            <MarketOverviewDenseQuoteItem
              key={`${moduleId}-${item.symbol}`}
              item={item}
              neutralLabel={t('marketOverviewPage.direction.neutral')}
            />
          ))}
        </div>
        {hiddenItemCount > 0 ? (
          <p className="text-[10px] text-white/38">+{hiddenItemCount} 项保留在数据源快照中</p>
        ) : null}
        <MarketOverviewPanelFooter panel={panel} sourceLabel={sourceLabel} />
      </div>
    </MarketOverviewCardFrame>
  );
};

function assignPanelValue(nextPanels: PanelState, panelKey: PanelKey, value: PanelState[PanelKey]): void {
  switch (panelKey) {
    case 'indices':
    case 'volatility':
    case 'crypto':
    case 'sentiment':
    case 'fundsFlow':
    case 'macro':
    case 'cnIndices':
    case 'cnBreadth':
    case 'cnFlows':
    case 'sectorRotation':
    case 'usBreadth':
    case 'rates':
    case 'fxCommodities':
      nextPanels[panelKey] = value as MarketOverviewPanel;
      break;
    case 'temperature':
      nextPanels.temperature = normalizeMarketTemperatureResponse(value as MarketTemperatureResponse);
      break;
    case 'briefing':
      nextPanels.briefing = value as MarketBriefingResponse;
      break;
    case 'futures':
      nextPanels.futures = value as MarketFuturesResponse;
      break;
    case 'cnShortSentiment':
      nextPanels.cnShortSentiment = value as CnShortSentimentResponse;
      break;
  }
}

function describePanelError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error || '');
  const lower = message.toLowerCase();
  if (lower.includes('timeout') || lower.includes('timed out') || message.includes('超时')) {
    return '数据源请求超时';
  }
  if (lower.includes('provider_down') || lower.includes('provider_error') || lower.includes('unavailable') || message.includes('不可用')) {
    return '数据源暂不可用';
  }
  return '数据源刷新失败';
}

function fallbackPanel(panelName: string, error: unknown): MarketOverviewPanel {
  const updatedAt = new Date().toISOString();
  const warning = describePanelError(error);
  return {
    panelName,
    lastRefreshAt: updatedAt,
    status: 'failure',
    errorMessage: '更新失败：数据源刷新失败',
    source: 'error',
    sourceLabel: '数据源异常',
    updatedAt,
    asOf: updatedAt,
    freshness: 'error',
    isFallback: true,
    isStale: true,
    warning: `数据源暂不可用，请稍后自动刷新。${warning}`,
    items: [],
  };
}

function fallbackPanelValue(panelKey: PanelKey, error: unknown): PanelState[PanelKey] {
  switch (panelKey) {
    case 'temperature':
      return {
        ...FALLBACK_TEMPERATURE,
        updatedAt: new Date().toISOString(),
        warning: `数据源暂不可用，请稍后自动刷新。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'briefing':
      return {
        ...FALLBACK_BRIEFING,
        updatedAt: new Date().toISOString(),
        warning: `数据源暂不可用，请稍后自动刷新。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'futures':
      return {
        ...FALLBACK_FUTURES,
        updatedAt: new Date().toISOString(),
        isRefreshing: true,
        warning: `数据源暂不可用，请稍后自动刷新。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'cnShortSentiment':
      return {
        ...FALLBACK_CN_SHORT_SENTIMENT,
        updatedAt: new Date().toISOString(),
        isRefreshing: true,
        warning: `数据源暂不可用，请稍后自动刷新。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'indices':
      return fallbackPanel('IndexTrendsCard', error) as PanelState[PanelKey];
    case 'volatility':
      return fallbackPanel('VolatilityCard', error) as PanelState[PanelKey];
    case 'crypto':
      return {
        ...FALLBACK_CRYPTO_PANEL,
        lastRefreshAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        asOf: new Date().toISOString(),
        warning: `正在刷新，稍后自动更新。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'sentiment':
      return fallbackPanel('MarketSentimentCard', error) as PanelState[PanelKey];
    case 'fundsFlow':
      return fallbackPanel('FundsFlowCard', error) as PanelState[PanelKey];
    case 'macro':
      return fallbackPanel('MacroIndicatorsCard', error) as PanelState[PanelKey];
    case 'cnIndices':
      return fallbackPanel('ChinaIndicesCard', error) as PanelState[PanelKey];
    case 'cnBreadth':
      return fallbackPanel('ChinaBreadthCard', error) as PanelState[PanelKey];
    case 'cnFlows':
      return fallbackPanel('ChinaFlowsCard', error) as PanelState[PanelKey];
    case 'sectorRotation':
      return fallbackPanel('SectorRotationCard', error) as PanelState[PanelKey];
    case 'usBreadth':
      return fallbackPanel('UsBreadthCard', error) as PanelState[PanelKey];
    case 'rates':
      return fallbackPanel('RatesCard', error) as PanelState[PanelKey];
    case 'fxCommodities':
      return fallbackPanel('FxCommoditiesCard', error) as PanelState[PanelKey];
  }
}

function withPanelTimeout<T>(promise: Promise<T>, panelKey: PanelKey): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      reject(new Error(`${String(panelKey)} request timed out`));
    }, PANEL_REQUEST_TIMEOUT_MS);
    promise.then(
      (value) => {
        window.clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        window.clearTimeout(timer);
        reject(error);
      },
    );
  });
}

function debugMarketPanel(panelKey: PanelKey, status: 'loading' | 'success' | 'fallback' | 'error'): void {
  if (import.meta.env.DEV && import.meta.env.MODE !== 'test') {
    console.debug(`[market-overview] ${String(panelKey)} ${status}`);
  }
}

const routeEntryPanelRequestCache = new Map<string, Promise<PanelState[PanelKey]>>();

function loadPanelWithRouteEntryDedupe(
  panelKey: PanelKey,
  loadPanel: () => Promise<PanelState[PanelKey]>,
): Promise<PanelState[PanelKey]> {
  const cacheKey = String(panelKey);
  const cached = routeEntryPanelRequestCache.get(cacheKey);
  if (cached) {
    return cached;
  }
  const promise = loadPanel();
  routeEntryPanelRequestCache.set(cacheKey, promise);
  window.queueMicrotask(() => {
    if (routeEntryPanelRequestCache.get(cacheKey) === promise) {
      routeEntryPanelRequestCache.delete(cacheKey);
    }
  });
  return promise;
}

type CryptoStreamSubscriber = (update: {
  status: CryptoRealtimeStatus;
  panel?: MarketOverviewPanel;
}) => void;

const cryptoStreamSubscribers = new Set<CryptoStreamSubscriber>();
let sharedCryptoEventSource: EventSource | null = null;
let latestCryptoStreamStatus: CryptoRealtimeStatus = 'snapshot';

function publishCryptoStreamUpdate(update: { status: CryptoRealtimeStatus; panel?: MarketOverviewPanel }): void {
  latestCryptoStreamStatus = update.status;
  cryptoStreamSubscribers.forEach((subscriber) => subscriber(update));
}

function ensureSharedCryptoStream(): void {
  if (typeof window === 'undefined' || typeof window.EventSource === 'undefined') {
    publishCryptoStreamUpdate({ status: 'snapshot' });
    return;
  }
  if (sharedCryptoEventSource) {
    return;
  }
  const eventSource = new window.EventSource(marketApi.cryptoStreamUrl(), { withCredentials: true });
  sharedCryptoEventSource = eventSource;
  eventSource.onopen = () => {
    publishCryptoStreamUpdate({ status: 'live' });
  };
  eventSource.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data) as Record<string, unknown>;
      const panel = marketApi.normalizeCryptoStreamPayload(payload);
      publishCryptoStreamUpdate({
        panel,
        status: panel.freshness === 'live' ? 'live' : 'snapshot',
      });
    } catch {
      publishCryptoStreamUpdate({ status: 'snapshot' });
    }
  };
  eventSource.onerror = () => {
    publishCryptoStreamUpdate({ status: 'reconnecting' });
  };
}

function subscribeToCryptoStream(subscriber: CryptoStreamSubscriber): () => void {
  cryptoStreamSubscribers.add(subscriber);
  ensureSharedCryptoStream();
  subscriber({ status: latestCryptoStreamStatus });
  return () => {
    cryptoStreamSubscribers.delete(subscriber);
    if (cryptoStreamSubscribers.size > 0 || typeof window === 'undefined') {
      return;
    }
    window.queueMicrotask(() => {
      if (cryptoStreamSubscribers.size === 0) {
        sharedCryptoEventSource?.close();
        sharedCryptoEventSource = null;
        latestCryptoStreamStatus = 'snapshot';
      }
    });
  };
}

const MarketOverviewPage: React.FC = () => {
  const { language, t } = useI18n();
  const initialLocalSnapshot = useMemo(() => buildInitialPanelsFromLocalSnapshot(), []);
  const [panels, setPanels] = useState<PanelState>(initialLocalSnapshot.panels);
  const [loading, setLoading] = useState(initialLocalSnapshot.source !== 'local');
  const [hasLocalSnapshot, setHasLocalSnapshot] = useState(initialLocalSnapshot.source === 'local');
  const [localSnapshotSavedAt, setLocalSnapshotSavedAt] = useState<string | undefined>(initialLocalSnapshot.savedAt);
  const [refreshErrors, setRefreshErrors] = useState<Record<string, string>>({});
  const [refreshingPanel, setRefreshingPanel] = useState<PanelKey | null>(null);
  const [activeCategory, setActiveCategory] = useState<MarketOverviewTab>('all');
  const [cryptoRealtimeStatus, setCryptoRealtimeStatus] = useState<CryptoRealtimeStatus>('snapshot');
  const [exportSummaryFeedback, setExportSummaryFeedback] = useState<string | null>(null);

  const loadPanels = useCallback(async (cancelledRef?: { current: boolean }) => {
    setLoading(true);
    const stagedRequests = MARKET_OVERVIEW_STAGED_REQUEST_GROUPS.flatMap((group) => group.requests);
    let remaining = MARKET_OVERVIEW_PRIMARY_REQUESTS.length + stagedRequests.length;
    const markSettled = () => {
      remaining -= 1;
      if (remaining <= 0 && !cancelledRef?.current) {
        setLoading(false);
      }
    };

    const runRequest = async ([panelKey, loadPanel]: PanelRequest) => {
      debugMarketPanel(panelKey, 'loading');
      try {
        const panel = await withPanelTimeout(loadPanelWithRouteEntryDedupe(panelKey, loadPanel), panelKey);
        if (!cancelledRef?.current) {
          setRefreshErrors((currentErrors) => {
            const nextErrors = { ...currentErrors };
            delete nextErrors[String(panelKey)];
            return nextErrors;
          });
          setPanels((currentPanels) => {
            const nextPanels = { ...currentPanels };
            assignPanelValue(nextPanels, panelKey, panel);
            return nextPanels;
          });
        }
        debugMarketPanel(panelKey, 'success');
      } catch (error) {
        if (!cancelledRef?.current) {
          setRefreshErrors((currentErrors) => ({
            ...currentErrors,
            [String(panelKey)]: describePanelError(error),
          }));
          setPanels((currentPanels) => {
            const nextPanels = { ...currentPanels };
            if (!currentPanels[panelKey]) {
              assignPanelValue(nextPanels, panelKey, fallbackPanelValue(panelKey, error));
            }
            return nextPanels;
          });
        }
        debugMarketPanel(panelKey, 'fallback');
      } finally {
        markSettled();
      }
    };

    const primaryPromises = MARKET_OVERVIEW_PRIMARY_REQUESTS.map(runRequest);
    const stagedPromises = MARKET_OVERVIEW_STAGED_REQUEST_GROUPS.flatMap((group) => (
      group.requests.map((request) => new Promise<void>((resolve) => {
        window.setTimeout(() => {
          if (cancelledRef?.current) {
            markSettled();
            resolve();
            return;
          }
          void runRequest(request).finally(resolve);
        }, group.delayMs);
      }))
    ));

    await Promise.allSettled([...primaryPromises, ...stagedPromises]);
  }, []);

  const refreshPanel = useCallback(async (
    panelKey: PanelKey,
    loadPanel: () => Promise<PanelState[PanelKey]>,
  ) => {
    setRefreshingPanel(panelKey);
    debugMarketPanel(panelKey, 'loading');
    try {
      const panel = await withPanelTimeout(loadPanel(), panelKey);
      setRefreshErrors((currentErrors) => {
        const nextErrors = { ...currentErrors };
        delete nextErrors[String(panelKey)];
        return nextErrors;
      });
      setPanels((currentPanels) => {
        const nextPanels = { ...currentPanels };
        assignPanelValue(nextPanels, panelKey, panel);
        return nextPanels;
      });
      debugMarketPanel(panelKey, 'success');
    } catch (error) {
      setRefreshErrors((currentErrors) => ({
        ...currentErrors,
        [String(panelKey)]: describePanelError(error),
      }));
      setPanels((currentPanels) => {
        if (currentPanels[panelKey]) {
          return currentPanels;
        }
        const nextPanels = { ...currentPanels };
        assignPanelValue(nextPanels, panelKey, fallbackPanelValue(panelKey, error));
        return nextPanels;
      });
      debugMarketPanel(panelKey, 'fallback');
    } finally {
      setRefreshingPanel((currentPanel) => (currentPanel === panelKey ? null : currentPanel));
    }
  }, []);

  useEffect(() => {
    const cancelledRef = { current: false };

    void loadPanels(cancelledRef).catch(() => {
      if (!cancelledRef.current) {
        setLoading(false);
      }
    });

    return () => {
      cancelledRef.current = true;
    };
  }, [loadPanels]);

  useEffect(() => {
    writeLocalMarketOverviewSnapshot(panels);
    setHasLocalSnapshot(true);
    setLocalSnapshotSavedAt(new Date().toISOString());
  }, [panels]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const cancelledRef = { current: false };
      void loadPanels(cancelledRef);
    }, AUTO_REFRESH_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, [loadPanels]);

  useEffect(() => {
    return subscribeToCryptoStream(({ panel, status }) => {
      if (panel) {
        setPanels((currentPanels) => ({
          ...currentPanels,
          crypto: panel,
        }));
      }
      setCryptoRealtimeStatus(status);
    });
  }, []);

  const categoryTabs = useMemo<Array<{ key: MarketOverviewTab; label: string }>>(() => [
    { key: 'all', label: t('marketOverviewPage.categories.all') },
    { key: 'us', label: t('marketOverviewPage.categories.us') },
    { key: 'cn', label: t('marketOverviewPage.categories.cn') },
    { key: 'global', label: t('marketOverviewPage.categories.macro') },
    { key: 'crypto', label: t('marketOverviewPage.categories.crypto') },
  ], [t]);

  const globalIndicesCard = (
    <MarketOverviewCard
      title={t('marketOverviewPage.cards.indexTrends.title')}
      eyebrow={t('marketOverviewPage.cards.indexTrends.eyebrow')}
      description={t('marketOverviewPage.cards.indexTrends.description')}
      sourceLabel={t('marketOverviewPage.cards.indexTrends.source')}
      panel={panels.indices}
      loading={loading && !panels.indices}
      refreshing={refreshingPanel === 'indices'}
      variant="denseQuote"
      onRefresh={() => {
        void refreshPanel('indices', marketOverviewApi.getIndices);
      }}
    />
  );

  const cryptoSnapshotCard = (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="flex items-center justify-end">
        <span className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-0.5 text-[10px] font-semibold uppercase text-white/55">
          {cryptoRealtimeStatus === 'live' ? 'Live' : cryptoRealtimeStatus === 'reconnecting' ? 'Reconnecting' : 'Snapshot'}
        </span>
      </div>
      {cryptoRealtimeStatus === 'reconnecting' ? (
        <div className="rounded-lg border border-amber-300/20 bg-amber-400/8 px-3 py-2 text-xs text-amber-100/80">
          实时连接断开，显示最近快照
        </div>
      ) : null}
      <div className="min-h-0 flex-1">
        <MarketOverviewCard
          title={t('marketOverviewPage.cards.crypto.title')}
          eyebrow={t('marketOverviewPage.cards.crypto.eyebrow')}
          description={t('marketOverviewPage.cards.crypto.description')}
          sourceLabel={t('marketOverviewPage.cards.crypto.source')}
          panel={panels.crypto}
          loading={loading && !panels.crypto}
          refreshing={refreshingPanel === 'crypto'}
          variant="denseQuote"
          onRefresh={() => {
            void refreshPanel('crypto', marketApi.getCrypto);
          }}
        />
      </div>
    </div>
  );

  const moduleNodes: Record<MarketOverviewModuleId, React.ReactNode> = {
    globalIndices: globalIndicesCard,
    usIndices: (
      <ContextMetricModuleCard
        moduleId="usIndices"
        title="US Index Core"
        eyebrow="US PRICE ACTION"
        description="SPX / NDX / DJI / RUT"
        panel={buildMetricPanel(panels, 'UsIndexCoreModule', ['SPX', 'NDX', 'DJI', 'RUT'])}
        sourceLabel={t('marketOverviewPage.cards.indexTrends.source')}
        refreshing={refreshingPanel === 'indices'}
        onRefresh={() => {
          void refreshPanel('indices', marketOverviewApi.getIndices);
        }}
      />
    ),
    cnHkIndices: (
      <ContextMetricModuleCard
        moduleId="cnHkIndices"
        title={t('marketOverviewPage.cards.cnIndices.title')}
        eyebrow="A股 / 港股"
        description="上证 / 深成 / 创业板 / 沪深300 / 恒生 / A50 / USDCNH"
        panel={buildMetricPanel(panels, 'CnHkIndexCoreModule', ['SHCOMP', 'SZCOMP', 'CHINEXT', 'CSI300', 'HSI', 'HSTECH', 'A50', 'USDCNH'])}
        sourceLabel={t('marketOverviewPage.cards.cnIndices.source')}
        refreshing={refreshingPanel === 'cnIndices'}
        onRefresh={() => {
          void refreshPanel('cnIndices', marketApi.getCnIndices);
        }}
      />
    ),
    cryptoCore: (
      <ContextMetricModuleCard
        moduleId="cryptoCore"
        title="加密核心"
        eyebrow="加密资产"
        description="BTC / ETH / SOL / BNB"
        panel={buildMetricPanel(panels, 'CryptoCoreModule', ['BTC', 'ETH', 'SOL', 'BNB'])}
        sourceLabel={t('marketOverviewPage.cards.crypto.source')}
        refreshing={refreshingPanel === 'crypto'}
        onRefresh={() => {
          void refreshPanel('crypto', marketApi.getCrypto);
        }}
      />
    ),
    volatility: (
      <VolatilityCard
        panel={panels.volatility}
        loading={loading && !panels.volatility}
        refreshing={refreshingPanel === 'volatility'}
        onRefresh={() => {
          void refreshPanel('volatility', marketOverviewApi.getVolatility);
        }}
      />
    ),
    fundsFlow: (
      <FundsFlowCard
        panel={panels.fundsFlow}
        loading={loading && !panels.fundsFlow}
        refreshing={refreshingPanel === 'fundsFlow'}
        onRefresh={() => {
          void refreshPanel('fundsFlow', marketOverviewApi.getFundsFlow);
        }}
      />
    ),
    sentiment: (
      <MarketSentimentCard
        panel={panels.sentiment}
        loading={loading && !panels.sentiment}
        refreshing={refreshingPanel === 'sentiment'}
        onRefresh={() => {
          void refreshPanel('sentiment', marketApi.getSentiment);
        }}
      />
    ),
    rates: (
      <MarketOverviewCard
        title={t('marketOverviewPage.cards.rates.title')}
        eyebrow={t('marketOverviewPage.cards.rates.eyebrow')}
        description={t('marketOverviewPage.cards.rates.description')}
        sourceLabel={t('marketOverviewPage.cards.rates.source')}
        panel={panels.rates}
        loading={loading && !panels.rates}
        refreshing={refreshingPanel === 'rates'}
        variant="denseQuote"
        onRefresh={() => {
          void refreshPanel('rates', marketApi.getRates);
        }}
      />
    ),
    fxCommodities: (
      <MarketOverviewCard
        title={t('marketOverviewPage.cards.fxCommodities.title')}
        eyebrow={t('marketOverviewPage.cards.fxCommodities.eyebrow')}
        description={t('marketOverviewPage.cards.fxCommodities.description')}
        sourceLabel={t('marketOverviewPage.cards.fxCommodities.source')}
        panel={panels.fxCommodities}
        loading={loading && !panels.fxCommodities}
        refreshing={refreshingPanel === 'fxCommodities'}
        variant="denseQuote"
        onRefresh={() => {
          void refreshPanel('fxCommodities', marketApi.getFxCommodities);
        }}
      />
    ),
    cryptoSnapshot: cryptoSnapshotCard,
    cnSnapshot: (
      <MarketOverviewCard
        title={t('marketOverviewPage.cards.cnIndices.title')}
        eyebrow={t('marketOverviewPage.cards.cnIndices.eyebrow')}
        description={t('marketOverviewPage.cards.cnIndices.description')}
        sourceLabel={t('marketOverviewPage.cards.cnIndices.source')}
        panel={panels.cnIndices}
        loading={loading && !panels.cnIndices}
        refreshing={refreshingPanel === 'cnIndices'}
        variant="denseQuote"
        onRefresh={() => {
          void refreshPanel('cnIndices', marketApi.getCnIndices);
        }}
      />
    ),
    usRates: (
      <ContextMetricModuleCard
        moduleId="usRates"
        title="US Rates"
        eyebrow="RATES / USD"
        description="US10Y / US2Y / US30Y / DXY"
        panel={buildMetricPanel(panels, 'UsRatesModule', ['US10Y', 'US2Y', 'US30Y', 'DXY'])}
        sourceLabel={t('marketOverviewPage.cards.rates.source')}
        refreshing={refreshingPanel === 'rates' || refreshingPanel === 'fxCommodities'}
        onRefresh={() => {
          void refreshPanel('rates', marketApi.getRates);
        }}
      />
    ),
    usSentiment: (
      <MarketSentimentCard
        panel={panels.sentiment}
        loading={loading && !panels.sentiment}
        refreshing={refreshingPanel === 'sentiment'}
        onRefresh={() => {
          void refreshPanel('sentiment', marketApi.getSentiment);
        }}
      />
    ),
    usBreadth: (
      <ContextMetricModuleCard
        moduleId="usBreadth"
        title="美股宽度"
        eyebrow="宽度代理"
        description="行业 ETF 代理 / RSP vs SPY / IWM vs SPY"
        panel={buildFilteredPanel(
          panels.usBreadth,
          'UsBreadthProxyModule',
          ['SECTORS_UP', 'SECTORS_DOWN', 'STRONGEST_SECTOR', 'WEAKEST_SECTOR', 'RSP_SPY', 'IWM_SPY', 'QQQ_SPY', 'SECTOR_PROXY_UNAVAILABLE'],
        )}
        sourceLabel="行业 ETF 代理"
        refreshing={refreshingPanel === 'usBreadth'}
        onRefresh={() => {
          void refreshPanel('usBreadth', marketApi.getUsBreadth);
        }}
      />
    ),
    usSectorRotation: (
      <ContextMetricModuleCard
        moduleId="usSectorRotation"
        title="行业健康度"
        eyebrow="行业 ETF"
        description="美股行业 ETF 强弱代理"
        panel={buildFilteredPanel(
          panels.usBreadth,
          'UsSectorHealthModule',
          ['STRONGEST_SECTOR', 'WEAKEST_SECTOR', 'XLK', 'XLF', 'XLY', 'XLE', 'XLV', 'XLI', 'XLP', 'XLU', 'SECTOR_PROXY_UNAVAILABLE'],
        )}
        sourceLabel="Yahoo Finance"
        refreshing={refreshingPanel === 'usBreadth'}
        onRefresh={() => {
          void refreshPanel('usBreadth', marketApi.getUsBreadth);
        }}
      />
    ),
    macroContext: (
      <ContextMetricModuleCard
        moduleId="macroContext"
        title="宏观压力"
        eyebrow="辅助上下文"
        description="DXY / US10Y / VIX / BTC"
        panel={buildMetricPanel(panels, 'UsMacroContextModule', ['DXY', 'US10Y', 'VIX', 'BTC'])}
        sourceLabel="宏观上下文"
      />
    ),
    cnBreadth: (
      <MarketOverviewCard
        title={t('marketOverviewPage.cards.cnBreadth.title')}
        eyebrow={t('marketOverviewPage.cards.cnBreadth.eyebrow')}
        description={t('marketOverviewPage.cards.cnBreadth.description')}
        sourceLabel={t('marketOverviewPage.cards.cnBreadth.source')}
        panel={panels.cnBreadth}
        loading={loading && !panels.cnBreadth}
        refreshing={refreshingPanel === 'cnBreadth'}
        onRefresh={() => {
          void refreshPanel('cnBreadth', marketApi.getCnBreadth);
        }}
      />
    ),
    cnFlows: (
      <MarketOverviewCard
        title={t('marketOverviewPage.cards.cnFlows.title')}
        eyebrow={t('marketOverviewPage.cards.cnFlows.eyebrow')}
        description={t('marketOverviewPage.cards.cnFlows.description')}
        sourceLabel={t('marketOverviewPage.cards.cnFlows.source')}
        panel={panels.cnFlows}
        loading={loading && !panels.cnFlows}
        refreshing={refreshingPanel === 'cnFlows'}
        onRefresh={() => {
          void refreshPanel('cnFlows', marketApi.getCnFlows);
        }}
      />
    ),
    sectorRotation: (
      <MarketOverviewCard
        title={t('marketOverviewPage.cards.sectorRotation.title')}
        eyebrow={t('marketOverviewPage.cards.sectorRotation.eyebrow')}
        description={t('marketOverviewPage.cards.sectorRotation.description')}
        sourceLabel={t('marketOverviewPage.cards.sectorRotation.source')}
        panel={panels.sectorRotation ? { ...panels.sectorRotation, items: panels.sectorRotation.items.slice(0, 5) } : undefined}
        loading={loading && !panels.sectorRotation}
        refreshing={refreshingPanel === 'sectorRotation'}
        onRefresh={() => {
          void refreshPanel('sectorRotation', marketApi.getSectorRotation);
        }}
      />
    ),
    shortSentiment: (
      <CnShortSentimentCard
        data={panels.cnShortSentiment}
        loading={loading && panels.cnShortSentiment === FALLBACK_CN_SHORT_SENTIMENT}
        refreshing={refreshingPanel === 'cnShortSentiment'}
        onRefresh={() => {
          void refreshPanel('cnShortSentiment', marketApi.getCnShortSentiment);
        }}
      />
    ),
    fxCnhContext: (
      <ContextMetricModuleCard
        moduleId="fxCnhContext"
        title="CNH / 外部压力"
        eyebrow="FX / RATES"
        description="USDCNH / DXY / US10Y"
        panel={buildMetricPanel(panels, 'CnhContextModule', ['USDCNH', 'DXY', 'US10Y'])}
        sourceLabel={t('marketOverviewPage.cards.fxCommodities.source')}
      />
    ),
    macroRates: (
      <ContextMetricModuleCard
        moduleId="macroRates"
        title="利率核心"
        eyebrow="全球宏观"
        description="US10Y / US2Y / US30Y"
        panel={buildMetricPanel(panels, 'MacroRatesModule', ['US10Y', 'US2Y', 'US30Y'])}
        sourceLabel={t('marketOverviewPage.cards.rates.source')}
        refreshing={refreshingPanel === 'rates'}
        onRefresh={() => {
          void refreshPanel('rates', marketApi.getRates);
        }}
      />
    ),
    macroFxCommodities: (
      <ContextMetricModuleCard
        moduleId="macroFxCommodities"
        title="外汇 / 商品"
        eyebrow="美元 / 实物资产"
        description="DXY / USDJPY / USDCNH / GOLD / WTI"
        panel={buildMetricPanel(panels, 'MacroFxCommoditiesModule', ['DXY', 'USDJPY', 'USDCNH', 'GOLD', 'WTI'])}
        sourceLabel={t('marketOverviewPage.cards.fxCommodities.source')}
        refreshing={refreshingPanel === 'fxCommodities'}
        onRefresh={() => {
          void refreshPanel('fxCommodities', marketApi.getFxCommodities);
        }}
      />
    ),
    globalRisk: (
      <ContextMetricModuleCard
        moduleId="globalRisk"
        title="全球风险"
        eyebrow="风险资产"
        description="VIX / BTC / SPX"
        panel={buildMetricPanel(panels, 'GlobalRiskModule', ['VIX', 'BTC', 'SPX'])}
        sourceLabel="风险上下文"
      />
    ),
    cryptoMomentum: (
      <ContextMetricModuleCard
        moduleId="cryptoMomentum"
        title="加密动量"
        eyebrow="趋势"
        description="BTC / ETH / SOL / BNB 的 24H 动量"
        panel={buildMetricPanel(panels, 'CryptoMomentumModule', ['BTC', 'ETH', 'SOL', 'BNB'])}
        sourceLabel={t('marketOverviewPage.cards.crypto.source')}
        refreshing={refreshingPanel === 'crypto'}
        onRefresh={() => {
          void refreshPanel('crypto', marketApi.getCrypto);
        }}
      />
    ),
    cryptoLiquidity: (
      <ContextMetricModuleCard
        moduleId="cryptoLiquidity"
        title="加密流动性"
        eyebrow="资金费率 / 流动性"
        description="资金费率；稳定币与占比在可靠数据源接入前保持不可用"
        panel={buildCryptoLiquidityPanel(panels.crypto)}
        sourceLabel="Binance Futures / 未接入上下文"
        refreshing={refreshingPanel === 'crypto'}
        onRefresh={() => {
          void refreshPanel('crypto', marketApi.getCrypto);
        }}
      />
    ),
    cryptoRiskContext: (
      <ContextMetricModuleCard
        moduleId="cryptoRiskContext"
        title="加密风险上下文"
        eyebrow="宏观压力"
        description="DXY / US10Y / VIX 作为辅助风险压力"
        panel={buildMetricPanel(panels, 'CryptoRiskContextModule', ['DXY', 'US10Y', 'VIX'])}
        sourceLabel="宏观压力"
      />
    ),
    cryptoSentiment: (
      <MarketSentimentCard
        panel={panels.sentiment}
        loading={loading && !panels.sentiment}
        refreshing={refreshingPanel === 'sentiment'}
        onRefresh={() => {
          void refreshPanel('sentiment', marketApi.getSentiment);
        }}
      />
    ),
  };

  const activeTabConfig = MARKET_OVERVIEW_TAB_CONFIG[activeCategory];
  const heroAnchors = useMemo(() => buildHeroAnchors(panels, activeTabConfig.pulse), [activeTabConfig.pulse, panels]);
  const dataQuality = useMemo(() => summarizeDataQuality(panels), [panels]);
  const refreshErrorCount = Object.keys(refreshErrors).length;
  const coverageSummary = useMemo(() => summarizeCardCoverage(panels, CATEGORY_CARDS[activeCategory]), [activeCategory, panels]);
  const activeCategoryLabel = categoryTabs.find((tab) => tab.key === activeCategory)?.label || '';
  const exportSummaryText = useMemo(() => buildMarketOverviewSummaryText({
    activeCategoryLabel,
    coverageSummary,
    dataQuality,
    heroAnchors,
    language,
    temperature: panels.temperature,
    briefing: panels.briefing,
  }), [activeCategoryLabel, coverageSummary, dataQuality, heroAnchors, language, panels.briefing, panels.temperature]);
  const activeRows = CATEGORY_LAYOUT[activeCategory];

  const hasRenderableModule = (moduleId: MarketOverviewModuleId): boolean => {
    if (loading) {
      return true;
    }
    if (moduleId === 'shortSentiment') {
      return Boolean(panels.cnShortSentiment.summary || panels.cnShortSentiment.warning);
    }
    if (moduleId === 'cryptoLiquidity') {
      return true;
    }
    const cards = MODULE_COVERAGE_CARDS[moduleId];
    if (cards.length === 0) {
      return true;
    }
    const panel = cards.map((cardKey) => panels[cardKey] as MarketOverviewPanel | undefined)
      .find((candidate) => candidate?.errorMessage || (candidate?.items?.length || 0) > 0);
    return Boolean(panel?.errorMessage || (panel?.items?.length || 0) > 0);
  };

  const moduleCardTestId: Partial<Record<MarketOverviewModuleId, string>> = {
    globalIndices: 'indices',
    usIndices: 'indices',
    cnHkIndices: 'cnIndices',
    cryptoSnapshot: 'crypto',
    cnSnapshot: 'cnIndices',
    shortSentiment: 'cnShortSentiment',
    macroRates: 'rates',
    macroFxCommodities: 'fxCommodities',
    usSentiment: 'sentiment',
    cryptoSentiment: 'sentiment',
  };

  const renderModule = (moduleId: MarketOverviewModuleId, rank: number, rail: WorkbenchRail = 'hero') => {
    const layoutMeta = MODULE_LAYOUT_META[moduleId];
    const cardTestId = moduleCardTestId[moduleId] || moduleId;
    return (
    <div
      key={moduleId}
      data-testid={`market-overview-card-${cardTestId}`}
      data-market-overview-module={moduleId}
      data-market-card-rank={rank}
      data-market-card-row={rail}
      data-market-card-size={layoutMeta.size}
      data-market-card-density={DENSE_QUOTE_MODULES.has(moduleId) ? 'dense-quote' : 'standard'}
      className="h-full min-w-0 w-full overflow-hidden"
    >
      {moduleNodes[moduleId]}
    </div>
    );
  };

  const renderPlannedRow = (row: MarketOverviewLayoutRow, rowIndex: number) => {
    const modules = row.modules.filter(hasRenderableModule);
    if (modules.length === 0) {
      return null;
    }
    const plannedRow = modules.length === 1 && row.allowSingleFullWidth
      ? { ...row, columns: 1 as const }
      : { ...row, columns: Math.min(row.columns, modules.length) as MarketOverviewRowColumns };
    const children = modules.map((moduleId, moduleIndex) => renderModule(moduleId, rowIndex * 10 + moduleIndex, row.tier));

    if (plannedRow.columns === 1) {
      return <MarketOverviewFullWidthRow key={row.id} row={plannedRow}>{children}</MarketOverviewFullWidthRow>;
    }
    if (plannedRow.columns === 3) {
      return <MarketOverviewThreeColumnRow key={row.id} row={plannedRow}>{children}</MarketOverviewThreeColumnRow>;
    }
    return <MarketOverviewTwoColumnRow key={row.id} row={plannedRow}>{children}</MarketOverviewTwoColumnRow>;
  };

  const handleExportSummary = useCallback(async () => {
    await navigator.clipboard.writeText(exportSummaryText);
    setExportSummaryFeedback(language === 'en' ? 'Summary copied' : '已复制摘要');
  }, [exportSummaryText, language]);

  const renderDeterministicGrid = () => (
    <main data-testid="market-overview-main-grid" data-workbench-split="9:3" className="grid grid-cols-1 items-start gap-4 xl:grid-cols-12">
      <section
        data-testid="market-overview-primary-rail"
        data-mobile-order="main"
        className="flex min-w-0 flex-col gap-4 xl:col-span-9"
      >
        <MarketOverviewMainStack>
          <section data-testid="market-overview-hero-lane" data-card-tier="hero" className="min-w-0">
            {activeRows.filter((row) => row.tier === 'hero').map(renderPlannedRow)}
          </section>
          <section data-testid="market-overview-secondary-grid" data-card-tier="secondary" className="flex min-w-0 flex-col gap-4">
            {activeRows.filter((row) => row.tier === 'secondary').map(renderPlannedRow)}
          </section>
        </MarketOverviewMainStack>
      </section>
      <aside data-testid="market-overview-side-rail" data-mobile-order="rail" className="flex min-w-0 flex-col gap-3 xl:col-span-3">
        <div data-testid="market-overview-rail" className="flex min-w-0 flex-col gap-3">
          {activeTabConfig.rail.includes('coverage') ? <CategoryCoverageSummary label={activeCategoryLabel} summary={coverageSummary} /> : null}
          {activeTabConfig.rail.includes('quality') ? <DataQualityCompactRailCard summary={dataQuality} /> : null}
          {activeTabConfig.rail.includes('signalWatch') ? <SignalWatchRailCard panels={panels} activeCategory={activeCategory} /> : null}
          {activeTabConfig.rail.includes('actionHint') ? <ActionHintRailCard temperature={panels.temperature} /> : null}
        </div>
      </aside>
      {activeRows.some((row) => row.tier === 'deep') || activeCategory === 'all' ? (
        <section
          data-testid="market-overview-deep-panels"
          data-panel-grouping="deterministic-rows"
          data-mobile-order="deep"
          data-card-tier="deep"
          className="flex min-w-0 flex-col gap-4 xl:col-span-9"
        >
          {activeRows.filter((row) => row.tier === 'deep').map(renderPlannedRow)}
          {activeCategory === 'all' ? <ExecutiveSecondaryGroups panels={panels} /> : null}
        </section>
      ) : null}
    </main>
  );

  return (
    <div
      data-testid="market-overview-shell"
      data-bento-surface="true"
      className="bento-surface-root flex min-h-0 w-full min-w-0 flex-1 flex-col gap-6 bg-[#030303] text-white"
    >
      <div data-testid="market-overview-workbench" className="flex min-h-0 w-full min-w-0 flex-1 flex-col gap-6">
        <section data-testid="market-overview-pulse-header" className="flex w-full min-w-0 flex-col gap-4">
          <div data-testid="market-overview-top-stack" className="flex w-full min-w-0 flex-col gap-4">
          <MarketDecisionStrip activeCategory={activeCategory} panels={panels} dataQuality={dataQuality} />
          <section data-testid="market-overview-summary-band" data-mobile-order="summary" data-market-research-flow="trust" className="min-w-0">
            <MarketOverviewStatusStrip
              temperature={<MarketTemperatureCompactSummary data={panels.temperature} />}
              dataQuality={<DataQualityCompactSummary summary={dataQuality} />}
              briefing={<MarketBriefingCompactSummary data={panels.briefing} />}
            />
          </section>
          <div data-market-research-flow="controls">
            <div
              data-testid="market-overview-category-tabs"
              data-selector-position="static-safe"
              data-mobile-order="controls"
              className="flex w-full min-w-0 flex-col gap-2 rounded-xl border border-white/8 bg-white/[0.02] p-2 backdrop-blur-md md:flex-row md:items-center md:justify-between"
            >
              <div className="flex min-w-0 items-center gap-2">
                <span className="shrink-0 rounded-md border border-white/[0.06] bg-white/[0.025] px-2 py-1 text-[10px] font-semibold text-white/42">
                  筛选
                </span>
                <div className="ui-scroll-x-quiet min-w-0">
                  <div className="flex w-max gap-2">
                    {categoryTabs.map((tab) => (
                      <button
                        key={tab.key}
                        type="button"
                        aria-pressed={activeCategory === tab.key}
                        className={`ui-truncate shrink-0 whitespace-nowrap rounded-md px-3 py-2 text-xs font-semibold transition ${
                          activeCategory === tab.key
                            ? 'bg-white/10 text-white shadow-sm'
                            : 'bg-transparent text-white/45 hover:text-white/75'
                        }`}
                        onClick={() => setActiveCategory(tab.key)}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              <button
                type="button"
                data-testid="market-overview-export-summary"
                className="w-fit rounded-md border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-xs font-semibold text-white/62 transition hover:bg-white/[0.06] hover:text-white"
                onClick={() => {
                  void handleExportSummary();
                }}
              >
                {exportSummaryFeedback || (language === 'en' ? 'Export' : '复制摘要')}
              </button>
            </div>
          </div>
          <MarketOverviewCacheStatus
            hasLocalSnapshot={hasLocalSnapshot}
            localSnapshotSavedAt={localSnapshotSavedAt}
            loading={loading}
            refreshingPanel={refreshingPanel}
            refreshErrorCount={refreshErrorCount}
            dataQuality={dataQuality}
          />
          <div data-market-research-flow="pulse">
            <CrossAssetHeroRibbon anchors={heroAnchors} />
          </div>
          </div>
        </section>
        {renderDeterministicGrid()}
      </div>
    </div>
  );
};

export default MarketOverviewPage;
