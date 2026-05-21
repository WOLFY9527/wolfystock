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
  routerReasonCodes?: string[];
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
};
