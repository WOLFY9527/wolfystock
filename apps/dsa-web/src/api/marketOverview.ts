import apiClient from './index';
import { toCamelCase } from './utils';

export type MarketRiskDirection = 'increasing' | 'decreasing' | 'neutral';
export type MarketPanelStatus = 'success' | 'failure';
export type MarketDataFreshness = 'live' | 'delayed' | 'cached' | 'stale' | 'fallback' | 'mock' | 'error';
export type MarketProviderHealthStatus = 'live' | 'cache' | 'stale' | 'fallback' | 'partial' | 'unavailable' | 'error' | 'refreshing';

export interface MarketProviderHealth {
  provider: string;
  status: MarketProviderHealthStatus;
  asOf?: string | null;
  updatedAt?: string | null;
  latencyMs?: number | null;
  errorSummary?: string | null;
  isFallback: boolean;
  isStale: boolean;
  isRefreshing: boolean;
  sourceLabel: string;
  card?: string;
}

export interface MarketDataMeta {
  source: string;
  sourceLabel?: string;
  sourceType?: string;
  providerHealth?: MarketProviderHealth;
  updatedAt: string;
  asOf?: string;
  freshness: MarketDataFreshness;
  isFallback?: boolean;
  isStale?: boolean;
  isRefreshing?: boolean;
  isFromSnapshot?: boolean;
  lastSuccessfulAt?: string;
  refreshError?: string | null;
  lastError?: string | null;
  delayMinutes?: number;
  warning?: string | null;
}

export interface MarketOverviewItem extends Partial<MarketDataMeta> {
  symbol: string;
  label: string;
  value?: number | null;
  unit?: string | null;
  changePct?: number | null;
  changeText?: string | null;
  riskDirection?: MarketRiskDirection;
  trend?: number[];
  source?: string;
  hoverDetails?: string[] | null;
}

export interface MarketOverviewPanel extends Partial<MarketDataMeta> {
  panelName: string;
  lastRefreshAt: string;
  status: MarketPanelStatus;
  errorMessage?: string | null;
  logSessionId?: string | null;
  items: MarketOverviewItem[];
}

function normalizePanel(payload: Record<string, unknown>): MarketOverviewPanel {
  const normalized = toCamelCase<MarketOverviewPanel>(payload);
  return {
    panelName: normalized.panelName,
    lastRefreshAt: normalized.lastRefreshAt,
    status: normalized.status,
    errorMessage: normalized.errorMessage,
    logSessionId: normalized.logSessionId,
    source: normalized.source,
    sourceLabel: normalized.sourceLabel,
    sourceType: normalized.sourceType,
    providerHealth: normalized.providerHealth,
    updatedAt: normalized.updatedAt || normalized.lastRefreshAt,
    asOf: normalized.asOf,
    freshness: normalized.freshness,
    isFallback: normalized.isFallback,
    isStale: normalized.isStale,
    isRefreshing: normalized.isRefreshing,
    isFromSnapshot: normalized.isFromSnapshot,
    lastSuccessfulAt: normalized.lastSuccessfulAt,
    refreshError: normalized.refreshError,
    lastError: normalized.lastError,
    delayMinutes: normalized.delayMinutes,
    warning: normalized.warning,
    items: Array.isArray(normalized.items) ? normalized.items : [],
  };
}

async function getPanel(path: string): Promise<MarketOverviewPanel> {
  const response = await apiClient.get<Record<string, unknown>>(path);
  return normalizePanel(response.data);
}

export const marketOverviewApi = {
  getIndices: () => getPanel('/api/v1/market-overview/indices'),
  getVolatility: () => getPanel('/api/v1/market-overview/volatility'),
  getSentiment: () => getPanel('/api/v1/market-overview/sentiment'),
  getFundsFlow: () => getPanel('/api/v1/market-overview/funds-flow'),
  getMacro: () => getPanel('/api/v1/market-overview/macro'),
};
