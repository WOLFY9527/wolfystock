import apiClient from './index';
import type { MarketDataMeta, MarketOverviewPanel, MarketOverviewItem, MarketProviderHealth } from './marketOverview';
import { toCamelCase } from './utils';
import { API_BASE_URL } from '../utils/constants';
import { buildAbsoluteApiUrl, joinApiPath } from './path';

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

const MARKET_API_BASE_PATH = '/api/v1/market';

export function buildMarketApiPath(path: string): string {
  return joinApiPath(MARKET_API_BASE_PATH, path);
}

export function buildMarketApiUrl(baseUrl: string, path: string): string {
  return buildAbsoluteApiUrl(baseUrl, path);
}

export const marketApi = {
  getCrypto: () => getPanel(buildMarketApiPath('crypto'), 'CryptoCard'),
  cryptoStreamUrl: () => buildMarketApiUrl(API_BASE_URL, buildMarketApiPath('crypto/stream')),
  normalizeCryptoStreamPayload: (payload: Record<string, unknown>) => normalizeMarketSnapshotPayload(payload, 'CryptoCard'),
  getSentiment: () => getPanel(buildMarketApiPath('sentiment'), 'MarketSentimentCard'),
  getCnIndices: () => getPanel(buildMarketApiPath('cn-indices'), 'ChinaIndicesCard'),
  getCnBreadth: () => getPanel(buildMarketApiPath('cn-breadth'), 'ChinaBreadthCard'),
  getCnFlows: () => getPanel(buildMarketApiPath('cn-flows'), 'ChinaFlowsCard'),
  getSectorRotation: () => getPanel(buildMarketApiPath('sector-rotation'), 'SectorRotationCard'),
  getUsBreadth: () => getPanel(buildMarketApiPath('us-breadth'), 'UsBreadthCard'),
  getRates: () => getPanel(buildMarketApiPath('rates'), 'RatesCard'),
  getFxCommodities: () => getPanel(buildMarketApiPath('fx-commodities'), 'FxCommoditiesCard'),
  getTemperature: async (): Promise<MarketTemperatureResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(buildMarketApiPath('temperature'));
    return normalizeMarketTemperatureResponse(toCamelCase<MarketTemperatureResponse>(response.data));
  },
  getMarketBriefing: async (): Promise<MarketBriefingResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(buildMarketApiPath('market-briefing'));
    return toCamelCase<MarketBriefingResponse>(response.data);
  },
  getFutures: async (): Promise<MarketFuturesResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(buildMarketApiPath('futures'));
    return toCamelCase<MarketFuturesResponse>(response.data);
  },
  getCnShortSentiment: async (): Promise<CnShortSentimentResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(buildMarketApiPath('cn-short-sentiment'));
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

const DEFAULT_MARKET_TEMPERATURE_SCORE: MarketTemperatureScore = {
  value: 50,
  label: '数据不足',
  trend: 'stable',
  description: '当前真实数据不足，市场温度仅供界面演示。',
};

function normalizeMarketTemperatureScore(score?: Partial<MarketTemperatureScore>): MarketTemperatureScore {
  return {
    ...DEFAULT_MARKET_TEMPERATURE_SCORE,
    ...score,
  };
}

export function normalizeMarketTemperatureResponse(
  payload?: Partial<MarketTemperatureResponse> | null,
): MarketTemperatureResponse {
  const scores: Partial<MarketTemperatureResponse['scores']> = payload?.scores || {};
  const hasCompleteScores = Boolean(
    scores.overall
    && scores.usRiskAppetite
    && scores.cnMoneyEffect
    && scores.macroPressure
    && scores.liquidity,
  );
  const inferredReliable = payload?.confidence != null
    ? payload.confidence >= 0.45 && (payload.reliableInputCount == null || payload.reliableInputCount >= 3)
    : false;

  return {
    source: payload?.source || 'fallback',
    sourceLabel: payload?.sourceLabel,
    providerHealth: payload?.providerHealth,
    updatedAt: payload?.updatedAt || new Date().toISOString(),
    asOf: payload?.asOf,
    freshness: payload?.freshness,
    isFallback: payload?.isFallback,
    isStale: payload?.isStale,
    isRefreshing: payload?.isRefreshing,
    delayMinutes: payload?.delayMinutes,
    warning: payload?.warning,
    confidence: payload?.confidence,
    reliableInputCount: payload?.reliableInputCount,
    fallbackInputCount: payload?.fallbackInputCount,
    excludedInputCount: payload?.excludedInputCount,
    isReliable: payload?.isReliable === false
      ? false
      : hasCompleteScores
        ? payload?.isReliable ?? inferredReliable
        : false,
    scores: {
      overall: normalizeMarketTemperatureScore(scores.overall),
      usRiskAppetite: normalizeMarketTemperatureScore(scores.usRiskAppetite),
      cnMoneyEffect: normalizeMarketTemperatureScore(scores.cnMoneyEffect),
      macroPressure: normalizeMarketTemperatureScore(scores.macroPressure),
      liquidity: normalizeMarketTemperatureScore(scores.liquidity),
    },
  };
}

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
