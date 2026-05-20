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

export interface LiquidityImpulseSynthesisEvidenceItem {
  key: string;
  label?: string | null;
  pillar?: string | null;
  direction?: string | null;
  signal?: number | null;
  weight?: number | null;
  impact?: number | null;
  expectedDirection?: string | null;
  reason?: string | null;
  source?: string | null;
  sourceTier?: string | null;
  trustLevel?: string | null;
  freshness?: string | null;
  observationOnly?: boolean;
  scoreContributionAllowed?: boolean;
  includedInScore?: boolean;
  proxyOnly?: boolean;
  discountReasons?: string[];
  degradationReason?: string | null;
}

export interface LiquidityImpulseSynthesis {
  liquidityImpulse: string;
  impulseLabel: string;
  subtype: string;
  confidence: number;
  confidenceLabel: string;
  pillarScores: Record<string, number>;
  directionScore: number;
  dominantDrivers: LiquidityImpulseSynthesisEvidenceItem[];
  counterEvidence: LiquidityImpulseSynthesisEvidenceItem[];
  dataGaps: LiquidityImpulseSynthesisEvidenceItem[];
  narrativeBullets: string[];
  evidenceQuality: Record<string, unknown>;
  notInvestmentAdvice: boolean;
}

export interface LiquidityMonitorResponse {
  endpoint: string;
  generatedAt: string;
  score: LiquidityMonitorScore;
  freshness: LiquidityMonitorFreshnessSummary;
  indicators: LiquidityMonitorIndicator[];
  liquidityImpulseSynthesis?: LiquidityImpulseSynthesis;
  advisoryDisclosure: string;
  sourceMetadata: LiquidityMonitorSourceMetadata;
}

function normalizeLiquidityImpulseEvidenceItem(
  item?: Partial<LiquidityImpulseSynthesisEvidenceItem> | null,
): LiquidityImpulseSynthesisEvidenceItem | null {
  if (!item?.key) {
    return null;
  }

  return {
    key: item.key,
    label: item.label,
    pillar: item.pillar,
    direction: item.direction,
    signal: item.signal,
    weight: item.weight,
    impact: item.impact,
    expectedDirection: item.expectedDirection,
    reason: item.reason,
    source: item.source,
    sourceTier: item.sourceTier,
    trustLevel: item.trustLevel,
    freshness: item.freshness,
    observationOnly: item.observationOnly,
    scoreContributionAllowed: item.scoreContributionAllowed,
    includedInScore: item.includedInScore,
    proxyOnly: item.proxyOnly,
    discountReasons: Array.isArray(item.discountReasons) ? item.discountReasons.filter(Boolean) : [],
    degradationReason: item.degradationReason,
  };
}

function normalizeLiquidityImpulseSynthesis(
  synthesis?: Partial<LiquidityImpulseSynthesis> | null,
): LiquidityImpulseSynthesis | undefined {
  if (!synthesis?.liquidityImpulse || !synthesis.impulseLabel || !synthesis.subtype || !synthesis.confidenceLabel) {
    return undefined;
  }

  const normalizeEvidenceList = (
    items?: Array<Partial<LiquidityImpulseSynthesisEvidenceItem> | null>,
  ): LiquidityImpulseSynthesisEvidenceItem[] => (
    Array.isArray(items)
      ? items
        .map((item) => normalizeLiquidityImpulseEvidenceItem(item))
        .filter((item): item is LiquidityImpulseSynthesisEvidenceItem => Boolean(item))
      : []
  );

  return {
    liquidityImpulse: synthesis.liquidityImpulse,
    impulseLabel: synthesis.impulseLabel,
    subtype: synthesis.subtype,
    confidence: typeof synthesis.confidence === 'number' ? synthesis.confidence : 0,
    confidenceLabel: synthesis.confidenceLabel,
    pillarScores: synthesis.pillarScores || {},
    directionScore: typeof synthesis.directionScore === 'number' ? synthesis.directionScore : 0,
    dominantDrivers: normalizeEvidenceList(synthesis.dominantDrivers),
    counterEvidence: normalizeEvidenceList(synthesis.counterEvidence),
    dataGaps: normalizeEvidenceList(synthesis.dataGaps),
    narrativeBullets: Array.isArray(synthesis.narrativeBullets) ? synthesis.narrativeBullets.filter(Boolean) : [],
    evidenceQuality: synthesis.evidenceQuality || {},
    notInvestmentAdvice: synthesis.notInvestmentAdvice !== false,
  };
}

function normalizeLiquidityMonitor(payload: Record<string, unknown>): LiquidityMonitorResponse {
  const normalized = toCamelCase<LiquidityMonitorResponse>(payload);
  return {
    endpoint: normalized.endpoint,
    generatedAt: normalized.generatedAt,
    score: normalized.score,
    freshness: normalized.freshness,
    indicators: Array.isArray(normalized.indicators) ? normalized.indicators : [],
    liquidityImpulseSynthesis: normalizeLiquidityImpulseSynthesis(normalized.liquidityImpulseSynthesis),
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
