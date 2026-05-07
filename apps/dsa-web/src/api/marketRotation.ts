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
  timeWindows?: Record<string, MarketRotationTimeWindow>;
  freshness: MarketDataFreshness;
  isFallback: boolean;
  isStale: boolean;
  source?: string | null;
  sourceLabel?: string | null;
  asOf?: string | null;
};

export type MarketRotationTimeWindow = {
  window: '5m' | '15m' | '60m' | '1d';
  label: string;
  available: boolean;
  changePercent?: number | null;
  relativeVolume?: number | null;
  freshness: MarketDataFreshness;
  isFallback: boolean;
  isStale: boolean;
  source?: string | null;
  sourceLabel?: string | null;
  asOf?: string | null;
  reason?: string | null;
};

export type MarketRotationMember = {
  symbol: string;
  name: string;
  observed?: boolean;
  price?: number | null;
  changePercent?: number | null;
  relativeStrengthVsBenchmark?: number | null;
  volumeRatio?: number | null;
  timeWindows?: Record<string, MarketRotationTimeWindow>;
  priceAboveVwap?: boolean | null;
  persistenceScore?: number | null;
  leadershipLabel?: string | null;
  freshnessLabel?: string | null;
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
  stageExplanation?: string | null;
  freshness: MarketDataFreshness;
  isFallback: boolean;
  riskLabels: MarketRotationRiskLabel[];
  riskExplanations?: string[];
};

export type MarketRotationTheme = MarketRotationSummaryItem & {
  englishName: string;
  focus?: string;
  benchmark: string;
  sectorBenchmark?: string | null;
  membersConfigured: string[];
  newslessRotation: boolean;
  newslessRotationEvidence?: string | null;
  stageExplanation?: string | null;
  riskExplanations?: string[];
  relativeStrength: {
    benchmark?: string;
    benchmarkChangePercent?: number | null;
    averageThemeChangePercent?: number | null;
    averageRelativeStrengthPercent?: number | null;
    vsBenchmarks?: Record<string, number | null>;
  };
  benchmarkProxies?: Record<string, {
    symbol: string;
    role?: 'market_proxy' | 'sector_proxy' | string;
    changePercent?: number | null;
    relativeStrength?: number | null;
    timeWindows?: Record<string, MarketRotationTimeWindow>;
    freshness?: MarketDataFreshness;
    isFallback?: boolean;
    isStale?: boolean;
    sourceLabel?: string | null;
    asOf?: string | null;
  }>;
  timeWindows?: Record<string, MarketRotationTimeWindow>;
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
      roleLabel?: string | null;
      freshnessLabel?: string | null;
      freshness?: MarketDataFreshness;
      isFallback?: boolean;
    }>;
  };
  themeDetail?: {
    watchlistLabel?: string;
    watchlistSafe?: boolean;
    safeActionLabel?: string;
    leadershipMembers?: MarketRotationWatchlistMember[];
    laggardMembers?: MarketRotationWatchlistMember[];
    memberEvidence?: MarketRotationWatchlistMember[];
    freshnessLabel?: string;
    asOf?: string | null;
    disclosure?: string;
    notes?: string[];
  };
  source?: string;
  sourceLabel?: string | null;
  asOf?: string | null;
  updatedAt?: string | null;
  evidence: string[];
  members: MarketRotationMember[];
  noAdviceDisclosure: string;
};

export type MarketRotationWatchlistMember = {
  symbol?: string;
  name?: string;
  role?: string;
  roleLabel?: string;
  changePercent?: number | null;
  relativeStrengthVsBenchmark?: number | null;
  volumeRatio?: number | null;
  freshness?: MarketDataFreshness;
  freshnessLabel?: string;
  observed?: boolean;
  notes?: string[];
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

function normalizeTimeWindows(windows?: Record<string, MarketRotationTimeWindow> | null): Record<string, MarketRotationTimeWindow> {
  if (!windows || typeof windows !== 'object') {
    return {};
  }
  return Object.values(windows).reduce<Record<string, MarketRotationTimeWindow>>((acc, window) => {
    if (window?.window) {
      acc[window.window] = window;
    }
    return acc;
  }, {});
}

function normalizeTheme(theme: MarketRotationTheme): MarketRotationTheme {
  const benchmarkProxies = Object.entries(theme.benchmarkProxies || {}).reduce<NonNullable<MarketRotationTheme['benchmarkProxies']>>(
    (acc, [symbol, proxy]) => {
      const proxySymbol = proxy.symbol || symbol;
      acc[proxySymbol] = {
        ...proxy,
        timeWindows: normalizeTimeWindows(proxy.timeWindows),
      };
      return acc;
    },
    {},
  );
  return {
    ...theme,
    timeWindows: normalizeTimeWindows(theme.timeWindows),
    benchmarkProxies,
    members: Array.isArray(theme.members)
      ? theme.members.map((member) => ({ ...member, timeWindows: normalizeTimeWindows(member.timeWindows) }))
      : [],
  };
}

function normalizeBenchmark(benchmark: MarketRotationBenchmark): MarketRotationBenchmark {
  return {
    ...benchmark,
    timeWindows: normalizeTimeWindows(benchmark.timeWindows),
  };
}

export const marketRotationApi = {
  getRotationRadar: async (): Promise<MarketRotationRadarResponse> => {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/market/rotation-radar');
    const normalized = toCamelCase<MarketRotationRadarResponse>(response.data);
    const benchmarks = Object.entries(normalized.benchmarks || {}).reduce<Record<string, MarketRotationBenchmark>>(
      (acc, [symbol, benchmark]) => {
        acc[symbol] = normalizeBenchmark(benchmark);
        return acc;
      },
      {},
    );
    return {
      ...normalized,
      themes: Array.isArray(normalized.themes) ? normalized.themes.map(normalizeTheme) : [],
      benchmarks,
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
