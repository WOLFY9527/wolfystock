import apiClient from './index';
import { toCamelCase } from './utils';
import {
  projectMarketTruth,
  type MarketObservationTruthInput,
} from '../utils/consumerDataQualityViewModel';

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

export interface MarketDataMeta extends MarketObservationTruthInput {
  source: string;
  providerHealth?: MarketProviderHealth;
  providerFreshness?: MarketProviderFreshness | null;
  dataQuality?: MarketConsumerDataQuality | null;
  updatedAt: string;
  freshness: MarketDataFreshness;
  isFromSnapshot?: boolean;
  lastSuccessfulAt?: string;
  refreshError?: string | null;
  lastError?: string | null;
  delayMinutes?: number;
  sourceConfidence?: string | null;
  sourceAuthorityReason?: string | null;
  routeRejectedReasonCodes?: string[];
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

const MARKET_PANEL_STATUSES = new Set<MarketPanelStatus>([
  'success',
  'partial',
  'unavailable',
  'failure',
]);

const MARKET_DATA_FRESHNESS_STATES = new Set<MarketDataFreshness>([
  'live',
  'fresh',
  'delayed',
  'cached',
  'stale',
  'partial',
  'fallback',
  'mock',
  'synthetic',
  'error',
  'unavailable',
  'unknown',
  'proxy',
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function hasText(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function isFiniteNumberOrNull(value: unknown): boolean {
  return value === null || (typeof value === 'number' && Number.isFinite(value));
}

export function isMarketDataFreshnessValue(value: unknown): value is MarketDataFreshness {
  return typeof value === 'string' && MARKET_DATA_FRESHNESS_STATES.has(value as MarketDataFreshness);
}

function hasPanelEvidenceTime(panel: Partial<MarketOverviewPanel>): boolean {
  return hasText(panel.lastRefreshAt) || hasText(panel.updatedAt) || hasText(panel.asOf);
}

function isMarketOverviewItemContract(value: unknown): value is MarketOverviewItem {
  if (!isRecord(value) || !hasText(value.symbol) || !hasText(value.label)) {
    return false;
  }
  if ('value' in value && !isFiniteNumberOrNull(value.value)) {
    return false;
  }
  if ('changePct' in value && value.changePct !== undefined && !isFiniteNumberOrNull(value.changePct)) {
    return false;
  }
  if ('trend' in value && value.trend !== undefined && (
    !Array.isArray(value.trend) || !value.trend.every((point) => typeof point === 'number' && Number.isFinite(point))
  )) {
    return false;
  }
  return value.freshness === undefined || isMarketDataFreshnessValue(value.freshness);
}

export function isMarketOverviewPanelContract(value: unknown): value is MarketOverviewPanel {
  if (!isRecord(value)) {
    return false;
  }
  const panel = value as Partial<MarketOverviewPanel>;
  if (
    !hasText(panel.panelName)
    || !MARKET_PANEL_STATUSES.has(panel.status as MarketPanelStatus)
    || !hasText(panel.source)
    || !isMarketDataFreshnessValue(panel.freshness)
    || !Array.isArray(panel.items)
    || !panel.items.every(isMarketOverviewItemContract)
  ) {
    return false;
  }

  const truth = projectMarketTruth(panel);
  const explicitlyUnavailable = truth.availability === 'unavailable'
    || truth.availability === 'malformed'
    || truth.freshness === 'unavailable'
    || truth.freshness === 'error';
  if (panel.status === 'success' || panel.status === 'partial') {
    const hasObservationIdentity = !['unknown', 'unavailable', 'error'].includes(panel.source.trim().toLowerCase())
      && !['unavailable', 'error', 'unknown'].includes(truth.freshness)
      && hasPanelEvidenceTime(panel);
    return hasObservationIdentity && (panel.status === 'success' || panel.items.length > 0);
  }
  if (panel.status === 'unavailable') {
    return explicitlyUnavailable;
  }
  return Boolean(
    explicitlyUnavailable
    || hasText(panel.errorMessage)
    || hasText(panel.refreshError)
    || hasText(panel.lastError)
    || (truth.source.class === 'fallback' && truth.freshness === 'fallback'),
  );
}

export function assertMarketOverviewPanelContract(value: unknown): MarketOverviewPanel {
  if (!isMarketOverviewPanelContract(value)) {
    throw new Error('invalid_market_overview_contract');
  }
  return value;
}

function normalizePanel(payload: unknown): MarketOverviewPanel {
  if (!isRecord(payload)) {
    throw new Error('invalid_market_overview_contract');
  }
  const normalized = toCamelCase<Record<string, unknown>>(payload) as unknown as MarketOverviewPanel;
  if (!Array.isArray(normalized.items)) {
    throw new Error('invalid_market_overview_contract');
  }
  const panel: MarketOverviewPanel = {
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
    updatedAt: normalized.updatedAt,
    observedAt: normalized.observedAt,
    marketTime: normalized.marketTime,
    providerTime: normalized.providerTime,
    receivedAt: normalized.receivedAt,
    generatedAt: normalized.generatedAt,
    asOf: normalized.asOf,
    expiresAt: normalized.expiresAt,
    freshness: normalized.freshness,
    isProxy: normalized.isProxy,
    isFallback: normalized.isFallback,
    isSynthetic: normalized.isSynthetic,
    isFixture: normalized.isFixture,
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
    sourceClass: normalized.sourceClass,
    trustLevel: normalized.trustLevel,
    sourceConfidence: normalized.sourceConfidence,
    observationOnly: normalized.observationOnly,
    decisionGrade: normalized.decisionGrade,
    readiness: normalized.readiness,
    readinessState: normalized.readinessState,
    domainReady: normalized.domainReady,
    runtimeAvailable: normalized.runtimeAvailable,
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
    items: normalized.items,
  };
  return assertMarketOverviewPanelContract(panel);
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
