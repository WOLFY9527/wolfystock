import apiClient from './index';
import { toCamelCase } from './utils';

export type AdminCostWindowKey = '15m' | '1h' | '24h' | '7d';
export type AdminCostBucket = 'hour' | 'day';
export type AdminCostArea = 'all' | 'llm' | 'provider' | 'market-cache' | 'scanner-ai';

export interface AdminCostSummaryParams {
  window?: AdminCostWindowKey;
  bucket?: AdminCostBucket;
  area?: AdminCostArea;
  limit?: number;
}

export interface AdminCostWindow {
  key: string;
  from: string;
  to: string;
  bucket: AdminCostBucket | string;
  historical: boolean;
}

export interface AdminCostOverview {
  llmCalls: number;
  llmUsageCalls: number;
  llmUsageTokens: number;
  estimatedDuplicateCandidates: number;
  providerCalls: number;
  providerCacheHits: number;
  providerCacheMisses: number;
  providerInflightJoins: number;
  providerCacheHitRate?: number | null;
  marketCacheHits: number;
  marketCacheMisses: number;
  marketCacheStaleServed: number;
  marketCacheColdFallbacks: number;
  marketCacheHitRate?: number | null;
  fallbackAttempts: number;
  integrityRetries: number;
  scannerAiAttempts: number;
  scannerAiCompleted: number;
  scannerAiSkipped: number;
}

export interface AdminCostRollup {
  group: string;
  count: number;
  eventCounts: Record<string, number>;
  dimensions: Record<string, string>;
}

export interface AdminCostCacheEfficiency {
  group: string;
  hits: number;
  misses: number;
  inflightJoins: number;
  hitRate?: number | null;
  dimensions: Record<string, string>;
}

export interface AdminCostLlmSection {
  byCallType: AdminCostRollup[];
  duplicateCandidates: AdminCostRollup[];
  fallbacks: AdminCostRollup[];
  integrityRetries: AdminCostRollup[];
  usageByCallType: AdminCostRollup[];
  usageByModel: AdminCostRollup[];
}

export interface AdminCostProviderSection {
  byCategory: AdminCostRollup[];
  fallbackDepth: AdminCostRollup[];
  cacheEfficiency: AdminCostCacheEfficiency[];
  duplicateCandidates: AdminCostRollup[];
}

export interface AdminCostMarketCacheSection {
  byPanelKey: AdminCostRollup[];
  staleServed: AdminCostRollup[];
  coldFallbacks: AdminCostRollup[];
  refreshes: AdminCostRollup[];
}

export interface AdminCostScannerAiSection {
  interpretations: AdminCostRollup[];
  duplicateCandidates: AdminCostRollup[];
  skips: AdminCostRollup[];
}

export interface AdminCostLimitation {
  code: string;
  message: string;
  severity: 'info' | 'warning' | string;
}

export interface AdminCostMetadata {
  readOnly: boolean;
  noExternalCalls: boolean;
  countersSource: string;
  exactness: 'observational_not_billing' | string;
  dataSources: string[];
  unsupportedSources: string[];
  redaction: string[];
  requestedArea: string;
  limit: number;
  notes: Record<string, unknown>;
}

export interface AdminCostSummaryResponse {
  generatedAt: string;
  window: AdminCostWindow;
  summary: AdminCostOverview;
  llm: AdminCostLlmSection;
  providers: AdminCostProviderSection;
  marketCache: AdminCostMarketCacheSection;
  scannerAi: AdminCostScannerAiSection;
  limitations: AdminCostLimitation[];
  metadata: AdminCostMetadata;
}

const EMPTY_OVERVIEW: AdminCostOverview = {
  llmCalls: 0,
  llmUsageCalls: 0,
  llmUsageTokens: 0,
  estimatedDuplicateCandidates: 0,
  providerCalls: 0,
  providerCacheHits: 0,
  providerCacheMisses: 0,
  providerInflightJoins: 0,
  providerCacheHitRate: null,
  marketCacheHits: 0,
  marketCacheMisses: 0,
  marketCacheStaleServed: 0,
  marketCacheColdFallbacks: 0,
  marketCacheHitRate: null,
  fallbackAttempts: 0,
  integrityRetries: 0,
  scannerAiAttempts: 0,
  scannerAiCompleted: 0,
  scannerAiSkipped: 0,
};

function safeArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? value as T[] : [];
}

function toSafeQuery(params: AdminCostSummaryParams): Record<string, unknown> {
  return {
    window: params.window || '24h',
    bucket: params.bucket || 'hour',
    area: params.area || 'all',
    limit: Math.min(Math.max(Number(params.limit || 50), 1), 200),
  };
}

function normalizeSummary(payload: Record<string, unknown>): AdminCostSummaryResponse {
  const normalized = toCamelCase<AdminCostSummaryResponse>(payload);
  return {
    generatedAt: normalized.generatedAt || '',
    window: normalized.window || { key: '24h', from: '', to: '', bucket: 'hour', historical: false },
    summary: { ...EMPTY_OVERVIEW, ...(normalized.summary || {}) },
    llm: {
      byCallType: safeArray<AdminCostRollup>(normalized.llm?.byCallType),
      duplicateCandidates: safeArray<AdminCostRollup>(normalized.llm?.duplicateCandidates),
      fallbacks: safeArray<AdminCostRollup>(normalized.llm?.fallbacks),
      integrityRetries: safeArray<AdminCostRollup>(normalized.llm?.integrityRetries),
      usageByCallType: safeArray<AdminCostRollup>(normalized.llm?.usageByCallType),
      usageByModel: safeArray<AdminCostRollup>(normalized.llm?.usageByModel),
    },
    providers: {
      byCategory: safeArray<AdminCostRollup>(normalized.providers?.byCategory),
      fallbackDepth: safeArray<AdminCostRollup>(normalized.providers?.fallbackDepth),
      cacheEfficiency: safeArray<AdminCostCacheEfficiency>(normalized.providers?.cacheEfficiency),
      duplicateCandidates: safeArray<AdminCostRollup>(normalized.providers?.duplicateCandidates),
    },
    marketCache: {
      byPanelKey: safeArray<AdminCostRollup>(normalized.marketCache?.byPanelKey),
      staleServed: safeArray<AdminCostRollup>(normalized.marketCache?.staleServed),
      coldFallbacks: safeArray<AdminCostRollup>(normalized.marketCache?.coldFallbacks),
      refreshes: safeArray<AdminCostRollup>(normalized.marketCache?.refreshes),
    },
    scannerAi: {
      interpretations: safeArray<AdminCostRollup>(normalized.scannerAi?.interpretations),
      duplicateCandidates: safeArray<AdminCostRollup>(normalized.scannerAi?.duplicateCandidates),
      skips: safeArray<AdminCostRollup>(normalized.scannerAi?.skips),
    },
    limitations: safeArray<AdminCostLimitation>(normalized.limitations),
    metadata: {
      readOnly: normalized.metadata?.readOnly === true,
      noExternalCalls: normalized.metadata?.noExternalCalls === true,
      countersSource: normalized.metadata?.countersSource || 'unknown',
      exactness: normalized.metadata?.exactness || 'observational_not_billing',
      dataSources: safeArray<string>(normalized.metadata?.dataSources),
      unsupportedSources: safeArray<string>(normalized.metadata?.unsupportedSources),
      redaction: safeArray<string>(normalized.metadata?.redaction),
      requestedArea: normalized.metadata?.requestedArea || 'all',
      limit: Number(normalized.metadata?.limit || 50),
      notes: {},
    },
  };
}

export const adminCostApi = {
  async getDuplicateSummary(params: AdminCostSummaryParams = {}): Promise<AdminCostSummaryResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/admin/cost/duplicate-summary', {
      params: toSafeQuery(params),
    });
    return normalizeSummary(response.data);
  },
};
