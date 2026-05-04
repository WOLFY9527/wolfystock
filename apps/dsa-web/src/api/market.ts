import apiClient from './index';
import type { MarketDataMeta, MarketOverviewPanel, MarketOverviewItem, MarketProviderHealth } from './marketOverview';
import { toCamelCase } from './utils';
import { API_BASE_URL } from '../utils/constants';

type MarketSnapshotItem = {
  symbol?: string;
  name?: string;
  label?: string;
  price?: number | null;
  value?: number | null;
  change?: number | null;
  changePercent?: number | null;
  changeText?: string | null;
  trend?: number[];
  sparkline?: number[];
  unit?: string | null;
  source?: string | null;
  sourceLabel?: string | null;
  sourceType?: string | null;
  providerHealth?: MarketProviderHealth;
  updatedAt?: string;
  asOf?: string;
  freshness?: MarketDataMeta['freshness'];
  isFallback?: boolean;
  isStale?: boolean;
  isRefreshing?: boolean;
  isFromSnapshot?: boolean;
  lastSuccessfulAt?: string;
  refreshError?: string | null;
  lastError?: string | null;
  delayMinutes?: number;
  warning?: string | null;
  market?: string | null;
  explanation?: string | null;
  hoverDetails?: string[] | null;
  riskDirection?: 'increasing' | 'decreasing' | 'neutral';
};

type MarketSnapshotPayload = {
  items?: MarketSnapshotItem[];
  lastUpdate?: string;
  updatedAt?: string;
  error?: string | null;
  fallbackUsed?: boolean;
  source?: string | null;
  sourceLabel?: string | null;
  sourceType?: string | null;
  providerHealth?: MarketProviderHealth;
  asOf?: string;
  freshness?: MarketDataMeta['freshness'];
  isFallback?: boolean;
  isStale?: boolean;
  isRefreshing?: boolean;
  isFromSnapshot?: boolean;
  lastSuccessfulAt?: string;
  refreshError?: string | null;
  lastError?: string | null;
  delayMinutes?: number;
  warning?: string | null;
  logSessionId?: string | null;
};

function normalizeItem(item: MarketSnapshotItem): MarketOverviewItem {
  const hoverDetails = Array.isArray(item.hoverDetails) ? [...item.hoverDetails] : [];
  if (item.market) {
    hoverDetails.push(`Market ${item.market}`);
  }
  if (item.explanation) {
    hoverDetails.push(item.explanation);
  }
  return {
    symbol: item.symbol || '',
    label: item.label || item.name || item.symbol || '',
    value: item.price ?? item.value,
    unit: item.unit,
    changePct: item.changePercent ?? item.change,
    changeText: item.changeText,
    riskDirection: item.riskDirection,
    trend: Array.isArray(item.trend) ? item.trend : Array.isArray(item.sparkline) ? item.sparkline : [],
    source: item.source || undefined,
    sourceLabel: item.sourceLabel || undefined,
    sourceType: item.sourceType || undefined,
    providerHealth: item.providerHealth,
    updatedAt: item.updatedAt,
    asOf: item.asOf,
    freshness: item.freshness,
    isFallback: item.isFallback,
    isStale: item.isStale,
    isRefreshing: item.isRefreshing,
    isFromSnapshot: item.isFromSnapshot,
    lastSuccessfulAt: item.lastSuccessfulAt,
    refreshError: item.refreshError,
    lastError: item.lastError,
    delayMinutes: item.delayMinutes,
    warning: item.warning,
    hoverDetails,
  };
}

function normalizeMarketSnapshotPayload(rawPayload: Record<string, unknown>, panelName: string): MarketOverviewPanel {
  const payload = toCamelCase<MarketSnapshotPayload>(rawPayload);
  return {
    panelName,
    lastRefreshAt: payload.lastUpdate || payload.updatedAt || new Date().toISOString(),
    status: payload.fallbackUsed ? 'failure' : 'success',
    errorMessage: payload.fallbackUsed ? payload.error : null,
    logSessionId: payload.logSessionId,
    source: payload.source || undefined,
    sourceLabel: payload.sourceLabel || undefined,
    sourceType: payload.sourceType || undefined,
    providerHealth: payload.providerHealth,
    updatedAt: payload.updatedAt || payload.lastUpdate || new Date().toISOString(),
    asOf: payload.asOf,
    freshness: payload.freshness,
    isFallback: payload.isFallback ?? payload.fallbackUsed,
    isStale: payload.isStale,
    isRefreshing: payload.isRefreshing,
    isFromSnapshot: payload.isFromSnapshot,
    lastSuccessfulAt: payload.lastSuccessfulAt,
    refreshError: payload.refreshError,
    lastError: payload.lastError,
    delayMinutes: payload.delayMinutes,
    warning: payload.warning,
    items: Array.isArray(payload.items) ? payload.items.map(normalizeItem) : [],
  };
}

async function getPanel(path: string, panelName: string): Promise<MarketOverviewPanel> {
  const response = await apiClient.get<Record<string, unknown>>(path);
  return normalizeMarketSnapshotPayload(response.data, panelName);
}

function buildEventSourceUrl(path: string): string {
  if (!API_BASE_URL) {
    return path;
  }
  return `${API_BASE_URL.replace(/\/$/, '')}${path}`;
}

export const marketApi = {
  getCrypto: () => getPanel('/api/v1/market/crypto', 'CryptoCard'),
  cryptoStreamUrl: () => buildEventSourceUrl('/api/v1/market/crypto/stream'),
  normalizeCryptoStreamPayload: (payload: Record<string, unknown>) => normalizeMarketSnapshotPayload(payload, 'CryptoCard'),
  getSentiment: () => getPanel('/api/v1/market/sentiment', 'MarketSentimentCard'),
  getCnIndices: () => getPanel('/api/v1/market/cn-indices', 'ChinaIndicesCard'),
  getCnBreadth: () => getPanel('/api/v1/market/cn-breadth', 'ChinaBreadthCard'),
  getCnFlows: () => getPanel('/api/v1/market/cn-flows', 'ChinaFlowsCard'),
  getSectorRotation: () => getPanel('/api/v1/market/sector-rotation', 'SectorRotationCard'),
  getUsBreadth: () => getPanel('/api/v1/market/us-breadth', 'UsBreadthCard'),
  getRates: () => getPanel('/api/v1/market/rates', 'RatesCard'),
  getFxCommodities: () => getPanel('/api/v1/market/fx-commodities', 'FxCommoditiesCard'),
  getTemperature: async (): Promise<MarketTemperatureResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/market/temperature');
    return toCamelCase<MarketTemperatureResponse>(response.data);
  },
  getMarketBriefing: async (): Promise<MarketBriefingResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/market/market-briefing');
    return toCamelCase<MarketBriefingResponse>(response.data);
  },
  getFutures: async (): Promise<MarketFuturesResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/market/futures');
    return toCamelCase<MarketFuturesResponse>(response.data);
  },
  getCnShortSentiment: async (): Promise<CnShortSentimentResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/market/cn-short-sentiment');
    return toCamelCase<CnShortSentimentResponse>(response.data);
  },
};

export type MarketTemperatureTrend = 'improving' | 'stable' | 'cooling' | 'rising' | 'falling';

export type MarketTemperatureScore = {
  value: number;
  label: string;
  trend: MarketTemperatureTrend;
  description: string;
};

export type MarketTemperatureResponse = {
  source: 'computed' | 'fallback' | 'mixed' | string;
  sourceLabel?: string;
  providerHealth?: MarketProviderHealth;
  updatedAt: string;
  asOf?: string;
  freshness?: MarketDataMeta['freshness'];
  isFallback?: boolean;
  isStale?: boolean;
  isRefreshing?: boolean;
  delayMinutes?: number;
  warning?: string | null;
  confidence?: number;
  reliableInputCount?: number;
  fallbackInputCount?: number;
  excludedInputCount?: number;
  isReliable?: boolean;
  scores: {
    overall: MarketTemperatureScore;
    usRiskAppetite: MarketTemperatureScore;
    cnMoneyEffect: MarketTemperatureScore;
    macroPressure: MarketTemperatureScore;
    liquidity: MarketTemperatureScore;
  };
};

export type MarketBriefingItem = {
  title: string;
  message: string;
  severity: 'positive' | 'neutral' | 'warning' | 'risk';
  category: 'us' | 'cn' | 'macro' | 'liquidity' | 'risk' | string;
  confidence?: number;
};

export type MarketBriefingResponse = {
  source: 'computed' | 'fallback' | 'mixed' | string;
  sourceLabel?: string;
  providerHealth?: MarketProviderHealth;
  updatedAt: string;
  asOf?: string;
  freshness?: MarketDataMeta['freshness'];
  isFallback?: boolean;
  isStale?: boolean;
  isRefreshing?: boolean;
  delayMinutes?: number;
  warning?: string | null;
  confidence?: number;
  reliableInputCount?: number;
  fallbackInputCount?: number;
  excludedInputCount?: number;
  isReliable?: boolean;
  items: MarketBriefingItem[];
};

export type MarketFutureItem = {
  name: string;
  symbol: string;
  value: number | null;
  change: number | null;
  changePercent: number | null;
  market: string;
  session: string;
  sparkline: number[];
  source: string;
  sourceLabel?: string;
  providerHealth?: MarketProviderHealth;
  updatedAt?: string;
  asOf?: string;
  freshness?: MarketDataMeta['freshness'];
  isFallback?: boolean;
  isStale?: boolean;
  isRefreshing?: boolean;
  delayMinutes?: number;
  warning?: string | null;
};

export type MarketFuturesResponse = {
  source: 'fallback' | 'public' | 'mixed' | string;
  sourceLabel?: string;
  providerHealth?: MarketProviderHealth;
  updatedAt: string;
  asOf?: string;
  freshness?: MarketDataMeta['freshness'];
  isFallback?: boolean;
  isStale?: boolean;
  isRefreshing?: boolean;
  delayMinutes?: number;
  warning?: string | null;
  items: MarketFutureItem[];
};

export type CnShortSentimentResponse = {
  source: 'fallback' | 'public' | 'mixed' | string;
  sourceLabel?: string;
  providerHealth?: MarketProviderHealth;
  updatedAt: string;
  asOf?: string;
  freshness?: MarketDataMeta['freshness'];
  isFallback?: boolean;
  isStale?: boolean;
  isRefreshing?: boolean;
  delayMinutes?: number;
  warning?: string | null;
  sentimentScore: number;
  summary: string;
  metrics: {
    limitUpCount: number;
    limitDownCount: number;
    failedLimitUpRate: number;
    maxConsecutiveLimitUps: number;
    yesterdayLimitUpPerformance: number;
    firstBoardCount: number;
    secondBoardCount: number;
    highBoardCount: number;
    twentyCmLimitUpCount: number;
    stRiskLevel?: string;
  };
};
