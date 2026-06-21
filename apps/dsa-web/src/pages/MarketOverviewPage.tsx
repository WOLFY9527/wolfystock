import { useCallback, useEffect, useRef, useState } from 'react';
import type { MarketDataMeta, MarketOverviewPanel } from '../api/marketOverview';
import { marketOverviewApi } from '../api/marketOverview';
import type {
  CnShortSentimentResponse,
  MarketBriefingResponse,
  MarketFuturesResponse,
  MarketTemperatureResponse,
  OfficialRiskSourceReadiness,
} from '../api/market';
import {
  buildOfficialRiskSourceReadinessView,
  marketApi,
  normalizeCnShortSentimentConsumerCopy,
  normalizeMarketBriefingConsumerCopy,
  normalizeMarketFuturesConsumerCopy,
  normalizeMarketOverviewPanelConsumerCopy,
  normalizeMarketTemperatureResponse,
} from '../api/market';
import {
  MarketOverviewWorkbench,
  type CryptoRealtimeStatus,
  type PanelKey,
  type PanelState,
} from '../components/market-overview/MarketOverviewWorkbench';
import { ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
import { TerminalChip, TerminalPageHeading } from '../components/terminal/TerminalPrimitives';
import { useI18n } from '../contexts/UiLanguageContext';
import { useProductSurface } from '../hooks/useProductSurface';

type LocalSnapshotEnvelope = {
  schemaVersion: 1;
  savedAt: string;
  payload: Partial<PanelState>;
};

const MARKET_OVERVIEW_LKG_STORAGE_KEY = 'wolfystock.marketOverview.lastKnownGood.v1';
const FAST_POLL_INTERVAL_MS = 45_000;
const MEDIUM_POLL_INTERVAL_MS = 120_000;
const SLOW_POLL_INTERVAL_MS = 300_000;
const PANEL_REQUEST_TIMEOUT_MS = 3_000;
const FIRST_STAGE_PANEL_DELAY_MS = 250;
const SECOND_STAGE_PANEL_DELAY_MS = 650;
const AUTO_REVALIDATE_INITIAL_DELAY_MS = 1_500;
const AUTO_REVALIDATE_RETRY_DELAY_MS = 2_500;
const AUTO_REVALIDATE_MAX_ATTEMPTS = 3;

type PanelRequest = readonly [PanelKey, () => Promise<PanelState[PanelKey]>];
type RefreshPanelRequestMode = 'background-refresh' | 'manual-refresh';
type StagedPanelRequestGroup = {
  delayMs: number;
  requests: PanelRequest[];
};
type PollingPanelRequestGroup = {
  intervalMs: number;
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

const MARKET_OVERVIEW_POLLING_GROUPS: PollingPanelRequestGroup[] = [
  {
    intervalMs: FAST_POLL_INTERVAL_MS,
    requests: [
      ['indices', marketOverviewApi.getIndices],
      ['volatility', marketOverviewApi.getVolatility],
      ['crypto', marketApi.getCrypto],
    ],
  },
  {
    intervalMs: MEDIUM_POLL_INTERVAL_MS,
    requests: [
      ['futures', marketApi.getFutures],
      ['cnIndices', marketApi.getCnIndices],
      ['cnBreadth', marketApi.getCnBreadth],
      ['usBreadth', marketApi.getUsBreadth],
      ['fxCommodities', marketApi.getFxCommodities],
      ['temperature', marketApi.getTemperature],
      ['briefing', marketApi.getMarketBriefing],
    ],
  },
  {
    intervalMs: SLOW_POLL_INTERVAL_MS,
    requests: [
      ['fundsFlow', marketOverviewApi.getFundsFlow],
      ['macro', marketOverviewApi.getMacro],
      ['cnFlows', marketApi.getCnFlows],
      ['sectorRotation', marketApi.getSectorRotation],
      ['rates', marketApi.getRates],
      ['sentiment', marketApi.getSentiment],
      ['cnShortSentiment', marketApi.getCnShortSentiment],
    ],
  },
];

const AUTO_REVALIDATE_PANEL_KEYS: PanelKey[] = [
  'indices',
  'volatility',
  'crypto',
  'sentiment',
  'fundsFlow',
  'macro',
  'cnIndices',
  'cnBreadth',
  'cnFlows',
  'sectorRotation',
  'usBreadth',
  'rates',
  'fxCommodities',
  'temperature',
  'briefing',
  'futures',
  'cnShortSentiment',
];

const FALLBACK_TEMPERATURE: MarketTemperatureResponse = {
  source: 'fallback',
  sourceLabel: '最近可用数据',
  updatedAt: new Date(0).toISOString(),
  freshness: 'fallback',
  isFallback: true,
  warning: '数据待补',
  confidence: 0,
  reliableInputCount: 0,
  fallbackInputCount: 0,
  excludedInputCount: 0,
  isReliable: false,
  scores: {
    overall: { value: 50, label: '数据不足', trend: 'stable', description: '数据待补' },
    usRiskAppetite: { value: 50, label: '数据不足', trend: 'stable', description: '数据待补' },
    cnMoneyEffect: { value: 50, label: '数据不足', trend: 'stable', description: '数据待补' },
    macroPressure: { value: 50, label: '数据不足', trend: 'stable', description: '数据待补' },
    liquidity: { value: 50, label: '数据不足', trend: 'stable', description: '数据待补' },
  },
};

const FALLBACK_BRIEFING: MarketBriefingResponse = {
  source: 'fallback',
  sourceLabel: '最近可用数据',
  updatedAt: new Date(0).toISOString(),
  freshness: 'fallback',
  isFallback: true,
  warning: '数据待补',
  confidence: 0,
  reliableInputCount: 0,
  fallbackInputCount: 0,
  excludedInputCount: 0,
  isReliable: false,
  items: [
    { title: '数据待补', message: '数据待补', severity: 'warning', category: 'risk', confidence: 0 },
    { title: '评分已暂停', message: '评分已暂停', severity: 'neutral', category: 'risk', confidence: 0 },
    { title: '等待数据恢复', message: '等待数据恢复', severity: 'neutral', category: 'risk', confidence: 0 },
  ],
};

const FALLBACK_FUTURES: MarketFuturesResponse = {
  source: 'fallback',
  sourceLabel: '最近可用数据',
  updatedAt: new Date(0).toISOString(),
  freshness: 'fallback',
  isFallback: true,
  warning: '最近可用数据',
  items: [
    { name: '纳指期货', symbol: 'NQ', value: 18420.5, change: 65.2, changePercent: 0.35, market: 'US', session: 'premarket', sparkline: [18320, 18380, 18420.5], source: 'fallback', sourceLabel: '最近可用数据', freshness: 'fallback', isFallback: true, warning: '最近可用数据' },
    { name: '标普500期货', symbol: 'ES', value: 5238.25, change: 14.5, changePercent: 0.28, market: 'US', session: 'premarket', sparkline: [5208, 5218, 5238.25], source: 'fallback', sourceLabel: '最近可用数据', freshness: 'fallback', isFallback: true, warning: '最近可用数据' },
    { name: '道指期货', symbol: 'YM', value: 38980, change: 72, changePercent: 0.19, market: 'US', session: 'premarket', sparkline: [38820, 38930, 38980], source: 'fallback', sourceLabel: '最近可用数据', freshness: 'fallback', isFallback: true, warning: '最近可用数据' },
    { name: '罗素2000期货', symbol: 'RTY', value: 2094.6, change: -3.8, changePercent: -0.18, market: 'US', session: 'premarket', sparkline: [2108, 2098, 2094.6], source: 'fallback', sourceLabel: '最近可用数据', freshness: 'fallback', isFallback: true, warning: '最近可用数据' },
    { name: '富时A50期货', symbol: 'CN00Y', value: 12580, change: 38, changePercent: 0.3, market: 'CN', session: 'day', sparkline: [12420, 12542, 12580], source: 'fallback', sourceLabel: '最近可用数据', freshness: 'fallback', isFallback: true, warning: '最近可用数据' },
    { name: '恒指期货', symbol: 'HSI_F', value: 17712, change: 128, changePercent: 0.73, market: 'HK', session: 'day', sparkline: [17490, 17640, 17712], source: 'fallback', sourceLabel: '最近可用数据', freshness: 'fallback', isFallback: true, warning: '最近可用数据' },
  ],
};

const FALLBACK_CRYPTO_PANEL: MarketOverviewPanel = {
  panelName: 'CryptoCard',
  lastRefreshAt: new Date(0).toISOString(),
  status: 'failure',
  source: 'fallback',
  sourceLabel: '最近可用数据',
  updatedAt: new Date(0).toISOString(),
  asOf: new Date(0).toISOString(),
  freshness: 'fallback',
  isFallback: true,
  isRefreshing: true,
  warning: '正在刷新，稍后自动更新',
  items: [
    { symbol: 'BTC', label: 'Bitcoin', value: 75800, unit: 'USD', changePct: -0.2, riskDirection: 'increasing', trend: [75220, 75640, 76110, 75800], source: 'fallback', sourceLabel: '最近可用数据', freshness: 'fallback', isFallback: true, warning: '正在刷新，稍后自动更新' },
    { symbol: 'ETH', label: 'Ethereum', value: 3120, unit: 'USD', changePct: -0.4, riskDirection: 'increasing', trend: [3090, 3148, 3162, 3120], source: 'fallback', sourceLabel: '最近可用数据', freshness: 'fallback', isFallback: true, warning: '正在刷新，稍后自动更新' },
    { symbol: 'BNB', label: 'BNB', value: 590, unit: 'USD', changePct: 0.3, riskDirection: 'decreasing', trend: [584, 588, 586, 590], source: 'fallback', sourceLabel: '最近可用数据', freshness: 'fallback', isFallback: true, warning: '正在刷新，稍后自动更新' },
  ],
};

const FALLBACK_CN_SHORT_SENTIMENT: CnShortSentimentResponse = {
  source: 'fallback',
  sourceLabel: '最近可用数据',
  updatedAt: new Date(0).toISOString(),
  freshness: 'fallback',
  isFallback: true,
  warning: '最近可用数据',
  sentimentScore: 50,
  summary: '数据待补',
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
  (Object.keys(panels) as PanelKey[]).forEach((panelKey) => {
    const value = panels[panelKey];
    if (value) {
      assignPanelValue(panels, panelKey, value as PanelState[PanelKey]);
    }
  });
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
      nextPanels[panelKey] = normalizeMarketOverviewPanelConsumerCopy(value as MarketOverviewPanel);
      break;
    case 'temperature':
      nextPanels.temperature = normalizeMarketTemperatureResponse(value as MarketTemperatureResponse);
      break;
    case 'briefing':
      nextPanels.briefing = normalizeMarketBriefingConsumerCopy(value as MarketBriefingResponse);
      break;
    case 'futures':
      nextPanels.futures = normalizeMarketFuturesConsumerCopy(value as MarketFuturesResponse);
      break;
    case 'cnShortSentiment':
      nextPanels.cnShortSentiment = normalizeCnShortSentimentConsumerCopy(value as CnShortSentimentResponse);
      break;
  }
}

function describePanelError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error || '');
  const lower = message.toLowerCase();
  if (lower.includes('timeout') || lower.includes('timed out') || message.includes('超时')) {
    return '数据更新超时';
  }
  if (lower.includes('provider_down') || lower.includes('provider_error') || lower.includes('unavailable') || message.includes('不可用')) {
    return '部分数据暂不可用';
  }
  return '数据更新失败';
}

function fallbackPanel(panelName: string, error: unknown): MarketOverviewPanel {
  const updatedAt = new Date().toISOString();
  const warning = describePanelError(error);
  return {
    panelName,
    lastRefreshAt: updatedAt,
    status: 'failure',
    errorMessage: '更新失败：数据更新失败',
    source: 'error',
    sourceLabel: '数据更新中',
    updatedAt,
    asOf: updatedAt,
    freshness: 'error',
    isFallback: true,
    isStale: true,
    warning: `部分数据暂不可用，请稍后自动刷新。${warning}`,
    items: [],
  };
}

function fallbackPanelValue(panelKey: PanelKey, error: unknown): PanelState[PanelKey] {
  switch (panelKey) {
    case 'temperature':
      return {
        ...FALLBACK_TEMPERATURE,
        updatedAt: new Date().toISOString(),
        warning: `部分数据暂不可用，请稍后自动刷新。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'briefing':
      return {
        ...FALLBACK_BRIEFING,
        updatedAt: new Date().toISOString(),
        warning: `部分数据暂不可用，请稍后自动刷新。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'futures':
      return {
        ...FALLBACK_FUTURES,
        updatedAt: new Date().toISOString(),
        isRefreshing: true,
        warning: `部分数据暂不可用，请稍后自动刷新。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'cnShortSentiment':
      return {
        ...FALLBACK_CN_SHORT_SENTIMENT,
        updatedAt: new Date().toISOString(),
        isRefreshing: true,
        warning: `部分数据暂不可用，请稍后自动刷新。${describePanelError(error)}`,
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

type AutoRevalidateMeta = Partial<MarketDataMeta> & {
  source?: string;
  sourceType?: string | null;
};

function shouldAutoRevalidatePanelValue(value: PanelState[PanelKey] | undefined): boolean {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const meta = value as AutoRevalidateMeta;
  const providerStatus = meta.providerHealth?.status;
  if (meta.isRefreshing || meta.providerHealth?.isRefreshing) {
    return true;
  }
  if (providerStatus === 'refreshing' || providerStatus === 'partial' || providerStatus === 'fallback') {
    return true;
  }
  if (meta.freshness === 'fallback' || meta.freshness === 'stale') {
    return true;
  }
  return false;
}

function getPanelLoader(panelKey: PanelKey): (() => Promise<PanelState[PanelKey]>) | null {
  switch (panelKey) {
    case 'indices':
      return marketOverviewApi.getIndices;
    case 'volatility':
      return marketOverviewApi.getVolatility;
    case 'crypto':
      return marketApi.getCrypto;
    case 'sentiment':
      return marketApi.getSentiment;
    case 'fundsFlow':
      return marketOverviewApi.getFundsFlow;
    case 'macro':
      return marketOverviewApi.getMacro;
    case 'cnIndices':
      return marketApi.getCnIndices;
    case 'cnBreadth':
      return marketApi.getCnBreadth;
    case 'cnFlows':
      return marketApi.getCnFlows;
    case 'sectorRotation':
      return marketApi.getSectorRotation;
    case 'usBreadth':
      return marketApi.getUsBreadth;
    case 'rates':
      return marketApi.getRates;
    case 'fxCommodities':
      return marketApi.getFxCommodities;
    case 'temperature':
      return marketApi.getTemperature;
    case 'briefing':
      return marketApi.getMarketBriefing;
    case 'futures':
      return marketApi.getFutures;
    case 'cnShortSentiment':
      return marketApi.getCnShortSentiment;
    default:
      return null;
  }
}

const routeEntryPanelRequestCache = new Map<string, Promise<PanelState[PanelKey]>>();
const inFlightRefreshPanelRequestCache = new Map<string, Promise<PanelState[PanelKey]>>();

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

function loadPanelWithRefreshDedupe(
  panelKey: PanelKey,
  mode: RefreshPanelRequestMode,
  loadPanel: () => Promise<PanelState[PanelKey]>,
): Promise<PanelState[PanelKey]> {
  const cacheKey = `${mode}:${String(panelKey)}`;
  const cached = inFlightRefreshPanelRequestCache.get(cacheKey);
  if (cached) {
    return cached;
  }
  const promise = loadPanel().finally(() => {
    if (inFlightRefreshPanelRequestCache.get(cacheKey) === promise) {
      inFlightRefreshPanelRequestCache.delete(cacheKey);
    }
  });
  inFlightRefreshPanelRequestCache.set(cacheKey, promise);
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

const OfficialRiskSourceReadinessStrip = ({
  readiness,
}: {
  readiness?: OfficialRiskSourceReadiness | null;
}) => {
  const view = buildOfficialRiskSourceReadinessView(readiness);

  return (
    <section
      data-testid="market-overview-source-readiness"
      className="rounded-lg border border-white/[0.06] bg-white/[0.025] px-3 py-2.5"
    >
      <div className="flex min-w-0 flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-medium text-white/48">官方风险源</p>
          <p className="mt-1 text-sm font-semibold text-white/84">{view.bundleLabel}</p>
        </div>
        <div className="flex min-w-0 flex-wrap gap-1.5 md:justify-end">
          <TerminalChip variant={view.bundleVariant}>{view.bundleLabel}</TerminalChip>
          {view.chips.map((chip) => (
            <TerminalChip key={chip.key} variant={chip.variant}>{chip.label}</TerminalChip>
          ))}
        </div>
      </div>
    </section>
  );
};

const MarketOverviewPage = () => {
  const { language } = useI18n();
  const { isAdminMode, canReadProviders } = useProductSurface();
  const [initialLocalSnapshot] = useState(() => buildInitialPanelsFromLocalSnapshot());
  const [panels, setPanels] = useState<PanelState>(initialLocalSnapshot.panels);
  const [officialRiskSourceReadiness, setOfficialRiskSourceReadiness] = useState<OfficialRiskSourceReadiness | null>(null);
  const [loading, setLoading] = useState(initialLocalSnapshot.source !== 'local');
  const [localSnapshotSavedAt, setLocalSnapshotSavedAt] = useState<string | undefined>(initialLocalSnapshot.savedAt);
  const [refreshErrors, setRefreshErrors] = useState<Record<string, string>>({});
  const [refreshingPanel, setRefreshingPanel] = useState<PanelKey | null>(null);
  const [cryptoRealtimeStatus, setCryptoRealtimeStatus] = useState<CryptoRealtimeStatus>('snapshot');
  const [autoRevalidateTick, setAutoRevalidateTick] = useState(0);
  const autoRevalidateTimersRef = useRef<Partial<Record<PanelKey, number>>>({});
  const autoRevalidateAttemptsRef = useRef<Partial<Record<PanelKey, number>>>({});
  const autoRevalidateInFlightRef = useRef<Partial<Record<PanelKey, true>>>({});
  const latestPanelsRef = useRef(panels);
  const latestRefreshingPanelRef = useRef<PanelKey | null>(null);

  const clearAutoRevalidateTimer = useCallback((panelKey: PanelKey) => {
    const timer = autoRevalidateTimersRef.current[panelKey];
    if (timer != null) {
      window.clearTimeout(timer);
      delete autoRevalidateTimersRef.current[panelKey];
    }
  }, []);

  const resetAutoRevalidatePanel = useCallback((panelKey: PanelKey) => {
    clearAutoRevalidateTimer(panelKey);
    delete autoRevalidateAttemptsRef.current[panelKey];
    delete autoRevalidateInFlightRef.current[panelKey];
  }, [clearAutoRevalidateTimer]);

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
    options?: { silent?: boolean },
  ) => {
    const mode: RefreshPanelRequestMode = options?.silent ? 'background-refresh' : 'manual-refresh';
    if (!options?.silent) {
      setRefreshingPanel(panelKey);
    }
    debugMarketPanel(panelKey, 'loading');
    try {
      const panel = await withPanelTimeout(loadPanelWithRefreshDedupe(panelKey, mode, loadPanel), panelKey);
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
      if (!options?.silent) {
        setRefreshingPanel((currentPanel) => (currentPanel === panelKey ? null : currentPanel));
      }
    }
  }, []);

  const scheduleAutoRevalidate = useCallback((panelKey: PanelKey) => {
    const panelValue = latestPanelsRef.current[panelKey];
    if (!shouldAutoRevalidatePanelValue(panelValue)) {
      resetAutoRevalidatePanel(panelKey);
      return;
    }
    if (latestRefreshingPanelRef.current === panelKey || autoRevalidateInFlightRef.current[panelKey]) {
      return;
    }
    if (autoRevalidateTimersRef.current[panelKey] != null) {
      return;
    }
    const attempts = autoRevalidateAttemptsRef.current[panelKey] ?? 0;
    if (attempts >= AUTO_REVALIDATE_MAX_ATTEMPTS) {
      return;
    }
    const loadPanel = getPanelLoader(panelKey);
    if (!loadPanel) {
      return;
    }
    const delayMs = attempts === 0 ? AUTO_REVALIDATE_INITIAL_DELAY_MS : AUTO_REVALIDATE_RETRY_DELAY_MS;
    autoRevalidateTimersRef.current[panelKey] = window.setTimeout(() => {
      delete autoRevalidateTimersRef.current[panelKey];
      if (latestRefreshingPanelRef.current === panelKey || autoRevalidateInFlightRef.current[panelKey]) {
        return;
      }
      if (!shouldAutoRevalidatePanelValue(latestPanelsRef.current[panelKey])) {
        delete autoRevalidateAttemptsRef.current[panelKey];
        return;
      }
      autoRevalidateAttemptsRef.current[panelKey] = attempts + 1;
      autoRevalidateInFlightRef.current[panelKey] = true;
      void refreshPanel(panelKey, loadPanel, { silent: true }).finally(() => {
        delete autoRevalidateInFlightRef.current[panelKey];
        setAutoRevalidateTick((currentTick) => currentTick + 1);
      });
    }, delayMs);
  }, [refreshPanel, resetAutoRevalidatePanel]);

  const refreshPollingGroup = useCallback((requests: PanelRequest[]) => {
    requests.forEach(([panelKey, loadPanel]) => {
      void refreshPanel(panelKey, loadPanel, { silent: true });
    });
  }, [refreshPanel]);

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
    let cancelled = false;

    async function loadSourceReadiness() {
      try {
        const payload = await marketApi.getDataReadiness();
        if (!cancelled) {
          setOfficialRiskSourceReadiness(payload?.officialRiskSourceReadiness || null);
        }
      } catch {
        if (!cancelled) {
          setOfficialRiskSourceReadiness(null);
        }
      }
    }

    void loadSourceReadiness();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    writeLocalMarketOverviewSnapshot(panels);
    setLocalSnapshotSavedAt(new Date().toISOString());
  }, [panels]);

  useEffect(() => {
    latestPanelsRef.current = panels;
  }, [panels]);

  useEffect(() => {
    latestRefreshingPanelRef.current = refreshingPanel;
  }, [refreshingPanel]);

  useEffect(() => {
    AUTO_REVALIDATE_PANEL_KEYS.forEach(scheduleAutoRevalidate);
  }, [panels, refreshingPanel, autoRevalidateTick, scheduleAutoRevalidate]);

  useEffect(() => () => {
    AUTO_REVALIDATE_PANEL_KEYS.forEach((panelKey) => {
      clearAutoRevalidateTimer(panelKey);
    });
  }, [clearAutoRevalidateTimer]);

  useEffect(() => {
    const timers = MARKET_OVERVIEW_POLLING_GROUPS.map((group) => (
      window.setInterval(() => {
        refreshPollingGroup(group.requests);
      }, group.intervalMs)
    ));
    return () => {
      timers.forEach((timer) => {
        window.clearInterval(timer);
      });
    };
  }, [refreshPollingGroup]);

  useEffect(() => {
    return subscribeToCryptoStream(({ panel, status }) => {
      if (panel) {
        resetAutoRevalidatePanel('crypto');
        setPanels((currentPanels) => ({
          ...currentPanels,
          crypto: normalizeMarketOverviewPanelConsumerCopy(panel),
        }));
      }
      setCryptoRealtimeStatus(status);
    });
  }, [resetAutoRevalidatePanel]);

  const handleWorkbenchRefresh = useCallback((panelKey: PanelKey) => {
    const loadPanel = getPanelLoader(panelKey);
    if (!loadPanel) {
      return;
    }
    resetAutoRevalidatePanel(panelKey);
    void refreshPanel(panelKey, loadPanel);
  }, [refreshPanel, resetAutoRevalidatePanel]);
  return (
    <ConsumerWorkspaceScope className="min-h-0 flex-1">
      <ConsumerWorkspacePageShell
        data-testid="market-overview-shell"
        className="flex min-h-0 flex-1 flex-col gap-4 md:gap-6"
      >
        <OfficialRiskSourceReadinessStrip readiness={officialRiskSourceReadiness} />
        <MarketOverviewWorkbench
          heading={(
            <TerminalPageHeading
              data-testid="market-overview-page-heading"
              title={language === 'en' ? 'Market Overview' : '市场总览'}
            />
          )}
          panels={panels}
          loading={loading}
          localSnapshotSavedAt={localSnapshotSavedAt}
          refreshErrorCount={Object.keys(refreshErrors).length}
          refreshingPanel={refreshingPanel}
          cryptoRealtimeStatus={cryptoRealtimeStatus}
          isCnShortSentimentBootstrapping={loading && panels.cnShortSentiment === FALLBACK_CN_SHORT_SENTIMENT}
          showAdminDiagnostics={isAdminMode && canReadProviders}
          onRefreshPanel={handleWorkbenchRefresh}
        />
      </ConsumerWorkspacePageShell>
    </ConsumerWorkspaceScope>
  );
};

export default MarketOverviewPage;
