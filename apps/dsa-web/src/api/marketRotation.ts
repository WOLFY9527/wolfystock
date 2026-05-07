import apiClient from './index';
import { toCamelCase } from './utils';
import type { MarketDataFreshness } from './marketOverview';

export type MarketRotationStage =
  | 'early_rotation'
  | 'confirmed_rotation'
  | 'crowded_or_extended'
  | 'cooling'
  | 'weak_or_no_signal';

export type MarketRotationRiskLabel =
  | 'gap_fade_risk'
  | 'thin_breadth'
  | 'single_name_driven'
  | 'stale_data'
  | 'fallback_data';

export type MarketRotationBenchmark = {
  symbol: string;
  changePercent?: number | null;
  freshness: MarketDataFreshness;
  isFallback: boolean;
  isStale: boolean;
  source?: string | null;
  sourceLabel?: string | null;
  asOf?: string | null;
};

export type MarketRotationMember = {
  symbol: string;
  name: string;
  observed?: boolean;
  price?: number | null;
  changePercent?: number | null;
  relativeStrengthVsBenchmark?: number | null;
  volumeRatio?: number | null;
  priceAboveVwap?: boolean | null;
  persistenceScore?: number | null;
  freshness: MarketDataFreshness;
  isFallback: boolean;
  isStale: boolean;
  source?: string | null;
  sourceLabel?: string | null;
  asOf?: string | null;
  notes?: string[];
};

export type MarketRotationSummaryItem = {
  id: string;
  name: string;
  rotationScore: number;
  confidence: number;
  stage: MarketRotationStage;
  freshness: MarketDataFreshness;
  isFallback: boolean;
  riskLabels: MarketRotationRiskLabel[];
};

export type MarketRotationTheme = MarketRotationSummaryItem & {
  englishName: string;
  focus?: string;
  benchmark: string;
  membersConfigured: string[];
  newslessRotation: boolean;
  newslessRotationEvidence?: string | null;
  relativeStrength: {
    benchmark?: string;
    benchmarkChangePercent?: number | null;
    averageThemeChangePercent?: number | null;
    averageRelativeStrengthPercent?: number | null;
    vsBenchmarks?: Record<string, number | null>;
  };
  volume: {
    averageRelativeVolume?: number | null;
    availableMemberCount?: number;
    label?: string;
  };
  breadth: {
    observedMembers?: number;
    configuredMembers?: number;
    coveragePercent?: number;
    percentUp?: number;
    percentOutperformingBenchmark?: number;
  };
  synchronization: {
    sameDirectionPercent?: number;
    aboveVwapPercent?: number;
    persistencePercent?: number;
    label?: string;
  };
  leadership: {
    leadershipConcentrationPercent?: number;
    broadParticipationPercent?: number;
    topMembers?: Array<{
      symbol: string;
      name?: string;
      changePercent?: number | null;
      relativeStrengthVsBenchmark?: number | null;
      volumeRatio?: number | null;
      freshness?: MarketDataFreshness;
      isFallback?: boolean;
    }>;
  };
  source?: string;
  sourceLabel?: string | null;
  asOf?: string | null;
  updatedAt?: string | null;
  evidence: string[];
  members: MarketRotationMember[];
  noAdviceDisclosure: string;
};

export type MarketRotationRadarResponse = {
  endpoint: string;
  generatedAt: string;
  source: string;
  sourceLabel?: string | null;
  freshness: MarketDataFreshness;
  isFallback: boolean;
  isStale: boolean;
  warning?: string | null;
  noAdviceDisclosure: string;
  benchmarks: Record<string, MarketRotationBenchmark>;
  summary: {
    strongestThemes: MarketRotationSummaryItem[];
    acceleratingThemes: MarketRotationSummaryItem[];
    fadingThemes: MarketRotationSummaryItem[];
    safeWording: string[];
  };
  themes: MarketRotationTheme[];
  metadata: Record<string, unknown>;
};

export const marketRotationApi = {
  getRotationRadar: async (): Promise<MarketRotationRadarResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/market/rotation-radar');
    const normalized = toCamelCase<MarketRotationRadarResponse>(response.data);
    return {
      ...normalized,
      themes: Array.isArray(normalized.themes) ? normalized.themes : [],
      benchmarks: normalized.benchmarks || {},
      summary: {
        strongestThemes: normalized.summary?.strongestThemes || [],
        acceleratingThemes: normalized.summary?.acceleratingThemes || [],
        fadingThemes: normalized.summary?.fadingThemes || [],
        safeWording: normalized.summary?.safeWording || [],
      },
      metadata: normalized.metadata || {},
    };
  },
};
