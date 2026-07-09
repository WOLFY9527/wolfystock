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
  /** Measured rotation score. Null means unavailable, not observed zero. */
  rotationScore: number | null;
  /** Measured confidence in [0,1]. Null means unavailable, not observed zero. */
  confidence: number | null;
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

export type MarketRotationQuoteCoverageSymbol = {
  symbol?: string;
  configured?: boolean;
  quoteAvailable?: boolean;
  missing?: boolean;
  stale?: boolean;
  freshness?: string | null;
  asOf?: string | null;
  sourceAuthorityAllowed?: boolean;
  scoreContributionAllowed?: boolean;
  fallbackOrLimitedSampleUsed?: boolean;
  sourceFamily?: string;
  providerClass?: string;
  reasonCodes?: string[];
  windowsFulfilled?: string[];
  missingWindows?: string[];
};

export type MarketRotationQuoteCoverageFamily = {
  familyId?: string;
  familyLabel?: string;
  configuredSymbols?: string[];
  availableSymbols?: string[];
  missingSymbols?: string[];
  staleSymbols?: string[];
  scoreAuthorityAllowedSymbols?: string[];
  observationOnlySymbols?: string[];
  configuredCount?: number;
  availableCount?: number;
  missingCount?: number;
  staleCount?: number;
  scoreAuthorityAllowedCount?: number;
  observationOnlyCount?: number;
  fallbackOrLimitedSampleUsed?: boolean;
  symbols?: MarketRotationQuoteCoverageSymbol[];
};

export type MarketRotationQuoteCoverageSummary = {
  configuredCount?: number;
  availableCount?: number;
  missingCount?: number;
  staleCount?: number;
  scoreAuthorityAllowedCount?: number;
  observationOnlyCount?: number;
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
  quoteCoverageByFamily?: MarketRotationQuoteCoverageFamily[];
  coverageSummary?: MarketRotationQuoteCoverageSummary;
  availableSymbols?: string[];
  missingSymbols?: string[];
  staleSymbols?: string[];
  scoreAuthorityAllowedSymbols?: string[];
  observationOnlySymbols?: string[];
  freshestAsOf?: string | null;
  sourceAuthority?: 'authorized' | 'partial' | 'unavailable' | 'unknown' | string;
  fallbackUsed?: boolean;
  blockerBucket?: string | null;
  consumerSummary?: string | null;
  nextDataAction?: string | null;
  scoreContributionAllowed?: boolean;
};

type MarketRotationQuoteReadinessVariant = 'success' | 'info' | 'caution' | 'neutral';

export type MarketRotationQuoteCoverageFamilyView = {
  key: string;
  label: string;
  statusLabel: string;
  variant: MarketRotationQuoteReadinessVariant;
  countsLabel: string;
  scoringLabel: string;
};

export type MarketRotationAlpacaQuoteAuthorityReadinessView = {
  label: string;
  variant: MarketRotationQuoteReadinessVariant;
  chips: Array<{
    key: string;
    label: string;
    variant: MarketRotationQuoteReadinessVariant;
  }>;
  detail: string;
  summaryItems: string[];
  familyRows: MarketRotationQuoteCoverageFamilyView[];
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

function normalizeQuoteCoverageFamily(
  family?: MarketRotationQuoteCoverageFamily | null,
): MarketRotationQuoteCoverageFamily | undefined {
  if (!family || typeof family !== 'object') {
    return undefined;
  }
  return {
    ...family,
    configuredSymbols: Array.isArray(family.configuredSymbols) ? family.configuredSymbols.filter(Boolean) : [],
    availableSymbols: Array.isArray(family.availableSymbols) ? family.availableSymbols.filter(Boolean) : [],
    missingSymbols: Array.isArray(family.missingSymbols) ? family.missingSymbols.filter(Boolean) : [],
    staleSymbols: Array.isArray(family.staleSymbols) ? family.staleSymbols.filter(Boolean) : [],
    scoreAuthorityAllowedSymbols: Array.isArray(family.scoreAuthorityAllowedSymbols)
      ? family.scoreAuthorityAllowedSymbols.filter(Boolean)
      : [],
    observationOnlySymbols: Array.isArray(family.observationOnlySymbols)
      ? family.observationOnlySymbols.filter(Boolean)
      : [],
    symbols: Array.isArray(family.symbols)
      ? family.symbols.map((row) => ({
        ...row,
        reasonCodes: Array.isArray(row.reasonCodes) ? row.reasonCodes.filter(Boolean) : [],
        windowsFulfilled: Array.isArray(row.windowsFulfilled) ? row.windowsFulfilled.filter(Boolean) : [],
        missingWindows: Array.isArray(row.missingWindows) ? row.missingWindows.filter(Boolean) : [],
      }))
      : [],
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
    quoteCoverageByFamily: Array.isArray(readiness.quoteCoverageByFamily)
      ? readiness.quoteCoverageByFamily
        .map((family) => normalizeQuoteCoverageFamily(family))
        .filter((family): family is MarketRotationQuoteCoverageFamily => Boolean(family))
      : [],
    coverageSummary: readiness.coverageSummary ? { ...readiness.coverageSummary } : undefined,
    availableSymbols: Array.isArray(readiness.availableSymbols) ? readiness.availableSymbols.filter(Boolean) : [],
    missingSymbols: Array.isArray(readiness.missingSymbols) ? readiness.missingSymbols.filter(Boolean) : [],
    staleSymbols: Array.isArray(readiness.staleSymbols) ? readiness.staleSymbols.filter(Boolean) : [],
    scoreAuthorityAllowedSymbols: Array.isArray(readiness.scoreAuthorityAllowedSymbols)
      ? readiness.scoreAuthorityAllowedSymbols.filter(Boolean)
      : [],
    observationOnlySymbols: Array.isArray(readiness.observationOnlySymbols)
      ? readiness.observationOnlySymbols.filter(Boolean)
      : [],
    freshestAsOf: readiness.freshestAsOf || null,
    sourceAuthority: readiness.sourceAuthority || 'unknown',
    fallbackUsed: readiness.fallbackUsed === true,
    blockerBucket: readiness.blockerBucket || null,
    consumerSummary: readiness.consumerSummary || null,
    nextDataAction: readiness.nextDataAction || null,
    scoreContributionAllowed: readiness.scoreContributionAllowed,
  };
}

function safeCount(value: unknown, defaultValue = 0): number {
  if (value === undefined || value === null || value === '') {
    return defaultValue;
  }
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric >= 0 ? Math.round(numeric) : defaultValue;
}

function countSymbols(values?: string[]): number {
  return Array.isArray(values) ? values.filter(Boolean).length : 0;
}

function summarizeQuoteCoverage(readiness?: MarketRotationAlpacaQuoteAuthorityReadiness | null): Required<MarketRotationQuoteCoverageSummary> {
  const families = Array.isArray(readiness?.quoteCoverageByFamily) ? readiness.quoteCoverageByFamily : [];
  const summary = readiness?.coverageSummary || {};
  const familyTotals = families.reduce<Required<MarketRotationQuoteCoverageSummary>>(
    (acc, family) => ({
      configuredCount: acc.configuredCount + safeCount(family.configuredCount, countSymbols(family.configuredSymbols)),
      availableCount: acc.availableCount + safeCount(family.availableCount, countSymbols(family.availableSymbols)),
      missingCount: acc.missingCount + safeCount(family.missingCount, countSymbols(family.missingSymbols)),
      staleCount: acc.staleCount + safeCount(family.staleCount, countSymbols(family.staleSymbols)),
      scoreAuthorityAllowedCount: acc.scoreAuthorityAllowedCount
        + safeCount(family.scoreAuthorityAllowedCount, countSymbols(family.scoreAuthorityAllowedSymbols)),
      observationOnlyCount: acc.observationOnlyCount
        + safeCount(family.observationOnlyCount, countSymbols(family.observationOnlySymbols)),
    }),
    {
      configuredCount: 0,
      availableCount: 0,
      missingCount: 0,
      staleCount: 0,
      scoreAuthorityAllowedCount: 0,
      observationOnlyCount: 0,
    },
  );
  return {
    configuredCount: safeCount(summary.configuredCount, familyTotals.configuredCount),
    availableCount: safeCount(summary.availableCount, familyTotals.availableCount),
    missingCount: safeCount(
      summary.missingCount,
      familyTotals.missingCount || countSymbols(readiness?.missingSymbols) || countSymbols(readiness?.quoteCoverage?.missingSymbols),
    ),
    staleCount: safeCount(summary.staleCount, familyTotals.staleCount || countSymbols(readiness?.staleSymbols)),
    scoreAuthorityAllowedCount: safeCount(
      summary.scoreAuthorityAllowedCount,
      familyTotals.scoreAuthorityAllowedCount || countSymbols(readiness?.scoreAuthorityAllowedSymbols),
    ),
    observationOnlyCount: safeCount(
      summary.observationOnlyCount,
      familyTotals.observationOnlyCount || countSymbols(readiness?.observationOnlySymbols),
    ),
  };
}

function quoteCoverageFamilyLabel(family?: MarketRotationQuoteCoverageFamily | null): string {
  switch (family?.familyId) {
    case 'broad_us_market':
      return '大盘代理覆盖';
    case 'sector_etfs':
      return '行业ETF覆盖';
    case 'volatility_risk':
      return '风险代理覆盖';
    default:
      return '代理覆盖';
  }
}

function quoteCoverageFamilyStatus(
  family: MarketRotationQuoteCoverageFamily,
): { label: string; variant: MarketRotationQuoteReadinessVariant } {
  const configuredCount = safeCount(family.configuredCount, countSymbols(family.configuredSymbols));
  const availableCount = safeCount(family.availableCount, countSymbols(family.availableSymbols));
  const missingCount = safeCount(family.missingCount, countSymbols(family.missingSymbols));
  const staleCount = safeCount(family.staleCount, countSymbols(family.staleSymbols));
  const scoreCount = safeCount(family.scoreAuthorityAllowedCount, countSymbols(family.scoreAuthorityAllowedSymbols));
  const observationCount = safeCount(family.observationOnlyCount, countSymbols(family.observationOnlySymbols));
  const limited = missingCount > 0 || staleCount > 0 || observationCount > 0 || scoreCount < configuredCount;
  if (configuredCount <= 0 || availableCount <= 0 || missingCount >= configuredCount) {
    return { label: '报价待补', variant: 'caution' };
  }
  if (family.familyId === 'sector_etfs') {
    return limited ? { label: 'ETF引用部分可用', variant: 'info' } : { label: 'ETF引用可用', variant: 'success' };
  }
  if (limited || scoreCount < configuredCount) {
    return { label: '代理覆盖有限', variant: 'caution' };
  }
  return { label: '代理覆盖可用', variant: 'success' };
}

function buildQuoteCoverageFamilyRows(
  readiness?: MarketRotationAlpacaQuoteAuthorityReadiness | null,
): MarketRotationQuoteCoverageFamilyView[] {
  const families = Array.isArray(readiness?.quoteCoverageByFamily) ? readiness.quoteCoverageByFamily : [];
  return families.map((family) => {
    const configuredCount = safeCount(family.configuredCount, countSymbols(family.configuredSymbols));
    const availableCount = safeCount(family.availableCount, countSymbols(family.availableSymbols));
    const missingCount = safeCount(family.missingCount, countSymbols(family.missingSymbols));
    const staleCount = safeCount(family.staleCount, countSymbols(family.staleSymbols));
    const scoreCount = safeCount(family.scoreAuthorityAllowedCount, countSymbols(family.scoreAuthorityAllowedSymbols));
    const observationCount = safeCount(family.observationOnlyCount, countSymbols(family.observationOnlySymbols));
    const status = quoteCoverageFamilyStatus(family);
    const availableLabel = family.familyId === 'sector_etfs' ? 'ETF引用可用' : '代理覆盖可用';
    return {
      key: family.familyId || quoteCoverageFamilyLabel(family),
      label: quoteCoverageFamilyLabel(family),
      statusLabel: status.label,
      variant: status.variant,
      countsLabel: `${availableLabel} ${availableCount}/${configuredCount} · 报价待补 ${missingCount} · 报价可能延迟 ${staleCount}`,
      scoringLabel: scoreCount > 0
        ? `评分可用 ${scoreCount} · 仅观察 ${observationCount}`
        : `评分待确认 · 仅观察 ${observationCount}`,
    };
  });
}

function uniqueReadinessChips(
  chips: MarketRotationAlpacaQuoteAuthorityReadinessView['chips'],
): MarketRotationAlpacaQuoteAuthorityReadinessView['chips'] {
  const seen = new Set<string>();
  return chips.filter((chip) => {
    if (seen.has(chip.label)) {
      return false;
    }
    seen.add(chip.label);
    return true;
  });
}

export function buildAlpacaQuoteAuthorityReadinessView(
  readiness?: MarketRotationAlpacaQuoteAuthorityReadiness | null,
): MarketRotationAlpacaQuoteAuthorityReadinessView {
  const coverage = summarizeQuoteCoverage(readiness);
  const summaryItems = [
    `报价待补 ${coverage.missingCount}`,
    `报价可能延迟 ${coverage.staleCount}`,
    `评分可用 ${coverage.scoreAuthorityAllowedCount}`,
    `仅观察 ${coverage.observationOnlyCount}`,
  ];
  const familyRows = buildQuoteCoverageFamilyRows(readiness);

  if (!readiness) {
    return {
      label: 'ETF引用待补',
      variant: 'caution',
      chips: [
        { key: 'readiness', label: 'ETF引用待补', variant: 'caution' },
        { key: 'missing', label: '报价待补', variant: 'caution' },
        { key: 'score', label: '评分待确认', variant: 'neutral' },
      ],
      detail: 'ETF 引用状态待补，当前先保持观察。',
      summaryItems,
      familyRows,
    };
  }

  const state = readiness.sourceAuthority;
  const primary = state === 'authorized' && readiness.providerConfigured !== false
    ? { label: 'ETF引用可用', variant: 'success' as const }
    : state === 'partial'
      ? { label: 'ETF引用部分可用', variant: 'info' as const }
      : state === 'unavailable' || readiness.providerConfigured === false
        ? { label: 'ETF引用待补', variant: 'caution' as const }
        : { label: 'ETF引用待补', variant: 'neutral' as const };

  const limited = readiness.scoreContributionAllowed === false
    || coverage.observationOnlyCount > 0
    || familyRows.some((family) => family.statusLabel === '代理覆盖有限');
  const chips = uniqueReadinessChips([
    { key: 'readiness', label: primary.label, variant: primary.variant },
    ...(limited ? [{ key: 'limitedCoverage', label: '代理覆盖有限', variant: 'caution' as const }] : []),
    ...(coverage.staleCount > 0 ? [{ key: 'stale', label: '报价可能延迟', variant: 'caution' as const }] : []),
    ...(limited ? [{ key: 'limited', label: '仅观察', variant: 'neutral' as const }] : []),
    {
      key: 'score',
      label: coverage.scoreAuthorityAllowedCount > 0 && readiness.scoreContributionAllowed !== false
        ? '评分可用'
        : '评分待确认',
      variant: coverage.scoreAuthorityAllowedCount > 0 && readiness.scoreContributionAllowed !== false ? 'success' as const : 'neutral' as const,
    },
  ]);

  return {
    label: primary.label,
    variant: primary.variant,
    chips,
    detail: limited ? '当前仅作观察，不纳入评分。' : 'ETF 引用状态可用于主题强弱观察。',
    summaryItems,
    familyRows,
  };
}

export type MarketRotationEvidenceBoundaryChip = {
  key: string;
  label: string;
  variant: 'success' | 'info' | 'caution' | 'neutral';
};

export type MarketRotationEvidenceBoundaryView = {
  label: string;
  variant: 'success' | 'info' | 'caution' | 'neutral';
  chips: MarketRotationEvidenceBoundaryChip[];
  nextEvidence: string;
  note?: string;
};

const ROTATION_BOUNDARY_SAMPLE_TOKENS = ['demo', 'sample', 'fixture', 'synthetic', 'mock', 'static'];

function normalizeRotationBoundaryToken(value?: string | null): string {
  return String(value || '').replace(/\s+/g, ' ').trim().toLowerCase();
}

function rotationBoundaryHasSampleToken(value?: string | null): boolean {
  const normalized = normalizeRotationBoundaryToken(value);
  return ROTATION_BOUNDARY_SAMPLE_TOKENS.some((token) => normalized.includes(token));
}

function rotationBoundaryLabel(
  readiness: MarketRotationAlpacaQuoteAuthorityReadinessView,
  payload?: MarketRotationRadarResponse | null,
): MarketRotationEvidenceBoundaryView {
  if (!payload) {
    return {
      label: '证据边界待确认',
      variant: 'neutral',
      chips: [
        { key: 'boundary', label: '证据边界待确认', variant: 'neutral' },
        { key: 'broad', label: '广度待补', variant: 'neutral' },
        { key: 'sector', label: '板块轮动待补', variant: 'neutral' },
        { key: 'risk', label: '风险状态待补', variant: 'neutral' },
      ],
      nextEvidence: '继续观察现有证据。',
      note: readiness.detail,
    };
  }

  const snapshot = payload?.consumerEvidenceSnapshot;
  const providerState = snapshot?.providerState;
  const sampleLike = [
    payload?.source,
    payload?.sourceLabel,
    providerState?.quoteMode,
    providerState?.status,
    providerState?.sourceType,
    providerState?.sourceTier,
    providerState?.providerTier,
    snapshot?.etfProxySummary?.label,
    ...(Array.isArray(snapshot?.reasonCodes) ? snapshot.reasonCodes : []),
  ].some((value) => rotationBoundaryHasSampleToken(value));

  const stale = payload?.isStale === true
    || snapshot?.isStale === true
    || payload?.freshness === 'stale'
    || readiness.familyRows.some((row) => row.statusLabel.includes('待更新'));
  const fallback = payload?.isFallback === true
    || snapshot?.isFallback === true
    || payload?.freshness === 'fallback';
  const limited = readiness.label !== 'ETF引用可用'
    || readiness.chips.some((chip) => chip.label === '仅观察' || chip.label === '代理覆盖有限' || chip.label === '报价可能延迟');
  const missing = readiness.label === 'ETF引用待补';
  const partial = snapshot?.isPartial === true
    || snapshot?.scoreContributionAllowed === false
    || readiness.label === 'ETF引用部分可用';

  const broadRow = readiness.familyRows.find((row) => row.label === '大盘代理覆盖');
  const sectorRow = readiness.familyRows.find((row) => row.label === '行业ETF覆盖');
  const riskRow = readiness.familyRows.find((row) => row.label === '风险代理覆盖');
  const broadChipLabel = `${broadRow?.label || '广度覆盖'} · ${broadRow?.statusLabel || '待补'}`;
  const sectorChipLabel = `${sectorRow?.label || '板块轮动'} · ${sectorRow?.statusLabel || '待补'}`;
  const riskChipLabel = `${riskRow?.label || '风险状态'} · ${riskRow?.statusLabel || '待补'}`;

  if (sampleLike) {
    return {
      label: '演示样本，仅观察',
      variant: 'neutral',
      chips: [
        { key: 'boundary', label: '演示样本，仅观察', variant: 'neutral' },
        { key: 'broad', label: broadChipLabel, variant: 'neutral' },
        { key: 'sector', label: sectorChipLabel, variant: 'neutral' },
        { key: 'risk', label: riskChipLabel, variant: 'neutral' },
      ],
      nextEvidence: '仅保留观察，不升格结论。',
      note: readiness.detail,
    };
  }

  if (stale) {
    return {
      label: '待更新',
      variant: 'caution',
      chips: [
        { key: 'boundary', label: '待更新', variant: 'caution' },
        { key: 'broad', label: broadChipLabel, variant: 'caution' },
        { key: 'sector', label: sectorChipLabel, variant: 'caution' },
        { key: 'risk', label: riskChipLabel, variant: 'caution' },
      ],
      nextEvidence: '下一步：更新广度、轮动和风险代理覆盖。',
      note: payload?.freshness === 'stale' ? '当前数据已过时，继续观察新快照。' : readiness.detail,
    };
  }

  if (fallback || missing || partial || limited) {
    const boundaryLabel = missing ? '待补' : partial ? '部分可用' : '仅观察';
    const boundaryVariant = missing ? 'caution' as const : partial ? 'info' as const : 'neutral' as const;
    const chips: MarketRotationEvidenceBoundaryChip[] = [
      { key: 'boundary', label: boundaryLabel, variant: boundaryVariant },
      { key: 'broad', label: broadChipLabel, variant: 'neutral' },
      { key: 'sector', label: sectorChipLabel, variant: 'neutral' },
      { key: 'risk', label: riskChipLabel, variant: 'neutral' },
    ];
    if (payload?.isFallback || snapshot?.isFallback) {
      chips.push({ key: 'freshness', label: '最近一次可用', variant: 'info' });
    }
    if (readiness.chips.some((chip) => chip.label === '仅观察')) {
      chips.push({ key: 'observe', label: '仅观察', variant: 'neutral' });
    }
    return {
      label: boundaryLabel,
      variant: boundaryVariant,
      chips,
      nextEvidence: missing
        ? '下一步：补齐报价覆盖与风险代理。'
        : '继续观察现有证据。',
      note: readiness.detail,
    };
  }

  return {
    label: '证据可用',
    variant: 'success',
    chips: [
      { key: 'boundary', label: '证据可用', variant: 'success' },
      { key: 'broad', label: broadChipLabel.replace('待补', '可用'), variant: 'success' },
      { key: 'sector', label: sectorChipLabel.replace('待补', '可用'), variant: 'success' },
      { key: 'risk', label: riskChipLabel.replace('待补', '可用'), variant: 'success' },
    ],
    nextEvidence: '继续观察广度、轮动和风险代理变化。',
    note: readiness.detail,
  };
}

export function buildMarketRotationEvidenceBoundaryView(
  payload?: MarketRotationRadarResponse | null,
): MarketRotationEvidenceBoundaryView {
  const readiness = buildAlpacaQuoteAuthorityReadinessView(payload?.alpacaQuoteAuthorityReadiness);
  return rotationBoundaryLabel(readiness, payload);
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
