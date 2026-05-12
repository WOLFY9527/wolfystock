import apiClient from './index';
import { toCamelCase } from './utils';

export type LiquidityMonitorFreshness = 'live' | 'cached' | 'delayed' | 'stale' | 'fallback' | 'mock' | 'error' | 'unavailable';
export type LiquidityMonitorRegime = 'abundant' | 'supportive' | 'neutral' | 'tight' | 'stress' | 'unavailable';
export type LiquidityMonitorIndicatorStatus = 'live' | 'partial' | 'unavailable';

export interface LiquidityMonitorScore {
  value: number;
  regime: LiquidityMonitorRegime;
  confidence: number;
  includedIndicatorCount: number;
  possibleIndicatorWeight: number;
  includedIndicatorWeight: number;
}

export interface LiquidityMonitorFreshnessSummary {
  status: LiquidityMonitorFreshness;
  weakestIndicatorFreshness: LiquidityMonitorFreshness;
  latestAsOf?: string | null;
}

export interface LiquidityMonitorIndicator {
  key: string;
  label: string;
  status: LiquidityMonitorIndicatorStatus;
  freshness: LiquidityMonitorFreshness;
  includedInScore: boolean;
  scoreContribution: number;
  scoreWeight: number;
  summary?: string | null;
  updatedAt?: string | null;
}

export interface LiquidityMonitorSourceMetadata {
  externalProviderCalls: boolean;
  providerRuntimeChanged: boolean;
  marketCacheMutation: boolean;
}

export interface LiquidityMonitorResponse {
  endpoint: string;
  generatedAt: string;
  score: LiquidityMonitorScore;
  freshness: LiquidityMonitorFreshnessSummary;
  indicators: LiquidityMonitorIndicator[];
  advisoryDisclosure: string;
  sourceMetadata: LiquidityMonitorSourceMetadata;
}

function normalizeLiquidityMonitor(payload: Record<string, unknown>): LiquidityMonitorResponse {
  const normalized = toCamelCase<LiquidityMonitorResponse>(payload);
  return {
    endpoint: normalized.endpoint,
    generatedAt: normalized.generatedAt,
    score: normalized.score,
    freshness: normalized.freshness,
    indicators: Array.isArray(normalized.indicators) ? normalized.indicators : [],
    advisoryDisclosure: normalized.advisoryDisclosure,
    sourceMetadata: normalized.sourceMetadata,
  };
}

export const liquidityMonitorApi = {
  async getLiquidityMonitor(): Promise<LiquidityMonitorResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/market/liquidity-monitor');
    return normalizeLiquidityMonitor(response.data);
  },
};
