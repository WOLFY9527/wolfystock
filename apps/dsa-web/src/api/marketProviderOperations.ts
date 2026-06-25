import apiClient from './index';
import { toCamelCase } from './utils';
import type { MarketProviderHealthStatus } from './marketOverview';

export interface AdminLogDrillThrough {
  label: string;
  route: string;
  query: Record<string, string>;
  eventId?: string | null;
}

export interface MarketProviderOperationsWindow {
  key: string;
  since?: string | null;
}

export interface MarketProviderOperationsSummary {
  totalItems: number;
  liveCount: number;
  cacheCount: number;
  staleCount: number;
  fallbackCount: number;
  partialCount: number;
  unavailableCount: number;
  errorCount: number;
  refreshingCount: number;
  eventCount: number;
  failureCount: number;
  fallbackEventCount: number;
  staleEventCount: number;
  slowEventCount: number;
}

export interface MarketProviderOperationItem {
  provider: string;
  sourceLabel?: string | null;
  sourceType?: string | null;
  domain: string;
  endpoint: string;
  card: string;
  cacheKey: string;
  status: MarketProviderHealthStatus | string;
  freshness?: string | null;
  asOf?: string | null;
  updatedAt?: string | null;
  lastSuccessfulAt?: string | null;
  lastKnownGoodAgeMinutes?: number | null;
  latencyMs?: number | null;
  isFallback: boolean;
  isStale: boolean;
  isRefreshing: boolean;
  isFromSnapshot: boolean;
  fallbackUsed: boolean;
  warning?: string | null;
  errorSummary?: string | null;
  adminLogDrillThrough: AdminLogDrillThrough;
}

export interface MarketProviderEventRollup {
  provider: string;
  endpoint?: string | null;
  card?: string | null;
  category?: string | null;
  eventCount: number;
  failureCount: number;
  fallbackCount: number;
  staleServedCount: number;
  slowCount: number;
  failureRate: number;
  topReasons: string[];
  latestLogEventId?: string | null;
  latestStartedAt?: string | null;
  adminLogDrillThrough: AdminLogDrillThrough;
}

export interface MarketProviderCacheState {
  cacheKey: string;
  ttlSeconds?: number | null;
  fetchedAt?: string | null;
  expiresAt?: string | null;
  isFresh?: boolean | null;
  isRefreshing: boolean;
  lastError?: string | null;
  persistentSnapshotAvailable: boolean;
  persistentSnapshotAgeMinutes?: number | null;
  status: MarketProviderHealthStatus | string;
}

export interface MarketProviderOperationsResponse {
  generatedAt: string;
  window: MarketProviderOperationsWindow;
  summary: MarketProviderOperationsSummary;
  items: MarketProviderOperationItem[];
  eventRollups: MarketProviderEventRollup[];
  cacheStates: MarketProviderCacheState[];
  limitations: string[];
  adminLogDrillThrough: AdminLogDrillThrough;
  metadata: {
    source?: string;
    readOnly?: boolean;
    externalProviderCalls?: boolean;
    cacheMutation?: boolean;
    [key: string]: unknown;
  };
}

export interface ProviderOperationsMatrixRow {
  providerId: string;
  providerName?: string | null;
  sourceLabel?: string | null;
  providerCategory?: string | null;
  sourceType?: string | null;
  sourceTier?: string | null;
  trustLevel?: string | null;
  freshnessExpectation?: string | null;
  runtimeState?: string | null;
  credentialState?: string | null;
  dependencyState?: string | null;
  enabledByDefault?: boolean;
  observationOnly?: boolean;
  scoreContributionAllowed?: boolean;
  sourceAuthorityAllowed?: boolean;
  scoreEligible?: boolean;
  inertMetadataOnly?: boolean;
  paidDataLikelyRequired?: boolean;
  keyRequired?: boolean;
  noDefaultLiveHttpCalls?: boolean;
  cacheRequired?: boolean;
  contractCoverageUniverses?: string[];
  contractCadences?: string[];
  contractFreshnessFloors?: string[];
  contractCoverageRatioFloor?: number | null;
  requiredSourceTiers?: string[];
  scoreEligibilityGates?: string[];
  supportedCapabilities?: string[];
  affectedSurfaces?: string[];
  productAffectedSurfaces?: string[];
  routerReasonCodes?: string[];
  reasonCodes?: string[];
  fulfilledMetrics?: string[];
  missingMetrics?: string[];
  authorityBasis?: string | null;
  universe?: string | null;
  coverageCount?: number | null;
  sourceFreshnessEvidence?: {
    freshness?: string | null;
    freshnessPolicy?: string | null;
    isFallback?: boolean | null;
    isPartial?: boolean | null;
    isUnavailable?: boolean | null;
    [key: string]: unknown;
  } | null;
  officialExchangePublishedBreadth?: boolean | null;
  fullBreadthAuthority?: boolean | null;
  missingProviderReason?: string | null;
  degradationReason?: string | null;
  remediationHint?: string | null;
  diagnosticOnly?: boolean;
}

export interface ProviderOperationsMatrixSummary {
  totalRows: number;
  observationOnlyRows: number;
  inertMetadataOnlyRows: number;
  missingProviderRows: number;
  scoreEligibleRows: number;
  paidDataLikelyRequiredRows: number;
}

export interface ProviderOperationsMatrixResponse {
  generatedAt: string;
  diagnosticOnly: boolean;
  rows: ProviderOperationsMatrixRow[];
  summary: ProviderOperationsMatrixSummary;
  metadata: {
    source?: string;
    readOnly?: boolean;
    diagnosticOnly?: boolean;
    externalProviderCalls?: boolean;
    providerProbesForced?: boolean;
    networkCallsEnabled?: boolean;
    cacheMutation?: boolean;
    providerOrderChanged?: boolean;
    dataFetcherManagerChanged?: boolean;
    frontendChanged?: boolean;
    dbChanged?: boolean;
    secretValuesIncluded?: boolean;
    rawProviderPayloadsIncluded?: boolean;
    readinessStatus?: string;
    rowCount?: number;
    [key: string]: unknown;
  };
}

export interface HistoricalOhlcvCachePreflightNextAction {
  state: string;
  summary?: string | null;
  requiredConfig?: string | null;
}

export interface HistoricalOhlcvCachePreflightSymbol {
  market: string;
  symbol: string;
  runtimeState: string;
  cacheState: string;
  dependencyState?: string | null;
  dependencyAvailable?: boolean | null;
  cachedBars: number;
  latestBarDate?: string | null;
  freshnessState: string;
  adjustmentState: string;
  dataState: string;
  seedState: string;
  seedResult?: string | null;
  barsWritten?: number | null;
  latestDate?: string | null;
  freshness?: string | null;
  adjustmentStatus?: string | null;
  intendedAction?: string | null;
  nextAction: HistoricalOhlcvCachePreflightNextAction;
}

export interface HistoricalOhlcvCachePreflightMarket {
  market: string;
  runtimeEnabled: boolean;
  dependencyAvailable: boolean;
  symbols: HistoricalOhlcvCachePreflightSymbol[];
}

export interface HistoricalOhlcvActivationChecklistSymbolSet {
  label: string;
  symbols: string[];
  supported: boolean;
}

export interface HistoricalOhlcvActivationChecklistCacheSummary {
  totalSymbols: number;
  cachedSymbolCount: number;
  readySymbolCount: number;
  staleSymbolCount: number;
  missingAdjustmentCount: number;
  failedSafelyCount: number;
}

export interface HistoricalOhlcvActivationChecklistItem {
  market: string;
  label: string;
  state: string;
  runtimeEnabled: boolean;
  dependencyAvailable: boolean;
  seedEnabled: boolean;
  requiredRuntimeFlags: string[];
  seedFlag: string;
  currentRepresentativeSymbols: string[];
  recommendedFirstSymbols: string[];
  disabledReasonCodes: string[];
  cacheSummary: HistoricalOhlcvActivationChecklistCacheSummary;
  availableSeedActions: string[];
  workflowUnlocks: string[];
  currentStatusSummary: string;
  nextStepSummary: string;
}

export interface HistoricalOhlcvActivationChecklist {
  contractVersion: string;
  operatorOnly: boolean;
  readOnly: boolean;
  noExternalCalls: boolean;
  consumerVisible: boolean;
  supportedStates: string[];
  starterSymbolSets: {
    us: HistoricalOhlcvActivationChecklistSymbolSet;
    cnIfSupported: HistoricalOhlcvActivationChecklistSymbolSet;
  };
  workflowUnlocks: string[];
  items: HistoricalOhlcvActivationChecklistItem[];
}

export interface HistoricalOhlcvCachePreflightResponse {
  contractVersion: string;
  mode: string;
  dryRun: boolean;
  seedEnabled: boolean;
  networkCallsEnabled: boolean;
  mutationEnabled: boolean;
  consumerSafe: boolean;
  representativeSymbols: {
    cn: string[];
    us: string[];
  };
  activationChecklist: HistoricalOhlcvActivationChecklist;
  markets: {
    cn?: HistoricalOhlcvCachePreflightMarket;
    us?: HistoricalOhlcvCachePreflightMarket;
    [key: string]: HistoricalOhlcvCachePreflightMarket | undefined;
  };
}

export interface HistoricalOhlcvCachePreflightParams {
  cnSymbols?: string[] | string;
  usSymbols?: string[] | string;
  requiredBars?: number;
  requireAdjusted?: boolean;
}

const DEFAULT_SUMMARY: MarketProviderOperationsSummary = {
  totalItems: 0,
  liveCount: 0,
  cacheCount: 0,
  staleCount: 0,
  fallbackCount: 0,
  partialCount: 0,
  unavailableCount: 0,
  errorCount: 0,
  refreshingCount: 0,
  eventCount: 0,
  failureCount: 0,
  fallbackEventCount: 0,
  staleEventCount: 0,
  slowEventCount: 0,
};

const DEFAULT_MATRIX_SUMMARY: ProviderOperationsMatrixSummary = {
  totalRows: 0,
  observationOnlyRows: 0,
  inertMetadataOnlyRows: 0,
  missingProviderRows: 0,
  scoreEligibleRows: 0,
  paidDataLikelyRequiredRows: 0,
};

function normalizeOperations(payload: Record<string, unknown>): MarketProviderOperationsResponse {
  const normalized = toCamelCase<MarketProviderOperationsResponse>(payload);
  return {
    generatedAt: normalized.generatedAt,
    window: normalized.window || { key: '24h' },
    summary: { ...DEFAULT_SUMMARY, ...(normalized.summary || {}) },
    items: Array.isArray(normalized.items) ? normalized.items : [],
    eventRollups: Array.isArray(normalized.eventRollups) ? normalized.eventRollups : [],
    cacheStates: Array.isArray(normalized.cacheStates) ? normalized.cacheStates : [],
    limitations: Array.isArray(normalized.limitations) ? normalized.limitations : [],
    adminLogDrillThrough: normalized.adminLogDrillThrough || { label: '查看 Admin Logs', route: '/zh/admin/logs', query: {} },
    metadata: normalized.metadata || {},
  };
}

function normalizeOperationsMatrix(payload: Record<string, unknown>): ProviderOperationsMatrixResponse {
  const normalized = toCamelCase<ProviderOperationsMatrixResponse>(payload);
  return {
    generatedAt: normalized.generatedAt,
    diagnosticOnly: normalized.diagnosticOnly === true,
    rows: Array.isArray(normalized.rows) ? normalized.rows : [],
    summary: { ...DEFAULT_MATRIX_SUMMARY, ...(normalized.summary || {}) },
    metadata: normalized.metadata || {},
  };
}

function normalizeSymbolList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item || '').trim()).filter(Boolean)
    : [];
}

function normalizeChecklistSymbolSet(value: unknown, fallbackLabel: string): HistoricalOhlcvActivationChecklistSymbolSet {
  const source = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  return {
    label: String(source.label || fallbackLabel),
    symbols: normalizeSymbolList(source.symbols),
    supported: source.supported !== false,
  };
}

function normalizeChecklistItem(value: unknown): HistoricalOhlcvActivationChecklistItem {
  const item = value && typeof value === 'object' ? toCamelCase<HistoricalOhlcvActivationChecklistItem>(value as Record<string, unknown>) : {} as HistoricalOhlcvActivationChecklistItem;
  return {
    market: String(item.market || ''),
    label: String(item.label || ''),
    state: String(item.state || ''),
    runtimeEnabled: item.runtimeEnabled === true,
    dependencyAvailable: item.dependencyAvailable === true,
    seedEnabled: item.seedEnabled === true,
    requiredRuntimeFlags: normalizeSymbolList(item.requiredRuntimeFlags),
    seedFlag: String(item.seedFlag || ''),
    currentRepresentativeSymbols: normalizeSymbolList(item.currentRepresentativeSymbols),
    recommendedFirstSymbols: normalizeSymbolList(item.recommendedFirstSymbols),
    disabledReasonCodes: normalizeSymbolList(item.disabledReasonCodes),
    cacheSummary: {
      totalSymbols: Number(item.cacheSummary?.totalSymbols || 0),
      cachedSymbolCount: Number(item.cacheSummary?.cachedSymbolCount || 0),
      readySymbolCount: Number(item.cacheSummary?.readySymbolCount || 0),
      staleSymbolCount: Number(item.cacheSummary?.staleSymbolCount || 0),
      missingAdjustmentCount: Number(item.cacheSummary?.missingAdjustmentCount || 0),
      failedSafelyCount: Number(item.cacheSummary?.failedSafelyCount || 0),
    },
    availableSeedActions: normalizeSymbolList(item.availableSeedActions),
    workflowUnlocks: normalizeSymbolList(item.workflowUnlocks),
    currentStatusSummary: String(item.currentStatusSummary || ''),
    nextStepSummary: String(item.nextStepSummary || ''),
  };
}

function normalizeActivationChecklist(value: unknown): HistoricalOhlcvActivationChecklist {
  const checklist = value && typeof value === 'object' ? toCamelCase<HistoricalOhlcvActivationChecklist>(value as Record<string, unknown>) : {} as HistoricalOhlcvActivationChecklist;
  return {
    contractVersion: String(checklist.contractVersion || ''),
    operatorOnly: checklist.operatorOnly !== false,
    readOnly: checklist.readOnly !== false,
    noExternalCalls: checklist.noExternalCalls !== false,
    consumerVisible: checklist.consumerVisible === true,
    supportedStates: normalizeSymbolList(checklist.supportedStates),
    starterSymbolSets: {
      us: normalizeChecklistSymbolSet(checklist.starterSymbolSets?.us, 'US first cache activation set'),
      cnIfSupported: normalizeChecklistSymbolSet(
        checklist.starterSymbolSets?.cnIfSupported,
        'CN first cache activation set if the local CN runtime is supported',
      ),
    },
    workflowUnlocks: normalizeSymbolList(checklist.workflowUnlocks),
    items: Array.isArray(checklist.items) ? checklist.items.map((item) => normalizeChecklistItem(item)) : [],
  };
}

function normalizeHistoricalOhlcvCachePreflight(payload: Record<string, unknown>): HistoricalOhlcvCachePreflightResponse {
  const normalized = toCamelCase<HistoricalOhlcvCachePreflightResponse>(payload);
  const markets = normalized.markets || {};
  return {
    contractVersion: normalized.contractVersion || '',
    mode: normalized.mode || 'preflight',
    dryRun: normalized.dryRun !== false,
    seedEnabled: normalized.seedEnabled === true,
    networkCallsEnabled: normalized.networkCallsEnabled === true,
    mutationEnabled: normalized.mutationEnabled === true,
    consumerSafe: normalized.consumerSafe === true,
    representativeSymbols: {
      cn: normalizeSymbolList(normalized.representativeSymbols?.cn),
      us: normalizeSymbolList(normalized.representativeSymbols?.us),
    },
    activationChecklist: normalizeActivationChecklist(normalized.activationChecklist),
    markets: {
      ...markets,
      cn: markets.cn ? {
        ...markets.cn,
        symbols: Array.isArray(markets.cn.symbols) ? markets.cn.symbols : [],
      } : undefined,
      us: markets.us ? {
        ...markets.us,
        symbols: Array.isArray(markets.us.symbols) ? markets.us.symbols : [],
      } : undefined,
    },
  };
}

function encodeSymbols(value?: string[] | string): string | undefined {
  if (Array.isArray(value)) {
    const symbols = value.map((item) => String(item || '').trim()).filter(Boolean);
    return symbols.length ? symbols.join(',') : undefined;
  }
  const text = String(value || '').trim();
  return text || undefined;
}

export const marketProviderOperationsApi = {
  async getOperations(window = '24h'): Promise<MarketProviderOperationsResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/admin/market-providers/operations', {
      params: { window },
    });
    return normalizeOperations(response.data);
  },

  async getOperationsMatrix(): Promise<ProviderOperationsMatrixResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/admin/providers/operations-matrix');
    return normalizeOperationsMatrix(response.data);
  },

  async getHistoricalOhlcvCachePreflight(
    params: HistoricalOhlcvCachePreflightParams = {},
  ): Promise<HistoricalOhlcvCachePreflightResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/admin/historical-ohlcv/cache-preflight', {
      params: {
        cn_symbols: encodeSymbols(params.cnSymbols),
        us_symbols: encodeSymbols(params.usSymbols),
        required_bars: params.requiredBars,
        require_adjusted: params.requireAdjusted,
      },
    });
    return normalizeHistoricalOhlcvCachePreflight(response.data);
  },
};
