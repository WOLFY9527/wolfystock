import apiClient from './index';
import { toCamelCase } from './utils';
import type { MarketDataFreshness } from './marketOverview';
import type { InvestorSignalContract } from '../types/scanner';

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
  themeFlowSignal?: InvestorSignalContract | null;
  sourceAuthorityAllowed?: boolean;
  evidenceQuality?: MarketRotationEvidenceQuality | string;
  dataGaps?: string[];
  sourceTier?: string | null;
  trustLevel?: string | null;
};

export type MarketRotationFamilyRollupItem = {
  familyId?: string;
  familyName?: string;
  themeIds?: string[];
  themeNames?: string[];
  leaderThemeIds?: string[];
  themeCount?: number;
  signalThemeCount?: number;
  averageRotationScore?: number | null;
  averageConfidence?: number | null;
  themeFlowSignal?: InvestorSignalContract | null;
};

export type MarketRotationConsumerThemeQuality = {
  id?: string;
  name?: string;
  rankEligible?: boolean;
  headlineEligible?: boolean;
  rankingLane?: string;
  observationOnly?: boolean;
  taxonomyOnly?: boolean;
  scoreContributionAllowed?: boolean;
  freshness?: string;
  isFallback?: boolean;
  isStale?: boolean;
  isPartial?: boolean;
  evidenceQuality?: string;
  dataGaps?: string[];
};

export type MarketRotationConsumerProviderState = {
  present?: boolean;
  status?: string;
  quoteMode?: string;
  sourceType?: string;
  sourceTier?: string;
  providerTier?: string;
  freshness?: string;
  asOf?: string | null;
  coverage?: {
    requestedSymbolCount?: number;
    usableSymbolCount?: number;
    coveragePercent?: number;
  };
  sourceAuthorityAllowed?: boolean;
  scoreContributionAllowed?: boolean;
  noExternalCalls?: boolean;
};

export type MarketRotationConsumerEtfProxySummary = {
  present?: boolean;
  proxyOnly?: boolean;
  label?: string;
  fundFlowAuthorityAllowed?: boolean;
  enabled?: boolean;
  source?: string | null;
  asOf?: string | null;
  eligibleSymbolCount?: number;
  leadingSymbols?: string[];
  laggingSymbols?: string[];
  reasonCodes?: string[];
};

export type MarketRotationConsumerEvidenceSnapshot = {
  market?: string;
  generatedAt?: string | null;
  asOf?: string | null;
  freshness?: string;
  isFallback?: boolean;
  isStale?: boolean;
  isPartial?: boolean;
  authorityGrant?: boolean;
  headlineEligibleThemeCount?: number;
  observationThemeCount?: number;
  taxonomyThemeCount?: number;
  scoreContributionAllowed?: boolean;
  reasonCodes?: string[];
  providerState?: MarketRotationConsumerProviderState;
  etfProxySummary?: MarketRotationConsumerEtfProxySummary;
  themes?: MarketRotationConsumerThemeQuality[];
  rotationFamilyRollup: MarketRotationFamilyRollupItem[];
};

export type MarketRotationAlpacaQuoteAuthorityReadiness = {
  providerConfigured?: boolean;
  dataFeed?: string | null;
  probeSymbols?: string[];
  quoteCoverage?: {
    covered?: number;
    total?: number;
    ratio?: number;
    missingSymbols?: string[];
  };
  freshestAsOf?: string | null;
  sourceAuthority?: 'authorized' | 'partial' | 'unavailable' | 'unknown' | string;
  fallbackUsed?: boolean;
  blockerBucket?: string | null;
  consumerSummary?: string | null;
  nextDataAction?: string | null;
  scoreContributionAllowed?: boolean;
};

export type MarketRotationAlpacaQuoteAuthorityReadinessView = {
  label: string;
  variant: 'success' | 'info' | 'caution' | 'neutral';
  chips: Array<{
    key: string;
    label: string;
    variant: 'success' | 'info' | 'caution' | 'neutral';
  }>;
  detail: string;
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

export type MarketRotationThemeCorrelationBreadthSnapshot = {
  contractVersion?: string;
  theme?: {
    id?: string | null;
    name?: string | null;
    market?: string | null;
  };
  participationState?: 'broad_group' | 'leader_concentrated' | 'mixed_or_partial' | 'insufficient_evidence' | string;
  leadershipConcentration?: {
    state?: 'balanced' | 'moderate' | 'concentrated' | 'unknown' | string;
    percent?: number | null;
    broadParticipationPercent?: number | null;
    topMembers?: string[];
  };
  correlationEvidence?: {
    state?: 'aligned' | 'mixed' | 'weak' | 'missing' | string;
    sameDirectionPercent?: number | null;
    aboveVwapPercent?: number | null;
    persistencePercent?: number | null;
  };
  breadthEvidence?: {
    state?: 'broad' | 'mixed' | 'thin' | 'missing' | string;
    observedMembers?: number | null;
    configuredMembers?: number | null;
    coveragePercent?: number | null;
    percentUp?: number | null;
    percentOutperformingBenchmark?: number | null;
  };
  staleInputs?: string[];
  missingInputs?: string[];
  observationBoundary?: {
    scope?: string;
    rankingImpact?: string;
    dataMutation?: string;
    dataFetches?: string;
    [key: string]: unknown;
  };
  researchNextSteps?: string[];
};

export type MarketRotationTheme = MarketRotationSummaryItem & {
  rotationStateEvidence?: Record<string, unknown> | null;
  themeCorrelationBreadthSnapshot?: MarketRotationThemeCorrelationBreadthSnapshot | null;
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
    rotationFamilyRollup?: MarketRotationFamilyRollupItem[];
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
  consumerEvidenceSnapshot?: MarketRotationConsumerEvidenceSnapshot;
  alpacaQuoteAuthorityReadiness?: MarketRotationAlpacaQuoteAuthorityReadiness;
  metadata: Record<string, unknown>;
};

function normalizeRotationFamilyRollupItem(
  item?: MarketRotationFamilyRollupItem | null,
): MarketRotationFamilyRollupItem | null {
  if (!item || typeof item !== 'object') {
    return null;
  }
  return {
    familyId: item.familyId,
    familyName: item.familyName,
    themeIds: Array.isArray(item.themeIds) ? item.themeIds.filter(Boolean) : [],
    themeNames: Array.isArray(item.themeNames) ? item.themeNames.filter(Boolean) : [],
    leaderThemeIds: Array.isArray(item.leaderThemeIds) ? item.leaderThemeIds.filter(Boolean) : [],
    themeCount: item.themeCount,
    signalThemeCount: item.signalThemeCount,
    averageRotationScore: item.averageRotationScore,
    averageConfidence: item.averageConfidence,
    themeFlowSignal: item.themeFlowSignal || undefined,
  };
}

function normalizeRotationConsumerEvidenceSnapshot(
  snapshot?: MarketRotationConsumerEvidenceSnapshot | null,
): MarketRotationConsumerEvidenceSnapshot | undefined {
  if (!snapshot || typeof snapshot !== 'object') {
    return undefined;
  }
  return {
    market: snapshot.market,
    generatedAt: snapshot.generatedAt || null,
    asOf: snapshot.asOf || null,
    freshness: snapshot.freshness,
    isFallback: snapshot.isFallback === true,
    isStale: snapshot.isStale === true,
    isPartial: snapshot.isPartial === true,
    ...(typeof snapshot.authorityGrant === 'boolean' ? { authorityGrant: snapshot.authorityGrant } : {}),
    headlineEligibleThemeCount: snapshot.headlineEligibleThemeCount,
    observationThemeCount: snapshot.observationThemeCount,
    taxonomyThemeCount: snapshot.taxonomyThemeCount,
    scoreContributionAllowed: snapshot.scoreContributionAllowed === true,
    reasonCodes: Array.isArray(snapshot.reasonCodes) ? snapshot.reasonCodes.filter(Boolean) : [],
    providerState: snapshot.providerState
      ? {
        ...snapshot.providerState,
        coverage: snapshot.providerState.coverage ? { ...snapshot.providerState.coverage } : undefined,
      }
      : undefined,
    etfProxySummary: snapshot.etfProxySummary
      ? {
        ...snapshot.etfProxySummary,
        leadingSymbols: Array.isArray(snapshot.etfProxySummary.leadingSymbols)
          ? snapshot.etfProxySummary.leadingSymbols.filter(Boolean)
          : [],
        laggingSymbols: Array.isArray(snapshot.etfProxySummary.laggingSymbols)
          ? snapshot.etfProxySummary.laggingSymbols.filter(Boolean)
          : [],
        reasonCodes: Array.isArray(snapshot.etfProxySummary.reasonCodes)
          ? snapshot.etfProxySummary.reasonCodes.filter(Boolean)
          : [],
      }
      : undefined,
    themes: Array.isArray(snapshot.themes)
      ? snapshot.themes.map((theme) => ({
        ...theme,
        dataGaps: Array.isArray(theme.dataGaps) ? theme.dataGaps.filter(Boolean) : [],
      }))
      : [],
    rotationFamilyRollup: Array.isArray(snapshot.rotationFamilyRollup)
      ? snapshot.rotationFamilyRollup
        .map((item) => normalizeRotationFamilyRollupItem(item))
        .filter((item): item is MarketRotationFamilyRollupItem => Boolean(item))
      : [],
  };
}

function normalizeAlpacaQuoteAuthorityReadiness(
  readiness?: MarketRotationAlpacaQuoteAuthorityReadiness | null,
): MarketRotationAlpacaQuoteAuthorityReadiness | undefined {
  if (!readiness || typeof readiness !== 'object') {
    return undefined;
  }
  return {
    providerConfigured: readiness.providerConfigured,
    dataFeed: readiness.dataFeed || null,
    probeSymbols: Array.isArray(readiness.probeSymbols) ? readiness.probeSymbols.filter(Boolean) : [],
    quoteCoverage: readiness.quoteCoverage
      ? {
        covered: readiness.quoteCoverage.covered,
        total: readiness.quoteCoverage.total,
        ratio: readiness.quoteCoverage.ratio,
        missingSymbols: Array.isArray(readiness.quoteCoverage.missingSymbols)
          ? readiness.quoteCoverage.missingSymbols.filter(Boolean)
          : [],
      }
      : undefined,
    freshestAsOf: readiness.freshestAsOf || null,
    sourceAuthority: readiness.sourceAuthority || 'unknown',
    fallbackUsed: readiness.fallbackUsed === true,
    blockerBucket: readiness.blockerBucket || null,
    consumerSummary: readiness.consumerSummary || null,
    nextDataAction: readiness.nextDataAction || null,
    scoreContributionAllowed: readiness.scoreContributionAllowed,
  };
}

export function buildAlpacaQuoteAuthorityReadinessView(
  readiness?: MarketRotationAlpacaQuoteAuthorityReadiness | null,
): MarketRotationAlpacaQuoteAuthorityReadinessView {
  if (!readiness) {
    return {
      label: '来源待确认',
      variant: 'neutral',
      chips: [{ key: 'readiness', label: '来源待确认', variant: 'neutral' }],
      detail: 'ETF 引用状态待确认，当前先保持观察。',
    };
  }

  const state = readiness.sourceAuthority;
  const primary = state === 'authorized' && readiness.providerConfigured !== false
    ? { label: 'ETF引用可用', variant: 'success' as const }
    : state === 'partial'
      ? { label: 'ETF引用部分可用', variant: 'info' as const }
      : state === 'unavailable' || readiness.providerConfigured === false
        ? { label: 'ETF引用待补', variant: 'caution' as const }
        : { label: '来源待确认', variant: 'neutral' as const };

  const limited = readiness.fallbackUsed === true || readiness.scoreContributionAllowed === false;
  const chips = [
    { key: 'readiness', label: primary.label, variant: primary.variant },
    ...(readiness.fallbackUsed ? [{ key: 'fallback', label: '备用样本观察', variant: 'caution' as const }] : []),
    ...(limited ? [{ key: 'limited', label: '仅观察', variant: 'neutral' as const }] : []),
  ];

  return {
    label: primary.label,
    variant: primary.variant,
    chips,
    detail: limited ? '当前仅作观察，不纳入评分。' : 'ETF 引用状态可用于主题强弱观察。',
  };
}

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
        rotationFamilyRollup: Array.isArray(normalized.summary?.rotationFamilyRollup)
          ? normalized.summary.rotationFamilyRollup
            .map((item) => normalizeRotationFamilyRollupItem(item))
            .filter((item): item is MarketRotationFamilyRollupItem => Boolean(item))
          : [],
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
      consumerEvidenceSnapshot: normalizeRotationConsumerEvidenceSnapshot(normalized.consumerEvidenceSnapshot),
      alpacaQuoteAuthorityReadiness: normalizeAlpacaQuoteAuthorityReadiness(
        normalized.alpacaQuoteAuthorityReadiness
        || (normalized.metadata?.alpacaQuoteAuthorityReadiness as MarketRotationAlpacaQuoteAuthorityReadiness | undefined),
      ),
      metadata: normalized.metadata || {},
    };
  },
};
