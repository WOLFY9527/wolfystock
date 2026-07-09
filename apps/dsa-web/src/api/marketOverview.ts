import apiClient from './index';
import { toCamelCase } from './utils';

export type MarketRiskDirection = 'increasing' | 'decreasing' | 'neutral';
export type MarketPanelStatus = 'success' | 'partial' | 'unavailable' | 'failure';
export type MarketDataFreshness =
  | 'live'
  | 'fresh'
  | 'delayed'
  | 'cached'
  | 'stale'
  | 'partial'
  | 'fallback'
  | 'mock'
  | 'synthetic'
  | 'error'
  | 'unavailable'
  | 'unknown'
  | 'proxy';
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

export interface MarketProviderFreshness {
  state: MarketDataFreshness;
  label?: string | null;
  available?: boolean;
  sourceConfidence?: string | null;
  isProxy?: boolean;
  isStale?: boolean;
  isUnavailable?: boolean;
  asOf?: string | null;
  sourceLabel?: string | null;
  dataSource?: string | null;
  degradationReason?: string | null;
  proxyFor?: string | null;
  proxySymbol?: string | null;
  proxyLabel?: string | null;
}

export interface MarketConsumerDataQuality {
  state: 'ready' | 'delayed' | 'cached' | 'partial' | 'no_evidence' | 'unavailable' | string;
  label: string;
  available: boolean;
}

export interface MarketDataMeta {
  source: string;
  sourceLabel?: string;
  sourceType?: string;
  providerHealth?: MarketProviderHealth;
  providerFreshness?: MarketProviderFreshness | null;
  dataQuality?: MarketConsumerDataQuality | null;
  updatedAt: string;
  asOf?: string;
  freshness: MarketDataFreshness;
  isProxy?: boolean;
  isFallback?: boolean;
  isStale?: boolean;
  isPartial?: boolean;
  isUnavailable?: boolean;
  isRefreshing?: boolean;
  isFromSnapshot?: boolean;
  lastSuccessfulAt?: string;
  refreshError?: string | null;
  lastError?: string | null;
  delayMinutes?: number;
  sourceTier?: string;
  trustLevel?: string;
  sourceConfidence?: string | null;
  observationOnly?: boolean;
  sourceAuthorityAllowed?: boolean;
  scoreContributionAllowed?: boolean;
  sourceAuthorityReason?: string | null;
  sourceAuthorityRouteRejected?: boolean;
  routeRejectedReasonCodes?: string[];
  reasonCodes?: string[];
  breadthClaimType?: string | null;
  officialExchangePublishedBreadth?: boolean;
  fulfilledMetrics?: string[];
  missingMetrics?: string[];
  metricCoverageRatio?: number | null;
  broadMarketClaimAllowed?: boolean;
  proxyFor?: string | null;
  proxySymbol?: string | null;
  proxyLabel?: string | null;
  officialSeriesId?: string | null;
  officialObservationDate?: string | null;
  officialAsOf?: string | null;
  degradationReason?: string | null;
  degradationReasons?: string[];
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
    providerFreshness: normalized.providerFreshness,
    dataQuality: normalized.dataQuality,
    updatedAt: normalized.updatedAt || normalized.lastRefreshAt,
    asOf: normalized.asOf,
    freshness: normalized.freshness,
    isProxy: normalized.isProxy,
    isFallback: normalized.isFallback,
    isStale: normalized.isStale,
    isPartial: normalized.isPartial,
    isUnavailable: normalized.isUnavailable,
    isRefreshing: normalized.isRefreshing,
    isFromSnapshot: normalized.isFromSnapshot,
    lastSuccessfulAt: normalized.lastSuccessfulAt,
    refreshError: normalized.refreshError,
    lastError: normalized.lastError,
    delayMinutes: normalized.delayMinutes,
    sourceTier: normalized.sourceTier,
    trustLevel: normalized.trustLevel,
    sourceConfidence: normalized.sourceConfidence,
    observationOnly: normalized.observationOnly,
    sourceAuthorityAllowed: normalized.sourceAuthorityAllowed,
    scoreContributionAllowed: normalized.scoreContributionAllowed,
    sourceAuthorityReason: normalized.sourceAuthorityReason,
    sourceAuthorityRouteRejected: normalized.sourceAuthorityRouteRejected,
    routeRejectedReasonCodes: normalized.routeRejectedReasonCodes,
    reasonCodes: normalized.reasonCodes,
    // Preserve backend-owned breadth claim / metric coverage semantics (no invention).
    breadthClaimType: normalized.breadthClaimType,
    officialExchangePublishedBreadth: normalized.officialExchangePublishedBreadth,
    fulfilledMetrics: normalized.fulfilledMetrics,
    missingMetrics: normalized.missingMetrics,
    metricCoverageRatio: normalized.metricCoverageRatio,
    broadMarketClaimAllowed: normalized.broadMarketClaimAllowed,
    officialSeriesId: normalized.officialSeriesId,
    officialObservationDate: normalized.officialObservationDate,
    officialAsOf: normalized.officialAsOf,
    proxyFor: normalized.proxyFor,
    proxySymbol: normalized.proxySymbol,
    proxyLabel: normalized.proxyLabel,
    degradationReason: normalized.degradationReason,
    degradationReasons: normalized.degradationReasons,
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
