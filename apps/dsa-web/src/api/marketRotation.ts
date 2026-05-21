import apiClient from './index';
import { toCamelCase } from './utils';
import type { MarketDataFreshness } from './marketOverview';

export type MarketRotationStage =
  | 'early_watch'
  | 'confirmed_rotation'
  | 'extended_watch'
  | 'cooling_watch'
  | 'weak_or_no_signal';

export type MarketRotationSignalType =
  | 'real_flow'
  | 'relative_strength'
  | 'momentum_proxy'
  | 'observation_only'
  | 'taxonomy_fallback'
  | 'insufficient_evidence';

export type MarketRotationEvidenceQuality =
  | 'score_grade_proxy'
  | 'degraded_proxy'
  | 'observation_only'
  | 'taxonomy_only'
  | 'insufficient'
  | 'score_grade_real_flow';

export type MarketRotationRiskLabel =
  | 'gap_fade_risk'
  | 'thin_breadth'
  | 'single_name_driven'
  | 'stale_or_incomplete_windows';

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
  rankEligible?: boolean;
  rankExclusionReason?: string | null;
  taxonomyOnly?: boolean;
  observationOnly?: boolean;
  headlineEligible?: boolean;
  rankingLane?: 'headline' | 'observation' | 'taxonomy';
  scoreContributionAllowed?: boolean;
  signalType?: MarketRotationSignalType;
  flowEvidenceType?: string;
  flowLanguageAllowed?: boolean;
  sourceAuthorityAllowed?: boolean;
  evidenceQuality?: MarketRotationEvidenceQuality | string;
  dataGaps?: string[];
  sourceTier?: string | null;
  trustLevel?: string | null;
};

export type MarketRotationAlertCandidate = {
  themeId?: string;
  themeName?: string;
  symbol?: string;
  name?: string;
  label?: string;
  signal?: MarketRotationStage;
  signalLabel?: string;
  confidence?: number;
  persistenceScore?: number | null;
  persistenceLabel?: string | null;
  riskLabels?: MarketRotationRiskLabel[];
  reasons?: string[];
  sortKey?: {
    confidence?: number;
    persistenceScore?: number | null;
    relativeStrengthVsBenchmark?: number | null;
    volumeRatio?: number | null;
  };
  sortExplanation?: string;
  readOnly?: boolean;
  deliveryEnabled?: boolean;
  noAdviceDisclosure?: string;
};

export type MarketRotationProxyQuality = {
  label?: string;
  coveragePercent?: number;
  availableProxyCount?: number;
  totalProxyCount?: number;
  requiredProxies?: string[];
  freshness?: MarketDataFreshness;
  hasMissingRequiredProxy?: boolean;
  hasStaleProxy?: boolean;
  missingReasons?: Record<string, string>;
  explanation?: string;
};

export type MarketRotationProxyStatus = {
  symbol?: string;
  available?: boolean;
  freshness?: MarketDataFreshness;
  isFallback?: boolean;
  isStale?: boolean;
  hasRequiredWindows?: boolean;
  missingReason?: string | null;
  qualityLabel?: string;
  coverageContribution?: number;
};

export type MarketRotationEtfLeadershipEvidence = {
  symbol?: string;
  sourceLabel?: string | null;
  sourceTier?: string | null;
  trustLevel?: string | null;
  freshness?: MarketDataFreshness;
  asOf?: string | null;
  sourceAuthorityAllowed?: boolean;
  scoreContributionAllowed?: boolean;
  reasonCodes?: string[];
  [key: string]: unknown;
};

export type MarketRotationEtfLeadershipDiagnostics = {
  enabled: boolean;
  source?: string | null;
  asOf?: string | null;
  eligibleSymbols: string[];
  leadingSymbols: string[];
  laggingSymbols: string[];
  leadershipSpread?: number | null;
  confidenceLabel?: string | null;
  reasonCodes: string[];
  evidence: MarketRotationEtfLeadershipEvidence[];
};

export type MarketRotationTheme = MarketRotationSummaryItem & {
  rotationStateEvidence?: Record<string, unknown> | null;
  market?: string;
  taxonomyType?: string;
  englishName: string;
  focus?: string;
  benchmark: string;
  sectorBenchmark?: string | null;
  membersConfigured: string[];
  representativeLabels?: string[];
  representativeSymbols?: string[];
  proxySymbols?: string[];
  mappedConcepts?: string[];
  aliases?: string[];
  confidenceLabel?: string;
  dataQuality?: string;
  dataCoverage?: string;
  sourceClass?: string;
  staticThemeOnly?: boolean;
  newslessRotation: boolean;
  newslessRotationEvidence?: string | null;
  persistenceScore?: number | null;
  persistenceEvidence?: {
    score?: number;
    label?: string;
    availableWindows?: string[];
    missingWindows?: string[];
    staleOrFallbackWindows?: string[];
    positiveWindowCount?: number;
    negativeWindowCount?: number;
    sameDirectionWindowCount?: number;
    requiredWindows?: string[];
    explanation?: string;
  };
  alertCandidates?: MarketRotationAlertCandidate[];
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
    quality?: MarketRotationProxyStatus;
  }>;
  proxyQuality?: MarketRotationProxyQuality;
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
    leaderSectionLabel?: string;
    laggardSectionLabel?: string;
    leaderExplanation?: string;
    laggardExplanation?: string;
    leadershipMembers?: MarketRotationWatchlistMember[];
    laggardMembers?: MarketRotationWatchlistMember[];
    memberEvidence?: MarketRotationWatchlistMember[];
    freshnessLabel?: string;
    asOf?: string | null;
    disclosure?: string;
    notes?: string[];
    mappedConcepts?: string[];
    representativeLabels?: string[];
    dataStateLabel?: string;
    nextStep?: string;
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
  market?: string;
  supportedMarkets?: string[];
  generatedAt: string;
  source: string;
  sourceLabel?: string | null;
  freshness: MarketDataFreshness;
  isFallback: boolean;
  isStale: boolean;
  warning?: string | null;
  noAdviceDisclosure: string;
  benchmarks: Record<string, MarketRotationBenchmark>;
  etfLeadershipDiagnostics: MarketRotationEtfLeadershipDiagnostics;
  summary: {
    strongestThemes: MarketRotationSummaryItem[];
    acceleratingThemes: MarketRotationSummaryItem[];
    fadingThemes: MarketRotationSummaryItem[];
    observationThemes?: MarketRotationSummaryItem[];
    taxonomyThemes?: MarketRotationSummaryItem[];
    eligibleThemeCount?: number;
    headlineEligibleThemeCount?: number;
    observationThemeCount?: number;
    headlineWarning?: string | null;
    noHeadlineReason?: string | null;
    rankingPolicy?: string | null;
    watchlistSignals: MarketRotationAlertCandidate[];
    watchlistSortingExplanation?: string | null;
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

function normalizeEtfLeadershipDiagnostics(
  diagnostics?: MarketRotationEtfLeadershipDiagnostics | null,
): MarketRotationEtfLeadershipDiagnostics {
  return {
    enabled: diagnostics?.enabled === true,
    source: diagnostics?.source || null,
    asOf: diagnostics?.asOf || null,
    eligibleSymbols: Array.isArray(diagnostics?.eligibleSymbols) ? diagnostics.eligibleSymbols : [],
    leadingSymbols: Array.isArray(diagnostics?.leadingSymbols) ? diagnostics.leadingSymbols : [],
    laggingSymbols: Array.isArray(diagnostics?.laggingSymbols) ? diagnostics.laggingSymbols : [],
    leadershipSpread: typeof diagnostics?.leadershipSpread === 'number' ? diagnostics.leadershipSpread : null,
    confidenceLabel: diagnostics?.confidenceLabel || null,
    reasonCodes: Array.isArray(diagnostics?.reasonCodes) ? diagnostics.reasonCodes : [],
    evidence: Array.isArray(diagnostics?.evidence)
      ? diagnostics.evidence.map((row) => ({
        ...row,
        reasonCodes: Array.isArray(row.reasonCodes) ? row.reasonCodes : [],
      }))
      : [],
  };
}

export const marketRotationApi = {
  getRotationRadar: async (market?: string): Promise<MarketRotationRadarResponse> => {
    const response = market
      ? await apiClient.get<Record<string, unknown>>('/api/v1/market/rotation-radar', { params: { market } })
      : await apiClient.get<Record<string, unknown>>('/api/v1/market/rotation-radar');
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
      etfLeadershipDiagnostics: normalizeEtfLeadershipDiagnostics(normalized.etfLeadershipDiagnostics),
      summary: {
        strongestThemes: normalized.summary?.strongestThemes || [],
        acceleratingThemes: normalized.summary?.acceleratingThemes || [],
        fadingThemes: normalized.summary?.fadingThemes || [],
        observationThemes: normalized.summary?.observationThemes,
        taxonomyThemes: normalized.summary?.taxonomyThemes,
        eligibleThemeCount: normalized.summary?.eligibleThemeCount,
        headlineEligibleThemeCount: normalized.summary?.headlineEligibleThemeCount,
        observationThemeCount: normalized.summary?.observationThemeCount,
        headlineWarning: normalized.summary?.headlineWarning,
        noHeadlineReason: normalized.summary?.noHeadlineReason,
        rankingPolicy: normalized.summary?.rankingPolicy,
        watchlistSignals: normalized.summary?.watchlistSignals || [],
        watchlistSortingExplanation: normalized.summary?.watchlistSortingExplanation || null,
        safeWording: normalized.summary?.safeWording || [],
      },
      metadata: normalized.metadata || {},
    };
  },
};
