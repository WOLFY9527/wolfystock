import { useCallback, useEffect, useRef, useState } from 'react';
import type { MarketDataMeta, MarketOverviewPanel } from '../api/marketOverview';
import { marketOverviewApi } from '../api/marketOverview';
import type {
  ConsumerEvidenceReadinessMatrix,
  CrossAssetDriverReadiness,
  CnShortSentimentResponse,
  ProfessionalDataCapabilityRegistryView,
  ProfessionalDataCapabilityViewItem,
  MarketBriefingResponse,
  MarketFuturesResponse,
  MarketRegimeReadModelResponse,
  MarketTemperatureResponse,
  OfficialRiskSourceReadiness,
} from '../api/market';
import {
  buildCrossAssetDriverReadinessView,
  buildConsumerEvidenceBoundaryView,
  buildOfficialRiskSourceReadinessView,
  buildProfessionalDataCapabilityRegistryView,
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
import { TerminalButton, TerminalChip, TerminalDisclosure, TerminalPageHeading } from '../components/terminal/TerminalPrimitives';
import { useI18n } from '../contexts/UiLanguageContext';
import { useProductSurface } from '../hooks/useProductSurface';
import { buildDataSourcesSetupHref, buildProviderOpsSetupHref } from '../utils/productSetupSurface';

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
const MARKET_OVERVIEW_SETUP_ACTION_CLASS = 'inline-flex min-h-8 items-center rounded-md border border-white/[0.08] bg-white/[0.035] px-2.5 py-1 text-[11px] font-semibold text-white/72 transition-colors hover:border-cyan-200/25 hover:bg-white/[0.06] hover:text-white';

type PanelRequest = readonly [PanelKey, () => Promise<PanelState[PanelKey]>];
type RefreshPanelRequestMode = 'route-entry' | 'background-refresh' | 'manual-refresh';
type MarketOverviewReadinessSnapshot = {
  officialRiskSourceReadiness: OfficialRiskSourceReadiness | null;
  consumerEvidenceReadinessMatrix: ConsumerEvidenceReadinessMatrix | null;
  crossAssetDriverReadiness: CrossAssetDriverReadiness | null;
};
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

const createUnavailableTemperature = (warning = '市场温度数据待补'): MarketTemperatureResponse => ({
  source: 'unavailable',
  sourceLabel: '待补数据',
  updatedAt: new Date(0).toISOString(),
  freshness: 'unavailable',
  isFallback: false,
  warning,
  confidence: 0,
  reliableInputCount: 0,
  fallbackInputCount: 0,
  excludedInputCount: 0,
  isReliable: false,
  temperatureAvailable: false,
  conclusionAllowed: false,
  disabledReason: 'missing_required_evidence',
  unavailableReason: 'market_overview_inputs_unavailable',
  scores: {
    overall: { value: 50, label: '数据不足', trend: 'stable', description: '数据待补' },
    usRiskAppetite: { value: 50, label: '数据不足', trend: 'stable', description: '数据待补' },
    cnMoneyEffect: { value: 50, label: '数据不足', trend: 'stable', description: '数据待补' },
    macroPressure: { value: 50, label: '数据不足', trend: 'stable', description: '数据待补' },
    liquidity: { value: 50, label: '数据不足', trend: 'stable', description: '数据待补' },
  },
});

const createUnavailableBriefing = (warning = '市场简报数据待补'): MarketBriefingResponse => ({
  source: 'unavailable',
  sourceLabel: '待补数据',
  updatedAt: new Date(0).toISOString(),
  freshness: 'unavailable',
  isFallback: false,
  warning,
  confidence: 0,
  reliableInputCount: 0,
  fallbackInputCount: 0,
  excludedInputCount: 0,
  isReliable: false,
  items: [],
});

const createUnavailableFutures = (warning = '期货数据待补'): MarketFuturesResponse => ({
  source: 'unavailable',
  sourceLabel: '待补数据',
  updatedAt: new Date(0).toISOString(),
  freshness: 'unavailable',
  isFallback: false,
  warning,
  items: [],
});

const createUnavailableCnShortSentiment = (warning = '短线情绪数据待补'): CnShortSentimentResponse => ({
  source: 'unavailable',
  sourceLabel: '待补数据',
  updatedAt: new Date(0).toISOString(),
  freshness: 'unavailable',
  isFallback: false,
  warning,
  sentimentScore: 0,
  summary: '数据待补',
  metrics: {
    limitUpCount: 0,
    limitDownCount: 0,
    failedLimitUpRate: 0,
    maxConsecutiveLimitUps: 0,
    yesterdayLimitUpPerformance: 0,
    firstBoardCount: 0,
    secondBoardCount: 0,
    highBoardCount: 0,
    twentyCmLimitUpCount: 0,
    stRiskLevel: 'unknown',
  },
});

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
    isUnavailable?: boolean;
    items?: unknown[];
    scores?: unknown;
    metrics?: unknown;
    summary?: unknown;
  };
  if (
    (payload.source === 'error' || payload.freshness === 'error' || payload.source === 'unavailable' || payload.freshness === 'unavailable' || payload.isUnavailable)
    && !payload.items?.length
  ) {
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
        temperature: normalizeMarketTemperatureResponse(createUnavailableTemperature()),
        briefing: createUnavailableBriefing(),
        futures: createUnavailableFutures(),
        cnShortSentiment: createUnavailableCnShortSentiment(),
      },
    };
  }
  const panels = {
    temperature: createUnavailableTemperature(),
    briefing: createUnavailableBriefing(),
    futures: createUnavailableFutures(),
    cnShortSentiment: createUnavailableCnShortSentiment(),
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

function writeLocalMarketOverviewSnapshot(panels: PanelState): string | null {
  if (typeof window === 'undefined') {
    return null;
  }
  const payload: Partial<PanelState> = {};
  (Object.keys(panels) as PanelKey[]).forEach((panelKey) => {
    const value = panels[panelKey];
    if (hasUsablePanelValue(value)) {
      payload[panelKey] = value as never;
    }
  });
  if (Object.keys(payload).length === 0) {
    return null;
  }
  const savedAt = new Date().toISOString();
  try {
    window.localStorage.setItem(MARKET_OVERVIEW_LKG_STORAGE_KEY, JSON.stringify({
      schemaVersion: 1,
      savedAt,
      payload,
    } satisfies LocalSnapshotEnvelope));
    return savedAt;
  } catch {
    // localStorage can be unavailable in private or quota-limited sessions.
    return null;
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
        ...createUnavailableTemperature(),
        updatedAt: new Date().toISOString(),
        warning: `市场温度数据待补。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'briefing':
      return {
        ...createUnavailableBriefing(),
        updatedAt: new Date().toISOString(),
        warning: `市场简报数据待补。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'futures':
      return {
        ...createUnavailableFutures(),
        updatedAt: new Date().toISOString(),
        warning: `期货数据待补。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'cnShortSentiment':
      return {
        ...createUnavailableCnShortSentiment(),
        updatedAt: new Date().toISOString(),
        warning: `短线情绪数据待补。${describePanelError(error)}`,
      } as PanelState[PanelKey];
    case 'indices':
      return fallbackPanel('IndexTrendsCard', error) as PanelState[PanelKey];
    case 'volatility':
      return fallbackPanel('VolatilityCard', error) as PanelState[PanelKey];
    case 'crypto':
      return fallbackPanel('CryptoCard', error) as PanelState[PanelKey];
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

const inFlightPanelRequestCache = new Map<string, Promise<PanelState[PanelKey]>>();
const inFlightReadinessRequestCache = new Map<string, Promise<unknown>>();

function panelRequestCacheKey(panelKey: PanelKey): string {
  return `market-overview:${String(panelKey)}`;
}

function loadPanelWithRequestDedupe(
  panelKey: PanelKey,
  _mode: RefreshPanelRequestMode,
  loadPanel: () => Promise<PanelState[PanelKey]>,
): Promise<PanelState[PanelKey]> {
  const cacheKey = panelRequestCacheKey(panelKey);
  const cached = inFlightPanelRequestCache.get(cacheKey);
  if (cached) {
    return cached;
  }
  const promise = loadPanel().finally(() => {
    if (inFlightPanelRequestCache.get(cacheKey) === promise) {
      inFlightPanelRequestCache.delete(cacheKey);
    }
  });
  inFlightPanelRequestCache.set(cacheKey, promise);
  return promise;
}

function loadReadinessWithRequestDedupe<T>(cacheKey: string, load: () => Promise<T>): Promise<T> {
  const cached = inFlightReadinessRequestCache.get(cacheKey) as Promise<T> | undefined;
  if (cached) {
    return cached;
  }
  const promise = load().finally(() => {
    if (inFlightReadinessRequestCache.get(cacheKey) === promise) {
      inFlightReadinessRequestCache.delete(cacheKey);
    }
  });
  inFlightReadinessRequestCache.set(cacheKey, promise);
  return promise;
}

export function __resetMarketOverviewRequestOwnershipForTests(): void {
  if (!import.meta.env.TEST) {
    return;
  }
  inFlightPanelRequestCache.clear();
  inFlightReadinessRequestCache.clear();
  cryptoStreamSubscribers.clear();
  sharedCryptoEventSource?.close();
  sharedCryptoEventSource = null;
  latestCryptoStreamStatus = 'snapshot';
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

const MarketOverviewEvidenceBoundaryStrip = ({
  matrix,
}: {
  matrix?: ConsumerEvidenceReadinessMatrix | null;
}) => {
  const view = buildConsumerEvidenceBoundaryView(matrix);

  return (
    <section
      data-testid="market-overview-evidence-boundary"
      className="rounded-lg border border-white/[0.06] bg-white/[0.025] px-3 py-2.5"
    >
      <div className="flex min-w-0 flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-medium text-white/48">市场总览证据边界</p>
          <p className="mt-1 text-sm font-semibold text-white/84">{view.label}</p>
        </div>
        <div className="flex min-w-0 flex-wrap gap-1.5 md:justify-end">
          <TerminalChip variant={view.variant}>{view.label}</TerminalChip>
          {view.chips.map((chip) => (
            <TerminalChip key={chip.key} variant={chip.variant}>{chip.label}</TerminalChip>
          ))}
        </div>
      </div>
      <p className="mt-2 text-[11px] leading-5 text-white/48">{view.nextEvidence}</p>
      {view.note ? <p className="mt-1 text-[11px] leading-5 text-white/40">{view.note}</p> : null}
    </section>
  );
};

const CrossAssetDriverReadinessStrip = ({
  readiness,
}: {
  readiness?: CrossAssetDriverReadiness | null;
}) => {
  const view = buildCrossAssetDriverReadinessView(readiness);

  return (
    <section
      data-testid="market-overview-cross-asset-readiness"
      className="rounded-lg border border-white/[0.06] bg-white/[0.025] px-3 py-2.5"
    >
      <div className="flex min-w-0 flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-medium text-white/48">跨资产驱动输入</p>
          <p className="mt-1 text-sm font-semibold text-white/84">{view.label}</p>
        </div>
        <div className="flex min-w-0 flex-wrap gap-1.5 md:justify-end">
          <TerminalChip variant={view.variant}>{view.label}</TerminalChip>
          {view.chips.map((chip) => (
            <TerminalChip key={chip.key} variant={chip.variant}>{chip.label}</TerminalChip>
          ))}
        </div>
      </div>
      <p className="mt-2 text-[11px] leading-5 text-white/48">{view.note}</p>
      <p className="mt-1 text-[11px] leading-5 text-white/40">仅展示已配置输入与缓存状态；未返回的驱动不做方向推断。</p>
    </section>
  );
};

type MarketRegimeReadinessStatus =
  | 'available'
  | 'missing provider'
  | 'entitlement required'
  | 'degraded'
  | 'stale'
  | 'not available';

type MarketRegimeReadinessCategory = {
  key: string;
  label: string;
  capabilityCategory?: string;
  match: RegExp;
  fallbackDetail: string;
};

type MarketRegimeReadinessItem = {
  key: string;
  label: string;
  status: MarketRegimeReadinessStatus;
  variant: 'neutral' | 'success' | 'caution' | 'danger' | 'info';
  detail: string;
  freshnessLabel: string;
  asOfLabel?: string;
};

const MARKET_REGIME_READINESS_CATEGORIES: MarketRegimeReadinessCategory[] = [
  {
    key: 'breadth',
    label: 'breadth',
    capabilityCategory: 'market_breadth_flows',
    match: /\bbreadth\b|advance|decline|new highs?|new lows?/i,
    fallbackDetail: 'Breadth inputs are not returned by the readiness registry.',
  },
  {
    key: 'sector-leadership',
    label: 'sector/industry leadership',
    capabilityCategory: 'sector_rotation',
    match: /sector|industry|rotation|leadership/i,
    fallbackDetail: 'Sector and industry leadership inputs are not returned by the readiness registry.',
  },
  {
    key: 'volatility-risk',
    label: 'volatility/risk regime',
    capabilityCategory: 'macro_cross_asset_regime',
    match: /volatility|risk|regime|vix|stress/i,
    fallbackDetail: 'Volatility and risk regime inputs are not returned by the readiness registry.',
  },
  {
    key: 'options-structure',
    label: 'options structure / gamma inputs',
    capabilityCategory: 'options_structure',
    match: /option|chain|greek|gamma|structure/i,
    fallbackDetail: 'Options structure inputs are not returned by the readiness registry.',
  },
  {
    key: 'flows-positioning',
    label: 'flows/positioning',
    capabilityCategory: 'market_breadth_flows',
    match: /flow|positioning|fund|liquidity|pressure/i,
    fallbackDetail: 'Flows and positioning inputs are not returned by the readiness registry.',
  },
  {
    key: 'macro-cross-asset',
    label: 'macro/cross-asset inputs',
    capabilityCategory: 'macro_cross_asset_regime',
    match: /macro|cross.?asset|rates?|fx|credit|liquidity/i,
    fallbackDetail: 'Macro and cross-asset inputs are not returned by the readiness registry.',
  },
];

const MARKET_REGIME_DIAGNOSTIC_TOKEN_PATTERN =
  /providerClass|providerName|providerAttempted|requiredProviderClass|sourceAuthorityRouter|apiKeyPresent|endpointHost|requestId|traceId|cacheKey|rawPayload|exceptionClass|exceptionChain|credential|token|env/gi;

function sanitizeMarketRegimeReadinessText(value?: string | null, fallback = 'freshness pending'): string {
  const trimmed = String(value || '').replace(/\s+/g, ' ').trim();
  if (!trimmed) {
    return fallback;
  }
  return trimmed
    .replace(MARKET_REGIME_DIAGNOSTIC_TOKEN_PATTERN, 'diagnostic hidden')
    .replace(/\bprovider\b/gi, 'data source')
    .replace(/\braw\b/gi, 'source')
    .replace(/\bdebug\b/gi, 'diagnostic')
    .replace(/\bcache\s*key\b/gi, 'stored reference');
}

function marketRegimeReadinessStatusVariant(
  status: MarketRegimeReadinessStatus,
): MarketRegimeReadinessItem['variant'] {
  if (status === 'available') return 'success';
  if (status === 'entitlement required') return 'danger';
  if (status === 'degraded' || status === 'stale' || status === 'missing provider') return 'caution';
  return 'neutral';
}

function marketRegimeReadinessStatusFromCapability(
  item?: ProfessionalDataCapabilityViewItem,
): MarketRegimeReadinessStatus {
  if (!item) {
    return 'missing provider';
  }
  const status = item.status.key;
  const freshness = String(item.freshness || item.detail || '').toLowerCase();
  if (freshness.includes('stale') || freshness.includes('expired')) {
    return 'stale';
  }
  if (status === 'live') return 'available';
  if (status === 'entitlement_required') return 'entitlement required';
  if (status === 'configured_missing') return 'missing provider';
  if (status === 'not_implemented') return 'not available';
  return 'degraded';
}

function marketRegimeReadinessSeverity(status: MarketRegimeReadinessStatus): number {
  const order: Record<MarketRegimeReadinessStatus, number> = {
    'entitlement required': 6,
    'not available': 5,
    'missing provider': 4,
    stale: 3,
    degraded: 2,
    available: 1,
  };
  return order[status];
}

function formatMarketRegimeReadinessDate(value?: string | null): string | undefined {
  if (!value) {
    return undefined;
  }
  const trimmed = String(value).trim();
  if (!trimmed) {
    return undefined;
  }
  const parsed = new Date(trimmed);
  if (!Number.isNaN(parsed.getTime())) {
    return parsed.toISOString().slice(0, 10);
  }
  return trimmed.slice(0, 10);
}

function capabilityMatchesMarketRegimeCategory(
  item: ProfessionalDataCapabilityViewItem,
  category: MarketRegimeReadinessCategory,
): boolean {
  const haystack = [
    item.capabilityId,
    item.label,
    item.detail,
  ].join(' ');
  return category.match.test(haystack);
}

function pickMarketRegimeCapability(
  category: MarketRegimeReadinessCategory,
  items: ProfessionalDataCapabilityViewItem[],
): ProfessionalDataCapabilityViewItem | undefined {
  const exactMatches = items.filter((item) => capabilityMatchesMarketRegimeCategory(item, category));
  const categoryMatches = category.capabilityCategory
    ? items.filter((item) => item.categoryKey === category.capabilityCategory)
    : [];
  const candidates = exactMatches.length ? exactMatches : categoryMatches;
  return candidates
    .map((item) => ({
      item,
      status: marketRegimeReadinessStatusFromCapability(item),
    }))
    .sort((left, right) => marketRegimeReadinessSeverity(right.status) - marketRegimeReadinessSeverity(left.status))[0]?.item;
}

function buildVolatilityRiskReadinessFromOfficialRisk(
  readiness?: OfficialRiskSourceReadiness | null,
): MarketRegimeReadinessItem | null {
  if (!readiness) {
    return null;
  }
  const pillars = [readiness.vix, readiness.rates, readiness.fedLiquidity].filter(Boolean);
  if (!pillars.length) {
    return null;
  }
  const isStale = pillars.some((pillar) => pillar?.state === 'stale' || pillar?.freshness === 'stale' || pillar?.freshness === 'fallback');
  const isBlocked = pillars.every((pillar) => pillar?.state === 'blocked' || pillar?.state === 'missing' || pillar?.freshness === 'unavailable');
  const hasReady = pillars.some((pillar) => pillar?.state === 'ready');
  const status: MarketRegimeReadinessStatus = isStale
    ? 'stale'
    : isBlocked
      ? 'not available'
      : hasReady
        ? 'available'
        : 'degraded';
  const asOfLabel = formatMarketRegimeReadinessDate(
    readiness.vix?.asOf || readiness.vix?.latestDate || readiness.rates?.asOf || readiness.rates?.latestDate || readiness.fedLiquidity?.asOf || readiness.fedLiquidity?.latestDate,
  );
  return {
    key: 'volatility-risk',
    label: 'volatility/risk regime',
    status,
    variant: marketRegimeReadinessStatusVariant(status),
    detail: sanitizeMarketRegimeReadinessText(readiness.consumerSummary || readiness.nextDataAction, 'Official risk inputs are partially returned.'),
    freshnessLabel: asOfLabel ? `freshness ${asOfLabel}` : 'freshness pending',
    asOfLabel,
  };
}

function buildMarketRegimeReadinessItems(
  view: ProfessionalDataCapabilityRegistryView | null,
  riskReadiness?: OfficialRiskSourceReadiness | null,
): MarketRegimeReadinessItem[] {
  const capabilityItems = (view?.categories || []).flatMap((category) => category.items);
  const officialRiskItem = buildVolatilityRiskReadinessFromOfficialRisk(riskReadiness);
  return MARKET_REGIME_READINESS_CATEGORIES.map((category) => {
    if (category.key === 'volatility-risk' && officialRiskItem) {
      const capability = pickMarketRegimeCapability(category, capabilityItems);
      if (capability) {
        const capabilityStatus = marketRegimeReadinessStatusFromCapability(capability);
        if (marketRegimeReadinessSeverity(capabilityStatus) >= marketRegimeReadinessSeverity(officialRiskItem.status)) {
          const capabilityAsOf = formatMarketRegimeReadinessDate(capability.asOf || capability.updatedAt);
          return {
            key: category.key,
            label: category.label,
            status: capabilityStatus,
            variant: marketRegimeReadinessStatusVariant(capabilityStatus),
            detail: sanitizeMarketRegimeReadinessText(capability.detail, category.fallbackDetail),
            freshnessLabel: sanitizeMarketRegimeReadinessText(capability.freshness, capabilityAsOf ? `freshness ${capabilityAsOf}` : 'freshness pending'),
            asOfLabel: capabilityAsOf,
          };
        }
      }
      return officialRiskItem;
    }

    const capability = pickMarketRegimeCapability(category, capabilityItems);
    const status = marketRegimeReadinessStatusFromCapability(capability);
    const asOfLabel = formatMarketRegimeReadinessDate(capability?.asOf || capability?.updatedAt);
    return {
      key: category.key,
      label: category.label,
      status,
      variant: marketRegimeReadinessStatusVariant(status),
      detail: sanitizeMarketRegimeReadinessText(capability?.detail, category.fallbackDetail),
      freshnessLabel: sanitizeMarketRegimeReadinessText(capability?.freshness, asOfLabel ? `freshness ${asOfLabel}` : 'freshness pending'),
      asOfLabel,
    };
  });
}

type MarketOverviewFamilyReadinessState =
  | 'available'
  | 'missing'
  | 'stale'
  | 'not_configured'
  | 'insufficient_coverage'
  | 'unavailable';

type MarketOverviewReadinessFamily = {
  key: string;
  label: string;
  state: MarketOverviewFamilyReadinessState;
  detail: string;
};

const MARKET_OVERVIEW_FAMILY_STATE_VARIANT: Record<MarketOverviewFamilyReadinessState, 'neutral' | 'success' | 'caution' | 'danger' | 'info'> = {
  available: 'success',
  missing: 'neutral',
  stale: 'caution',
  not_configured: 'neutral',
  insufficient_coverage: 'caution',
  unavailable: 'danger',
};

function panelHasCurrentItems(panel?: MarketOverviewPanel | null): boolean {
  return Boolean(
    panel
      && panel.source !== 'error'
      && panel.source !== 'unavailable'
      && panel.freshness !== 'error'
      && panel.freshness !== 'unavailable'
      && panel.isUnavailable !== true
      && Array.isArray(panel.items)
      && panel.items.some((item) => item.isUnavailable !== true && item.value != null),
  );
}

function futuresHasCurrentItems(futures?: MarketFuturesResponse | null): boolean {
  return Boolean(
    futures
      && futures.source !== 'error'
      && futures.source !== 'unavailable'
      && futures.freshness !== 'error'
      && futures.freshness !== 'unavailable'
      && Array.isArray(futures.items)
      && futures.items.some((item) => item.value != null),
  );
}

function panelFamilyState(panels: Array<MarketOverviewPanel | undefined | null>): MarketOverviewFamilyReadinessState {
  if (panels.some((panel) => panelHasCurrentItems(panel) && (panel?.isStale || panel?.freshness === 'stale'))) {
    return 'stale';
  }
  if (panels.some(panelHasCurrentItems)) {
    return 'available';
  }
  if (panels.some((panel) => panel?.source === 'error' || panel?.freshness === 'error')) {
    return 'unavailable';
  }
  return 'missing';
}

function capabilityFamilyState(
  view: ProfessionalDataCapabilityRegistryView | null,
  categoryKey: string,
  match: RegExp,
): MarketOverviewFamilyReadinessState {
  const items = (view?.categories || []).flatMap((category) => category.items);
  const candidates = items.filter((item) => item.categoryKey === categoryKey || match.test(`${item.capabilityId} ${item.label} ${item.detail}`));
  if (!candidates.length) {
    return 'not_configured';
  }
  if (candidates.some((item) => item.status.key === 'live')) {
    return 'available';
  }
  if (candidates.some((item) => item.status.key === 'degraded')) {
    return 'insufficient_coverage';
  }
  if (candidates.some((item) => String(item.freshness || '').toLowerCase().includes('stale'))) {
    return 'stale';
  }
  if (candidates.some((item) => item.status.key === 'configured_missing' || item.status.key === 'entitlement_required')) {
    return 'not_configured';
  }
  return 'unavailable';
}

function evidenceFamilyState(
  matrix: ConsumerEvidenceReadinessMatrix | null,
  match: RegExp,
): MarketOverviewFamilyReadinessState | null {
  const items = (matrix?.items || []).filter((item) => match.test(`${item.surface} ${item.evidenceFamily} ${item.requiredInputs.join(' ')}`));
  if (!items.length) {
    return null;
  }
  if (items.some((item) => item.readinessState === 'score_grade')) {
    return 'available';
  }
  if (items.some((item) => item.staleInputs.length > 0)) {
    return 'stale';
  }
  if (items.some((item) => item.readinessState === 'observation_only')) {
    return 'insufficient_coverage';
  }
  if (items.some((item) => item.blockedInputs.length > 0 || item.readinessState === 'blocked')) {
    return 'unavailable';
  }
  return 'missing';
}

function crossAssetFamilyState(readiness: CrossAssetDriverReadiness | null): MarketOverviewFamilyReadinessState {
  const drivers = readiness?.drivers || [];
  if (!drivers.length) {
    return 'not_configured';
  }
  if (drivers.some((driver) => driver.state === 'available')) {
    return drivers.every((driver) => driver.state === 'available') ? 'available' : 'insufficient_coverage';
  }
  if (drivers.some((driver) => driver.state === 'stale')) {
    return 'stale';
  }
  if (drivers.some((driver) => driver.state === 'insufficient_history')) {
    return 'insufficient_coverage';
  }
  if (drivers.every((driver) => driver.state === 'not_configured')) {
    return 'not_configured';
  }
  return 'missing';
}

function buildMarketOverviewReadinessFamilies(params: {
  panels: PanelState;
  consumerEvidenceReadinessMatrix: ConsumerEvidenceReadinessMatrix | null;
  crossAssetDriverReadiness: CrossAssetDriverReadiness | null;
  professionalDataCapabilities: ProfessionalDataCapabilityRegistryView | null;
}): MarketOverviewReadinessFamily[] {
  const { panels, consumerEvidenceReadinessMatrix, crossAssetDriverReadiness, professionalDataCapabilities } = params;
  const marketIndexState = evidenceFamilyState(consumerEvidenceReadinessMatrix, /market[_-]?index|index|quote/i)
    || (futuresHasCurrentItems(panels.futures) ? 'available' : panelFamilyState([panels.indices, panels.cnIndices]));
  const sectorState = evidenceFamilyState(consumerEvidenceReadinessMatrix, /sector|industry|rotation/i)
    || capabilityFamilyState(professionalDataCapabilities, 'sector_rotation', /sector|industry|rotation/i);
  const breadthState = evidenceFamilyState(consumerEvidenceReadinessMatrix, /breadth|advance|decline/i)
    || panelFamilyState([panels.cnBreadth, panels.usBreadth]);
  const macroState = evidenceFamilyState(consumerEvidenceReadinessMatrix, /macro|regime|rates|volatility/i)
    || capabilityFamilyState(professionalDataCapabilities, 'macro_cross_asset_regime', /macro|regime|rates|volatility/i);
  const crossAssetState = crossAssetFamilyState(crossAssetDriverReadiness);
  const newsState = evidenceFamilyState(consumerEvidenceReadinessMatrix, /news|catalyst|regime/i)
    || capabilityFamilyState(professionalDataCapabilities, 'stock_research_data', /news|catalyst|regime/i);
  const historicalState = crossAssetDriverReadiness?.drivers.some((driver) => driver.cachedOhlcv?.usableBars > 0)
    ? 'available'
    : crossAssetDriverReadiness?.drivers.some((driver) => driver.state === 'insufficient_history')
      ? 'insufficient_coverage'
      : 'missing';

  return [
    { key: 'market-index', label: 'market/index', state: marketIndexState, detail: '指数、区域市场和期货输入。' },
    { key: 'sector-rotation', label: 'sector/industry rotation', state: sectorState, detail: '行业、主题和轮动输入。' },
    { key: 'market-breadth', label: 'market breadth', state: breadthState, detail: '上涨/下跌、新高/新低和市场宽度输入。' },
    { key: 'macro-regime', label: 'macro/regime', state: macroState, detail: '宏观、利率、波动率和 regime 输入。' },
    { key: 'cross-asset', label: 'cross-asset drivers', state: crossAssetState, detail: '美元、利率、商品、信用或其他跨资产驱动。' },
    { key: 'news-catalyst', label: 'news/catalyst/regime evidence', state: newsState, detail: '新闻、催化和 regime 证据边界。' },
    { key: 'historical-ohlcv', label: 'historical OHLCV', state: historicalState, detail: '页面依赖的历史 OHLCV 和缓存覆盖。' },
  ];
}

const MarketOverviewReadinessEmptyPanel = ({
  families,
  showOperatorCue,
}: {
  families: MarketOverviewReadinessFamily[];
  showOperatorCue: boolean;
}) => {
  const allClosed = families.every((family) => family.state !== 'available');

  return (
    <section
      data-testid="market-overview-readiness-empty-panel"
      className="rounded-lg border border-amber-300/14 bg-amber-300/[0.035] px-3 py-3"
    >
      <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-medium text-amber-100/68">Market Overview readiness</p>
          <p className="mt-1 text-sm font-semibold text-white/86">
            {allClosed ? 'Market Overview 数据待补' : 'Market Overview 部分数据可用'}
          </p>
          <p className="mt-1 max-w-3xl text-[11px] leading-5 text-white/52">
            缺失的数据族保持关闭，不生成市场概览、图表分数、结论或建议；已返回的数据区块仍按原始证据展示。
          </p>
        </div>
        {showOperatorCue ? (
          <div className="flex shrink-0 flex-wrap gap-2">
            <a className={MARKET_OVERVIEW_SETUP_ACTION_CLASS} href={buildProviderOpsSetupHref('market_overview')}>
              查看数据状态
            </a>
            <a className={MARKET_OVERVIEW_SETUP_ACTION_CLASS} href={buildDataSourcesSetupHref('market_overview')}>
              前往数据设置
            </a>
          </div>
        ) : (
          <TerminalChip variant="neutral" className="shrink-0">仅显示可用证据</TerminalChip>
        )}
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
        {families.map((family) => (
          <div key={family.key} className="min-w-0 rounded-md border border-white/[0.05] bg-black/10 px-3 py-2.5">
            <div className="flex min-w-0 items-start justify-between gap-2">
              <p className="min-w-0 text-[11px] font-semibold text-white/76">{family.label}</p>
              <TerminalChip variant={MARKET_OVERVIEW_FAMILY_STATE_VARIANT[family.state]} className="shrink-0 text-[10px]">
                {family.state}
              </TerminalChip>
            </div>
            <p className="mt-1 text-[11px] leading-5 text-white/42">{family.detail}</p>
          </div>
        ))}
      </div>
    </section>
  );
};

const MarketRegimeReadinessSurface = ({
  view,
  riskReadiness,
  loading,
  error,
  onRetry,
}: {
  view: ProfessionalDataCapabilityRegistryView | null;
  riskReadiness?: OfficialRiskSourceReadiness | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) => {
  const statusCounts = view?.statusCounts || [];
  const readinessItems = buildMarketRegimeReadinessItems(view, riskReadiness);

  return (
    <section
      data-testid="market-regime-readiness-surface"
      className="rounded-lg border border-white/[0.06] bg-white/[0.025] px-3 py-2.5"
    >
      <div className="flex min-w-0 flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-medium text-white/48">Market regime data readiness</p>
          <p className="mt-1 text-sm font-semibold text-white/84">
            {loading
              ? '正在加载市场状态数据'
              : error
                ? '市场状态数据可用性暂不可用'
                : '关键市场状态输入可用性'}
          </p>
          <p className="mt-1 text-[11px] leading-5 text-white/42">
            no fabricated regime score · no fake gamma or flow values
          </p>
        </div>
        <div className="flex min-w-0 flex-wrap gap-1.5 md:justify-end">
          {statusCounts.map((chip) => (
            <TerminalChip key={chip.key} variant={chip.variant}>{chip.label}</TerminalChip>
          ))}
        </div>
      </div>

      {loading ? (
        <div data-testid="market-regime-readiness-skeleton" className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="h-20 animate-pulse rounded-md border border-white/[0.05] bg-white/[0.03]" />
          ))}
        </div>
      ) : error ? (
        <div data-testid="market-regime-readiness-error" className="mt-3 flex items-center justify-between gap-3 rounded-md border border-amber-300/20 bg-amber-400/8 px-3 py-2">
          <p className="min-w-0 text-xs leading-5 text-amber-100/80">
            {error}
          </p>
          <TerminalButton variant="compact" onClick={onRetry}>
            重试
          </TerminalButton>
        </div>
      ) : (
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {readinessItems.map((item) => (
            <section
              key={item.key}
              data-testid={`market-regime-readiness-${item.key}`}
              className="rounded-md border border-white/[0.05] bg-white/[0.02] px-3 py-2.5"
            >
              <div className="flex min-w-0 items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[11px] font-medium text-white/48">{item.label}</p>
                  <p className="mt-1 text-sm font-semibold text-white/86">{item.status}</p>
                </div>
                <TerminalChip variant={item.variant}>{item.status}</TerminalChip>
              </div>
              <p className="mt-2 text-[11px] leading-5 text-white/48">{item.detail}</p>
              <p className="mt-1 text-[11px] leading-5 text-white/36">
                {item.asOfLabel ? `${item.freshnessLabel} · as of ${item.asOfLabel}` : item.freshnessLabel}
              </p>
            </section>
          ))}
        </div>
      )}
    </section>
  );
};

const MARKET_REGIME_READ_MODEL_CHIP_VARIANT: Record<string, 'neutral' | 'success' | 'caution' | 'danger' | 'info'> = {
  product_ready: 'success',
  ok: 'success',
  degraded: 'caution',
  partial: 'caution',
  blocked: 'danger',
  failed_closed: 'danger',
  unavailable: 'neutral',
};

const MARKET_REGIME_CARD_VARIANT: Record<string, 'neutral' | 'success' | 'caution' | 'danger' | 'info'> = {
  positive: 'success',
  neutral: 'info',
  negative: 'caution',
  degraded: 'caution',
  unavailable: 'danger',
};

const MARKET_REGIME_NO_ADVICE_PATTERN =
  /\b(buy|sell|hold|recommendation|target price|enter|exit|long|short)\b|加仓|减仓|买入|卖出|持有|目标价|推荐/gi;

function sanitizeRegimeReadModelText(value?: unknown, fallback = 'Evidence unavailable'): string {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (!text) {
    return fallback;
  }
  return text
    .replace(MARKET_REGIME_NO_ADVICE_PATTERN, 'observation-only')
    .replace(/Proxy/g, 'Context')
    .replace(/proxy/g, 'context');
}

function regimeReadModelConsumerLabel(value: unknown, language: 'zh' | 'en', fallback?: string): string {
  const raw = sanitizeRegimeReadModelText(value, fallback || (language === 'en' ? 'Evidence unavailable' : '证据暂不可用'));
  const normalized = raw.trim().toLowerCase().replace(/[\s-]+/g, '_');
  const labels: Record<string, { zh: string; en: string }> = {
    available: { zh: '可用', en: 'Available' },
    unavailable: { zh: '暂不可用', en: 'Unavailable' },
    missing: { zh: '待补', en: 'Missing' },
    stale: { zh: '待更新', en: 'Needs refresh' },
    partial: { zh: '部分可用', en: 'Partly available' },
    blocked: { zh: '已阻断', en: 'Blocked' },
    degraded: { zh: '部分缺口', en: 'Partial context' },
    unknown: { zh: '待确认', en: 'To confirm' },
    insufficient_data: { zh: '数据不足', en: 'Insufficient data' },
    product_ready: { zh: '产品可用', en: 'Product-ready' },
    failed_closed: { zh: '已失败关闭', en: 'Failed closed' },
    none: { zh: '无', en: 'none' },
  };
  if (labels[normalized]) {
    return labels[normalized][language];
  }
  if (language === 'zh' && /\b(quote|snapshot|ohlcv|universe|provider|cache|raw|schema|diagnostic)\b/i.test(raw)) {
    return '证据细节已折叠';
  }
  return raw;
}

function formatRegimeReadModelMetricValue(value: unknown): string {
  if (value == null || value === '') {
    return 'n/a';
  }
  if (typeof value === 'number') {
    return Number.isFinite(value) ? String(Math.round(value * 10000) / 10000) : 'n/a';
  }
  if (Array.isArray(value)) {
    return value.length ? value.map((item) => sanitizeRegimeReadModelText(item)).join(', ') : 'none';
  }
  if (typeof value === 'object') {
    return 'available';
  }
  return sanitizeRegimeReadModelText(value);
}

const MarketRegimeReadModelSurface = ({
  payload,
  loading,
  error,
  onRetry,
}: {
  payload: MarketRegimeReadModelResponse | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) => {
  const { language } = useI18n();
  const locale = language === 'en' ? 'en' : 'zh';
  const readinessLabel = payload?.readiness?.label || 'unavailable';
  const status = payload?.status || 'unavailable';
  const missingFamilies = payload?.missingDataFamilies || payload?.readiness?.missingDataFamilies || [];
  const blockedSurfaces = payload?.blockedProductSurfaces || payload?.readiness?.blockedProductSurfaces || [];
  const evidenceCards = payload?.evidenceCards || [];
  const dataQuality = payload?.dataQuality;

  return (
    <section
      data-testid="market-regime-read-model-surface"
      className="rounded-lg border border-white/[0.06] bg-white/[0.025] px-3 py-3"
    >
      <div className="flex min-w-0 flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-medium text-white/48">{locale === 'en' ? 'Market regime read model' : '市场状态证据口径'}</p>
          <p className="mt-1 text-sm font-semibold text-white/86">
            {loading
              ? (locale === 'en' ? 'Loading local regime evidence' : '正在读取本地市场证据')
              : error
                ? (locale === 'en' ? 'Local regime evidence unavailable' : '本地市场证据暂不可用')
                : `${regimeReadModelConsumerLabel(payload?.regime?.label, locale, 'insufficient_data')} · ${regimeReadModelConsumerLabel(status, locale)}`}
          </p>
          <p className="mt-1 max-w-4xl text-[11px] leading-5 text-white/50">
            {loading
              ? (locale === 'en' ? 'Waiting for read-only local evidence fields.' : '正在等待只读市场证据字段。')
              : error
                ? (locale === 'en' ? 'Local regime evidence is unavailable; readiness stays visible as blocked.' : '本地市场证据暂不可用；就绪状态保持为阻断说明。')
                : regimeReadModelConsumerLabel(payload?.productSummary, locale, locale === 'en' ? 'Market regime evidence is not available.' : '市场状态证据暂不可用。')}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-1.5">
          <TerminalChip variant={MARKET_REGIME_READ_MODEL_CHIP_VARIANT[readinessLabel] || 'neutral'}>
            {regimeReadModelConsumerLabel(readinessLabel, locale)}
          </TerminalChip>
          <TerminalChip variant={MARKET_REGIME_READ_MODEL_CHIP_VARIANT[status] || 'neutral'}>
            {regimeReadModelConsumerLabel(status, locale)}
          </TerminalChip>
          {payload?.noAdvice ? <TerminalChip variant="info">{locale === 'en' ? 'Research context only' : '仅作研究语境'}</TerminalChip> : null}
        </div>
      </div>

      {loading ? (
        <div data-testid="market-regime-read-model-skeleton" className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="h-28 animate-pulse rounded-md border border-white/[0.05] bg-white/[0.03]" />
          ))}
        </div>
      ) : error ? (
        <div className="mt-3 flex items-center justify-between gap-3 rounded-md border border-amber-300/20 bg-amber-400/8 px-3 py-2">
          <p className="min-w-0 text-xs leading-5 text-amber-100/80">{error}</p>
          <TerminalButton variant="compact" onClick={onRetry}>重试</TerminalButton>
        </div>
      ) : (
        <>
          <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {evidenceCards.map((card) => (
              <section
                key={card.id}
                data-testid={`market-regime-evidence-card-${card.id}`}
                className="rounded-md border border-white/[0.05] bg-white/[0.02] px-3 py-2.5"
              >
                <div className="flex min-w-0 items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[11px] font-medium text-white/48">{sanitizeRegimeReadModelText(card.title)}</p>
                    <p className="mt-1 text-sm font-semibold text-white/86">{sanitizeRegimeReadModelText(card.headline)}</p>
                  </div>
                  <TerminalChip variant={MARKET_REGIME_CARD_VARIANT[card.status] || MARKET_REGIME_CARD_VARIANT[card.severity] || 'neutral'}>
                    {sanitizeRegimeReadModelText(card.status)}
                  </TerminalChip>
                </div>
                {card.metrics.length ? (
                  <div className="mt-2 grid gap-1.5">
                    {card.metrics.slice(0, 4).map((metric) => (
                      <div key={`${card.id}-${metric.label}`} className="flex min-w-0 items-center justify-between gap-2 text-[11px]">
                        <span className="min-w-0 text-white/42">{sanitizeRegimeReadModelText(metric.label)}</span>
                        <span className="max-w-[55%] truncate text-right font-medium text-white/72">
                          {formatRegimeReadModelMetricValue(metric.value)}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : null}
                {card.reasons.length ? (
                  <ul className="mt-2 space-y-1">
                    {card.reasons.slice(0, 2).map((reason) => (
                      <li key={reason} className="text-[11px] leading-5 text-white/44">
                        {sanitizeRegimeReadModelText(reason)}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {card.sourceFields?.length ? (
                  <p className="mt-2 truncate text-[10px] text-white/30">
                    {card.sourceFields.map((field) => sanitizeRegimeReadModelText(field)).join(' · ')}
                  </p>
                ) : null}
              </section>
            ))}
          </div>

          <div className="mt-3 grid gap-3 lg:grid-cols-3">
            <section className="rounded-md border border-white/[0.05] bg-black/10 px-3 py-2.5">
              <p className="text-[11px] font-medium text-white/48">{locale === 'en' ? 'Data quality' : '数据质量'}</p>
              <div className="mt-2 grid gap-1.5 text-[11px] text-white/62">
                <p>{locale === 'en' ? 'Adjusted series' : '复权序列'}: {regimeReadModelConsumerLabel(dataQuality?.adjustedCoverageState, locale, 'unknown')}</p>
                <p>{locale === 'en' ? 'Price bars' : '价格走势'}: {regimeReadModelConsumerLabel(dataQuality?.ohlcvCoverage?.state, locale, 'unknown')}</p>
                <p>{locale === 'en' ? 'Price state' : '报价状态'}: {regimeReadModelConsumerLabel(dataQuality?.quoteSnapshotCoverage?.state, locale, 'unknown')}</p>
              </div>
            </section>
            <section className="rounded-md border border-white/[0.05] bg-black/10 px-3 py-2.5">
              <p className="text-[11px] font-medium text-white/48">{locale === 'en' ? 'Missing evidence groups' : '待补证据组'}</p>
              <p className="mt-2 text-[11px] leading-5 text-white/62">
                {missingFamilies.length ? missingFamilies.map((item) => regimeReadModelConsumerLabel(item, locale)).join(locale === 'en' ? ', ' : '、') : regimeReadModelConsumerLabel('none', locale)}
              </p>
            </section>
            <section className="rounded-md border border-white/[0.05] bg-black/10 px-3 py-2.5">
              <p className="text-[11px] font-medium text-white/48">{locale === 'en' ? 'Blocked surfaces' : '暂不可用界面'}</p>
              <p className="mt-2 text-[11px] leading-5 text-white/62">
                {blockedSurfaces.length ? blockedSurfaces.map((item) => regimeReadModelConsumerLabel(item, locale)).join(locale === 'en' ? ', ' : '、') : regimeReadModelConsumerLabel('none', locale)}
              </p>
            </section>
          </div>

          <p className="mt-3 text-[11px] leading-5 text-white/42">
            {regimeReadModelConsumerLabel(payload?.nextOperatorAction || payload?.readiness?.nextOperatorAction, locale, locale === 'en' ? 'No next operator action returned.' : '暂未返回下一步证据动作。')}
          </p>
        </>
      )}
    </section>
  );
};

const MarketOverviewPage = () => {
  const { language } = useI18n();
  const { isAdminMode, canReadProviders } = useProductSurface();
  const [initialLocalSnapshot] = useState(() => buildInitialPanelsFromLocalSnapshot());
  const [panels, setPanels] = useState<PanelState>(initialLocalSnapshot.panels);
  const [officialRiskSourceReadiness, setOfficialRiskSourceReadiness] = useState<OfficialRiskSourceReadiness | null>(null);
  const [consumerEvidenceReadinessMatrix, setConsumerEvidenceReadinessMatrix] = useState<ConsumerEvidenceReadinessMatrix | null>(null);
  const [crossAssetDriverReadiness, setCrossAssetDriverReadiness] = useState<CrossAssetDriverReadiness | null>(null);
  const [professionalDataCapabilities, setProfessionalDataCapabilities] = useState<ProfessionalDataCapabilityRegistryView | null>(null);
  const [professionalDataCapabilitiesLoading, setProfessionalDataCapabilitiesLoading] = useState(true);
  const [professionalDataCapabilitiesError, setProfessionalDataCapabilitiesError] = useState<string | null>(null);
  const [regimeReadModel, setRegimeReadModel] = useState<MarketRegimeReadModelResponse | null>(null);
  const [regimeReadModelLoading, setRegimeReadModelLoading] = useState(true);
  const [regimeReadModelError, setRegimeReadModelError] = useState<string | null>(null);
  const [loading, setLoading] = useState(initialLocalSnapshot.source !== 'local');
  const [localSnapshotSavedAt, setLocalSnapshotSavedAt] = useState<string | undefined>(initialLocalSnapshot.savedAt);
  const [refreshErrors, setRefreshErrors] = useState<Record<string, string>>({});
  const [refreshingPanel, setRefreshingPanel] = useState<PanelKey | null>(null);
  const [cryptoRealtimeStatus, setCryptoRealtimeStatus] = useState<CryptoRealtimeStatus>('snapshot');
  const [autoRevalidateTick, setAutoRevalidateTick] = useState(0);
  const [localSnapshotPersistTick, setLocalSnapshotPersistTick] = useState(0);
  const ownsOperatorReadinessRequests = Boolean(isAdminMode && canReadProviders);
  const autoRevalidateTimersRef = useRef<Partial<Record<PanelKey, number>>>({});
  const autoRevalidateAttemptsRef = useRef<Partial<Record<PanelKey, number>>>({});
  const autoRevalidateInFlightRef = useRef<Partial<Record<PanelKey, true>>>({});
  const latestPanelsRef = useRef(panels);
  const latestRefreshingPanelRef = useRef<PanelKey | null>(null);
  const pendingLocalSnapshotRef = useRef<PanelState | null>(null);

  const queueLocalSnapshotPersist = useCallback((nextPanels: PanelState) => {
    pendingLocalSnapshotRef.current = nextPanels;
    setLocalSnapshotPersistTick((currentTick) => currentTick + 1);
  }, []);

  const commitPanelValue = useCallback((
    panelKey: PanelKey,
    value: PanelState[PanelKey],
    options?: { persist?: boolean },
  ) => {
    const nextPanels = { ...latestPanelsRef.current };
    assignPanelValue(nextPanels, panelKey, value);
    latestPanelsRef.current = nextPanels;
    setPanels(nextPanels);
    if (options?.persist) {
      queueLocalSnapshotPersist(nextPanels);
    }
  }, [queueLocalSnapshotPersist]);

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
    const routeEntrySnapshotPanels = { ...latestPanelsRef.current };

    const runRequest = async ([panelKey, loadPanel]: PanelRequest) => {
      debugMarketPanel(panelKey, 'loading');
      try {
        const panel = await withPanelTimeout(loadPanelWithRequestDedupe(panelKey, 'route-entry', loadPanel), panelKey);
        if (!cancelledRef?.current) {
          setRefreshErrors((currentErrors) => {
            const nextErrors = { ...currentErrors };
            delete nextErrors[String(panelKey)];
            return nextErrors;
          });
          commitPanelValue(panelKey, panel);
          assignPanelValue(routeEntrySnapshotPanels, panelKey, panel);
        }
        debugMarketPanel(panelKey, 'success');
      } catch (error) {
        if (!cancelledRef?.current) {
          setRefreshErrors((currentErrors) => ({
            ...currentErrors,
            [String(panelKey)]: describePanelError(error),
          }));
          if (!latestPanelsRef.current[panelKey]) {
            const fallback = fallbackPanelValue(panelKey, error);
            commitPanelValue(panelKey, fallback);
            if (!routeEntrySnapshotPanels[panelKey]) {
              assignPanelValue(routeEntrySnapshotPanels, panelKey, fallback);
            }
          }
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
    if (!cancelledRef?.current) {
      queueLocalSnapshotPersist(routeEntrySnapshotPanels);
    }
  }, [commitPanelValue, queueLocalSnapshotPersist]);

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
      const panel = await withPanelTimeout(loadPanelWithRequestDedupe(panelKey, mode, loadPanel), panelKey);
      setRefreshErrors((currentErrors) => {
        const nextErrors = { ...currentErrors };
        delete nextErrors[String(panelKey)];
        return nextErrors;
      });
      commitPanelValue(panelKey, panel, { persist: true });
      debugMarketPanel(panelKey, 'success');
    } catch (error) {
      setRefreshErrors((currentErrors) => ({
        ...currentErrors,
        [String(panelKey)]: describePanelError(error),
      }));
      if (!latestPanelsRef.current[panelKey]) {
        commitPanelValue(panelKey, fallbackPanelValue(panelKey, error), { persist: true });
      }
      debugMarketPanel(panelKey, 'fallback');
    } finally {
      if (!options?.silent) {
        setRefreshingPanel((currentPanel) => (currentPanel === panelKey ? null : currentPanel));
      }
    }
  }, [commitPanelValue]);

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
    if (!ownsOperatorReadinessRequests) {
      setOfficialRiskSourceReadiness(null);
      setConsumerEvidenceReadinessMatrix(null);
      setCrossAssetDriverReadiness(null);
      return;
    }
    let cancelled = false;

    async function loadSourceReadiness() {
      try {
        const payload = await loadReadinessWithRequestDedupe<MarketOverviewReadinessSnapshot>(
          'operator:data-readiness',
          async () => {
            const readiness = await marketApi.getDataReadiness();
            return {
              officialRiskSourceReadiness: readiness?.officialRiskSourceReadiness || null,
              consumerEvidenceReadinessMatrix: readiness?.consumerEvidenceReadinessMatrix || null,
              crossAssetDriverReadiness: readiness?.crossAssetDriverReadiness || null,
            };
          },
        );
        if (!cancelled) {
          setOfficialRiskSourceReadiness(payload.officialRiskSourceReadiness);
          setConsumerEvidenceReadinessMatrix(payload.consumerEvidenceReadinessMatrix);
          setCrossAssetDriverReadiness(payload.crossAssetDriverReadiness);
        }
      } catch {
        if (!cancelled) {
          setOfficialRiskSourceReadiness(null);
          setConsumerEvidenceReadinessMatrix(null);
          setCrossAssetDriverReadiness(null);
        }
      }
    }

    void loadSourceReadiness();

    return () => {
      cancelled = true;
    };
  }, [ownsOperatorReadinessRequests]);

  const loadProfessionalDataCapabilities = useCallback(async (cancelledRef?: { current: boolean }) => {
    if (!ownsOperatorReadinessRequests) {
      setProfessionalDataCapabilities(null);
      setProfessionalDataCapabilitiesError(null);
      setProfessionalDataCapabilitiesLoading(false);
      return;
    }
    setProfessionalDataCapabilitiesLoading(true);
    setProfessionalDataCapabilitiesError(null);
    try {
      const payload = await loadReadinessWithRequestDedupe(
        'operator:professional-data-capabilities',
        marketApi.getProfessionalDataCapabilities,
      );
      if (!cancelledRef?.current) {
        setProfessionalDataCapabilities(buildProfessionalDataCapabilityRegistryView(payload));
      }
    } catch {
      if (!cancelledRef?.current) {
        setProfessionalDataCapabilities(null);
        setProfessionalDataCapabilitiesError('市场状态数据可用性暂不可用，请稍后重试。');
      }
    } finally {
      if (!cancelledRef?.current) {
        setProfessionalDataCapabilitiesLoading(false);
      }
    }
  }, [ownsOperatorReadinessRequests]);

  useEffect(() => {
    const cancelledRef = { current: false };
    void loadProfessionalDataCapabilities(cancelledRef);
    return () => {
      cancelledRef.current = true;
    };
  }, [loadProfessionalDataCapabilities]);

  const loadRegimeReadModel = useCallback(async (cancelledRef?: { current: boolean }) => {
    setRegimeReadModelLoading(true);
    setRegimeReadModelError(null);
    try {
      const payload = await marketApi.getRegimeReadModel();
      if (!cancelledRef?.current) {
        setRegimeReadModel(payload);
      }
    } catch {
      if (!cancelledRef?.current) {
        setRegimeReadModel(null);
        setRegimeReadModelError('unavailable');
      }
    } finally {
      if (!cancelledRef?.current) {
        setRegimeReadModelLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    const cancelledRef = { current: false };
    void loadRegimeReadModel(cancelledRef);
    return () => {
      cancelledRef.current = true;
    };
  }, [loadRegimeReadModel]);

  useEffect(() => {
    if (localSnapshotPersistTick === 0) {
      return;
    }
    const snapshot = pendingLocalSnapshotRef.current;
    if (!snapshot) {
      return;
    }
    const savedAt = writeLocalMarketOverviewSnapshot(snapshot);
    if (savedAt) {
      setLocalSnapshotSavedAt(savedAt);
    }
  }, [localSnapshotPersistTick]);

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
        commitPanelValue('crypto', panel, { persist: true });
      }
      setCryptoRealtimeStatus(status);
    });
  }, [commitPanelValue, resetAutoRevalidatePanel]);

  const handleWorkbenchRefresh = useCallback((panelKey: PanelKey) => {
    const loadPanel = getPanelLoader(panelKey);
    if (!loadPanel) {
      return;
    }
    resetAutoRevalidatePanel(panelKey);
    void refreshPanel(panelKey, loadPanel);
  }, [refreshPanel, resetAutoRevalidatePanel]);

  const marketOverviewReadinessFamilies = buildMarketOverviewReadinessFamilies({
    panels,
    consumerEvidenceReadinessMatrix,
    crossAssetDriverReadiness,
    professionalDataCapabilities,
  });
  const hasUnavailableMarketOverviewFamily = marketOverviewReadinessFamilies.some((family) => family.state !== 'available');
  return (
    <ConsumerWorkspaceScope className="min-h-0 flex-1">
      <ConsumerWorkspacePageShell
        data-testid="market-overview-shell"
        data-product-surface="market-overview"
        className="flex min-h-0 flex-1 flex-col gap-4 md:gap-6"
      >
        <MarketOverviewWorkbench
          heading={(
            <TerminalPageHeading
              data-testid="market-overview-page-heading"
              title={language === 'en' ? 'Market State Overview' : '市场状态概览'}
            />
          )}
          panels={panels}
          loading={loading}
          localSnapshotSavedAt={localSnapshotSavedAt}
          refreshErrorCount={Object.keys(refreshErrors).length}
          refreshingPanel={refreshingPanel}
          cryptoRealtimeStatus={cryptoRealtimeStatus}
          isCnShortSentimentBootstrapping={loading && panels.cnShortSentiment.source === 'unavailable'}
          showAdminDiagnostics={isAdminMode && canReadProviders}
          onRefreshPanel={handleWorkbenchRefresh}
        />
        <TerminalDisclosure
          data-testid="market-overview-data-diagnostics-disclosure"
          title="查看数据诊断"
          summary="市场状态、证据覆盖和内部就绪度默认折叠"
          className="bg-black/10"
        >
          {hasUnavailableMarketOverviewFamily ? (
            <MarketOverviewReadinessEmptyPanel
              families={marketOverviewReadinessFamilies}
              showOperatorCue={isAdminMode && canReadProviders}
            />
          ) : null}
          <div className="mt-3 grid gap-3">
            <OfficialRiskSourceReadinessStrip readiness={officialRiskSourceReadiness} />
            <MarketOverviewEvidenceBoundaryStrip matrix={consumerEvidenceReadinessMatrix} />
            <CrossAssetDriverReadinessStrip readiness={crossAssetDriverReadiness} />
            <MarketRegimeReadinessSurface
              view={professionalDataCapabilities}
              riskReadiness={officialRiskSourceReadiness}
              loading={professionalDataCapabilitiesLoading}
              error={professionalDataCapabilitiesError}
              onRetry={() => {
                void loadProfessionalDataCapabilities();
              }}
            />
            <MarketRegimeReadModelSurface
              payload={regimeReadModel}
              loading={regimeReadModelLoading}
              error={regimeReadModelError}
              onRetry={() => {
                void loadRegimeReadModel();
              }}
            />
          </div>
        </TerminalDisclosure>
      </ConsumerWorkspacePageShell>
    </ConsumerWorkspaceScope>
  );
};

export default MarketOverviewPage;
