import apiClient from './index';
import { toCamelCase } from './utils';

export interface ProviderCircuitDiagnosticsParams {
  provider?: string;
  routeFamily?: string;
  state?: string;
  eventType?: string;
  since?: string;
  limit?: number;
}

export interface ProviderCircuitDiagnosticsMetadata {
  readOnly: boolean;
  noExternalCalls: boolean;
  liveEnforcement: boolean;
  providerBehaviorChanged: boolean;
  marketCacheBehaviorChanged: boolean;
  dataSources: string[];
  limit: number;
  redaction: string[];
  filters: Record<string, unknown>;
}

export interface ProviderCircuitStateItem {
  provider: string;
  providerCategory?: string | null;
  routeFamily?: string | null;
  state: string;
  reasonBucket?: string | null;
  cooldownUntil?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface ProviderCircuitEventItem {
  provider: string;
  providerCategory?: string | null;
  routeFamily?: string | null;
  eventType: string;
  fromState?: string | null;
  toState?: string | null;
  reasonBucket?: string | null;
  requestCountBucket?: string | null;
  durationBucketMs?: number | null;
  failureCountBucket?: string | null;
  createdAt?: string | null;
}

export interface ProviderQuotaWindowItem {
  provider: string;
  providerCategory?: string | null;
  routeFamily?: string | null;
  windowType: string;
  windowStart: string;
  windowEnd: string;
  requestCount: number;
  reservedUnits: number;
  consumedUnits: number;
  releasedUnits: number;
  rejectedCount: number;
  successCount: number;
  failureCount: number;
  timeoutCount: number;
  provider429Count: number;
  provider403Count: number;
  fallbackCount: number;
  probeCount: number;
  cacheOnlyCount: number;
  staleServedCount: number;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface ProviderProbeEventItem {
  provider: string;
  providerCategory?: string | null;
  routeFamily?: string | null;
  probeType: string;
  probeSource: string;
  resultBucket: string;
  durationBucketMs?: number | null;
  createdAt?: string | null;
}

export interface ProviderRecentErrorBucketItem {
  reasonBucket: string;
  countBucket: string;
  latestAt?: string | null;
}

export interface ProviderSlaTrendSummaryItem {
  windowCountBucket: string;
  requestCountBucket: string;
  failureCountBucket: string;
  timeoutCountBucket: string;
  provider429CountBucket: string;
  provider403CountBucket: string;
  latestObservationAt?: string | null;
}

export interface ProviderSlaReadinessItem {
  provider: string;
  providerCategory?: string | null;
  routeFamily?: string | null;
  readinessState: string;
  reasonCode: string;
  credentialState: string;
  liveProvidersEnabled: boolean;
  providerEnabled: boolean;
  credentialsPresent: boolean;
  dryRunEnabled: boolean;
  liveHttpCallsEnabled: boolean;
  brokerOrderPathEnabled: boolean;
  portfolioMutationPathEnabled: boolean;
  tradeableData: boolean;
  latencyBucketMs?: number | null;
  latencyState: string;
  errorRate?: number | null;
  errorState: string;
  freshnessSeconds?: number | null;
  freshnessState: string;
  recentErrors: ProviderRecentErrorBucketItem[];
  trendSummary?: ProviderSlaTrendSummaryItem;
  circuitAdvisoryState: string;
  circuitStateCandidate: string;
  liveEnforcement: boolean;
  wouldBlockCall: boolean;
  wouldChangeProviderOrder: boolean;
  wouldChangeFallbackBehavior: boolean;
  noExternalCalls: boolean;
}

export interface ProviderCircuitResponse<T> {
  generatedAt: string;
  items: T[];
  metadata: ProviderCircuitDiagnosticsMetadata;
}

export interface ProviderCircuitDiagnosticsBundle {
  states: ProviderCircuitResponse<ProviderCircuitStateItem>;
  events: ProviderCircuitResponse<ProviderCircuitEventItem>;
  quotaWindows: ProviderCircuitResponse<ProviderQuotaWindowItem>;
  probeEvents: ProviderCircuitResponse<ProviderProbeEventItem>;
  slaReadiness: ProviderCircuitResponse<ProviderSlaReadinessItem>;
}

function safeArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? value as T[] : [];
}

function safeLimit(limit?: number): number {
  const parsed = Number(limit || 50);
  if (!Number.isFinite(parsed)) return 50;
  return Math.min(Math.max(Math.trunc(parsed), 1), 200);
}

function safeLabel(value?: string): string | undefined {
  const normalized = String(value || '').trim().toLowerCase().replace(/[^a-z0-9:_-]/g, '').slice(0, 64);
  return normalized || undefined;
}

function toSafeQuery(params: ProviderCircuitDiagnosticsParams = {}, extras: Record<string, string | undefined> = {}) {
  return {
    provider: safeLabel(params.provider),
    routeFamily: safeLabel(params.routeFamily),
    since: typeof params.since === 'string' ? params.since.slice(0, 64) : undefined,
    limit: safeLimit(params.limit),
    ...extras,
  };
}

function normalizeMetadata(value?: Partial<ProviderCircuitDiagnosticsMetadata> | null): ProviderCircuitDiagnosticsMetadata {
  return {
    readOnly: value?.readOnly === true,
    noExternalCalls: value?.noExternalCalls === true,
    liveEnforcement: value?.liveEnforcement === true,
    providerBehaviorChanged: value?.providerBehaviorChanged === true,
    marketCacheBehaviorChanged: value?.marketCacheBehaviorChanged === true,
    dataSources: safeArray<string>(value?.dataSources),
    limit: Number(value?.limit || 50),
    redaction: safeArray<string>(value?.redaction),
    filters: value?.filters || {},
  };
}

function normalizeResponse<T>(payload: Record<string, unknown>): ProviderCircuitResponse<T> {
  const normalized = toCamelCase<ProviderCircuitResponse<T>>(payload);
  return {
    generatedAt: normalized.generatedAt || '',
    items: safeArray<T>(normalized.items),
    metadata: normalizeMetadata(normalized.metadata),
  };
}

export const adminProviderCircuitsApi = {
  async getStates(params: ProviderCircuitDiagnosticsParams = {}): Promise<ProviderCircuitResponse<ProviderCircuitStateItem>> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/admin/providers/circuits', {
      params: toSafeQuery(params, { state: safeLabel(params.state) }),
    });
    return normalizeResponse<ProviderCircuitStateItem>(response.data);
  },

  async getEvents(params: ProviderCircuitDiagnosticsParams = {}): Promise<ProviderCircuitResponse<ProviderCircuitEventItem>> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/admin/providers/circuits/events', {
      params: toSafeQuery(params, { eventType: safeLabel(params.eventType) }),
    });
    return normalizeResponse<ProviderCircuitEventItem>(response.data);
  },

  async getQuotaWindows(params: ProviderCircuitDiagnosticsParams = {}): Promise<ProviderCircuitResponse<ProviderQuotaWindowItem>> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/admin/providers/quota-windows', {
      params: toSafeQuery(params),
    });
    return normalizeResponse<ProviderQuotaWindowItem>(response.data);
  },

  async getProbeEvents(params: ProviderCircuitDiagnosticsParams = {}): Promise<ProviderCircuitResponse<ProviderProbeEventItem>> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/admin/providers/probe-events', {
      params: toSafeQuery(params),
    });
    return normalizeResponse<ProviderProbeEventItem>(response.data);
  },

  async getSlaReadiness(params: ProviderCircuitDiagnosticsParams = {}): Promise<ProviderCircuitResponse<ProviderSlaReadinessItem>> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/admin/providers/sla-readiness', {
      params: toSafeQuery(params),
    });
    return normalizeResponse<ProviderSlaReadinessItem>(response.data);
  },

  async getDiagnostics(params: ProviderCircuitDiagnosticsParams = {}): Promise<ProviderCircuitDiagnosticsBundle> {
    const [states, events, quotaWindows, probeEvents, slaReadiness] = await Promise.all([
      adminProviderCircuitsApi.getStates(params),
      adminProviderCircuitsApi.getEvents(params),
      adminProviderCircuitsApi.getQuotaWindows(params),
      adminProviderCircuitsApi.getProbeEvents(params),
      adminProviderCircuitsApi.getSlaReadiness(params),
    ]);
    return { states, events, quotaWindows, probeEvents, slaReadiness };
  },
};
